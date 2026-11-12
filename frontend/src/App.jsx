// FirstLook. The app opens on the typhoon; once it has passed, the power interruptions (the test
// cases) appear as pins and as a list. Opening one shows the zone around it, the infrastructure
// inside, the order Liwa ranks it in, and the crew's ETA from the nearest Meralco office.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import L from 'leaflet'
import { api } from './api'
import MapView from './map/MapView'
import { NETWORK_NOTE, OFFICE_NOTE } from './map/GridLayer'
import { EQUIPMENT_ICON, EQUIPMENT_NAME, layout as caseLayout, ranking, standing } from './map/cases'
import Panel from './panel/Panel'
import Assistant from './assistant/Assistant'
import TyphoonPanel from './typhoon/TyphoonPanel'
import Records from './records/Records'
import { makeTrack } from './typhoon/track'
import { Mark, Meralco, Wordmark } from './Logo'
import { Alert, Bell, Close, Landmark, Office, Pylon } from './icons'

const NONE = []

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

// The map key. It folds away while an interruption is open so it does not cover the zone.
function Legend({ layers, zone, folded }) {
  const [open, setOpen] = useState(true)
  useEffect(() => { setOpen(!folded) }, [folded])
  return (
    <div className={`map-key${open ? '' : ' closed'}`}>
      <button className="legend-toggle" onClick={() => setOpen((o) => !o)} aria-expanded={open}>{open ? 'Hide key' : 'Map key'}</button>
      {open && (
        <div className="key-body">
          <section>
            <h4>Power interruptions</h4>
            <ul>
              <li><i className="dot t-critical">!</i>Critical customers</li>
              <li><i className="dot t-high">!</i>Community services</li>
              <li><i className="dot t-medium">!</i>Residential</li>
            </ul>
            <p className="lg-note">The number beside a pin is how many outage reports are linked to it.</p>
          </section>
          {zone && (
            <section>
              <h4>Inside the zone</h4>
              <ul>
                <li><i className="lg-num first">1</i>Check first</li>
                <li><i className="lg-num">2</i>Next, in order</li>
                <li><i className="lg-num hold">II</i>On hold</li>
                <li><i className="lg-num done">✓</i>Resolved</li>
                {Object.keys(EQUIPMENT_NAME).map((kind) => (
                  <li key={kind}><svg className="lg-mark" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round"><path d={EQUIPMENT_ICON[kind]} /></svg>{EQUIPMENT_NAME[kind]}</li>
                ))}
                <li><i className="lg-road" />Crew&rsquo;s road route</li>
              </ul>
            </section>
          )}
          {layers.grid && (
            <section>
              <h4>Power network</h4>
              <ul>
                <li><i className="lg-eq lg-sub" />Substation</li>
                <li><i className="lg-line" style={{ borderTopWidth: 4 }} />Main line</li>
                <li><i className="lg-line" style={{ borderTopWidth: 2 }} />Branch line</li>
                <li><i className="lg-eq lg-tx" />Transformer</li>
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

function Drawer({ open, onClose, basemap, onReplay, onPage }) {
  if (!open) return null
  return (
    <div className="drawer-wrap" onClick={onClose}>
      <nav className="drawer" onClick={(e) => e.stopPropagation()} aria-label="Menu">
        <div className="drawer-head"><Wordmark /><button className="icon-btn" onClick={onClose} aria-label="Close menu"><Close size={16} /></button></div>
        <div className="drawer-group">
          <button className="drawer-item" onClick={() => { onReplay(); onClose() }}><strong>Replay the typhoon</strong><span>Shows the storm crossing Luzon again, on a new track</span></button>
          <button className="drawer-item" onClick={() => { onPage('history'); onClose() }}><strong>History</strong><span>Past typhoons: what happened and how fast power came back</span></button>
          <button className="drawer-item" onClick={() => { onPage('reports'); onClose() }}><strong>Reports</strong><span>Export a PDF report for any typhoon</span></button>
        </div>
        <p className="drawer-foot muted small">
          {basemap === 'google' ? 'Map: Google Maps.' : 'Map: free OpenStreetMap map. Add a Google Maps key to frontend/.env.local to switch.'}
          {' '}The storm and the interruptions are invented for this demo; place names are real.
        </p>
        <div className="drawer-brand"><Meralco /></div>
      </nav>
    </div>
  )
}

export default function App() {
  const [state, setState] = useState(null)              // the service area: barangays and the power network
  const [error, setError] = useState(null)
  // The app opens on the typhoon itself. Interruptions only exist once it has passed.
  const [phase, setPhase] = useState('before')          // before | passing | after
  const [trackSeed, setTrackSeed] = useState(() => Math.floor(Math.random() * 1e9))
  const [tick, setTick] = useState(null)                // where the storm is while it passes
  const [cases, setCases] = useState([])                // the interruptions, each with Liwa's decision once made
  const [offices, setOffices] = useState([])            // Meralco offices on the map: the crew comes from the nearest one
  const [caseBusy, setCaseBusy] = useState(null)        // id of the interruption being ranked
  const [caseError, setCaseError] = useState(null)
  const [runningAll, setRunningAll] = useState(false)
  const [lastDecision, setLastDecision] = useState(null)
  const [sel, setSel] = useState(null)                  // the open interruption: { kind: 'case', id }
  const [resolved, setResolved] = useState({})          // per interruption: the poles marked resolved on screen
  const [picked, setPicked] = useState(null)            // the pole whose route was asked for; none = the first in the order
  const [route, setRoute] = useState(null)              // where the drawn route came from: loading | google | osm | none
  const [told, setTold] = useState({})                  // per interruption: what customers reported
  const [shift, setShift] = useState({})                // per interruption: the last change of conditions, and where everything stood before it
  const [layers, setLayers] = useState({ cases: true, landmarks: false, grid: false, offices: false })
  const [menu, setMenu] = useState(false)
  const [page, setPage] = useState(null)                // the records page over the map: history | reports
  const [notesOpen, setNotesOpen] = useState(false)
  const [notes, setNotes] = useState([])
  const [toasts, setToasts] = useState([])
  const [unread, setUnread] = useState(0)
  const [basemap, setBasemap] = useState(null)
  const [sheet, setSheet] = useState(false)
  const mobile = useIsMobile()
  const counter = useRef(0)
  const officesTold = useRef(false)

  const open = useCallback((s) => { setSel(s); setPicked(null); setSheet(true); setCaseError(null) }, [])
  const close = () => setSel(null)

  const toast = useCallback((found) => {
    const time = new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
    const stamped = found.map((n) => ({ ...n, id: ++counter.current, time }))
    setNotes((old) => [...stamped.slice().reverse(), ...old].slice(0, 30))
    setUnread((u) => u + stamped.length)
    setToasts((old) => [...old, ...stamped].slice(-3))
    stamped.forEach((n) => setTimeout(() => setToasts((old) => old.filter((t) => t.id !== n.id)), 6000))
  }, [])

  useEffect(() => {
    api.state().then(setState).catch((e) => setError(e.message))
    fetch(`${import.meta.env.BASE_URL}grid/meralco-osm.json`).then((r) => r.json()).then((d) => setOffices(d.offices ?? [])).catch(() => {})
    api.cases().then((d) => setCases(d.cases)).catch((e) => setError(e.message))
  }, [])

  const allClear = state?.event.all_clear
  const track = useMemo(() => (allClear ? makeTrack(trackSeed, allClear) : null), [trackSeed, allClear])
  const intro = phase !== 'after' && Boolean(track)
  const replay = useCallback(() => {
    setTrackSeed(Math.floor(Math.random() * 1e9)); setTick(null); setSel(null); setResolved({}); setPhase('before')
  }, [])
  const count = cases.length
  const reveal = useCallback(() => {
    setPhase('after'); setTick(null)
    toast([{ tone: 'info', title: 'The typhoon has passed', body: `${count} power interruptions are waiting. Open one to see what to check first.` }])
  }, [toast, count])

  // Liwa ranks an interruption when it is opened.
  const decideCase = useCallback(async (id, force = false) => {
    setCaseBusy(id); setCaseError(null)
    try {
      const decision = await api.caseDecision(id, force)
      setCases((list) => list.map((c) => (c.id === id ? { ...c, decision } : c)))
      setLastDecision(decision)
    } catch (e) {
      setCaseError(e.message)
    }
    setCaseBusy(null)
  }, [])
  const runAllCases = async () => {
    setRunningAll(true)
    for (const c of cases) await decideCase(c.id, true)      // one at a time: each is a call to Claude
    setRunningAll(false)
  }
  const openCase = sel ? cases.find((c) => c.id === sel.id) : null
  // One ranking for the map and the panel. Resolving a pole takes it out, and the next one becomes the first.
  const done = openCase ? resolved[openCase.id] ?? NONE : NONE
  const rank = openCase ? ranking(openCase, done) : null
  const active = rank ? (rank.go.find((j) => j.pole_id === picked) ?? rank.go[0])?.pole_id ?? null : null
  const resolve = (id, pole) => { setResolved((r) => ({ ...r, [id]: [...(r[id] ?? []), pole] })); setPicked(null) }
  const undo = (id, pole) => { setResolved((r) => ({ ...r, [id]: (r[id] ?? []).filter((p) => p !== pole) })); setPicked(null) }
  // Conditions changed at something on hold (made safe, flood cleared): the server records it
  // and Liwa ranks the interruption again as it now stands. What was resolved on screen is recorded at the same time.
  const changeCondition = async (id, pole, change) => {
    const now = cases.find((c) => c.id === id)
    const before = now?.decision ? standing(ranking(now, resolved[id] ?? NONE)) : {}
    setCaseBusy(id); setCaseError(null); setPicked(null)
    try {
      const next = await api.caseCondition(id, { pole_id: pole, change, done: resolved[id] ?? [] })
      setResolved((r) => ({ ...r, [id]: [] }))
      setShift((s) => ({ ...s, [id]: { pole, change, before } }))
      setCases((list) => list.map((c) => (c.id === id ? next : c)))
      const decision = await api.caseDecision(id)
      setCases((list) => list.map((c) => (c.id === id ? { ...c, decision } : c)))
      setLastDecision(decision)
    } catch (e) {
      setCaseError(e.message)
    }
    setCaseBusy(null)
  }
  const restartCase = async (id) => {
    setCaseBusy(id); setCaseError(null); setPicked(null)
    try {
      const next = await api.caseRestart(id)
      setResolved((r) => ({ ...r, [id]: [] }))
      setShift((s) => ({ ...s, [id]: null }))
      setCases((list) => list.map((c) => (c.id === id ? next : c)))
      const decision = await api.caseDecision(id)
      setCases((list) => list.map((c) => (c.id === id ? { ...c, decision } : c)))
    } catch (e) {
      setCaseError(e.message)
    }
    setCaseBusy(null)
  }
  useEffect(() => {
    if (openCase && !openCase.decision && !caseBusy) decideCase(openCase.id)
    if (openCase && !told[openCase.id]) api.caseReports(openCase.id).then((d) => setTold((t) => ({ ...t, [d.case_id]: d }))).catch(() => {})
  }, [openCase?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  // Where the map looks: every interruption at once, or the open one's zone together with the office the crew comes from.
  const focus = useMemo(() => {
    if (!state || phase !== 'after' || !cases.length) return null
    if (!sel) return { key: `all-${cases.length}`, bounds: L.latLngBounds([...state.areas.map((a) => a.pos), ...cases.map((c) => c.place?.pos).filter(Boolean)]), maxZoom: 12 }
    const index = cases.findIndex((c) => c.id === sel.id)
    if (index < 0) return null
    const plan = caseLayout(cases[index], index, state.areas, offices)
    const bounds = L.latLng(plan.center).toBounds(plan.radius * 2.15)
    if (plan.office && plan.office.km < 9) bounds.extend(plan.office.pos)
    return { key: `c-${sel.id}-${offices.length}`, bounds, maxZoom: 15.5 }
  }, [sel?.id, phase, cases.length, offices.length, Boolean(state)]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!state) {
    return <div className="boot"><Mark size={44} /><p>{error ? `Can't reach the FirstLook server. Start the backend on port 8000, then reload. (${error})` : 'Loading…'}</p></div>
  }

  const toggle = (k) => {
    if (k === 'offices' && !layers[k] && !officesTold.current) {
      officesTold.current = true
      toast([{ tone: 'info', title: 'Showing Meralco offices', body: OFFICE_NOTE }])
    }
    setLayers((l) => ({ ...l, [k]: !l[k] }))
  }
  const chips = [['cases', 'Interruptions', Alert], ['landmarks', 'Landmarks', Landmark], ['grid', 'Meralco grid', Pylon], ['offices', 'Meralco offices', Office]]

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

      <MapView state={state} layers={layers} focus={focus} padLeft={420} mobile={mobile}
        typhoon={intro ? { track, running: phase === 'passing', onTick: setTick, onDone: reveal } : null}
        cases={cases} offices={offices} openId={sel?.id ?? null} active={active} resolved={done}
        onSelectCase={(id) => open({ kind: 'case', id })} onPickPole={setPicked} onRoute={setRoute}
        onBasemap={setBasemap} onError={setError} />
      {intro ? (
        <TyphoonPanel name={state.event.name} track={track} running={phase === 'passing'} tick={tick}
          onStart={() => setPhase('passing')} onSkip={reveal} />
      ) : (
        <>
          <Panel state={state} cases={cases} offices={offices} sel={sel} open={open} back={close} close={close}
            onMenu={() => setMenu(true)} sheet={sheet} setSheet={setSheet}
            caseBusy={caseBusy} caseError={caseError} onDecideCase={decideCase}
            rank={rank} active={active} route={route} told={openCase ? told[openCase.id] : null} shift={openCase ? shift[openCase.id] : null}
            onChange={changeCondition} onRestart={restartCase}
            onPickPole={setPicked} onResolve={resolve} onUndo={undo} />
          <div className="map-chips" role="group" aria-label="Map layers">
            {chips.map(([k, label, Icon]) => (
              <button key={k} className={layers[k] ? 'mchip on' : 'mchip'} aria-pressed={layers[k]} onClick={() => toggle(k)}><Icon size={15} />{label}</button>
            ))}
          </div>
          {!mobile && <Legend layers={layers} zone={Boolean(sel)} folded={Boolean(sel)} />}
          <Assistant cases={cases} busy={Boolean(caseBusy)} running={runningAll} lastDecision={lastDecision}
            mobile={mobile} sheetOpen={sheet} onRunAll={runAllCases} />
        </>
      )}

      <div className="top-right">
        <button className="icon-btn raised bell" onClick={() => { setNotesOpen((o) => !o); setUnread(0) }} aria-label={`Notifications, ${unread} new`}>
          <Bell />{unread > 0 && <span className="badge">{unread}</span>}
        </button>
        {notesOpen && (
          <div className="popover">
            <div className="pop-head"><strong>Notifications</strong><button className="icon-btn" onClick={() => setNotesOpen(false)} aria-label="Close notifications"><Close size={14} /></button></div>
            {notes.length === 0 && <p className="muted">Nothing yet.</p>}
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

      <Drawer open={menu} onClose={() => setMenu(false)} basemap={basemap} onReplay={replay} onPage={setPage} />
      {page && <Records tab={page} onTab={setPage} onClose={() => setPage(null)} />}
    </div>
  )
}
