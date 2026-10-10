// Presentation of supplied labels only; never infer reliability from probability.
export default function RecordAttention({ record }) {
  const rejected = record.prediction_status === 'Rejected'
  const malicious = record.label === 'Malicious'
  const review = record.reliability === 'Review' || record.reliability === 'Low'
  const attention = rejected || (malicious && review) ? ['High attention', 'high']
    : malicious && record.reliability === 'High' ? ['Security alert', 'security']
      : record.label === 'Normal' && review ? ['Normal review', 'review'] : null
  if (!attention) return null
  return <div className="record-attention"><span className={`attention-badge attention-${attention[1]}`}>{attention[0]}</span>
    <small>{rejected ? record.rejection_reason || record.reliability_reason : record.reliability_reason}</small>
  </div>
}
