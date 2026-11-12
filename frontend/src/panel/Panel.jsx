// The side panel after the storm: the power interruptions, and one page for the one that is open.
import { useEffect, useRef, useState } from 'react'
import { Back, Close, Menu, Search } from '../icons'
import { CaseDetail, CaseList } from './Cases'
import { layout } from '../map/cases'

export default function Panel({ state, cases, offices, sel, open, back, close, onMenu, sheet, setSheet, caseBusy, caseError, onDecideCase, rank, active, route, told, onPickPole, onResolve, onUndo }) {
  const [q, setQ] = useState('')
  const scroller = useRef(null)
  useEffect(() => { if (scroller.current) scroller.current.scrollTop = 0 }, [sel?.id])
  const index = sel ? cases.findIndex((c) => c.id === sel.id) : -1
  const places = Object.fromEntries(cases.map((c, i) => [c.id, layout(c, i, state.areas, offices).place]))
  const s = q.trim().toLowerCase()
  const shown = s.length >= 2
    ? cases.filter((c) => `${c.title} ${c.setup} ${places[c.id]} ${c.jobs.map((j) => j.facility_label).join(' ')}`.toLowerCase().includes(s))
    : cases

  return (
    <aside className={`panel${sheet ? ' open' : ''}`} aria-label="FirstLook panel">
      <button className="sheet-handle" onClick={() => setSheet(!sheet)} aria-label={sheet ? 'Collapse panel' : 'Expand panel'}><i /></button>
      <div className="searchbar">
        <button className="icon-btn" onClick={onMenu} aria-label="Open menu"><Menu /></button>
        <Search size={18} className="muted" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search the interruptions" aria-label="Search the interruptions" />
        {q && <button className="icon-btn" onClick={() => setQ('')} aria-label="Clear search"><Close size={16} /></button>}
      </div>

      <div className="panel-scroll" ref={scroller}>
        {index >= 0 ? (
          <>
            <div className="detail-nav">
              <button className="icon-btn" onClick={back} aria-label="Back"><Back /></button>
              <span>Power interruption</span>
              <button className="icon-btn" onClick={close} aria-label="Close"><Close size={16} /></button>
            </div>
            <CaseDetail key={sel.id} c={cases[index]} plan={layout(cases[index], index, state.areas, offices)} rank={rank} active={active} route={route} told={told}
              busy={caseBusy === sel.id} error={caseError} onDecide={(force) => onDecideCase(sel.id, force)}
              onPick={onPickPole} onResolve={(pole) => onResolve(sel.id, pole)} onUndo={(pole) => onUndo(sel.id, pole)} />
          </>
        ) : (
          <>
            <header className="storm">
              <div className="storm-name"><h1>{state.event.name}</h1></div>
              <p className="storm-line">The storm has passed. <b>{cases.length} power interruptions</b> are waiting.</p>
            </header>
            {shown.length === 0 && <p className="muted pad">Nothing found for “{q}”.</p>}
            <CaseList cases={shown} places={places} onOpen={open} />
          </>
        )}
      </div>
    </aside>
  )
}
