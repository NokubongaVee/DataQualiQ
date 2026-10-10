import test from 'node:test'
import assert from 'node:assert/strict'
import { File } from 'node:buffer'
import { analyzeNetwork, backendErrorMessage, validateNetworkFile } from '../api/networkAnalysis.js'
import { NETWORK_SUMMARY_KEY, normalizeNetworkAnalysis, networkSummary, persistNetworkSummary, readNetworkSummary, PROCESSING_STAGES } from './networkAnalysis.js'
import { rememberPage } from './navigation.js'

export function combinedFixture() {
  return { filename: 'network.csv', data_quality: { score: 85, grade: 'B' },
    intrusion_summary: { records_analysed: 2, records_predicted: 2, normal_count: 1, malicious_count: 1, rejected_count: 0, average_predicted_class_probability: .8 },
    model_performance: { source: 'official_test_evaluation', is_current_upload_metric: false, accuracy: .8641111596948938 },
    reliability_summary: { high_count: 1, review_count: 1, low_count: 0, rejected_count: 0 },
    records: [{ record_index: 0, prediction: 0, probability_normal: .7, probability_malicious: .3, reliability: 'High' }, { record_index: 1, prediction: 1, probability_normal: .1, probability_malicious: .9, reliability: 'Review' }],
    pagination: { offset: 0, limit: 100, returned_records: 2, total_records: 2, has_more: false, next_offset: null }, recommendations: [{ priority: 'high', message: 'Review malicious predictions.' }] }
}

test('file validation is limited to selection, CSV extension and size', () => {
  assert.match(validateNetworkFile(null), /upload/)
  assert.match(validateNetworkFile(new File(['a'], 'data.txt')), /CSV/)
  assert.match(validateNetworkFile(new File([], 'data.csv')), /empty/)
  assert.match(validateNetworkFile({ name: 'large.csv', size: 51 * 1024 * 1024 }), /50 MiB/)
  assert.equal(validateNetworkFile(new File(['a\n1'], 'DATA.CSV')), '')
})

test('network request uses configured URL, multipart file and only one bounded page', async () => {
  const file = new File(['a\n1'], 'network.csv')
  const result = combinedFixture()
  let calls = 0
  const received = await analyzeNetwork(file, { baseUrl: 'https://example.test/api/', fetchImpl: async (url, options) => {
    calls++
    assert.equal(url, 'https://example.test/api/analyze-network?offset=0&limit=100')
    assert.equal(options.method, 'POST')
    assert.equal(options.body.get('file').name, 'network.csv')
    assert.equal(await options.body.get('file').text(), 'a\n1')
    assert.equal(options.headers, undefined)
    return { ok: true, json: async () => result }
  } })
  assert.equal(received, result)
  assert.equal(calls, 1)
})

test('structured sections, official source, probabilities, reliability and pagination stay intact', () => {
  const result = combinedFixture()
  assert.equal(normalizeNetworkAnalysis(result), result)
  assert.equal(result.records[1].probability_malicious, .9)
  assert.equal(result.records[1].reliability, 'Review')
  assert.equal(result.model_performance.is_current_upload_metric, false)
  assert.deepEqual(result.pagination, { offset: 0, limit: 100, returned_records: 2, total_records: 2, has_more: false, next_offset: null })
})

test('large response persists only a scalar summary', () => {
  const result = combinedFixture()
  result.records[0].evidence = Array(200000).fill('large row evidence')
  result.recommendations.push({ evidence: result.records[0].evidence })
  const writes = new Map()
  const saved = persistNetworkSummary({ setItem: (key, value) => writes.set(key, value), removeItem() {} }, result)
  const stored = writes.get(NETWORK_SUMMARY_KEY)
  assert.ok(stored.length < 2048)
  assert.equal(writes.size, 1)
  assert.deepEqual(Object.keys(saved).sort(), ['data_quality', 'filename', 'intrusion_summary', 'reliability_summary'])
  assert.ok(!stored.includes('evidence') && !stored.includes('records"') && !stored.includes('recommendations'))
  assert.equal(result.records[0].evidence.length, 200000)
})

test('quota failure never discards the active result or prevents Dashboard navigation', () => {
  const result = combinedFixture()
  const storage = { setItem() { throw new Error('QuotaExceededError') }, removeItem() { throw new Error('SecurityError') } }
  const active = normalizeNetworkAnalysis(result)
  const summary = persistNetworkSummary(storage, active)
  const page = rememberPage(storage, 'overview')
  assert.equal(active, result)
  assert.equal(summary.intrusion_summary.records_analysed, 2)
  assert.equal(page, 'overview')
})

test('refresh reads only summary, never reconstructs records or official metrics', () => {
  const value = JSON.stringify(networkSummary(combinedFixture()))
  const summary = readNetworkSummary({ getItem: () => value })
  assert.equal(summary.intrusion_summary.records_analysed, 2)
  assert.equal(summary.records, undefined)
  assert.equal(summary.model_performance, undefined)
  assert.equal(normalizeNetworkAnalysis(summary), null)
  assert.equal(readNetworkSummary({ getItem: () => 'bad JSON' }), null)
  assert.equal(readNetworkSummary({ getItem: () => 'x'.repeat(10000) }), null)
})

test('backend schema errors list missing features and do not expose object strings', async () => {
  await assert.rejects(analyzeNetwork(new File(['a'], 'bad.csv'), { fetchImpl: async () => ({ ok: false, status: 422, json: async () => ({ detail: { code: 'missing_features', missing_fields: ['dur', 'proto', 'spkts'] } }) }) }), /Missing required features: dur, proto, spkts/)
  assert.match(backendErrorMessage({ detail: { code: 'artifacts_missing', message: 'Saved model unavailable.' } }, 503), /Saved model/)
})

test('unavailable backend, unreadable responses and malformed contracts are actionable', async () => {
  const file = new File(['a'], 'network.csv')
  await assert.rejects(analyzeNetwork(file, { fetchImpl: async () => { throw new Error('network') } }), /backend is unavailable/)
  await assert.rejects(analyzeNetwork(file, { fetchImpl: async () => ({ json: async () => { throw new Error('not JSON') } }) }), /unreadable response/)
  await assert.rejects(analyzeNetwork(file, { fetchImpl: async () => ({ ok: true, json: async () => ({ score: 100 }) }) }), /incompatible network analysis/)
})

test('record page size and official metric attribution are validated', () => {
  const result = combinedFixture()
  result.records = Array(1001).fill(result.records[0])
  assert.equal(normalizeNetworkAnalysis(result), null)
  const ambiguous = combinedFixture()
  ambiguous.model_performance.is_current_upload_metric = true
  assert.equal(normalizeNetworkAnalysis(ambiguous), null)
})

test('processing stages cover the combined request without percentages', () => {
  assert.deepEqual(PROCESSING_STAGES, ['Reading dataset', 'Checking data quality', 'Preparing network features', 'Running intrusion detection', 'Preparing combined results'])
})
