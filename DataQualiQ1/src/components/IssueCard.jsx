const SEVERITY_STYLES = {
  High: { border: '#E24B4A', badgeBg: '#FCEBEB', badgeText: '#A32D2D' },
  Medium: { border: '#EA580C', badgeBg: '#FFF7ED', badgeText: '#9A3412' },
  Low: { border: '#1D9E75', badgeBg: '#E1F5EE', badgeText: '#085041' },
}

export default function IssueCard({ title, description, severity, suggestion }) {
  const severityText = String(severity || 'Low').toLowerCase()
  const severityLabel = severityText.charAt(0).toUpperCase() + severityText.slice(1)
  const style = SEVERITY_STYLES[severityLabel] || SEVERITY_STYLES.Low
  return (
    <div
      className="min-w-0 rounded-lg p-3 sm:p-4"
      style={{ background: '#F5F6F8', borderLeft: `3px solid ${style.border}` }}
    >
      <div className="flex flex-wrap items-center gap-2 mb-1">
        <span
          className="text-xs shrink-0 font-medium px-2 py-0.5 rounded-full"
          style={{ background: style.badgeBg, color: style.badgeText }}
        >
          {severityLabel}
        </span>
        <span className="text-sm font-medium" style={{ color: '#0B1E33' }}>{title}</span>
      </div>
      <p className="text-sm mb-1 leading-relaxed" style={{ color: '#64748B' }}>
        {description}
      </p>
      {suggestion && <p className="text-sm mt-2 leading-relaxed" style={{ color: '#0B1E33' }}>{suggestion}</p>}

    </div>
  )
}
