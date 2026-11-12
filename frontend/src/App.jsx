import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import L from 'leaflet'
import { api } from './api'
import MapView from './map/MapView'
import Panel from './panel/Panel'
import Evaluation from './Evaluation'
import { Mark, Meralco, Wordmark } from './Logo'
import { TIERS } from './theme'
import { Back, Bell, Close, Hospital, Landmark, Pause, People, Play } from './icons'

const RESULT = {
  damaged: ['damage found', 'bad'],
  intact: ['no damage', 'good'],
  inconclusive: ["couldn't confirm", 'warn'],
}

// Turns a change between two storm states into plain-language notifications.
function describeChanges(prev, next) {
  if (next.event.id !== prev.event.id) {
    return { reset: true, notes: [{ tone: 'info', title: 'New storm loaded', body: `${next.summary.reports} messages from ${next.summary.people} people. Start with the top of the list.` }] }
  }
  const notes = []
  next.log.slice(0, next.log.length - prev.log.length).reverse().forEach((o) => {
    const [label, tone] = RESULT[o.result]
    notes.push({ tone, title: `${o.asset_name}: ${label}`, body: `Reported by ${o.by}` })
  })
  next.areas.forEach((a) => {
    const before = prev.areas.find((p) => p.id === a.id)
    if (before?.hazard_open && !a.hazard_open) notes.push({ tone: 'good', title: `Made safe: Brgy. ${a.barangay}`, body: `By ${a.hazard_handled_by}` })
  })
  next.roads.forEach((r) => {
    const before = prev.roads.find((p) => p.id === r.id)
    if (before && before.blocked !== r.blocked) {
      notes.push({ tone: r.blocked ? 'bad' : 'good', title: `${r.name} ${r.blocked ? 'closed' : 'reopened'}`, body: 'Routes and priorities updated.' })
    }
  })
  next.repaired.forEach((x) => {
    if (prev.repaired.some((p) => p.asset_id === x.asset_id)) return
    const back = x.back.map((n) => n.split(',')[0]).join(', ')
    const dark = x.still_dark.map((n) => n.split(',')[0]).join(', ')
    notes.push({ tone: dark ? 'warn' : 'good', title: `Repaired: ${x.name}`, body: dark ? `Power back in ${back || 'no barangays yet'}. Still dark: ${dark}. Another break is likely.` : `Power back in ${back}.` })
  })
  if (next.resources.identified && !prev.resources.identified) {
    notes.push({ tone: 'good', title: 'Damage pinned down', body: `${next.resources.top_label}. See Ready for repair.` })
  } else {
    const top = next.recommendations[0]
    if (top && top.tier !== 'low' && prev.recommendations[0] && top.asset_id !== prev.recommendations[0].asset_id) {
      notes.push({ tone: 'accent', title: 'New top priority', body: `${top.name}, ${top.place}` })
    }
  }
  return { reset: false, notes }
}

function useIsMobile() {
  const query = '(max-width: 820px)'
  const [mobile, setMobile] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const mq = window.matchMedia(query)
    const update = () => setMobile(mq.matches)
    mq.addEventListener('change', update)
    return () => mq.removeEventListener('change', update)
  }, [])
  return mobile
}

const LEGEND = ['critical', 'high', 'medium', 'low', 'confirmed', 'unknown', 'restored']

function Legend() {
  const [open, setOpen] = useState(true)
  return (
    <div className={`map-key${open ? '' : ' closed'}`}>
      <button className="legend-toggle" onClick={() => setOpen((o) => !o)} aria-expanded={open}>{open ? 'Hide key' : 'Map key'}</button>
      {open && (
        <ul>
          {LEGEND.map((t) => <li key={t}><i className={`dot t-${t}`}>{t === 'unknown' ? '?' : t === 'restored' ? '✓' : '!'}</i>{TIERS[t].label}</li>)}
          <li><i className="lg-closed" />Road closed</li>
        </ul>
      )}
    </div>
  )
}

function Drawer({ open, onClose, view, setView, playing, setPlaying, run, basemap, onTruth }) {
  if (!open) return null
  const go = (v) => { setView(v); onClose() }
  return (
    <div className="drawer-wrap" onClick={onClose}>
      <nav className="drawer" onClick={(e) => e.stopPropagation()} aria-label="Menu">
        <div className="drawer-head"><Wordmark /><button className="icon-btn" onClick={onClose} aria-label="Close menu"><Close size={16} /></button></div>
        <div className="drawer-group">
          {[['map', 'Live map', 'Priorities, reports and road closures'], ['insights', 'Insights', 'How FirstLook compares with other ways of choosing']].map(([k, label, hint]) => (
            <button key={k} className={view === k ? 'drawer-item on' : 'drawer-item'} onClick={() => go(k)}><strong>{label}</strong><span>{hint}</span></button>
          ))}
        </div>
        <div className="drawer-group">
          <h4>Demo controls</h4>
          <button className="drawer-item" onClick={() => { setPlaying((p) => !p); onClose() }}>
            <strong>{playing ? <><Pause size={13} /> Pause the demo</> : <><Play size={13} /> Play the demo</>}</strong>
            <span>Simulates field results and repairs, step by step, until every barangay has power</span>
          </button>
          <button className="drawer-item" onClick={() => { setPlaying(false); run(() => api.reset(null)); onClose() }}><strong>Restart the demo storm</strong><span>Same storm, nothing checked yet</span></button>
          <button className="drawer-item" onClick={() => { setPlaying(false); run(() => api.reset(Math.floor(Math.random() * 1e6))); onClose() }}><strong>Load a random storm</strong><span>New damage, new reports</span></button>
          <button className="drawer-item" onClick={() => { onTruth(); onClose() }}><strong>Reveal the hidden damage</strong><span>Shows what really broke in this simulated storm</span></button>
        </div>
        <p className="drawer-foot muted small">
          {basemap === 'google' ? 'Map: Google Maps.' : 'Map: free OpenStreetMap map. Add a Google Maps key to frontend/.env.local to switch.'}
          {' '}All storm data is invented for this demo; place names are real.
        </p>
        <div className="drawer-brand"><Meralco /></div>
      </nav>
    </div>
  )
}

export default function App() {
  const [state, setState] = useState(null)
  const [reports, setReports] = useState([])
  const [error, setError] = useState(null)
  const [view, setView] = useState('map')
  const [stack, setStack] = useState([])
  const [tab, setTab] = useState('priorities')
  const [stage, setStage] = useState('check')
  const [layers, setLayers] = useState({ reports: true, critical: true, roads: false, landmarks: false })
  const [menu, setMenu] = useState(false)
  const [notesOpen, setNotesOpen] = useState(false)
  const [notes, setNotes] = useState([])
  const [toasts, setToasts] = useState([])
  const [unread, setUnread] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [basemap, setBasemap] = useState(null)
  const [sheet, setSheet] = useState(false)
  const mobile = useIsMobile()
  const previous = useRef(null)
  const latest = useRef(null)
  const counter = useRef(0)
  const inFlight = useRef(false)

  const sel = stack[stack.length - 1] ?? null
  const open = useCallback((s) => {
    setStack((st) => {
      const top = st[st.length - 1]
      if (top && top.kind === s.kind && top.id === s.id) return st
      return [...st.slice(-15), s]
    })
    setSheet(true)
  }, [])
  const back = () => setStack((st) => st.slice(0, -1))
  const close = () => setStack([])

  const toast = useCallback((found, reset = false) => {
    const time = new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
    const stamped = found.map((n) => ({ ...n, id: ++counter.current, time }))
    setNotes((old) => [...stamped.slice().reverse(), ...(reset ? [] : old)].slice(0, 30))
    setUnread((u) => (reset ? 0 : u) + stamped.length)
    setToasts((old) => [...old, ...stamped].slice(-3))
    stamped.forEach((n) => setTimeout(() => setToasts((old) => old.filter((t) => t.id !== n.id)), 6000))
  }, [])

  // Runs an API call; any response that carries the storm state refreshes the screen.
  const run = useCallback(async (fn) => {
    try {
      const data = await fn()
      if (data?.assets) setState(data)
      else if (data?.state) setState(data.state)
      setError(null)
      return data
    } catch (e) {
      setError(e.message)
      return null
    }
  }, [])

  useEffect(() => {
    run(api.state)
    const timer = setInterval(() => run(api.state), 5000)   // keeps the dispatcher and field screens in step
    return () => clearInterval(timer)
  }, [run])

  const eventId = state?.event.id
  const reportCount = state?.summary.reports
  useEffect(() => { setStack([]); setStage('check') }, [eventId])
  // Reload the feed when a storm starts or new messages arrive (e.g. after a repair).
  useEffect(() => {
    if (!eventId) return
    api.reports().then((d) => setReports(d.reports)).catch((e) => setError(e.message))
  }, [eventId, reportCount])

  useEffect(() => {
    latest.current = state
    const prev = previous.current
    previous.current = state
    if (!state || !prev) return
    const { reset, notes: found } = describeChanges(prev, state)
    if (found.length) toast(found, reset)
  }, [state, toast])

  // Demo: field results come in for the top place until the damage is pinned down, then
  // repairs happen one at a time; if an area stays dark, checking resumes.
  useEffect(() => {
    if (!playing) return undefined
    const step = async () => {
      const s = latest.current
      if (!s || inFlight.current) return
      const top = s.recommendations.find((r) => r.tier !== 'low')
      const ready = s.handoff.find((h) => !h.blocked_by.length)
      const dark = s.areas.some((a) => a.p_out >= 0.5)
      inFlight.current = true
      try {
        if (!s.resources.identified && top) {
          setStage('check'); setStack([{ kind: 'priority', id: top.asset_id }])
          await run(() => api.observe(top.asset_id, null))
        } else if (ready) {
          setStage('repair'); setStack([])
          await run(() => api.repair(ready.asset_id, 'Repair team (demo)'))
        } else if (dark && top) {
          setStage('check'); setStack([{ kind: 'priority', id: top.asset_id }])
          await run(() => api.observe(top.asset_id, null))
        } else {
          setPlaying(false); setStage('done'); setStack([])
        }
      } finally {
        inFlight.current = false
      }
    }
    step()
    const timer = setInterval(step, 2800)
    return () => clearInterval(timer)
  }, [playing, run])

  const focus = useMemo(() => {
    if (!state || !sel) return null
    if (sel.kind === 'priority') {
      const a = state.assets.find((x) => x.id === sel.id)
      const rec = state.recommendations.find((r) => r.asset_id === sel.id)
      const pts = [a.pos, ...(rec?.covers.areas ?? []).map((c) => state.areas.find((x) => x.id === c.id).pos)]
      return pts.length > 1 ? { key: `p-${sel.id}`, bounds: L.latLngBounds(pts) } : { key: `p-${sel.id}`, pos: a.pos, zoom: 13 }
    }
    if (sel.kind === 'area') return { key: `a-${sel.id}`, pos: state.areas.find((x) => x.id === sel.id).pos, zoom: 14 }
    const r = reports.find((x) => x.id === sel.id)
    return r ? { key: `r-${sel.id}`, pos: r.pos, zoom: 15 } : null
  }, [sel?.kind, sel?.id, state?.event.id, reports.length]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!state) {
    return <div className="boot"><Mark size={44} /><p>{error ? `Can't reach the FirstLook server. Start the backend on port 8000, then reload. (${error})` : 'Loading the storm picture…'}</p></div>
  }

  const revealTruth = () => api.truth().then((t) => toast([{ tone: 'accent', title: 'Hidden damage in this storm', body: t.label }])).catch((e) => setError(e.message))
  const toggle = (k) => setLayers((l) => ({ ...l, [k]: !l[k] }))
  const chips = [
    ['reports', 'Reports', People], ['critical', 'Critical sites', Hospital],
    ['landmarks', 'Landmarks', Landmark],
  ]

  return (
    <div className={`app${mobile ? ' mobile' : ''}`}>
      {error && <div className="error-bar" role="alert">{error}<button className="btn ghost sm" onClick={() => setError(null)}>Dismiss</button></div>}
      <div className="toasts" aria-live="polite">
        {toasts.map((n) => (
          <div key={n.id} className={`toast ${n.tone}`}>
            <span className={`pip ${n.tone}`} />
            <div><strong>{n.title}</strong><span>{n.body}</span></div>
            <button className="icon-btn" aria-label="Dismiss" onClick={() => setToasts((old) => old.filter((t) => t.id !== n.id))}><Close size={14} /></button>
          </div>
        ))}
      </div>

      {view === 'map' ? (
        <>
          <MapView state={state} reports={reports} sel={sel} layers={layers} focus={focus} padLeft={420} mobile={mobile}
            onSelectArea={(id) => open({ kind: 'area', id })}
            onSelectReport={(id) => open({ kind: 'report', id })}
            onToggleRoad={(road) => run(() => api.road(road.id, !road.blocked))}
            onBasemap={setBasemap} />
          <Panel state={state} reports={reports} sel={sel} open={open} back={back} close={close} tab={tab} setTab={setTab}
            run={run} onMenu={() => setMenu(true)} stage={stage} setStage={setStage}
            roadsOn={layers.roads} onRoads={() => toggle('roads')} sheet={sheet} setSheet={setSheet} />
          <div className="map-chips" role="group" aria-label="Map layers">
            {chips.map(([k, label, Icon]) => (
              <button key={k} className={layers[k] ? 'mchip on' : 'mchip'} aria-pressed={layers[k]} onClick={() => toggle(k)}><Icon size={15} />{label}</button>
            ))}
          </div>
          {!mobile && <Legend />}
        </>
      ) : (
        <div className="page">
          <header className="page-bar">
            <button className="btn" onClick={() => setView('map')}><Back size={16} />Back to live map</button>
            <strong>Insights</strong>
            <span />
          </header>
          <div className="page-body"><Evaluation /></div>
        </div>
      )}

      <div className="top-right">
        {playing && <button className="btn sm live" onClick={() => setPlaying(false)}><Pause size={12} />Demo running</button>}
        <button className="icon-btn raised bell" onClick={() => { setNotesOpen((o) => !o); setUnread(0) }} aria-label={`Notifications, ${unread} new`}>
          <Bell />{unread > 0 && <span className="badge">{unread}</span>}
        </button>
        {notesOpen && (
          <div className="popover">
            <div className="pop-head"><strong>Notifications</strong><button className="icon-btn" onClick={() => setNotesOpen(false)} aria-label="Close notifications"><Close size={14} /></button></div>
            {notes.length === 0 && <p className="muted">Nothing yet. Updates appear here as results come in from the field.</p>}
            {notes.map((n) => (
              <div key={n.id} className="note-row">
                <span className={`pip ${n.tone}`} />
                <div><strong>{n.title}</strong><span className="muted">{n.body}</span></div>
                <span className="muted small">{n.time}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <Drawer open={menu} onClose={() => setMenu(false)} view={view} setView={setView} playing={playing} setPlaying={setPlaying}
        run={run} basemap={basemap} onTruth={revealTruth} />
    </div>
  )
}
