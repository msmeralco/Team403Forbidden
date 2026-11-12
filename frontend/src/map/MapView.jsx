// The map: the typhoon first, then the power interruptions and, for the open one, its zone.
import { useEffect, useMemo, useRef } from 'react'
import L from 'leaflet'
import { MapContainer, ZoomControl, useMap } from 'react-leaflet'
import { addBasemap } from './basemap'
import GridLayer from './GridLayer'
import CaseLayer from './CaseLayer'
import { ZONE_KM, layout } from './cases'
import ZoneFocus from './ZoneFocus'
import RouteLayer from './RouteLayer'
import TyphoonLayer from '../typhoon/TyphoonLayer'

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

// Frame the whole service area beside the panel once, then follow what is open.
function Camera({ bounds, focus, padLeft, mobile }) {
  const map = useMap()
  const first = useRef(true)
  useEffect(() => {
    const pad = mobile ? { paddingTopLeft: [20, 120], paddingBottomRight: [20, window.innerHeight * 0.45] }
      : { paddingTopLeft: [padLeft + 30, 90], paddingBottomRight: [40, 40] }
    if (first.current) {
      first.current = false
      map.fitBounds(bounds, { ...pad, animate: false })   // no opening animation: it would finish late and undo a later view
      return
    }
    if (focus?.bounds) map.flyToBounds(focus.bounds, { ...pad, maxZoom: focus.maxZoom ?? 13.5, duration: 0.8 })
  }, [map, focus?.key]) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

export default function MapView({ state, layers, focus, padLeft, mobile, typhoon, cases, offices, openId, active, resolved, onSelectCase, onPickPole, onRoute, onBasemap, onError }) {
  const bounds = useMemo(() => L.latLngBounds([...state.areas.map((a) => a.pos), ...state.assets.map((a) => a.pos)]), []) // eslint-disable-line
  // The open interruption sits in a barangay: the network inside its zone is drawn around it.
  const index = openId ? cases.findIndex((c) => c.id === openId) : -1
  const plan = index >= 0 ? layout(cases[index], index, state.areas, offices) : null
  const zone = plan?.area ?? null
  const target = plan && active ? plan.poles.find((p) => p.job.pole_id === active)?.pos : null      // the pole the crew's route is drawn to
  const pad = mobile ? { paddingTopLeft: [20, 120], paddingBottomRight: [20, window.innerHeight * 0.45] } : { paddingTopLeft: [padLeft + 30, 90], paddingBottomRight: [40, 40] }
  return (
    <div className="map">
      <MapContainer bounds={bounds} zoomSnap={0.25} minZoom={5} maxZoom={19} scrollWheelZoom zoomControl={false}>
        <Basemap onKind={onBasemap} clean={!layers.landmarks} />
        <Camera bounds={bounds} focus={focus} padLeft={padLeft} mobile={mobile} />
        {!mobile && <ZoomControl position="bottomright" />}
        {typhoon ? (
          // Before and during the typhoon the map shows only the storm: no interruptions yet.
          <TyphoonLayer track={typhoon.track} running={typhoon.running} home={bounds} onTick={typhoon.onTick} onDone={typhoon.onDone} pad={pad} />
        ) : (
          <>
            <ZoneFocus center={plan?.center} km={ZONE_KM} />
            <GridLayer state={state} sel={zone ? { kind: 'area', id: zone.id } : null} show={layers.grid} offices={layers.offices}
              zoneKm={ZONE_KM} zoneAt={plan && !zone ? plan.center : null} plain onError={onError} />
            <RouteLayer from={target ? plan.office?.pos : null} to={target} onRoute={onRoute} />
            {layers.cases && <CaseLayer cases={cases} areas={state.areas} offices={offices} openId={openId} active={active} resolved={resolved}
              onOpen={onSelectCase} onPickPole={onPickPole} />}
          </>
        )}
      </MapContainer>
    </div>
  )
}
