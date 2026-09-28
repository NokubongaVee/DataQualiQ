import { rankReviews } from '../utils/reviewOrder'

export default function RecommendedActions({ issues, onDownload }) {
  const actions = rankReviews(issues).slice(0, 4).map((issue) => (
    issue.recommendation?.action || issue.suggestion || issue.legacy?.suggestion || 'Review the affected records.'
  ))

  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-xl p-3" style={{ background: '#F5F6F8' }}>
        <p className="text-sm font-medium mb-2" style={{ color: '#0B1E33' }}>
          Recommended actions
        </p>
        <div className="flex flex-col gap-2">
          {actions.length === 0 ? (
            <p className="text-xs" style={{ color: '#64748B' }}>No actions needed.</p>
          ) : (
            actions.map((action, i) => (
              <label key={i} className="min-h-11 flex items-start gap-3 py-2 text-sm" style={{ color: '#0B1E33' }}>
                <input className="mt-1 h-5 w-5 shrink-0" type="checkbox" style={{ accentColor: '#0F8C86' }} />
                <span className="min-w-0">{action}</span>
              </label>
            ))
          )}
        </div>
      </div>

      <button
        type="button"
        onClick={onDownload}
        className="rounded-xl py-2.5 text-sm font-medium text-white"
        style={{ background: '#0B1E33' }}
      >
        Download full report
      </button>
    </div>
  )
}
