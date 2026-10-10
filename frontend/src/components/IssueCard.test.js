import assert from 'node:assert/strict'
import { getDisplayIssue } from '../utils/issueDisplay.js'
import { after, before, test } from 'node:test'
import React from 'react'
import { renderToString } from 'react-dom/server'
import { createServer } from 'vite'

let server, IssueCard
before(async () => {
  server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: 'custom' })
  IssueCard = (await server.ssrLoadModule('/src/components/IssueCard.jsx')).default
})
after(async () => { await server?.close() })

function render(evidence) {
  return renderToString(React.createElement(IssueCard, {
    title: 'Values to review', severity: 'high', description: 'Assessment completed', suggestion: 'Check source records.', evidence,
  }))
}

test('cards retain the summary and recommendation without evidence sections', () => {
  for (const evidence of [undefined, {}, { examples: 'bad@example' }, { examples: ['invalid'], explanation: { why: 'Extra explanation' } }]) {
    const html = render(evidence)
    assert.ok(html.includes('Values to review'))
    assert.ok(html.includes('Assessment completed'))
    assert.ok(html.includes('Check source records.'))
    assert.ok(html.includes('High'))
    assert.ok(!html.includes('Why was this flagged?'))
    assert.ok(!html.includes('Supporting evidence'))
    assert.ok(!html.includes('Extra explanation'))
    assert.ok(!html.includes('<details'))
  }
})


test('current applicant results show consequences and action inside the existing card', () => {
  const issue = { issue_to_review: { title: 'Missing email', description: '6 of 10 records have no email.', impact: 'Missing contact details can delay interview invitations.', severity: 'high' }, recommendation: { action: 'Check the original application forms.' } }
  const html = renderToString(React.createElement(IssueCard, getDisplayIssue(issue)))
  assert.ok(html.includes('6 of 10 records have no email. Missing contact details can delay interview invitations.'))
  assert.ok(html.includes('Check the original application forms.'))
  assert.ok(!html.includes('<details'))
  assert.ok(!html.includes('Supporting evidence'))
})

test('saved legacy results and explanation-only consequences remain readable without duplicates', () => {
  const impact = 'Missing ages limit age-based summaries.'
  assert.equal(getDisplayIssue({ legacy: { description: 'Age missing.', suggestion: 'Confirm whether age is required.', severity: 'low' }, evidence: { explanation: { consequence: impact } } }).description, `Age missing. ${impact}`)
  assert.equal(getDisplayIssue({ description: `Age missing. ${impact}`, impact }).description, `Age missing. ${impact}`)
  assert.equal(getDisplayIssue({ description: 'Old finding.' }).description, 'Old finding.')
})

test('severity badges use red, orange, and green including lowercase API values', () => {
  for (const [severity, color] of [['high', '#E24B4A'], ['medium', '#EA580C'], ['low', '#1D9E75']]) {
    const html = renderToString(React.createElement(IssueCard, { title: 'Review', severity }))
    assert.ok(html.includes(color))
  }
})
