// Share the same readable finding summary across Overview and Issues.
export function getDisplayIssue(issue) {
  const review = issue.issue_to_review || issue
  const recommendation = issue.recommendation || {}
  const legacy = issue.legacy || {}
  const evidence = review.evidence || issue.evidence || {}
  const description = review.description || issue.description || legacy.description || ''
  const impact = review.impact || issue.impact || evidence.explanation?.consequence || ''
  // Older results may already include the consequence in their description.
  const summary = impact && !description.includes(impact)
    ? `${description} ${impact}`.trim()
    : description

  return {
    title: review.title || issue.title || legacy.title || 'Data issue detected',
    description: summary,
    suggestion: recommendation.action || issue.suggestion || legacy.suggestion || 'Review the affected records.',
    severity: review.severity || issue.severity || legacy.severity || 'Medium',
  }
}
