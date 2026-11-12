import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import {
  SOURCES, SOURCE_ORDER, TIERS, about, areaTier, clock, fmt, gmaps, likelihood, plural, tierRank,
} from '../theme'
import {
  Alert, Back, Check, Clock, Close, External, Home, Hospital, Menu, People, Pin, Quiet, Road, Search, Shield,
} from '../icons'
import { ReportFull, ReportRow, SourceBadge } from './ReportCard'

function Fact({ icon: Icon, value, label }) {
  return <span className="fact"><Icon size={15} /><b>{value}</b> {label}</span>
}

function Banner({ tier, children }) {
  return <div className={`banner t-${tier}`}><span className="banner-dot" /><div><strong>{TIERS[tier].label}</strong>{children && <span>{children}</span>}</div></div>
}

// ---------------------------------------------------------------------------
// Priorities
// ---------------------------------------------------------------------------
function PriorityItem({ r, open }) {
  return (
    <li className={`prio t-${r.tier}`}>
      <button className="prio-main" onClick={() => open({ kind: 'priority', id: r.asset_id })}>
        <span className={`rank t-${r.tier}`}>{r.rank}</span>
        <span className="prio-body">
          <span className={`prio-tier t-${r.tier}`}>{TIERS[r.tier].label}</span>
          <strong className="prio-name">{r.name}</strong>
          <span className="muted">{r.place}</span>
          <span className="prio-why">{r.headline}</span>
          <span className="facts">
            {r.covers.people > 0 && <Fact icon={People} value={fmt(r.covers.people)} label="reporting" />}
            {r.covers.accounts > 0 && <Fact icon={Home} value={about(r.covers.accounts)} label="accounts" />}
            {r.covers.critical.length > 0 && <Fact icon={Hospital} value={r.covers.critical.length} label="critical" />}
            <Fact icon={Clock} value={`${r.travel_min} min`} label={`from ${r.from}`} />
          </span>
        </span>
      </button>
    </li>
  )
}

function Priorities({ state, open, run, view, setView }) {
  const [more, setMore] = useState(false)
  const recs = state.recommendations
  const main = recs.filter((r) => r.tier !== 'low')
  const rest = recs.filter((r) => r.tier === 'low')
  const ready = state.handoff.length
  const doneCount = state.repaired.length + state.log.filter((o) => o.result === 'intact').length
  return (
    <div className="tab-body">
      <div className="seg-row wide" role="tablist" aria-label="Stage">
        <button role="tab" aria-selected={view === 'check'} className={view === 'check' ? 'seg-btn on' : 'seg-btn'} onClick={() => setView('check')}>Check next</button>
        <button role="tab" aria-selected={view === 'repair'} className={view === 'repair' ? 'seg-btn on' : 'seg-btn'} onClick={() => setView('repair')}>
          Ready for repair{ready > 0 && <span className="count">{ready}</span>}
        </button>
        <button role="tab" aria-selected={view === 'done'} className={view === 'done' ? 'seg-btn on' : 'seg-btn'} onClick={() => setView('done')}>
          Done{doneCount > 0 && <span className="count">{doneCount}</span>}
        </button>
      </div>

      {view === 'check' && (
        <>
          {ready > 0 && (
            <button className="found" onClick={() => setView('repair')}>
              <Shield size={16} /><span><strong>{plural(ready, 'damaged spot')} found</strong> and ready for repair. See the list.</span>
            </button>
          )}
          <p className="intro">The places worth checking first. Safety hazards stay on top; the rest are ranked by how many people are affected and how much one visit can clear up.</p>
          <ol className="prios">
            {main.map((r) => <PriorityItem key={r.asset_id} r={r} open={open} />)}
            {more && rest.map((r) => <PriorityItem key={r.asset_id} r={r} open={open} />)}
          </ol>
          {main.length === 0 && (state.summary.areas_reporting === 0 && state.repaired.length > 0
            ? <p className="found static"><Check size={16} /><span><strong>All clear.</strong> Every barangay that reported an outage has power back.</span></p>
            : <p className="note">Nothing urgent left to check. Remaining places would tell us very little.</p>)}
          {rest.length > 0 && (
            <button className="btn ghost wide" onClick={() => setMore((m) => !m)}>
              {more ? 'Hide low-priority places' : `Show ${rest.length} low-priority places`}
            </button>
          )}
          {state.excluded.length > 0 && (
            <section className="excluded">
              <h3>Can't be reached right now</h3>
              {state.excluded.map((e) => (
                <button key={e.asset_id} className="ex-row" onClick={() => open({ kind: 'priority', id: e.asset_id })}>
                  <span>{state.assets.find((a) => a.id === e.asset_id)?.name}</span>
                  <span className="muted small">Roads closed</span>
                </button>
              ))}
            </section>
          )}
        </>
      )}

      {view === 'repair' && <Handoff state={state} open={open} run={run} />}
      {view === 'done' && <Done state={state} open={open} />}
    </div>
  )
}

// Facts for the repair decision. FirstLook does not rank repairs; Meralco decides the order.
function HandoffCard({ h, open, run }) {
  const [by, setBy] = useState('')
  const r = h.restores
  return (
    <li className={`handoff${h.blocked_by.length ? ' blocked' : ''}`}>
      <button className="linkish" onClick={() => open({ kind: 'priority', id: h.asset_id })}>
        <strong className="prio-name">{h.name}</strong>
        <span className="muted">{h.place}. Found by {h.found_by}, {clock(h.found_at)}{h.notes ? `: ${h.notes}` : ''}</span>
      </button>
      {h.blocked_by.length > 0 && (
        <p className="hand-line warn"><Alert size={15} />Fix {h.blocked_by[0]} first. Nothing behind this can come back until then.</p>
      )}
      {h.hazards.length > 0 && <p className="hand-line danger"><Alert size={15} />Safety hazard here: {h.hazards.map((x) => `${x.label.toLowerCase()} in ${x.area}`).join(', ')}</p>}
      {!h.blocked_by.length && (r.sure.length > 0 || r.maybe.length > 0) && (
        <p className="hand-line"><Check size={15} />
          <span>Brings back about <b>{about(r.sure_accounts + r.maybe_accounts)}</b> customer accounts: {[...r.sure, ...r.maybe].map((n) => n.split(',')[0]).join(', ')}{r.maybe.length > 0 ? ` (${r.maybe.map((n) => n.split(',')[0]).join(', ')} only if nothing else is broken)` : ''}.</span>
        </p>
      )}
      {r.still_dark.length > 0 && (
        <p className="hand-line warn"><Alert size={15} /><span>Stays dark even after this: {r.still_dark.map((n) => n.split(',')[0]).join(', ')}. Another break is likely behind it.</span></p>
      )}
      {!h.blocked_by.length && h.p_upstream_damage >= 0.15 && (
        <p className="hand-line warn"><Alert size={15} /><span>{Math.round(h.p_upstream_damage * 100)}% chance something further up the line is also broken. Worth checking first.</span></p>
      )}
      {h.critical.length > 0 && <p className="hand-line"><Hospital size={15} /><span>{h.critical.join(', ')}</span></p>}
      {!h.blocked_by.length && (
        <div className="hand-actions">
          <input className="field-input" placeholder="Repaired by (optional)" value={by} onChange={(e) => setBy(e.target.value)} />
          <button className="btn primary sm" onClick={() => run(() => api.repair(h.asset_id, by))}>Mark as repaired</button>
        </div>
      )}
    </li>
  )
}

function Handoff({ state, open, run }) {
  if (!state.handoff.length) {
    return <p className="note">No confirmed damage waiting for repair yet. When someone records "Damage found" at a place, it appears here.</p>
  }
  return (
    <>
      <p className="intro">Confirmed damage, with what each repair would bring back. The repair order is Meralco's call; anything that can't help yet is marked.</p>
      <ul className="handoffs">{state.handoff.map((h) => <HandoffCard key={h.asset_id} h={h} open={open} run={run} />)}</ul>
    </>
  )
}

const RESULT = { damaged: ['Damage found', 'confirmed'], intact: ['No damage', 'checked'], inconclusive: ["Couldn't tell", 'low'] }

function Done({ state, open }) {
  const intact = state.log.filter((o) => o.result === 'intact')
  if (!state.repaired.length && !intact.length) return <p className="note">Nothing finished yet.</p>
  return (
    <>
      {state.repaired.length > 0 && (
        <section className="excluded">
          <h3>Repaired</h3>
          {state.repaired.map((x) => (
            <div key={x.asset_id} className="done-row">
              <button className="ex-row" onClick={() => open({ kind: 'priority', id: x.asset_id })}>
                <span className="ex-name"><i className="dot t-restored">✓</i>{x.name}</span>
                <span className="muted small">{clock(x.time)}, {x.by}</span>
              </button>
              {x.back.length > 0 && <p className="muted small">Power back: {x.back.map((n) => n.split(',')[0]).join(', ')}</p>}
              {x.still_dark.length > 0 && <p className="small warn-text">Still dark: {x.still_dark.map((n) => n.split(',')[0]).join(', ')}. Another break is being looked for.</p>}
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
              <span className="muted small">{clock(o.time)}, {o.by}</span>
            </button>
          ))}
        </section>
      )}
    </>
  )
}

function RecordResult({ id, run }) {
  const [result, setResult] = useState(null)
  const [by, setBy] = useState('')
  const [notes, setNotes] = useState('')
  const choices = [['damaged', 'Damage found'], ['intact', 'No damage'], ['inconclusive', "Couldn't tell"]]
  const save = async () => {
    const ok = await run(() => api.observe(id, result, notes, by))
    if (ok) { setResult(null); setNotes('') }
  }
  return (
    <section className="record">
      <h3>Record what was found</h3>
      <p className="muted small">When someone reports back from this spot, enter it here. The list re-ranks right away.</p>
      <div className="seg-row" role="radiogroup" aria-label="What was found">
        {choices.map(([k, label]) => (
          <button key={k} role="radio" aria-checked={result === k} className={result === k ? 'seg-btn on' : 'seg-btn'} onClick={() => setResult(k)}>{label}</button>
        ))}
      </div>
      <input className="field-input" placeholder="Reported by (optional), e.g. Line crew 4" value={by} onChange={(e) => setBy(e.target.value)} />
      <input className="field-input" placeholder="Notes (optional), e.g. broken crossarm" value={notes} onChange={(e) => setNotes(e.target.value)} />
      <button className="btn primary" disabled={!result} onClick={save}>Save result</button>
    </section>
  )
}

function Technical({ assetId, version }) {
  const [data, setData] = useState(null)
  const [opened, setOpened] = useState(false)
  useEffect(() => {
    if (!opened) return undefined
    let live = true
    api.explain(assetId).then((d) => live && setData(d)).catch(() => {})
    return () => { live = false }
  }, [assetId, version, opened])
  const pct = (p) => `${Math.round(p * 100)}%`
  return (
    <details className="tech" onToggle={(e) => setOpened(e.currentTarget.open)}>
      <summary>Technical details for engineers</summary>
      {!data ? <p className="muted">Loading…</p> : (
        <div className="tech-body">
          <p>Chance this spot is damaged: <b>{pct(data.recommendation?.p_damaged ?? 0)}</b>. Urgency multiplier: <b>{data.urgency}×</b>. Information from one visit: <b>{data.info_gain_bits} bits</b>.</p>
          {[['If damage is found', data.if_damaged], ['If no damage is found', data.if_intact]].map(([title, b]) => (
            <div key={title} className="tech-branch">
              <strong>{title}</strong> <span className="muted">({pct(b.probability)} likely)</span>
              <ul>{b.scenarios.slice(0, 3).map((s) => <li key={s.label}>{s.label}: {pct(s.before)} to {pct(s.after)}</li>)}</ul>
            </div>
          ))}
          <p className="muted small">{data.caveat}</p>
        </div>
      )}
    </details>
  )
}

function PriorityDetail({ state, id, open, run }) {
  const asset = state.assets.find((a) => a.id === id)
  const rec = state.recommendations.find((r) => r.asset_id === id)
  const version = state.log.length + state.roads.filter((r) => r.blocked).length
  const hazardAreas = state.areas.filter((a) => a.transformer === id && Object.keys(a.hazards).length)
  const done = asset.status === 'damaged' || asset.status === 'intact'
  const hand = state.handoff.find((h) => h.asset_id === id)
  const fixed = state.repaired.find((x) => x.asset_id === id)
  const tier = rec?.tier ?? (fixed ? 'restored' : asset.status === 'damaged' ? 'confirmed' : done ? 'checked' : 'low')
  const excluded = state.excluded.find((e) => e.asset_id === id)
  const found = state.log.find((o) => o.asset_id === id)

  return (
    <div className="detail">
      <Banner tier={tier}>
        {rec ? `Number ${rec.rank} on the list` : fixed ? `Repaired by ${fixed.by}, ${clock(fixed.time)}` : asset.status === 'damaged' ? `Damage found, reported by ${found?.by}` : asset.status === 'intact' ? `Checked, no damage found (${found?.by})` : excluded ? (excluded.reason === 'No open road access' ? 'No open road to get there' : 'Marked unreachable') : ''}
      </Banner>
      <h2>{asset.name}</h2>
      <p className="muted place"><Pin size={15} />{asset.place}</p>

      {hazardAreas.map((a) => (
        <div key={a.id} className={`alert${a.hazard_open ? '' : ' safe'}`}>
          {a.hazard_open ? <Alert size={18} /> : <Shield size={18} />}
          <div>
            <strong>{Object.keys(a.hazards).join(', ')} in Brgy. {a.barangay}</strong>
            <span>{a.hazard_open ? `Reported by ${plural(Object.values(a.hazards).reduce((s, n) => s + n, 0), 'message')}. Keep people away until it's made safe.` : `Made safe by ${a.hazard_handled_by}.`}</span>
          </div>
          {a.hazard_open && <button className="btn sm" onClick={() => run(() => api.hazard(a.id, true))}>Mark as made safe</button>}
        </div>
      ))}

      {rec && (
        <section>
          <h3>Why it's number {rec.rank}</h3>
          <p>{rec.headline}. {rec.reason}</p>
          <div className="stat-grid">
            <div><b>{fmt(rec.covers.people)}</b><span>people reporting</span></div>
            <div><b>{about(rec.covers.accounts)}</b><span>customer accounts served</span></div>
            <div><b>{rec.covers.barangays}</b><span>barangays</span></div>
            <div><b>{rec.covers.critical.length}</b><span>critical sites</span></div>
          </div>
        </section>
      )}

      {rec && (
        <section>
          <h3>Getting there</h3>
          <p>{rec.travel_min} min drive from the {rec.from}{rec.route.via.length ? `, ${rec.route.km} km via ${rec.route.via.join(', ')}` : ''}. Plus about {rec.inspect_min} min on site.</p>
          <p className="muted small">Suggested route only. It already avoids roads marked closed.</p>
        </section>
      )}
      {!rec && excluded?.reason === 'No open road access' && (
        <section><h3>Getting there</h3><p className="muted">Every road there is marked closed. Reopen one in the Roads tab.</p></section>
      )}

      <section>
        <h3>Exact location</h3>
        <p>{asset.name}, {asset.place}</p>
        <p className="muted small">{asset.pos[0].toFixed(4)}, {asset.pos[1].toFixed(4)}</p>
        <a className="btn sm" href={gmaps(asset.pos)} target="_blank" rel="noreferrer"><External size={15} />Open in Google Maps</a>
      </section>

      <section>
        <h3>What to check on site</h3>
        <p>{asset.objective}</p>
      </section>

      {rec && rec.covers.areas.length > 0 && (
        <section>
          <h3>Barangays this could explain</h3>
          <div className="chips-wrap">
            {rec.covers.areas.map((a) => {
              const area = state.areas.find((x) => x.id === a.id)
              const t = areaTier(area) ?? 'low'
              return <button key={a.id} className="area-chip" onClick={() => open({ kind: 'area', id: a.id })}><i className={`dot t-${t}`} />{a.name}{area.people ? <span className="muted">{area.people}</span> : null}</button>
            })}
          </div>
        </section>
      )}
      {rec && rec.covers.critical.length > 0 && (
        <section>
          <h3>Critical sites likely without power</h3>
          <ul className="plain">{rec.covers.critical.map((c) => <li key={c}><Hospital size={15} />{c}</li>)}</ul>
        </section>
      )}

      {hand && (
        <section>
          <h3>Ready for repair</h3>
          <ul className="handoffs"><HandoffCard h={hand} open={() => {}} run={run} /></ul>
        </section>
      )}
      {fixed && (
        <section>
          <h3>After the repair</h3>
          {fixed.back.length > 0 && <p>Power back: {fixed.back.map((n) => n.split(',')[0]).join(', ')}.</p>}
          {fixed.still_dark.length > 0 && <p className="warn-text">Still dark: {fixed.still_dark.map((n) => n.split(',')[0]).join(', ')}. Residents report no power, so another break is likely; it's back on the Check next list.</p>}
        </section>
      )}

      {!done && <RecordResult id={id} run={run} />}

      {!done && (
        <section>
          <h3>Dispatcher controls</h3>
          <div className="seg-row">
            {[[2, 'Raise priority'], [1, 'Normal'], [0.5, 'Lower priority']].map(([w, label]) => (
              <button key={w} className={asset.priority === w ? 'seg-btn on' : 'seg-btn'} onClick={() => run(() => api.priority(id, w))}>{label}</button>
            ))}
          </div>
        </section>
      )}
      <Technical assetId={id} version={version} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Reports and barangays
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

function SourceFilter({ counts, value, onChange }) {
  return (
    <div className="filter-row" role="group" aria-label="Filter by channel">
      <button className={!value ? 'fchip on' : 'fchip'} onClick={() => onChange(null)}>All</button>
      {SOURCE_ORDER.filter((k) => counts[k]).map((k) => (
        <button key={k} className={value === k ? 'fchip on' : 'fchip'} onClick={() => onChange(value === k ? null : k)}>
          <SourceBadge source={k} size={18} />{SOURCES[k].short}<span className="muted">{counts[k]}</span>
        </button>
      ))}
    </div>
  )
}

function useLimited(list, step = 40) {
  const [n, setN] = useState(step)
  return [list.slice(0, n), list.length > n ? () => setN((x) => x + step) : null]
}

function AreaDetail({ state, reports, id, open, run, now }) {
  const a = state.areas.find((x) => x.id === id)
  const [source, setSource] = useState(null)
  const mine = useMemo(() => reports.filter((r) => r.area_id === id), [reports, id])
  const shown = source ? mine.filter((r) => r.source === source) : mine
  const [list, more] = useLimited(shown)
  const tier = areaTier(a) ?? 'ok'
  const rec = a.best_asset && state.recommendations.find((r) => r.asset_id === a.best_asset)
  const expected = a.expected_people

  return (
    <div className="detail">
      <Banner tier={tier}>{TIERS[tier].hint}</Banner>
      <h2>Brgy. {a.barangay}</h2>
      <p className="muted place"><Pin size={15} />{a.city}</p>

      {Object.keys(a.hazards).length > 0 && (
        <div className={`alert${a.hazard_open ? '' : ' safe'}`}>
          {a.hazard_open ? <Alert size={18} /> : <Shield size={18} />}
          <div>
            <strong>{Object.keys(a.hazards).join(', ')}</strong>
            <span>{a.hazard_open ? 'Reported here. Keep people away until it is made safe.' : `Made safe by ${a.hazard_handled_by}.`}</span>
          </div>
          {a.hazard_open
            ? <button className="btn sm" onClick={() => run(() => api.hazard(a.id, true))}>Mark as made safe</button>
            : <button className="btn ghost sm" onClick={() => run(() => api.hazard(a.id, false))}>Reopen</button>}
        </div>
      )}
      {(a.restored_msgs > 0 || a.still_dark_msgs > 0) && (
        <div className={`alert ${a.restored ? 'safe' : 'quiet'}`}>
          {a.restored ? <Check size={18} /> : <Alert size={18} />}
          <div>
            <strong>{a.restored ? 'Power is back' : 'Still dark after a repair'}</strong>
            <span>{a.restored ? `${plural(a.restored_msgs, 'resident')} confirmed power came back.` : `${plural(a.still_dark_msgs, 'resident')} say there's still no power, so another break is likely.`}</span>
          </div>
        </div>
      )}
      {a.quiet && !a.restored && (
        <div className="alert quiet">
          <Quiet size={18} />
          <div><strong>Quiet area</strong><span>Only {plural(a.people, 'person')} reported, but about {expected} would be expected from {fmt(a.accounts)} customer accounts. Phones may be dead or people evacuated. Don't wait for more reports.</span></div>
        </div>
      )}

      <div className="stat-grid">
        <div><b>{fmt(a.people)}</b><span>people reporting</span></div>
        <div><b>{fmt(a.reports)}</b><span>messages</span></div>
        <div><b>{about(a.accounts)}</b><span>customer accounts</span></div>
        <div><b className="word">{likelihood(a.p_out)}</b><span>based on reports so far</span></div>
      </div>
      {Object.keys(a.clues).length > 0 && <p className="clue-line">Clues from reports: {Object.entries(a.clues).map(([k, n]) => `${k} (${n})`).join(', ')}</p>}
      {a.vulnerable > 0 && <p className="clue-line">{plural(a.vulnerable, 'message')} mention someone elderly, sick or very young.</p>}
      {a.critical.length > 0 && <ul className="plain">{a.critical.map((c) => <li key={c}><Hospital size={15} />{c}</li>)}</ul>}

      <section>
        <h3>Next step</h3>
        {rec ? (
            <button className={`next-card t-${rec.tier}`} onClick={() => open({ kind: 'priority', id: rec.asset_id })}>
              <span className={`rank t-${rec.tier}`}>{rec.rank}</span>
              <span><strong>{rec.name}</strong><span className="muted">{rec.headline}</span></span>
            </button>
          ) : <p className="muted">{a.confirmed ? 'Damage confirmed upstream. Repairs will restore this area.' : 'Nothing to inspect here right now.'}</p>}
      </section>

      {mine.length > 0 && (
        <section>
          <h3>Where the reports came from</h3>
          <ChannelBar bySource={a.by_source} />
        </section>
      )}
      <section>
        <h3>{mine.length ? `All ${mine.length} messages` : 'No messages from this barangay'}</h3>
        {mine.length > 0 && <SourceFilter counts={a.by_source} value={source} onChange={setSource} />}
        <ul className="reports">{list.map((r) => <ReportRow key={r.id} r={r} now={now} showPlace={false} onOpen={() => open({ kind: 'report', id: r.id })} />)}</ul>
        {more && <button className="btn ghost wide" onClick={more}>Show more</button>}
      </section>
    </div>
  )
}

function Reports({ state, reports, open, now }) {
  const [mode, setMode] = useState('areas')
  const [source, setSource] = useState(null)
  const [cat, setCat] = useState(null)
  const counts = state.summary.by_source
  const catCount = (c) => reports.filter((r) => (c === 'vulnerable' ? r.vulnerable : r.category === c)).length
  const filtered = reports.filter((r) => (!source || r.source === source) && (!cat || (cat === 'vulnerable' ? r.vulnerable : r.category === cat)))
  const [list, more] = useLimited(filtered)
  const areas = state.areas.filter((a) => a.people || areaTier(a) === 'unknown')
    .sort((x, y) => tierRank(areaTier(x)) - tierRank(areaTier(y)) || y.people - x.people)

  return (
    <div className="tab-body">
      <p className="intro">{fmt(state.summary.reports)} messages from {fmt(state.summary.people)} people across six channels. Someone who reported through several channels counts once.</p>
      <ChannelBar bySource={counts} />
      <div className="seg-row" role="tablist">
        <button className={mode === 'areas' ? 'seg-btn on' : 'seg-btn'} onClick={() => setMode('areas')}>By barangay</button>
        <button className={mode === 'all' ? 'seg-btn on' : 'seg-btn'} onClick={() => setMode('all')}>All messages</button>
      </div>
      {mode === 'areas' ? (
        <ul className="area-list">
          {areas.map((a) => {
            const t = areaTier(a)
            return (
              <li key={a.id}>
                <button className="area-row" onClick={() => open({ kind: 'area', id: a.id })}>
                  <i className={`dot big t-${t}`}>{t === 'unknown' ? '?' : t === 'ok' ? '' : '!'}</i>
                  <span className="ar-body">
                    <strong>Brgy. {a.barangay}</strong>
                    <span className="muted">{a.city}</span>
                    <span className="ar-tags">
                      <span className={`prio-tier t-${t}`}>{TIERS[t].label}</span>
                      {a.quiet && <span className="tag noise">Quiet area</span>}
                      {Object.keys(a.clues).map((c) => <span key={c} className="tag clue">{c}</span>)}
                    </span>
                  </span>
                  <span className="ar-count"><b>{a.people}</b><span className="muted small">people</span></span>
                </button>
              </li>
            )
          })}
        </ul>
      ) : (
        <>
          <div className="filter-row" role="group" aria-label="Filter by type">
            {[[null, 'Everything'], ['hazard', 'Safety hazards'], ['clue', 'Damage clues'], ['vulnerable', 'Vulnerable people'], ['noise', 'Single houses']].map(([k, label]) => (
              <button key={label} className={cat === k ? 'fchip on' : 'fchip'} onClick={() => setCat(k)}>
                {label}{k && <span className="muted">{catCount(k)}</span>}
              </button>
            ))}
          </div>
          <SourceFilter counts={counts} value={source} onChange={setSource} />
          <ul className="reports">{list.map((r) => <ReportRow key={r.id} r={r} now={now} onOpen={() => open({ kind: 'report', id: r.id })} />)}</ul>
          {filtered.length === 0 && <p className="muted pad-y">No messages match these filters.</p>}
          {more && <button className="btn ghost wide" onClick={more}>Show more</button>}
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Roads
// ---------------------------------------------------------------------------
function Roads({ state, run, roadsOn, onRoads }) {
  const closed = state.roads.filter((r) => r.blocked)
  return (
    <div className="tab-body">
      <p className="intro">Roads reported closed by floods or debris. Drive times and which places can be reached already account for them.</p>
      {closed.length === 0 ? <p className="muted">No roads marked closed.</p> : (
        <ul className="road-list">
          {closed.map((r) => (
            <li key={r.id}><Road size={16} /><span>{r.name}</span><button className="btn ghost sm" onClick={() => run(() => api.road(r.id, false))}>Reopen</button></li>
          ))}
        </ul>
      )}
      <button className={roadsOn ? 'btn sm on' : 'btn sm'} onClick={onRoads}>{roadsOn ? 'Done' : 'Mark another road closed'}</button>
      {roadsOn && <p className="muted small">Click a road on the map to mark it closed or open.</p>}
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

// ---------------------------------------------------------------------------
// The panel
// ---------------------------------------------------------------------------
const TABS = [['priorities', 'Priorities'], ['reports', 'Reports'], ['roads', 'Roads']]

export default function Panel({ state, reports, sel, open, back, close, tab, setTab, run, onMenu, roadsOn, onRoads, sheet, setSheet, stage, setStage }) {
  const [q, setQ] = useState('')
  const scroller = useRef(null)
  useEffect(() => { if (scroller.current) scroller.current.scrollTop = 0 }, [sel?.kind, sel?.id, tab])
  const now = state.event.now
  const sum = state.summary
  const report = sel?.kind === 'report' && reports.find((r) => r.id === sel.id)
  const title = sel ? { priority: 'Priorities', area: 'Barangay', report: 'Message' }[sel.kind] : null

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
            {sel.kind === 'area' && <AreaDetail key={sel.id} state={state} reports={reports} id={sel.id} open={open} run={run} now={now} />}
            {sel.kind === 'report' && report && (
              <ReportFull r={report} now={now}
                also={reports.filter((o) => o.person_id === report.person_id && o.id !== report.id)}
                onOpen={(rid) => open({ kind: 'report', id: rid })} onArea={() => open({ kind: 'area', id: report.area_id })} />
            )}
          </>
        ) : (
          <>
            <header className="storm">
              <div className="storm-name"><span className="drill">Drill</span><h1>Typhoon Dalisay</h1></div>
              <p className="muted">
                Storm passed at {clock(state.event.all_clear)}. {fmt(sum.reports)} messages from {fmt(sum.people)} people so far.
              </p>
              <div className="kpis">
                <div><b>{sum.areas_reporting}</b><span>barangays reporting outages</span></div>
                <div><b>{about(sum.accounts_reporting)}</b><span>customer accounts in those barangays</span></div>
                <div className={sum.hazards_open ? 'warn' : ''}><b>{sum.hazards_open}</b><span>safety {sum.hazards_open === 1 ? 'hazard' : 'hazards'} open</span></div>
                <div><b>{sum.quiet_areas}</b><span>quiet {sum.quiet_areas === 1 ? 'area' : 'areas'} (few reports)</span></div>
              </div>
            </header>
            <nav className="tabs" role="tablist">
              {TABS.map(([k, label]) => (
                <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>
                  {label}
                  {k === 'priorities' && <span className="count">{state.recommendations.filter((r) => r.tier !== 'low').length}</span>}
                  {k === 'reports' && <span className="count">{sum.reports}</span>}
                </button>
              ))}
            </nav>
            {tab === 'priorities' && <Priorities state={state} open={open} run={run} view={stage} setView={setStage} />}
            {tab === 'reports' && <Reports state={state} reports={reports} open={open} now={now} />}
            {tab === 'roads' && <Roads state={state} run={run} roadsOn={roadsOn} onRoads={onRoads} />}
          </>
        )}
      </div>
    </aside>
  )
}
