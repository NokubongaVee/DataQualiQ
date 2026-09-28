import assert from 'node:assert/strict'
import test from 'node:test'
import { rankReviews } from './reviewOrder.js'

test('sorts by priority and measured rank without mutating findings', () => {
  const input = [
    { recommendation: { priority: 'low' }, issue_to_review: { evidence: { priority_score: .1 } } },
    { recommendation: { priority: 'high' }, issue_to_review: { evidence: { priority_score: .7 } } },
    { recommendation: { priority: 'high' }, issue_to_review: { evidence: { priority_score: .9 } } },
  ]
  assert.deepEqual(rankReviews(input), [input[2], input[1], input[0]])
  assert.equal(input[0].recommendation.priority, 'low')
})

test('top four are priority ranked, with compatible legacy severity casing', () => {
  const low = Array.from({ length: 4 }, () => ({ severity: 'Low' }))
  const high = { severity: 'High' }
  assert.equal(rankReviews([...low, high]).slice(0, 4)[0], high)
  assert.deepEqual(rankReviews(), [])
})
