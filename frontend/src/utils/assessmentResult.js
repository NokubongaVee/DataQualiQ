export const SUMMARY_KEY = 'assessmentSummary'

export function getSessionStorage() {
  try { return window.sessionStorage } catch { return null }
}

export function normalizeAssessmentResult(result) {
  if (!result || typeof result !== 'object' || !Number.isFinite(result.score)
    || typeof result.filename !== 'string') return null
  return {
    ...result,
    issues: Array.isArray(result.issues) ? result.issues.filter(Boolean) : [],
    translated_issues: Array.isArray(result.translated_issues) ? result.translated_issues.filter(Boolean) : [],
  }
}

// Explicit scalar allowlist: never copy findings, evidence, records or arbitrary keys.
export function assessmentSummary(result) {
  if (!result || typeof result.filename !== 'string' || !Number.isFinite(result.score)) return null
  const summary = { filename: result.filename.slice(0, 512), score: result.score }
  for (const key of ['total_rows', 'total_columns']) {
    if (Number.isFinite(result[key]) && result[key] >= 0) summary[key] = result[key]
  }
  if (typeof result.grade === 'string') summary.grade = result.grade.slice(0, 16)
  return summary
}

export function persistAssessmentSummary(storage, result) {
  const summary = assessmentSummary(result)
  try { storage?.removeItem('assessmentResult') } catch { /* Legacy cleanup is best effort. */ }
  try { if (summary) storage?.setItem(SUMMARY_KEY, JSON.stringify(summary)) } catch { /* Memory remains authoritative. */ }
  return summary
}

export function readAssessmentSummary(storage) {
  try {
    const saved = storage?.getItem(SUMMARY_KEY)
    return saved && saved.length <= 2048 ? assessmentSummary(JSON.parse(saved)) : null
  } catch { return null }
}

export function clearStoredAssessment(storage) {
  for (const key of ['assessmentResult', SUMMARY_KEY]) {
    try { storage?.removeItem(key) } catch { /* Storage must never prevent an assessment. */ }
  }
}
