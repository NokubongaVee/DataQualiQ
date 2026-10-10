import TrafficClassification from './TrafficClassification'
import RecordAttention from './RecordAttention'
import NetworkRecommendations from './NetworkRecommendations'
import { percentage } from '../utils/intrusionResults'

const count = value => Number.isFinite(value) ? value.toLocaleString() : 'Not available'
const probability = value => value == null ? 'Not available' : percentage(value)

export default function NetworkDashboard({ result }) {
  const { intrusion_summary: intrusion, data_quality: quality, model_performance: model,
    reliability_summary: reliability, records, pagination, recommendations } = result
  const classified = intrusion.normal_count + intrusion.malicious_count
  const distribution = classified > 0 ? { normal: intrusion.normal_count / classified, malicious: intrusion.malicious_count / classified } : null
  const official = model.source === 'official_test_evaluation' && model.is_current_upload_metric === false
  const cards = [
    ['Records analysed', count(intrusion.records_analysed), 'All uploaded records', ''],
    ['Normal traffic', count(intrusion.normal_count), 'Predicted Normal', 'text-accent'],
    ['Attacks detected', count(intrusion.malicious_count), 'Predicted Malicious · verify with security evidence', 'text-attack'],
    ['Data-quality score', `${quality.score}/100`, `Grade ${quality.grade || 'Not available'} · heuristic score`, 'text-warning'],
    ['Average predicted-class probability', probability(intrusion.average_predicted_class_probability), 'Predicted records only · not calibrated certainty', ''],
  ]
  const levels = [['High', 'high_count', 'high'], ['Review', 'review_count', 'review'], ['Low', 'low_count', 'low']]
  return <div className="network-dashboard">
    <section className="summary-grid" aria-label="Analysis summary">{cards.map(([label, value, note, color]) => <article className="panel summary-card" key={label}>
      <span className="muted">{label}</span><strong className={color}>{value}</strong><small>{note}</small>
    </article>)}</section>
    <div className="middle-grid">
      <div className="network-traffic"><TrafficClassification intrusion={{ distribution, normal: intrusion.normal_count, malicious: intrusion.malicious_count }} />
        <p className="panel-note">{count(classified)} classified records: {count(intrusion.normal_count)} Normal / {count(intrusion.malicious_count)} Malicious. Rejected records are excluded from chart percentages.</p></div>
      <section className="panel middle-panel"><h2>Data quality</h2><div className="network-quality-score"><strong>{quality.score}/100</strong><span>Grade {quality.grade || 'Not available'}</span></div>
        <p className="panel-note">Heuristic quality score, not a percentage of correct data.</p>
        <ul className="network-quality-counts">{[['Missing values', 'missing_values'], ['Duplicates', 'duplicates'], ['Invalid values', 'invalid_values'], ['Inconsistencies', 'inconsistencies'], ['Analytical anomalies', 'analytical_anomalies']].map(([label, key]) => <li key={key}><span>{label}</span><div><strong>{count(quality[key]?.affected_records)}</strong><small> affected records · {count(quality[key]?.occurrences)} occurrences</small></div></li>)}</ul>
        <p className="panel-note">Counts can overlap. Analytical anomalies are not automatically input errors or attacks.</p>
      </section>
      <section className="panel middle-panel"><h2>Model performance (official test evaluation)</h2>
        <div className="model-grid">{[['Accuracy', 'accuracy'], ['Precision', 'precision'], ['Recall', 'recall'], ['F1-score', 'f1']].map(([label, key]) => <div key={key}><span>{label}</span><strong>{official ? probability(model[key]) : 'Not available'}</strong></div>)}</div>
        <p className="panel-note">{official ? 'Saved official test evaluation; not calculated from the current upload.' : 'Official evaluation metadata is unavailable.'}</p>
        {official && <p className="panel-note">{model.dataset} · {count(model.records_evaluated)} evaluated records</p>}
      </section>
    </div>
    <section className="panel middle-panel network-reliability"><div className="panel-heading"><h2>Reliability</h2><span className="muted">Input integrity · separate from model probability</span></div>
      <div className="network-reliability-grid">{levels.map(([label, key, style]) => <div key={key}><div><span className={`reliability-${style}`}>{label}</span><strong>{count(reliability[key])}</strong></div><progress className={`network-bar-${style}`} value={reliability[key]} max={intrusion.records_analysed || 1} aria-label={`${label} reliability records`} /></div>)}
        <div><div><span>Rejected</span><strong>{count(reliability.rejected_count)}</strong></div><small>Included in Low; no prediction or probability.</small></div>
      </div>
    </section>
    <div className="results-grid">
      <section className="panel records-panel"><div className="panel-heading"><h2>Record-level results preview</h2><span className="muted">{count(pagination.returned_records)} returned / {count(pagination.total_records)} total</span></div>
        {records.length ? <div className="table-scroll"><table><thead><tr>{['Record', 'Prediction', 'Probability', 'Reliability', 'Quality / Issue summary', 'Rejection reason'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{records.map(record => <tr key={record.record_index}>
          <td className="mono">#{record.record_index + 1}</td><td><span className={`badge prediction-${record.prediction_status === 'Rejected' ? 'pending' : record.label?.toLowerCase()}`}>{record.prediction_status === 'Rejected' ? 'Rejected' : record.label || 'Not available'}</span></td>
          <td>{record.prediction_status === 'Rejected' ? 'Not available' : probability(record.predicted_class_probability)}</td>
          <td><span className={`badge reliability-${record.reliability?.toLowerCase()}`}>{record.reliability || 'Not available'}</span></td>
          <td className="network-evidence"><span>{record.quality_status || 'Not available'}</span>{record.quality_finding_count > 0 && <small>{count(record.quality_finding_count)} findings{record.quality_findings_truncated ? ' · evidence truncated' : ''}</small>}{record.quality_findings?.length > 0 && <details><summary>View returned evidence</summary><ul>{record.quality_findings.slice(0, 10).map((finding, index) => <li key={index}>{finding.column ? `${finding.column}: ` : ''}{finding.reason || finding.check}</li>)}</ul></details>}</td>
          <td className="network-evidence">{record.rejection_reason || (record.prediction_status === 'Rejected' ? record.reliability_reason : '—')}<RecordAttention record={record} /></td>
        </tr>)}</tbody></table></div> : <p className="panel-note">No record rows were returned for this page.</p>}
      </section>
      <NetworkRecommendations recommendations={recommendations} />
    </div>
  </div>
}
