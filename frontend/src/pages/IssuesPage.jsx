import { rankReviews } from '../utils/reviewOrder'
import { useState } from 'react'
import Header from '../components/Header'
import DashboardNav from '../components/DashboardNav'
import IssueCard from '../components/IssueCard'

function getDisplayIssue(issue) {
  const review = issue.issue_to_review || issue
  const recommendation = issue.recommendation || {}
  const legacy = issue.legacy || {}

  return {
    title: review.title || issue.title || legacy.title || 'Data issue detected',
    description: review.description || issue.description || legacy.description || '',
    suggestion: recommendation.action || issue.suggestion || legacy.suggestion || 'Review the affected records.',
    severity: review.severity || issue.severity || legacy.severity || 'Medium',
    evidence: review.evidence,
  }
}

export default function IssuesPage({ onNavigate }) {
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
        <Header activePage="issues" onNavigate={onNavigate} />
        <div className="dashboard-layout flex flex-col md:flex-row flex-1 min-h-0">
          <DashboardNav activePage="issues" onNavigate={onNavigate} />
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

  return (
    <div className="min-h-screen w-full flex flex-col" style={{ background: '#F5F6F8' }}>
      <Header activePage="issues" onNavigate={onNavigate} />
      <div className="dashboard-layout flex flex-col md:flex-row flex-1 min-h-0">
        <DashboardNav activePage="issues" onNavigate={onNavigate} />
        <main className="min-w-0 flex-1 max-w-6xl mx-auto px-4 sm:px-8 py-6 w-full">
          <p className="text-sm mb-1" style={{ color: '#64748B' }}>{result.filename}</p>
          <h1 className="text-2xl font-bold" style={{ color: '#0B1E33' }}>Issues to review</h1>
          <p className="text-sm mt-1 mb-6" style={{ color: '#64748B' }}>
            Review each finding and follow the suggested fix when appropriate.
          </p>
          <div className="flex flex-col gap-3">
            {(result.translated_issues || []).length === 0 ? (
              <div className="rounded-2xl bg-white border border-slate-200 p-8 text-center">
                <p className="font-semibold" style={{ color: '#0B1E33' }}>No issues found in this dataset.</p>
                <p className="text-sm mt-2" style={{ color: '#64748B' }}>All current checks passed without findings.</p>
              </div>
            ) : (
              rankReviews(result.translated_issues).map((issue, index) => {
                const displayIssue = getDisplayIssue(issue)
                return (
                  <IssueCard
                    key={`${displayIssue.title}-${index}`}
                    title={displayIssue.title}
                    description={displayIssue.description}
                    suggestion={displayIssue.suggestion}
                    severity={displayIssue.severity}
                    evidence={displayIssue.evidence}
                  />
                )
              })
            )}
          </div>
        </main>
      </div>
    </div>
  )
}