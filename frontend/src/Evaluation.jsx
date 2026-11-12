import { useEffect, useState } from 'react'
import { api, minutes } from './api'

const STYLE = {
  firstlook: { stroke: '#f47b20', width: 2.5 },
  nearest: { stroke: '#161614', width: 1.5 },
  fixed: { stroke: '#161614', width: 1.5, dash: '4 5' },
}
const W = 880, H = 300, PAD = { l: 44, r: 16, t: 12, b: 30 }

function Chart({ strategies }) {
  // Trim the time axis to where the slowest curve has flattened out.
  const last = Math.max(...strategies.map((s) => {
    const end = s.curve[s.curve.length - 1].pct
    const i = s.curve.findIndex((p) => p.pct - end < 1)
    return s.curve[i < 0 ? s.curve.length - 1 : i].t
  }))
  const tMax = Math.max(60, Math.ceil(last / 60) * 60)
  const x = (t) => PAD.l + (t / tMax) * (W - PAD.l - PAD.r)
  const y = (p) => PAD.t + (1 - p / 100) * (H - PAD.t - PAD.b)
  const ticks = Array.from({ length: tMax / 60 + 1 }, (_, i) => i * 60)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="Scenario uncertainty over time for each strategy">
      {[0, 25, 50, 75, 100].map((p) => (
        <g key={p}>
          <line x1={PAD.l} x2={W - PAD.r} y1={y(p)} y2={y(p)} className="grid" />
          <text x={PAD.l - 8} y={y(p) + 4} textAnchor="end">{p}%</text>
        </g>
      ))}
      {ticks.map((t) => <text key={t} x={x(t)} y={H - 8} textAnchor="middle">{t / 60}h</text>)}
      {[...strategies].reverse().map((s) => (
        <polyline key={s.key} fill="none" stroke={STYLE[s.key].stroke} strokeWidth={STYLE[s.key].width}
          strokeDasharray={STYLE[s.key].dash} strokeLinejoin="round"
          points={s.curve.filter((p) => p.t <= tMax).map((p) => `${x(p.t)},${y(p.pct)}`).join(' ')} />
      ))}
    </svg>
  )
}

export default function Evaluation() {
  const [runs, setRuns] = useState(200)
  const [data, setData] = useState(null)
  const [config, setConfig] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => { api.config().then(setConfig).catch(() => {}) }, [])

  const start = async () => {
    setBusy(true); setError(null)
    try { setData(await api.evaluate(runs, 1)) } catch (e) { setError(e.message) }
    setBusy(false)
  }

  const base = data?.strategies[0]
  return (
    <main className="eval">
      <div className="row head">
        <div>
          <h1>Evaluation</h1>
          <p className="muted">Simulated storms, two crews. FirstLook against nearest-first and fixed-order inspection.</p>
        </div>
        <div className="actions">
          <label className="muted">Storms
            <input type="number" min="10" max="1000" step="10" value={runs}
              onChange={(e) => setRuns(Math.min(1000, Math.max(10, Number(e.target.value) || 10)))} />
          </label>
          <button className="btn primary" onClick={start} disabled={busy}>{busy ? 'Running…' : 'Run simulation'}</button>
        </div>
      </div>
      {error && <p className="verdict">{error}</p>}
      {!data && !busy && <p className="muted">Run the simulation to compare the three strategies.</p>}

      {data && (
        <>
          <div className="cols">
            {data.strategies.map((s) => (
              <div key={s.key} className={s.key === 'firstlook' ? 'col lead' : 'col'}>
                <span className="label">{s.label}</span>
                <div className="num huge">{minutes(s.total_min)}</div>
                <div className="muted">to identify repair needs
                  {s !== base && <span className="num"> · {Math.round((s.total_min / base.total_min - 1) * 100)}% slower</span>}
                </div>
                <div className="row line"><span>Travel</span><span className="num">{minutes(s.travel_min)}</span></div>
                <div className="row line"><span>Inspections</span><span className="num">{s.visits.toFixed(1)}</span></div>
                <div className="row line"><span>Storms identified</span><span className="num">{Math.round(s.identified_rate * 100)}%</span></div>
                <div className="row line"><span>Correct scenario</span><span className="num">{Math.round(s.correct_rate * 100)}%</span></div>
              </div>
            ))}
          </div>

          <span className="label">Scenario uncertainty over time, mean of {data.runs} storms</span>
          <Chart strategies={data.strategies} />
          <div className="legend flat">
            <span><i className="lg route" />FirstLook</span>
            <span><i className="lg solid" />Nearest-first</span>
            <span><i className="lg dashed" />Fixed order</span>
          </div>

          <span className="label">Sensitivity check</span>
          <p>
            With scenario weights deliberately perturbed, FirstLook takes <span className="num">{minutes(data.sensitivity.total_min)}</span> and
            names the correct scenario in <span className="num">{Math.round(data.sensitivity.correct_rate * 100)}%</span> of storms.
          </p>
          {data.notes.map((n) => <p key={n} className="muted small">{n}</p>)}
        </>
      )}

      {config && (
        <>
          <span className="label">Disclosed assumptions</span>
          <div className="assumptions">
            {Object.entries(config).map(([k, v]) => (
              <div key={k} className="row line">
                <span>{k.replaceAll('_', ' ')}</span>
                <span className="num">{typeof v === 'object' ? Object.entries(v).map(([a, b]) => `${a} ${b}`).join(' · ') : String(v)}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </main>
  )
}
