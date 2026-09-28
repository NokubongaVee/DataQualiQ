import assert from 'node:assert/strict'
import test from 'node:test'
import { countAffectedValues, countInvalidFormatValues } from './affectedValues.js'

test('overlapping rules count a cell once, separate columns remain separate cells', () => {
  const issues = [
    { check: 'format', column: 'amount', count: 2, row_indices: [0, 1] },
    { check: 'invalid_currency', column: 'amount', count: 1, row_indices: [1] },
    { check: 'invalid_email', column: 'email', count: 1, row_indices: [1] },
  ]
  assert.equal(countInvalidFormatValues(issues), 3)
  assert.equal(countAffectedValues(issues), 3)
  assert.equal(issues[0].count, 2)
})

test('format card excludes missing, duplicates and outliers', () => {
  const issues = [
    { check: 'missing', column: 'amount', count: 1, row_indices: [0] },
    { check: 'duplicate', column: null, count: 1, row_indices: [1] },
    { check: 'outlier', column: 'amount', count: 1, row_indices: [2] },
  ]
  assert.equal(countInvalidFormatValues(issues), 0)
  assert.equal(countAffectedValues(issues), 3)
})

test('field affected values deduplicate overlapping format, validity and outlier findings', () => {
  const issues = ['format', 'invalid_numeric', 'outlier'].map(check => (
    { check, column: 'amount', count: 1, row_indices: [0] }
  ))
  assert.equal(countAffectedValues(issues), 1)
})

test('empty findings produce zero', () => {
  assert.equal(countInvalidFormatValues(), 0)
  assert.equal(countAffectedValues([]), 0)
})
