import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { AlertCircle, CheckCircle, Save, ChevronRight } from 'lucide-react'
import { api } from '../api/client'

const TYPE_BADGE = {
  text: { bg: '#e0e7ff', color: '#3730a3' },
  date: { bg: '#fce7f3', color: '#9d174d' },
  currency: { bg: '#d1fae5', color: '#065f46' },
  number: { bg: '#fef3c7', color: '#92400e' },
  address: { bg: '#ede9fe', color: '#5b21b6' },
  identifier: { bg: '#ffedd5', color: '#92400e' },
}

function FieldMappingRow({ field, schema, existing, onChange }) {
  const current = existing || { mapping_type: 'unmapped', entity: '', attribute: '', literal_value: '' }
  const [type, setType] = useState(current.mapping_type || 'unmapped')
  const [entity, setEntity] = useState(current.entity || '')
  const [attribute, setAttribute] = useState(current.attribute || '')
  const [literal, setLiteral] = useState(current.literal_value || '')
  const isAuthor = field.is_author_field === true

  const handleChange = (t, e, a, l) => {
    setType(t); setEntity(e); setAttribute(a); setLiteral(l)
    onChange(field.key, { mapping_type: t, entity: e, attribute: a, literal_value: l })
  }

  const tb = TYPE_BADGE[field.field_type] || { bg: '#f3f4f6', color: '#374151' }

  return (
    <tr style={isAuthor ? { background: '#f0fdf4' } : {}}>
      <td>
        <div style={{ fontWeight: 600, fontSize: '0.82rem', fontFamily: 'Courier New, monospace', background: 'var(--paper-warm)', padding: '2px 6px', borderRadius: 4, display: 'inline-block' }}>
          {`{{${field.key}}}`}
        </div>
        <div style={{ fontSize: '0.78rem', color: 'var(--ink-muted)', marginTop: 2 }}>{field.label}</div>
        {isAuthor && (
          <div style={{ fontSize: '0.72rem', color: '#16a34a', marginTop: 2, fontWeight: 600 }}>🔒 Author field — auto-filled</div>
        )}
      </td>
      <td>
        <span style={{ background: tb.bg, color: tb.color, padding: '2px 8px', borderRadius: 4, fontSize: '0.72rem', fontWeight: 600 }}>
          {field.field_type}
        </span>
      </td>
      <td>
        <select
          className="form-control"
          style={{ minWidth: 120 }}
          value={type}
          onChange={e => handleChange(e.target.value, entity, attribute, literal)}
        >
          <option value="unmapped">— Unmapped —</option>
          <option value="entity">Entity Field</option>
          <option value="literal">Literal Value</option>
        </select>
      </td>
      <td>
        {type === 'entity' && (
          <div className="flex gap-2">
            <select
              className="form-control"
              value={entity}
              onChange={e => { setEntity(e.target.value); setAttribute(''); handleChange(type, e.target.value, '', literal) }}
              style={{ minWidth: 120 }}
            >
              <option value="">Select entity…</option>
              {Object.entries(schema).map(([key, val]) => (
                <option key={key} value={key}>{val.label}</option>
              ))}
            </select>
            {entity && (
              <select
                className="form-control"
                value={attribute}
                onChange={e => { setAttribute(e.target.value); handleChange(type, entity, e.target.value, literal) }}
                style={{ minWidth: 150 }}
              >
                <option value="">Select attribute…</option>
                {Object.entries(schema[entity]?.attributes || {}).map(([k, label]) => (
                  <option key={k} value={k}>{label}</option>
                ))}
              </select>
            )}
          </div>
        )}
        {type === 'literal' && (
          <input
            className="form-control"
            placeholder="Static value…"
            value={literal}
            onChange={e => { setLiteral(e.target.value); handleChange(type, entity, attribute, e.target.value) }}
            style={{ minWidth: 200 }}
          />
        )}
        {type === 'unmapped' && (
          <span style={{ color: 'var(--ink-muted)', fontSize: '0.82rem' }}>Will be flagged at generation time</span>
        )}
      </td>
      <td>
        {type === 'entity' && entity && attribute
          ? <span style={{ color: 'var(--success)', fontSize: '0.8rem' }}>✓ {entity}.{attribute}</span>
          : type === 'literal' && literal
          ? <span style={{ color: 'var(--success)', fontSize: '0.8rem' }}>✓ {isAuthor ? '🔒 Auto' : 'Literal'}</span>
          : <span style={{ color: 'var(--warning)', fontSize: '0.8rem' }}>⚠ Unmapped</span>
        }
      </td>
    </tr>
  )
}

export default function MappingPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [template, setTemplate] = useState(null)
  const [fields, setFields] = useState([])
  const [schema, setSchema] = useState({})
  const [existingMappings, setExistingMappings] = useState({})
  const [pendingMappings, setPendingMappings] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([
      api.getTemplate(id),
      api.getMappings(id),
      api.getEntitySchema(),
    ]).then(([t, mappings, s]) => {
      setTemplate(t)
      try { setFields(JSON.parse(t.fields_json)) } catch {}
      setSchema(s)
      const byKey = {}
      mappings.forEach(m => { byKey[m.field_key] = m })
      setExistingMappings(byKey)
    }).catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  const handleChange = (key, data) => {
    setPendingMappings(prev => ({ ...prev, [key]: { field_key: key, ...data } }))
    setSaved(false)
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      const toSave = Object.values(pendingMappings)
      
      const invalidEntity = toSave.find(m => m.mapping_type === 'entity' && (!m.entity || !m.attribute))
      if (invalidEntity) {
        throw new Error(`Please select an entity and attribute for the '${invalidEntity.field_key}' field.`)
      }
      const invalidLiteral = toSave.find(m => m.mapping_type === 'literal' && !m.literal_value)
      if (invalidLiteral) {
        throw new Error(`Please enter a literal value for the '${invalidLiteral.field_key}' field.`)
      }

      if (toSave.length > 0) {
        await api.saveMappings(id, toSave)
      }
      setSaved(true)
    } catch (e) {
      setError(e.message)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="text-muted">Loading mappings…</div>
  if (!template) return null

  const allMappings = { ...existingMappings }
  Object.entries(pendingMappings).forEach(([k, v]) => { allMappings[k] = v })
  const mappedCount = Object.values(allMappings).filter(m => m.mapping_type !== 'unmapped' && m.mapping_type).length

  return (
    <div>
      <div className="page-header">
        <h2>Field Mappings</h2>
        <p>Map each template field to your transaction data model. Every mapped field will be auto-filled during generation.</p>
      </div>

      <div className="progress-steps">
        {['Upload PDF', 'Review Template', 'Map Fields', 'Generate'].map((label, i) => (
          <div key={i} className={`step ${i === 2 ? 'active' : i < 2 ? 'done' : ''}`}>
            <div className="step-num">{i < 2 ? '✓' : i + 1}</div>
            <div className="step-label">{label}</div>
          </div>
        ))}
      </div>

      <div className="flex justify-between items-center mb-4">
        <div className="text-muted">
          {mappedCount} of {fields.length} fields mapped
        </div>
        <div className="flex gap-2">
          <button className="btn btn-outline" onClick={() => navigate(`/templates/${id}`)}>Back to Review</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving || Object.keys(pendingMappings).length === 0}>
            {saving ? <><div className="spinner" />Saving…</> : <><Save size={14} />Save Mappings</>}
          </button>
          {saved && (
            <button className="btn btn-gold" onClick={() => navigate(`/templates/${id}/generate`)}>
              Generate Document <ChevronRight size={14} />
            </button>
          )}
        </div>
      </div>

      {error && <div className="alert alert-error mb-4"><AlertCircle size={16} />{error}</div>}
      {saved && (
        <div className="alert alert-success mb-4">
          <CheckCircle size={16} />
          Mappings saved! You can now generate documents.
        </div>
      )}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Field</th>
                <th>Type</th>
                <th>Mapping Type</th>
                <th>Source</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {fields.map(f => (
                <FieldMappingRow
                  key={f.key}
                  field={f}
                  schema={schema}
                  existing={allMappings[f.key]}
                  onChange={handleChange}
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}