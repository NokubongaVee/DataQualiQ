import assert from 'node:assert/strict'
import { before, after, test } from 'node:test'
import { readFile } from 'node:fs/promises'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'
import { getIntrusionResults, percentage } from './src/utils/intrusionResults.js'
import { normalizeAssessmentResult } from './src/utils/assessmentResult.js'

const results = JSON.parse(await readFile(new URL('../docs/statistics-audit/results.json', import.meta.url), 'utf8'))
let server, Overview, Chart, Quality, Upload, Pages
before(async () => {
  server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: 'custom' })
  ;[Overview, Chart, Quality] = await Promise.all(['pages/OverviewPage', 'components/IssuesByFieldChart', 'components/QualityFindings'].map(async name => (await server.ssrLoadModule('/src/' + name + '.jsx')).default))
  Upload = (await server.ssrLoadModule('/src/pages/UploadPage.jsx')).default
  Pages = (await server.ssrLoadModule('/src/pages/AnalysisPages.jsx')).default
})
after(async () => { delete globalThis.sessionStorage; await server?.close() })
const render = (component, props) => renderToStaticMarkup(React.createElement(component, props))
const plain = html => html.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ')
const expectedCards = { clean: [0,0,0,0], missing: [3,0,0,0], duplicates: [0,3,0,0], invalid: [0,0,3,0], outlier: [0,0,0,1], mixed: [3,0,3,1], many_fields: [7,0,0,0], all_missing: [60,0,0,0] }

const network = JSON.parse(await readFile(new URL('../docs/phase9/functional_validation.json', import.meta.url), 'utf8')).response
test('combined Dashboard uses real sections without workflow boxes or the placeholder', () => {
  const html = render(Overview, { result: network })
  const text = plain(html)
  for (const heading of ['Records analysed', 'Normal traffic', 'Attacks detected', 'Data-quality score', 'Average predicted-class probability', 'Traffic classification', 'Data quality', 'Model performance (official test evaluation)', 'Reliability', 'Record-level results preview', 'Security recommendations']) assert.ok(text.includes(heading), heading)
  for (const absent of ['Analysis workflow', 'STEP 1', 'STEP 2', 'STEP 3', 'STEP 4', 'Network analysis complete', 'Average model confidence']) assert.ok(!text.includes(absent), absent)
  assert.ok(text.includes(network.intrusion_summary.records_analysed.toLocaleString().replace(/\s+/g, ' ')))
  assert.ok(text.includes(network.intrusion_summary.normal_count.toLocaleString().replace(/\s+/g, ' ')))
  assert.ok(text.includes(network.intrusion_summary.malicious_count.toLocaleString().replace(/\s+/g, ' ')))
  assert.ok(text.includes(network.data_quality.score + '/100'))
  assert.ok(text.includes(percentage(network.intrusion_summary.average_predicted_class_probability)))
  assert.ok(text.includes('not calculated from the current upload'))
  assert.ok(text.includes(percentage(network.model_performance.accuracy)))
  assert.ok(html.includes('<svg') && html.includes('<table'))
  assert.equal((html.match(/<tbody>[\s\S]*?<\/tbody>/)?.[0].match(/<tr>/g) || []).length, network.records.length)
  for (const item of network.recommendations) { assert.ok(text.includes(item.message)); assert.ok(text.includes(item.reason)) }
  assert.ok(!text.includes('additional pages are not loaded automatically'))
  assert.ok(!text.includes('Record numbers use original CSV'))
})

test('combined Dashboard omits the warning banner and handles rejected records', () => {
  const result = structuredClone(network)
  Object.assign(result.reliability_summary, { review_count: 0, low_count: 0, rejected_count: 0 })
  assert.ok(!render(Overview, { result }).includes('Some records need manual review'))
  Object.assign(result.reliability_summary, { low_count: 1, rejected_count: 1 })
  result.records = [{ record_index: 22, prediction_status: 'Rejected', label: null, predicted_class_probability: null, reliability: 'Low', quality_status: 'Issue detected', quality_finding_count: 2, quality_findings_truncated: true, quality_findings: [], rejection_reason: 'Invalid dur' }]
  result.pagination.returned_records = 1
  const text = plain(render(Overview, { result }))
  assert.ok(!text.includes('Some records need manual review'))
  assert.ok(text.includes('#23 Rejected Not available Low'))
  assert.ok(text.includes('Invalid dur') && text.includes('evidence truncated'))
})

test('combined Dashboard supports zero predictions, no recommendations and missing official provenance', () => {
  const result = structuredClone(network)
  Object.assign(result.intrusion_summary, { normal_count: 0, malicious_count: 0, average_predicted_class_probability: null })
  result.records = []; result.recommendations = []
  result.model_performance.is_current_upload_metric = true
  const html = render(Overview, { result })
  assert.ok(!/NaN|Infinity/.test(html))
  assert.ok(html.includes('No classified records were returned.'))
  assert.ok(html.includes('No record rows were returned for this page.'))
  assert.ok(html.includes('No recommendations were returned by the backend.'))
  assert.ok(html.includes('Official evaluation metadata is unavailable.'))
  assert.ok(!html.includes(percentage(network.model_performance.accuracy)))
  assert.ok(render(Overview, {}).includes('No active analysis is available.'))
})

test('workflow belongs only to Upload and all dedicated pages preserve assessment evidence', () => {
  const result = results.mixed
  const upload = render(Upload, {})
  assert.ok(upload.includes('Feed us the') && upload.includes('needs attention.'))
  assert.ok(upload.includes('Analysis workflow'))
  assert.ok(upload.indexOf('Upload &amp; Analyse') < upload.indexOf('Dashboard'))
  assert.ok(!render(Overview, { result }).includes('Analysis workflow'))
  for (const page of ['data-quality', 'intrusion-detection', 'results', 'reports']) {
    const html = render(Pages, { page, result })
    assert.ok(!html.includes('Analysis workflow'))
    if (page === 'data-quality') assert.ok(html.includes('Field evidence and check coverage'))
    if (page === 'intrusion-detection') assert.ok(html.includes('Not supplied'))
    if (page === 'results') assert.ok(html.includes('Needs verification') && html.includes('value="normal"'))
    if (page === 'reports') assert.ok(html.includes('Export report'))
  }
})

for (const [name, result] of Object.entries(results)) {
  test(name + ': real quality statistics and complete field evidence survive the redesign', () => {
    const html = render(Overview, { result })
    const text = plain(html)
    const labels = ['Missing values', 'Duplicate rows', 'Invalid / inconsistent values', 'Statistical outliers']
    expectedCards[name].forEach((count, index) => assert.ok(text.includes(labels[index] + ' ' + count), text))
    assert.ok(text.includes(result.score + '/100'))
    assert.ok(text.includes('Grade ' + result.grade))
    assert.ok(text.includes('Awaiting model classification'))
    assert.ok(text.includes('Record predictions are pending'))
    assert.ok(text.includes('Model performance metrics will appear'))
    assert.ok(!text.includes('Some attack predictions may be less reliable'))
    const center = html.match(/<text[^>]*y="61"[^>]*>(\d+)<\/text>/)
    assert.equal(Number(center?.[1]), result.issues.reduce((sum, issue) => sum + issue.count, 0))
    for (const issue of result.issues.filter(issue => issue.column)) assert.ok(html.includes(issue.column))
    for (const issue of result.translated_issues) assert.ok(text.includes(issue.issue_to_review.title))
  })
}

test('field chart fractions, empty chart, and collision-safe Other grouping remain correct', async () => {
  for (const counts of [[], [{name:'a',count:2},{name:'b',count:3}]]) {
    const html = render(Chart, { fieldCounts: counts })
    assert.ok(!/NaN|Infinity/.test(html))
    const arcs = [...html.matchAll(/stroke-dasharray="([\d.]+) ([\d.]+)"/g)]
    assert.equal(arcs.length, counts.length)
    arcs.forEach((arc,index) => assert.ok(Math.abs(Number(arc[1])/Number(arc[2])-counts[index].count/5)<1e-12))
  }
  const result = JSON.parse(await readFile(new URL('../docs/statistics-audit/other-column-result.json', import.meta.url), 'utf8'))
  const html = render(Quality, { result })
  assert.equal((html.match(/<article/g) || []).length, 4)
  assert.ok(plain(html).includes('Other 2 finding occurrences · Affected values 2'))
  assert.ok(html.includes('Other (dataset)'))
})

test('future response displays supplied values, records and only evidence-backed attack warnings', () => {
  const result = { ...results.clean, intrusion_detection: {
    total_records: 4, normal_count: 3, malicious_count: 1, average_confidence: .94,
    metrics: { accuracy: .962, precision: .951, recall: .947, f1: .949 },
    records: [{ record_id: 412, source_ip: '10.0.4.17', destination_ip: '10.0.1.5', protocol: 'TCP',
      prediction: 'malicious', confidence: .98, data_quality_status: 'missing_fields' }],
  }}
  const html = render(Overview, { result })
  const text = plain(html)
  assert.ok(text.includes('Some attack predictions may be less reliable'))
  assert.ok(text.includes('1 supplied records classified as attacks'))
  assert.ok(text.includes('96.2%')); assert.ok(text.includes('94%'))
  assert.ok(text.includes('#00412')); assert.ok(text.includes('98%'))
  assert.ok(text.includes('Missing fields')); assert.ok(html.includes('reliability-pending'))
  assert.ok(!html.includes('reliability-high'))
  assert.equal(getIntrusionResults(result).distribution.malicious, .25)
  result.intrusion_detection.records[0].data_quality_status = 'good'
  assert.ok(!plain(render(Overview, { result })).includes('Some attack predictions may be less reliable'))
})

test('partial, zero, malformed and missing ML values are not presented as completed measurements', () => {
  for (const value of [undefined, null, [], 'bad']) {
    const result = getIntrusionResults({ intrusion_detection: value })
    assert.equal(result.normal, null); assert.equal(result.distribution, null)
  }
  assert.equal(getIntrusionResults({ intrusion_detection: { normal_count: 3 } }).distribution, null)
  assert.equal(getIntrusionResults({ intrusion_detection: { total_records: 10, normal_count: 3, malicious_count: 2 } }).distribution, null)
  assert.equal(getIntrusionResults({ intrusion_detection: { normal_count: 0, malicious_count: 0 } }).distribution, null)
  assert.equal(percentage(0), '0%')
  for (const value of [undefined, null, NaN, -1, 94, '0.9']) assert.equal(percentage(value), 'Pending')
  assert.equal(normalizeAssessmentResult({ score: 'bad' }), null)
  globalThis.sessionStorage = { getItem: () => null }
  const empty = plain(render(Overview, {}))
  assert.ok(empty.includes('No active analysis is available.')); assert.ok(!empty.includes('Export report'))
})

test('model processing remains an in-progress state', () => {
  const result = { ...results.clean, intrusion_detection: { status: 'processing' } }
  const text = plain(render(Overview, { result }))
  assert.ok(!text.includes('Analysis workflow'))
  assert.ok(text.includes('Classification in progress'))
  assert.ok(text.includes('Record predictions are being processed'))
})

test('refresh without an active response shows only the historical summary on every results page', () => {
  const summary = { filename: 'previous.csv', total_rows: 175341, total_columns: 45, score: 100, grade: 'A' }
  for (const html of [render(Overview, { summary }), ...['data-quality', 'intrusion-detection', 'results', 'reports'].map(page => render(Pages, { page, summary }))]) {
    const text = plain(html)
    assert.ok(text.includes('No active analysis is available.'))
    assert.ok(text.includes('Please upload and analyse the network dataset again.'))
    assert.ok(text.includes('Previous analysis summary only'))
    assert.ok(!text.includes('Export report'))
    assert.ok(!text.includes('Field evidence and check coverage'))
    assert.ok(!text.includes('Record predictions are pending'))
  }
})

test('network detail routes render actual quality, official matrix, record evidence and reports', () => {
  const quality = plain(render(Pages, { page: 'data-quality', result: network }))
  for (const label of ['Grade', 'Missing values', 'Duplicates', 'Invalid values', 'Inconsistencies', 'Statistical / analytical anomalies', 'Data errors', 'Quality issues', 'Returned record finding evidence']) assert.ok(quality.includes(label), label)
  assert.ok(quality.includes(network.data_quality.score + '/100'))
  const intrusion = plain(render(Pages, { page: 'intrusion-detection', result: network }))
  for (const label of ['Model performance \u2014 official test evaluation', 'False Alarm', 'Missed Attack', 'Correctly Detected Attack', 'Reliability', 'False Negative']) assert.ok(intrusion.includes(label), label)
  assert.ok(intrusion.includes(percentage(network.model_performance.accuracy)))
  const records = render(Pages, { page: 'results', result: network })
  assert.equal((records.match(/<tbody>[\s\S]*?<\/tbody>/)?.[0].match(/<tr>/g) || []).length, network.records.length)
  assert.ok(records.includes('Predicted probability') && records.includes('Inspect record'))
  assert.ok(records.includes('reupload/reanalysis'))
  const report = plain(render(Pages, { page: 'reports', result: network }))
  assert.ok(report.includes(network.filename) && report.includes('Export report PDF'))
  for (const item of network.recommendations) assert.ok(report.includes(item.message))
  for (const page of ['data-quality', 'intrusion-detection', 'results', 'reports']) assert.ok(render(Pages, { page }).includes('No active analysis is available.'))
})

test('network record details preserve rejection reasons and PDF preview stays bounded', async () => {
  const { networkReportLines } = await server.ssrLoadModule('/src/utils/downloadNetworkPdf.js')
  const result = structuredClone(network)
  result.records[0] = { ...result.records[0], prediction_status: 'Rejected', label: null, predicted_class_probability: null, probability_normal: null, probability_malicious: null, reliability: 'Low', rejection_reason: 'Invalid dur', reliability_reason: 'Invalid required input' }
  const html = plain(render(Pages, { page: 'results', result }))
  assert.ok(html.includes('Rejected Not available Low') && html.includes('Invalid dur'))
  const first = result.records[0]
  result.records = Array.from({ length: 1000 }, (_, index) => ({ ...first, record_index: index }))
  const lines = networkReportLines(result)
  assert.equal(lines.filter(line => /^Record \d+:/.test(line)).length, 20)
  assert.ok(lines.some(line => line.includes('official test evaluation')))
  assert.ok(lines.some(line => line.includes('Invalid dur')))
  assert.ok(!lines.some(line => line.includes('Record 21:')))
})

test('attention labels use supplied classes and reliability, with specific reasons and no probability thresholds', async () => {
  const Attention = (await server.ssrLoadModule('/src/components/RecordAttention.jsx')).default
  const record = { label: 'Malicious', reliability: 'Review', predicted_class_probability: .94, reliability_reason: 'Missing dur handled by saved training median' }
  const review = plain(render(Attention, { record }))
  assert.ok(review.includes('High attention') && review.includes(record.reliability_reason))
  assert.ok(plain(render(Attention, { record: { ...record, reliability: 'Low' } })).includes('High attention'))
  assert.ok(plain(render(Attention, { record: { ...record, reliability: 'High', predicted_class_probability: .01 } })).includes('Security alert'))
  assert.ok(plain(render(Attention, { record: { ...record, label: 'Normal' } })).includes('Normal review'))
  assert.ok(plain(render(Attention, { record: { ...record, label: null, prediction_status: 'Rejected', rejection_reason: 'Invalid required proto prevented prediction' } })).includes('Invalid required proto prevented prediction'))
  assert.equal(render(Attention, { record: { ...record, label: 'Normal', reliability: 'High' } }), '')
  assert.ok(!/block|isolate|firewall/i.test(review))
})

test('recommendation panel keeps backend text and counts, with a concise expandable remainder', async () => {
  const Recommendations = (await server.ssrLoadModule('/src/components/NetworkRecommendations.jsx')).default
  const html = render(Recommendations, { recommendations: network.recommendations })
  for (const item of network.recommendations) { assert.ok(html.includes(item.message)); assert.ok(html.includes(item.reason)) }
  assert.equal((html.match(/<li>/g) || []).length, network.recommendations.length)
  if (network.recommendations.length > 3) assert.ok(html.includes('more recommendations'))
  assert.ok(!/block traffic|isolate sources|firewall rule/i.test(html))
  assert.ok(render(Recommendations, { recommendations: [] }).includes('No recommendations were returned by the backend.'))
})

test('final report separates upload sections from official metrics and includes supported limitations', async () => {
  const { networkReportSections, networkReportLines, createNetworkPdf } = await server.ssrLoadModule('/src/utils/downloadNetworkPdf.js')
  const sections = networkReportSections(network)
  assert.deepEqual(sections.map(section => section.title), ['Executive summary', 'Data quality', 'Intrusion detection - current upload', 'Model Performance - Official Test Evaluation', 'Reliability - predictive-input integrity', 'Suspicious / important records', 'Security recommendations', 'Limitations'])
  const lines = networkReportLines(network).join('\n')
  assert.ok(lines.includes(network.filename) && lines.includes(`${network.intrusion_summary.records_analysed} network records were analysed`))
  for (const phrase of ['Normal percentage', 'Malicious percentage', 'Average predicted-class probability', 'NOT calculated from the current uploaded file', 'False negatives are missed malicious traffic', 'High: prediction produced', 'Review: prediction produced', 'Low: prediction could not', 'not live packet capture', 'no analysis timestamp was inferred']) assert.ok(lines.includes(phrase), phrase)
  assert.ok(lines.includes(percentage(network.model_performance.accuracy)))
  for (const item of network.recommendations) assert.ok(lines.includes(item.message) && lines.includes(item.reason))
  const pdf = createNetworkPdf(network)
  assert.ok(pdf.output().startsWith('%PDF-'))
  assert.ok(pdf.getNumberOfPages() > 1)
  assert.throws(() => createNetworkPdf(null), /No active network analysis/)
  const unavailable = structuredClone(network); unavailable.model_performance.is_current_upload_metric = true
  assert.ok(networkReportLines(unavailable).includes('Official evaluation metadata unavailable; no upload metrics substituted.'))
})

test('important PDF records follow explicit review/rejection ordering without changing input', async () => {
  const { importantReportRecords, networkReportLines } = await server.ssrLoadModule('/src/utils/downloadNetworkPdf.js')
  const base = network.records[0]
  const records = [
    { ...base, record_index: 1, label: 'Normal', reliability: 'High' },
    { ...base, record_index: 2, label: 'Malicious', reliability: 'High' },
    { ...base, record_index: 3, label: null, reliability: 'Low', prediction_status: 'Rejected', rejection_reason: 'Invalid dur' },
    { ...base, record_index: 4, label: 'Malicious', reliability: 'Low' },
    { ...base, record_index: 5, label: 'Malicious', reliability: 'Review' },
  ]
  const original = structuredClone(records)
  assert.deepEqual(importantReportRecords(records).map(row => row.record_index), [5, 4, 3, 2])
  assert.deepEqual(records, original)
  const huge = { ...network, records: Array.from({ length: 82332 }, (_, index) => ({ ...base, record_index: index, label: 'Malicious', reliability: 'Review', quality_findings: Array(100).fill({ column: 'dur', reason: 'Specific evidence' }) })) }
  const lines = networkReportLines(huge)
  assert.equal(lines.filter(line => /^Record \d+:/.test(line)).length, 20)
  assert.equal(lines.filter(line => line.includes('Specific evidence')).length, 60)
  assert.ok(!lines.join(' ').includes('Record 21:'))
  assert.deepEqual(importantReportRecords([{ ...base, label: 'Normal', reliability: 'High' }]), [])
})
