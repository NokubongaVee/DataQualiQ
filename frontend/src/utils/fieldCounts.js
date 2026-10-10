// Group by column identity, not its display label. null represents row findings.
export function getFieldCounts(issues = []) {
  const counts = new Map()
  for (const issue of issues) {
    const column = issue.column ?? null
    counts.set(column, (counts.get(column) || 0) + (issue.count || 0))
  }
  let rowLabel = 'Other'
  while (counts.has(rowLabel)) rowLabel += ' (dataset)'
  return [...counts].map(([column, count]) => ({
    column, name: column ?? rowLabel, count,
  })).sort((a, b) => b.count - a.count)
}
