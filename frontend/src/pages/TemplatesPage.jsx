import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { LayoutTemplate, AlertCircle, ChevronRight } from 'lucide-react'
import { api } from '../api/client'

function Badge({ status }) {
  const map = {
    draft: ['badge-draft', 'Draft'],
    confirmed: ['badge-confirmed', 'Confirmed'],
    contract: ['badge-general', 'Contract'],
    agreement: ['badge-general', 'Agreement'],
    allotment: ['badge-general', 'Allotment'],
    invoice: ['badge-general', 'Invoice'],
    general: ['badge-draft', 'General'],
  }
  const [cls, label] = map[status] || ['badge-draft', status]
  return <span className={`badge ${cls}`}>{label}</span>
}

export default function TemplatesPage() {
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    api.listTemplates()
      .then(setTemplates)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-muted">Loading templates…</div>
  if (error) return <div className="alert alert-error"><AlertCircle size={16} />{error}</div>

  return (
    <div>
      <div className="page-header">
        <h2>Templates</h2>
        <p>Extracted templates ready for field mapping and document generation.</p>
      </div>

      {templates.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📋</div>
          <h3>No templates yet</h3>
          <p>Upload a document to get started.</p>
          <button className="btn btn-primary mt-4" onClick={() => navigate('/')}>Upload Document</button>
        </div>
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Template Name</th>
                <th>Type</th>
                <th>Fields</th>
                <th>Status</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {templates.map(t => {
                let fields = []
                try { fields = JSON.parse(t.fields_json) } catch {}
                return (
                  <tr key={t.id} style={{ cursor: 'pointer' }} onClick={() => navigate(`/templates/${t.id}`)}>
                    <td>
                      <div style={{ fontWeight: 500, color: 'var(--ink)' }}>{t.name}</div>
                      <div className="text-muted" style={{ fontSize: '0.78rem' }}>{t.description}</div>
                    </td>
                    <td><Badge status={t.document_type} /></td>
                    <td>
                      <span className="text-mono">{fields.length}</span>
                    </td>
                    <td><Badge status={t.status} /></td>
                    <td className="text-muted">{new Date(t.created_at).toLocaleDateString()}</td>
                    <td><ChevronRight size={16} color="var(--ink-muted)" /></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}