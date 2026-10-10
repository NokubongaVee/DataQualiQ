import { ShieldCheck, Upload } from 'lucide-react'

export default function Header({ activePage = 'overview', filename, onNavigate }) {
  const pages = [['upload', 'Upload & Analyse'], ['overview', 'Dashboard']]
  if (activePage !== 'upload') {
    pages.push(['data-quality', 'Data Quality'], ['intrusion-detection', 'Intrusion Detection'], ['results', 'Results'], ['reports', 'Reports'])
  }
  return <header className="app-header">
    <div className="brand"><ShieldCheck size={30} aria-hidden="true" /><div><h1>Data Quality-Aware Intrusion Detection</h1><p>Check the data first, then trust the prediction.</p></div></div>
    <div className="header-actions">{filename && <span className="filename mono" title={filename}>{filename}</span>}<button className="button primary" onClick={() => onNavigate?.('upload')}><Upload size={16} aria-hidden="true" />Upload traffic data</button></div>
    <nav className="section-nav" aria-label="Analysis navigation">{pages.map(([page, label]) => <button key={page} className={activePage === page ? 'active' : ''} aria-current={activePage === page ? 'page' : undefined} onClick={() => onNavigate?.(page)}>{label}</button>)}</nav>
  </header>
}
