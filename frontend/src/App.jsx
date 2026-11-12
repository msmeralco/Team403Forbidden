import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import L from 'leaflet'
import { api } from './api'
import MapView from './map/MapView'
import { NETWORK_NOTE, OFFICE_NOTE } from './map/GridLayer'
import { meterBlock, upstream } from './map/network'
import Panel from './panel/Panel'
import Assistant from './assistant/Assistant'
import TyphoonPanel from './typhoon/TyphoonPanel'
import { makeTrack } from './typhoon/track'
import { Mark, Meralco, Wordmark } from './Logo'
import { TIERS } from './theme'
import { Bell, Close, Landmark, Office, Pause, People, Play, Pylon } from './icons'

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
    notes.push({ tone, title: `${o.asset_name}: ${label}`, body: `Reported by ${o.by}`, field: true })
  })
  next.areas.forEach((a) => {
    const before = prev.areas.find((p) => p.id === a.id)
    if (before?.hazard_open && !a.hazard_open) notes.push({ tone: 'good', title: `Made safe: Brgy. ${a.barangay}`, body: `By ${a.hazard_handled_by}` })
  })
  next.areas.forEach((a) => {
    const before = prev.areas.find((p) => p.id === a.id)
    if (before && !before.hazard_open && a.hazard_open && !before.hazard_handled_by) {
      notes.push({ tone: 'bad', title: `Safety hazard: Brgy. ${a.barangay}`, body: `${Object.keys(a.hazards)[0]}, ${a.city}` })
    }
  })
  if (prev.ai.status === 'reading' && next.ai.status === 'done') {
    notes.push({ tone: 'info', title: 'The AI reader has finished', body: next.ai.caught_reports ? `It caught ${next.ai.caught_reports} messages the keyword rules missed.` : 'It found nothing the keyword rules missed.' })
  }
  next.repaired.forEach((x) => {
    if (prev.repaired.some((p) => p.asset_id === x.asset_id)) return
    const back = x.back.map((n) => n.split(',')[0]).join(', ')
    const dark = x.still_dark.map((n) => n.split(',')[0]).join(', ')
    notes.push({ tone: dark ? 'warn' : 'good', title: `Repaired: ${x.name}`, body: dark ? `Power back in ${back || 'no barangays yet'}. Still dark: ${dark}. Another break is likely.` : `Power back in ${back}.`, field: true })
  })
  if (next.resources.identified && !prev.resources.identified) {
    notes.push({ tone: 'good', title: 'Damage pinned down', body: `${next.resources.top_label}. See Damage found.` })
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

const KEY_GROUPS = [
  ['Where to check', ['critical', 'high', 'medium', 'low']],
  ['What we know', ['confirmed', 'unknown', 'restored']],
]

function Legend({ layers, network }) {
  const [open, setOpen] = useState(true)
  return (
    <div className={`map-key${open ? '' : ' closed'}`}>
      <button className="legend-toggle" onClick={() => setOpen((o) => !o)} aria-expanded={open}>{open ? 'Hide key' : 'Map key'}</button>
      {open && (
        <div className="key-body">
          {KEY_GROUPS.map(([title, tiers]) => (
            <section key={title}>
              <h4>{title}</h4>
              <ul>{tiers.map((t) => <li key={t}><i className={`dot t-${t}`}>{t === 'unknown' ? '?' : t === 'restored' ? '✓' : '!'}</i>{TIERS[t].label}</li>)}</ul>
            </section>
          ))}
          {network && (
            <section>
              <h4>Power network</h4>
              <ul>
                <li><i className="lg-eq lg-sub" />Substation</li>
                <li><i className="lg-line" style={{ borderTopWidth: 4 }} />Main line</li>
                <li><i className="lg-line" style={{ borderTopWidth: 2 }} />Branch line</li>
                <li><i className="lg-eq lg-tx" />Transformer</li>
              </ul>
            </section>
          )}
          {network && (
            <section>
              <h4>kWh meters</h4>
              <ul>
                <li><i className="lg-meter on" />Has power</li>
                <li><i className="lg-meter dark" />Likely no power</li>
                <li><i className="lg-meter told" />Reported no power</li>
              </ul>
              <p className="lg-note">{NETWORK_NOTE}</p>
            </section>
          )}
          {layers.offices && (
            <section>
              <h4>Meralco offices</h4>
              <ul><li><i className="lg-office" />Office</li></ul>
              <p className="lg-note">{OFFICE_NOTE}</p>
            </section>
          )}
        </div>
      )}
    </div>
  )
}

function Drawer({ open, onClose, playing, setPlaying, run, basemap, onReplay }) {
  const [cases, setCases] = useState(null)       // test cases found in backend/cases
  useEffect(() => {
    if (open) api.cases().then(setCases).catch(() => setCases({ cases: [], errors: ['The list of test cases could not be loaded.'] }))
  }, [open])
  if (!open) return null
  return (
    <div className="drawer-wrap" onClick={onClose}>
      <nav className="drawer" onClick={(e) => e.stopPropagation()} aria-label="Menu">
        <div className="drawer-head"><Wordmark /><button className="icon-btn" onClick={onClose} aria-label="Close menu"><Close size={16} /></button></div>
        <div className="drawer-group">
          <h4>Test cases</h4>
          {cases?.cases.map((c) => (
            <button key={c.id} className="drawer-item" onClick={() => { setPlaying(false); run(() => api.loadStage(c.id, 1)); onClose() }}>
              <strong>{c.name}</strong>
              <span>{c.stages.map((s) => s.name).join(', then ')}</span>
            </button>
          ))}
          {cases && cases.cases.length === 0 && <p className="drawer-note muted small">None yet. Put case files in backend/cases.</p>}
          {cases?.errors.map((e) => <p key={e} className="drawer-note small warn-text">{e}</p>)}
        </div>
        <div className="drawer-group">
          <h4>Demo controls</h4>
          <button className="drawer-item" onClick={() => { setPlaying((p) => !p); onClose() }}>
            <strong>{playing ? <><Pause size={13} /> Pause the demo</> : <><Play size={13} /> Play the demo</>}</strong>
            <span>Simulates field results and repairs, step by step, until every barangay has power</span>
          </button>
          <button className="drawer-item" onClick={() => { setPlaying(false); onReplay(); onClose() }}><strong>Replay the typhoon</strong><span>Shows the storm crossing Luzon again, on a new track</span></button>
          <button className="drawer-item" onClick={() => { setPlaying(false); run(() => api.reset(null)); onClose() }}><strong>Restart the demo storm</strong><span>Same storm, nothing checked yet</span></button>
          <button className="drawer-item" onClick={() => { setPlaying(false); run(() => api.reset(Math.floor(Math.random() * 1e6))); onClose() }}><strong>Load a random storm</strong><span>New damage, new reports</span></button>
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
  // The app opens on the typhoon itself. Outages only exist once it has passed.
  const [phase, setPhase] = useState('before')          // before | passing | after
  const [trackSeed, setTrackSeed] = useState(() => Math.floor(Math.random() * 1e9))
  const [tick, setTick] = useState(null)                // where the storm is while it passes
  const [pathView, setPathView] = useState(null)        // barangay whose houses and meters are framed up close
  const [zoneKm, setZoneKm] = useState(2)               // radius of the zone around an opened case; null = its whole supply path
  const [stack, setStack] = useState([])
  const [tab, setTab] = useState('check')
  const [layers, setLayers] = useState({ reports: true, landmarks: false, grid: false, offices: false })
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
  const gridTold = useRef(false)

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

  const reading = state?.ai.status === 'reading'
  useEffect(() => {
    run(api.state)
    // Keeps every open screen in step; quicker while the AI reader is still working.
    const timer = setInterval(() => run(api.state), reading ? 1500 : 5000)
    return () => clearInterval(timer)
  }, [run, reading])

  const eventId = state?.event.id
  const reportCount = state?.summary.reports
  useEffect(() => { setStack([]); setTab('check') }, [eventId])
  // Reload the feed when a storm starts or new messages arrive (e.g. after a repair).
  useEffect(() => {
    if (!eventId) return
    api.reports().then((d) => setReports(d.reports)).catch((e) => setError(e.message))
  }, [eventId, reportCount, state?.ai.read, state?.ai.photos, state?.ai.caught_reports])

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
          setTab('check'); setStack([{ kind: 'priority', id: top.asset_id }])
          await run(() => api.observe(top.asset_id, null))
        } else if (ready) {
          setTab('found'); setStack([])
          await run(() => api.repair(ready.asset_id, 'Repair team (demo)'))
        } else if (dark && top) {
          setTab('check'); setStack([{ kind: 'priority', id: top.asset_id }])
          await run(() => api.observe(top.asset_id, null))
        } else {
          setPlaying(false); setTab('found'); setStack([])
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
    if (sel.kind === 'area') {
      // Frame the whole path that feeds the barangay, from the substation down; or, on request, just its houses and meters.
      const area = state.areas.find((x) => x.id === sel.id)
      const chain = upstream(state, area.transformer)
      const houses = pathView === sel.id
      if (!houses && zoneKm) return { key: `a-${sel.id}-zone-${zoneKm}`, bounds: L.latLng(area.pos).toBounds(zoneKm * 2100), maxZoom: 16 }
      const far = houses ? [] : [...chain.map((x) => x.pos), state.substation.pos]
      return { key: `a-${sel.id}-${houses}`, bounds: L.latLngBounds([...meterBlock(area).corner, ...far]), maxZoom: houses ? 17.75 : 15 }
    }
    const r = reports.find((x) => x.id === sel.id)
    return r ? { key: `r-${sel.id}`, pos: r.pos, zoom: 15 } : null
  }, [sel?.kind, sel?.id, state?.event.id, reports.length, pathView, zoneKm]) // eslint-disable-line react-hooks/exhaustive-deps

  const allClear = state?.event.all_clear
  const track = useMemo(() => (allClear ? makeTrack(trackSeed, allClear) : null), [trackSeed, allClear])
  const intro = phase !== 'after' && Boolean(track) && state?.event.kind === 'typhoon'     // an interruption has no typhoon to show
  const replay = useCallback(() => {
    setTrackSeed(Math.floor(Math.random() * 1e9)); setTick(null); setStack([]); setPhase('before')
  }, [])
  const reveal = useCallback(() => {
    setPhase('after'); setTick(null)
    const s = latest.current
    if (s) toast([{ tone: 'info', title: `${s.event.name} has passed`, body: `${s.summary.reports} messages from ${s.summary.people} people so far. Start with number 1.` }])
  }, [toast])
  // The first stage of a test case is a typhoon: show it arriving before its outages.
  const caseStage = state?.case ? `${state.case.id}-${state.case.stage}-${state.event.id}` : null
  useEffect(() => { if (state?.case?.stage === 1 && state.event.kind === 'typhoon') replay() }, [caseStage]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!state) {
    return <div className="boot"><Mark size={44} /><p>{error ? `Can't reach the FirstLook server. Start the backend on port 8000, then reload. (${error})` : 'Loading the storm picture…'}</p></div>
  }

  const toggle = (k) => {
    // Say once where the grid picture comes from, so nobody takes it for Meralco's own map.
    if (k === 'offices' && !layers[k] && !gridTold.current) {
      gridTold.current = true
      toast([{ tone: 'info', title: 'Showing Meralco offices', body: OFFICE_NOTE, quiet: true }])
    }
    setLayers((l) => ({ ...l, [k]: !l[k] }))
  }
  const chips = [
    ['reports', 'Reports', People],
    ['landmarks', 'Landmarks', Landmark],
    ['grid', 'Meralco grid', Pylon], ['offices', 'Meralco offices', Office],
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

      <>
          <MapView state={state} reports={reports} sel={sel} layers={layers} focus={focus} padLeft={420} mobile={mobile}
            typhoon={intro ? { track, running: phase === 'passing', onTick: setTick, onDone: reveal } : null}
            onSelectArea={(id) => open({ kind: 'area', id })}
            onSelectPlace={(id) => open({ kind: 'priority', id })} zoneKm={zoneKm}
            onSelectReport={(id) => open({ kind: 'report', id })}
            onBasemap={setBasemap} onError={setError} />
          {intro ? (
            <TyphoonPanel name={state.event.name} track={track} running={phase === 'passing'} tick={tick}
              onStart={() => setPhase('passing')} onSkip={reveal} />
          ) : (
            <>
              <Panel state={state} reports={reports} sel={sel} open={open} back={back} close={close} tab={tab} setTab={setTab}
                run={run} onMenu={() => setMenu(true)} sheet={sheet} setSheet={setSheet}
                onShowPath={(id) => setPathView((v) => (v === id ? null : id))} pathShown={pathView} zoneKm={zoneKm} setZoneKm={(k) => { setZoneKm(k); setPathView(null) }} />
              <div className="map-chips" role="group" aria-label="Map layers">
                {chips.map(([k, label, Icon]) => (
                  <button key={k} className={layers[k] ? 'mchip on' : 'mchip'} aria-pressed={layers[k]} onClick={() => toggle(k)}><Icon size={15} />{label}</button>
                ))}
              </div>
              {!mobile && <Legend layers={layers} network={layers.grid || Boolean(sel && sel.kind !== 'report')} />}
              <Assistant state={state} note={toasts[toasts.length - 1] ?? null} mobile={mobile} sheetOpen={sheet} onOpen={open} />
            </>
          )}
      </>

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

      <Drawer open={menu} onClose={() => setMenu(false)} playing={playing} setPlaying={setPlaying}
        run={run} basemap={basemap} onReplay={replay} />
    </div>
  )
}
