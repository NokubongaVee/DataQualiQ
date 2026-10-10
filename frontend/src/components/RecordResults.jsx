import { useState } from 'react'
import { normaliseStatus, percentage, QUALITY_LABELS, RELIABILITY_LABELS } from '../utils/intrusionResults'

function statusBadge(value, labels, kind) {
  const status = normaliseStatus(value)
  const label = labels[status] || 'Pending'
  return <span className={`badge ${kind}-${labels[status] ? status : 'pending'}`}>{label}</span>
}

export default function RecordResults({ intrusion }) {
  const [filter, setFilter] = useState('all')
  const [page, setPage] = useState(0)
  const filtered = intrusion.records.filter(record => filter === 'all'
    || (filter === 'normal' && normaliseStatus(record.prediction) === 'normal')
    || (filter === 'malicious' && normaliseStatus(record.prediction) === 'malicious')
    || (filter === 'review' && (['review', 'low'].includes(normaliseStatus(record.reliability)) || intrusion.flaggedAttacks.includes(record))))
  const pageSize = 25
  const maxPage = Math.max(0, Math.ceil(filtered.length / pageSize) - 1)
  const currentPage = Math.min(page, maxPage)
  const visible = filtered.slice(currentPage * pageSize, (currentPage + 1) * pageSize)
  return <section className="panel records-panel" id="results">
    <div className="panel-heading"><h2>Record-level results</h2><label className="table-filter">Show <select value={filter} onChange={event => { setFilter(event.target.value); setPage(0) }}><option value="all">All</option><option value="normal">Normal</option><option value="malicious">Malicious</option><option value="review">Needs verification</option></select></label></div>
    <div className="table-scroll" tabIndex={0} role="region" aria-label="Record-level results table">
      <table><thead><tr>{['Record', 'Source → Destination', 'Protocol', 'Prediction', 'Confidence', 'Data Quality', 'Reliability'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead>
        <tbody>{visible.map((record, index) => <tr key={`${record.record_id ?? 'record'}-${currentPage}-${index}`}>
          <td className="mono">{record.record_id != null ? `#${String(record.record_id).padStart(5, '0')}` : 'Pending'}</td>
          <td className="mono">{record.source_ip || 'Pending'} <span className="muted">→</span> {record.destination_ip || 'Pending'}</td>
          <td>{record.protocol || 'Pending'}</td>
          <td>{statusBadge(record.prediction, { normal: 'Normal', malicious: 'Malicious' }, 'prediction')}</td>
          <td>{percentage(record.confidence)}</td>
          <td>{statusBadge(record.data_quality_status, QUALITY_LABELS, 'quality')}</td>
          <td>{statusBadge(record.reliability, RELIABILITY_LABELS, 'reliability')}</td>
        </tr>)}</tbody>
      </table>
    </div>
    {!visible.length && <div className="empty-state table-empty"><strong>{intrusion.records.length ? 'No records match this filter' : intrusion.data?.status === 'processing' ? 'Record predictions are being processed' : 'Record predictions are pending'}</strong><p>{intrusion.records.length ? 'Choose another filter to review the supplied records.' : 'The current assessment contains data-quality findings. Source, destination, predictions, confidence and reliability will appear when supplied by the intrusion-detection service.'}</p></div>}
    {filtered.length > 0 && <div className="pagination"><small>{currentPage * pageSize + 1}–{Math.min((currentPage + 1) * pageSize, filtered.length)} of {filtered.length.toLocaleString()} supplied records</small><div><button className="button subtle" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}>Previous</button><button className="button subtle" disabled={currentPage === maxPage} onClick={() => setPage(currentPage + 1)}>Next</button></div></div>}
    <p className="panel-note">Reliability is supplied by the backend; it is never inferred from confidence here.</p>
  </section>
}
