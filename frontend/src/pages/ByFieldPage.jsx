import { useState } from 'react'
import Header from '../components/Header'
import DashboardNav from '../components/DashboardNav'
import IssuesByFieldChart from '../components/IssuesByFieldChart'
import { countAffectedValues } from '../utils/affectedValues'

const TYPE_LABELS = {
  missing: 'Missing values',
  duplicate: 'Duplicate rows',
  format: 'Inconsistent formatting',
  invalid_email: 'Invalid email',
  invalid_phone: 'Invalid phone',
  invalid_date: 'Invalid date',
  invalid_currency: 'Invalid currency',
  invalid_numeric: 'Invalid numeric value',
  invalid_text: 'Text quality issue',
  invalid_categorical: 'Category consistency',
  outlier: 'Statistical outlier',
  repeated_identifier: 'Repeated candidate identifier',
  header_conflict: 'Header/value conflict',
  relationship_deviation: 'Relationship exception',
  pattern_deviation: 'Pattern exception',
  ambiguous_date: 'Ambiguous date convention',
  invalid_percentage: 'Percentage syntax',
}

function getFieldCounts(issues) {
  const counts = Object.create(null)
  for (const issue of issues || []) {
    const col = issue.column || 'Other'
    counts[col] = (counts[col] || 0) + issue.count
  }
  return Object.entries(counts)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
}

export default function ByFieldPage({ onNavigate }) {
  const [result] = useState(() => {
    const stored = sessionStorage.getItem('assessmentResult')
    if (!stored) return null
    try {
      return JSON.parse(stored)
    } catch {
      return null
    }
  })

  if (!result) {
    return (
      <div className="min-h-screen w-full flex flex-col" style={{ background: '#F5F6F8' }}>
        <Header activePage="by-field" onNavigate={onNavigate} />
        <div className="dashboard-layout flex flex-col md:flex-row flex-1 min-h-0">
          <DashboardNav activePage="by-field" onNavigate={onNavigate} />
          <main className="min-w-0 flex-1 flex flex-col items-center justify-center px-4 text-center">
          <p className="text-lg font-medium mb-2" style={{ color: '#0B1E33' }}>
            No results yet
          </p>
          <p className="text-sm mb-6" style={{ color: '#64748B' }}>
            Upload a CSV file to see your data quality assessment.
          </p>
          <button
            type="button"
            onClick={() => onNavigate && onNavigate('upload')}
            className="px-6 py-2.5 rounded-xl text-white text-sm font-semibold"
            style={{ background: '#0F8C86' }}
          >
            Go to upload
          </button>
          </main>
        </div>
      </div>
    )
  }

  const fieldCounts = getFieldCounts(result.issues)
  const fieldDetails = fieldCounts.map((field) => {
    const fieldIssues = (result.issues || []).filter((issue) => (issue.column || 'Other') === field.name)
    const issueTypes = [...new Set(fieldIssues.map((issue) => TYPE_LABELS[issue.check] || issue.check))]
    const affectedRows = countAffectedValues(fieldIssues)
    const highestPercentage = Math.max(...fieldIssues.map((issue) => issue.pct || 0), 0)
    return { ...field, issueTypes, affectedRows, highestPercentage }
  })

  return (
    <div className="min-h-screen w-full flex flex-col" style={{ background: '#F5F6F8' }}>
      <Header activePage="by-field" onNavigate={onNavigate} />
      <div className="dashboard-layout flex flex-col md:flex-row flex-1 min-h-0">
        <DashboardNav activePage="by-field" onNavigate={onNavigate} />
        <main className="min-w-0 flex-1 max-w-[1600px] mx-auto px-4 sm:px-8 py-6 w-full">
          <p className="text-sm mb-1" style={{ color: '#64748B' }}>{result.filename}</p>
          <h1 className="text-2xl font-bold" style={{ color: '#0B1E33' }}>Issues by field</h1>
          <p className="text-sm mt-1 mb-6" style={{ color: '#64748B' }}>
            See which columns need attention and what kind of problems they contain.
          </p>
          <details className="mb-5 rounded-xl bg-white border border-slate-200 p-4 text-sm">
            <summary className="cursor-pointer font-semibold">Dataset understanding and check coverage</summary>
            <p className="mt-2 text-slate-600">Possible dataset purpose: {(result.dataset_context?.name || 'unknown').replaceAll('_', ' ')}. Recommendations use observed issues and available field context; confirm that this matches your intended use.</p>
            {Object.entries(result.column_profiles || {}).map(([name, profile]) => (
              <details key={name} className="mt-3 border-t pt-2">
                <summary className="cursor-pointer">{name}: {profile.type}; possible {profile.role.replaceAll('_', ' ')} ({Math.round(profile.confidence * 100)}% support)</summary>
                <p className="mt-2">{profile.measurements?.full?.present_count} present, {profile.measurements?.full?.missing_count} missing, {profile.measurements?.full?.unique_count} distinct values.</p>
                <p>Pattern sample: {profile.measurements?.sample?.size} of {profile.measurements?.sample?.population} present values.</p>
                {(profile.contradictions || []).map((text, i) => <p key={i}>{text}</p>)}
                {Object.entries(profile.checks || {}).map(([check, entry]) => <p key={check} className="mt-1 text-xs text-slate-600">{check.replaceAll('_', ' ')}: {entry.selected ? 'Selected' : 'Skipped'}. {entry.reason}</p>)}
              </details>
            ))}
          </details>

          {fieldDetails.length === 0 ? (
            <div className="rounded-2xl bg-white border border-slate-200 p-8 text-center">
              <p className="text-base font-semibold" style={{ color: '#0B1E33' }}>No field issues found</p>
              <p className="text-sm mt-2" style={{ color: '#64748B' }}>Every checked field passed the current quality checks.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 xl:grid-cols-[minmax(220px,0.6fr)_minmax(0,1.4fr)] gap-5 items-start">
              <IssuesByFieldChart fieldCounts={fieldCounts} />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {fieldDetails.map((field) => (
                  <article key={field.name} className="rounded-2xl bg-white border border-slate-200 p-5 shadow-sm">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h2 className="font-bold" style={{ color: '#0B1E33' }}>{field.name}</h2>
                        <p className="text-xs mt-1" style={{ color: '#64748B' }}>{field.issueTypes.join(' • ')}</p>
                      </div>
                      <span className="text-2xl font-bold" style={{ color: '#D85A30' }}>{field.count}</span>
                    </div>
                    <div className="mt-5 flex items-end justify-between text-sm">
                      <span style={{ color: '#64748B' }}>Affected values</span>
                      <strong style={{ color: '#0B1E33' }}>{field.affectedRows}</strong>
                    </div>
                    <div className="mt-3 h-2 rounded-full bg-slate-100 overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${Math.min(field.highestPercentage, 100)}%`, background: '#00BAB1' }} />
                    </div>
                    <p className="text-xs mt-2" style={{ color: '#64748B' }}>Highest affected rate: {field.highestPercentage}%</p>
                  </article>
                ))}
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
