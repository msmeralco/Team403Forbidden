// The side panel. Three tabs and nothing else:
//   Check next     the ranked list of places to look at
//   Damage found   what has been confirmed and is waiting for Meralco's repair teams
//   Messages       what residents sent
// Opening any item shows one short page: why, what to look for, how to get there, what was found.
import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import { SOURCES, SOURCE_ORDER, TIERS, about, areaTier, clock, fmt, gmaps, plural } from '../theme'
import { Alert, Back, Check, Close, External, Menu, Pin, Quiet, Search, Shield } from '../icons'
import { ReportFull, ReportRow, SourceBadge } from './ReportCard'
import { PIN_MESSAGES } from '../features'
import { METERS, ZONES, suspects } from '../map/network'

const first = (names) => names.map((n) => n.split(',')[0]).join(', ')

function Banner({ tier, children }) {
  return <div className={`banner t-${tier}`}><span className="banner-dot" /><div><strong>{TIERS[tier].label}</strong>{children && <span>{children}</span>}</div></div>
}

// ---------------------------------------------------------------------------
// Check next: the ranked list
// ---------------------------------------------------------------------------
function PriorityItem({ r, open }) {
  const people = r.covers.people
  return (
    <li className={`prio t-${r.tier}`}>
      <button className="prio-main" onClick={() => open({ kind: 'priority', id: r.asset_id })}>
        <span className={`rank t-${r.tier}`}>{r.rank}</span>
        <span className="prio-body">
          <span className={`prio-tier t-${r.tier}`}>{TIERS[r.tier].label}</span>
          <strong className="prio-name">{r.name}</strong>
          <span className="prio-why">{r.headline}</span>
          <span className="prio-meta">{people > 0 ? `${plural(people, 'person', 'people')} reporting, ` : ''}{r.travel_min} min away</span>
        </span>
      </button>
    </li>
  )
}

function CheckNext({ state, open, setTab }) {
  const [more, setMore] = useState(false)
  const main = state.recommendations.filter((r) => r.tier !== 'low')
  const rest = state.recommendations.filter((r) => r.tier === 'low')
  const ready = state.handoff.length
  return (
    <div className="tab-body">
      {ready > 0 && (
        <button className="found" onClick={() => setTab('found')}>
          <Shield size={16} /><span><strong>{plural(ready, 'damaged spot')} found</strong> and waiting for repair. See the list.</span>
        </button>
      )}
      {main.length > 0 && <p className="intro">Ranked in this order: <b>1</b> safety, <b>2</b> essential facilities, <b>3</b> position in the network, <b>4</b> customers and load, then reports and travel time.</p>}
      <ol className="prios">
        {main.map((r) => <PriorityItem key={r.asset_id} r={r} open={open} />)}
        {more && rest.map((r) => <PriorityItem key={r.asset_id} r={r} open={open} />)}
      </ol>
      {main.length === 0 && (state.summary.areas_reporting === 0 && state.repaired.length > 0
        ? <p className="found static"><Check size={16} /><span><strong>All clear.</strong> Every barangay that reported an outage has power back.</span></p>
        : <p className="note">Nothing urgent is left to check.</p>)}
      {rest.length > 0 && (
        <button className="btn ghost wide" onClick={() => setMore((m) => !m)}>
          {more ? 'Hide the less urgent places' : `Show ${rest.length} less urgent places`}
        </button>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Damage found: confirmed damage, then what is finished
// ---------------------------------------------------------------------------
// FirstLook does not rank or do repairs. It lists what each repair would bring back; Meralco decides.
function HandoffCard({ h, open, run }) {
  const r = h.restores
  const blocked = h.blocked_by.length > 0
  return (
    <li className={`handoff${blocked ? ' blocked' : ''}`}>
      <button className="linkish" onClick={() => open({ kind: 'priority', id: h.asset_id })}>
        <strong className="prio-name">{h.name}</strong>
        <span className="muted">{h.place}</span>
      </button>
      {h.hazards.length > 0 && <p className="hand-line danger"><Alert size={15} />{h.hazards.map((x) => `${x.label} in ${x.area}`).join(', ')}</p>}
      {blocked
        ? <p className="hand-line warn"><Alert size={15} />Fix {h.blocked_by[0]} first. This repair can't help until then.</p>
        : (r.sure.length > 0 || r.maybe.length > 0) && (
          <p className="hand-line"><Check size={15} /><span>Fixing this brings back about <b>{about(r.sure_accounts + r.maybe_accounts)}</b> customer accounts in {first([...r.sure, ...r.maybe])}.</span></p>
        )}
      {r.still_dark.length > 0 && <p className="hand-line warn"><Alert size={15} /><span>{first(r.still_dark)} would stay dark. Another break is likely.</span></p>}
      {!blocked && <button className="btn sm" onClick={() => run(() => api.repair(h.asset_id, ''))}>Mark as repaired</button>}
    </li>
  )
}

function Found({ state, open, run }) {
  const intact = state.log.filter((o) => o.result === 'intact')
  return (
    <div className="tab-body">
      {state.handoff.length === 0
        ? <p className="note">No confirmed damage is waiting for repair. When a visit finds damage, it appears here.</p>
        : (
          <>
            <p className="intro">Damage confirmed on site. Meralco's repair teams decide the order; this shows what each repair brings back.</p>
            <ul className="handoffs">{state.handoff.map((h) => <HandoffCard key={h.asset_id} h={h} open={open} run={run} />)}</ul>
          </>
        )}
      {state.repaired.length > 0 && (
        <section className="excluded">
          <h3>Repaired</h3>
          {state.repaired.map((x) => (
            <div key={x.asset_id} className="done-row">
              <button className="ex-row" onClick={() => open({ kind: 'priority', id: x.asset_id })}>
                <span className="ex-name"><i className="dot t-restored">✓</i>{x.name}</span>
                <span className="muted small">{clock(x.time)}</span>
              </button>
              {x.back.length > 0 && <p className="muted small">Power back: {first(x.back)}</p>}
              {x.still_dark.length > 0 && <p className="small warn-text">Still dark: {first(x.still_dark)}. Another break is being looked for.</p>}
            </div>
          ))}
        </section>
      )}
      {intact.length > 0 && (
        <section className="excluded">
          <h3>Checked, no damage</h3>
          {intact.map((o) => (
            <button key={o.id} className="ex-row" onClick={() => open({ kind: 'priority', id: o.asset_id })}>
              <span className="ex-name"><i className="dot t-checked" />{o.asset_name}</span>
              <span className="muted small">{clock(o.time)}</span>
            </button>
          ))}
        </section>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// One place
// ---------------------------------------------------------------------------
function HazardAlert({ a, run, named }) {
  return (
    <div className={`alert${a.hazard_open ? '' : ' safe'}`}>
      {a.hazard_open ? <Alert size={18} /> : <Shield size={18} />}
      <div>
        <strong>{Object.keys(a.hazards).join(', ')}{named ? ` in Brgy. ${a.barangay}` : ''}</strong>
        <span>{a.hazard_open ? 'Keep people away until it is made safe.' : `Made safe by ${a.hazard_handled_by}.`}</span>
      </div>
      {a.hazard_open && <button className="btn sm" onClick={() => run(() => api.hazard(a.id, true))}>Mark as made safe</button>}
    </div>
  )
}

function WhatWasFound({ id, run }) {
  const [busy, setBusy] = useState(false)
  const save = async (result) => { setBusy(true); await run(() => api.observe(id, result)); setBusy(false) }
  return (
    <section className="record">
      <h3>What was found there?</h3>
      <div className="found-btns">
        <button className="btn primary" disabled={busy} onClick={() => save('damaged')}>Damage found</button>
        <button className="btn" disabled={busy} onClick={() => save('intact')}>No damage</button>
        <button className="btn" disabled={busy} onClick={() => save('inconclusive')}>Couldn't tell</button>
      </div>
      <p className="muted small">The list re-ranks as soon as you answer.</p>
    </section>
  )
}

function PriorityDetail({ state, id, open, run }) {
  const asset = state.assets.find((a) => a.id === id)
  const rec = state.recommendations.find((r) => r.asset_id === id)
  const hazardAreas = state.areas.filter((a) => a.transformer === id && Object.keys(a.hazards).length)
  const done = asset.status === 'damaged' || asset.status === 'intact'
  const hand = state.handoff.find((h) => h.asset_id === id)
  const fixed = state.repaired.find((x) => x.asset_id === id)
  const found = state.log.find((o) => o.asset_id === id)
  const tier = rec?.tier ?? (fixed ? 'restored' : asset.status === 'damaged' ? 'confirmed' : done ? 'checked' : 'low')
  const status = rec ? `Number ${rec.rank} on the list`
    : fixed ? `Repaired, ${clock(fixed.time)}`
      : asset.status === 'damaged' ? `Found by ${found?.by}`
        : asset.status === 'intact' ? 'Checked, no damage' : 'Not on the list right now'

  return (
    <div className="detail">
      <Banner tier={tier}>{status}</Banner>
      <h2>{asset.name}</h2>
      <p className="muted place"><Pin size={15} />{asset.place}</p>

      {hazardAreas.map((a) => <HazardAlert key={a.id} a={a} run={run} named />)}

      {rec && (
        <section>
          <h3>Why it is number {rec.rank}</h3>
          <ol className="why">
            <li className={rec.basis.safety.length ? 'on' : ''}>
              <b>Safety</b>
              <span>{rec.basis.safety.length ? `${rec.basis.safety.join('; ')}, still open.` : 'No open hazard here.'}</span>
            </li>
            <li className={rec.basis.essential.length ? 'on' : ''}>
              <b>Essential facilities</b>
              <span>{rec.basis.essential.length ? `${rec.basis.essential.map((e) => `${e.name} in ${e.area}`).join(', ')}: likely without power.` : 'None behind this place.'}</span>
            </li>
            <li className="on">
              <b>Network</b>
              <span>{rec.basis.level_label}. {rec.basis.level === 1 ? 'Everything further down the line depends on it.' : rec.basis.level === 4 ? 'The last step before the houses.' : 'Feeds the lines and transformers after it.'}</span>
            </li>
            <li className={rec.basis.reported_people || rec.basis.predicted_accounts ? 'on' : ''}>
              <b>Customers and load</b>
              <span>About {about(rec.basis.predicted_accounts)} accounts predicted without power, roughly {rec.basis.load_mw} MW. {plural(rec.basis.reported_people, 'person', 'people')} reported. {Math.round(rec.basis.p_damaged * 100)}% chance the damage is here.</span>
            </li>
          </ol>
        </section>
      )}
      {!done && (
        <section>
          <h3>What to look for</h3>
          <p>{asset.objective}</p>
        </section>
      )}
      {!done && (
        <section>
          <h3>Getting there</h3>
          {rec && <p>{rec.travel_min} min drive from the {rec.from}{rec.route.via.length ? `, via ${rec.route.via.join(', ')}` : ''}.</p>}
          <a className="btn sm" href={gmaps(asset.pos)} target="_blank" rel="noreferrer"><External size={15} />Open in Google Maps</a>
        </section>
      )}

      {hand && (
        <section>
          <h3>Waiting for repair</h3>
          <ul className="handoffs"><HandoffCard h={hand} open={() => {}} run={run} /></ul>
        </section>
      )}
      {fixed && (
        <section>
          <h3>After the repair</h3>
          {fixed.back.length > 0 && <p>Power is back in {first(fixed.back)}.</p>}
          {fixed.still_dark.length > 0 && <p className="warn-text">Still dark: {first(fixed.still_dark)}. Residents say so, which means another break; it is back on the Check next list.</p>}
        </section>
      )}

      {!done && <WhatWasFound id={id} run={run} />}
    </div>
  )
}

// ---------------------------------------------------------------------------
// One barangay
// ---------------------------------------------------------------------------
function useLimited(list, step = 30) {
  const [n, setN] = useState(step)
  return [list.slice(0, n), list.length > n ? () => setN((x) => x + step) : null]
}

function AreaDetail({ state, reports, id, open, run, now, onShowPath, pathShown, zoneKm, setZoneKm }) {
  const a = state.areas.find((x) => x.id === id)
  const mine = useMemo(() => reports.filter((r) => r.area_id === id), [reports, id])
  const [list, more] = useLimited(mine)
  const tier = areaTier(a) ?? 'ok'
  const chain = suspects(state, id)
  const STATUS = {
    check: (x) => `${Math.round(x.rec.basis.p_damaged * 100)}% chance the damage is here`,
    unlikely: () => 'Unlikely: the evidence points elsewhere',
    found: () => 'Damage found, waiting for repair',
    repaired: () => 'Repaired',
    clear: () => 'Checked, no damage',
  }

  return (
    <div className="detail">
      <Banner tier={tier}>{TIERS[tier].hint}</Banner>
      <h2>Brgy. {a.barangay}</h2>
      <p className="muted place"><Pin size={15} />{a.city}</p>

      {Object.keys(a.hazards).length > 0 && <HazardAlert a={a} run={run} />}
      {(a.restored_msgs > 0 || a.still_dark_msgs > 0) && (
        <div className={`alert ${a.restored ? 'safe' : 'quiet'}`}>
          {a.restored ? <Check size={18} /> : <Alert size={18} />}
          <div>
            <strong>{a.restored ? 'Power is back' : 'Still dark after a repair'}</strong>
            <span>{a.restored ? `${plural(a.restored_msgs, 'resident')} confirmed it.` : `${plural(a.still_dark_msgs, 'resident')} say there is still no power, so another break is likely.`}</span>
          </div>
        </div>
      )}
      {a.quiet && !a.restored && (
        <div className="alert quiet">
          <Quiet size={18} />
          <div><strong>Quiet area</strong><span>Only {plural(a.people, 'person', 'people')} reported, but about {a.expected_people} would be expected. Phones may be dead or people evacuated.</span></div>
        </div>
      )}

      <p className="lead">
        {a.people > 0 ? <><b>{plural(a.people, 'person', 'people')}</b> reported no power here, in {plural(a.reports, 'message')}.</> : 'Nobody has reported from here yet.'}
        {a.vulnerable > 0 && ` ${plural(a.vulnerable, 'message')} mention someone elderly, sick or very young.`}
        {a.critical.length > 0 && ` Also here: ${a.critical.join(', ')}.`}
      </p>

      <section>
        <h3>Possible affected infrastructure</h3>
        <div className="seg-row" role="group" aria-label="Zone around this case">
          {[...ZONES, null].map((k) => (
            <button key={k ?? 'all'} className={zoneKm === k ? 'seg-btn on' : 'seg-btn'} aria-pressed={zoneKm === k} onClick={() => setZoneKm(k)}>{k ? `${k} km` : 'Whole path'}</button>
          ))}
        </div>
        <p className="muted small">
          {zoneKm ? `The circle on the map is ${zoneKm} km around this case. Equipment inside it that could be why these houses are dark, in the order to check it:`
            : `Everything between the ${state.substation.name.toLowerCase()} and these houses, in the order to check it:`}
        </p>
        {[['in', chain.filter((x) => !zoneKm || x.away <= zoneKm)], ['out', chain.filter((x) => zoneKm && x.away > zoneKm)]].map(([where, list]) => list.length > 0 && (
          <div key={where} className="suspect-group">
            {where === 'out' && <h4>Further up the line, outside the zone</h4>}
            <ol className={`suspects${where === 'out' ? ' outside' : ''}`}>
              {list.map((x) => (
                <li key={x.asset.id}>
                  <button onClick={() => open({ kind: 'priority', id: x.asset.id })}>
                    {x.status === 'check'
                      ? <span className={`rank t-${x.rec.tier}`}>{x.rec.rank}</span>
                      : <span className={`rank mark is-${x.status}`}>{x.status === 'unlikely' ? '' : x.status === 'found' ? '!' : '✓'}</span>}
                    <span><strong>{x.asset.name}</strong><span className="muted">{x.level}. {STATUS[x.status](x)}</span></span>
                  </button>
                </li>
              ))}
            </ol>
          </div>
        ))}
        {zoneKm && chain.every((x) => x.away > zoneKm) && <p className="note">No equipment on this barangay's supply path sits inside {zoneKm} km. Widen the zone.</p>}
        <p className="muted small">The map also draws {METERS} of about {about(a.accounts)} meters here.</p>
        <button className="btn sm" onClick={() => onShowPath(id)}>{pathShown === id ? 'Back to the zone' : 'Zoom in to the houses and meters'}</button>
      </section>

      {PIN_MESSAGES && mine.length > 0 && (
        <section>
          <h3>{plural(mine.length, 'message')} from here</h3>
          <ul className="reports">{list.map((r) => <ReportRow key={r.id} r={r} now={now} showPlace={false} onOpen={() => open({ kind: 'report', id: r.id })} />)}</ul>
          {more && <button className="btn ghost wide" onClick={more}>Show more</button>}
        </section>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Messages
// ---------------------------------------------------------------------------
function ChannelBar({ bySource }) {
  const total = Object.values(bySource).reduce((s, n) => s + n, 0)
  if (!total) return null
  return (
    <div className="chbar">
      <div className="chbar-track">{SOURCE_ORDER.filter((k) => bySource[k]).map((k) => <i key={k} className={`s-${k}`} style={{ flexGrow: bySource[k] }} title={`${SOURCES[k].label}: ${bySource[k]}`} />)}</div>
      <ul className="chbar-legend">{SOURCE_ORDER.filter((k) => bySource[k]).map((k) => <li key={k}><SourceBadge source={k} size={18} />{SOURCES[k].short}<b>{bySource[k]}</b></li>)}</ul>
    </div>
  )
}

const KINDS = [[null, 'Everything'], ['hazard', 'Safety hazards'], ['vulnerable', 'Vulnerable people'], ['photo', 'With a photo'], ['caught', 'Caught by AI']]
const inKind = (r, k) => !k || (k === 'vulnerable' ? r.vulnerable : k === 'caught' ? Boolean(r.caught) : k === 'photo' ? Boolean(r.photo) : r.category === k)

function Messages({ state, reports, open, now, kind, setKind }) {
  const filtered = reports.filter((r) => inKind(r, kind))
  const [list, more] = useLimited(filtered)
  const count = (k) => reports.filter((r) => inKind(r, k)).length
  return (
    <div className="tab-body">
      <p className="intro">{fmt(state.summary.reports)} messages from {fmt(state.summary.people)} people. Someone who used several channels counts once.</p>
      <ChannelBar bySource={state.summary.by_source} />
      <div className="filter-row" role="group" aria-label="Show">
        {KINDS.filter(([k]) => !k || count(k) > 0).map(([k, label]) => (
          <button key={label} className={kind === k ? 'fchip on' : 'fchip'} onClick={() => setKind(k)}>{label}{k && <span className="muted">{count(k)}</span>}</button>
        ))}
      </div>
      <ul className="reports">{list.map((r) => <ReportRow key={r.id} r={r} now={now} onOpen={() => open({ kind: 'report', id: r.id })} />)}</ul>
      {more && <button className="btn ghost wide" onClick={more}>Show more</button>}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------
function SearchResults({ q, state, reports, open, done }) {
  const s = q.trim().toLowerCase()
  const areas = state.areas.filter((a) => `${a.barangay} ${a.city}`.toLowerCase().includes(s)).slice(0, 5)
  const places = state.assets.filter((a) => `${a.name} ${a.place}`.toLowerCase().includes(s)).slice(0, 4)
  const msgs = reports.filter((r) => `${r.text} ${r.author}`.toLowerCase().includes(s)).slice(0, 4)
  const go = (sel) => { open(sel); done() }
  if (!areas.length && !places.length && !msgs.length) return <div className="search-results"><p className="muted pad">Nothing found for “{q}”. Try a barangay or city name.</p></div>
  return (
    <div className="search-results">
      {areas.length > 0 && <h4>Barangays</h4>}
      {areas.map((a) => <button key={a.id} onClick={() => go({ kind: 'area', id: a.id })}><Pin size={16} /><span>Brgy. {a.barangay}<small className="muted">{a.city}</small></span></button>)}
      {places.length > 0 && <h4>Places to check</h4>}
      {places.map((a) => <button key={a.id} onClick={() => go({ kind: 'priority', id: a.id })}><Pin size={16} /><span>{a.name}<small className="muted">{a.place}</small></span></button>)}
      {msgs.length > 0 && <h4>Messages</h4>}
      {msgs.map((r) => <button key={r.id} onClick={() => go({ kind: 'report', id: r.id })}><SourceBadge source={r.source} size={18} /><span className="clip">{r.text || r.meta.outage_type}<small className="muted">{r.author}, Brgy. {r.barangay}</small></span></button>)}
    </div>
  )
}

// The AI reader only gets a line when it is actually doing something.
function AiLine({ ai, onShow }) {
  if (ai.status === 'reading') {
    return (
      <div className="ai-line">
        <span className="ai-chip">AI</span>
        <div><span>Reading messages: {fmt(ai.read)} of {fmt(ai.total)}</span><i className="ai-bar"><b style={{ width: `${ai.total ? (ai.read / ai.total) * 100 : 0}%` }} /></i></div>
      </div>
    )
  }
  if (ai.status !== 'done') return null
  return (
    <div className="ai-line">
      <span className="ai-chip">AI</span>
      <div>
        <span>Read {fmt(ai.total)} messages and {plural(ai.photos, 'photo')}.{' '}
          {ai.caught_reports > 0 ? `Caught ${fmt(ai.caught_reports)} that the keyword rules missed.` : 'Found nothing the keyword rules missed.'}</span>
        {ai.caught_reports > 0 && <button className="link" onClick={onShow}>Show them</button>}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// The panel
// ---------------------------------------------------------------------------
export default function Panel({ state, reports, sel, open, back, close, tab, setTab, run, onMenu, sheet, setSheet, onShowPath, pathShown, zoneKm, setZoneKm }) {
  const [q, setQ] = useState('')
  const [kind, setKind] = useState(null)
  const hazardAreas = state.areas.filter((a) => a.hazard_open)
  const scroller = useRef(null)
  useEffect(() => { if (scroller.current) scroller.current.scrollTop = 0 }, [sel?.kind, sel?.id, tab])
  const now = state.event.now
  const sum = state.summary
  const report = sel?.kind === 'report' && reports.find((r) => r.id === sel.id)
  const title = sel ? { priority: 'Place to check', area: 'Barangay', report: 'Message' }[sel.kind] : null
  const tabs = [
    ['check', 'Check next', state.recommendations.filter((r) => r.tier !== 'low').length],
    ['found', 'Damage found', state.handoff.length],
    ['messages', 'Messages', sum.reports],
  ]

  return (
    <aside className={`panel${sheet ? ' open' : ''}`} aria-label="FirstLook panel">
      <button className="sheet-handle" onClick={() => setSheet(!sheet)} aria-label={sheet ? 'Collapse panel' : 'Expand panel'}><i /></button>
      <div className="searchbar">
        <button className="icon-btn" onClick={onMenu} aria-label="Open menu"><Menu /></button>
        <Search size={18} className="muted" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search a barangay, city or message" aria-label="Search" />
        {q && <button className="icon-btn" onClick={() => setQ('')} aria-label="Clear search"><Close size={16} /></button>}
      </div>
      {q.trim().length >= 2 && <SearchResults q={q} state={state} reports={reports} open={open} done={() => setQ('')} />}

      <div className="panel-scroll" ref={scroller}>
        {sel ? (
          <>
            <div className="detail-nav">
              <button className="icon-btn" onClick={back} aria-label="Back"><Back /></button>
              <span>{title}</span>
              <button className="icon-btn" onClick={close} aria-label="Close"><Close size={16} /></button>
            </div>
            {sel.kind === 'priority' && <PriorityDetail state={state} id={sel.id} open={open} run={run} />}
            {sel.kind === 'area' && <AreaDetail key={sel.id} state={state} reports={reports} id={sel.id} open={open} run={run} now={now} onShowPath={onShowPath} pathShown={pathShown} zoneKm={zoneKm} setZoneKm={setZoneKm} />}
            {sel.kind === 'report' && report && (
              <ReportFull r={report} now={now} model={state.ai.model}
                also={reports.filter((o) => o.person_id === report.person_id && o.id !== report.id)}
                onOpen={(rid) => open({ kind: 'report', id: rid })} onArea={() => open({ kind: 'area', id: report.area_id })} />
            )}
          </>
        ) : (
          <>
            <header className="storm">
              <div className="storm-name"><h1>{state.event.name}</h1></div>
              {state.case && (
                <p className="case-line">
                  Test case, stage {state.case.stage} of {state.case.stages.length}.{' '}
                  {state.case.stage < state.case.stages.length
                    ? <button className="link" onClick={() => run(() => api.loadStage(state.case.id, state.case.stage + 1))}>Next: {state.case.stages[state.case.stage].name}</button>
                    : 'This is the last stage.'}
                </p>
              )}
              <p className="storm-line">
                {sum.areas_reporting > 0
                  ? <><b>{plural(sum.areas_reporting, 'barangay')}</b> {sum.areas_reporting === 1 ? 'reports' : 'report'} no power. </>
                  : 'No barangay is reporting an outage. '}
                {hazardAreas.length > 0
                  ? <button className="danger-link" onClick={() => open({ kind: 'area', id: hazardAreas[0].id })}>{plural(hazardAreas.length, 'safety hazard')} open</button>
                  : 'No safety hazards open.'}
              </p>
              <AiLine ai={state.ai} onShow={() => { setTab('messages'); setKind('caught') }} />
            </header>
            <nav className="tabs" role="tablist">
              {tabs.map(([k, label, count]) => (
                <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>
                  {label}{count > 0 && <span className="count">{count}</span>}
                </button>
              ))}
            </nav>
            {tab === 'check' && <CheckNext state={state} open={open} setTab={setTab} />}
            {tab === 'found' && <Found state={state} open={open} run={run} />}
            {tab === 'messages' && <Messages state={state} reports={reports} open={open} now={now} kind={kind} setKind={setKind} />}
          </>
        )}
      </div>
    </aside>
  )
}
