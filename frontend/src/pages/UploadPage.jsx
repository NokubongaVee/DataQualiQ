import { useEffect, useRef, useState } from 'react';
import { ShieldCheck, Database, Search, FileCheck2, ChevronRight } from 'lucide-react'
import Dropzone from '../components/Dropzone'
import Header from '../components/Header'
import { analyzeNetwork, validateNetworkFile } from '../api/networkAnalysis'
import { PROCESSING_STAGES } from '../utils/networkAnalysis'

export default function UploadPage({ onNavigate, onAssessmentComplete, onAssessmentClear }) {
  const assessmentVersion = useRef(0);
  const inFlight = useRef(false);
  const requestController = useRef(null);
  useEffect(() => () => { assessmentVersion.current += 1; requestController.current?.abort(); }, []);
  const [selectedFile, setSelectedFile] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [stageIndex, setStageIndex] = useState(0);
  useEffect(() => {
    if (!isLoading) return;
    const interval = setInterval(() => setStageIndex(current => Math.min(current + 1, PROCESSING_STAGES.length - 1)), 1600);
    return () => clearInterval(interval);
  }, [isLoading]);

  const handleFileSelected = (file) => {
    if (inFlight.current) return;
    assessmentVersion.current += 1;
    setIsLoading(false);
    setSelectedFile(file);
    setErrorMessage('');
    onAssessmentClear?.();
  };

  const handleRunAssessment = async () => {
    if (inFlight.current) return;
    const validation = validateNetworkFile(selectedFile);
    if (validation) {
      setErrorMessage(validation);
      return;
    }

    const requestVersion = ++assessmentVersion.current;
    inFlight.current = true;
    requestController.current = new AbortController();
    setStageIndex(0);
    setIsLoading(true);
    setErrorMessage('');

    let completedResult;
    try {
      completedResult = await analyzeNetwork(selectedFile, { offset: 0, limit: 100, signal: requestController.current.signal });
      // A replaced file or unmounted upload must not publish stale statistics.
      if (requestVersion !== assessmentVersion.current) return;
    } catch (error) {
      if (requestVersion !== assessmentVersion.current) return;
      if (error.name !== 'AbortError') setErrorMessage(`Unable to analyse this network dataset. ${error.message}`);
      return;
    } finally {
      inFlight.current = false;
      if (requestVersion === assessmentVersion.current) setIsLoading(false);
    }
    // Publishing a successful response is separate from the backend error path.
    if (completedResult && requestVersion === assessmentVersion.current) onAssessmentComplete?.(completedResult);
  };
  return (
    <div className="app-shell traffic-entry">
      <Header activePage="upload" filename={selectedFile?.name} onNavigate={onNavigate} />
      <main>
        <div className="traffic-entry-layout">
        <section className="traffic-entry-copy">
          <h1>Feed us the<br />traffic.<br /><span>We’ll find what<br className="hero-break" /> needs attention.</span></h1>
          <p className="traffic-entry-intro">Upload network traffic data. We assess its quality, classify each record as normal or malicious, and highlight results that need review.</p>
        <section className="upload-panel">
          <Dropzone onFileSelected={handleFileSelected} errorMessage={errorMessage} disabled={isLoading} />
          <div className="upload-submit">
            <span role="status">{isLoading ? 'Uploading and analysing network traffic…' : selectedFile ? 'CSV selected · ready for analysis' : 'CSV files · maximum 50 MiB'}</span>
            <button onClick={handleRunAssessment} disabled={isLoading} aria-busy={isLoading} className="button primary">
              {isLoading ? 'Analysing network traffic…' : 'Analyse Network Traffic'}
            </button>
          </div>
          {isLoading && <section className="processing-panel" aria-label="Analysis processing" aria-live="polite"><h3>Analysis in progress</h3><p>The API returns one final response. These stages describe the analysis; timing is approximate, not live backend progress.</p><ol>{PROCESSING_STAGES.map((stage, index) => <li key={stage} className={index === stageIndex ? 'stage-active' : ''}><span>{stage}</span><small>{index === stageIndex ? 'Illustrative processing state · awaiting response' : 'Included in this analysis'}</small></li>)}</ol></section>}
          <details className="traffic-upload-help"><summary>Dataset requirements</summary><p>Upload a compatible network-traffic CSV, up to 50 MiB. The backend validates required predictive fields; target labels and identifiers are not required. Your original CSV is preserved.</p></details>
        </section>
        <ol className="traffic-entry-steps" aria-label="Analysis workflow">{[[Database, 'CHECK', 'Assess data quality'], [Search, 'CLASSIFY', 'Detect normal and malicious traffic'], [FileCheck2, 'REVIEW', 'Highlight results that need attention']].map(([Icon, title, description], index) => <li key={title}><span className="traffic-step-number">0{index + 1}</span><div><Icon size={19} aria-hidden="true" /><strong>{title}</strong><small>{description}</small></div>{index < 2 && <ChevronRight className="traffic-step-arrow" size={18} aria-hidden="true" />}</li>)}</ol>
        </section>
        <aside className="traffic-radar-panel" aria-label="Illustration of network traffic screening">
          <div className="traffic-radar"><svg viewBox="0 0 400 400" aria-hidden="true"><defs><radialGradient id="radar-glow"><stop stopColor="#00b8f5" stopOpacity=".18" /><stop offset="1" stopColor="#00b8f5" stopOpacity="0" /></radialGradient><linearGradient id="radar-sweep"><stop stopColor="#00b8f5" stopOpacity=".02" /><stop offset="1" stopColor="#00b8f5" stopOpacity=".32" /></linearGradient></defs><circle cx="200" cy="200" r="180" fill="url(#radar-glow)" />{[52, 94, 136, 180].map(radius => <circle key={radius} cx="200" cy="200" r={radius} fill="none" stroke="#006080" strokeWidth="1" />)}<path d="M200 20V380M20 200H380" stroke="#004657" /><path d="M200 200V20A180 180 0 0 1 319 65Z" fill="url(#radar-sweep)" stroke="#0084ad" /><path d="M200 20V158" stroke="#00bbf4" strokeWidth="2" />{[[109,115],[83,249],[145,323],[260,295],[283,136]].map(([cx,cy]) => <circle key={cx} cx={cx} cy={cy} r="5" fill="#00b8f5" />)}{[[136,75],[314,226]].map(([cx,cy]) => <g key={cx}><circle cx={cx} cy={cy} r="12" fill="none" stroke="#e75e45" /><circle cx={cx} cy={cy} r="6" fill="#ff684f" /></g>)}{[[66,174],[221,344]].map(([cx,cy]) => <circle key={cx} cx={cx} cy={cy} r="7" fill="none" stroke="#ffb847" strokeWidth="2" />)}</svg><ShieldCheck className="traffic-radar-shield" size={80} strokeWidth={1.2} aria-hidden="true" /></div>
          <div className="traffic-radar-legend"><span><i className="normal" />Normal</span><span><i className="malicious" />Malicious</span><span><i className="review" />Needs review</span></div><small className="traffic-radar-caption">Network screening illustration ? upload to see your results</small>
        </aside>
        </div>
      </main>
    </div>
  );
}
