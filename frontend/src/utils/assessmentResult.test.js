import assert from 'node:assert/strict'
import { test } from 'node:test'
import { assessmentSummary, persistAssessmentSummary, readAssessmentSummary, clearStoredAssessment, normalizeAssessmentResult, getSessionStorage, SUMMARY_KEY } from './assessmentResult.js'
import { rememberPage, restorePage } from './navigation.js'

const result = { filename: 'UNSW_NB15_training-set.csv', total_rows: 175341, total_columns: 45, score: 100, grade: 'A' }
function storage() {
  const values = new Map()
  return { values, getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) }
}

test('large responses retain evidence in memory but persist only bounded backend scalars', () => {
  const evidence = 'x'.repeat(12 * 1024 * 1024)
  const response = { ...result, issues: [{ evidence }], translated_issues: [{ evidence }], intrusion_detection: { records: [evidence] } }
  const saved = storage()
  saved.setItem('assessmentResult', 'legacy payload')
  assert.deepEqual(persistAssessmentSummary(saved, response), result)
  assert.equal(saved.getItem('assessmentResult'), null)
  assert.ok(saved.getItem(SUMMARY_KEY).length < 1024)
  assert.deepEqual(readAssessmentSummary(saved), result)
  assert.equal(normalizeAssessmentResult(response).issues[0].evidence, evidence)
  assert.equal(normalizeAssessmentResult(response).intrusion_detection, response.intrusion_detection)
})

test('summary bounds strings and rejects nested or invalid numeric fields', () => {
  const summary = assessmentSummary({ ...result, filename: 'x'.repeat(10000), grade: 'y'.repeat(10000), total_rows: [], total_columns: Infinity, issues: [result] })
  assert.ok(JSON.stringify(summary).length < 1024)
  assert.deepEqual(Object.keys(summary), ['filename', 'score', 'grade'])
  assert.equal(assessmentSummary({ filename: 'bad', score: NaN }), null)
})

test('quota and disabled storage never block successful results or navigation', () => {
  const blocked = { setItem() { throw new Error('QuotaExceededError') }, getItem() { throw new Error('SecurityError') }, removeItem() { throw new Error('SecurityError') } }
  assert.deepEqual(persistAssessmentSummary(blocked, result), result)
  assert.equal(rememberPage(blocked, 'reports'), 'reports')
  assert.equal(restorePage(blocked), 'upload')
  assert.equal(readAssessmentSummary(blocked), null)
  assert.doesNotThrow(() => clearStoredAssessment(blocked))
  assert.equal(getSessionStorage(), null)
})

test('refresh restores only a summary; malformed and legacy full results are never loaded', () => {
  const saved = storage()
  saved.setItem('assessmentResult', JSON.stringify(result))
  assert.equal(readAssessmentSummary(saved), null)
  saved.setItem(SUMMARY_KEY, '{invalid')
  assert.equal(readAssessmentSummary(saved), null)
  saved.setItem(SUMMARY_KEY, 'x'.repeat(3000))
  assert.equal(readAssessmentSummary(saved), null)
  persistAssessmentSummary(saved, result)
  clearStoredAssessment(saved)
  assert.equal(readAssessmentSummary(saved), null)
})
