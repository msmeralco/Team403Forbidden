import { useEffect, useMemo } from 'react'
import L from 'leaflet'
import '@maplibre/maplibre-gl-leaflet'
import { MapContainer, Marker, Polyline, Tooltip, ZoomControl, useMap } from 'react-leaflet'
import { pct } from './api'

const ACCENT = '#f47b20'
const INK = '#1f2328'
const STYLE_URL = 'https://tiles.openfreemap.org/styles/liberty'
const ATTRIBUTION = '<a href="https://openfreemap.org">OpenFreeMap</a> © <a href="https://openmaptiles.org">OpenMapTiles</a> · Data © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'

// Vector basemap rendered by MapLibre inside the Leaflet map.
function Basemap() {
  const map = useMap()
  useEffect(() => {
    const layer = L.maplibreGL({ style: STYLE_URL, attribution: ATTRIBUTION }).addTo(map)
    return () => { map.removeLayer(layer) }
  }, [map])
  return null
}

// Fit the network into the area not covered by the floating panels.
function Fit({ bounds, mobile, sheetOpen }) {
  const map = useMap()
  useEffect(() => {
    const el = map.getContainer()
    const fit = () => {
      map.invalidateSize()
      const w = el.clientWidth
      const h = el.clientHeight
      if (mobile) {
        map.fitBounds(bounds, { paddingTopLeft: [24, 185], paddingBottomRight: [60, sheetOpen ? h * 0.42 + 20 : 90] })
      } else if (w > 1100) {
        map.fitBounds(bounds, { paddingTopLeft: [420, 30], paddingBottomRight: [400, 50] })
      } else {
        map.fitBounds(bounds, { paddingTopLeft: [350, 30], paddingBottomRight: [330, 50] })
      }
    }
    const observer = new ResizeObserver(fit)
    observer.observe(el)
    return () => observer.disconnect()
  }, [map, bounds, mobile, sheetOpen])
  return null
}

function tone(a) {
  if (a.status !== 'uninspected') return a.status
  if (a.restricted) return 'restricted'
  return a.p_fail >= 0.2 ? 'suspect' : 'unknown'
}

function assetIcon(a, selected, top) {
  const cls = `mk ${a.type} ${tone(a)}${selected ? ' sel' : ''}${top ? ' top' : ''}`
  const reports = a.reports ? `<em>${a.reports}</em>` : ''
  return L.divIcon({
    className: '', iconSize: [18, 18], iconAnchor: [9, 9],
    html: `<div class="${cls}"><i></i><span><b>${a.id}</b>${reports}</span></div>`,
  })
}

const crewIcon = (c) => L.divIcon({
  className: '', iconSize: [30, 30], iconAnchor: [15, 15],
  html: `<div class="crew-mk">${c.name.replace('Crew ', 'C')}</div>`,
})
const subIcon = L.divIcon({
  className: '', iconSize: [22, 22], iconAnchor: [11, 11],
  html: '<div class="sub-mk"><span><b>Substation</b></span></div>',
})
const closedIcon = L.divIcon({
  className: '', iconSize: [18, 18], iconAnchor: [9, 9], html: '<div class="closed-mk"></div>',
})

const STATUS_TEXT = {
  damaged: 'Confirmed damaged', intact: 'Confirmed intact',
  inconclusive: 'Inconclusive visit', uninspected: 'Not inspected',
}
const mid = (r) => [(r.a[0] + r.b[0]) / 2, (r.a[1] + r.b[1]) / 2]

// A line with a white casing underneath, the way map apps draw routes.
function Cased({ id, positions, color, weight, dashArray }) {
  return (
    <>
      <Polyline key={`${id}-case`} positions={positions} interactive={false}
        pathOptions={{ color: '#fff', weight: weight + 4, opacity: 0.95, lineCap: 'round' }} />
      <Polyline key={`${id}-core`} positions={positions} interactive={false}
        pathOptions={{ color, weight, dashArray, lineCap: 'round' }} />
    </>
  )
}

export default function MapView({ state, selected, route, onSelect, onToggleRoad, mobile, sheetOpen }) {
  const positions = useMemo(() => Object.fromEntries(
    [[state.substation.id, state.substation.pos], ...state.assets.map((a) => [a.id, a.pos])]), [state])
  const bounds = useMemo(() => L.latLngBounds(Object.values(positions)), []) // eslint-disable-line
  const topId = state.recommendations[0]?.asset_id

  return (
    <div className="map">
      <MapContainer bounds={bounds} zoomSnap={0.25} scrollWheelZoom zoomControl={false}>
        <Basemap />
        <Fit bounds={bounds} mobile={mobile} sheetOpen={sheetOpen} />
        {!mobile && <ZoomControl position="bottomright" />}

        {state.roads.map((r) => (
          <Polyline key={`${r.id}-${r.blocked}`} positions={[r.a, r.b]}
            pathOptions={r.blocked
              ? { color: '#d93025', weight: 5, opacity: 0.9, lineCap: 'round', className: 'road' }
              : { color: '#5f6368', weight: 7, opacity: 0.1, lineCap: 'round', className: 'road' }}
            eventHandlers={{ click: () => onToggleRoad(r) }}>
            <Tooltip sticky>
              <strong>{r.name}</strong><br />
              {r.blocked ? 'Closed · click to reopen' : `${Math.round(r.minutes)} min · click to close`}
            </Tooltip>
          </Polyline>
        ))}
        {state.roads.filter((r) => r.blocked).map((r) => (
          <Marker key={`closed-${r.id}`} position={mid(r)} icon={closedIcon} interactive={false} />
        ))}

        {state.assets.map((a) => (
          <Cased key={a.id} id={`line-${a.id}`} positions={[positions[a.parent], a.pos]} color={INK} weight={2.2} />
        ))}

        {state.crews.filter((c) => c.route).map((c) => (
          <Cased key={`${c.id}-${c.asset_id}`} id={`crew-${c.id}`} positions={c.route.points} color={INK} weight={3.5} dashArray="2 9" />
        ))}
        {route && <Cased key={`${selected}-${route.km}`} id="route" positions={route.points} color={ACCENT} weight={5} />}

        <Marker position={state.substation.pos} icon={subIcon} interactive={false} />

        {state.assets.map((a) => (
          <Marker key={a.id} position={a.pos} icon={assetIcon(a, a.id === selected, a.id === topId)}
            zIndexOffset={a.id === selected ? 400 : 0}
            eventHandlers={{ click: () => onSelect(a.id) }}>
            <Tooltip direction="top" offset={[0, -12]}>
              <strong>{a.name}</strong><br />
              {a.place}<br />
              {STATUS_TEXT[a.status]}{a.restricted ? ' · restricted' : ''} · {pct(a.p_fail)} chance damaged
              {a.reports ? <><br />{a.reports} outage reports</> : null}
            </Tooltip>
          </Marker>
        ))}

        {state.crews.map((c) => (
          <Marker key={c.id} position={c.pos} icon={crewIcon(c)} zIndexOffset={600} interactive={false} />
        ))}
      </MapContainer>

      <div className="legend">
        <span><i className="lg damaged" />Damaged</span>
        <span><i className="lg intact" />Intact</span>
        <span><i className="lg suspect" />Suspected</span>
        <span><i className="lg unknown" />Not inspected</span>
        <span><i className="lg route" />Suggested route</span>
        <span><i className="lg closed" />Road closed</span>
      </div>
    </div>
  )
}
