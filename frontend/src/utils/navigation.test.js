import assert from 'node:assert/strict'
import { test } from 'node:test'
import { restorePage, rememberPage } from './navigation.js'

function storage() {
  const values = new Map([['assessmentSummary', '{"score":80}']])
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) }
}

test('refresh respects Upload even when previous assessment results exist', () => {
  const saved = storage()
  rememberPage(saved, 'overview')
  rememberPage(saved, 'upload')
  assert.equal(restorePage(saved), 'upload')
  assert.ok(saved.getItem('assessmentSummary'))
})

test('each dashboard page survives refresh; missing or invalid pages open Upload', () => {
  const saved = storage()
  assert.equal(restorePage(saved), 'upload')
  for (const page of ['overview', 'data-quality', 'intrusion-detection', 'results', 'reports']) {
    rememberPage(saved, page)
    assert.equal(restorePage(saved), page)
  }
  saved.setItem('currentPage', 'invalid')
  assert.equal(restorePage(saved), 'upload')
})
