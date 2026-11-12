// Liwa: the inspection planner. She floats over the map; click her to see the plan.
// There is nothing to type. When the picture changes, the backend retrieves the guidance that fits
// from the reference documents in its local vector database and has Claude write the plan from it
// (or keeps FirstLook's own order when Claude is not reachable).
// She advises only: she cannot dispatch, repair or send anything.
import { Component, Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import { Close } from '../icons'
import AssistantPanel from './AssistantPanel'
import { Bolt, Flat } from './Flat'
import './assistant.css'

const Scene = lazy(() => import('./Scene'))   // three.js loads only when Liwa is shown
const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), Math.max(lo, hi))

function hasWebGL() {
  try {
    const c = document.createElement('canvas')
    return Boolean(window.WebGLRenderingContext && (c.getContext('webgl2') || c.getContext('webgl')))
  } catch { return false }
}

function useMedia(query) {
  const [on, setOn] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const mq = window.matchMedia(query)
    const update = () => setOn(mq.matches)
    mq.addEventListener('change', update)
    return () => mq.removeEventListener('change', update)
  }, [query])
  return on
}

function useTabVisible() {
  const [visible, setVisible] = useState(() => document.visibilityState !== 'hidden')
  useEffect(() => {
    const update = () => setVisible(document.visibilityState !== 'hidden')
    document.addEventListener('visibilitychange', update)
    return () => document.removeEventListener('visibilitychange', update)
  }, [])
  return visible
}

function useViewport() {
  const [size, setSize] = useState({ w: window.innerWidth, h: window.innerHeight })
  useEffect(() => {
    const update = () => setSize({ w: window.innerWidth, h: window.innerHeight })
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [])
  return size
}

class SceneBoundary extends Component {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch() { this.props.onFail?.() }
  render() { return this.state.failed ? this.props.fallback : this.props.children }
}

export default function Assistant({ state, note, mobile, sheetOpen, onOpen }) {
  const still = useMedia('(prefers-reduced-motion: reduce)')
  const visible = useTabVisible()
  const view = useViewport()
  const [webgl, setWebgl] = useState(hasWebGL)
  const [status, setStatus] = useState(null)   // what is indexed, whether Claude is reachable, a short brief
  const [plan, setPlan] = useState(null)       // the inspection plan for the storm as it stands
  const [planning, setPlanning] = useState(false)
  const [error, setError] = useState(null)
  const [panel, setPanel] = useState(false)
  const [mini, setMini] = useState(false)
  const [flash, setFlash] = useState(null)     // a short pose: speaking, alert or success
  const [hover, setHover] = useState(false)
  const [spoken, setSpoken] = useState('')     // announced to screen readers
  const [place, setPlace] = useState({ right: 64, bottom: 14 })
  const dragged = useRef(false)
  const firstNote = useRef(true)

  const pose = useCallback((name, ms) => {
    setFlash(name)
    setTimeout(() => setFlash((f) => (f === name ? null : f)), ms)
  }, [])
  // No speech bubble: Liwa moves when she has something to say, and the words go to screen readers.
  const say = useCallback((text) => { setSpoken(text); pose('speaking', 2400) }, [pose])

  // The brief follows the storm. A plan is written only while the panel is open, and again when
  // something changes: a new stage, a field result, a repair, a hazard made safe.
  const eventId = state.event.id
  const version = `${eventId}-${state.log.length}-${state.repaired.length}-${state.summary.hazards_open}-${state.summary.reports}`
  useEffect(() => { setPlan(null); setError(null) }, [eventId])
  useEffect(() => {
    let live = true
    api.liwa().then((s) => { if (live) setStatus(s) }).catch(() => {})
    return () => { live = false }
  }, [version])

  const writePlan = useCallback(async (force = false) => {
    setPlanning(true); setError(null)
    try {
      const made = await api.liwaPlan(force)
      setPlan(made)
      say(made.steps.length ? `Inspection plan ready. First: ${made.steps[0].name}.` : 'Nothing urgent is left to inspect.')
    } catch (e) {
      setError(e.message)
    }
    setPlanning(false)
  }, [say])
  useEffect(() => { if (panel) writePlan() }, [panel, version, writePlan])

  // Field results and repairs are other people's work; announce them as that.
  useEffect(() => {
    if (firstNote.current) { firstNote.current = false; return }
    if (!note || note.quiet) return
    say(`${note.field ? 'From the field: ' : ''}${note.title}. ${note.body}`)
    if (note.title.startsWith('Damage pinned down')) pose('success', 2200)
    else if (note.tone === 'bad') pose('alert', 1500)
  }, [note?.id])   // eslint-disable-line react-hooks/exhaustive-deps

  const pose3d = useMemo(() => {
    if (planning) return 'thinking'
    if (flash) return flash
    return hover ? 'listening' : 'idle'
  }, [flash, planning, hover])

  const openPanel = () => { if (!dragged.current) setPanel(true) }
  useEffect(() => {
    if (!panel) return undefined
    const onKey = (e) => { if (e.key === 'Escape') setPanel(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [panel])

  // Dragging on a desktop. A drag never counts as a click.
  const W = mobile ? 92 : 150
  const H = mobile ? 118 : 196
  const startDrag = (e) => {
    if (mobile || e.button !== 0) return
    const from = { x: e.clientX, y: e.clientY, ...place }
    let moved = false
    const move = (ev) => {
      const dx = ev.clientX - from.x
      const dy = ev.clientY - from.y
      if (!moved && Math.hypot(dx, dy) < 6) return
      moved = true
      dragged.current = true
      setPlace({ right: clamp(from.right - dx, 8, window.innerWidth - W - 80), bottom: clamp(from.bottom - dy, 8, window.innerHeight - H - 70) })
    }
    const up = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      if (moved) setTimeout(() => { dragged.current = false }, 0)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
  }

  const small = mini || (mobile && sheetOpen)       // a phone with the sheet up only has room for a button
  const anchor = mobile
    ? { right: 8, bottom: `calc(${sheetOpen ? 78 : 42}% + 8px)` }
    : { right: clamp(place.right, 8, view.w - W - 80), bottom: clamp(place.bottom, 8, view.h - H - 70) }
  const above = mobile ? 0 : view.h - anchor.bottom - H - 78
  const panelStyle = mobile ? undefined
    : above >= 380 ? { right: 0, bottom: 'calc(100% + 10px)', maxHeight: above }
      : { right: 'calc(100% + 10px)', bottom: 0, maxHeight: view.h - anchor.bottom - 84 }
  const fallback = <div className="flat-crew"><Flat state={pose3d} size={mobile ? 56 : 84} /></div>

  return (
    <div className={`liwa${mobile ? ' phone' : ''}${small ? ' small' : ''}`} style={anchor}>
      <p className="sr-only" aria-live="polite">{spoken}</p>

      {panel && (
        <AssistantPanel status={status} plan={plan} planning={planning} error={error} style={panelStyle}
          onUpdate={() => writePlan(true)} onClose={() => setPanel(false)}
          onOpen={(sel) => { onOpen(sel); if (mobile) setPanel(false) }} />
      )}

      {mobile && panel ? null : small ? (
        <button className="liwa-mini" onClick={() => { setMini(false); if (mobile) openPanel() }} aria-label="Show Liwa" title="Show Liwa"><Bolt size={24} /></button>
      ) : (
        <div className="liwa-stage" style={{ width: W, height: H }} onPointerDown={startDrag}>
          <div className="liwa-canvas" style={{ height: H - 26 }}>
            {webgl ? (
              <SceneBoundary fallback={fallback} onFail={() => setWebgl(false)}>
                <Suspense fallback={fallback}><Scene state={pose3d} still={still} paused={!visible} /></Suspense>
              </SceneBoundary>
            ) : fallback}
          </div>
          <button className={`liwa-hit is-${pose3d}`} onClick={openPanel} onPointerEnter={() => setHover(true)} onPointerLeave={() => setHover(false)}
            onFocus={() => setHover(true)} onBlur={() => setHover(false)} aria-label="Liwa, the inspection planner. Open the inspection plan.">
            <span className="liwa-name">Inspection plan</span>
          </button>
          <button className="liwa-min" onClick={() => { setMini(true); setPanel(false) }} onPointerDown={(e) => e.stopPropagation()}
            aria-label="Minimise Liwa" title="Minimise"><Close size={12} /></button>
        </div>
      )}
    </div>
  )
}
