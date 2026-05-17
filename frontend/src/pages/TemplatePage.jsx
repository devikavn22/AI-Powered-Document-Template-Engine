import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { AlertCircle, CheckCircle, ChevronRight, Edit2 } from 'lucide-react'
import { api } from '../api/client'

const TYPE_COLORS = {
  text: '#e0e7ff',
  date: '#fce7f3',
  currency: '#d1fae5',
  number: '#fef3c7',
  address: '#ede9fe',
  identifier: '#ffedd5',
}

export default function TemplatePage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [template, setTemplate] = useState(null)
  const [fields, setFields] = useState([])
  const [warnings, setWarnings] = useState([])
  const [loading, setLoading] = useState(true)
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState(null)
  const [editingName, setEditingName] = useState(false)
  const [name, setName] = useState('')

  useEffect(() => {
    api.getTemplate(id)
      .then(t => {
        setTemplate(t)
        setName(t.name)
        try { setFields(JSON.parse(t.fields_json)) } catch { setFields([]) }
        try { setWarnings(JSON.parse(t.extraction_warnings || '[]')) } catch { setWarnings([]) }
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  const handleConfirm = async () => {
    setConfirming(true)
    try {
      if (name !== template.name) {
        await api.updateTemplate(id, { name })
      }
      await api.confirmTemplate(id)
      navigate(`/templates/${id}/map`)
    } catch (e) {
      setError(e.message)
    } finally {
      setConfirming(false)
    }
  }

  if (loading) return <div className="text-muted">Loading template…</div>
  if (error) return <div className="alert alert-error"><AlertCircle size={16} />{error}</div>
  if (!template) return null

  const isConfirmed = template.status === 'confirmed'

  return (
    <div>
      <div className="page-header">
        <div className="flex items-center gap-3 mb-2">
          {editingName ? (
            <input
              className="form-control"
              style={{ fontSize: '1.4rem', fontFamily: 'var(--font-display)', width: 'auto', flexGrow: 1 }}
              value={name}
              onChange={e => setName(e.target.value)}
              onBlur={() => setEditingName(false)}
              autoFocus
            />
          ) : (
            <h2 onClick={() => !isConfirmed && setEditingName(true)} style={{ cursor: isConfirmed ? 'default' : 'pointer' }}>
              {name}
              {!isConfirmed && <Edit2 size={14} style={{ marginLeft: 8, color: 'var(--ink-muted)', verticalAlign: 'middle' }} />}
            </h2>
          )}
          <span className={`badge ${isConfirmed ? 'badge-confirmed' : 'badge-draft'}`}>
            {isConfirmed ? 'Confirmed' : 'Draft'}
          </span>
        </div>
        <p>{template.description}</p>
      </div>

      <div className="progress-steps">
        {['Upload PDF', 'Review Template', 'Map Fields', 'Generate'].map((label, i) => (
          <div key={i} className={`step ${i === 1 ? 'active' : i < 1 ? 'done' : ''}`}>
            <div className="step-num">{i < 1 ? '✓' : i + 1}</div>
            <div className="step-label">{label}</div>
          </div>
        ))}
      </div>

      {warnings.length > 0 && (
        <div className="alert alert-warning mb-4">
          <AlertCircle size={16} />
          <div>
            <strong>Extraction warnings ({warnings.length})</strong>
            <ul style={{ marginTop: 4, paddingLeft: 16 }}>
              {warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          </div>
        </div>
      )}

      <div className="card mb-4">
        <div className="card-header">
          <span className="card-title">Extracted Fields ({fields.length})</span>
          <span className="badge badge-general">{template.document_type}</span>
        </div>
        <p className="text-muted mb-4">Review the fields AI extracted. Every placeholder will need a mapping before you can generate documents.</p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Field Key</th>
                <th>Label</th>
                <th>Type</th>
                <th>Description</th>
                <th>Example Value</th>
                <th>Required</th>
              </tr>
            </thead>
            <tbody>
              {fields.map(f => (
                <tr key={f.key}>
                  <td><span className="text-mono">{`{{${f.key}}}`}</span></td>
                  <td style={{ fontWeight: 500, color: 'var(--ink)' }}>{f.label}</td>
                  <td>
                    <span style={{
                      background: TYPE_COLORS[f.field_type] || '#f3f4f6',
                      padding: '2px 8px',
                      borderRadius: 4,
                      fontSize: '0.75rem',
                      fontWeight: 500,
                    }}>
                      {f.field_type}
                    </span>
                  </td>
                  <td className="text-muted">{f.description}</td>
                  <td style={{ fontStyle: 'italic', color: 'var(--ink-muted)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {f.example_value}
                  </td>
                  <td>{f.required ? '✓' : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card mb-4">
        <div className="card-title mb-2">Template Preview</div>
        <p className="text-muted mb-3">Document body with <span className="text-mono">{'{{FIELD_KEY}}'}</span> placeholders.</p>
        <pre style={{
          background: 'var(--paper-warm)',
          border: '1px solid var(--paper-border)',
          borderRadius: 'var(--radius)',
          padding: '16px',
          fontSize: '0.78rem',
          overflowX: 'auto',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          maxHeight: '400px',
          lineHeight: 1.7,
          color: 'var(--ink-soft)',
          fontFamily: 'Georgia, serif',
        }}>
          {template.template_body}
        </pre>
      </div>

      {!isConfirmed ? (
        <div className="flex gap-3">
          <button className="btn btn-gold btn-lg" onClick={handleConfirm} disabled={confirming}>
            {confirming ? <><div className="spinner" /> Confirming…</> : <>Confirm Template <ChevronRight size={16} /></>}
          </button>
          <button className="btn btn-outline" onClick={() => navigate('/templates')}>Back to Templates</button>
        </div>
      ) : (
        <div className="flex gap-3">
          <button className="btn btn-gold btn-lg" onClick={() => navigate(`/templates/${id}/map`)}>
            Manage Field Mappings <ChevronRight size={16} />
          </button>
          <button className="btn btn-outline" onClick={() => navigate(`/templates/${id}/generate`)}>
            Generate Document
          </button>
        </div>
      )}
    </div>
  )
}