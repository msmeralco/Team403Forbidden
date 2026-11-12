// Liwa's panel: the hierarchy she ranks by (the policy records in the reference database),
// and a button that runs her on every interruption to check her against the test file. Nothing to type.
import { useEffect, useRef } from 'react'
import { Close } from '../icons'
import { Flat } from './Flat'

// "claude-opus-5-5" -> "Claude Opus 5.5"
const modelName = (id = '') => {
  const [brand, family, ...version] = id.split('-')
  const cap = (w = '') => w.charAt(0).toUpperCase() + w.slice(1)
  return `${cap(brand)} ${cap(family)} ${version.join('.')}`.trim()
}

export default function AssistantPanel({ status, cases, busy, running, style, onRunAll, onClose }) {
  const closeBtn = useRef(null)
  useEffect(() => { closeBtn.current?.focus({ preventScroll: true }) }, [])
  const online = status?.generator === 'claude-code'
  const done = cases.filter((c) => c.decision)
  const right = done.filter((c) => c.decision.correct).length

  return (
    <section className="lp" style={style} role="dialog" aria-label="Liwa, the planner">
      <header className="lp-head">
        <div className="lp-title">
          <Flat size={30} state={busy ? 'thinking' : 'idle'} />
          <h2>Liwa</h2>
          {status && <span className={`lp-mode${online ? ' on' : ''}`}>{online ? modelName(status.model) : 'Offline'}</span>}
          <button ref={closeBtn} className="icon-btn" onClick={onClose} aria-label="Close Liwa's panel"><Close size={16} /></button>
        </div>
        <p className="muted small">When you open an interruption, I look up the hierarchy below in the reference database and rank its poles, live. I recommend; people decide, and Meralco&rsquo;s crews do the work.</p>
      </header>

      <div className="lp-feed">
        <div className="lp-brief">
          <h3>So far</h3>
          <p>{done.length === 0 ? `None of the ${cases.length} interruptions is ranked yet.` : `${done.length} of ${cases.length} interruptions ranked. ${right} of ${done.length} match the expected answer in the test file.`}</p>
        </div>
        <h3 className="lp-sub">The hierarchy I rank by</h3>
        {!status && <p className="lp-line">Reading the reference database…</p>}
        {status && status.guidance.length === 0 && <p className="lp-note">No policy records are loaded. Put them in <code>backend/reference</code>.</p>}
        {status?.guidance.map((g, i) => (
          <details key={g.title} className="lp-ref" open={i === 0}>
            <summary><b>{i + 1}</b><span>{g.title}</span></summary>
            <p>{g.text}</p>
          </details>
        ))}
        {status && status.examples > 0 && <p className="muted small lp-foot-note">Plus {status.examples} worked examples. An interruption never sees its own example.</p>}
      </div>

      <footer className="lp-foot">
        <div className="lp-run">
          <button className="btn sm" disabled={running || busy} onClick={onRunAll}>{running ? 'Ranking' : `Test me on all ${cases.length}`}</button>
          {status && <span className="muted small">{online ? 'Ranks every interruption afresh and compares each answer with the test file. About 5 seconds each.' : 'Claude Code is not reachable: the test file’s own rule is used.'}</span>}
        </div>
      </footer>
    </section>
  )
}
