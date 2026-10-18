// Network integration: real React/Edge upload checks, mocked boundaries and real backend.
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdtemp, readFile, writeFile, mkdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import net from 'node:net'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

const frontend = path.dirname(fileURLToPath(import.meta.url))
const project = path.resolve(frontend, '..')
const temporary = await mkdtemp(path.join(tmpdir(), 'dataqualiq-network-'))
const delay = ms => new Promise(resolve => setTimeout(resolve, ms))
async function until(fn, label) {
  const deadline = Date.now() + 60000
  while (Date.now() < deadline) {
    const value = await fn()
    if (value) return value
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
  backend = spawn(path.join(project, 'backend/venv/Scripts/python.exe'), ['-B', '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', String(apiPort)], {
    cwd: path.join(project, 'backend'), windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, OPENBLAS_NUM_THREADS: '1', OMP_NUM_THREADS: '1' },
  })
  await until(async () => { try { return (await fetch(`http://127.0.0.1:${apiPort}/health`)).ok } catch { return false } }, 'backend startup')
  process.env.VITE_API_BASE_URL = '/network-test-api'
  server = await createServer({ root: frontend, server: { host: '127.0.0.1', port: await freePort(), strictPort: true,
    proxy: { '/network-test-api': { target: `http://127.0.0.1:${apiPort}`, changeOrigin: true, rewrite: value => value.replace(/^\/network-test-api/, '') } } } })
  await server.listen()
  browser = spawn(process.env.EDGE_PATH || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', ['--headless=new', '--no-first-run', '--disable-gpu', '--remote-debugging-port=0', '--user-data-dir=' + temporary, 'about:blank'], { windowsHide: true, stdio: 'ignore' })
  const browserPort = await until(async () => { try { return (await readFile(path.join(temporary, 'DevToolsActivePort'), 'utf8')).split('\n')[0] } catch { return false } }, 'Edge startup')
  const targets = await (await fetch(`http://127.0.0.1:${browserPort}/json/list`)).json()
  ws = new WebSocket(targets.find(target => target.type === 'page').webSocketDebuggerUrl)
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject })
  let sequence = 0
  const pending = new Map(), exceptions = []
  const call = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++sequence
    const timer = setTimeout(() => { pending.delete(id); reject(new Error('CDP timeout: ' + method)) }, 30000)
    pending.set(id, { resolve: value => { clearTimeout(timer); resolve(value) }, reject: error => { clearTimeout(timer); reject(error) } })
    ws.send(JSON.stringify({ id, method, params }))
  })
  ws.onmessage = event => {
    const message = JSON.parse(event.data)
    if (message.method === 'Runtime.exceptionThrown') exceptions.push(message.params.exceptionDetails.text)
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
  const click = label => evaluate(`[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(label)}).click()`)
  const active = `(()=>{const element=document.querySelector('.app-shell');let fiber=element[Object.keys(element).find(k=>k.startsWith('__reactFiber'))];while(fiber&&fiber.type?.name!=='App')fiber=fiber.return;return fiber?.memoizedState?.memoizedState})()`
  const select = async filename => {
    const { root } = await call('DOM.getDocument')
    const { nodeId } = await call('DOM.querySelector', { nodeId: root.nodeId, selector: 'input[type=file]' })
    await call('DOM.setFileInputFiles', { nodeId, files: [filename] })
    await until(() => evaluate(`document.body.innerText.includes(${JSON.stringify(path.basename(filename))})`), 'file selection')
  }
  await call('Runtime.enable'); await call('Page.enable')
  await call('Page.navigate', { url: `http://127.0.0.1:${server.httpServer.address().port}` })
  await until(() => evaluate('!!document.querySelector("input[type=file]")'), 'upload screen')
  const mockPath = path.join(temporary, 'mock.csv')
  await writeFile(mockPath, 'a\n1\n')
  const fixture = JSON.parse(await readFile(path.join(project, 'backend/test_data/network_analysis.json'), 'utf8')).response
  fixture.filename = 'mock.csv'
  await evaluate(`window.__originalFetch=window.fetch;window.__payload=${JSON.stringify(fixture)};window.__calls=[];window.__writes=[];window.__originalSetItem=Storage.prototype.setItem;Storage.prototype.setItem=function(key,value){window.__writes.push({key,length:value.length});return window.__originalSetItem.call(this,key,value)};window.fetch=(url,options)=>{window.__calls.push({url,file:options.body.get('file').name});return new Promise(resolve=>{window.__resolve=resolve})}`)
  for (const [width, height] of [[320, 667], [390, 844], [768, 1024], [1024, 768], [1366, 768], [1440, 900], [1920, 1080]]) {
    await call('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false })
    assert.ok(await evaluate(`document.documentElement.scrollWidth <= ${width}`), `Upload overflow at ${width}`)
    assert.ok(await evaluate(`document.documentElement.scrollHeight <= ${height}`), `Upload vertical overflow at ${width}x${height}: ${await evaluate("document.documentElement.scrollHeight")}`)
    assert.ok(await evaluate('!!document.querySelector(".traffic-entry-layout") && !!document.querySelector("input[type=file]")'))
  }
  await mkdir(path.join(temporary, 'upload'), { recursive: true })
  const entryScreenshot = await call('Page.captureScreenshot', { format: 'png' })
  await writeFile(path.join(temporary, 'upload/desktop.png'), Buffer.from(entryScreenshot.data, 'base64'))
  await select(mockPath)
  // Invoke the actual React handler twice in one turn, before rendering can disable it.
  await evaluate(`(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Analyse Network Traffic');const p=b[Object.keys(b).find(k=>k.startsWith('__reactProps'))];p.onClick();p.onClick()})()`)
  await until(() => evaluate('!!document.querySelector(".processing-panel")'), 'processing UI')
  assert.equal(await evaluate('window.__calls.length'), 1)
  assert.ok(await evaluate('document.querySelector("button[aria-busy=true]").disabled && document.querySelector("input[type=file]").disabled'))
  for (const stage of ['Reading dataset', 'Checking data quality', 'Preparing network features', 'Running intrusion detection', 'Preparing combined results']) assert.ok(await evaluate(`document.body.innerText.includes(${JSON.stringify(stage)})`))
  assert.ok(await evaluate('document.body.innerText.includes("not live backend progress")'))
  await evaluate('window.__resolve({ok:true,json:async()=>window.__payload})')
  await until(() => evaluate("!!document.querySelector('.network-dashboard')"), 'Dashboard success')
  assert.equal(await evaluate('document.querySelector(".section-nav [aria-current=page]").textContent'), 'Dashboard')
  assert.equal(await evaluate(`Object.keys(${active}).filter(k=>['data_quality','intrusion_summary','model_performance','reliability_summary','records','pagination','recommendations'].includes(k)).length`), 7)
  assert.ok(await evaluate(`!(${active}).model_performance.is_current_upload_metric`))
  assert.ok(await evaluate('window.__writes.every(w=>w.length<2048 && !["assessmentResult","networkAnalysisResult"].includes(w.key))'))
  assert.equal(await evaluate('JSON.parse(sessionStorage.getItem("networkAnalysisSummary")).intrusion_summary.records_analysed'), 1000)
  for (const page of ['Data Quality', 'Intrusion Detection', 'Results', 'Reports']) {
    await click(page)
    assert.ok(await evaluate('!document.body.innerText.includes("Network analysis complete") && !!document.querySelector("main section")'))
  }
  await call('Page.reload')
  await until(() => evaluate('document.body.innerText.includes("No active analysis is available.")'), 'refresh empty state')
  assert.ok(await evaluate('document.body.innerText.includes("Previous analysis summary only")'))
  assert.equal(await evaluate(active), null)
  // Reload creates a new JS realm: retain its native APIs before further mocks.
  await evaluate('window.__originalFetch=window.fetch;window.__originalSetItem=Storage.prototype.setItem')
  await click('Upload & Analyse'); await select(mockPath)
  await evaluate('window.fetch=async()=>({ok:false,status:422,json:async()=>({detail:{code:"missing_features",missing_fields:["dur","proto","spkts"]}})})')
  await click('Analyse Network Traffic')
  await until(() => evaluate('document.body.innerText.includes("Missing required features: dur, proto, spkts")'), 'schema error')
  assert.ok(await evaluate('!document.querySelector("button[aria-busy]").disabled'))
  await evaluate(`window.__payload=${JSON.stringify(fixture)};window.__payload.records[0].quality_findings=Array(100000).fill({check:'outlier',category:'analytical_security_anomaly',reason:'memory only'});window.fetch=async()=>({ok:true,json:async()=>window.__payload});Storage.prototype.setItem=function(){throw new DOMException('forced quota','QuotaExceededError')}`)
  await click('Analyse Network Traffic')
  await until(() => evaluate('!!document.querySelector(".network-dashboard")'), 'quota-safe success')
  assert.equal(await evaluate(`(${active}).records[0].quality_findings.length`), 100000)
  assert.ok(await evaluate('!document.body.innerText.includes("Unable to analyse")'))
  // Finally exercise the real frontend -> proxy -> backend with a compatible CSV.
  await click('Upload & Analyse')
  const realPath = path.join(temporary, 'real-network-sample.csv')
  const csv = await readFile(path.join(project, 'data/UNSW_NB15_testing-set.csv'), 'utf8')
  await writeFile(realPath, csv.split('\n').slice(0, 1001).join('\n') + '\n')
  await evaluate('window.fetch=window.__originalFetch;Storage.prototype.setItem=window.__originalSetItem;window.__realCalls=[];const realFetch=window.fetch;window.fetch=(url,options)=>{window.__realCalls.push(url);return realFetch(url,options)}')
  await select(realPath); await click('Analyse Network Traffic')
  await until(() => evaluate('!!document.querySelector(".network-dashboard")'), 'real backend analysis')
  const result = await evaluate(`(()=>{const r=${active};return {sections:Object.keys(r),intrusion_summary:r.intrusion_summary,reliability_summary:r.reliability_summary,quality_score:r.data_quality.score,records:r.records.length,pagination:r.pagination,official_source:r.model_performance.source}})()`)
  assert.equal(result.intrusion_summary.records_analysed, 1000)
  assert.equal(result.records, 100)
  assert.equal(await evaluate('window.__realCalls.length'), 1)
  for (const [page, expected] of [['Data Quality', 'Returned record finding evidence'], ['Intrusion Detection', 'Missed Attack'], ['Results', 'Inspect record'], ['Reports', 'Export report PDF']]) {
    await click(page)
    assert.ok(await evaluate(`document.body.innerText.includes(${JSON.stringify(expected)})`))
  }
  await click('Results')
  const activeRecords = await evaluate(`(${active}).records`)
  const filters = []
  const change = async (index, value) => {
    await evaluate(`(()=>{const select=document.querySelectorAll('select')[${index}];select.value=${JSON.stringify(value)};select.dispatchEvent(new Event('change',{bubbles:true}))})()`)
    await delay(100)
  }
  for (const value of ['all', 'Malicious', 'Normal']) {
    await change(0, value)
    const displayed = await evaluate('document.querySelectorAll("tbody tr").length')
    assert.equal(displayed, activeRecords.filter(record => value === 'all' || record.label === value).length)
    filters.push({ prediction: value, displayed })
  }
  await change(0, 'all')
  for (const value of ['High', 'Review', 'Low', 'all']) {
    await change(1, value)
    const displayed = await evaluate('document.querySelectorAll("tbody tr").length')
    assert.equal(displayed, activeRecords.filter(record => value === 'all' || record.reliability === value).length)
    filters.push({ reliability: value, displayed })
  }
  await mkdir(path.join(temporary, 'page-checks'), { recursive: true })
  await writeFile(path.join(temporary, 'page-checks/filters.json'), JSON.stringify(filters, null, 2))
  await evaluate('document.querySelector("tbody details").open=true')
  assert.ok(await evaluate('document.body.innerText.includes("Original row position") && document.body.innerText.includes("Normal probability") && document.body.innerText.includes("Reliability:")'))
  await click('Reports')
  const exportDirectory = path.join(temporary, 'page-checks')
  await mkdir(exportDirectory, { recursive: true })
  await call('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: exportDirectory })
  await click('Export report PDF')
  await until(async () => { try { return (await readFile(path.join(exportDirectory, 'DataQualiQ-network-report.pdf'))).subarray(0, 5).toString() === '%PDF-' } catch { return false } }, 'real PDF export download')
  const activeResult = await evaluate(active)
  const pdfModule = await server.ssrLoadModule('/src/utils/downloadNetworkPdf.js')
  const selected = pdfModule.importantReportRecords(activeResult.records)
  await writeFile(path.join(exportDirectory, 'pdf_expected.json'), JSON.stringify({ sections: pdfModule.networkReportSections(activeResult), selected_record_positions: selected.map(record => record.record_index + 1), source: 'Real frontend/backend upload; first 1000 testing rows; 100 returned records', filename: activeResult.filename }, null, 2))
  assert.ok(selected.length <= 20)
  await click('Dashboard')
  const summaryBytes = await evaluate('sessionStorage.getItem("networkAnalysisSummary").length')
  assert.ok(summaryBytes < 2048)
  assert.equal(exceptions.length, 0, exceptions.join('\n'))
  assert.ok(await evaluate('!document.querySelector(".workflow") && !!document.querySelector(".network-dashboard table")'))
  await call('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: false })
  assert.ok(await evaluate('document.documentElement.scrollWidth <= 390'))
  await call('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
  const report = { browser: 'Headless Microsoft Edge, real React UI', checks: ['file selection', 'multipart request', 'approximate processing states', 'controls disabled', 'synchronous duplicate guard', 'structured memory state', 'summary-only storage', 'Dashboard and route navigation', 'refresh empty state', 'schema errors and retry', 'large result and forced storage quota failure', 'real backend upload'], real_backend_result: result, persisted_summary_bytes: summaryBytes, runtime_exceptions: exceptions }
  await mkdir(path.join(temporary, 'page-checks'), { recursive: true })
  await writeFile(path.join(temporary, 'page-checks/browser_validation.json'), JSON.stringify(report, null, 2))
  const screenshot = await call('Page.captureScreenshot', { format: 'png' })
  await writeFile(path.join(temporary, 'page-checks/dashboard.png'), Buffer.from(screenshot.data, 'base64'))
  console.log('PASS: mocked UI boundaries, quota-safe memory/navigation, refresh and real frontend/backend upload')
  console.log(JSON.stringify({ real_backend_result: result, persisted_summary_bytes: summaryBytes }))
} finally {
  ws?.close(); browser?.kill(); backend?.kill()
  await Promise.race([server?.close(), delay(3000)])
}
