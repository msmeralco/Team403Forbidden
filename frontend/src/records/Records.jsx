// Typhoon records: a full page opened from the menu, with two views.
//   History   past typhoons, newest first, on a time line: what happened, how fast power came
//             back (the curve), what caused the damage, and what was changed afterwards.
//   Reports   one PDF per typhoon: a restoration report for each past one, and a situation report
//             for the one in progress.
// Every past typhoon is invented for the demonstration; the page says so once, at the top.
import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { Back, Check, Download } from '../icons'
import './records.css'

const n = (v) => Number(v).toLocaleString()
const hours = (h) => (h == null ? 'n/a' : `${h} h`)
const month = (iso) => new Date(iso).toLocaleDateString([], { month: 'short', year: 'numeric' })
const moment = (iso) => new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })
const SECTIONS = [
  'The event: strength, track, when it arrived and when crews could go out',
  'Impact at a glance: customers affected, interruptions, time to restore, customer-minutes interrupted',
  'Restoration progress: the curve and its milestones (50%, 90%, Critical customers, everyone)',
  'Impact by customer tier',
  'Causes of damage and the work done',
  'Customer reports by channel, hazards described, people who depend on power',
  'Safety and holds: what was held, why, and for how long',
  'How the work was prioritised, and where a dispatcher changed it',
  'Crews and resources',
  'The full interruption log, with times',
  'Open items and follow-up actions',
  'Definitions and limits of the data, and a sign-off block',
]

// Share of customers restored against hours after the all clear. One series, so no legend: the
// caption names it. Power returns a repair at a time, so the line is stepped. Hover reads a value.
function Curve({ points, half, ninety, name }) {
  const [at, setAt] = useState(null)
  const box = useRef(null)
  const W = 560, H = 190, L = 40, R = 14, T = 12, B = 26
  const span = Math.max(6, Math.ceil(points[points.length - 1][0] / 6) * 6)
  const x = (h) => L + ((W - L - R) * h) / span
  const y = (p) => T + (H - T - B) * (1 - p / 100)
  const path = points.slice(1).reduce((d, [h, p]) => `${d} H${x(h).toFixed(1)} V${y(p).toFixed(1)}`, `M${x(0)} ${y(0)}`)
  const share = (h) => points.reduce((best, [ph, pp]) => (ph <= h ? pp : best), 0)
  const mark = (h, label) => {
    const p = points.find(([ph, pp]) => ph >= h && pp >= (label.startsWith('50') ? 50 : 90))?.[1] ?? share(h)
    const right = x(h) > W * 0.55          // late marks are labelled up and to the left, where the line has not been yet
    return (
      <g key={label}>
        <circle cx={x(h)} cy={y(p)} r="4.5" className="cv-dot" />
        <text x={x(h) + (right ? -9 : 9)} y={y(p) + (right ? -9 : 16)} textAnchor={right ? 'end' : 'start'} className="cv-label">{label} at {h} h</text>
      </g>
    )
  }
  const move = (e) => {
    const r = box.current.getBoundingClientRect()
    const h = Math.min(span, Math.max(0, (((e.clientX - r.left) / r.width) * W - L) / (W - L - R) * span))
    setAt(Math.round(h * 2) / 2)
  }
  const step = span <= 36 ? 6 : 12
  return (
    <figure className="curve">
      <svg ref={box} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${name}: half of customers had power back ${half} hours after the all clear, 90% after ${ninety} hours.`}
        onMouseMove={move} onMouseLeave={() => setAt(null)}>
        {[0, 50, 100].map((p) => (
          <g key={p}><line x1={L} x2={W - R} y1={y(p)} y2={y(p)} className="cv-grid" /><text x={L - 7} y={y(p) + 4} textAnchor="end" className="cv-tick">{p}%</text></g>
        ))}
        {Array.from({ length: span / step + 1 }, (_, i) => i * step).map((h) => <text key={h} x={x(h)} y={H - 7} textAnchor="middle" className="cv-tick">{h} h</text>)}
        <path d={path} className="cv-line" />
        {mark(half, '50%')}
        {mark(ninety, '90%')}
        {at != null && (
          <g>
            <line x1={x(at)} x2={x(at)} y1={T} y2={H - B} className="cv-cross" />
            <circle cx={x(at)} cy={y(share(at))} r="4" className="cv-dot ring" />
          </g>
        )}
      </svg>
      <figcaption>
        {at == null
          ? 'Share of affected customers with power back, by hours after the all clear.'
          : <><b>{at} h after the all clear:</b> {share(at)}% of customers had power back.</>}
      </figcaption>
    </figure>
  )
}

function Bars({ rows, of }) {
  const top = Math.max(...rows.map((r) => r.value))
  return (
    <ul className="bars">
      {rows.map((r) => (
        <li key={r.label}>
          <span>{r.label}</span>
          <i><b style={{ width: `${Math.max(1.5, (100 * r.value) / top)}%` }} /></i>
          <em>{n(r.value)} {of}</em>
        </li>
      ))}
    </ul>
  )
}

function Typhoon({ e, onExport, saving }) {
  const s = e.summary
  return (
    <li className="ty-event">
      <div className="ty-when"><b>{month(e.landfall)}</b><span>{e.class}</span></div>
      <article>
        <h2>{e.name}</h2>
        <p className="ty-line">Winds up to {e.peak_kmh} km/h, wind signal no. {e.signal}. {e.track}</p>
        <p className="ty-what">{e.what}</p>
        <dl className="figures">
          <div><dt>{n(s.customers)}</dt><dd>customers affected</dd></div>
          <div><dt>{s.interruptions}</dt><dd>power interruptions</dd></div>
          <div><dt>{hours(s.hours_to_90)}</dt><dd>to restore 90% of them</dd></div>
          <div><dt>{hours(s.hours_to_all)}</dt><dd>until everyone was back</dd></div>
        </dl>
        <Curve points={s.curve} half={s.hours_to_half} ninety={s.hours_to_90} name={e.name} />
        <details className="ty-more">
          <summary>More about {e.name}</summary>
          <div className="ty-cols">
            <section>
              <h3>What caused the damage</h3>
              <Bars rows={s.causes.map((c) => ({ label: c.cause, value: c.customers }))} of="customers" />
            </section>
            <section>
              <h3>Who was affected</h3>
              <table className="plain">
                <thead><tr><th>Customer tier</th><th>Interruptions</th><th>Customers</th><th>Last one back</th></tr></thead>
                <tbody>{s.by_tier.map((t) => <tr key={t.tier}><td>{t.name}</td><td>{t.interruptions}</td><td>{n(t.customers)}</td><td>{hours(t.last_h)}</td></tr>)}</tbody>
              </table>
            </section>
          </div>
          <ul className="ty-facts">
            <li><b>{n(s.reports)}</b> reports from customers. {n(s.hazard_reports)} described a hazard and {n(s.vulnerable_reports)} mentioned someone who depends on power.</li>
            <li><b>{s.held}</b> of {s.interruptions} interruptions were held before work could start (not safe for the crew, or flooded), {hours(s.held_hours)} in all.</li>
            <li><b>{s.crews}</b> crews. The recommended first check was followed in {s.followed} of {s.interruptions} interruptions{s.changed ? `; a dispatcher changed ${s.changed}` : ''}.</li>
            <li>Longest outage: <b>{hours(s.longest_h)}</b>, {s.longest_where}. Average per affected customer: {hours(s.average_outage_h)}.</li>
          </ul>
          <h3>What was changed afterwards</h3>
          <ul className="ty-list">{e.lessons.map((l) => <li key={l}>{l}</li>)}</ul>
          {e.open.length > 0 && <><h3>Left open</h3><ul className="ty-list">{e.open.map((l) => <li key={l}>{l}</li>)}</ul></>}
        </details>
        <button className="btn sm" disabled={saving === e.id} onClick={() => onExport(e.id, e.document)}><Download size={15} />{saving === e.id ? 'Preparing the PDF' : 'Export the restoration report'}</button>
      </article>
    </li>
  )
}

export default function Records({ tab, onTab, onClose }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(null)        // id of the report being prepared
  const [saved, setSaved] = useState({})            // id -> file name, once exported
  const [failed, setFailed] = useState(null)

  useEffect(() => { api.history().then(setData).catch((e) => setError(e.message)) }, [])
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const exportPdf = async (id, document_) => {
    setSaving(id); setFailed(null)
    try {
      const blob = await api.reportPdf(id)
      const link = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: `${document_}.pdf` })
      document.body.append(link)
      link.click()
      link.remove()
      setTimeout(() => URL.revokeObjectURL(link.href), 4000)
      setSaved((done) => ({ ...done, [id]: `${document_}.pdf` }))
    } catch (e) {
      setFailed(`The report could not be prepared. ${e.message}`)
    }
    setSaving(null)
  }

  const now = data?.current
  const reports = data ? [
    { id: 'current', document: now.document, title: `Situation report: ${now.name}`, status: 'In progress', when: `As of now. ${now.count} interruptions, ${n(now.customers)} customers without power.` },
    ...data.events.map((e) => ({ id: e.id, document: e.document, title: `Restoration report: ${e.name}`, status: 'Final', when: `${moment(e.landfall)} to ${moment(e.summary.restored)}. ${e.summary.interruptions} interruptions, ${n(e.summary.customers)} customers.` })),
  ] : []

  return (
    <div className="records" role="dialog" aria-label="Typhoon records">
      <header className="rec-bar">
        <button className="icon-btn" onClick={onClose} aria-label="Back to the map"><Back /></button>
        <h1>Typhoon records</h1>
        <div className="pills" role="tablist" aria-label="Records">
          <button role="tab" aria-selected={tab === 'history'} className={tab === 'history' ? 'on' : ''} onClick={() => onTab('history')}>History</button>
          <button role="tab" aria-selected={tab === 'reports'} className={tab === 'reports' ? 'on' : ''} onClick={() => onTab('reports')}>Reports</button>
        </div>
      </header>

      <div className="rec-body">
        <p className="rec-note">The past typhoons on this page are invented for the demonstration. Their names are not PAGASA names and none of this is a Meralco record.</p>
        {error && <p className="warn-text" role="alert">The records could not be loaded. Start the FirstLook server, then open this page again. ({error})</p>}
        {!data && !error && <p className="muted">Loading the records</p>}
        {failed && <p className="warn-text" role="alert">{failed}</p>}

        {data && tab === 'history' && (
          <>
            <p className="rec-lead">What each typhoon did to this sector, how fast the power came back, and what was changed because of it.</p>
            <ol className="ty-timeline">
              <li className="ty-event now">
                <div className="ty-when"><b>Now</b><span>In progress</span></div>
                <article>
                  <h2>{now.name}</h2>
                  <p className="ty-what">The storm has passed and restoration is under way: {now.count} power interruptions, {n(now.customers)} customers without power, {n(now.reports)} reports from customers. {now.on_hold} pieces of equipment are on hold.</p>
                  <button className="btn sm" onClick={onClose}>Go to the map</button>
                  <button className="btn ghost sm" disabled={saving === 'current'} onClick={() => exportPdf('current', now.document)}><Download size={15} />{saving === 'current' ? 'Preparing the PDF' : 'Export the situation report'}</button>
                </article>
              </li>
              {data.events.map((e) => <Typhoon key={e.id} e={e} onExport={exportPdf} saving={saving} />)}
            </ol>
          </>
        )}

        {data && tab === 'reports' && (
          <>
            <p className="rec-lead">One PDF per typhoon, written from its interruption log. Export one to file it, print it or send it on.</p>
            <ul className="rep-docs">
              {reports.map((r) => (
                <li key={r.id}>
                  <div>
                    <h2>{r.title}</h2>
                    <p><span className={`rec-status${r.status === 'Final' ? '' : ' live'}`}>{r.status}</span>{r.document}</p>
                    <p className="muted">{r.when}</p>
                    {saved[r.id] && <p className="rec-saved"><Check size={14} />Exported as {saved[r.id]}. Look in your downloads.</p>}
                  </div>
                  <button className="btn primary" disabled={saving === r.id} onClick={() => exportPdf(r.id, r.document)}><Download size={16} />{saving === r.id ? 'Preparing' : 'Export PDF'}</button>
                </li>
              ))}
            </ul>
            <section className="rec-contents">
              <h2>What a restoration report contains</h2>
              <ol>{SECTIONS.map((line) => <li key={line}>{line}</li>)}</ol>
              <p className="muted">The situation report for a typhoon in progress is shorter: where things stand, every interruption with what to check first, the customer reports, and how the work is being prioritised.</p>
            </section>
          </>
        )}
      </div>
    </div>
  )
}
