// Liwa: the planner. She floats over the map and thinks while she ranks an interruption's
// equipment. Click her to see the hierarchy she ranks by and to let her plan every interruption.
// There is nothing to type, and she only recommends: she cannot dispatch, repair or send anything.
import { Component, Suspense, lazy, useEffect, useState } from 'react'
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

// busy: she is ranking something now. lastDecision: the latest result, so she can react to it.
export default function Assistant({ cases, busy, running, lastDecision, mobile, sheetOpen, onRunAll }) {
  const still = useMedia('(prefers-reduced-motion: reduce)')
  const visible = useTabVisible()
  const view = useViewport()
  const [webgl, setWebgl] = useState(hasWebGL)
  const [status, setStatus] = useState(null)   // whether Claude is reachable, and the hierarchy she ranks by
  const [panel, setPanel] = useState(false)
  const [mini, setMini] = useState(false)
  const [flash, setFlash] = useState(null)     // a short pose after a result
  const [hover, setHover] = useState(false)
  const [spoken, setSpoken] = useState('')     // announced to screen readers
  const [place, setPlace] = useState({ right: 64, bottom: 14 })
  const [dragging, setDragging] = useState(false)

  useEffect(() => { api.liwa().then(setStatus).catch(() => {}) }, [])
  useEffect(() => {
    if (!lastDecision) return undefined
    setSpoken(`Liwa: ${lastDecision.action === 'HOLD' ? 'hold the crew' : `send the crew to ${lastDecision.pole_id}`}. ${lastDecision.reason}`)
    setFlash(lastDecision.action === 'HOLD' ? 'alert' : 'success')
    const timer = setTimeout(() => setFlash(null), 1800)
    return () => clearTimeout(timer)
  }, [lastDecision?.key]) // eslint-disable-line react-hooks/exhaustive-deps

  const pose = busy ? 'thinking' : flash ?? (hover ? 'listening' : 'idle')
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
      setDragging(true)
      setPlace({ right: clamp(from.right - dx, 8, window.innerWidth - W - 80), bottom: clamp(from.bottom - dy, 8, window.innerHeight - H - 70) })
    }
    const up = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      if (moved) setTimeout(() => setDragging(false), 0)
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
  const fallback = <div className="flat-crew"><Flat state={pose} size={mobile ? 56 : 84} /></div>

  return (
    <div className={`liwa${mobile ? ' phone' : ''}${small ? ' small' : ''}`} style={anchor}>
      <p className="sr-only" aria-live="polite">{spoken}</p>
      {panel && <AssistantPanel status={status} cases={cases} busy={busy} running={running} style={panelStyle} onRunAll={onRunAll} onClose={() => setPanel(false)} />}
      {mobile && panel ? null : small ? (
        <button className="liwa-mini" onClick={() => { setMini(false); if (mobile) setPanel(true) }} aria-label="Show Liwa" title="Show Liwa"><Bolt size={24} /></button>
      ) : (
        <div className="liwa-stage" style={{ width: W, height: H }} onPointerDown={startDrag}>
          <div className="liwa-canvas" style={{ height: H - 26 }}>
            {webgl ? (
              <SceneBoundary fallback={fallback} onFail={() => setWebgl(false)}>
                <Suspense fallback={fallback}><Scene state={pose} still={still} paused={!visible} /></Suspense>
              </SceneBoundary>
            ) : fallback}
          </div>
          <button className={`liwa-hit is-${pose}`} onClick={() => { if (!dragging) setPanel(true) }} onPointerEnter={() => setHover(true)} onPointerLeave={() => setHover(false)}
            onFocus={() => setHover(true)} onBlur={() => setHover(false)} aria-label="Liwa, the planner. Open to see the hierarchy she ranks by.">
            <span className="liwa-name">{busy ? 'Liwa is ranking' : 'Liwa'}</span>
          </button>
          <button className="liwa-min" onClick={() => { setMini(true); setPanel(false) }} onPointerDown={(e) => e.stopPropagation()}
            aria-label="Minimise Liwa" title="Minimise"><Close size={12} /></button>
        </div>
      )}
    </div>
  )
}
