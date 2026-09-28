// Optional Windows end-to-end smoke test using installed Edge and Node 24.
// Requires port 5173 and the sibling frontend's installed packages.
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdtemp, readFile, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import net from 'node:net'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = path.dirname(fileURLToPath(import.meta.url))
const frontend = path.resolve(root, '../DataQualiQ1')
const temp = await mkdtemp(path.join(tmpdir(), 'dataqualiq-smoke-'))
const delay = ms => new Promise(resolve => setTimeout(resolve, ms))
async function until(fn, label) {
  const deadline = Date.now() + 30000
  while (Date.now() < deadline) {
    try { const value = await fn(); if (value) return value } catch {}
    await delay(100)
  }
  throw new Error(`Timed out: ${label}`)
}
let backend, browser, server, ws
try {
  const portProbe = net.createServer()
  await new Promise(resolve => portProbe.listen(0, '127.0.0.1', resolve))
  const apiPort = portProbe.address().port
  await new Promise(resolve => portProbe.close(resolve))
  backend = spawn(path.join(root, 'venv/Scripts/python.exe'), ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', String(apiPort)], { cwd: root, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
  let backendLog = ''
  backend.stderr.on('data', chunk => { backendLog += chunk })
  await until(async () => (await fetch(`http://127.0.0.1:${apiPort}/health`)).ok, `backend startup: ${backendLog}`)
  const { createServer } = await import(pathToFileURL(path.join(frontend, 'node_modules/vite/dist/node/index.js')))
  server = await createServer({ root: frontend, server: { host: '127.0.0.1', port: 5173, strictPort: true } })
  await server.listen()
  const edge = process.env.EDGE_PATH || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
  browser = spawn(edge, ['--headless=new', '--no-first-run', '--disable-gpu', '--remote-debugging-port=0', `--user-data-dir=${temp}`, 'about:blank'], { windowsHide: true, stdio: 'ignore' })
  const port = await until(async () => (await readFile(path.join(temp, 'DevToolsActivePort'), 'utf8')).split('\n')[0], 'Edge startup')
  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()
  ws = new WebSocket(targets.find(target => target.type === 'page').webSocketDebuggerUrl)
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject })
  let id = 0
  const pending = new Map()
  const exceptions = []
  ws.onmessage = event => {
    const message = JSON.parse(event.data)
    if (message.method === 'Fetch.requestPaused') {
      // Route only this browser's API request to the fresh test service.
      // Existing services on port 8000 and frontend source remain untouched.
      call('Fetch.continueRequest', { requestId: message.params.requestId,
        url: message.params.request.url.replace('http://localhost:8000', `http://127.0.0.1:${apiPort}`) }).catch(error => exceptions.push(error.message))
    }
    if (message.method === 'Runtime.exceptionThrown') exceptions.push(message.params.exceptionDetails.text)
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id)
      pending.delete(message.id)
      message.error ? reject(new Error(JSON.stringify(message.error))) : resolve(message.result)
    }
  }
  const call = (method, params = {}) => new Promise((resolve, reject) => {
    const current = ++id
    const timer = setTimeout(() => { pending.delete(current); reject(new Error(`CDP timeout: ${method}`)) }, 15000)
    pending.set(current, {
      resolve: value => { clearTimeout(timer); resolve(value) },
      reject: error => { clearTimeout(timer); reject(error) },
    })
    ws.send(JSON.stringify({ id: current, method, params }))
  })
  const evaluate = async expression => {
    const result = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails))
    return result.result.value
  }
  await call('Runtime.enable')
  await call('Fetch.enable', { patterns: [{ urlPattern: 'http://localhost:8000/*' }] })
  await call('Page.enable')
  await call('Page.navigate', { url: 'http://127.0.0.1:5173' })
  await until(() => evaluate("!!document.querySelector('input[type=file]')"), 'upload page')
  async function upload(file) {
    const { root: document } = await call('DOM.getDocument')
    const { nodeId } = await call('DOM.querySelector', { nodeId: document.nodeId, selector: 'input[type=file]' })
    await call('DOM.setFileInputFiles', { nodeId, files: [file] })
    await until(() => evaluate(`document.body.innerText.includes(${JSON.stringify(path.basename(file))})`), 'selected file')
    await evaluate("[...document.querySelectorAll('button')].find(b => b.textContent.includes('Run Assessment')).click()")
  }
  await upload(path.join(root, 'sample_data/customers_raw.csv'))
  const assessment = await until(() => evaluate("JSON.parse(sessionStorage.getItem('assessmentResult'))"), 'assessment result')
  assert.equal(assessment.total_rows, 10)
  await until(() => evaluate("document.body.innerText.includes('Issues to review')"), 'rendered evidence controls')
  assert.ok(await evaluate("document.body.innerText.includes('Heuristic score')"), 'honest score label')
  const severity = assessment.translated_issues[0].issue_to_review.severity
  const badgeColors = { high: 'rgb(252, 235, 235)', medium: 'rgb(255, 247, 237)', low: 'rgb(225, 245, 238)' }
  assert.ok(await evaluate(`[...document.querySelectorAll('span')].some(s => s.textContent.toLowerCase() === ${JSON.stringify(severity)} && getComputedStyle(s).backgroundColor === ${JSON.stringify(badgeColors[severity])})`), 'Severity must select its existing badge color')
  for (const tab of ['By field', 'Issues', 'Actions', 'Overview']) {
    await evaluate(`[...document.querySelectorAll('nav button')].find(s => s.textContent.trim() === ${JSON.stringify(tab)}).click()`)
    await delay(150)
    assert.ok(await evaluate("document.body.innerText.length > 100"), `${tab} renders`)
  }
  await evaluate("[...document.querySelectorAll('header button')].find(s => s.textContent.trim() === 'Upload').click()")
  await until(() => evaluate("!!document.querySelector('input[type=file]')"), 'upload unfamiliar data')
  await upload(path.join(root, 'sample_data/generalisation/spectrometry.csv'))
  const unfamiliar = await until(() => evaluate("JSON.parse(sessionStorage.getItem('assessmentResult'))"), 'unfamiliar result')
  assert.equal(unfamiliar.dataset_context.name, 'unknown')
  assert.ok(unfamiliar.issues.some(i => i.check === 'repeated_identifier'))
  assert.ok(unfamiliar.translated_issues.every((issue, i, all) => i === 0 ||
    all[i-1].issue_to_review.evidence.priority_score >= issue.issue_to_review.evidence.priority_score))
  await until(() => evaluate("document.body.innerText.includes('Issues to review')"), 'unfamiliar evidence')
  await call('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: temp })
  await evaluate("[...document.querySelectorAll('button')].find(b => b.textContent.includes('Download full report')).click()")
  await until(async () => (await readFile(path.join(temp, 'spectrometry-assessment.pdf'))).subarray(0, 4).toString() === '%PDF', 'PDF export')
  await evaluate("[...document.querySelectorAll('header button')].find(s => s.textContent.trim() === 'Upload').click()")
  await until(() => evaluate("!!document.querySelector('input[type=file]')"), 'return to upload')
  const malformed = path.join(temp, 'malformed.csv')
  await writeFile(malformed, 'a,b\n1,2,3\n')
  await upload(malformed)
  await until(() => evaluate("document.body.innerText.includes('Assessment failed: Malformed CSV')"), 'visible backend error')
  assert.equal(await evaluate("sessionStorage.getItem('assessmentResult')"), null)
  assert.equal(exceptions.length, 0, `Uncaught browser errors: ${exceptions}`)
  console.log('PASS: sample and unfamiliar CSV uploads, severity badge, priority order, four dashboard tabs, PDF export, malformed-upload error, no uncaught exceptions.')
} finally {
  ws?.close()
  browser?.kill()
  backend?.kill()
  await Promise.race([server?.close(), delay(3000)])
  // Keep the isolated profile under the OS temp directory for troubleshooting.
}
