function getStatusMessage(issueCount) {
  if (issueCount === 0) return 'No findings from the checks performed'
  return `${issueCount} finding${issueCount === 1 ? '' : 's'} to review`
}

export default function ScoreCard({ score, grade, label, issueCount }) {
  const radius = 32
  const circumference = 2 * Math.PI * radius
  const progress = (score / 100) * circumference

  return (
    <div
      className="rounded-2xl p-4 flex flex-col justify-between h-full"
      style={{ background: '#0B1E33' }}
    >
      <p className="text-xs mb-2.5" style={{ color: '#9FE1CB' }}>
        Overall data quality
      </p>
      <svg width="76" height="76" viewBox="0 0 76 76" className="mx-auto">
        <circle cx="38" cy="38" r={radius} fill="none" stroke="#1C3350" strokeWidth="7" />
        <circle
          cx="38" cy="38" r={radius}
          fill="none" stroke="#1D9E75" strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          transform="rotate(-90 38 38)"
        />
        <text x="38" y="34" textAnchor="middle" fontSize="20" fontWeight="500" fill="#FFFFFF">
          {score}
        </text>
        <text x="38" y="48" textAnchor="middle" fontSize="9" fill="#9FE1CB">
          /100
        </text>
      </svg>
      <div>
        <p className="text-xs font-medium mb-0.5" style={{ color: '#FFFFFF' }}>
          {getStatusMessage(issueCount)}
        </p>
        <p className="text-xs" style={{ color: '#9FE1CB' }}>
          Grade {grade} &middot; {label}
        </p>
        <p className="text-xs mt-2" style={{ color: '#9FE1CB' }}>Heuristic score; not a percentage of correct data.</p>
      </div>
    </div>
  )
}
