import { useState } from 'react';
import ScanPreview from '../components/ScanPreview'
import Dropzone from '../components/Dropzone'
import Header from '../components/Header'

export default function UploadPage({ onNavigate }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const handleFileSelected = (file) => {
    setSelectedFile(file);
    setErrorMessage('');
    sessionStorage.removeItem('assessmentResult');
  };

  const handleRunAssessment = async () => {
    if (!selectedFile) {
      setErrorMessage('Please upload a CSV file first.');
      return;
    }

    const formData = new FormData();
    formData.append('file', selectedFile);

    const startTime = performance.now();
    setIsLoading(true);
    setErrorMessage('');

    try {
      const response = await fetch('http://localhost:8000/assess', {
        method: 'POST',
        body: formData,
      });

      let result;
      try {
        result = await response.json();
      } catch {
        throw new Error('The backend returned an invalid response.')
      }
      if (!response.ok) {
        const detail = typeof result.detail === 'string'
          ? result.detail
          : 'The backend could not assess this file.'
        throw new Error(detail)
      }

      const elapsedSeconds = ((performance.now() - startTime) / 1000).toFixed(1);
      result.time_taken = elapsedSeconds;

      sessionStorage.setItem('assessmentResult', JSON.stringify(result));
      onNavigate('overview');
    } catch (error) {
      setErrorMessage(`Assessment failed: ${error.message}`);
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };
  return (
    <div className="landing-page min-h-screen w-full flex flex-col" style={{ background: '#F5F6F8', fontFamily: 'Inter, sans-serif' }}>

      <Header activePage="upload" onNavigate={onNavigate} />

      <main className="min-w-0 flex-1 max-w-7xl mx-auto px-4 sm:px-8 py-3 w-full">
        <div className="landing-hero grid grid-cols-1 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)] gap-6 lg:gap-8 items-start">
          <div className="min-w-0 flex flex-col justify-center h-full">
            <h1 className="text-3xl sm:text-4xl font-extrabold leading-[1.15] tracking-tight" style={{ color: '#0B1E33' }}>
              Know your data<br />before it costs you<br /><span style={{ color: '#00BAB1' }}>a decision.</span>
            </h1>
            <p className="mt-5 text-slate-500 text-lg leading-relaxed max-w-sm">
              Upload a spreadsheet and receive an instant data quality assessment.
            </p>
          </div>
          <ScanPreview />
        </div>
        <div className="upload-controls">
          <Dropzone onFileSelected={handleFileSelected} errorMessage={errorMessage} />
          <div className="flex justify-center mt-3 pb-3">
            <button
              onClick={handleRunAssessment}
              disabled={isLoading}
              aria-busy={isLoading}
              className="flex items-center gap-2.5 px-10 py-3 rounded-xl text-white text-base font-bold shadow-lg"
              style={{ background: isLoading ? '#7AA7A4' : '#0F8C86' }}
            >
              {isLoading ? 'Assessing dataset...' : 'Run Assessment'}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
