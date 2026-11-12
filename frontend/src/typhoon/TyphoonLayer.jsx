// Draws the simulated typhoon on the map and, when told to run, moves it along its track.
// Before the run it shows the forecast: the whole track, the points every 12 hours and the cone.
// During the run the eye travels the track; when the storm has passed Metro Manila the map
// flies back to the service area and onDone is called. Leaflet is driven directly, so the
// animation never re-renders React.
import { useEffect, useRef } from 'react'
import L from 'leaflet'
import { useMap } from 'react-leaflet'
import { CLEAR_H, METRO_MANILA, category, km, when } from './track'
import './typhoon.css'

const SECONDS = 17                       // how long the passage takes on screen
const COLOR = { td: '#5f6368', ts: '#1a73e8', sts: '#e37400', ty: '#c5221f', sty: '#7b1fa2' }
const EYE = '<svg viewBox="-12 -12 24 24" width="46" height="46"><g fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round">'
  + '<path d="M0 -5 C 7 -5.5 10.5 0 9 8"/><path d="M0 5 C -7 5.5 -10.5 0 -9 -8"/></g><circle r="5.2" fill="currentColor"/><circle r="1.8" fill="#fff"/></svg>'

const pointIcon = (p, passed) => L.divIcon({
  className: '', iconSize: [22, 22], iconAnchor: [11, 11],
  html: `<div class="ty-pt ty-${p.cat.key}${passed ? ' passed' : ''}"><b>${p.cat.letter}</b><span>${when(p.time)}</span></div>`,
})

export default function TyphoonLayer({ track, running, home, pad, onTick, onDone }) {
  const map = useMap()
  const parts = useRef(null)
  const finished = useRef(false)
  const tick = useRef(onTick)
  const done = useRef(onDone)
  const spinning = useRef(running)
  tick.current = onTick
  done.current = onDone
  spinning.current = running

  // The forecast picture.
  useEffect(() => {
    finished.current = false
    if (!map.getPane('typhoon')) map.createPane('typhoon').style.zIndex = 450
    const all = track.path.map((p) => p.pos)
    const group = L.layerGroup().addTo(map)
    const cone = L.polygon(track.cone(-track.before), { pane: 'typhoon', stroke: true, color: '#5f6368', weight: 1, dashArray: '4 5', fillColor: '#5f6368', fillOpacity: 0.13, interactive: false }).addTo(group)
    L.polyline(all, { pane: 'typhoon', color: '#3c4043', weight: 2, dashArray: '2 7', opacity: 0.85, interactive: false }).addTo(group)
    const passed = L.polyline([], { pane: 'typhoon', color: '#202124', weight: 3.5, interactive: false }).addTo(group)
    const points = track.points.map((p) => ({ p, marker: L.marker(p.pos, { icon: pointIcon(p, false), interactive: false, keyboard: false, zIndexOffset: 200 }).addTo(group), passed: false }))
    const first = track.at(-track.before)
    const reach = L.circle(first.pos, { pane: 'typhoon', radius: 150000, stroke: false, fillColor: '#5f6368', fillOpacity: 0.16, interactive: false }).addTo(group)
    const eye = L.marker(first.pos, { icon: L.divIcon({ className: '', iconSize: [46, 46], iconAnchor: [23, 23], html: `<div class="ty-eye">${EYE}</div>` }), interactive: false, keyboard: false, zIndexOffset: 900 }).addTo(group)
    parts.current = { group, cone, passed, points, reach, eye }
    map.fitBounds(L.latLngBounds(all).pad(0.08), { ...pad, animate: false })
    const place = (h) => {
      const { pos } = track.at(h)
      const kmh = track.wind(h)
      const cat = category(kmh)
      eye.setLatLng(pos)
      reach.setLatLng(pos)
      reach.setRadius((110 + kmh * 1.25) * 1000)
      reach.setStyle({ fillColor: COLOR[cat.key] })
      const el = eye.getElement()?.firstChild
      if (el) el.className = `ty-eye ty-${cat.key}${spinning.current ? ' spin' : ''}`
      return { pos, kmh, cat }
    }
    parts.current.place = place
    place(-track.before)
    return () => {
      map.getContainer().classList.remove('stormy')
      map.removeLayer(group)
      parts.current = null
      if (!finished.current) { try { map.fitBounds(home, { ...pad, animate: false }) } catch { /* the map is going away */ } }
    }
  }, [map, track]) // eslint-disable-line react-hooks/exhaustive-deps

  // The passage.
  useEffect(() => {
    if (!running || !parts.current) return undefined
    const { cone, passed, points, place } = parts.current
    const from = -track.before
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const length = (still ? 2 : SECONDS) * 1000
    const started = performance.now()
    let frame = 0
    let lastTick = 0
    let lastCone = from
    let ended = false
    const trail = []
    const finish = () => {
      if (ended) return
      ended = true
      finished.current = true
      map.getContainer().classList.remove('stormy')
      let called = false
      const call = () => { if (!called) { called = true; done.current?.() } }
      map.once('moveend', call)
      setTimeout(call, 2600)                       // in case the map was already there
      map.flyToBounds(home, { ...pad, duration: still ? 0.01 : 1.8 })
    }
    const step = (now) => {
      const t = Math.min((now - started) / length, 1)
      const h = from + (CLEAR_H - from) * t
      const { pos, kmh, cat } = place(h)
      trail.push(pos)
      passed.setLatLngs(trail)
      if (h - lastCone > 1.5 || t === 1) { lastCone = h; cone.setLatLngs(track.cone(h)) }
      points.forEach((x) => { if (!x.passed && x.p.h <= h) { x.passed = true; x.marker.setIcon(pointIcon(x.p, true)) } })
      const away = km(pos, METRO_MANILA)
      map.getContainer().classList.toggle('stormy', away < 280)
      if (now - lastTick > 120 || t === 1) {
        lastTick = now
        tick.current?.({ progress: t, time: track.timeAt(h), kmh: Math.round(kmh / 5) * 5, cat, away: Math.round(away / 10) * 10, west: pos[1] < METRO_MANILA[1] })
      }
      if (t < 1) frame = requestAnimationFrame(step)
      else finish()
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [running, map, track]) // eslint-disable-line react-hooks/exhaustive-deps

  return null
}
