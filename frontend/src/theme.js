// Priority colors mean one thing each, everywhere: on pins, in lists, in the report.
export const TIERS = {
  critical: { label: 'Safety hazard', hint: 'Someone reported a live wire, sparks or a fallen pole. Make it safe first.' },
  high: { label: 'Essential facilities', hint: 'A hospital, health center, evacuation center or water pump is likely without power.' },
  medium: { label: 'Homes', hint: 'Homes are reported or predicted without power.' },
  low: { label: 'Watch', hint: 'Few reports or little to learn from a visit right now.' },
  confirmed: { label: 'Damage found', hint: 'Someone on site confirmed damage. Repair is needed.' },
  unknown: { label: 'No reports yet', hint: 'Probably affected, but nobody has reported from here.' },
  restored: { label: 'Power restored', hint: 'Repaired, and residents confirm power is back.' },
  checked: { label: 'Checked', hint: 'Someone checked this spot and found no damage.' },
  ok: { label: 'Power likely on', hint: 'Reports here look like single houses or flickering lights.' },
}
export const TIER_ORDER = ['critical', 'high', 'medium', 'confirmed', 'low', 'unknown', 'restored', 'ok']
export const tierRank = (t) => { const i = TIER_ORDER.indexOf(t); return i < 0 ? 99 : i }

// How a barangay appears on the map (null = not shown).
export function areaTier(a) {
  if (a.hazard_open) return 'critical'
  if (a.confirmed) return 'confirmed'
  if (a.restored) return 'restored'
  if (a.tier === 'ok') return a.people ? 'ok' : null
  if (!a.people) return a.p_out >= 0.3 ? 'unknown' : null
  return a.tier
}

export const SOURCES = {
  facebook_post: { label: 'Facebook post', short: 'Facebook' },
  facebook_comment: { label: "Comment on Meralco's page", short: 'FB comment' },
  x: { label: 'X post', short: 'X' },
  sms: { label: 'Text message', short: 'SMS' },
  hotline: { label: 'Hotline 16211', short: 'Hotline' },
  app: { label: 'Meralco App', short: 'App' },
}
export const SOURCE_ORDER = ['facebook_comment', 'facebook_post', 'x', 'sms', 'hotline', 'app']

export const CATEGORY = {
  hazard: 'Safety hazard',
  clue: 'Damage clue',
  noise: 'Probably not an area outage',
  follow_up: 'Follow-up',
  outage: 'No power',
  restored: 'Power is back',
}

const TZ = 'Asia/Manila'
export const clock = (iso) => new Date(iso).toLocaleTimeString('en-PH', { hour: 'numeric', minute: '2-digit', timeZone: TZ })
export const day = (iso) => new Date(iso).toLocaleDateString('en-PH', { month: 'short', day: 'numeric', timeZone: TZ })
export function ago(iso, nowIso) {
  const m = Math.max(0, Math.round((new Date(nowIso) - new Date(iso)) / 60000))
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  return h < 24 ? `${h}h ${m % 60 ? `${m % 60}m ` : ''}ago` : `${Math.floor(h / 24)}d ago`
}
export const fmt = (n) => Math.round(n).toLocaleString('en-PH')
// Account counts come from Meralco's records; rounded so they read as "about", not as exact live figures.
export const about = (n) => (n < 1000 ? fmt(n) : fmt(Math.round(n / 100) * 100))
export const plural = (n, one, many = `${one}s`) => `${fmt(n)} ${n === 1 ? one : many}`
// What the AI reader caught that the keyword rules did not, in words.
const CAUGHT = { hazard: 'a safety hazard', clue: 'a damage clue', vulnerable: 'a vulnerable person' }
export const caughtText = (r) => (r.caught ?? []).map((c) => `${CAUGHT[c.what]}${c.by === 'photo' ? ' (from the photo)' : ''}`).join(' and ')
export const gmaps = (pos) => `https://www.google.com/maps/search/?api=1&query=${pos[0]},${pos[1]}`
export function likelihood(p) {
  if (p >= 0.85) return 'Almost certainly without power'
  if (p >= 0.5) return 'Likely without power'
  if (p >= 0.15) return 'May be without power'
  return 'Power likely on'
}
