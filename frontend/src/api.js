async function call(path, body) {
  const res = await fetch('/api' + path, body === undefined ? undefined : {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const error = new Error(data?.detail ? String(data.detail) : `Request failed (${res.status})`)
    error.data = data   // some answers say what is missing, e.g. { need: 'area' }
    throw error
  }
  return data
}

export const api = {
  state: () => call('/state'),
  reports: () => call('/reports'),
  addReport: (body) => call('/reports', body),
  repair: (asset, by = '') => call(`/assets/${asset}/repaired`, { by }),
  hazard: (area, handled) => call(`/areas/${area}/hazard`, { handled }),
  explain: (id) => call(`/recommendations/${id}/explain`),
  observe: (asset, result, notes = '', by = '') =>
    call('/observations', { asset_id: asset, result, notes, by }),
  road: (id, blocked) => call(`/roads/${encodeURIComponent(id)}/${blocked ? 'block' : 'unblock'}`, {}),
  restrict: (id, on) => call(`/assets/${id}/${on ? 'restrict' : 'unrestrict'}`, {}),
  priority: (id, weight) => call(`/assets/${id}/priority`, { weight }),
  reset: (seed) => call('/reset', { seed }),
  config: () => call('/config'),
  truth: () => call('/truth'),
  liwa: () => call('/liwa'),
  liwaPlan: (force = false) => call(`/liwa/plan${force ? '?force=true' : ''}`),
  cases: () => call('/cases'),
  caseReports: (id) => call(`/cases/${encodeURIComponent(id)}/reports`),
  caseDecision: (id, force = false) => call(`/cases/${encodeURIComponent(id)}/decision${force ? '?force=true' : ''}`),
}

export const minutes = (m) => {
  const v = Math.round(m)
  return v < 60 ? `${v} min` : `${Math.floor(v / 60)}h ${String(v % 60).padStart(2, '0')}m`
}
export const pct = (p) => `${Math.round(p * 100)}%`
