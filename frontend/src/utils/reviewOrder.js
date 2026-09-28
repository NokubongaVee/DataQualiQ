const priorities = { high: 3, medium: 2, low: 1 }

export function rankReviews(issues = []) {
  return [...issues].sort((a, b) => {
    const ae = a.issue_to_review?.evidence || {}
    const be = b.issue_to_review?.evidence || {}
    const ap = priorities[String(a.recommendation?.priority || a.issue_to_review?.severity || a.severity).toLowerCase()] || 0
    const bp = priorities[String(b.recommendation?.priority || b.issue_to_review?.severity || b.severity).toLowerCase()] || 0
    return bp - ap || (be.priority_score || 0) - (ae.priority_score || 0)
      || (be.affected_percentage || 0) - (ae.affected_percentage || 0)
  })
}
