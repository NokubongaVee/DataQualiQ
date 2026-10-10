import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import Header from '../components/Header'
import SummaryCards from '../components/SummaryCards'
import TrafficClassification from '../components/TrafficClassification'
import DataQualityPanel from '../components/DataQualityPanel'
import ModelPerformance from '../components/ModelPerformance'
import RecordResults from '../components/RecordResults'
import RecommendedActions from '../components/RecommendedActions'
import QualityFindings from '../components/QualityFindings'
import NoActiveAssessment from '../components/NoActiveAssessment'
import NetworkDashboard from '../components/NetworkDashboard'
import { getIntrusionResults } from '../utils/intrusionResults'
import { downloadAssessmentPdf } from '../utils/downloadAssessmentPdf'

export default function OverviewPage({ result, summary, onNavigate }) {
  const [exportError, setExportError] = useState('')
  const intrusion = getIntrusionResults(result)
  const exportReport = () => {
    try { downloadAssessmentPdf(result); setExportError('') }
    catch { setExportError('The report could not be exported. Please try again.') }
  }
  if (!result) return <div className="app-shell"><Header onNavigate={onNavigate} /><main><NoActiveAssessment summary={summary} onNavigate={onNavigate} /></main></div>
  if (result.intrusion_summary && result.data_quality) return <div className="app-shell"><Header filename={result.filename} onNavigate={onNavigate} /><main>
    <section className="page-intro"><div><h1>Security Analysis Overview</h1><p>Data quality and intrusion-detection results for the uploaded network traffic.</p></div><button className="button outline" onClick={() => onNavigate('upload')}>Analyse another file</button></section>
    <NetworkDashboard result={result} />
  </main></div>
  return <div className="app-shell"><Header filename={result?.filename} onNavigate={onNavigate} /><main>
    <section className="page-intro"><div><h1>Security Analysis Overview</h1><p>Data quality and intrusion-detection results for the uploaded network traffic.</p><small>See what the model detected, how reliable the source data is, and which records need attention.</small></div><button className="button outline" onClick={() => onNavigate('upload')}>Analyse another file</button></section>
    {intrusion.flaggedAttacks.length > 0 && <div className="warning-panel" role="alert"><AlertTriangle size={22} aria-hidden="true" /><div><strong>Some attack predictions may be less reliable</strong><p>{intrusion.flaggedAttacks.length.toLocaleString()} supplied records classified as attacks contain missing, inconsistent or invalid fields. Review these manually before acting. This count covers the record results provided.</p></div></div>}
    <SummaryCards result={result} intrusion={intrusion} />
    <div className="middle-grid"><TrafficClassification intrusion={intrusion} /><DataQualityPanel result={result} /><ModelPerformance intrusion={intrusion} /></div>
    <div className="results-grid"><RecordResults intrusion={intrusion} /><RecommendedActions issues={result?.translated_issues} intrusion={intrusion} hasResult={!!result} onDownload={exportReport} /></div>
    {exportError && <p role="alert" className="error-message">{exportError}</p>}
    {result && <QualityFindings result={result} />}
    <footer><span>DataQualiQ · Traffic analysis workspace</span><span>{result ? 'Quality assessment complete' + (result.time_taken ? ' · ' + result.time_taken + 's' : '') : 'Upload a CSV to begin'} · {intrusion.data ? 'Model results supplied' : 'Intrusion detection pending'}</span></footer>
  </main></div>
}
