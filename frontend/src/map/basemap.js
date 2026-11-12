import L from 'leaflet'
import '@maplibre/maplibre-gl-leaflet'
import GoogleMutant from 'leaflet.gridlayer.googlemutant'

// Real Google Maps when a key is configured (frontend/.env.local, never committed):
//   VITE_GOOGLE_MAPS_API_KEY=your-key
// Otherwise a free OpenStreetMap basemap recoloured to Google's palette.
export const GOOGLE_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || ''

const FREE_STYLE = 'https://tiles.openfreemap.org/styles/liberty'
const FREE_ATTRIBUTION = '<a href="https://openfreemap.org">OpenFreeMap</a> © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'

// Google Maps exactly as people know it, minus the clutter that competes with outage pins:
// business and landmark icons, transit stations and road-number shields. Colours untouched.
const CLEAN = [
  { featureType: 'poi', elementType: 'labels', stylers: [{ visibility: 'off' }] },
  { featureType: 'poi.business', stylers: [{ visibility: 'off' }] },
  { featureType: 'transit.station', stylers: [{ visibility: 'off' }] },
  { featureType: 'road', elementType: 'labels.icon', stylers: [{ visibility: 'off' }] },
]

let googleLoading = null
function loadGoogle(key) {
  if (window.google?.maps?.Map) return Promise.resolve()
  if (googleLoading) return googleLoading
  googleLoading = new Promise((resolve, reject) => {
    window.__firstlookGoogleReady = () => resolve()
    const s = document.createElement('script')
    s.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&v=weekly&callback=__firstlookGoogleReady`
    s.async = true
    s.onerror = () => reject(new Error('Google Maps did not load'))
    document.head.appendChild(s)
    setTimeout(() => reject(new Error('Google Maps timed out')), 10000)
  })
  return googleLoading
}

// Free fallback: Google's familiar palette. First matching rule wins, and a rule only
// touches paint keys that fit the layer type.
const PAINT = [
  [/^background$/, { 'background-color': '#F5F5F3' }],
  [/^park$/, { 'fill-color': '#CDEBD3', 'fill-opacity': 0.95, 'fill-outline-color': '#CDEBD3' }],
  [/^landcover_(wood|grass)$/, { 'fill-color': '#D3ECD7', 'fill-opacity': 0.6 }],
  [/^landuse_residential$/, { 'fill-color': '#EEEEEB' }],
  [/^landuse_hospital$/, { 'fill-color': '#FBE4E2' }],
  [/^water$/, { 'fill-color': '#AADAFF' }],
  [/^waterway_(tunnel|river|other)$/, { 'line-color': '#AADAFF' }],
  [/^building$/, { 'fill-color': '#E8E8E5', 'fill-outline-color': '#DEDEDB' }],
  [/_motorway(_link)?_casing$/, { 'line-color': '#E7B547' }],
  [/_motorway(_link)?$/, { 'line-color': '#FBD571' }],
  [/_casing$/, { 'line-color': '#D9DBDE' }],
  [/_(trunk_primary|secondary_tertiary|link|minor|street|service_track)$/, { 'line-color': '#FFFFFF' }],
  [/^highway-name/, { 'text-color': '#5F6368', 'text-halo-color': '#FFFFFF', 'text-halo-width': 1.2 }],
  [/^water_name|^waterway_line_label/, { 'text-color': '#3F72AF' }],
  [/^label_/, { 'text-color': '#3C4043', 'text-halo-color': '#FFFFFF', 'text-halo-width': 1.5 }],
]
const ALWAYS_HIDE = /^(building-3d|natural_earth|road_one_way)/
const CLEAN_HIDE = /^(poi_|airport$|highway-shield|road_shield)/
const PREFIX = { fill: 'fill-', line: 'line-', symbol: 'text-', background: 'background-' }

let freeBase = null
async function googleLikeStyle(clean) {
  if (!freeBase) {
    const style = await (await fetch(FREE_STYLE)).json()
    style.layers = style.layers.filter((l) => !ALWAYS_HIDE.test(l.id)).map((l) => {
      const rule = PAINT.find(([re]) => re.test(l.id))
      if (!rule || !PREFIX[l.type]) return l
      const paint = Object.fromEntries(Object.entries(rule[1]).filter(([k]) => k.startsWith(PREFIX[l.type])))
      return { ...l, paint: { ...l.paint, ...paint } }
    })
    freeBase = style
  }
  return clean ? { ...freeBase, layers: freeBase.layers.filter((l) => !CLEAN_HIDE.test(l.id)) } : freeBase
}

// Adds the basemap to a Leaflet map. `clean` hides landmarks; setClean() switches live.
export function addBasemap(map, onKind, clean = true) {
  let layer = null
  let done = false
  let kind = GOOGLE_KEY ? 'google' : 'free'
  let current = clean

  const swap = (next, k) => {
    if (done) return
    if (layer) map.removeLayer(layer)
    layer = next.addTo(map)
    layer.bringToBack?.()
    kind = k
    onKind?.(k)
  }
  const free = () => googleLikeStyle(current)
    .then((style) => swap(L.maplibreGL({ style, attribution: FREE_ATTRIBUTION }), 'free'))
    .catch(() => swap(L.maplibreGL({ style: FREE_STYLE, attribution: FREE_ATTRIBUTION }), 'free'))
  const google = () => loadGoogle(GOOGLE_KEY)
    .then(() => swap(new GoogleMutant({ type: 'roadmap', styles: current ? CLEAN : [], maxZoom: 20 }), 'google'))
    .catch(free)

  if (GOOGLE_KEY) {
    window.gm_authFailure = () => free()   // bad or restricted key: fall back quietly
    google()
  } else {
    free()
  }
  return {
    setClean(next) {
      if (next === current) return
      current = next
      if (kind === 'google') google()
      else free()
    },
    remove() { done = true; if (layer) map.removeLayer(layer) },
  }
}
