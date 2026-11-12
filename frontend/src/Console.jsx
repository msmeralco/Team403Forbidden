import { useEffect, useState } from 'react'
import { api, minutes, pct } from './api'
import MapView from './MapView'

function Sparkline({ history }) {
  if (history.length < 2) return null
  const tMax = Math.max(...history.map((h) => h.t), 1)
  const points = history.map((h) => `${(h.t / tMax) * 120},${30 - (Math.min(h.pct, 100) / 100) * 28}`).join(' ')
  return <svg className="spark" width="120" height="32" aria-hidden="true"><polyline points={points} /></svg>
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

const RESULT_LABEL = { damaged: 'Damage found', intact: 'No damage', inconclusive: "Couldn't confirm" }
const value = (rel) => (rel >= 0.66 ? ['High value', 'high'] : rel >= 0.33 ? ['Medium value', 'mid'] : ['Low value', 'low'])
const chance = (x) => (x >= 0.5 ? ['Likely', 'high'] : x >= 0.15 ? ['Possible', 'mid'] : ['Unlikely', 'low'])

function Recommendation({ rec, selected, crews, onSelect, onAssign, onWhy }) {
  const others = crews.filter((c) => c.id !== rec.crew_id && c.status === 'idle')
  return (
    <li className={`rec${selected ? ' sel' : ''}${rec.rank === 1 ? ' first' : ''}`} onClick={onSelect}>
      <span className="rank num">{String(rec.rank).padStart(2, '0')}</span>
      <div className="rec-body">
        <div className="row">
          <strong>{rec.name}</strong>
          <span className={`chip ${value(rec.score_rel)[1]}`}>{value(rec.score_rel)[0]}</span>
        </div>
        <div className="muted">{rec.place}</div>
        <div className="bar"><i style={{ width: `${Math.max(rec.score_rel * 100, 1)}%` }} /></div>
        <div className="muted num">
          {rec.crew_name} · {rec.travel_min} min drive · {rec.inspect_min} min on site
        </div>
        {selected && (
          <>
            <p className="reason">{rec.reason}</p>
            <div className="actions" onClick={(e) => e.stopPropagation()}>
              <button className="btn primary" onClick={() => onAssign(rec.crew_id)}>Send {rec.crew_name}</button>
              {others.map((c) => (
                <button key={c.id} className="btn" onClick={() => onAssign(c.id)}>{c.name}</button>
              ))}
              <button className="btn ghost" onClick={onWhy}>Why this one?</button>
            </div>
          </>
        )}
      </div>
    </li>
  )
}

function Branch({ title, tone, data }) {
  return (
    <div className={`branch ${tone}`}>
      <div className="row"><strong>{title}</strong><span className="num muted">{pct(data.probability)} likely</span></div>
      {data.scenarios.map((s) => (
        <div key={s.label} className="shift">
          <div className="row"><span>{s.label}</span><span className="num">{pct(s.before)} → {pct(s.after)}</span></div>
          <div className="bar thin"><i style={{ width: `${s.after * 100}%` }} /></div>
        </div>
      ))}
      <div className="muted num">Uncertainty left: {Math.round(data.uncertainty_pct)}%</div>
    </div>
  )
}

function Why({ assetId, state, run, onClose }) {
  const [data, setData] = useState(null)
  const version = state.log.length + state.roads.filter((r) => r.blocked).length + state.crews.filter((c) => c.asset_id).length
  useEffect(() => {
    let live = true
    api.explain(assetId).then((d) => live && setData(d)).catch(() => live && setData(null))
    return () => { live = false }
  }, [assetId, version])
  if (!data) return <section className="pad muted">Loading…</section>

  const asset = state.assets.find((a) => a.id === assetId)
  const rec = data.recommendation
  return (
    <section className="pad why">
      <div className="row">
        <span className="label">Why this one?</span>
        <button className="btn ghost" onClick={onClose}>Close</button>
      </div>
      <h2>{data.name}</h2>
      <div className="muted">{data.place}</div>
      <p>{data.establishes} {data.reason}</p>

      <Branch title="If damaged" tone="bad" data={data.if_damaged} />
      <Branch title="If intact" tone="good" data={data.if_intact} />

      {rec && (
        <>
          <span className="label">What it costs and gains</span>
          <div className="triple">
            <div><span className="num big">{rec.travel_min}</span><span className="muted">min drive</span></div>
            <div><span className="num big">{rec.inspect_min}</span><span className="muted">min on site</span></div>
            <div><span className="num big">{state.uncertainty.bits > 0 ? Math.round((rec.info_gain_bits / state.uncertainty.bits) * 100) : 0}%</span><span className="muted">less uncertainty</span></div>
          </div>
          <div className="muted">{rec.crew_name} · {rec.route.km} km{rec.route.via.length ? ` via ${rec.route.via.join(', ')}` : ''}</div>
          <div className="actions">
            <button className="btn primary" onClick={() => run(() => api.assign(rec.crew_id, assetId))}>Send {rec.crew_name}</button>
          </div>
        </>
      )}

      <span className="label">Dispatcher controls</span>
      <div className="actions">
        <button className="btn" onClick={() => run(() => api.restrict(assetId, !asset.restricted))}>
          {asset.restricted ? 'Restore access' : 'Mark inaccessible'}
        </button>
        {[[0.5, 'Lower priority'], [1, 'Normal'], [2, 'Raise priority']].map(([w, label]) => (
          <button key={w} className={asset.priority === w ? 'btn on' : 'btn'}
            onClick={() => run(() => api.priority(assetId, w))}>{label}</button>
        ))}
      </div>
      <p className="muted small">{data.caveat}</p>
    </section>
  )
}

export default function Console({ state, run, dock, collapsed }) {
  const recs = state.recommendations
  const [selected, setSelected] = useState(recs[0]?.asset_id ?? null)
  const [why, setWhy] = useState(null)
  const [truth, setTruth] = useState(null)
  const [rightOpen, setRightOpen] = useState(true)
  const mobile = useIsMobile()
  const [sheetOpen, setSheetOpen] = useState(true)
  const [tab, setTab] = useState('list')
  const openWhy = (id) => { setWhy(id); setTab('info'); setSheetOpen(true) }

  const fresh = state.log.length === 0
  useEffect(() => { if (fresh) setTruth(null) }, [fresh, state.event.seed])
  useEffect(() => {
    // Keep a recommendation selected as the list changes.
    if (!state.assets.some((a) => a.id === selected && a.status === 'uninspected' && !a.assigned_crew)) {
      setSelected(recs[0]?.asset_id ?? null)
    }
  }, [state]) // eslint-disable-line react-hooks/exhaustive-deps

  const selectedRec = recs.find((r) => r.asset_id === selected)
  const res = state.resources

  const listContent = (
    <>
          <div className="pad head">
          <h1>Where to look next</h1>
          <p className="muted">The visits that will tell us the most in the least time.</p>
        </div>
        <ol className="recs">
          {recs.map((rec) => (
            <Recommendation key={rec.asset_id} rec={rec} crews={state.crews}
              selected={rec.asset_id === selected}
              onSelect={() => setSelected(rec.asset_id)}
              onAssign={(crew) => run(() => api.assign(crew, rec.asset_id))}
              onWhy={() => openWhy(rec.asset_id)} />
          ))}
          {recs.length === 0 && <li className="pad muted">Nothing left to inspect.</li>}
        </ol>
        {state.excluded.length > 0 && (
          <div className="pad">
            <span className="label">Left out</span>
            {state.excluded.map((e) => (
              <div key={e.asset_id} className="row line">
                <span>{e.name}<span className="muted"> · {e.reason}</span></span>
                <button className="btn ghost" onClick={() => openWhy(e.asset_id)}>Review</button>
              </div>
            ))}
          </div>
        )}
    </>
  )
  const infoContent = (
    <>
        {why ? <Why assetId={why} state={state} run={run} onClose={() => setWhy(null)} /> : (
          <>
            <section className="pad hero">
              <div className="row center">
                <span className="label">Most likely damage</span>
                {!mobile && <button className="link" onClick={() => setRightOpen(false)}>Hide</button>}
              </div>
              <h2>{res.top_label}</h2>
              <div className="confidence"><i className={res.identified ? 'ok' : ''} style={{ width: `${res.top_p * 100}%` }} /></div>
              <div className="row center">
                <span><span className="num big">{pct(res.top_p)}</span> <span className="muted">sure</span></span>
                <Sparkline history={state.uncertainty.history} />
              </div>
              <div className="muted small">
                {res.identified ? 'Clear enough to send repair crews.' : 'Not confirmed yet. Each inspection sharpens the picture.'}
                {' '}{minutes(state.elapsed_min)} elapsed · {state.log.length} report{state.log.length === 1 ? '' : 's'} in.
              </div>
            </section>
            <section className="pad">
              <span className="label">Crews</span>
              {state.crews.map((c) => (
                <div key={c.id} className="row line">
                  <span>
                    <strong>{c.name}</strong>
                    <span className="muted">
                      {c.asset_id
                        ? ` → ${c.asset_id}${c.travel_min != null ? ` · ${c.travel_min} min` : ' · road closed'}`
                        : ` · idle in ${c.at}`}
                    </span>
                  </span>
                  {c.asset_id && <button className="btn ghost" onClick={() => run(() => api.unassign(c.id))}>Unassign</button>}
                </div>
              ))}
            </section>

            <section className="pad">
              <div className="row">
                <span className="label">Possible causes</span>
                <span className="muted num small">{state.scenario_count} checked</span>
              </div>
              {state.scenarios.map((s, i) => (
                <div key={s.label} className={i === 0 ? 'scenario lead' : 'scenario'}>
                  <div className="row"><span>{s.label}</span><span className="num">{pct(s.p)}</span></div>
                  <div className="bar thin"><i style={{ width: `${s.p * 100}%` }} /></div>
                </div>
              ))}
              {truth
                ? <p className="muted small">Ground truth: {truth.label}</p>
                : <button className="btn ghost small" onClick={() => api.truth().then(setTruth)}>Reveal ground truth (demo)</button>}
            </section>

            <section className="pad">
              <span className="label">Repair needs</span>
              <p className={res.identified ? 'verdict ok' : 'verdict'}>
                {res.identified
                  ? 'Ready to plan repairs.'
                  : 'Too early to commit repair crews.'}
              </p>
              {res.items.map((r) => (
                <div key={r.resource} className="row line">
                  <span>{r.resource}</span><span className={`chip ${chance(r.expected)[1]}`}>{chance(r.expected)[0]}</span>
                </div>
              ))}
              <p className="muted small">How likely each repair job is, given what we know so far.</p>
            </section>

            <section className="pad">
              <span className="label">Field reports</span>
              {state.log.length === 0 && <p className="muted">No reports from the field yet.</p>}
              {state.log.map((o) => (
                <div key={o.id} className="evidence">
                  <span className={`pip ${o.result}`} />
                  <div>
                    <div className="row">
                      <span><strong>{o.asset_name}</strong> · {RESULT_LABEL[o.result]}</span>
                      <span className="num muted">{minutes(o.t)}</span>
                    </div>
                    <div className="muted">
                      {o.crew_name}{o.simulated ? ' · simulated' : ''} · uncertainty left {Math.round(o.uncertainty_pct)}%
                      {o.notes ? ` · ${o.notes}` : ''}
                    </div>
                  </div>
                </div>
              ))}
            </section>
          </>
        )}
    </>
  )

  return (
    <main className={mobile ? 'console mobile' : 'console'}>
      <MapView state={state} selected={selected} route={selectedRec?.route} mobile={mobile} sheetOpen={sheetOpen}
        onSelect={(id) => { setSelected(id); if (why) setWhy(id) }}
        onToggleRoad={(road) => run(() => api.road(road.id, !road.blocked))} />

      <div className={collapsed ? 'left collapsed' : 'left'}>
        {dock}
        {!collapsed && !mobile && <aside className="card list">{listContent}</aside>}
      </div>

      {mobile ? (
        <div className={sheetOpen ? 'card sheet-m open' : 'card sheet-m'}>
          <div className="sheet-head">
            <div className="seg">
              <button className={tab === 'list' ? 'on' : ''} onClick={() => { setTab('list'); setSheetOpen(true) }}>Inspections</button>
              <button className={tab === 'info' ? 'on' : ''} onClick={() => { setTab('info'); setSheetOpen(true) }}>
                Overview
              </button>
            </div>
            <button className="icon-btn" onClick={() => setSheetOpen((o) => !o)} aria-label={sheetOpen ? 'Minimise panel' : 'Open panel'}>
              <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" style={sheetOpen ? null : { transform: 'rotate(180deg)' }}>
                <path d="M3.5 6 8 10.5 12.5 6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
          {sheetOpen && <div className="sheet-body">{tab === 'list' ? listContent : infoContent}</div>}
        </div>
      ) : !rightOpen ? (
        <button className="card right pill" onClick={() => setRightOpen(true)} aria-label="Show scenarios">
          <span className="label">Most likely</span><span className="num big">{pct(res.top_p)} sure</span>
        </button>
      ) : (
        <aside className="card right">{infoContent}</aside>
      )}
    </main>
  )
}
