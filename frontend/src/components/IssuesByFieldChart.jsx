const COLORS = ['#5AA8FF', '#FF8B4E', '#FFCA45', '#7BD7B0', '#9AAFBF']

export default function IssuesByFieldChart({ fieldCounts }) {
  const total = fieldCounts.reduce((sum, f) => sum + f.count, 0) || 1
  const radius = 55
  const circumference = 2 * Math.PI * radius

  const segments = fieldCounts.reduce((accumulator, field, i) => {
    const fraction = field.count / total
    const previousOffset = accumulator.offset
    accumulator.segments.push({
      ...field,
      color: COLORS[i % COLORS.length],
      dasharray: `${fraction * circumference} ${circumference}`,
      dashoffset: -previousOffset,
    })
    accumulator.offset = previousOffset + fraction * circumference
    return accumulator
  }, { segments: [], offset: 0 }).segments

  return (
    <div className="rounded-xl p-3" style={{ background: 'var(--surface-deep)' }}>
      <p className="text-sm font-medium mb-2">
        Issues by field
      </p>
      <div className="relative flex items-center justify-center" style={{ minHeight: 130 }}>
        <svg role="img" aria-label="Affected occurrences by field" className="w-full max-w-[180px] h-auto" viewBox="0 0 130 130">
          <circle cx="65" cy="65" r={radius} fill="none" stroke="var(--border)" strokeWidth="14" />
          {segments.map((seg, i) => (
            <circle
              key={i}
              cx="65" cy="65" r={radius}
              fill="none" stroke={seg.color} strokeWidth="14"
              strokeDasharray={seg.dasharray}
              strokeDashoffset={seg.dashoffset}
              transform="rotate(-90 65 65)"
            />
          ))}
          <text x="65" y="61" textAnchor="middle" fontSize="16" fontWeight="500" fill="#e4edf5">
            {fieldCounts.reduce((sum, field) => sum + field.count, 0)}
          </text>
          <text x="65" y="76" textAnchor="middle" fontSize="10" fill="#9aafbf">
            occurrences
          </text>
        </svg>
      </div>
      <div className="flex flex-wrap gap-2 mt-2">
        {fieldCounts.map((field, i) => (
          <span key={field.name} className="min-w-0 max-w-full flex items-center gap-2 text-sm muted">
            <span
              className="w-2 h-2 shrink-0 rounded-sm"
              style={{ background: COLORS[i % COLORS.length] }}
            />
            <span className="min-w-0">{field.name}</span>
          </span>
        ))}
      </div>
    </div>
  )
}
