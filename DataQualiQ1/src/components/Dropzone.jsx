import { UploadCloud } from 'lucide-react'
import { useDropzone } from 'react-dropzone'

export default function Dropzone({ onFileSelected, errorMessage }) {
  const { getRootProps, getInputProps, acceptedFiles, fileRejections } = useDropzone({
    accept: {
      'text/csv': ['.csv'],
      'text/plain': ['.csv'],
      'application/csv': ['.csv'],
      'application/vnd.ms-excel': ['.csv'],
      'application/octet-stream': ['.csv'],
    },
    maxSize: 50 * 1024 * 1024,
    onDrop: (files) => {
      if (files.length > 0 && onFileSelected) {
        onFileSelected(files[0]);
      }
    },
  });

  const file = acceptedFiles[0];
  const rejectionMessage = fileRejections.length > 0
    ? 'Please choose a CSV file smaller than 50 MB.'
    : errorMessage

  return (
    <div className="mt-2 mx-auto rounded-3xl bg-white shadow-md p-3 w-full" style={{ maxWidth: '1000px' }}>
      <div
        {...getRootProps({ role: 'group', 'aria-label': 'Choose or drop a CSV file' })}
        className="rounded-2xl flex flex-col items-center justify-center py-4 px-3 sm:px-8 cursor-pointer text-center"
        style={{ border: '2px dashed #00BAB1' }}
      >
        <input {...getInputProps({ 'aria-label': 'CSV file' })} />
        <UploadCloud size={26} color="#00BAB1" strokeWidth={1.8} />
        <div className="max-w-full mt-2 text-base font-bold" style={{ color: '#0B1E33' }}>
          {file ? file.name : 'Drop CSV Here'}
        </div>
<div className="text-sm text-slate-400">or</div>
<button
  type="button"
  className="mt-2 px-5 py-2 rounded-lg text-white text-sm font-semibold"
  style={{ background: '#0F8C86' }}
>
  Browse Files
</button>
        <div className="mt-2 text-sm text-slate-400 font-mono">
          {file ? `${(file.size / 1024).toFixed(1)} KB` : 'customers_raw.csv'}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-center gap-2 mt-3 text-sm text-slate-600 text-center">
        <span>CSV Supported</span>
        <span className="w-1 h-1 rounded-full bg-slate-300" />
        <span>Maximum File Size: 50 MB</span>
      </div>
      {rejectionMessage && (
        <p role="alert" className="mt-2 text-center text-sm font-medium" style={{ color: '#B42318' }}>
          {rejectionMessage}
        </p>
      )}
    </div>
  )
}
