import { countInvalidFormatValues } from '../utils/affectedValues'

export default function DataQualityPanel({ result }) {
  const issues = result?.issues || []
  const sum = check => issues.filter(issue => issue.check === check).reduce((total, issue) => total + (issue.count || 0), 0)
  const missingRows = new Set(issues.filter(issue => issue.check === 'missing').flatMap(issue => issue.row_indices || []))
  const totalCells = result?.total_rows * result?.total_columns
  const completeness = totalCells > 0 ? Math.max(0, 100 * (1 - sum('missing') / totalCells)) : null
  const counts = [[sum('missing'), 'Missing values'], [sum('duplicate'), 'Duplicate rows'], [countInvalidFormatValues(issues), 'Invalid / inconsistent values'], [sum('outlier'), 'Statistical outliers']]
  return <section className="panel middle-panel" id="data-quality">
    <h2>Data quality</h2>
    {result ? <>
      <div className="quality-metric"><div><span>Cell completeness</span><strong>{completeness === null ? 'Unavailable' : `${Number(completeness.toFixed(1))}%`}</strong></div>{completeness !== null && <progress max="100" value={completeness} aria-label="Cell completeness" />}</div>
      <div className="quality-metric"><div><span>Assessment score</span><strong>{result.score}/100</strong></div><progress max="100" value={Math.min(100, Math.max(0, result.score))} aria-label="Heuristic assessment score" /></div>
      <p className="panel-note">Heuristic score; not a percentage of correct data. Prediction reliability is pending unless supplied by the model.</p>
      <ul className="quality-counts">{counts.map(([count, label]) => <li key={label}><span>{label}</span><strong>{count.toLocaleString()}</strong></li>)}</ul>
      {result.total_rows > 0 && <p className="panel-note">Missing values affect {missingRows.size.toLocaleString()} of {result.total_rows.toLocaleString()} rows ({Number((100 * missingRows.size / result.total_rows).toFixed(1))}%). {result.translated_issues.length} findings to review.</p>}
      <a className="text-link" href="#quality-findings" onClick={() => { const details = document.getElementById('quality-findings'); if (details) details.open = true }}>Review quality findings →</a>
    </> : <div className="empty-state"><strong>No quality assessment yet</strong><p>Upload a traffic CSV to check missing values, duplicate records, invalid formats, inconsistencies and statistical outliers.</p></div>}
  </section>
}
