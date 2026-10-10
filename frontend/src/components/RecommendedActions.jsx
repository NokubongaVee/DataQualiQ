import { useState } from 'react'
import { Download } from 'lucide-react'
import { rankReviews } from '../utils/reviewOrder'
import { normaliseStatus } from '../utils/intrusionResults'

export default function RecommendedActions({ issues = [], intrusion, onDownload, hasResult }) {
  const [completed, setCompleted] = useState([])
  const ranked = rankReviews(issues)
  const securityActions = []
  if (intrusion.malicious > 0 || intrusion.records.some(record => normaliseStatus(record.prediction) === 'malicious')) securityActions.push('Review the supplied malicious predictions against the original traffic records before taking action.')
  if (intrusion.flaggedAttacks.length) securityActions.push('Manually verify malicious predictions linked to missing, inconsistent or invalid fields. Confirm source values before rerunning analysis.')
  return <aside className="panel recommendations-panel" id="reports">
    <h2>Security recommendations</h2>
    {securityActions.length ? <ul className="security-actions">{securityActions.map(action => <li key={action}>{action}</li>)}</ul> : <p className="panel-note">Security recommendations will appear when intrusion-detection results are available. No blocking or isolation decision has been made.</p>}
    {ranked.length > 0 && <details className="action-details"><summary>Data quality actions <span className="muted">{completed.length}/{ranked.length}</span></summary><progress max={ranked.length} value={completed.length} aria-label="Data quality action progress" /><p className="panel-note">{completed.length} of {ranked.length} actions completed · {Math.round(100 * completed.length / ranked.length)}%. Checklist progress lasts while this dashboard is open.</p><div className="action-list">{ranked.map((issue, index) => <label className={completed.includes(index) ? 'action-item completed' : 'action-item'} key={index}><input type="checkbox" checked={completed.includes(index)} onChange={() => setCompleted(current => current.includes(index) ? current.filter(value => value !== index) : [...current, index])} /><span>{issue.recommendation?.action || issue.suggestion || issue.legacy?.suggestion || 'Review the source records.'}<small>{issue.recommendation?.reason}</small></span></label>)}</div></details>}
    {hasResult && !ranked.length && <p className="panel-note">No data quality actions were reported by the checks performed.</p>}
    <button className="button outline export-button" disabled={!hasResult} onClick={onDownload}><Download size={16} aria-hidden="true" />Export report</button>
    <small className="panel-note">{intrusion.data ? 'Exports available quality and model results.' : 'Exports the current data quality assessment. ML results are pending.'}</small>
  </aside>
}
