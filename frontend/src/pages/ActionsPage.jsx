import { rankReviews } from '../utils/reviewOrder'
import { useState } from 'react'
import Header from '../components/Header'
import DashboardNav from '../components/DashboardNav'
import { downloadAssessmentPdf } from '../utils/downloadAssessmentPdf'

function getAction(issue) {
  return issue.recommendation?.action || issue.suggestion || issue.legacy?.suggestion || 'Review the affected records.'
}

function getTitle(issue) {
  return issue.recommendation?.title || issue.title || issue.legacy?.title || 'Review flagged records'
}

function getPriority(issue) {
  return issue.recommendation?.priority || (issue.severity === 'High' ? 'high' : issue.severity === 'Low' ? 'low' : 'medium')
}

export default function ActionsPage({ onNavigate }) {
  const [result] = useState(() => {
    const stored = sessionStorage.getItem('assessmentResult')
    if (!stored) return null
    try {
      return JSON.parse(stored)
    } catch {
      return null
    }
  })
  const [completed, setCompleted] = useState([])

  const handleDownload = () => {
    if (!result) return
    downloadAssessmentPdf(result)
  }

  if (!result) {
    return (
      <div className="min-h-screen w-full flex flex-col" style={{ background: '#F5F6F8' }}>
        <Header activePage="actions" onNavigate={onNavigate} />
        <div className="dashboard-layout flex flex-col md:flex-row flex-1 min-h-0">
          <DashboardNav activePage="actions" onNavigate={onNavigate} />
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
      <Header activePage="actions" onNavigate={onNavigate} />
      <div className="dashboard-layout flex flex-col md:flex-row flex-1 min-h-0">
        <DashboardNav activePage="actions" onNavigate={onNavigate} />
        <main className="min-w-0 flex-1 max-w-5xl mx-auto px-4 sm:px-8 py-6 w-full">
          <p className="text-sm mb-1" style={{ color: '#64748B' }}>{result.filename}</p>
          <h1 className="text-2xl font-bold" style={{ color: '#0B1E33' }}>Recommended actions</h1>
          <p className="text-sm mt-1" style={{ color: '#64748B' }}>Work through the suggested fixes and keep track of what has been reviewed.</p>

          <div className="mt-6 rounded-2xl bg-white border border-slate-200 p-5 shadow-sm">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-semibold" style={{ color: '#0B1E33' }}>Progress</p>
                <p className="text-xs mt-1" style={{ color: '#64748B' }}>{completed.length} of {(result.translated_issues || []).length} actions completed</p>
              </div>
              <span className="text-xl font-bold" style={{ color: '#0F8C86' }}>{(result.translated_issues || []).length ? Math.round((completed.length / result.translated_issues.length) * 100) : 0}%</span>
            </div>
            <div className="mt-3 h-2 rounded-full bg-slate-100 overflow-hidden">
              <div className="h-full rounded-full transition-all" style={{ width: `${(result.translated_issues || []).length ? (completed.length / result.translated_issues.length) * 100 : 0}%`, background: '#00BAB1' }} />
            </div>
          </div>

          <div className="mt-4 flex flex-col gap-3">
            {(result.translated_issues || []).length === 0 ? (
              <div className="rounded-2xl bg-white border border-slate-200 p-8 text-center">
                <p className="font-semibold" style={{ color: '#0B1E33' }}>No actions needed</p>
                <p className="text-sm mt-2" style={{ color: '#64748B' }}>This dataset has no reported issues requiring a recommendation.</p>
              </div>
            ) : (
              rankReviews(result.translated_issues).map((issue, index) => {
                const priority = getPriority(issue)
                const isComplete = completed.includes(index)
                return (
                  <label key={`${getTitle(issue)}-${index}`} className={`flex items-start gap-4 rounded-2xl bg-white border p-5 cursor-pointer transition ${isComplete ? 'border-emerald-200 bg-emerald-50/40' : 'border-slate-200 shadow-sm'}`}>
                    <input
                      type="checkbox"
                      checked={isComplete}
                      onChange={() => setCompleted((current) => isComplete ? current.filter((item) => item !== index) : [...current, index])}
                      className="mt-1 h-4 w-4"
                      style={{ accentColor: '#0F8C86' }}
                    />
                    <span className="flex-1 min-w-0">
                      <span className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold" style={{ color: '#0B1E33' }}>{getTitle(issue)}</span>
                        <span className="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase" style={{ color: priority === 'high' ? '#A32D2D' : priority === 'low' ? '#085041' : '#9A3412', background: priority === 'high' ? '#FCEBEB' : priority === 'low' ? '#E1F5EE' : '#FFF7ED' }}>
                          {priority} priority
                        </span>
                      </span>
                      <span className="block text-sm mt-2 leading-relaxed" style={{ color: '#64748B' }}>{getAction(issue)}</span>
                      <span className="block text-xs mt-2 text-slate-500">{issue.recommendation?.reason}</span>
                    </span>
                  </label>
                )
              })
            )}
          </div>

          <button type="button" onClick={handleDownload} className="mt-5 w-full rounded-xl py-3 text-sm font-semibold text-white" style={{ background: '#0B1E33' }}>Download full report</button>
        </main>
      </div>
    </div>
  )
}
