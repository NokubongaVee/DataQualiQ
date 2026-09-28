import { rankReviews } from '../utils/reviewOrder'
import { useState } from 'react'
import Header from '../components/Header'
import DashboardNav from '../components/DashboardNav'
import ScoreCard from '../components/ScoreCard'
import StatCards from '../components/StatCards'
import IssueCard from '../components/IssueCard'
import IssuesByFieldChart from '../components/IssuesByFieldChart'
import RecommendedActions from '../components/RecommendedActions'
import { downloadAssessmentPdf } from '../utils/downloadAssessmentPdf'

function getFieldCounts(issues) {
  const counts = Object.create(null)
  for (const issue of issues || []) {
    const column = issue.column || 'Other'
    counts[column] = (counts[column] || 0) + (issue.count || 0)
  }

  return Object.entries(counts)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 5)
}

function getDisplayIssue(issue) {
  const review = issue.issue_to_review || issue
  const recommendation = issue.recommendation || {}
  const legacy = issue.legacy || {}

  return {
    title: review.title || issue.title || 'Data issue detected',
    description: review.description || issue.description || legacy.description || '',
    suggestion: recommendation.action || issue.suggestion || legacy.suggestion || 'Review the affected records.',
    severity: review.severity || issue.severity || legacy.severity || 'Medium',
    evidence: review.evidence,
  }
}

export default function OverviewPage({ onNavigate }) {
  const [result] = useState(() => {
    const stored = sessionStorage.getItem('assessmentResult')
    if (!stored) return null

    try {
      const parsed = JSON.parse(stored)
      return parsed && typeof parsed.score === 'number' && parsed.filename
        ? parsed
        : null
    } catch {
      return null
    }
  })

  const handleDownload = () => {
    if (!result) return
    downloadAssessmentPdf(result)
  }

  if (!result) {
    return (
      <div className="min-h-screen w-full flex flex-col" style={{ background: '#F5F6F8' }}>
        <Header activePage="overview" onNavigate={onNavigate} />
        <div className="dashboard-layout flex flex-col md:flex-row flex-1 min-h-0">
          <DashboardNav activePage="overview" onNavigate={onNavigate} />
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
      <Header activePage="overview" onNavigate={onNavigate} />
      <div className="dashboard-layout flex flex-col md:flex-row flex-1 min-h-0">
        <DashboardNav activePage="overview" onNavigate={onNavigate} />
        <main className="min-w-0 flex-1 max-w-[1600px] mx-auto px-4 sm:px-8 py-6 w-full">
          <p className="text-sm mb-4" style={{ color: '#64748B' }}>
            {result.filename}
          </p>

          <div className="flex flex-col xl:flex-row gap-3 items-stretch mb-6">
            <div className="xl:w-[288px] flex-shrink-0">
              <ScoreCard
                score={result.score}
                grade={result.grade}
                label={result.label}
                issueCount={result.translated_issues?.length || 0}
              />
            </div>
            <div className="min-w-0 flex-1">
              <StatCards
                totalRows={result.total_rows}
                totalColumns={result.total_columns}
                timeTaken={result.time_taken}
                issues={result.issues}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)] gap-5 items-start">
            <section>
              <div className="mb-3">
                <h1 className="text-xl font-bold" style={{ color: '#0B1E33' }}>Issues to review</h1>
                <p className="text-sm mt-1" style={{ color: '#64748B' }}>
                  Ranked by potential impact on decisions made from this data
                </p>
              </div>
              <div className="flex flex-col gap-2.5">
                {(result.translated_issues || []).length === 0 ? (
                  <div className="rounded-xl p-6" style={{ background: '#FFFFFF', border: '1px solid #E2E8F0' }}>
                    <p className="text-sm" style={{ color: '#64748B' }}>No issues found in this dataset.</p>
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
            </section>

            <aside className="flex flex-col gap-4">
              <IssuesByFieldChart fieldCounts={getFieldCounts(result.issues)} />
              <RecommendedActions
                issues={result.translated_issues || []}
                onDownload={handleDownload}
              />
            </aside>
          </div>
        </main>
      </div>
    </div>
  )
}
