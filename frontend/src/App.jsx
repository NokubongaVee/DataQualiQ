import { useEffect, useState } from 'react'
import UploadPage from './pages/UploadPage'
import OverviewPage from './pages/OverviewPage'
import AnalysisPages from './pages/AnalysisPages'
import { clearStoredAssessment, getSessionStorage, normalizeAssessmentResult, persistAssessmentSummary, readAssessmentSummary } from './utils/assessmentResult'
import { restorePage, rememberPage } from './utils/navigation'
import { clearNetworkSummary, normalizeNetworkAnalysis, persistNetworkSummary, readNetworkSummary } from './utils/networkAnalysis'

function App() {
  // Full responses live only here. Navigation never reads a persisted response.
  const [result, setResult] = useState(null)
  const [summary, setSummary] = useState(() => readNetworkSummary(getSessionStorage()) || readAssessmentSummary(getSessionStorage()))
  const [page, setPage] = useState(() => {
    const refreshing = performance.getEntriesByType('navigation')[0]?.type === 'reload'
    return refreshing ? restorePage(getSessionStorage()) : 'upload'
  })
  useEffect(() => {
    try { getSessionStorage()?.removeItem('assessmentResult') } catch { /* Remove legacy payload when possible. */ }
  }, [])
  const navigate = nextPage => setPage(rememberPage(getSessionStorage(), nextPage))
  const completeAssessment = response => {
    const networkResult = normalizeNetworkAnalysis(response)
    setResult(networkResult || normalizeAssessmentResult(response))
    setSummary(networkResult ? persistNetworkSummary(getSessionStorage(), response) : persistAssessmentSummary(getSessionStorage(), response))
    navigate('overview')
  }
  const clearAssessment = () => {
    setResult(null)
    setSummary(null)
    clearStoredAssessment(getSessionStorage())
    clearNetworkSummary(getSessionStorage())
  }

  if (page === 'upload') return <UploadPage onNavigate={navigate} onAssessmentComplete={completeAssessment} onAssessmentClear={clearAssessment} />
  if (page === 'overview') return <OverviewPage result={result} summary={summary} onNavigate={navigate} />
  return <AnalysisPages key={page} page={page} result={result} summary={summary} onNavigate={navigate} />
}

export default App
