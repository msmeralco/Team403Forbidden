// The power network, drawn the way it is built: substation, lines, transformers, and the kWh meters
// in the houses of each barangay.
//
//   - With the "Meralco grid" chip on, the whole network is drawn.
//   - Whenever a barangay pin or a place is opened, the part of the network tied to it is drawn and
//     picked out: for a barangay, the path that feeds it; for a place, everything it feeds.
//     Equipment that is worth checking carries its number on the list.
//
// The network is the exercise's own (20 pieces of equipment, a sample of meters per barangay).
// Lines follow real roads where a road path was fetched (scripts/fetch_network_routes.py).
// The "Meralco offices" chip is separate: offices as mapped on OpenStreetMap.
import { useEffect, useMemo, useState } from 'react'
import L from 'leaflet'
import { useMap } from 'react-leaflet'
import { LEVEL, METERS, clip, km, meterBlock, trace as traceOf } from './network'

const LINE = '#00695C'
const PICKED = '#111827'
export const NETWORK_NOTE = `Simulated network. ${METERS} meters per barangay are a sample.`
export const OFFICE_NOTE = "Offices as mapped by OpenStreetMap volunteers, not Meralco's own list."
const CREDIT = 'Line paths and offices © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors'
const METER_ZOOM = 14.5
const WIDTH = { segment: 4.2, switch: 4.2, pole: 4.2, lateral: 3.2, transformer: 2.6 }

const GLYPH = {
  substation: '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20V8l8-4 8 4v12"/><path d="M13 9.5 9.5 14h5L11 18.5"/></svg>',
  transformer: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.3"><circle cx="9" cy="12" r="5.2"/><circle cx="15" cy="12" r="5.2"/></svg>',
  switch: '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"><path d="M3 15h5M16 15h5M8 15l8-7"/></svg>',
  pole: '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round"><path d="M12 4v17M6 8h12"/></svg>',
  line: '<svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M4 12h16"/></svg>',
  office: '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 21V5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v16M15 10h3a1 1 0 0 1 1 1v10M3 21h18"/><path d="M8.5 8h3M8.5 12h3M8.5 16h3"/></svg>',
}
const SHAPE = { segment: 'line', lateral: 'line', switch: 'switch', pole: 'pole', transformer: 'transformer' }
const officeIcon = L.divIcon({ className: '', iconSize: [22, 22], iconAnchor: [11, 11], html: `<div class="grid-office">${GLYPH.office}</div>` })

const files = {}
const load = (name) => {
  files[name] ??= fetch(`${import.meta.env.BASE_URL}grid/${name}`)
    .then((res) => { if (!res.ok) throw new Error(`${name}: ${res.status}`); return res.json() })
    .catch((error) => { delete files[name]; throw error })
  return files[name]
}

// Tooltip text built as DOM nodes: names are never treated as HTML.
const label = (title, detail) => {
  const el = document.createElement('div')
  const strong = document.createElement('strong')
  strong.textContent = title
  el.append(strong)
  if (detail) el.append(document.createElement('br'), detail)
  return el
}

function equipmentIcon(asset, rec, status, picked, selected) {
  const shape = SHAPE[asset.type]
  const big = shape === 'transformer'
  const size = big ? 26 : shape === 'line' ? 18 : 20
  const rank = rec && rec.tier !== 'low' ? `<b class="eq-rank t-${rec.tier}">${rec.rank}</b>` : ''
  return L.divIcon({
    className: '', iconSize: [size, size], iconAnchor: [size / 2, size / 2],
    html: `<div class="eq eq-${shape} is-${status}${picked ? ' picked' : ''}${selected ? ' selected' : ''}">${GLYPH[shape]}${rank}</div>`,
  })
}

// zoneKm: when a barangay is open, only what lies within this many km of it is drawn (null = its whole supply path).
export default function GridLayer({ state, sel, show, offices, zoneKm, onSelectAsset, onSelectArea, onError }) {
  const map = useMap()
  const [routes, setRoutes] = useState(null)        // road paths for the lines; null until loaded, {} if there are none
  const [places, setPlaces] = useState(null)        // office locations
  const [near, setNear] = useState(() => map.getZoom() >= METER_ZOOM)
  const picked = useMemo(() => traceOf(state, sel), [state, sel?.kind, sel?.id]) // eslint-disable-line react-hooks/exhaustive-deps
  const drawing = show || Boolean(picked)

  useEffect(() => {
    const update = () => setNear(map.getZoom() >= METER_ZOOM)
    map.on('zoomend', update)
    return () => { map.off('zoomend', update) }
  }, [map])
  useEffect(() => {
    if (!drawing || routes) return
    load('network-routes.json').then((d) => setRoutes(d.routes ?? {})).catch(() => setRoutes({}))      // no file: straight lines
  }, [drawing, routes])
  useEffect(() => {
    if (!offices || places) return
    load('meralco-osm.json').then((d) => setPlaces(d.offices ?? [])).catch(() => onError?.('The list of Meralco offices could not be loaded.'))
  }, [offices, places]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!(drawing || offices) || !map.attributionControl) return undefined
    map.attributionControl.addAttribution(CREDIT)
    return () => { map.attributionControl.removeAttribution(CREDIT) }
  }, [map, drawing, offices])

  // Redraw only when something that shows has changed.
  const version = JSON.stringify([
    state.event.id, show, near, sel?.kind, sel?.id, zoneKm, Boolean(routes),
    state.assets.map((a) => a.status), state.repaired.map((x) => x.asset_id),
    state.recommendations.map((r) => [r.asset_id, r.rank, r.tier]),
    state.areas.map((a) => [a.people, a.p_out >= 0.5, a.restored]),
  ])
  useEffect(() => {
    if (!drawing || !routes) return undefined
    if (!map.getPane('grid')) map.createPane('grid').style.zIndex = 350      // above the basemap, under pins and routes
    const renderer = L.canvas({ pane: 'grid', padding: 0.3, tolerance: 4 })
    const group = L.layerGroup().addTo(map)
    const base = { renderer, pane: 'grid', lineCap: 'round', lineJoin: 'round' }
    const pos = new Map(state.assets.map((a) => [a.id, a.pos]))
    pos.set('SUB', state.substation.pos)
    const recs = new Map(state.recommendations.map((r) => [r.asset_id, r]))
    const fixed = new Set(state.repaired.map((x) => x.asset_id))
    const path = (from, to, a, b) => {
      const flat = routes[`${from}>${to}`]
      if (!flat) return [a, b]
      const points = []
      for (let i = 0; i < flat.length; i += 2) points.push([flat[i], flat[i + 1]])
      return points
    }
    // The zone around an opened case: a circle. Inside it everything is drawn; outside, nothing
    // (or, with the whole network switched on, a faded backdrop).
    const zoneArea = sel?.kind === 'area' && zoneKm ? state.areas.find((a) => a.id === sel.id) : null
    const zone = zoneArea ? { center: zoneArea.pos, km: zoneKm } : null
    const inside = (p) => km(p, zone.center) <= zone.km
    const DIM = 0.2
    const stroke = (points, width, on, title, click, dim) => {
      const opacity = dim ? DIM : 1
      L.polyline(points, { ...base, color: '#fff', weight: width + 3, opacity: 0.9 * opacity, interactive: false }).addTo(group)
      const drawn = L.polyline(points, { ...base, color: picked && on && !dim ? PICKED : LINE, weight: width, opacity, interactive: Boolean(click) || Boolean(title) }).addTo(group)
      if (title) drawn.bindTooltip(title, { sticky: true })
      if (click) drawn.on('click', click)
    }
    const line = (points, width, on, title, click) => {
      if (zone) {
        if (show) stroke(points, width, false, null, null, true)
        clip(points, zone.center, zone.km).forEach((part) => stroke(part, width, on, title, click, false))
      } else if (show || on) stroke(points, width, on, title, click, Boolean(picked) && !on)
    }
    // How strongly to draw something at `p`: 1 = full, DIM = backdrop, 0 = not at all.
    const weightAt = (p, on) => (zone ? (inside(p) ? 1 : show ? DIM : 0) : show || on ? (picked && !on ? DIM : 1) : 0)
    if (zone) {
      L.circle(zone.center, { ...base, radius: zone.km * 1000, color: PICKED, weight: 1.6, dashArray: '7 7', fillColor: PICKED, fillOpacity: 0.045, interactive: false }).addTo(group)
      L.marker([zone.center[0] + zone.km / 110.574, zone.center[1]], {
        icon: L.divIcon({ className: '', iconSize: [0, 0], html: `<span class="zone-label">${zone.km} km zone</span>` }), interactive: false, keyboard: false,
      }).addTo(group)
    }

    // Lines between equipment.
    state.assets.forEach((a) => {
      line(path(a.parent, a.id, pos.get(a.parent), a.pos), WIDTH[a.type], Boolean(picked?.assets.has(a.id)),
        a.type === 'transformer' ? `Line to ${a.name}` : a.name, () => onSelectAsset(a.id))
    })

    // From each transformer to its barangays, and the houses there.
    state.areas.forEach((area) => {
      const on = Boolean(picked?.areas.has(area.id))
      const fade = weightAt(area.pos, on)
      const dark = area.p_out >= 0.5 && !area.restored
      line(path(area.transformer, area.id, pos.get(area.transformer), area.pos), 1.8, on, null, null)
      if (!fade || (!on && !near)) return
      const block = meterBlock(area)
      const wire = dark ? '#80868B' : LINE
      L.polyline(block.backbone, { ...base, color: wire, weight: 2, opacity: fade, dashArray: dark ? '5 5' : null, interactive: false }).addTo(group)
      block.poles.forEach((p) => L.circleMarker(p, { ...base, radius: 2.4, stroke: false, fillColor: wire, fillOpacity: fade, interactive: false }).addTo(group))
      block.houses.forEach((h) => {
        L.polyline([h.pole, h.meter], { ...base, color: wire, weight: 1, opacity: 0.8 * fade, interactive: false }).addTo(group)
        L.polygon(h.corners, { ...base, color: '#9AA0A6', weight: 1, opacity: fade, fillColor: '#fff', fillOpacity: 0.95 * fade, interactive: false }).addTo(group)
        const state_ = h.reported && !area.restored ? 'reported' : dark ? 'dark' : 'on'
        L.circleMarker(h.meter, {
          ...base, radius: state_ === 'reported' ? 4 : 3.2, weight: 1.6, opacity: fade, fillOpacity: fade,
          color: state_ === 'on' ? '#fff' : state_ === 'dark' ? '#5F6368' : '#fff',
          fillColor: state_ === 'on' ? '#00897B' : state_ === 'dark' ? '#fff' : '#202124',
        }).bindTooltip(label(`kWh meter, Brgy. ${area.barangay}`, state_ === 'reported' ? 'This household reported no power' : state_ === 'dark' ? 'Likely without power, no report' : 'Has power'), { direction: 'top' })
          .on('click', () => onSelectArea(area.id)).addTo(group)
      })
    })

    // Equipment, with its number on the list where it is worth checking.
    state.assets.forEach((a) => {
      const on = Boolean(picked?.assets.has(a.id))
      const fade = weightAt(a.pos, on)
      if (!fade) return
      const rec = recs.get(a.id)
      const status = fixed.has(a.id) ? 'repaired' : a.status === 'damaged' ? 'found' : a.status === 'intact' ? 'clear' : 'live'
      const detail = status === 'repaired' ? 'Repaired' : status === 'found' ? 'Damage found, waiting for repair' : status === 'clear' ? 'Checked, no damage'
        : rec && rec.tier !== 'low' ? `Number ${rec.rank} on the list. ${LEVEL[a.type]}` : LEVEL[a.type]
      L.marker(a.pos, { icon: equipmentIcon(a, rec, status, on && fade === 1, sel?.kind === 'priority' && sel.id === a.id), opacity: fade, zIndexOffset: on ? 300 : -300, keyboard: false })
        .bindTooltip(label(a.name, detail), { direction: 'top', offset: [0, -10] })
        .on('click', () => onSelectAsset(a.id)).addTo(group)
    })
    const atSource = weightAt(state.substation.pos, Boolean(picked))
    if (atSource) L.marker(state.substation.pos, {
      icon: L.divIcon({ className: '', iconSize: [32, 32], iconAnchor: [16, 16], html: `<div class="eq eq-substation${picked && atSource === 1 ? ' picked' : ''}">${GLYPH.substation}</div>` }),
      opacity: atSource, zIndexOffset: 350, keyboard: false,
    }).bindTooltip(label(state.substation.name, 'Substation: everything here is fed from this point'), { direction: 'top', offset: [0, -14] }).addTo(group)

    return () => { map.removeLayer(group); renderer.remove() }
  }, [map, version, drawing, routes]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!offices || !places) return undefined
    const group = L.layerGroup(places.map((o) => L.marker([o.lat, o.lon], { icon: officeIcon, zIndexOffset: -500, keyboard: false })
      .bindTooltip(label(o.name, o.city), { direction: 'top', offset: [0, -10] }))).addTo(map)
    return () => { map.removeLayer(group) }
  }, [map, offices, places])

  return null
}
