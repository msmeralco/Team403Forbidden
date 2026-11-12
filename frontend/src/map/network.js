// The exercise's power network as the app sees it: who feeds whom, and where a barangay's meters sit.
// Pure functions over the storm state: no map, no drawing.

export const LEVEL = {
  segment: 'Main line', switch: 'Switch on the main line', pole: 'Pole on the main line',
  lateral: 'Branch line', transformer: 'Distribution transformer',
}
export const METERS = 24          // meters drawn for each barangay: a sample, not every account
export const ZONES = [2, 5, 10]   // radius choices, in km, for the zone around an opened case

// Distance in km between two [lat, lon] points. Accurate enough at city scale.
export const km = (a, b) => Math.hypot((b[1] - a[1]) * 111.32 * Math.cos(a[0] * Math.PI / 180), (b[0] - a[0]) * 110.574)

// The parts of a line that lie inside a circle. A line can leave and come back, so this returns pieces.
export function clip(points, center, radius) {
  const fine = [points[0]]
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1]
    const b = points[i]
    const n = Math.max(1, Math.ceil(km(a, b) / (radius / 30)))
    for (let k = 1; k <= n; k++) fine.push([a[0] + (b[0] - a[0]) * (k / n), a[1] + (b[1] - a[1]) * (k / n)])
  }
  const parts = []
  let run = null
  fine.forEach((p) => {
    if (km(p, center) <= radius) (run ??= []).push(p)
    else { if (run && run.length > 1) parts.push(run); run = null }
  })
  if (run && run.length > 1) parts.push(run)
  return parts
}

// Equipment from `id` up to the substation, nearest first.
export function upstream(state, id) {
  const by = new Map(state.assets.map((a) => [a.id, a]))
  const chain = []
  for (let a = by.get(id); a; a = by.get(a.parent)) chain.push(a)
  return chain
}

// Everything fed through `id`: the equipment below it and the barangays they serve.
export function downstream(state, id) {
  const assets = new Set([id])
  let grew = true
  while (grew) {
    grew = false
    state.assets.forEach((a) => { if (assets.has(a.parent) && !assets.has(a.id)) { assets.add(a.id); grew = true } })
  }
  return { assets, areas: new Set(state.areas.filter((a) => assets.has(a.transformer)).map((a) => a.id)) }
}

// What to light up for the current selection: the path that feeds a barangay, or a place and all it feeds.
export function trace(state, sel) {
  if (!sel) return null
  if (sel.kind === 'area') {
    const area = state.areas.find((a) => a.id === sel.id)
    return area ? { assets: new Set(upstream(state, area.transformer).map((a) => a.id)), areas: new Set([area.id]) } : null
  }
  if (sel.kind === 'priority') {
    const down = downstream(state, sel.id)
    upstream(state, sel.id).forEach((a) => down.assets.add(a.id))
    return down
  }
  return null
}

// The equipment that could be why a barangay is dark, in the order to check it.
export function suspects(state, areaId) {
  const area = state.areas.find((a) => a.id === areaId)
  if (!area) return []
  const recs = new Map(state.recommendations.map((r) => [r.asset_id, r]))
  const fixed = new Set(state.repaired.map((x) => x.asset_id))
  const order = (x) => (x.rec && x.rec.tier !== 'low' ? x.rec.rank : x.rec ? 500 + x.rec.rank : 1000)
  return upstream(state, area.transformer).map((asset) => {
    const rec = recs.get(asset.id)
    const state_ = fixed.has(asset.id) ? 'repaired' : asset.status === 'damaged' ? 'found' : asset.status === 'intact' ? 'clear' : rec && rec.tier !== 'low' ? 'check' : 'unlikely'
    return { asset, rec, status: state_, level: LEVEL[asset.type], away: km(area.pos, asset.pos) }
  }).sort((a, b) => order(a) - order(b))
}

function hash(text) {
  let h = 2166136261
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619)
  return h >>> 0
}

// A tidy block of houses for one barangay: a short secondary line with poles, and houses on both
// sides, each with its meter on the wall facing the line. Positions are a drawing aid, not a survey.
export function meterBlock(area) {
  const seed = hash(area.id)
  const angle = ((seed % 4) * 45 + 15) * Math.PI / 180                 // which way the street runs
  const [lat0, lon0] = area.pos
  const at = (along, across) => {                                       // metres in the street's own frame
    const east = along * Math.cos(angle) - across * Math.sin(angle)
    const north = along * Math.sin(angle) + across * Math.cos(angle)
    return [lat0 + north / 110574, lon0 + east / (111320 * Math.cos(lat0 * Math.PI / 180))]
  }
  const poles = [-2.5, -1.5, -0.5, 0.5, 1.5, 2.5].map((k) => at(k * 54, 0))
  const houses = []
  poles.forEach((pole, p) => {
    const s = (p - 2.5) * 54
    ;[[-13, 26], [13, 26], [-13, -26], [13, -26]].forEach(([da, dc]) => {
      const side = Math.sign(dc)
      houses.push({
        pole,
        corners: [at(s + da - 5, dc - 4 * side), at(s + da + 5, dc - 4 * side), at(s + da + 5, dc + 4 * side), at(s + da - 5, dc + 4 * side)],
        meter: at(s + da, dc - 4 * side),                               // on the wall nearest the line
      })
    })
  })
  // Which houses reported: a fixed shuffle, so the same barangay always lights the same houses.
  const order = houses.map((_, i) => i).sort((a, b) => hash(`${area.id}:${a}`) - hash(`${area.id}:${b}`))
  const reported = new Set(order.slice(0, Math.min(area.people, houses.length)))
  houses.forEach((h, i) => { h.reported = reported.has(i) })
  return { backbone: [poles[0], poles[poles.length - 1]], poles, houses, corner: [at(-150, -40), at(150, 40)] }
}
