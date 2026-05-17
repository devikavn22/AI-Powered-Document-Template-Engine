import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { UploadCloud, FileText, AlertCircle, CheckCircle, Clock } from 'lucide-react'
import { api } from '../api/client'

function StatusBadge({ status }) {
  const map = {
    uploaded: ['badge-uploaded', 'Uploaded'],
    extracting: ['badge-extracting', 'Analysing…'],
    extracted: ['badge-extracted', 'Extracted'],
    confirmed: ['badge-confirmed', 'Confirmed'],
    failed: ['badge-failed', 'Failed'],
  }
  const [cls, label] = map[status] || ['badge-draft', status]
  return <span className={`badge ${cls}`}>{label}</span>
}

export default function UploadPage() {
  const navigate = useNavigate()
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [recent, setRecent] = useState(null)
  const [polling, setPolling] = useState(false)
  const fileRef = useRef()

  const handleFile = async (file) => {
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Only PDF files are accepted.')
      return
    }
    if (file.size > 20 * 1024 * 1024) {
      setError('File must be under 20 MB.')
      return
    }
    setError(null)
    setUploading(true)
    try {
      const doc = await api.uploadDocument(file)
      setRecent(doc)
      setUploading(false)
      // Poll until extracted or failed
      setPolling(true)
      const interval = setInterval(async () => {
        try {
          const updated = await api.getDocument(doc.id)
          setRecent(updated)
          if (updated.status === 'extracted' || updated.status === 'failed') {
            clearInterval(interval)
            setPolling(false)
            if (updated.status === 'extracted') {
              // Navigate to template review after a short delay
              setTimeout(() => {
                navigate('/templates')
              }, 1500)
            }
          }
        } catch {}
      }, 2000)
    } catch (e) {
      setError(e.message)
      setUploading(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <h2>Upload a Document</h2>
        <p>Upload a PDF contract, agreement, or legal document. AI will extract a reusable template.</p>
      </div>

      <div className="progress-steps">
        {['Upload PDF', 'Review Template', 'Map Fields', 'Generate'].map((label, i) => (
          <div key={i} className={`step ${i === 0 ? 'active' : ''}`}>
            <div className="step-num">{i + 1}</div>
            <div className="step-label">{label}</div>
          </div>
        ))}
      </div>

      <div className="card">
        <div
          className={`upload-zone ${dragging ? 'drag-over' : ''}`}
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]) }}
        >
          <div className="upload-zone-icon">📄</div>
          <h3>{uploading ? 'Uploading…' : 'Drop your PDF here'}</h3>
          <p>or click to browse · Max 20 MB</p>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf"
            style={{ display: 'none' }}
            onChange={(e) => handleFile(e.target.files[0])}
          />
        </div>
      </div>

      {error && (
        <div className="alert alert-error mt-4">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {recent && (
        <div className="card mt-4">
          <div className="card-header">
            <span className="card-title flex items-center gap-2">
              <FileText size={16} /> {recent.original_filename}
            </span>
            <StatusBadge status={recent.status} />
          </div>

          {recent.status === 'extracting' && (
            <div className="alert alert-info">
              <div className="spinner" />
              <span>AI is analysing your document and extracting the template structure…</span>
            </div>
          )}

          {recent.status === 'extracted' && (
            <div className="alert alert-success">
              <CheckCircle size={16} />
              <span>Template extracted! Redirecting to review…</span>
            </div>
          )}

          {recent.status === 'failed' && (
            <div className="alert alert-error">
              <AlertCircle size={16} />
              <span><strong>Extraction failed:</strong> {recent.error_message}</span>
            </div>
          )}

          <div className="text-muted mt-2">
            {recent.page_count > 0 && `${recent.page_count} pages · `}
            {(recent.file_size / 1024).toFixed(1)} KB
          </div>
        </div>
      )}

      <div className="card mt-4">
        <div className="card-title mb-4">How it works</div>
        <div className="grid-3">
          {[
            ['📤', 'Upload', 'Upload any PDF contract, agreement, allotment letter, or invoice.'],
            ['🤖', 'AI Extraction', 'Claude analyses the document and identifies every dynamic field — names, dates, amounts, identifiers.'],
            ['⚙️', 'Map & Generate', 'Map fields to your transaction data model, then generate filled PDFs on demand.'],
          ].map(([icon, title, desc]) => (
            <div key={title} style={{ padding: '16px', background: 'var(--paper-warm)', borderRadius: 'var(--radius)', textAlign: 'center' }}>
              <div style={{ fontSize: '1.8rem', marginBottom: '8px' }}>{icon}</div>
              <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, marginBottom: '4px' }}>{title}</div>
              <div className="text-muted">{desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}