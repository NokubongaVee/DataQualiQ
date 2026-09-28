import assert from 'node:assert/strict'
import { test } from 'node:test'
import { restorePage, rememberPage } from './navigation.js'

function storage() {
  const values = new Map([['assessmentResult', '{"score":80}']])
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) }
}

test('refresh respects Upload even when previous assessment results exist', () => {
  const saved = storage()
  rememberPage(saved, 'overview')
  rememberPage(saved, 'upload')
  assert.equal(restorePage(saved), 'upload')
  assert.ok(saved.getItem('assessmentResult'))
})

test('each dashboard page survives refresh; missing or invalid pages open Upload', () => {
  const saved = storage()
  assert.equal(restorePage(saved), 'upload')
  for (const page of ['overview', 'issues', 'by-field', 'actions']) {
    rememberPage(saved, page)
    assert.equal(restorePage(saved), page)
  }
  saved.setItem('currentPage', 'invalid')
  assert.equal(restorePage(saved), 'upload')
})
