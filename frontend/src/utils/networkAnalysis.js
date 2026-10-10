export const NETWORK_SUMMARY_KEY = 'networkAnalysisSummary'
export const PROCESSING_STAGES = ['Reading dataset', 'Checking data quality', 'Preparing network features', 'Running intrusion detection', 'Preparing combined results']

const object = value => value && typeof value === 'object' && !Array.isArray(value)
const count = value => Number.isInteger(value) && value >= 0

// Keep the backend contract intact; presentation must not replace it with aliases.
export function normalizeNetworkAnalysis(result) {
  if (!object(result) || typeof result.filename !== 'string'
    || !['data_quality', 'intrusion_summary', 'model_performance', 'reliability_summary', 'pagination'].every(key => object(result[key]))
    || !Array.isArray(result.records) || result.records.length > 1000 || !Array.isArray(result.recommendations)
    || !Number.isFinite(result.data_quality.score)
    || !['records_analysed', 'records_predicted', 'normal_count', 'malicious_count', 'rejected_count'].every(key => count(result.intrusion_summary[key]))
    || !['high_count', 'review_count', 'low_count', 'rejected_count'].every(key => count(result.reliability_summary[key]))
    || result.model_performance.source !== 'official_test_evaluation' || result.model_performance.is_current_upload_metric !== false
    || !['offset', 'limit', 'returned_records', 'total_records'].every(key => count(result.pagination[key]))
    || result.pagination.limit > 1000 || result.pagination.returned_records !== result.records.length
    || typeof result.pagination.has_more !== 'boolean') return null
  return result
}

export function networkSummary(result) {
  if (!object(result) || typeof result.filename !== 'string' || !object(result.data_quality)
    || !Number.isFinite(result.data_quality.score) || !object(result.intrusion_summary) || !object(result.reliability_summary)) return null
  const summary = { filename: result.filename.slice(0, 512), data_quality: { score: result.data_quality.score }, intrusion_summary: {}, reliability_summary: {} }
  if (typeof result.data_quality.grade === 'string') summary.data_quality.grade = result.data_quality.grade.slice(0, 16)
  for (const [section, keys] of [['intrusion_summary', ['records_analysed', 'normal_count', 'malicious_count']], ['reliability_summary', ['high_count', 'review_count', 'low_count', 'rejected_count']]]) {
    for (const key of keys) {
      if (!count(result[section][key])) return null
      summary[section][key] = result[section][key]
    }
  }
  return summary
}

export function persistNetworkSummary(storage, result) {
  const summary = networkSummary(result)
  try { storage?.removeItem('assessmentResult') } catch { /* Legacy cleanup is optional. */ }
  try { storage?.removeItem('assessmentSummary') } catch { /* A previous generic summary must not win. */ }
  try { if (summary) storage?.setItem(NETWORK_SUMMARY_KEY, JSON.stringify(summary)) } catch { /* Successful memory state remains authoritative. */ }
  return summary
}

export function readNetworkSummary(storage) {
  try {
    const saved = storage?.getItem(NETWORK_SUMMARY_KEY)
    return saved && saved.length <= 2048 ? networkSummary(JSON.parse(saved)) : null
  } catch { return null }
}

export function clearNetworkSummary(storage) {
  try { storage?.removeItem(NETWORK_SUMMARY_KEY) } catch { /* Clearing memory must work without storage. */ }
}
