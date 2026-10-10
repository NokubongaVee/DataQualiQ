import { UploadCloud } from 'lucide-react'
import { useDropzone } from 'react-dropzone'

export default function Dropzone({ onFileSelected, errorMessage, disabled = false }) {
  const { getRootProps, getInputProps, acceptedFiles, fileRejections, isDragActive } = useDropzone({
    accept: {
      'text/csv': ['.csv'], 'text/plain': ['.csv'], 'application/csv': ['.csv'],
      'application/vnd.ms-excel': ['.csv'], 'application/octet-stream': ['.csv'],
    },
    maxSize: 50 * 1024 * 1024,
    multiple: false,
    disabled,
    onDrop: files => { if (files.length && onFileSelected) onFileSelected(files[0]) },
  })
  const file = acceptedFiles[0]
  const rejectionMessage = fileRejections.length ? 'Please choose one CSV file no larger than 50 MiB.' : errorMessage
  return <>
    <div {...getRootProps({ role: 'group', 'aria-label': 'Choose or drop a CSV file', 'aria-disabled': disabled })} className={isDragActive ? 'dropzone is-dragging' : 'dropzone'}>
      <input {...getInputProps({ 'aria-label': 'CSV file', disabled })} />
      <UploadCloud size={30} aria-hidden="true" />
      <strong>{file ? file.name : 'Drop your network CSV here'}</strong>
      <small>{file ? (file.size / 1024).toFixed(1) + ' KB · CSV selected' : '.csv network traffic data'}</small>
      {!file && <span className="muted">or choose a file</span>}
      <button type="button" disabled={disabled} className="button outline">Choose File</button>
    </div>
    {rejectionMessage && <p role="alert" className="error-message">{rejectionMessage}</p>}
  </>
}
