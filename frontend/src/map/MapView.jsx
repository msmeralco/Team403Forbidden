import { useEffect, useMemo, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet.markercluster'
import { MapContainer, Marker, Polyline, Tooltip, ZoomControl, useMap } from 'react-leaflet'
import { addBasemap } from './basemap'
import { TIERS, areaTier, tierRank } from '../theme'
import { svg } from '../icons'

const BLUE = '#0B57D0'

function Basemap({ onKind, clean }) {
  const map = useMap()
  const ctrl = useRef(null)
  useEffect(() => {
    ctrl.current = addBasemap(map, onKind, clean)
    return () => ctrl.current.remove()
  }, [map]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { ctrl.current?.setClean(clean) }, [clean])
  return null
}

// Frame the whole storm area beside the panel once, then follow the selection.
function Camera({ bounds, focus, padLeft, mobile }) {
  const map = useMap()
  const first = useRef(true)
  useEffect(() => {
    const pad = mobile ? { paddingTopLeft: [20, 120], paddingBottomRight: [20, window.innerHeight * 0.45] }
      : { paddingTopLeft: [padLeft + 30, 90], paddingBottomRight: [40, 40] }
    if (first.current) {
      first.current = false
      map.fitBounds(bounds, pad)
      return
    }
    if (!focus) return
    if (focus.bounds) map.flyToBounds(focus.bounds, { ...pad, maxZoom: 13.5, duration: 0.8 })
    else if (focus.pos) {
      const z = Math.max(map.getZoom(), focus.zoom ?? 14)
      const target = map.project(focus.pos, z).subtract([mobile ? 0 : padLeft / 2, mobile ? -window.innerHeight * 0.2 : 0])
      map.flyTo(map.unproject(target, z), z, { duration: 0.8 })
    }
  }, [map, focus?.key]) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

const pinHtml = (tier, people, opts = {}) => {
  const glyph = tier === 'unknown' ? '?' : tier === 'restored' ? '✓' : tier === 'ok' ? '' : '!'
  const tab = people ? `<span class="pin-tab">${svg.people}${people}</span>` : ''
  return `<div class="pin t-${tier}${opts.sel ? ' sel' : ''}${opts.dim ? ' dim' : ''}${opts.lit ? ' lit' : ''}">
    <svg class="pin-shape" viewBox="0 0 32 40" aria-hidden="true"><path d="M16 39C16 39 29 26.6 29 16A13 13 0 0 0 3 16C3 26.6 16 39 16 39Z"/></svg>
    <b>${glyph}</b>${tab}</div>`
}

const clusterIcon = (cluster) => {
  const kids = cluster.getAllChildMarkers()
  const tier = kids.map((m) => m.options.tier).sort((a, b) => tierRank(a) - tierRank(b))[0]
  const people = kids.reduce((s, m) => s + (m.options.people || 0), 0)
  return L.divIcon({
    className: '', iconSize: [46, 46], iconAnchor: [23, 23],
    html: `<div class="cluster t-${tier}"><b>${kids.length}</b><span>areas</span>${people ? `<em>${svg.people}${people}</em>` : ''}</div>`,
  })
}

// Barangay pins, grouped into numbered bubbles when zoomed out.
function AreaPins({ areas, selectedArea, lit, showOk, onSelect }) {
  const map = useMap()
  const select = useRef(onSelect)
  select.current = onSelect
  const group = useMemo(() => L.markerClusterGroup({
    showCoverageOnHover: false, spiderfyOnMaxZoom: false, maxClusterRadius: 56,
    disableClusteringAtZoom: 12, iconCreateFunction: clusterIcon,
  }), [])
  useEffect(() => { map.addLayer(group); return () => { map.removeLayer(group) } }, [map, group])

  const key = JSON.stringify([areas.map((a) => [a.id, areaTier(a), a.people]), selectedArea, lit && [...lit], showOk])
  useEffect(() => {
    group.clearLayers()
    // "Power likely on" pins only matter up close; from far away they are noise.
    const visible = (a, t) => t && (t !== 'ok' || showOk || a.id === selectedArea)
    const markers = areas.map((a) => [a, areaTier(a)]).filter(([a, t]) => visible(a, t)).map(([a, tier]) => {
      const sel = a.id === selectedArea
      const m = L.marker(a.pos, {
        tier, people: a.people, keyboard: true, title: `Brgy. ${a.barangay}, ${a.city}: ${TIERS[tier].label}`,
        zIndexOffset: sel ? 1000 : (10 - tierRank(tier)) * 20,
        icon: L.divIcon({
          className: '', iconSize: [32, 40], iconAnchor: [16, 39],
          html: pinHtml(tier, a.people, { sel, lit: lit?.has(a.id), dim: lit && !lit.has(a.id) && !sel }),
        }),
      })
      m.on('click', () => select.current(a.id))
      return m
    })
    group.addLayers(markers)
  }, [group, key]) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

const reportIcon = (r, sel) => L.divIcon({
  className: '', iconSize: [22, 22], iconAnchor: [11, 11],
  html: `<div class="rdot s-${r.source}${r.category === 'hazard' ? ' hz' : ''}${sel ? ' sel' : ''}">${svg.source[r.source]}</div>`,
})
// Where the suggested route starts: the nearest Meralco office.
const officeIcon = (name) => L.divIcon({
  className: '', iconSize: [120, 26], iconAnchor: [13, 13],
  html: `<div class="office-mk"><i>M</i><span>${name}</span></div>`,
})
const targetIcon = L.divIcon({
  className: '', iconSize: [120, 34], iconAnchor: [17, 17],
  html: `<div class="target-mk"><i>${svg.target}</i><span>Check here</span></div>`,
})
// Drawn just left of the barangay pin so it never covers the pin's count tab.
const siteIcon = L.divIcon({ className: '', iconSize: [20, 20], iconAnchor: [36, 30], html: `<div class="site-mk">${svg.hospital}</div>` })
const closedIcon = L.divIcon({ className: '', iconSize: [20, 20], iconAnchor: [10, 10], html: `<div class="closed-mk">${svg.closed}</div>` })
const mid = (r) => [(r.a[0] + r.b[0]) / 2, (r.a[1] + r.b[1]) / 2]

function useZoom() {
  const map = useMap()
  const [zoom, setZoom] = useState(map.getZoom())
  useEffect(() => {
    const update = () => setZoom(map.getZoom())
    map.on('zoomend', update)
    return () => { map.off('zoomend', update) }
  }, [map])
  return zoom
}

function Cased({ positions, color, weight, dash }) {
  return (
    <>
      <Polyline positions={positions} interactive={false} pathOptions={{ color: '#fff', weight: weight + 4, opacity: 0.95, lineCap: 'round' }} />
      <Polyline positions={positions} interactive={false} pathOptions={{ color, weight, dashArray: dash, lineCap: 'round' }} />
    </>
  )
}

// Everything drawn over the basemap. Detail appears as you zoom in, so the zoomed-out
// view stays readable: barangay pins only.
function Overlays({ state, reports, sel, layers, onSelectArea, onSelectReport, onToggleRoad }) {
  const zoom = useZoom()
  const close = zoom >= 12
  const rec = sel?.kind === 'priority' ? state.recommendations.find((r) => r.asset_id === sel.id) : null
  const target = sel?.kind === 'priority' ? state.assets.find((a) => a.id === sel.id) : null
  const lit = rec ? new Set(rec.covers.areas.map((a) => a.id)) : null
  const report = sel?.kind === 'report' ? reports.find((r) => r.id === sel.id) : null
  const areaId = sel?.kind === 'area' ? sel.id : report?.area_id
  const dots = areaId ? reports.filter((r) => r.area_id === areaId) : []
  const sites = state.areas.filter((a) => a.critical.length && a.p_out >= 0.5)
  const closed = state.roads.filter((r) => r.blocked)

  return (
    <>
      {layers.roads && state.roads.filter((r) => !r.blocked).map((r) => (
        <Polyline key={`open-${r.id}`} positions={[r.a, r.b]} eventHandlers={{ click: () => onToggleRoad(r) }}
          pathOptions={{ color: '#5F6368', weight: 9, opacity: 0.22, lineCap: 'round', className: 'road-hit' }}>
          <Tooltip sticky>{r.name}: open. Click to mark it closed.</Tooltip>
        </Polyline>
      ))}
      {closed.map((r) => (
        <Polyline key={`closed-${r.id}`} positions={[r.a, r.b]} eventHandlers={{ click: () => onToggleRoad(r) }}
          pathOptions={{ color: '#C5221F', weight: close ? 5 : 3.5, opacity: 0.8, lineCap: 'round', dashArray: '1 8', className: 'road-hit' }}>
          <Tooltip sticky>{r.name}: closed{layers.roads ? '. Click to reopen.' : ''}</Tooltip>
        </Polyline>
      ))}
      {close && closed.map((r) => <Marker key={`cm-${r.id}`} position={mid(r)} icon={closedIcon} interactive={false} />)}

      {rec && <Cased key={`pv-${rec.asset_id}-${rec.route.km}`} positions={rec.route.points} color={BLUE} weight={4} dash="1 9" />}

      {layers.critical && close && sites.map((a) => (
        <Marker key={`site-${a.id}`} position={a.pos} icon={siteIcon}>
          <Tooltip direction="top" offset={[0, -8]}>{a.critical.join(', ')}, Brgy. {a.barangay}</Tooltip>
        </Marker>
      ))}

      {layers.reports && <AreaPins areas={state.areas} selectedArea={areaId} lit={lit} showOk={close} onSelect={onSelectArea} />}

      {dots.map((r) => (
        <Marker key={r.id} position={r.pos} icon={reportIcon(r, r.id === report?.id)} zIndexOffset={r.id === report?.id ? 2000 : -1000}
          eventHandlers={{ click: () => onSelectReport(r.id) }} />
      ))}

      {target && <Marker position={target.pos} icon={targetIcon} zIndexOffset={1500} interactive={false} />}
      {rec && <Marker position={rec.route.points[0]} icon={officeIcon(rec.from)} zIndexOffset={1400} interactive={false} />}
    </>
  )
}

export default function MapView({ state, reports, sel, layers, focus, padLeft, mobile, onSelectArea, onSelectReport, onToggleRoad, onBasemap }) {
  const bounds = useMemo(() => L.latLngBounds([...state.areas.map((a) => a.pos), ...state.assets.map((a) => a.pos)]), []) // eslint-disable-line
  return (
    <div className="map">
      <MapContainer bounds={bounds} zoomSnap={0.25} minZoom={8} maxZoom={19} scrollWheelZoom zoomControl={false}>
        <Basemap onKind={onBasemap} clean={!layers.landmarks} />
        <Camera bounds={bounds} focus={focus} padLeft={padLeft} mobile={mobile} />
        {!mobile && <ZoomControl position="bottomright" />}
        <Overlays state={state} reports={reports} sel={sel} layers={layers}
          onSelectArea={onSelectArea} onSelectReport={onSelectReport} onToggleRoad={onToggleRoad} />
      </MapContainer>
    </div>
  )
}
