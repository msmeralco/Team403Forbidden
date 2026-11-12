// Liwa's panel: the inspection plan. Nothing to type. Each step opens its place on the map,
// and the guidance the plan rests on is listed underneath.
import { useEffect, useRef } from 'react'
import { minutes } from '../api'
import { TIERS } from '../theme'
import { Close } from '../icons'
import { Flat } from './Flat'

// "claude-opus-5-5" -> "Claude Opus 5.5"
const modelName = (id = '') => {
  const [brand, family, ...version] = id.split('-')
  const cap = (w = '') => w.charAt(0).toUpperCase() + w.slice(1)
  return `${cap(brand)} ${cap(family)} ${version.join('.')}`.trim()
}
const seconds = (ms) => `${(ms / 1000).toFixed(1)} s`

export default function AssistantPanel({ status, plan, planning, error, style, onUpdate, onClose, onOpen }) {
  const closeBtn = useRef(null)
  useEffect(() => { closeBtn.current?.focus({ preventScroll: true }) }, [])
  const online = status?.generator === 'claude-code'
  const ownDocs = plan?.reference_documents ?? 0
  const written = plan?.generator === 'claude-code'

  return (
    <section className="lp" style={style} role="dialog" aria-label="Liwa, the inspection planner">
      <header className="lp-head">
        <div className="lp-title">
          <Flat size={30} state={planning ? 'thinking' : 'idle'} />
          <h2>Liwa</h2>
          {status && <span className={`lp-mode${online ? ' on' : ''}`}>{online ? modelName(status.model) : 'Offline'}</span>}
          <button ref={closeBtn} className="icon-btn" onClick={onClose} aria-label="Close the inspection plan"><Close size={16} /></button>
        </div>
        <p className="muted small">I write the inspection plan from the reference documents and this event&rsquo;s records. I advise; people decide, and Meralco&rsquo;s crews do the work.</p>
      </header>

      <div className="lp-feed">
        <div className="lp-brief">
          <h3>Right now</h3>
          <p>{status ? status.brief : 'Reading the event…'}</p>
        </div>

        <div className="lp-plan-head">
          <h3>Inspection plan</h3>
          {planning && <span className="lp-busy"><i className="lp-spin" />{plan ? 'Updating' : 'Writing the plan'}</span>}
        </div>
        {error && <p className="lp-error" role="alert">The plan could not be written: {error}</p>}
        {!plan && !planning && !error && <p className="lp-line">No plan yet.</p>}
        {plan && (
          <>
            <p className="lp-say">{plan.summary}</p>
            {plan.steps.length === 0 && <p className="lp-line">Nothing urgent is left to inspect.</p>}
            <ol className="lp-plan">
              {plan.steps.map((s) => (
                <li key={s.asset_id}>
                  <button onClick={() => onOpen({ kind: 'priority', id: s.asset_id })}>
                    <span className={`lp-rank t-${s.tier}`}>{s.n}</span>
                    <span className="lp-step">
                      <strong>{s.name}</strong>
                      <span className="muted">{TIERS[s.tier].label}, {minutes(s.travel_min)} away</span>
                      <span>{s.why}</span>
                      {s.refs.length > 0 && <span className="muted small">Follows reference {s.refs.join(', ')}</span>}
                    </span>
                  </button>
                </li>
              ))}
            </ol>

            <h3 className="lp-sub">What the plan rests on</h3>
            {ownDocs === 0 && (
              <p className="lp-note">No reference documents are loaded yet, so this follows FirstLook&rsquo;s built-in rule. Put <code>.md</code> or <code>.txt</code> files in <code>backend/reference</code> and the plan will be ranked by them.</p>
            )}
            {plan.references.map((r) => (
              <details key={r.n} className="lp-ref">
                <summary><b>{r.n}</b><span>{r.title}</span>{r.used && <em>used</em>}</summary>
                <p>{r.text}</p>
              </details>
            ))}
          </>
        )}
      </div>

      <footer className="lp-foot">
        <div className="lp-run">
          <button className="btn sm" disabled={planning} onClick={onUpdate}>Update plan</button>
          {plan && (
            <span className="muted small">
              {written ? `Written by ${modelName(plan.model)} in ${seconds(plan.ms.generate)}` : 'Claude Code was not reachable: this is FirstLook’s own order'}
              {plan.reordered ? '. The references changed the order.' : ''}
            </span>
          )}
        </div>
      </footer>
    </section>
  )
}
