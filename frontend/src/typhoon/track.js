// A simulated typhoon track across Luzon. Pure functions: no map, no drawing.
//
// Every track starts over the Pacific, crosses Luzon near Metro Manila and leaves to the west,
// but the exact path, speed and peak strength come from a seed, so no two runs look the same.
// Time is counted in hours from landfall (negative before it); the storm is "over" for the
// service area CLEAR_H hours after landfall, which is the all-clear time the rest of the app uses.

const RAD = Math.PI / 180
export const METRO_MANILA = [14.6, 121.0]
export const CLEAR_H = 9

// Philippine classification by sustained winds near the center, in km/h.
export const CATEGORIES = [
  { key: 'td', min: 0, label: 'Tropical depression', letter: 'D' },
  { key: 'ts', min: 62, label: 'Tropical storm', letter: 'S' },
  { key: 'sts', min: 89, label: 'Severe tropical storm', letter: 'S' },
  { key: 'ty', min: 118, label: 'Typhoon', letter: 'T' },
  { key: 'sty', min: 185, label: 'Super typhoon', letter: 'T' },
]
export const category = (kmh) => [...CATEGORIES].reverse().find((c) => kmh >= c.min)

function random(seed) {                      // mulberry32: small, fast, repeatable
  let a = seed >>> 0
  return () => {
    a = (a + 0x6D2B79F5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function km(a, b) {
  const dLat = (b[0] - a[0]) * RAD
  const dLon = (b[1] - a[1]) * RAD
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[0] * RAD) * Math.cos(b[0] * RAD) * Math.sin(dLon / 2) ** 2
  return 6371 * 2 * Math.asin(Math.sqrt(h))
}

// A point `dist` km from `p` in direction `bearing` (degrees clockwise from north). Fine at this scale.
function offset(p, bearing, dist) {
  return [p[0] + (dist / 111) * Math.cos(bearing * RAD), p[1] + (dist / (111 * Math.cos(p[0] * RAD))) * Math.sin(bearing * RAD)]
}
const bearing = (a, b) => Math.atan2((b[1] - a[1]) * Math.cos(a[0] * RAD), b[0] - a[0]) / RAD
const bezier = (p0, p1, p2, t) => [0, 1].map((i) => (1 - t) ** 2 * p0[i] + 2 * (1 - t) * t * p1[i] + t * t * p2[i])
const ramp = (keys, x) => {                  // straight lines between [x, y] keyframes
  if (x <= keys[0][0]) return keys[0][1]
  for (let i = 1; i < keys.length; i++) {
    if (x <= keys[i][0]) return keys[i - 1][1] + ((x - keys[i - 1][0]) / (keys[i][0] - keys[i - 1][0])) * (keys[i][1] - keys[i - 1][1])
  }
  return keys[keys.length - 1][1]
}

// One leg of the path sampled at even distances, so the storm moves at a steady speed along it.
function leg(p0, p1, p2, hours, from) {
  const raw = Array.from({ length: 121 }, (_, i) => bezier(p0, p1, p2, i / 120))
  const dist = [0]
  for (let i = 1; i < raw.length; i++) dist.push(dist[i - 1] + km(raw[i - 1], raw[i]))
  return raw.map((pos, i) => ({ pos, h: from + hours * (dist[i] / dist[dist.length - 1]) }))
}

export function makeTrack(seed, allClearIso) {
  const r = random(seed)
  const landfall = [14.25 + r() * 0.8, 121.1 + r() * 0.5]
  const start = [9.5 + r() * 3.5, 136.5 + r() * 3]
  const end = [15.8 + r() * 3.2, 109.5 + r() * 2.5]
  const bend = [(start[0] + landfall[0]) / 2 + (r() - 0.5) * 2.6, (start[1] + landfall[1]) / 2]
  const carry = [landfall[0] + (landfall[0] - bend[0]) * 0.5 + (r() - 0.35) * 1.2, landfall[1] + (landfall[1] - bend[1]) * 0.5]
  const before = 60 + Math.round(r() * 12)          // hours from the first point to landfall
  const after = 46                                  // hours from landfall to the last point
  const peak = 135 + r() * 70                       // strongest winds, km/h
  const path = [...leg(start, bend, landfall, before, -before), ...leg(landfall, carry, end, after, 0).slice(1)]

  const at = (h) => {
    const x = Math.min(Math.max(h, -before), after)
    let i = path.findIndex((p) => p.h >= x)
    if (i <= 0) i = 1
    const a = path[i - 1]
    const b = path[i]
    const t = (x - a.h) / (b.h - a.h || 1)
    return { pos: [a.pos[0] + (b.pos[0] - a.pos[0]) * t, a.pos[1] + (b.pos[1] - a.pos[1]) * t], heading: bearing(a.pos, b.pos) }
  }
  // Strengthens over warm sea, peaks just before landfall, weakens crossing Luzon, recovers a little after.
  const wind = (h) => ramp([[-before, 50], [-before * 0.55, 85], [-18, peak * 0.9], [-4, peak], [3, peak * 0.82], [12, peak * 0.7], [after, peak * 0.85]], h)
  const clear = new Date(allClearIso).getTime()
  const timeAt = (h) => new Date(clear + (h - CLEAR_H) * 3600e3)

  // Forecast points at 8 AM and 8 PM, Philippine time.
  const points = []
  for (let h = Math.ceil(-before); h <= after; h++) {
    const hour = (Math.round(timeAt(h).getTime() / 3600e3) % 24 + 8) % 24
    if (hour === 8 || hour === 20) points.push({ h, pos: at(h).pos, kmh: Math.round(wind(h) / 5) * 5, cat: category(wind(h)), time: timeAt(h) })
  }

  // The area the center may pass through from hour `from` on: narrow now, wider further ahead.
  const cone = (from) => {
    const left = []
    const right = []
    const span = Math.max(after - from, 1)
    for (let h = from; h <= after + 0.01; h += 1.5) {
      const { pos, heading } = at(h)
      const radius = 18 + 250 * ((h - from) / span) ** 0.85 * Math.min(span / 60, 1)
      left.push(offset(pos, heading - 90, radius))
      right.push(offset(pos, heading + 90, radius))
    }
    const tip = at(after)
    const radius = 18 + 250 * Math.min(span / 60, 1)
    const cap = Array.from({ length: 9 }, (_, i) => offset(tip.pos, tip.heading - 90 + (i + 1) * 18, radius))
    return [...left, ...cap, ...right.reverse()]
  }

  return { seed, path, points, before, after, landfall, at, wind, timeAt, cone }
}

const WHEN = { weekday: 'short', hour: 'numeric', timeZone: 'Asia/Manila' }
// "8 AM Tue"
export const when = (date) => {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-PH', WHEN).formatToParts(date).map((p) => [p.type, p.value]))
  return `${parts.hour} ${(parts.dayPeriod || '').toUpperCase()} ${parts.weekday}`.replace(/\s+/g, ' ').trim()
}
