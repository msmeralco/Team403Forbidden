// How a power interruption (a test case) is shown: which pin it gets, where it is drawn, and the
// one ranking that both the map and the side panel show.
// The case file has no coordinates, so each case is drawn in a real barangay, its poles are placed
// inside a zone around it, and the crew comes from the nearest Meralco office on the map.
// The layout is a drawing aid; the facts (tier, safety, reports, ETA) are the case file's own.
// Pure functions: no map.

const RAD = Math.PI / 180
export const ZONE_KM = 2
const RINGS = [640, 1620, 1130]                                             // metres from the middle
export const TIER_CLASS = { 1: 'critical', 2: 'high', 3: 'medium' }        // pin colour by customer tier
export const km = (a, b) => Math.hypot((b[1] - a[1]) * 111.32 * Math.cos(a[0] * RAD), (b[0] - a[0]) * 110.574)
const offset = (p, bearing, metres) => [
  p[0] + (metres / 110574) * Math.cos(bearing * RAD),
  p[1] + (metres / (111320 * Math.cos(p[0] * RAD))) * Math.sin(bearing * RAD),
]

// A case counts as the highest customer tier among the jobs still waiting.
export const tierOf = (c) => Math.min(3, ...c.jobs.filter((j) => j.status === 'pending').map((j) => j.tier))
export const reportsOf = (c) => c.jobs.filter((j) => j.status === 'pending').reduce((sum, j) => sum + j.report_count, 0)
export const reportsText = (n) => `${n} ${n === 1 ? 'report' : 'reports'}`
export const officeName = (o) => (/^Meralco (office|business center)$/i.test(o.name) && o.city ? `${o.name}, ${o.city}` : o.name)
const EQUIPMENT = { pole: 'Pole at', transformer: 'Transformer at', line: 'Line to' }
// The mark of each kind of equipment, as one SVG path on a 24 by 24 grid, drawn as an outline:
// a pole with its crossarms and insulators, a transformer (two windings), a line section (a wire sagging between two poles).
export const EQUIPMENT_ICON = {
  pole: 'M12 2.5v19M5 7h14M5 7v2.5M19 7v2.5M8 12h8',
  transformer: 'M3.5 12a5 5 0 1 0 10 0a5 5 0 1 0-10 0M10.5 12a5 5 0 1 0 10 0a5 5 0 1 0-10 0',
  line: 'M5 5.5v13.5M2.5 8h5M19 5.5v13.5M16.5 8h5M5 8c4 6.5 10 6.5 14 0',
}
export const EQUIPMENT_NAME = { pole: 'Pole', transformer: 'Transformer', line: 'Line section' }
export const poleName = (job) => `${EQUIPMENT[job.equipment] ?? EQUIPMENT.pole} ${job.facility_label}`
// Customers still without power: what the equipment not yet done would restore.
export const customersOf = (c, resolved = []) => c.jobs.filter((j) => j.status === 'pending' && !resolved.includes(j.pole_id)).reduce((sum, j) => sum + j.customers_restored, 0)

// The barangays in an order that keeps the cases apart: each next one is the farthest from those already used.
const orders = new WeakMap()
function spread(areas) {
  if (!orders.has(areas)) {
    const order = [areas[0]]
    const rest = new Set(areas.slice(1))
    while (rest.size) {
      let best = null
      let far = -1
      rest.forEach((a) => {
        const d = Math.min(...order.map((o) => km(o.pos, a.pos)))
        if (d > far) { far = d; best = a }
      })
      order.push(best)
      rest.delete(best)
    }
    orders.set(areas, order)
  }
  return orders.get(areas)
}

export function layout(c, index, areas, offices) {
  const order = spread(areas)
  // The server says where: one of the sector's barangays, or a place of its own (Manila and other cities).
  const area = areas.find((a) => a.id === c.place?.area_id) ?? (c.place?.pos ? null : order[index % order.length])
  const center = c.place?.pos ?? area.pos
  const nearest = offices.reduce((best, o) => (!best || km([o.lat, o.lon], center) < km([best.lat, best.lon], center) ? o : best), null)
  const n = c.jobs.length
  const poles = c.jobs.map((job, k) => ({ job, pos: offset(center, 30 + index * 37 + (k * 360) / n, RINGS[k % 3]) }))      // spread round the zone, on three rings in turn
  return {
    area, center, poles, radius: ZONE_KM * 1000,
    place: c.place?.label ?? `Brgy. ${area.barangay}, ${area.city.split(',')[0]}`,
    office: nearest && { name: officeName(nearest), pos: [nearest.lat, nearest.lon], km: km([nearest.lat, nearest.lon], center) },
  }
}

export const minutes = (seconds) => (seconds == null ? null : `${Math.round(seconds / 60)} min`)

// Why a pole cannot be worked on now, from the case's own facts. null means the crew could take it.
export function blocker(job) {
  if (job.status === 'completed') return 'Already done'
  if (job.safety === 'unsafe') return 'Not safe for the crew yet'
  if (job.flood_status === 'flooded_hold' && job.work_type !== 'inspect') return 'Flooded: waiting for clearance'
  return null
}

// The ranking, once Liwa has decided: the poles to go to in order (the first is the one to check
// first), the poles on hold with the reason, and the poles that are done. null until she has decided.
// resolved: pole ids marked resolved on screen. They leave the order, and the next pole becomes the first.
export function ranking(c, resolved = []) {
  const d = c.decision
  if (!d) return null
  const dispatch = d.action === 'DISPATCH'
  const place = (j) => (j.pole_id === d.pole_id ? -1 : d.order.indexOf(j.pole_id))
  const ranked = (j) => dispatch && (j.pole_id === d.pole_id || d.order.includes(j.pole_id))
  const done = (j) => j.status === 'completed' || resolved.includes(j.pole_id)
  return {
    go: c.jobs.filter((j) => ranked(j) && !done(j)).sort((a, b) => place(a) - place(b)),
    held: c.jobs.filter((j) => !ranked(j) && !done(j)).map((job) => ({ job, why: blocker(job) ?? d.held.find((h) => h.pole_id === job.pole_id)?.why ?? 'Waiting' })),
    done: c.jobs.filter(done).map((job) => ({ job, mine: resolved.includes(job.pole_id) })),
  }
}

// Liwa's sentences, with any equipment id that slipped in replaced by its name.
export function plain(text, jobs) {
  if (!text) return text
  return [...jobs].sort((a, b) => b.pole_id.length - a.pole_id.length)
    .reduce((out, j) => out.split(j.pole_id).join(`the ${poleName(j).charAt(0).toLowerCase()}${poleName(j).slice(1)}`), text)
}

// Where every piece of equipment stands in a ranking: its number, 'hold' or 'done'. Used to say what moved.
export function standing(rank) {
  const at = {}
  rank.go.forEach((j, i) => { at[j.pole_id] = i + 1 })
  rank.held.forEach(({ job }) => { at[job.pole_id] = 'hold' })
  rank.done.forEach(({ job }) => { at[job.pole_id] = 'done' })
  return at
}

// What Liwa recommends, in a few words.
export function said(d, jobs) {
  if (d.action === 'HOLD') return 'Hold the crew'
  if (d.action !== 'DISPATCH') return 'Tie: a person should decide'
  const job = jobs.find((j) => j.pole_id === d.pole_id)
  return `Check first: ${job ? poleName(job) : d.pole_id}`
}
