// The road route from a Meralco office to a pole.
// With a Google Maps key this is Google's own driving directions (the Routes library first, then
// the older Directions service, whichever the key allows). Without one, or if Google refuses, the
// public OpenStreetMap router (OSRM) is asked. If nothing answers, null: a straight line is drawn.
// Only the path is used. The ETA shown in the app is always the one given in the case.

const cache = new Map()
const off = { routes: false, directions: false, osrm: false }      // a service that refused once is not asked again
const point = (p) => ({ lat: p[0], lng: p[1] })
const number = (v) => (typeof v === 'function' ? v() : v)
const pairs = (path) => path.map((p) => [number(p.lat), number(p.lng)])

async function googleRoutes(from, to) {
  const maps = window.google?.maps
  if (off.routes || !maps?.importLibrary) return null
  try {
    const { Route } = await maps.importLibrary('routes')
    if (!Route?.computeRoutes) { off.routes = true; return null }
    const { routes } = await Route.computeRoutes({ origin: point(from), destination: point(to), travelMode: 'DRIVING', fields: ['path'] })
    const path = routes?.[0]?.path
    return path?.length > 1 ? { points: pairs(path), by: 'google' } : null
  } catch {
    off.routes = true
    return null
  }
}

async function googleDirections(from, to) {
  const maps = window.google?.maps
  if (off.directions || !maps?.DirectionsService) return null
  try {
    const found = await new maps.DirectionsService().route({ origin: point(from), destination: point(to), travelMode: 'DRIVING' })
    const path = found?.routes?.[0]?.overview_path
    return path?.length > 1 ? { points: pairs(path), by: 'google' } : null
  } catch {
    off.directions = true
    return null
  }
}

async function osrm(from, to) {
  if (off.osrm) return null
  const stop = new AbortController()
  const timer = setTimeout(() => stop.abort(), 6000)
  try {
    const res = await fetch(`https://router.project-osrm.org/route/v1/driving/${from[1]},${from[0]};${to[1]},${to[0]}?overview=full&geometries=geojson`, { signal: stop.signal })
    if (!res.ok) throw new Error(String(res.status))
    const line = (await res.json()).routes?.[0]?.geometry?.coordinates
    return line?.length > 1 ? { points: line.map(([lon, lat]) => [lat, lon]), by: 'osm' } : null
  } catch {
    off.osrm = true
    return null
  } finally {
    clearTimeout(timer)
  }
}

// Resolves to { points: [[lat, lon], ...], by: 'google' | 'osm' }, or null when no road route was found.
export function directions(from, to) {
  const key = [...from, ...to].map((n) => n.toFixed(5)).join(',')
  if (!cache.has(key)) {
    cache.set(key, (async () => (await googleRoutes(from, to)) ?? (await googleDirections(from, to)) ?? (await osrm(from, to)))()
      .then((found) => { if (!found) cache.delete(key); return found }))
  }
  return cache.get(key)
}
