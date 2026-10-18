// Windows/Edge integration checks for the consolidated traffic dashboard.
// Uses the existing backend environment without changing backend source files.
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdtemp, readFile, writeFile, mkdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import net from 'node:net'
import { fileURLToPath, pathToFileURL } from 'node:url'

const frontend = path.dirname(fileURLToPath(import.meta.url))
const backendRoot = path.resolve(frontend, '../backend')
const temp = await mkdtemp(path.join(tmpdir(), 'dataqualiq-dashboard-'))
const delay = ms => new Promise(resolve => setTimeout(resolve, ms))
async function until(fn, label) {
  const deadline = Date.now() + 45000
  while (Date.now() < deadline) {
    try { const value = await fn(); if (value) return value } catch {}
    await delay(100)
  }
  throw new Error('Timed out: ' + label)
}
async function freePort() {
  const probe = net.createServer()
  await new Promise(resolve => probe.listen(0, '127.0.0.1', resolve))
  const port = probe.address().port
  await new Promise(resolve => probe.close(resolve))
  return port
}
let backend, browser, server, ws
try {
  const apiPort = await freePort()
  backend = spawn(path.join(backendRoot, 'venv/Scripts/python.exe'), ['-B', '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', String(apiPort)], { cwd: backendRoot, windowsHide: true, env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' }, stdio: ['ignore', 'pipe', 'pipe'] })
  let backendLog = ''
  backend.stderr.on('data', chunk => { backendLog += chunk })
  await until(async () => (await fetch('http://127.0.0.1:' + apiPort + '/health')).ok, 'backend startup ' + backendLog)
  const { createServer } = await import(pathToFileURL(path.join(frontend, 'node_modules/vite/dist/node/index.js')))
  server = await createServer({ root: frontend, server: { host: '127.0.0.1', port: await freePort(), strictPort: true, proxy: { '/audit-assess': { target: 'http://127.0.0.1:' + apiPort, changeOrigin: true, rewrite: () => '/assess' } } } })
  await server.listen()
  const uiPort = server.httpServer.address().port
  const edge = process.env.EDGE_PATH || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
  browser = spawn(edge, ['--headless=new', '--no-first-run', '--disable-gpu', '--remote-debugging-port=0', '--user-data-dir=' + temp, 'about:blank'], { windowsHide: true, stdio: 'ignore' })
  const browserPort = await until(async () => (await readFile(path.join(temp, 'DevToolsActivePort'), 'utf8')).split('\n')[0], 'Edge startup')
  const targets = await (await fetch('http://127.0.0.1:' + browserPort + '/json/list')).json()
  ws = new WebSocket(targets.find(target => target.type === 'page').webSocketDebuggerUrl)
  await new Promise((resolve,reject) => { ws.onopen = resolve; ws.onerror = reject })
  let sequence = 0
  const pending = new Map()
  const exceptions = []
  const call = (method, params = {}) => new Promise((resolve,reject) => {
    const id = ++sequence
    const timer = setTimeout(() => { pending.delete(id); reject(new Error('CDP timeout: ' + method)) }, method === 'Page.captureScreenshot' ? 45000 : 15000)
    pending.set(id, { resolve: value => { clearTimeout(timer); resolve(value) }, reject: error => { clearTimeout(timer); reject(error) } })
    ws.send(JSON.stringify({ id, method, params }))
  })
  ws.onmessage = event => {
    const message = JSON.parse(event.data)
    if (message.method === 'Runtime.exceptionThrown') exceptions.push(message.params.exceptionDetails.text)
    if (message.method === 'Fetch.requestPaused') {
      const url = message.params.request.url.replace('http://localhost:8000', 'http://127.0.0.1:' + apiPort)
      call('Fetch.continueRequest', { requestId: message.params.requestId, url }).catch(error => exceptions.push(error.message))
    }
    if (message.id && pending.has(message.id)) {
      const task = pending.get(message.id); pending.delete(message.id)
      message.error ? task.reject(new Error(JSON.stringify(message.error))) : task.resolve(message.result)
    }
  }
  const evaluate = async expression => {
    const result = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails))
    return result.result.value
  }
  const click = label => evaluate('[...document.querySelectorAll("button")].find(b => b.textContent.trim() === ' + JSON.stringify(label) + ').click()')
  await call('Runtime.enable')
  await call('Page.enable')
  // Add the allowed development origin to rewritten requests while using an isolated UI port.
  await call('Fetch.enable', { patterns: [{ urlPattern: 'http://localhost:8000/*' }] })
  await call('Page.navigate', { url: 'http://127.0.0.1:' + uiPort })
  await until(() => evaluate('!!document.querySelector("input[type=file]")'), 'upload page')

  async function selectFile(file) {
    const { root } = await call('DOM.getDocument')
    const { nodeId } = await call('DOM.querySelector', { nodeId: root.nodeId, selector: 'input[type=file]' })
    await call('DOM.setFileInputFiles', { nodeId, files: [file] })
    await until(() => evaluate('document.body.innerText.includes(' + JSON.stringify(path.basename(file)) + ')'), 'file selection')
  }
  // The browser's isolated port is outside backend CORS. Proxy responses through
  // an actual same-origin Vite endpoint, preserving the unchanged app API call.
  await call('Fetch.disable')
  await evaluate('window.originalFetch = window.fetch; window.fetch = async (url, options) => { const response = await window.originalFetch(String(url).includes("localhost:8000/assess") ? "/audit-assess" : url, options); if (response.ok) window.auditResult = await response.clone().json(); return response }')
  const fixtures = path.resolve(frontend, '../backend/test_data/statistics/fixtures')
  await selectFile(path.join(fixtures, 'mixed.csv'))
  await click('Analyse Network Traffic')
  await until(() => evaluate('!!sessionStorage.getItem("assessmentSummary") && !document.querySelector("input[type=file]")'), 'real upload and dashboard')
  const result = await evaluate('window.auditResult')
  assert.equal(result.score, 38)
  assert.equal(result.total_rows, 20)
  assert.ok(await evaluate('document.body.innerText.includes("Missing values") && document.body.innerText.includes("Statistical outliers")'))
  assert.ok(await evaluate('document.body.innerText.includes("Record predictions are pending")'))
  assert.equal(await evaluate('!!document.querySelector(".warning-panel")'), false)
  assert.equal(await evaluate('!!document.querySelector(".workflow")'), false)
  console.log('PASS: real CSV upload, current quality data, recommendations, no invented ML values')

  async function layout(label, width, height) {
    await call('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: width < 768 })
    await delay(150)
    const sizes = await evaluate('({ viewport: innerWidth, document: document.documentElement.scrollWidth })')
    assert.ok(sizes.document <= sizes.viewport + 1, label + ' horizontal overflow: ' + JSON.stringify(sizes))
  }
  for (const [width,height] of [[1440,1000], [768,1024], [390,844], [320,720]]) {
    await layout('Dashboard', width,height)
    assert.ok(await evaluate('getComputedStyle(document.body).backgroundColor !== "rgb(255, 255, 255)"'))
  }
  await call('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false })
  const shot = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
  await writeFile(path.join(temp, 'dashboard-current.png'), Buffer.from(shot.data,'base64'))
  const actions = await evaluate('document.querySelectorAll(".action-item input").length')
  assert.equal(actions, result.translated_issues.length)
  await evaluate('document.querySelector(".action-details").open = true')
  await evaluate('document.querySelector(".action-item input").click()')
  assert.ok(await evaluate('document.body.innerText.includes("1 of 6 actions completed")'))
  const downloads = path.join(temp, 'downloads'); await mkdir(downloads)
  await call('Browser.setDownloadBehavior', { behavior:'allow', downloadPath:downloads })
  await click('Export report')
  const pdf = await until(async () => {
    const contents = await readFile(path.join(downloads,'mixed-assessment.pdf'))
    return contents.subarray(0,4).toString() === '%PDF' && contents.toString('latin1')
  }, 'quality PDF')
  assert.ok(pdf.includes('38/100'))
  console.log('PASS: mobile/tablet/desktop layouts, action progress and real PDF export')

  // Inject a synthetic contract only in the test browser, never in application code.
  const future = { ...result, filename:'contract-test.csv', intrusion_detection: {
    total_records:4, normal_count:3, malicious_count:1, average_confidence:.94,
    metrics:{ accuracy:.962, precision:.951, recall:.947, f1:.949 },
    records:[{record_id:412,source_ip:'10.0.4.17',destination_ip:'10.0.1.5',protocol:'TCP',prediction:'malicious',confidence:.98,data_quality_status:'missing_fields',reliability:'low'}],
  }}
  await click('Upload & Analyse')
  await selectFile(path.join(fixtures, 'clean.csv'))
  await evaluate('window.auditFetch = window.fetch; window.fetch = async () => new Response(' + JSON.stringify(JSON.stringify(future)) + ', {status:200,headers:{"Content-Type":"application/json"}})')
  await click('Analyse Network Traffic')
  await until(() => evaluate('!document.querySelector("input[type=file]")'), 'in-memory future response')
  await evaluate('window.fetch = window.auditFetch')
  await until(() => evaluate('!!document.querySelector(".warning-panel")'), 'future contract warning')
  assert.ok(await evaluate('document.body.innerText.includes("96.2%") && document.body.innerText.includes("Low — verify")'))
  for (const [width,height] of [[1440,1000],[768,1024],[390,844],[320,720]]) await layout('Future results',width,height)
  await call('Emulation.setDeviceMetricsOverride', { width:1440,height:1000,deviceScaleFactor:1,mobile:false })
  await writeFile(path.join(temp,'dashboard-contract.png'), Buffer.from((await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'))
  await click('Export report')
  const combined = await until(async () => (await readFile(path.join(downloads,'contract-test-assessment.pdf'))).toString('latin1'), 'combined PDF')
  assert.ok(combined.includes('Intrusion detection results')); assert.ok(combined.includes('96.2%'))
  assert.ok(combined.includes('Reliability warning:'))
  for (const label of ['Data Quality', 'Intrusion Detection', 'Results', 'Reports']) {
    await click(label)
    assert.equal(await evaluate('!!document.querySelector(".workflow")'), false)
    for (const [width,height] of [[1440,1000],[390,844],[320,720]]) await layout(label,width,height)
    if (label === 'Results') {
      await evaluate('{const select=document.querySelector(".table-filter select"); select.value="normal"; select.dispatchEvent(new Event("change",{bubbles:true}))}')
      assert.ok(await evaluate('document.body.innerText.includes("No records match this filter")'))
      await evaluate('{const select=document.querySelector(".table-filter select"); select.value="review"; select.dispatchEvent(new Event("change",{bubbles:true}))}')
      assert.ok(await evaluate('document.body.innerText.includes("#00412")'))
    }
  }
  console.log('PASS: future contract warning, actual confidence/reliability badges and combined PDF')

  await click('Upload & Analyse')
  for (const [width,height] of [[1440,1000],[390,844],[320,720]]) await layout('Upload',width,height)
  await call('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false})
  await writeFile(path.join(temp,'upload.png'),Buffer.from((await call('Page.captureScreenshot',{format:'png'})).data,'base64'))
  const malformed = path.join(temp,'malformed.csv'); await writeFile(malformed,'a,b\n1,2,3\n')
  await selectFile(malformed); await click('Analyse Network Traffic')
  await until(() => evaluate('document.body.innerText.includes("Assessment failed: Malformed CSV")'), 'visible malformed-file error')
  assert.equal(await evaluate('sessionStorage.getItem("assessmentSummary")'),null)
  // Delay an actual response, replace the selected file and release the old result.
  await evaluate('window.auditFetch=window.fetch; window.fetch=async(...args)=>{const response=await window.auditFetch(...args); await new Promise(resolve=>window.releaseAssessment=resolve);return response}')
  await selectFile(path.join(fixtures,'mixed.csv')); await click('Analyse Network Traffic')
  await until(() => evaluate('!!window.releaseAssessment'),'pending response')
  assert.ok(await evaluate('document.body.innerText.includes("Pending model integration") && !!document.querySelector(".stage-active")'))
  await selectFile(path.join(fixtures,'clean.csv'))
  await evaluate('window.releaseAssessment()'); await delay(250)
  assert.equal(await evaluate('sessionStorage.getItem("assessmentSummary")'),null)
  assert.ok(await evaluate('!!document.querySelector("input[type=file]")'))
  await evaluate('window.fetch=window.auditFetch')
  await click('Analyse Network Traffic')
  await until(() => evaluate('!!sessionStorage.getItem("assessmentSummary") && !document.querySelector("input[type=file]")'),'replacement assessment')
  assert.equal(await evaluate('JSON.parse(sessionStorage.getItem("assessmentSummary")).score'),100)
  assert.equal(await evaluate('sessionStorage.getItem("assessmentResult")'), null)
  await click('Reports'); await call('Page.reload')
  await until(() => evaluate('document.body.innerText.includes("No active assessment is available.")'), 'refresh empty report')
  assert.ok(await evaluate('document.body.innerText.includes("Previous assessment summary only") && !document.body.innerText.includes("Export report")'))
  await click('Dashboard')
  assert.ok(await evaluate('document.body.innerText.includes("Please upload and analyse the dataset again.")'))
  // A response far beyond browser storage quotas must still work in memory.
  await click('Upload & Analyse')
  await selectFile(path.join(fixtures, 'clean.csv'))
  await evaluate('window.largeResponse = ' + JSON.stringify(future) + '; window.largeResponse.filename="large-response.csv"; window.largeResponse.total_rows=175341; window.largeResponse.test_evidence="x".repeat(24*1024*1024); window.fetch=async()=>new Response(JSON.stringify(window.largeResponse),{status:200,headers:{"Content-Type":"application/json"}}); window.storageWrites=[]; window.originalSetItem=Storage.prototype.setItem; Storage.prototype.setItem=function(key,value){window.storageWrites.push({key,length:value.length}); return window.originalSetItem.call(this,key,value)}')
  await click('Analyse Network Traffic')
  await until(() => evaluate('document.body.innerText.includes("large-response.csv") && !document.querySelector("input[type=file]")'), 'large in-memory result')
  assert.ok(await evaluate('window.storageWrites.every(write=>write.key!=="assessmentResult" && write.length<2048)'))
  assert.ok(await evaluate('JSON.parse(sessionStorage.getItem("assessmentSummary")).total_rows===175341'))
  for (const label of ['Data Quality', 'Intrusion Detection', 'Results', 'Reports']) {
    await click(label)
    assert.ok(await evaluate('!document.body.innerText.includes("No active assessment")'))
    if (label === 'Results') assert.ok(await evaluate('document.body.innerText.includes("#00412")'))
  }
  // Storage quota failure must never become an assessment failure or block routing.
  await click('Upload & Analyse')
  await selectFile(path.join(fixtures, 'clean.csv'))
  await evaluate('Storage.prototype.setItem=function(){throw new DOMException("forced quota failure","QuotaExceededError")}')
  await click('Analyse Network Traffic')
  await until(() => evaluate('!document.querySelector("input[type=file]")'), 'successful assessment despite quota failure')
  assert.ok(await evaluate('!document.body.innerText.includes("Assessment failed") && document.body.innerText.includes("large-response.csv")'))
  await click('Reports')
  assert.ok(await evaluate('document.body.innerText.includes("Export report")'))
  await evaluate('Storage.prototype.setItem=window.originalSetItem')
  console.log('PASS: large response stays in memory, bounded summary, refresh empty states and quota-safe upload/navigation')
  await click('Upload & Analyse'); await call('Page.reload')
  await until(() => evaluate('!!document.querySelector("input[type=file]")'),'Upload refresh persistence')
  assert.equal(exceptions.length,0,exceptions.join('\n'))
  console.log('PASS: malformed upload, stale-response protection, replacement upload and session navigation')
  console.log('Screenshots and PDFs: ' + temp)
} finally {
  ws?.close(); browser?.kill(); backend?.kill()
  await Promise.race([server?.close(),delay(3000)])
}
