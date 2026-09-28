import assert from 'node:assert/strict'
import { after, before, test } from 'node:test'
import React from 'react'
import { renderToString } from 'react-dom/server'
import { createServer } from 'vite'

let server, IssueCard
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })
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
