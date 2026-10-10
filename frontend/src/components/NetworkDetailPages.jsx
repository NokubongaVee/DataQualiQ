import { useState } from 'react'
import TrafficClassification from './TrafficClassification'
import NetworkDashboard from './NetworkDashboard'
import RecordAttention from './RecordAttention'
import { percentage } from '../utils/intrusionResults'
import { downloadNetworkPdf } from '../utils/downloadNetworkPdf'

const number = value => Number.isFinite(value) ? value.toLocaleString() : 'Not available'
const probability = value => value == null ? 'Not available' : percentage(value)
const groups = [['Missing values', 'missing_values', 'Quality issues'], ['Duplicates', 'duplicates', 'Quality issues'], ['Invalid values', 'invalid_values', 'Data errors'], ['Inconsistencies', 'inconsistencies', 'Quality issues'], ['Statistical / analytical anomalies', 'analytical_anomalies', 'Analytical/security anomalies']]

function QualityDetails({ result }) {
  const quality = result.data_quality
  return <>
    <section className="panel middle-panel"><h2>Quality score {quality.score}/100 · Grade {quality.grade}</h2><p className="panel-note">Heuristic data-quality score, separate from prediction accuracy. Statistical / analytical anomalies are not automatically bad data or confirmed attacks.</p>
      <div className="detail-grid">{groups.map(([label, key, category]) => <article className="panel middle-panel" key={key}><h3>{label}</h3><span className="muted">{category}</span><p>{number(quality[key]?.affected_records)} affected records · {number(quality[key]?.occurrences)} occurrences · {number(quality[key]?.finding_count)} findings</p>
        <ul>{quality[key]?.by_column?.map(item => <li key={item.column}>{item.column}: {number(item.occurrences)} occurrences</li>)}</ul>{quality[key]?.columns_truncated && <p className="panel-note">Field summary truncated by the backend.</p>}</article>)}</div>
      <p className="panel-note">Occurrences can overlap across fields and findings. Duplicate counts exclude the first occurrence.</p>
    </section>
    <section className="panel middle-panel"><h2>Quality warnings</h2>{quality.warnings?.length ? <ul>{quality.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul> : <p>No quality warnings were returned.</p>}</section>
    <section className="panel middle-panel"><h2>Returned record finding evidence</h2><p className="panel-note">Only evidence from the current returned page is available. A field summary is not a complete row-level finding list.</p>
      {result.records.some(record => record.quality_finding_count > 0) ? result.records.filter(record => record.quality_finding_count > 0).map(record => <details className="field-details" key={record.record_index}><summary>Record #{record.record_index + 1} · {number(record.quality_finding_count)} findings{record.quality_findings_truncated ? ' · evidence truncated' : ''}</summary><ul>{record.quality_findings.slice(0, 10).map((finding, index) => <li key={index}>{finding.column || 'Dataset'} · {finding.check} · {finding.category}: {finding.reason}</li>)}</ul></details>) : <p>No record findings were returned for this page.</p>}
    </section>
  </>
}

function IntrusionDetails({ result }) {
  const { intrusion_summary: summary, model_performance: model, reliability_summary: reliability } = result
  const total = summary.normal_count + summary.malicious_count
  const official = model.source === 'official_test_evaluation' && model.is_current_upload_metric === false
  return <>
    <div className="detail-grid"><TrafficClassification intrusion={{ normal: summary.normal_count, malicious: summary.malicious_count, distribution: total ? { normal: summary.normal_count / total, malicious: summary.malicious_count / total } : null }} /><section className="panel middle-panel"><h2>Current upload predictions</h2><dl className="model-info">{[['Records analysed', number(summary.records_analysed)], ['Normal traffic', number(summary.normal_count)], ['Malicious traffic', number(summary.malicious_count)], ['Normal %', total ? percentage(summary.normal_count / total) : 'Not available'], ['Malicious %', total ? percentage(summary.malicious_count / total) : 'Not available'], ['Average predicted-class probability', probability(summary.average_predicted_class_probability)]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl><p className="panel-note">Percentages use predicted records only; rejected records are excluded. Probability is a model estimate, not calibrated certainty or input reliability.</p></section></div>
    <section className="panel middle-panel"><h2>Model performance — official test evaluation</h2><p className="panel-note">Saved official evaluation, not performance on the current upload.</p>{official ? <><div className="model-grid">{[['Accuracy', 'accuracy'], ['Precision', 'precision'], ['Recall', 'recall'], ['F1-score', 'f1']].map(([label, key]) => <div key={key}><span>{label}</span><strong>{probability(model[key])}</strong></div>)}</div><p>{model.dataset} · {number(model.records_evaluated)} evaluated records</p>
      <h3>Confusion matrix</h3><div className="table-scroll"><table><caption>Official evaluation: rows actual, columns predicted</caption><thead><tr><th scope="col">Actual / Predicted</th><th scope="col">Normal</th><th scope="col">Malicious</th></tr></thead><tbody><tr><th scope="row">Normal</th><td>True Normal: {number(model.confusion_matrix?.[0]?.[0])}</td><td>False Alarm: {number(model.confusion_matrix?.[0]?.[1])}</td></tr><tr><th scope="row">Malicious</th><td>Missed Attack: {number(model.confusion_matrix?.[1]?.[0])}</td><td>Correctly Detected Attack: {number(model.confusion_matrix?.[1]?.[1])}</td></tr></tbody></table></div><p className="panel-note">False Positive = normal traffic classified as malicious. False Negative = malicious traffic classified as normal: a missed attack.</p></> : <p>Official evaluation metadata is unavailable.</p>}</section>
    <section className="panel middle-panel"><h2>Reliability — input integrity</h2><div className="model-grid">{[['High', 'high_count'], ['Review', 'review_count'], ['Low', 'low_count'], ['Rejected', 'rejected_count']].map(([label, key]) => <div key={key}><span>{label}</span><strong>{number(reliability[key])}</strong></div>)}</div><p className="panel-note">Reliability is separate from model probability. Low records are rejected; they have no prediction. Rejected counts are included in Low.</p></section>
  </>
}

function RecordDetails({ result }) {
  const [prediction, setPrediction] = useState('all')
  const [reliability, setReliability] = useState('all')
  const records = result.records.filter(record => (prediction === 'all' || (record.prediction_status === 'Rejected' ? 'Rejected' : record.label) === prediction) && (reliability === 'all' || record.reliability === reliability))
  return <section className="panel records-panel network-dashboard"><h2>Record-level results</h2><p>{number(result.pagination.returned_records)} returned records of {number(result.pagination.total_records)} · Offset {number(result.pagination.offset)} · Limit {number(result.pagination.limit)}</p>
    <div className="panel-heading"><label className="table-filter">Prediction<select value={prediction} onChange={event => setPrediction(event.target.value)}>{['all', 'Normal', 'Malicious', 'Rejected'].map(value => <option key={value} value={value}>{value === 'all' ? 'All predictions' : value}</option>)}</select></label><label className="table-filter">Reliability<select value={reliability} onChange={event => setReliability(event.target.value)}>{['all', 'High', 'Review', 'Low'].map(value => <option key={value} value={value}>{value === 'all' ? 'All reliability' : value}</option>)}</select></label></div>
    <div className="table-scroll"><table><thead><tr>{['Record', 'Prediction', 'Predicted probability', 'Reliability', 'Quality status', 'Quality findings', 'Rejection reason'].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead><tbody>{records.map(record => <tr key={record.record_index}><td>#{record.record_index + 1}</td><td className={`prediction-${record.label?.toLowerCase()}`}>{record.prediction_status === 'Rejected' ? 'Rejected' : record.label}</td><td>{record.prediction_status === 'Rejected' ? 'Not available' : probability(record.predicted_class_probability)}</td><td className={`reliability-${record.reliability?.toLowerCase()}`}>{record.reliability}</td><td className="network-evidence">{record.quality_status}<RecordAttention record={record} /></td><td className="network-evidence"><details><summary>Inspect record · {number(record.quality_finding_count)} findings</summary><p>Original row position: {record.record_index + 1} (header excluded)</p><p>Normal probability: {probability(record.probability_normal)}</p><p>Malicious probability: {probability(record.probability_malicious)}</p><p>Predicted-class probability: {probability(record.predicted_class_probability)}</p><p>Reliability: {record.reliability} · {record.reliability_reason}</p><ul>{record.quality_findings.slice(0, 10).map((finding, index) => <li key={index}>{finding.column || 'Dataset'} · {finding.category} · {finding.reason || finding.check}</li>)}</ul>{record.quality_findings_truncated && <p>Finding evidence truncated by backend.</p>}</details></td><td className="network-evidence">{record.rejection_reason || (record.prediction_status === 'Rejected' ? record.reliability_reason : '—')}</td></tr>)}</tbody></table></div>
    {!records.length && <p>No returned records match these filters.</p>}<p className="panel-note">Filters apply only to this returned page. Probability and reliability are separate.</p>{result.pagination.has_more && <p className="panel-note">More records exist (next offset {number(result.pagination.next_offset)}). Another window currently requires reupload/reanalysis. No additional pages are fetched automatically.</p>}
  </section>
}

export default function NetworkDetailPages({ page, result }) {
  const [exportError, setExportError] = useState('')
  if (page === 'data-quality') return <div className="network-details"><QualityDetails result={result} /></div>
  if (page === 'intrusion-detection') return <div className="network-details"><IntrusionDetails result={result} /></div>
  if (page === 'results') return <RecordDetails result={result} />
  return <div className="network-details"><section className="panel middle-panel"><h2>Combined analysis report</h2><p className="filename mono">{result.filename}</p><p className="panel-note">Decision-support PDF with full-file summaries, official evaluation, reliability, backend recommendations and up to 20 important records selected from the returned page.</p><button className="button primary" onClick={() => { try { downloadNetworkPdf(result); setExportError('') } catch { setExportError('The report could not be exported. Please try again.') } }}>Export report PDF</button>{exportError && <p className="error-message" role="alert">{exportError}</p>}</section><NetworkDashboard result={result} /><QualityDetails result={result} /></div>
}
