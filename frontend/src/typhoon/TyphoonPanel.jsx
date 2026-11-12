// The side panel while the typhoon is still to come or is passing. No interruption is shown
// here: they only exist after the storm.
import { Play } from '../icons'
import { when } from './track'

export default function TyphoonPanel({ name, track, running, tick, onStart, onSkip }) {
  const landfall = track.points.reduce((best, p) => (Math.abs(p.h) < Math.abs(best.h) ? p : best), track.points[0])
  return (
    <aside className="panel ty-panel" aria-label="Typhoon simulation">
      <span className="sheet-handle" aria-hidden="true"><i /></span>
      <div className="panel-scroll">
        <header className="storm">
          <div className="storm-name"><h1>{name}</h1></div>
          {!running && <p className="storm-line">Forecast to cross Luzon near Metro Manila around <b>{when(landfall.time)}</b>.</p>}
        </header>

        {!running ? (
          <div className="tab-body">
            <button className="btn primary ty-start" onClick={onStart}><Play size={15} />Start the typhoon</button>
            <p className="intro">The map shows the forecast track, the points every 12 hours, and the area the center may pass through. Power interruptions only appear once the storm has passed.</p>
            <table className="ty-table">
              <thead><tr><th>When</th><th>Strength</th><th>Winds</th></tr></thead>
              <tbody>
                {track.points.map((p) => (
                  <tr key={p.h}>
                    <td>{when(p.time)}</td>
                    <td><i className={`ty-dot ty-${p.cat.key}`}>{p.cat.letter}</i>{p.cat.label}</td>
                    <td>{p.kmh} km/h</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="muted small">A simulated track, different every time. <button className="link" onClick={onSkip}>Skip to after the storm</button></p>
          </div>
        ) : (
          <div className="tab-body" aria-live="polite">
            <p className="ty-clock">{tick ? when(tick.time) : when(track.timeAt(-track.before))}</p>
            {tick && (
              <>
                <p className="ty-now"><i className={`ty-dot ty-${tick.cat.key}`}>{tick.cat.letter}</i><b>{tick.cat.label}</b>, {tick.kmh} km/h near the center</p>
                <p className="storm-line">
                  {tick.away < 120 ? 'Passing over Metro Manila now.' : `${tick.away.toLocaleString()} km ${tick.west ? 'west' : 'east'} of Metro Manila, ${tick.west ? 'moving away' : 'coming closer'}.`}
                </p>
              </>
            )}
            <div className="ty-bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round((tick?.progress ?? 0) * 100)}><i style={{ width: `${(tick?.progress ?? 0) * 100}%` }} /></div>
            <p className="muted small">The power interruptions will appear when the storm has passed. <button className="link" onClick={onSkip}>Skip</button></p>
          </div>
        )}
      </div>
    </aside>
  )
}
