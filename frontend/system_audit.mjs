// Network integration: real React/Edge upload checks, mocked boundaries and real backend.
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { spawn, spawnSync } from 'node:child_process'
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
  const deadline = Date.now() + 600000
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
  const denyFit = 'from sklearn.ensemble import RandomForestClassifier; from ml.preprocessing import NetworkMLPreprocessor; from unittest.mock import Mock; deny=Mock(side_effect=AssertionError("No fitting during upload analysis")); RandomForestClassifier.fit=deny; NetworkMLPreprocessor.fit=deny; NetworkMLPreprocessor.fit_transform=deny; import uvicorn; uvicorn.run("main:app",host="127.0.0.1",port=' + apiPort + ')'
  backend = spawn(path.join(project, 'backend/venv/Scripts/python.exe'), ['-B', '-c', denyFit], {
    cwd: path.join(project, 'backend'), windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, OPENBLAS_NUM_THREADS: '1', OMP_NUM_THREADS: '1' },
  })
  let backendLog = ''
  backend.stdout.on('data', data => { backendLog += data.toString() })
  backend.stderr.on('data', data => { backendLog += data.toString() })
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
  const realPath = path.join(project, 'data/UNSW_NB15_testing-set.csv')

  await evaluate('window.fetch=window.__originalFetch;Storage.prototype.setItem=window.__originalSetItem;window.__realCalls=[];const realFetch=window.fetch;window.fetch=(url,options)=>{window.__realCalls.push(url);return realFetch(url,options)}')
  const fixtureRun = spawnSync(path.join(project, 'backend/venv/Scripts/python.exe'), ['-B', path.join(project, 'backend/test_data/create_network_fixtures.py'), temporary], { cwd: project, encoding: 'utf8', windowsHide: true })
  assert.equal(fixtureRun.status, 0, fixtureRun.stderr)
  const inputs = JSON.parse(fixtureRun.stdout)
  const cases = []
  const official = JSON.parse(await readFile(path.join(project, 'backend/models/model_metadata.json'), 'utf8'))
  const hashes = async () => Object.fromEntries(await Promise.all(Object.values(official.files).map(async info => [info.filename, createHash('sha256').update(await readFile(path.join(project, 'backend/models', info.filename))).digest('hex')])))
  const beforeHashes = await hashes()
  const output = path.join(temporary, 'system-validation')
  await mkdir(output, { recursive: true })
  const recordCase = async (name, input, expected, actual, passed = true, notes = '') => {
    cases.push({ name, input, expected, actual, passed, notes })
    await writeFile(path.join(output, 'browser_cases.json'), JSON.stringify(cases, null, 2))
  }
  for (const input of inputs) {
    await click('Upload & Analyse'); await select(input.path)
    assert.equal(await evaluate(active), null, 'Selecting a new file must clear prior results')
    await click('Analyse Network Traffic')
    await until(() => evaluate('!!document.querySelector(".network-dashboard") || !!document.querySelector(".error-message")'), input.name)
    const response = await evaluate(active)
    if (input.error) {
      const error = await evaluate('document.querySelector(".error-message")?.innerText')
      const passed = !response && !!error && (input.name !== 'missing_features' || ['dur', 'proto', 'spkts'].every(field => error.includes(field)))
      await recordCase(input.name, input.description, 'Clear error; no active/stale result; retry enabled', { error, active_result: !!response }, passed)
      assert.ok(passed, input.name)
      assert.ok(await evaluate('!document.querySelector("button[aria-busy]").disabled'))
      continue
    }
    assert.ok(response, input.name)
    const summary = response.intrusion_summary, quality = response.data_quality
    let passed = summary.records_analysed === input.rows && response.records.length === input.rows
    if (input.name === 'missing_values') passed &&= response.records[0].reliability === 'Review' && response.records[1].reliability === 'Review' && response.records[0].preprocessing_handled_missing.some(item => item.column === 'dur') && response.records[1].preprocessing_handled_missing.some(item => item.column === 'service') && quality.missing_values.occurrences >= 2
    if (input.name === 'invalid_numeric') passed &&= response.records[0].prediction_status === 'Rejected' && response.records[0].prediction === null && response.records[0].predicted_class_probability === null && !!response.records[0].rejection_reason && quality.invalid_values.occurrences >= 1
    if (input.name === 'unseen_category') passed &&= response.records[0].reliability === 'Review' && quality.schema_audit.unseen_categories.proto >= 1 && response.records[0].reliability_reason.includes('Unseen proto')
    if (input.name === 'analytical_outlier') passed &&= summary.rejected_count === 0 && response.records[input.rows - 1].reliability === 'High' && response.records[input.rows - 1].quality_findings.some(item => item.category === 'analytical_security_anomaly')
    if (input.name === 'duplicates') passed &&= quality.duplicates.affected_records >= 1 && summary.rejected_count === 0 && response.records[input.rows - 1].reliability === 'High'
    passed &&= response.model_performance.is_current_upload_metric === false && response.model_performance.accuracy === official.phase5_evaluation.metrics.accuracy
    await recordCase(input.name, input.description, input.expected, { summary, reliability: response.reliability_summary, quality_score: quality.score, missing: quality.missing_values, duplicates: quality.duplicates, invalid: quality.invalid_values, anomalies: quality.analytical_anomalies, changed_records: response.records.filter(row => row.reliability !== 'High' || row.record_index === input.rows - 1) }, passed)
    assert.ok(passed, input.name)
  }
  await click('Upload & Analyse'); await select(inputs[0].path)
  await evaluate('window.fetch=async()=>{throw new TypeError("Simulated connection failure")}')
  await click('Analyse Network Traffic')
  await until(() => evaluate('document.body.innerText.includes("backend is unavailable")'), 'backend unavailable UI')
  assert.equal(await evaluate(active), null)
  assert.ok(await evaluate('!document.querySelector("button[aria-busy]").disabled'))
  await recordCase('backend_unavailable', 'Mocked connection rejection', 'Clear connection message, no results, retry enabled', await evaluate('document.querySelector(".error-message").innerText'))
  await evaluate('window.fetch=window.__originalFetch')
  await click('Upload & Analyse')
  await evaluate('window.__realCalls=[];window.fetch=(url,options)=>{window.__realCalls.push(url);return window.__originalFetch(url,options)}')
  await select(realPath); await click('Analyse Network Traffic')

  await until(() => evaluate('!!document.querySelector(".network-dashboard")'), 'real backend analysis')
  const result = await evaluate(`(()=>{const r=${active};return {sections:Object.keys(r),intrusion_summary:r.intrusion_summary,reliability_summary:r.reliability_summary,quality_score:r.data_quality.score,records:r.records.length,pagination:r.pagination,official_source:r.model_performance.source}})()`)
  assert.equal(result.intrusion_summary.records_analysed, 82332)
  assert.equal(result.records, 100)
  assert.equal(await evaluate('window.__realCalls.length'), 1)
  for (const [page, expected] of [['Data Quality', 'Returned record finding evidence'], ['Intrusion Detection', 'Missed Attack'], ['Results', 'Inspect record'], ['Reports', 'Export report PDF']]) {
    await click(page)
    assert.ok(await evaluate(`document.body.innerText.includes(${JSON.stringify(expected)})`))
  }
  const largeActive = await evaluate(active)
  assert.equal(largeActive.intrusion_summary.normal_count, 26700)
  assert.equal(largeActive.intrusion_summary.malicious_count, 55632)
  const serializedBytes = Buffer.byteLength(JSON.stringify(largeActive))
  const heap = await call('Runtime.getHeapUsage')
  await recordCase('large_file', 'Full official UNSW_NB15_testing-set.csv', '82332 analysed, 100 returned rows, bounded response, safe summary persistence', { summary: largeActive.intrusion_summary, reliability: largeActive.reliability_summary, pagination: largeActive.pagination, response_bytes: serializedBytes, browser_js_heap: heap, storage_bytes: await evaluate('sessionStorage.getItem("networkAnalysisSummary").length') })
  await click('Results')
  await evaluate('(()=>{const select=document.querySelector("select");select.value="Malicious";select.dispatchEvent(new Event("change",{bubbles:true}))})()')
  await delay(100)
  const displayed = await evaluate('document.querySelector("tbody").querySelectorAll("tr").length')
  assert.equal(displayed, largeActive.records.filter(row => row.label === 'Malicious' && row.prediction_status !== 'Rejected').length)
  await recordCase('returned_page_filters', 'Current 100-row page; Malicious filter', 'Only supplied Malicious rows shown', { displayed })
  await click('Reports')
  const exportDirectory = path.join(temporary, 'system-validation')
  await mkdir(exportDirectory, { recursive: true })
  await call('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: exportDirectory })
  await click('Export report PDF')
  await until(async () => { try { return (await readFile(path.join(exportDirectory, 'DataQualiQ-network-report.pdf'))).subarray(0, 5).toString() === '%PDF-' } catch { return false } }, 'real PDF export download')
  const activeResult = await evaluate(active)
  const pdfModule = await server.ssrLoadModule('/src/utils/downloadNetworkPdf.js')
  const selected = pdfModule.importantReportRecords(activeResult.records)
  await writeFile(path.join(exportDirectory, 'pdf_expected.json'), JSON.stringify({ sections: pdfModule.networkReportSections(activeResult), selected_record_positions: selected.map(record => record.record_index + 1), source: 'Real frontend/backend upload; full official testing CSV; 100 returned records', filename: activeResult.filename }, null, 2))
  assert.ok(selected.length <= 20)
  await click('Dashboard')
  const summaryBytes = await evaluate('sessionStorage.getItem("networkAnalysisSummary").length')
  assert.ok(summaryBytes < 2048)
  assert.equal(exceptions.length, 0, exceptions.join('\n'))
  assert.ok(await evaluate('!document.querySelector(".workflow") && !!document.querySelector(".network-dashboard table")'))
  await call('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: false })
  assert.ok(await evaluate('document.documentElement.scrollWidth <= 390'))
  await call('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
  const afterHashes = await hashes()
  assert.deepEqual(afterHashes, beforeHashes)
  for (const info of Object.values(official.files)) assert.equal(afterHashes[info.filename], info.sha256)
  await recordCase('saved_inference_and_checksums', 'Real API process; fit and fit_transform forbidden', 'No fitting, saved artifacts unchanged', { fit_methods_forbidden: true, hashes: afterHashes })
  await writeFile(path.join(output, 'backend.log'), backendLog)
  const report = { browser: 'Headless Microsoft Edge, real React UI', checks: ['file selection', 'multipart request', 'approximate processing states', 'controls disabled', 'synchronous duplicate guard', 'structured memory state', 'summary-only storage', 'Dashboard and route navigation', 'refresh empty state', 'schema errors and retry', 'large result and forced storage quota failure', 'real backend upload'], real_backend_result: result, persisted_summary_bytes: summaryBytes, runtime_exceptions: exceptions }
  await mkdir(path.join(temporary, 'system-validation'), { recursive: true })
  await writeFile(path.join(temporary, 'system-validation/browser_validation.json'), JSON.stringify(report, null, 2))
  const screenshot = await call('Page.captureScreenshot', { format: 'png' })
  await writeFile(path.join(temporary, 'system-validation/dashboard.png'), Buffer.from(screenshot.data, 'base64'))
  console.log('PASS: mocked UI boundaries, quota-safe memory/navigation, refresh and real frontend/backend upload')
  console.log(JSON.stringify({ real_backend_result: result, persisted_summary_bytes: summaryBytes }))
} finally {
  ws?.close(); browser?.kill(); backend?.kill()
  await Promise.race([server?.close(), delay(3000)])
}
