// Optional Windows end-to-end smoke test using installed Edge and Node 24.
// Requires port 5173 and the sibling frontend's installed packages.
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdtemp, readFile, writeFile, mkdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import net from 'node:net'
import { fileURLToPath, pathToFileURL } from 'node:url'

const frontend = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(frontend, '../backend')
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
  let chooserCount = 0
  ws.onmessage = event => {
    const message = JSON.parse(event.data)
    if (message.method === 'Fetch.requestPaused') {
      // Route only this browser's API request to the fresh test service.
      // Existing services on port 8000 and frontend source remain untouched.
      call('Fetch.continueRequest', { requestId: message.params.requestId,
        url: message.params.request.url.replace('http://localhost:8000', `http://127.0.0.1:${apiPort}`) }).catch(error => exceptions.push(error.message))
    }
    if (message.method === 'Page.fileChooserOpened') chooserCount += 1
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
  await call('Page.setInterceptFileChooserDialog', { enabled: true })
  await call('Page.navigate', { url: 'http://127.0.0.1:5173' })
  await until(() => evaluate("!!document.querySelector('input[type=file]')"), 'upload page')
  async function upload(file, beforeSubmit) {
    const { root: document } = await call('DOM.getDocument')
    const { nodeId } = await call('DOM.querySelector', { nodeId: document.nodeId, selector: 'input[type=file]' })
    await call('DOM.setFileInputFiles', { nodeId, files: [file] })
    await until(() => evaluate(`document.body.innerText.includes(${JSON.stringify(path.basename(file))})`), 'selected file')
    if (beforeSubmit) await beforeSubmit()
    await evaluate("[...document.querySelectorAll('button')].find(b => b.textContent.includes('Run Assessment')).click()")
  }

  const artifacts = path.join(frontend, 'responsive-test-artifacts')
  await mkdir(artifacts, { recursive: true })
  const filename = 'assessment_' + 'long_filename_'.repeat(8) + '.csv'
  const fixture = path.join(temp, filename)
  const field = 'measurement_' + 'long_column_name_'.repeat(9)
  const rows = Array.from({length: 30}, (_, i) => `Q${String(i).padStart(3, '0')},${i === 29 ? 99999 : i === 0 ? '' : 10 + i % 5},${i === 28 ? 'invalid' : `person${i}@example.org`}`)
  await writeFile(fixture, `record_id,${field},contact\n${rows.join('\n')}\n`.replaceAll('\\n', '\n'))
  const viewports = [[320,640],[375,812],[430,932],[768,1024],[1024,768],[1366,768],[1440,900],[1920,1080],[812,375],[1024,600],[2560,1440]]
  async function key(key, code) {
    await call('Input.dispatchKeyEvent', { type:'keyDown', key, code, text: key === 'Enter' ? '\r' : '', unmodifiedText: key === 'Enter' ? '\r' : '', windowsVirtualKeyCode: key === 'Enter' ? 13 : 27 })
    await call('Input.dispatchKeyEvent', { type:'keyUp', key, code, windowsVirtualKeyCode: key === 'Enter' ? 13 : 27 })
  }
  async function navigate(label, width) {
    if (width < 768) {
      await evaluate("document.querySelector('.mobile-menu summary').focus()")
      await key('Enter', 'Enter')
      await delay(100)
      assert.ok(await evaluate("document.querySelector('.mobile-menu').open"), 'keyboard opens menu ' + JSON.stringify(await evaluate("({width:innerWidth,active:document.activeElement.outerHTML,menu:document.querySelector('.mobile-menu').outerHTML,rect:document.querySelector('.mobile-menu').getBoundingClientRect().toJSON()})")))
    }
    await evaluate(`[...document.querySelectorAll('nav button')].find(b => b.textContent.trim() === ${JSON.stringify(label)} && b.getBoundingClientRect().height > 0).click()`)
    await delay(70)
    if (width < 768) assert.equal(await evaluate("document.querySelector('.mobile-menu').open"), false, 'menu closes on navigation')
  }
  async function layout(label, width, height) {
    const state = await evaluate(`(() => {
      const all = [...document.querySelectorAll('main, main section, main aside, main article, main details, header, nav')].filter(e => e.getBoundingClientRect().height > 0)
      const bad = all.filter(e => {const r=e.getBoundingClientRect();return r.right > innerWidth+1 || r.left < -1}).map(e => e.tagName + ':' + e.className)
      const small = [...document.querySelectorAll('button,summary')].filter(e => e.getBoundingClientRect().height > 0 && e.getBoundingClientRect().height < 43).map(e => e.textContent)
      return {width: document.documentElement.scrollWidth, viewport: innerWidth, bad, small, text: document.querySelector('main')?.innerText.length}
    })()`)
    assert.ok(state.width <= width + 1, `${label} ${width}x${height} page overflow: ${JSON.stringify(state)}`)
    assert.deepEqual(state.bad, [], `${label} content exceeds viewport`)
    assert.deepEqual(state.small, [], `${label} touch targets`)
    assert.ok(state.text > 60)
  }
  async function uploadLayout(state, width, height) {
    await evaluate('window.scrollTo(0,0)')
    const geometry = await evaluate(`(() => {
      const preview = document.querySelector('.scan-preview')
      const upload = document.querySelector('.upload-controls')
      const button = [...document.querySelectorAll('button')].find(b => b.textContent.includes('Run Assessment'))
      const p=preview.getBoundingClientRect(), u=upload.getBoundingClientRect(), b=button.getBoundingClientRect()
      const overflow = [preview, ...preview.querySelectorAll('*')].filter(e => !e.classList.contains('sr-only') && e.clientWidth > 0 && (e.scrollWidth > e.clientWidth+2 || e.scrollHeight > e.clientHeight+2)).map(e => e.tagName + ':' + e.className)
      const scrollers = [preview, ...preview.querySelectorAll('*')].filter(e => ['auto','scroll'].includes(getComputedStyle(e).overflowX) || ['auto','scroll'].includes(getComputedStyle(e).overflowY)).map(e => e.tagName)
      const overlap = p.left < u.right && p.right > u.left && p.top < u.bottom && p.bottom > u.top
      return {overflow, scrollers, overlap, buttonBottom:b.bottom, buttonTop:b.top, disabled:button.disabled, previewHeight:p.height}
    })()`)
    assert.deepEqual(geometry.overflow, [], `${state} preview content overflow ${width}: ${JSON.stringify(geometry)}`)
    assert.deepEqual(geometry.scrollers, [], 'preview never uses internal scroll containers')
    assert.equal(geometry.overlap,false,'preview and controls do not overlap')
    assert.equal(geometry.disabled,false,'submission conditions preserved')
    if ([375,768,1366,1440,1920].includes(width)) {
      const shot=await call('Page.captureScreenshot',{format:'png'})
      await writeFile(path.join(artifacts,`upload-${width}-${state}.png`),Buffer.from(shot.data,'base64'))
    }
    console.log(`Upload ${width}x${height} ${state}: button bottom ${Math.round(geometry.buttonBottom)}px; preview ${Math.round(geometry.previewHeight)}px; no internal overflow`)
  }
  const results = []
  for (const [width,height] of viewports) {
    await call('Emulation.setDeviceMetricsOverride', {width,height,deviceScaleFactor:1,mobile:width < 768})
    await call('Emulation.setTouchEmulationEnabled', {enabled: width < 768})
    await delay(150)
    await navigate('Upload', width)
    await layout('Upload', width, height)
    await uploadLayout('unselected', width, height)
    if ([320,1920].includes(width)) {
      const before = chooserCount
      await evaluate("[...document.querySelectorAll('button')].find(b => b.textContent.includes('Browse Files')).focus()")
      await key('Enter','Enter')
      await until(() => chooserCount > before, 'accessible Browse Files opens native file chooser')
    }
    await upload(fixture, () => uploadLayout('selected',width,height))
    await until(() => evaluate("!!document.querySelector('main') && !!sessionStorage.getItem('assessmentResult') && !document.querySelector('input[type=file]')"), 'real results')
    for (const label of ['Overview','Issues','By field','Actions']) {
      await navigate(label, width)
      if (label === 'By field') await evaluate("document.querySelectorAll('main details').forEach(d => d.open = true)")
      await layout(label, width, height)
      if (label === 'Overview' && [320,768,1920].includes(width)) {
        await evaluate('window.scrollTo(0,0)')
        const shot = await call('Page.captureScreenshot', { format:'png' })
        await writeFile(path.join(artifacts, `overview-${width}.png`), Buffer.from(shot.data, 'base64'))
      }
      if (label === 'Actions' && [320,1920].includes(width)) {
        await evaluate("document.querySelector('main input[type=checkbox]').click()")
        assert.ok(await evaluate("document.querySelector('main input[type=checkbox]').checked"))
        const downloads = path.join(temp, `downloads-${width}`)
        await mkdir(downloads)
        await call('Browser.setDownloadBehavior', {behavior:'allow',downloadPath:downloads})
        await evaluate("[...document.querySelectorAll('button')].find(b => b.textContent.includes('Download full report')).click()")
        await until(async () => (await readFile(path.join(downloads, filename.replace('.csv','-assessment.pdf')))).subarray(0,4).toString() === '%PDF', 'PDF download')
      }
    }
    results.push({width,height,pages:['Upload','Overview','Issues','By field','Actions'],overflow:false})
    console.log(`PASS ${width}x${height}: all five pages, actual CSV results, navigation, touch targets`)
  }
  await call('Emulation.setEmulatedMedia', {features:[{name:'prefers-reduced-motion',value:'reduce'}]})
  await navigate('Upload',2560)
  assert.equal(await evaluate("getComputedStyle(document.querySelector('.scan-beam')).display"), 'none')
  const malformed = path.join(temp,'malformed.csv')
  await writeFile(malformed, 'a,b\n1,2,3\n')
  await upload(malformed)
  await until(() => evaluate("document.body.innerText.includes('Assessment failed: Malformed CSV')"), 'visible upload error')
  assert.equal(exceptions.length,0, `Uncaught browser exceptions: ${exceptions}`)
  await writeFile(path.join(artifacts,'results.json'), JSON.stringify({browser:await call('Browser.getVersion'),results,pdfWidths:[320,1920],reducedMotion:true},null,2))
  console.log('PASS: mobile and desktop PDF, reduced motion, malformed upload handling; no uncaught exceptions.')
} finally {
  ws?.close()
  browser?.kill()
  backend?.kill()
  await Promise.race([server?.close(),delay(3000)])
}
