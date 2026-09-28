import { countInvalidFormatValues } from '../utils/affectedValues'

const RANK_COLORS = [
  { color: '#1D9E75', text: '#085041' }, // smallest: green
  { color: '#7F77DD', text: '#3C3489' }, // 2nd smallest: purple
  { color: '#EF9F27', text: '#854F0B' }, // 3rd smallest: orange
  { color: '#E24B4A', text: '#A32D2D' }, // largest: red
]

function groupIssuesByCategory(issues) {
  const counts = { missing: 0, duplicate: 0, outlier: 0 }

  for (const issue of issues || []) {
    const type = issue.check
    const rowCount = issue.count || 0
    if (type === 'missing') counts.missing += rowCount
    else if (type === 'duplicate') counts.duplicate += rowCount
    else if (type === 'outlier') counts.outlier += rowCount
  }

  const categories = [
    { label: 'Missing values', count: counts.missing },
    { label: 'Duplicate rows', count: counts.duplicate },
    { label: 'Invalid / inconsistent values', count: countInvalidFormatValues(issues) },
    { label: 'Statistical outliers', count: counts.outlier },
  ]

  // Rank by count ascending, then assign colors by rank position
  const rankOrder = [...categories]
    .map((cat, i) => ({ ...cat, originalIndex: i }))
    .sort((a, b) => a.count - b.count)

  const withColors = new Array(categories.length)
  rankOrder.forEach((cat, rank) => {
    withColors[cat.originalIndex] = {
      ...categories[cat.originalIndex],
      color: RANK_COLORS[rank].color,
      text: RANK_COLORS[rank].text,
    }
  })

  return withColors
}

export default function StatCards({ totalRows, totalColumns, timeTaken, issues }) {
  const categories = groupIssuesByCategory(issues)

  return (
    <div className="flex flex-col gap-2.5">
      <div className="grid grid-cols-1 min-[375px]:grid-cols-3 gap-2.5">
        <div className="min-w-0 rounded-xl p-3 sm:p-4 flex flex-col justify-center" style={{ background: '#EEF0F3', minHeight: '92px' }}>
          <p className="text-2xl font-medium" style={{ color: '#0B1E33' }}>{totalRows}</p>
          <p className="text-sm mt-1" style={{ color: '#64748B' }}>Rows scanned</p>
        </div>
        <div className="min-w-0 rounded-xl p-3 sm:p-4 flex flex-col justify-center" style={{ background: '#EEF0F3', minHeight: '92px' }}>
          <p className="text-2xl font-medium" style={{ color: '#0B1E33' }}>{totalColumns}</p>
          <p className="text-sm mt-1" style={{ color: '#64748B' }}>Columns checked</p>
        </div>
        <div className="min-w-0 rounded-xl p-3 sm:p-4 flex flex-col justify-center" style={{ background: '#EEF0F3', minHeight: '92px' }}>
          <p className="text-2xl font-medium" style={{ color: '#0B1E33' }}>
            {timeTaken != null ? `${timeTaken}s` : '—'}
          </p>
          <p className="text-sm mt-1" style={{ color: '#64748B' }}>Time to scan</p>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5">
        {categories.map((cat) => (
          <div key={cat.label} className="min-w-0 rounded-xl p-3 sm:p-4 flex items-center gap-2.5" style={{ background: '#EEF0F3', minHeight: '92px' }}>
            <span className="w-4 h-4 rounded-full flex-shrink-0" style={{ background: cat.color }} />
            <div className="min-w-0">
              <p className="text-xl font-medium" style={{ color: cat.text }}>{cat.count}</p>
              <p className="text-sm" style={{ color: '#64748B' }}>{cat.label}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
