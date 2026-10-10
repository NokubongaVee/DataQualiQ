export default function NoActiveAssessment({ summary, onNavigate }) {
  return <section className="panel empty-state">
    <h2>No active analysis is available.</h2>
    <p>Please upload and analyse the network dataset again.</p>
    {summary && <div><h3>Previous analysis summary only</h3><p>{summary.filename}</p>{summary.intrusion_summary ? <p>{summary.intrusion_summary.records_analysed.toLocaleString()} records · Score {summary.data_quality.score}/100 · Grade {summary.data_quality.grade || '—'}</p> : <p>{summary.total_rows?.toLocaleString()} records · {summary.total_columns} fields · Score {summary.score}/100{summary.grade ? ` · Grade ${summary.grade}` : ''}</p>}<p>Detailed findings, predictions and report evidence are unavailable after refresh.</p></div>}
    <button className="button primary" onClick={() => onNavigate('upload')}>Upload &amp; Analyse</button>
  </section>
}
