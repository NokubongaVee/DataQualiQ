import { useState } from 'react'
import Header from '../components/Header'
import DataQualityPanel from '../components/DataQualityPanel'
import QualityFindings from '../components/QualityFindings'
import TrafficClassification from '../components/TrafficClassification'
import ModelPerformance from '../components/ModelPerformance'
import RecordResults from '../components/RecordResults'
import RecommendedActions from '../components/RecommendedActions'
import NoActiveAssessment from '../components/NoActiveAssessment'
import NetworkDetailPages from '../components/NetworkDetailPages'
import { getIntrusionResults, percentage } from '../utils/intrusionResults'
import { downloadAssessmentPdf } from '../utils/downloadAssessmentPdf'

const titles = { 'data-quality': ['Data Quality', 'Inspect findings, affected fields and recommended corrections.'], 'intrusion-detection': ['Intrusion Detection', 'Review supplied model predictions and performance.'], results: ['Results', 'Inspect individual traffic records and filter those needing attention.'], reports: ['Reports', 'Export the available assessment and model evidence.'] }

export default function AnalysisPages({ page, result, summary, onNavigate }) {
  const [exportError, setExportError] = useState('')
  const intrusion = getIntrusionResults(result)
  const exportReport = () => {
    try { downloadAssessmentPdf(result); setExportError('') }
    catch { setExportError('The report could not be exported. Please try again.') }
  }
  const issues = result?.issues || []
  const count = predicate => issues.filter(predicate).reduce((sum, issue) => sum + (issue.count || 0), 0)
  if (result?.intrusion_summary && result.data_quality) return <div className="app-shell"><Header activePage={page} filename={result.filename} onNavigate={onNavigate} /><main>
    <section className="page-intro"><div><h1>{titles[page][0]}</h1><p>{titles[page][1]}</p></div></section><NetworkDetailPages page={page} result={result} />
  </main></div>
  return <div className="app-shell"><Header activePage={page} filename={result?.filename} onNavigate={onNavigate} /><main>
    <section className="page-intro"><div><h1>{titles[page][0]}</h1><p>{titles[page][1]}</p></div></section>
    {!result ? <NoActiveAssessment summary={summary} onNavigate={onNavigate} /> : <>
      {page === 'data-quality' && <><div className="detail-grid"><DataQualityPanel result={result} /><section className="panel"><h2>Validation detail</h2><ul className="quality-counts"><li><span>Invalid values</span><strong>{count(issue => issue.check?.startsWith('invalid_'))}</strong></li><li><span>Inconsistent formats</span><strong>{count(issue => issue.check === 'format')}</strong></li><li><span>Affected fields</span><strong>{new Set(issues.filter(issue => issue.column != null).map(issue => issue.column)).size}</strong></li></ul><p className="panel-note">Finding occurrences can overlap. The evidence below shows the checks performed and affected values.</p></section></div><QualityFindings result={result} expanded /><RecommendedActions issues={result.translated_issues} intrusion={intrusion} hasResult onDownload={exportReport} /></>}
      {page === 'intrusion-detection' && <><div className="detail-grid"><TrafficClassification intrusion={intrusion} /><ModelPerformance intrusion={intrusion} /></div><section className="panel"><h2>Model information</h2><dl className="model-info">{[['Normal predictions', intrusion.normal ?? 'Pending'], ['Malicious predictions', intrusion.malicious ?? 'Pending'], ['Average confidence', percentage(intrusion.data?.average_confidence)], ['Model name', typeof intrusion.data?.model_name === 'string' ? intrusion.data.model_name : 'Not supplied'], ['Model version', typeof intrusion.data?.model_version === 'string' ? intrusion.data.model_version : 'Not supplied']].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>{!intrusion.data && <p className="panel-note">The current API performs data-quality assessment only. Predictions, confidence and performance appear when supplied by the model.</p>}</section></>}
      {page === 'results' && <RecordResults intrusion={intrusion} />}
      {page === 'reports' && <><section className="panel"><h2>Assessment report</h2><p className="filename mono">{result.filename}</p><p>{result.total_rows?.toLocaleString()} records · {result.total_columns} fields · Score {result.score}/100</p><p className="panel-note">Includes dataset details, quality findings, evidence and recommendations. Supplied intrusion results, confidence and record reliability are included when available.</p>{intrusion.flaggedAttacks.length > 0 && <p className="text-warning">Some malicious predictions have data-quality problems. Verify these records before acting.</p>}</section><RecommendedActions issues={result.translated_issues} intrusion={intrusion} hasResult onDownload={exportReport} /></>}
    </>}
    {exportError && <p className="error-message" role="alert">{exportError}</p>}
  </main></div>
}
