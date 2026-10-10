const SEVERITY_STYLES = {
  High: { border: '#E24B4A', badgeBg: '#352023', badgeText: '#ffaba5' },
  Medium: { border: '#EA580C', badgeBg: '#34291a', badgeText: '#ffc66d' },
  Low: { border: '#1D9E75', badgeBg: '#15322d', badgeText: '#79d9b2' },
}

export default function IssueCard({ title, description, severity, suggestion }) {
  const severityText = String(severity || 'Low').toLowerCase()
  const severityLabel = severityText.charAt(0).toUpperCase() + severityText.slice(1)
  const style = SEVERITY_STYLES[severityLabel] || SEVERITY_STYLES.Low
  return (
    <div
      className="issue-card min-w-0 rounded-lg p-3 sm:p-4"
      style={{ background: 'var(--surface-deep)', borderLeft: `3px solid ${style.border}` }}
    >
      <div className="flex flex-wrap items-center gap-2 mb-1">
        <span
          className="text-xs shrink-0 font-medium px-2 py-0.5 rounded-full"
          style={{ background: style.badgeBg, color: style.badgeText }}
        >
          {severityLabel}
        </span>
        <span className="text-sm font-medium">{title}</span>
      </div>
      <p className="text-sm mb-1 leading-relaxed muted">
        {description}
      </p>
      {suggestion && <p className="text-sm mt-2 leading-relaxed">{suggestion}</p>}

    </div>
  )
}
