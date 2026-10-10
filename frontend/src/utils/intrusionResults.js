// Only presentation of supplied results. No classification or reliability inference.
export const QUALITY_LABELS = {
  good: 'Good', missing: 'Missing fields', missing_fields: 'Missing fields',
  inconsistent: 'Inconsistent values', inconsistent_values: 'Inconsistent values',
  invalid: 'Invalid values', invalid_values: 'Invalid values',
}
export const RELIABILITY_LABELS = { high: 'High', review: 'Review', low: 'Low — verify' }

export function nonnegativeNumber(value) {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null
}

export function percentage(value) {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1
    ? `${Number((value * 100).toFixed(1))}%` : 'Pending'
}

export function normaliseStatus(value) {
  return typeof value === 'string' ? value.trim().toLowerCase().replace(/[ -]+/g, '_') : ''
}

export function getIntrusionResults(result) {
  const supplied = result?.intrusion_detection
  const data = supplied && typeof supplied === 'object' && !Array.isArray(supplied) ? supplied : null
  const records = Array.isArray(data?.records)
    ? data.records.filter(record => record && typeof record === 'object' && !Array.isArray(record)) : []
  const flaggedAttacks = records.filter(record => normaliseStatus(record.prediction) === 'malicious'
    && ['missing', 'missing_fields', 'inconsistent', 'inconsistent_values', 'invalid', 'invalid_values']
      .includes(normaliseStatus(record.data_quality_status)))
  const normal = nonnegativeNumber(data?.normal_count)
  const malicious = nonnegativeNumber(data?.malicious_count)
  const total = nonnegativeNumber(data?.total_records)
  // Do not silently turn partial counts or unclassified rows into a full distribution.
  const classified = normal !== null && malicious !== null ? normal + malicious : null
  const distribution = classified > 0 && (total === null || total === classified)
    ? { normal: normal / classified, malicious: malicious / classified } : null
  return { data, records, flaggedAttacks, normal, malicious, total, distribution }
}
