import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import Console from './Console'
import Field from './Field'
import Evaluation from './Evaluation'
import { Mark, Meralco, Wordmark } from './Logo'

const TABS = [['console', 'Console'], ['field', 'Field'], ['evaluation', 'Evaluation']]
const RESULT = {
  damaged: ['Damage found', 'bad'],
  intact: ['No damage', 'good'],
  inconclusive: ["Couldn't confirm", 'warn'],
}

const Chevron = ({ flip }) => (
  <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" style={flip ? { transform: 'rotate(180deg)' } : null}>
    <path d="M10 3.5 5.5 8l4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)
const Bell = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
    <path d="M4 11V7.2a4 4 0 0 1 8 0V11l1.2 1.5H2.8L4 11Zm2.6 3h2.8" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)

// Turns a change between two event states into plain-language notifications.
function describeChanges(prev, next) {
  if (next.event.seed !== prev.event.seed || next.log.length < prev.log.length) {
    return { reset: true, notes: [{ tone: 'info', title: 'New storm loaded', body: 'Outage reports are in. Start with the top inspection.' }] }
  }
  const notes = []
  const name = (id) => next.assets.find((a) => a.id === id)?.name ?? id

  next.log.slice(0, next.log.length - prev.log.length).reverse().forEach((o) => {
    const [label, tone] = RESULT[o.result]
    notes.push({ tone, title: `${o.asset_name}: ${label}`, body: `${o.crew_name} reported from the field.` })
  })
  next.crews.forEach((c) => {
    const before = prev.crews.find((p) => p.id === c.id)
    if (c.asset_id && before?.asset_id !== c.asset_id) {
      notes.push({ tone: 'info', title: `${c.name} sent out`, body: `Heading to ${name(c.asset_id)}${c.travel_min != null ? ` · ${c.travel_min} min drive` : ''}.` })
    }
  })
  next.roads.forEach((r) => {
    const before = prev.roads.find((p) => p.id === r.id)
    if (before && before.blocked !== r.blocked) {
      notes.push({ tone: r.blocked ? 'bad' : 'good', title: `${r.name} ${r.blocked ? 'closed' : 'reopened'}`, body: 'Routes and rankings were updated.' })
    }
  })
  if (next.resources.identified && !prev.resources.identified) {
    notes.push({ tone: 'good', title: 'Damage identified', body: `${next.resources.top_label}. Repair crews can be sent.` })
  } else {
    const top = next.recommendations[0]
    if (top && prev.recommendations[0] && top.asset_id !== prev.recommendations[0].asset_id) {
      notes.push({ tone: 'accent', title: 'New top inspection', body: `${top.name} · ${top.place}` })
    }
  }
  return { reset: false, notes }
}

// Brand, navigation, notifications and demo controls. Replaces a page header.
function Dock({ state, view, setView, run, collapsed, onToggle, notes, unread, onOpenNotes, playing, setPlaying }) {
  const [open, setOpen] = useState(false)
  if (collapsed) {
    return (
      <button className="card dock mini" onClick={onToggle} aria-label="Expand panel">
        <Mark /><Chevron flip />{unread > 0 && <span className="badge">{unread}</span>}
      </button>
    )
  }
  return (
    <div className="card dock">
      <div className="row center">
        <Wordmark />
        <span className="row center gap">
          <Meralco />
          <button className="icon-btn bell" aria-label={`Notifications, ${unread} new`}
            onClick={() => { setOpen((o) => !o); onOpenNotes() }}>
            <Bell />{unread > 0 && <span className="badge">{unread}</span>}
          </button>
          {onToggle && <button className="icon-btn" onClick={onToggle} aria-label="Collapse panel"><Chevron /></button>}
        </span>
      </div>
      {open && (
        <div className="popover">
          <div className="row center"><span className="label">Notifications</span><button className="link" onClick={() => setOpen(false)}>Close</button></div>
          {notes.length === 0 && <p className="muted">Nothing yet. Updates appear here as crews report in.</p>}
          {notes.map((n) => (
            <div key={n.id} className="note-row">
              <span className={`pip ${n.tone}`} />
              <div><strong>{n.title}</strong><div className="muted">{n.body}</div></div>
              <span className="muted small">{n.time}</span>
            </div>
          ))}
        </div>
      )}
      <nav className="seg">
        {TABS.map(([key, label]) => (
          <button key={key} className={view === key ? 'on' : ''} onClick={() => setView(key)}>{label}</button>
        ))}
      </nav>
      <div className="row center">
        <button className={playing ? 'btn play on' : 'btn play'} onClick={() => setPlaying((p) => !p)}>
          {playing ? 'Pause demo' : 'Play demo'}
        </button>
        <span className="row gap">
          <button className="link" onClick={() => { setPlaying(false); run(() => api.reset(null)) }}>Restart</button>
          <button className="link" onClick={() => { setPlaying(false); run(() => api.reset(Math.floor(Math.random() * 1e6))) }}>New storm</button>
        </span>
      </div>
    </div>
  )
}

export default function App() {
  const [state, setState] = useState(null)
  const [view, setView] = useState('console')
  const [collapsed, setCollapsed] = useState(false)
  const [error, setError] = useState(null)
  const [notes, setNotes] = useState([])       // newest first
  const [toasts, setToasts] = useState([])
  const [unread, setUnread] = useState(0)
  const [playing, setPlaying] = useState(false)
  const previous = useRef(null)
  const latest = useRef(null)
  const counter = useRef(0)
  const inFlight = useRef(false)

  // Runs an API call; any response that carries the event state refreshes the screen.
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
    const timer = setInterval(() => run(api.state), 5000)   // keeps console and field screens in step
    return () => clearInterval(timer)
  }, [run])

  // Notify on every change, including ones made from another screen.
  useEffect(() => {
    latest.current = state
    const prev = previous.current
    previous.current = state
    if (!state || !prev) return
    const { reset, notes: found } = describeChanges(prev, state)
    if (!found.length) return
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    const stamped = found.map((n) => ({ ...n, id: ++counter.current, time }))
    setNotes((old) => [...stamped.slice().reverse(), ...(reset ? [] : old)].slice(0, 30))
    setUnread((u) => (reset ? 0 : u) + stamped.length)
    setToasts((old) => [...old, ...stamped].slice(-4))
    stamped.forEach((n) => setTimeout(() => setToasts((old) => old.filter((t) => t.id !== n.id)), 6500))
  }, [state])

  // Demo: dispatches the top inspection, then reports the field result, step by step.
  useEffect(() => {
    if (!playing) return undefined
    const step = async () => {
      const s = latest.current
      if (!s || inFlight.current) return   // one action at a time
      const idle = s.crews.filter((c) => !c.asset_id)
      const busy = s.crews.find((c) => c.asset_id)
      const top = s.recommendations[0]
      inFlight.current = true
      try {
        if (!s.resources.identified && top && idle.some((c) => c.id === top.crew_id)) {
          await run(() => api.assign(top.crew_id, top.asset_id))
        } else if (busy) {
          await run(() => api.observe(busy.id, busy.asset_id, null, ''))
        } else {
          setPlaying(false)
        }
      } finally {
        inFlight.current = false
      }
    }
    step()
    const timer = setInterval(step, 2800)
    return () => clearInterval(timer)
  }, [playing, run])

  if (!state) {
    return <div className="boot"><Mark size={44} />{error ? `Cannot reach the FirstLook API: ${error}` : 'Loading…'}</div>
  }

  const dock = (toggle) => (
    <Dock state={state} view={view} setView={setView} run={run} notes={notes} unread={unread}
      onOpenNotes={() => setUnread(0)} playing={playing} setPlaying={setPlaying}
      collapsed={toggle && collapsed} onToggle={toggle ? () => setCollapsed((c) => !c) : null} />
  )
  return (
    <div className="app">
      {error && <div className="toast" role="alert">{error}<button onClick={() => setError(null)}>Dismiss</button></div>}
      <div className="notes" aria-live="polite">
        {toasts.map((n) => (
          <div key={n.id} className={`card note ${n.tone}`}>
            <span className={`pip ${n.tone}`} />
            <div><strong>{n.title}</strong><div className="muted">{n.body}</div></div>
            <button className="link" aria-label="Dismiss" onClick={() => setToasts((old) => old.filter((t) => t.id !== n.id))}>×</button>
          </div>
        ))}
      </div>
      {view === 'console'
        ? <Console state={state} run={run} dock={dock(true)} collapsed={collapsed} />
        : (
          <div className="page">
            <div className="page-dock">{dock(false)}</div>
            <div className="card sheet">
              {view === 'field' ? <Field state={state} run={run} /> : <Evaluation />}
            </div>
          </div>
        )}
    </div>
  )
}
