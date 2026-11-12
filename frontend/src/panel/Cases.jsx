// The power interruptions in the side panel: the list, grouped by customer tier, and one page per
// interruption. The page opens with three numbers (customers without power, reports, things to
// check) and then has two views, switched by the pills:
//   What to check     the ranking: 1 is the one to check first, grouped by customer tier, then
//                     what is on hold and what is done. The same numbers are on the map. Click one
//                     to see the crew's road route to it; "Resolve" on number 1 moves on to the next.
//   Customer reports  the reports by channel. Open a channel, then a report, to see it the way
//                     that channel shows it.
// How Liwa got there is folded away at the bottom of the first view.
import { Fragment, useState } from 'react'
import { Alert, AppMark, Back, Check, FacebookMark, Pause, PhoneMark, Pin, SmsMark, XMark } from '../icons'
import { EQUIPMENT_ICON, TIER_CLASS, customersOf, minutes, plain, poleName, reportsOf, reportsText, said, standing, tierOf } from '../map/cases'
import { ReportFull, SourceBadge, clock, sender } from './ReportCard'

const TIER_NAME = { 1: 'Critical customers', 2: 'Community services', 3: 'Residential' }
const CHANNEL_ICON = { 'Meralco App': AppMark, SMS: SmsMark, 'Hotline 16211': PhoneMark, Facebook: FacebookMark, X: XMark }
const CHANNEL_CLASS = { 'Meralco App': 'app', SMS: 'sms', 'Hotline 16211': 'hotline', Facebook: 'facebook', X: 'x' }
const ROUTE_NOTE = {
  loading: 'Finding the road route',
  google: 'Road route shown on the map, from Google Maps',
  osm: 'Road route shown on the map, from OpenStreetMap',
  none: 'No road route found: a straight line is shown',
}
const count = (n, one, many) => `${n.toLocaleString()} ${n === 1 ? one : many}`
// "claude-opus-5-5" -> "Claude Opus 5.5"
const modelName = (id = '') => {
  const [brand, family, ...version] = id.split('-')
  const cap = (w = '') => w.charAt(0).toUpperCase() + w.slice(1)
  return `${cap(brand)} ${cap(family)} ${version.join('.')}`.trim()
}
// One plain line of facts about a piece of equipment.
const facts = (j) => [
  `Restores ${count(j.customers_restored, 'customer', 'customers')}`,
  reportsText(j.report_count),
  j.distance_meters ? `${j.distance_meters / 1000} km away` : null,
  j.work_type === 'inspect' ? 'inspection only' : null,
  j.flood_status === 'flooded_partial_cleared' ? 'flood partly cleared' : null,
].filter(Boolean).join(', ')

// The equipment's own mark (pole, transformer, line section) with its name.
function Name({ job }) {
  return (
    <strong className="eq-name">
      <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d={EQUIPMENT_ICON[job.equipment] ?? EQUIPMENT_ICON.pole} />
      </svg>
      {poleName(job)}
    </strong>
  )
}

export function CaseList({ cases, places, onOpen }) {
  return (
    <div className="tab-body">
      <p className="intro">Open one to see what to check first.</p>
      {[1, 2, 3].map((t) => {
        const group = cases.filter((c) => tierOf(c) === t)
        if (group.length === 0) return null
        return (
          <section key={t} className={`tier-group t-${TIER_CLASS[t]}`}>
            <h3 className="tier-title"><i className="dot">!</i>{TIER_NAME[t]}<span>{group.length}</span></h3>
            <ol className="prios cases">
              {group.map((c) => (
                <li key={c.id} className="prio">
                  <button className="prio-main" onClick={() => onOpen({ kind: 'case', id: c.id })}>
                    <span className="rank">!</span>
                    <span className="prio-body">
                      <strong className="prio-name">{c.title}</strong>
                      <span className="prio-meta">{places[c.id]}</span>
                      <span className="prio-meta">{count(customersOf(c), 'customer', 'customers')} without power, {reportsText(reportsOf(c))}</span>
                      {c.decision && <span className="prio-said">{said(c.decision, c.jobs)}</span>}
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          </section>
        )
      })}
    </div>
  )
}

// What customers reported. One row per channel; open a channel to list its reports (hazards first,
// then people who depend on power); open a report to see it as that channel shows it.
function Reports({ c, told, note, place }) {
  const [channel, setChannel] = useState(null)
  const [post, setPost] = useState(null)
  if (!told) return <p className="muted small">Loading the reports</p>
  const name = Object.fromEntries(c.jobs.map((j) => [j.pole_id, poleName(j)]))
  const weight = (r) => (r.hazard ? 0 : r.vulnerable ? 1 : 2)
  const s = told.summary
  const open = post && told.reports.find((r) => r.id === post)
  if (open) {
    return (
      <div className="rep-one">
        <button className="link back" onClick={() => setPost(null)}><Back size={15} />Back to the {open.channel} reports</button>
        <ReportFull r={open} place={place} about={name[open.pole_id]} unsafe={c.jobs.find((j) => j.pole_id === open.pole_id)?.safety === 'unsafe'} />
      </div>
    )
  }
  return (
    <>
      <p className="muted small">
        {reportsText(s.total)}, one per person. {s.hazard} describe a hazard and {s.vulnerable} mention someone who depends on power.
        The messages are invented for this demo.
      </p>
      {note && <p className="rep-note"><b>Liwa on the reports:</b> {note}</p>}
      {told.channels.filter((ch) => s.by_channel[ch] > 0).map((ch) => {
        const Icon = CHANNEL_ICON[ch]
        const on = channel === ch
        return (
          <div key={ch} className={`rep-group ch-${CHANNEL_CLASS[ch]}${on ? ' open' : ''}`}>
            <button className="rep-head" onClick={() => setChannel(on ? null : ch)} aria-expanded={on}>
              <i><Icon size={15} /></i><span>{ch}</span><b>{s.by_channel[ch]}</b>
            </button>
            {on && (
              <ul className="rep-list">
                {told.reports.filter((r) => r.channel === ch).sort((a, b) => weight(a) - weight(b)).map((r) => (
                  <li key={r.id}>
                    <button className="report-row" onClick={() => setPost(r.id)}>
                      <SourceBadge source={r.source} />
                      <span className="rr-body">
                        <span className="rr-head"><strong>{sender(r)}</strong><span className="muted rr-time">{clock(r.time)}</span></span>
                        <span className="rr-text">{r.text}</span>
                        <span className="rr-foot">
                          {r.hazard && <span className="tag hazard">{r.hazard}</span>}
                          {r.vulnerable && <span className="tag clue">Depends on power</span>}
                          <span className="muted">{name[r.pole_id]}</span>
                        </span>
                      </span>
                      {r.photo && <img className="rr-thumb" src={r.photo.url} alt="" />}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )
      })}
    </>
  )
}

const CHANGE_SAID = { safe: 'is now safe for the crew', unsafe: 'is not safe for the crew after all', flood_cleared: 'is clear of flood' }
const stood = (at) => (at === 'hold' ? 'on hold' : at === 'done' ? 'done' : at == null ? 'not ranked' : `number ${at}`)

// After conditions change: what changed, and what moved because of it.
function Moved({ c, rank, shift, onRestart, busy }) {
  const now = standing(rank)
  const name = Object.fromEntries(c.jobs.map((j) => [j.pole_id, poleName(j)]))
  const moves = c.jobs.map((j) => j.pole_id).filter((id) => shift.before[id] !== undefined && shift.before[id] !== now[id])
    .sort((a, b) => (a === shift.pole ? -1 : b === shift.pole ? 1 : (Number(now[a]) || 99) - (Number(now[b]) || 99)))
  const shown = moves.slice(0, 4)
  return (
    <div className="moved" role="status">
      <strong>Liwa ranked this again</strong>
      <p>{name[shift.pole]} {CHANGE_SAID[shift.change]}.</p>
      {shown.length > 0 ? (
        <ul>
          {shown.map((id) => <li key={id}><b>{name[id]}</b><span>{stood(shift.before[id])}</span><i aria-hidden="true">to</i><span className="to">{stood(now[id])}</span></li>)}
          {moves.length > shown.length && <li className="rest">and {moves.length - shown.length} more moved</li>}
        </ul>
      ) : <p className="muted">Nothing changed place.</p>}
      <button className="link" disabled={busy} onClick={onRestart}>Put this interruption back as it was</button>
    </div>
  )
}

// rank: the ranking with resolved equipment taken out (see ranking() in map/cases.js). active: the one whose route is on the map.
// shift: the last change of conditions and where everything stood before it. onChange(pole, what) records a new one.
export function CaseDetail({ c, plan, rank, active, route, told, shift, busy, error, onDecide, onPick, onResolve, onUndo, onChange, onRestart }) {
  const [view, setView] = useState('order')            // order | reports
  const d = c.decision
  const tier = TIER_CLASS[tierOf(c)]
  const from = plan.office ? ` from ${plan.office.name}` : ''
  const eta = (j) => (minutes(j.eta_seconds) ? `Crew ETA ${minutes(j.eta_seconds)}` : null)
  const started = rank && rank.done.some((x) => x.mine)
  const resolved = rank ? rank.done.filter((x) => x.mine).map((x) => x.job.pole_id) : []
  // Why something sits where it does: Liwa's main reason for the original first one, her short reason for the others.
  const why = (j, i) => plain(i === 0 && !started ? d.reason : d.whys?.[j.pole_id], c.jobs)
  return (
    <div className="detail">
      <div className={`banner t-${tier}`}><span className="banner-dot" /><div><strong>{TIER_NAME[tierOf(c)]}</strong><span>The highest customer tier still waiting here</span></div></div>
      <h2>{c.title}</h2>
      <p className="muted place"><Pin size={15} />Near {plan.place}</p>
      <div className="stats">
        <div><b>{customersOf(c, resolved).toLocaleString()}</b><span>customers without power</span></div>
        <div><b>{reportsOf(c).toLocaleString()}</b><span>reports from customers</span></div>
        <div><b>{c.jobs.length}</b><span>things to check</span></div>
      </div>
      <p className="lead">{c.setup}</p>

      <div className="pills" role="tablist" aria-label="What to show for this interruption">
        <button role="tab" aria-selected={view === 'order'} className={view === 'order' ? 'on' : ''} onClick={() => setView('order')}>What to check, in order</button>
        <button role="tab" aria-selected={view === 'reports'} className={view === 'reports' ? 'on' : ''} onClick={() => setView('reports')}>Customer reports<b>{reportsOf(c)}</b></button>
      </div>

      {view === 'reports' && (
        <section className="case-view">
          <Reports c={c} told={told} note={plain(d?.report_note, c.jobs)} place={plan.place} />
        </section>
      )}

      {view === 'order' && (
        <section className="case-view">
          {!d && busy && <p className="case-wait"><i className="lp-spin" />{c.changes?.length ? 'Conditions changed. Liwa is ranking the equipment again' : 'Liwa is reading the reports and ranking the equipment now'}</p>}
          {rank && shift && <Moved c={c} rank={rank} shift={shift} onRestart={onRestart} busy={busy} />}
          {!d && error && <p className="warn-text" role="alert">Liwa could not rank this: {error} <button className="link" onClick={() => onDecide(true)}>Try again</button></p>}
          {!d && (
            <ul className="order">
              {c.jobs.map((j) => <li key={j.pole_id} className="held"><div className="pick"><span className="num">?</span><span className="body"><Name job={j} /><span className="facts">{facts(j)}</span></span></div></li>)}
            </ul>
          )}

          {rank && rank.go.length === 0 && !started && <div className="hold-card"><strong>Hold the crew</strong><p>{plain(d.reason, c.jobs)}</p></div>}
          {rank && rank.go.length === 0 && started && <div className="hold-card done"><strong>Nothing left to send the crew to</strong><p>Everything that could be worked on is resolved.{rank.held.length > 0 ? ` ${rank.held.length} ${rank.held.length === 1 ? 'is' : 'are'} still on hold.` : ''}</p></div>}
          {rank && rank.go.length > 0 && (
            <ol className="order">
              {rank.go.map((j, i) => {
                const on = j.pole_id === active
                const newTier = i === 0 || rank.go[i - 1].tier !== j.tier
                return (
                  <Fragment key={j.pole_id}>
                    {newTier && <li className={`tier-head t-${TIER_CLASS[j.tier]}`}>{TIER_NAME[j.tier]}</li>}
                    <li className={`${i === 0 ? 'first' : ''}${on ? ' showing' : ''}`}>
                      <button className="pick" onClick={() => onPick(j.pole_id)} aria-pressed={on} title="Show the crew's road route to this">
                        <span className="num">{i + 1}</span>
                        <span className="body">
                          {i === 0 && <span className="tag">Check first</span>}
                          <Name job={j} />
                          {eta(j) && <span className="eta">{eta(j)}{i === 0 ? from : ''}</span>}
                          <span className="facts">{facts(j)}</span>
                          {i > 0 && why(j, i) && <span className="facts">{why(j, i)}</span>}
                          {on && route && <span className="route-on">{ROUTE_NOTE[route]}</span>}
                        </span>
                      </button>
                      {i === 0 && (
                        <div className="more">
                          {why(j, i) && <p className="reason"><b>Why first:</b> {why(j, i)}</p>}
                          <button className="btn primary sm" onClick={() => onResolve(j.pole_id)}><Check size={15} />Resolve</button>
                          <span className="muted small">Resolve once the crew has checked it: they fixed something, or there was nothing to fix.{rank.go.length > 1 ? ' Number 2 is next.' : ''}</span>
                        </div>
                      )}
                    </li>
                  </Fragment>
                )
              })}
            </ol>
          )}
          {rank && rank.held.length > 0 && (
            <>
              <h4 className="order-head">On hold</h4>
              <ul className="order">
                {rank.held.map(({ job, why: reason }) => (
                  <li key={job.pole_id} className="held">
                    <div className="pick"><span className="num"><Pause size={14} /></span><span className="body"><Name job={job} /><span className="eta">{reason}</span><span className="facts">{job.tier_name}. {facts(job)}</span></span></div>
                    {(job.safety === 'unsafe' || (job.flood_status === 'flooded_hold' && job.work_type !== 'inspect')) && (
                      <div className="more hold-more">
                        {job.safety === 'unsafe'
                          ? <button className="btn sm" disabled={busy} onClick={() => onChange(job.pole_id, 'safe')}>Now safe for the crew</button>
                          : <button className="btn sm" disabled={busy} onClick={() => onChange(job.pole_id, 'flood_cleared')}>Flood cleared</button>}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}
          {rank && rank.done.length > 0 && (
            <>
              <h4 className="order-head">Done</h4>
              <ul className="order">
                {rank.done.map(({ job, mine }) => (
                  <li key={job.pole_id} className="done">
                    <div className="pick"><span className="num"><Check size={15} /></span><span className="body"><Name job={job} />
                      <span className="facts">{mine ? 'Resolved. ' : 'Already done. '}{mine && <button className="link" onClick={() => onUndo(job.pole_id)}>Undo</button>}</span></span></div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      {view === 'order' && d && (
        <details className="how">
          <summary>How Liwa decided</summary>
          <p className="muted small">Test scenario: {c.scenario}{c.added ? ' (one of the seven added for this build)' : ' (supplied in the test file)'}.</p>
          {d.changed ? (
            <p className={`case-check${d.agrees_with_rule ? ' ok' : ' off'}`}>
              {d.agrees_with_rule ? <Check size={15} /> : <Alert size={15} />}
              Conditions have changed, so the scenario's expected answer no longer applies. {d.agrees_with_rule ? 'Same first choice as the written rule gives for the situation now.' : 'The written rule gives a different first choice for the situation now.'}
            </p>
          ) : (
            <p className={`case-check${d.correct ? ' ok' : ' off'}`}>
              {d.correct ? <Check size={15} /> : <Alert size={15} />}
              {d.correct ? 'Same first choice as the expected answer for this scenario.' : `The scenario expects: ${said(c.expected, c.jobs)}. ${c.expected.reason}`}
            </p>
          )}
          <p className="muted small">
            {d.generator === 'claude-code'
              ? `Ranked by ${modelName(d.model)} in ${(d.ms.generate / 1000).toFixed(1)} seconds. She read the ${reportsText(d.reports?.total ?? 0)} from customers and the ${d.references.length} records below from the reference database.`
              : 'Claude was not reachable, so this is the rule written in the test file itself.'}
            {plan.office ? ` ETAs are the ones in the test file; the crew is shown coming from ${plan.office.name}, the nearest Meralco office.` : ''}
          </p>
          {d.references.map((ref) => (
            <details key={ref.n} className="lp-ref">
              <summary><b>{ref.n}</b><span>{ref.title}</span>{ref.example && <em className="eg">example</em>}{ref.used && <em>used</em>}</summary>
              <p>{ref.text}</p>
            </details>
          ))}
          <button className="btn sm" disabled={busy} onClick={() => onDecide(true)}>{busy ? 'Ranking' : 'Ask Liwa again'}</button>
        </details>
      )}
    </div>
  )
}
