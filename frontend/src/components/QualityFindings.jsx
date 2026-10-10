import IssueCard from './IssueCard'
import IssuesByFieldChart from './IssuesByFieldChart'
import { getDisplayIssue } from '../utils/issueDisplay'
import { getFieldCounts } from '../utils/fieldCounts'
import { countAffectedValues } from '../utils/affectedValues'
import { rankReviews } from '../utils/reviewOrder'

export default function QualityFindings({ result, expanded = false }) {
  const fields = getFieldCounts(result.issues)
  return <details open={expanded || undefined} className="panel quality-details" id="quality-findings">
    <summary>Data quality findings <span className="muted">· {result.issues.length} findings · {result.total_columns ?? '—'} fields</span></summary>
    <p className="panel-note">Review source records before correcting data. A good score does not establish fitness for an intrusion-detection model.</p>
    <div className="quality-review-layout"><div className="finding-list">{rankReviews(result.translated_issues).map((issue, index) => <IssueCard key={index} {...getDisplayIssue(issue)} />)}{!result.translated_issues.length && <p className="empty-state">No issues found by the checks performed.</p>}</div>
      <details open={expanded || undefined} className="field-details"><summary>Field evidence and check coverage</summary>
        <IssuesByFieldChart fieldCounts={fields} />
        {fields.map(field => {
          const findings = result.issues.filter(issue => (issue.column ?? null) === field.column)
          return <article className="field-evidence" key={field.name}><strong>{field.name}</strong><p>{field.count} finding occurrences · Affected values {countAffectedValues(findings)}</p><p>{[...new Set(findings.map(issue => issue.check.replaceAll('_', ' ')))].join(' · ')}</p></article>
        })}
        <p className="panel-note">Occurrences can overlap. Affected values are deduplicated within each field.</p>
        <p className="panel-note">Possible dataset purpose: {(result.dataset_context?.name || 'unknown').replaceAll('_', ' ')}. Confirm this against the intended use.</p>
        {Object.entries(result.column_profiles || {}).map(([name, profile]) => <details key={name}><summary>{name}: {profile.type || 'unknown'} · possible {(profile.role || 'unknown').replaceAll('_', ' ')}</summary><p>{profile.measurements?.full?.present_count ?? '—'} present, {profile.measurements?.full?.missing_count ?? '—'} missing, {profile.measurements?.full?.unique_count ?? '—'} distinct.</p><p>Pattern sample: {profile.measurements?.sample?.size ?? '—'} of {profile.measurements?.sample?.population ?? '—'} present values.</p>{(profile.contradictions || []).map((text, index) => <p key={index}>{text}</p>)}{Object.entries(profile.checks || {}).map(([check, plan]) => <p key={check}>{check.replaceAll('_', ' ')}: {plan.selected ? 'Selected' : 'Skipped'}. {plan.reason}</p>)}</details>)}
      </details></div>
  </details>
}
