import { normaliseStatus } from '../utils/intrusionResults'

export default function WorkflowSteps({ uploaded = false, selected = false, assessed = false, loading = false, intrusion, networkAnalysis = false }) {
  const ready = intrusion?.records?.some(record => ['normal', 'malicious'].includes(normaliseStatus(record.prediction)))
    || (intrusion?.normal !== null && intrusion?.malicious !== null && !!intrusion?.data)
  const steps = [
    ['Upload data', 'Network traffic CSV', uploaded ? 'Done' : loading ? 'In progress' : selected ? 'Ready to upload' : 'Not started'],
    ['Data quality check', 'Missing, duplicate and invalid values', loading ? 'In progress' : assessed ? 'Done' : 'Not started'],
    ['ML classification', 'Normal or malicious', intrusion?.data?.status === 'processing' ? 'In progress' : ready ? 'Done' : 'Pending model results'],
    ['Combined report', 'Quality + cybersecurity results', assessed ? ready ? 'Ready to review' : 'Quality ready · ML pending' : 'Not started'],
  ]
  if (networkAnalysis) {
    if (loading) steps.forEach(step => { step[2] = 'Awaiting combined response' })
    else if (!assessed) steps[2][2] = 'Not started'
  }
  return <ol className="workflow" aria-label="Analysis workflow">
    {steps.map(([title, subtitle, status], index) => <li key={title} className={`workflow-step ${status === 'Done' ? 'is-done' : ''} ${index === 3 && assessed ? 'is-current' : ''}`}>
      <span className="eyebrow">Step {index + 1}</span><strong>{title}</strong>
      <span className="step-subtitle">{subtitle}</span>
      <span className={`step-status ${status === 'Done' ? 'text-good' : ''}`} role="status">{status}</span>
    </li>)}
  </ol>
}
