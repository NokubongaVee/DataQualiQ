export default function NetworkAnalysisReady({ result }) {
  const summary = result.intrusion_summary
  const quality = result.data_quality
  const reliability = result.reliability_summary
  return <section className="panel" aria-label="Active network analysis">
    <h2>Network analysis complete</h2>
    <p className="filename mono">{result.filename}</p>
    <p>{summary.records_analysed.toLocaleString()} records analysed · {summary.normal_count.toLocaleString()} Normal · {summary.malicious_count.toLocaleString()} Malicious</p>
    <p>Quality score {quality.score}/100 · Grade {quality.grade || '—'}</p>
    <p>High {reliability.high_count.toLocaleString()} · Review {reliability.review_count.toLocaleString()} · Low {reliability.low_count.toLocaleString()} · Rejected {summary.rejected_count.toLocaleString()}</p>
    <p className="panel-note">{result.records.length} record results received of {result.pagination.total_records.toLocaleString()}. Detailed dashboard and report views are not available yet.</p>
    <p className="panel-note">Model probabilities are estimates. Saved performance metrics describe the official test evaluation, not this upload.</p>
  </section>
}
