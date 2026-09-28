// The API identifies cells by column and zero-based data-row index.
// Keep raw issue objects/counts intact; deduplicate only displayed value totals.
export function countAffectedValues(issues = []) {
  const rowsByColumn = new Map()
  let rowLevelCount = 0
  for (const issue of issues) {
    if (issue.column == null) {
      // Duplicate-row findings have no column and retain their original count.
      rowLevelCount += issue.count || 0
      continue
    }
    if (!rowsByColumn.has(issue.column)) rowsByColumn.set(issue.column, new Set())
    const rows = rowsByColumn.get(issue.column)
    for (const row of issue.row_indices || []) rows.add(row)
  }
  return rowLevelCount + [...rowsByColumn.values()].reduce((sum, rows) => sum + rows.size, 0)
}

export function countInvalidFormatValues(issues = []) {
  return countAffectedValues(issues.filter(issue => (
    issue.check === 'format' || issue.check?.startsWith('invalid_')
  )))
}
