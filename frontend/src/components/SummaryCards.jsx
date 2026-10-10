import { nonnegativeNumber, percentage } from '../utils/intrusionResults'

export default function SummaryCards({ result, intrusion }) {
  const rows = nonnegativeNumber(result?.total_rows) ?? intrusion.total
  const cards = [
    ['Records analysed', rows === null ? 'Pending' : rows.toLocaleString(), result?.total_columns != null ? `${result.total_columns} fields assessed` : 'Upload a traffic CSV', ''],
    ['Normal traffic', intrusion.normal === null ? 'Pending' : intrusion.normal.toLocaleString(), 'Model classification', 'text-accent'],
    ['Attacks detected', intrusion.malicious === null ? 'Pending' : intrusion.malicious.toLocaleString(), 'Model classification', intrusion.malicious > 0 ? 'text-attack' : ''],
    ['Data quality score', result ? `${result.score}/100` : 'Pending', result ? `Grade ${result.grade || '—'} · ${result.label || 'Heuristic score'}` : 'Run the quality assessment', 'text-warning'],
    ['Average model confidence', percentage(intrusion.data?.average_confidence), 'Supplied by the model', ''],
  ]
  return <section className="summary-grid" aria-label="Analysis summary">
    {cards.map(([label, value, note, color]) => <article className="panel summary-card" key={label}>
      <span className="muted">{label}</span><strong className={color}>{value}</strong><small>{note}</small>
    </article>)}
  </section>
}
