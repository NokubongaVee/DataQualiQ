import { percentage } from '../utils/intrusionResults'

export default function TrafficClassification({ intrusion }) {
  const distribution = intrusion.distribution
  const circumference = 2 * Math.PI * 45
  return <section className="panel middle-panel" id="intrusion-detection">
    <h2>Traffic classification</h2>
    {distribution ? <div className="classification-content">
      <svg viewBox="0 0 120 120" role="img" aria-label={`Normal ${percentage(distribution.normal)}, malicious ${percentage(distribution.malicious)}`}>
        <circle cx="60" cy="60" r="45" fill="none" stroke="var(--blue)" strokeWidth="15" />
        <circle cx="60" cy="60" r="45" fill="none" stroke="var(--orange)" strokeWidth="15" strokeDasharray={`${distribution.malicious * circumference} ${circumference}`} transform="rotate(-90 60 60)" />
        <text x="60" y="58" textAnchor="middle">{percentage(distribution.malicious)}</text><text className="chart-label" x="60" y="74" textAnchor="middle">malicious</text>
      </svg>
      <div className="chart-legend"><p><i className="legend-dot normal" />Normal <strong>{percentage(distribution.normal)}</strong></p><p><i className="legend-dot malicious" />Malicious <strong>{percentage(distribution.malicious)}</strong></p></div>
    </div> : <div className="empty-state"><span className="empty-symbol" aria-hidden="true">◎</span><strong>{intrusion.data?.status === 'processing' ? 'Classification in progress' : 'Awaiting model classification'}</strong><p>{intrusion.normal === 0 && intrusion.malicious === 0 ? 'No classified records were returned.' : 'Normal and malicious traffic percentages will appear when complete classification counts are available.'}</p></div>}
  </section>
}
