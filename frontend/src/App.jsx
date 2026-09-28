import { useState } from 'react'
import UploadPage from './pages/UploadPage'
import OverviewPage from './pages/OverviewPage'
import IssuesPage from './pages/IssuesPage'
import ByFieldPage from './pages/ByFieldPage'
import ActionsPage from './pages/ActionsPage'
import { restorePage, rememberPage } from './utils/navigation'

const DASHBOARD_PAGES = {
  overview: OverviewPage,
  issues: IssuesPage,
  'by-field': ByFieldPage,
  actions: ActionsPage,
}

function App() {
  const [page, setPage] = useState(() => restorePage(sessionStorage))
  const navigate = (nextPage) => {
    setPage(rememberPage(sessionStorage, nextPage))
  }

  if (page === 'upload') {
    return <UploadPage onNavigate={navigate} />
  }

  const DashboardSubPage = DASHBOARD_PAGES[page] || OverviewPage
  return <DashboardSubPage onNavigate={navigate} />
}

export default App
