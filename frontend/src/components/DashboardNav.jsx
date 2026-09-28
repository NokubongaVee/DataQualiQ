const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'by-field', label: 'By field' },
  { id: 'issues', label: 'Issues' },
  { id: 'actions', label: 'Actions' },
]

export default function DashboardNav({ activePage, onNavigate }) {
  const tabStyle = (isActive) => ({
    color: isActive ? '#08756F' : '#64748B',
    background: isActive ? '#E6FBFA' : 'transparent',
  })

  return (
    <nav aria-label="Dashboard navigation" className="hidden md:flex w-[160px] lg:w-[180px] shrink-0 flex-col gap-1 p-3 lg:p-4">
      {TABS.map((tab) => (
        <button
          type="button"
          aria-current={activePage === tab.id ? 'page' : undefined}
          key={tab.id}
          className="text-left px-3 py-2 rounded-lg text-sm font-semibold cursor-pointer transition-colors"
          onClick={() => onNavigate && onNavigate(tab.id)}
          style={tabStyle(activePage === tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  )
}