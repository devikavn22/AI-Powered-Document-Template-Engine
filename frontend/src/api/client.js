const BASE = '/api'

async function request(method, path, body, isFormData = false) {
  const opts = {
    method,
    headers: isFormData ? {} : { 'Content-Type': 'application/json' },
    body: isFormData ? body : body ? JSON.stringify(body) : undefined,
  }
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const err = await res.json()
      if (Array.isArray(err.detail) && err.detail[0]?.msg) {
        detail = err.detail.map(e => `${e.loc?.slice(1)?.join('.') || 'field'}: ${e.msg}`).join(', ')
      } else {
        detail = err.detail?.errors ? err.detail.errors.join(', ') : (err.detail || detail)
      }
    } catch {}
    
    if (typeof detail !== 'string') {
      try { detail = JSON.stringify(detail) } catch { detail = 'Unknown error' }
    }
    throw new Error(detail)
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  // Documents
  uploadDocument: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return request('POST', '/documents/upload', fd, true)
  },
  listDocuments: () => request('GET', '/documents/'),
  getDocument: (id) => request('GET', `/documents/${id}`),

  // Templates
  listTemplates: () => request('GET', '/templates/'),
  getTemplate: (id) => request('GET', `/templates/${id}`),
  updateTemplate: (id, data) => request('PATCH', `/templates/${id}`, data),
  confirmTemplate: (id) => request('POST', `/templates/${id}/confirm`),
  getEntitySchema: () => request('GET', '/templates/entity-schema'),

  // Mappings
  getMappings: (templateId) => request('GET', `/mappings/${templateId}`),
  saveMappings: (templateId, mappings) => request('POST', `/mappings/${templateId}`, mappings),

  // Generations
  listGenerations: (templateId) => request('GET', `/generations/${templateId}`),
  createGeneration: (templateId, payload) => request('POST', `/generations/${templateId}`, payload),
  downloadGeneration: (genId) => `${BASE}/generations/download/${genId}`,
}