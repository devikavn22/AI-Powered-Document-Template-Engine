import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { AlertCircle, Download, FileText, Lock, Edit3 } from 'lucide-react'
import { api } from '../api/client'

// Entity fields for entity-mapped fields (payload structure)
const ENTITY_SCHEMA_LABELS = {
  buyer: 'Buyer / Client',
  seller: 'Seller / Vendor',
  property: 'Property / Unit',
  deal: 'Deal / Order',
  agent: 'Agent',
  bank: 'Bank / Financier',
  witness: 'Witness',
  system: 'System (Auto)',
}

export default function GeneratePage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [template, setTemplate] = useState(null)
  const [mappings, setMappings] = useState([])
  const [fields, setFields] = useState([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [generation, setGeneration] = useState(null)
  const [error, setError] = useState(null)
  const [history, setHistory] = useState(null)

  // Dynamic overrides: field_key → value entered by user at generate time
  const [overrides, setOverrides] = useState({})
  // Entity payload for entity-mapped fields
  const [entityPayload, setEntityPayload] = useState({})

  useEffect(() => {
    Promise.all([api.getTemplate(id), api.getMappings(id), api.listGenerations(id)])
      .then(([t, m, g]) => {
        setTemplate(t)
        setMappings(m)
        setHistory(g)
        try { setFields(JSON.parse(t.fields_json || '[]')) } catch { setFields([]) }
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  const handleOverride = (key, value) => {
    setOverrides(prev => ({ ...prev, [key]: value }))
  }

  const handleEntityField = (entity, attr, value) => {
    setEntityPayload(prev => ({
      ...prev,
      [entity]: { ...(prev[entity] || {}), [attr]: value }
    }))
  }

  const handleGenerate = async () => {
    setGenerating(true)
    setError(null)
    setGeneration(null)
    try {
      // Build the payload: entity data + field overrides for unmapped/counterparty fields
      const payload = {
        ...entityPayload,
        field_overrides: overrides,
      }
      const gen = await api.createGeneration(id, payload)
      setGeneration(gen)
      setHistory(prev => [gen, ...(prev || [])])
    } catch (e) {
      setError(e.message)
    } finally {
      setGenerating(false)
    }
  }

  if (loading) return <div className="text-muted">Loading…</div>
  if (!template) return null

  // Categorise fields
  const mappingByKey = {}
  mappings.forEach(m => { mappingByKey[m.field_key] = m })

  const unmappedFields = fields.filter(f => {
    const m = mappingByKey[f.key]
    return !m || m.mapping_type === 'unmapped'
  })

  const literalFields = fields.filter(f => {
    const m = mappingByKey[f.key]
    return m && m.mapping_type === 'literal'
  })

  const entityMappedFields = fields.filter(f => {
    const m = mappingByKey[f.key]
    return m && m.mapping_type === 'entity'
  })

  // Group entity fields by entity
  const entityGroups = {}
  entityMappedFields.forEach(f => {
    const m = mappingByKey[f.key]
    if (!entityGroups[m.entity]) entityGroups[m.entity] = []
    entityGroups[m.entity].push({ field: f, mapping: m })
  })

  let flagged = []
  if (generation?.flagged_fields) {
    try { flagged = JSON.parse(generation.flagged_fields) } catch {}
  }

  const hasUnmapped = unmappedFields.length > 0

  return (
    <div>
      <div className="page-header">
        <h2>Generate Document</h2>
        <p>Fill in the counterparty details below and generate a download-ready PDF.</p>
      </div>

      <div className="progress-steps">
        {['Upload PDF', 'Review Template', 'Map Fields', 'Generate'].map((label, i) => (
          <div key={i} className={`step ${i === 3 ? 'active' : 'done'}`}>
            <div className="step-num">{i < 3 ? '✓' : i + 1}</div>
            <div className="step-label">{label}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 20, alignItems: 'start' }}>
        <div>

          {/* ── Unmapped / Counterparty fields ── */}
          {unmappedFields.length > 0 && (
            <div className="card mb-4">
              <div className="card-header">
                <span className="card-title">
                  <Edit3 size={15} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
                  Counterparty Details
                </span>
                <span className="badge badge-draft">{unmappedFields.length} fields</span>
              </div>
              <p className="text-muted mb-4" style={{ fontSize: '0.85rem' }}>
                These fields are specific to the other party signing this document. Fill them in for this generation.
              </p>
              <div className="grid-2">
                {unmappedFields.map(f => (
                  <div key={f.key} className="form-group" style={{ marginBottom: 14 }}>
                    <label className="form-label">
                      {f.label}
                      {f.required && <span style={{ color: 'var(--error)', marginLeft: 3 }}>*</span>}
                    </label>
                    <input
                      type={f.field_type === 'date' ? 'date' : f.field_type === 'currency' || f.field_type === 'number' ? 'number' : 'text'}
                      className="form-control"
                      placeholder={f.description || f.label}
                      value={overrides[f.key] || ''}
                      onChange={e => handleOverride(f.key, e.target.value)}
                    />
                    <div style={{ fontSize: '0.72rem', color: 'var(--ink-muted)', marginTop: 3 }}>{f.description}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Auto-filled (literal) fields ── */}
          {literalFields.length > 0 && (
            <div className="card mb-4">
              <div className="card-header">
                <span className="card-title">
                  <Lock size={14} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle', color: '#16a34a' }} />
                  Auto-filled Fields
                </span>
                <span style={{ fontSize: '0.75rem', color: '#16a34a', fontWeight: 600 }}>✓ Pre-populated from document</span>
              </div>
              <p className="text-muted mb-3" style={{ fontSize: '0.85rem' }}>
                These values were extracted from the original document and will be auto-filled. You can override them if needed.
              </p>
              <div className="grid-2">
                {literalFields.map(f => {
                  const m = mappingByKey[f.key]
                  return (
                    <div key={f.key} className="form-group" style={{ marginBottom: 12, background: '#f0fdf4', borderRadius: 6, padding: '8px 10px' }}>
                      <label className="form-label" style={{ color: '#15803d', fontSize: '0.78rem' }}>
                        🔒 {f.label}
                      </label>
                      <input
                        type="text"
                        className="form-control"
                        value={overrides[f.key] !== undefined ? overrides[f.key] : (m?.literal_value || '')}
                        onChange={e => handleOverride(f.key, e.target.value)}
                        style={{ background: '#fff', borderColor: '#86efac' }}
                      />
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* ── Entity-mapped fields ── */}
          {Object.keys(entityGroups).length > 0 && (
            <div className="card mb-4">
              <div className="card-title mb-3">Entity Data</div>
              <p className="text-muted mb-4" style={{ fontSize: '0.85rem' }}>
                These fields are mapped to your data model. Fill in the relevant entity details.
              </p>
              {Object.entries(entityGroups).map(([entity, items]) => (
                <div key={entity} style={{ marginBottom: 16 }}>
                  <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: 8, color: 'var(--ink)' }}>
                    {ENTITY_SCHEMA_LABELS[entity] || entity}
                  </div>
                  <div className="grid-2">
                    {items.map(({ field, mapping }) => (
                      <div key={field.key} className="form-group" style={{ marginBottom: 10 }}>
                        <label className="form-label">{field.label} <span style={{ color: 'var(--ink-muted)', fontWeight: 400 }}>({mapping.attribute})</span></label>
                        <input
                          type={field.field_type === 'date' ? 'date' : 'text'}
                          className="form-control"
                          value={(entityPayload[entity] || {})[mapping.attribute] || ''}
                          onChange={e => handleEntityField(entity, mapping.attribute, e.target.value)}
                          placeholder={field.description}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}

          {fields.length === 0 && (
            <div className="alert alert-warning">
              <AlertCircle size={16} /> No fields found in this template. Please re-upload your document.
            </div>
          )}
        </div>

        {/* ── Sidebar ── */}
        <div>
          <div className="card mb-4" style={{ position: 'sticky', top: 20 }}>
            <div className="card-title mb-2">Generate PDF</div>
            <div className="text-muted mb-4" style={{ fontSize: '0.82rem' }}>
              Template: <strong>{template.name}</strong><br />
              {unmappedFields.length} counterparty fields · {literalFields.length} auto-filled · {entityMappedFields.length} entity-mapped
            </div>

            {error && <div className="alert alert-error mb-3"><AlertCircle size={14} />{error}</div>}

            {generation && generation.status === 'completed' && (
              <>
                {flagged.length > 0 && (
                  <div className="alert alert-warning mb-3">
                    <AlertCircle size={14} />
                    <div>
                      <strong>{flagged.length} field{flagged.length > 1 ? 's' : ''} still missing:</strong>
                      <ul style={{ marginTop: 4, paddingLeft: 14, fontSize: '0.8rem' }}>
                        {flagged.map(f => <li key={f.key}><code>{f.key}</code></li>)}
                      </ul>
                    </div>
                  </div>
                )}
                <div className="alert alert-success mb-3">
                  <FileText size={14} /> Document generated!
                </div>
                <a
                  href={api.downloadGeneration(generation.id)}
                  className="btn btn-gold w-full"
                  style={{ justifyContent: 'center', marginBottom: 8 }}
                  download
                >
                  <Download size={14} /> Download PDF
                </a>
              </>
            )}

            <button
              className="btn btn-primary w-full"
              style={{ justifyContent: 'center' }}
              onClick={handleGenerate}
              disabled={generating}
            >
              {generating ? <><div className="spinner" />Generating…</> : <>Generate PDF</>}
            </button>

            <button
              className="btn btn-outline w-full mt-2"
              style={{ justifyContent: 'center' }}
              onClick={() => navigate(`/templates/${id}/map`)}
            >
              Edit Mappings
            </button>
          </div>

          {history && history.length > 0 && (
            <div className="card">
              <div className="card-title mb-3">Generation History</div>
              {history.map(g => (
                <div key={g.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--paper-border)' }}>
                  <div>
                    <div style={{ fontSize: '0.8rem', fontWeight: 500 }}>{g.output_filename || '—'}</div>
                    <div className="text-muted" style={{ fontSize: '0.75rem' }}>{new Date(g.created_at).toLocaleString()}</div>
                  </div>
                  <div className="flex gap-2 items-center">
                    <span className={`badge badge-${g.status}`}>{g.status}</span>
                    {g.status === 'completed' && (
                      <a href={api.downloadGeneration(g.id)} className="btn btn-outline btn-sm" download>
                        <Download size={12} />
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}