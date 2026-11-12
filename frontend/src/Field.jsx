import { useState } from 'react'
import { api } from './api'

const RESULTS = [
  ['damaged', 'Damaged', 'Physical damage found'],
  ['intact', 'Intact', 'No damage found'],
  ['inconclusive', 'Inconclusive', 'Could not reach or see it'],
]

export default function Field({ state, run }) {
  const [crewId, setCrewId] = useState(state.crews[0].id)
  const [result, setResult] = useState(null)
  const [notes, setNotes] = useState('')
  const crew = state.crews.find((c) => c.id === crewId)
  const asset = state.assets.find((a) => a.id === crew.asset_id)

  const submit = async (value) => {
    const done = await run(() => api.observe(crew.id, asset.id, value, notes))
    if (done) { setResult(null); setNotes('') }
  }

  return (
    <main className="field">
      <div className="seg">
        {state.crews.map((c) => (
          <button key={c.id} className={c.id === crewId ? 'on' : ''} onClick={() => { setCrewId(c.id); setResult(null) }}>
            {c.name}
          </button>
        ))}
      </div>

      {!asset ? (
        <div className="empty">
          <h1>No assignment</h1>
          <p className="muted">{crew.name} is idle in {crew.at}. The dispatcher assigns the next inspection from the console.</p>
        </div>
      ) : (
        <>
          <span className="label">Current assignment</span>
          <h1>{asset.name}</h1>
          <div className="muted">{asset.place}</div>
          <p className="objective">{asset.objective}</p>
          <div className="triple">
            <div><span className="num big">{crew.travel_min ?? '–'}</span><span className="muted">min travel</span></div>
            <div><span className="num big">{crew.route?.km ?? '–'}</span><span className="muted">km</span></div>
            <div><span className="num big">{asset.inspect_min}</span><span className="muted">min inspect</span></div>
          </div>
          {crew.route?.via.length > 0 && <div className="muted">From {crew.at} via {crew.route.via.join(', ')}</div>}

          <span className="label">Record what you found</span>
          <div className="choices">
            {RESULTS.map(([value, title, hint]) => (
              <button key={value} className={`choice ${value}${result === value ? ' on' : ''}`} onClick={() => setResult(value)}>
                <strong>{title}</strong><span className="muted">{hint}</span>
              </button>
            ))}
          </div>
          <textarea placeholder="Notes (optional)" value={notes} rows={3} onChange={(e) => setNotes(e.target.value)} />
          <button className="btn primary wide" disabled={!result} onClick={() => submit(result)}>Submit observation</button>
          <button className="btn ghost wide" onClick={() => submit(null)}>Simulate the field result (demo)</button>
        </>
      )}
    </main>
  )
}
