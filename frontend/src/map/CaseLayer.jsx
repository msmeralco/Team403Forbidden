// The power interruptions (test cases) on the map.
// Each is a "!" pin coloured by its customer tier, with its number of outage reports.
// When one is open, only that one is drawn: its equipment as markers that carry two things side
// by side, the equipment's own mark (pole, transformer or line section) and its number in the
// order to check (1 is the one to check first). What is on hold carries a pause mark instead of a
// number, what is resolved a tick. The nearest Meralco office is marked too. The numbers are the
// same ones the side panel lists. Click a numbered marker to see the crew's road route to it
// (RouteLayer draws it, one at a time).
// (The zone circle is drawn by GridLayer; the blur outside it by ZoneFocus.)
import { useEffect, useRef } from 'react'
import L from 'leaflet'
import { useMap } from 'react-leaflet'
import { EQUIPMENT_ICON, TIER_CLASS, layout, minutes, poleName, ranking, reportsOf, reportsText, tierOf } from './cases'

const PAUSE = '<svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z"/></svg>'
const TICK = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>'
const esc = (text) => String(text).replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]))
const mark = (job, size) => `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="${EQUIPMENT_ICON[job.equipment] ?? EQUIPMENT_ICON.pole}"/></svg>`
const pin = (tier, reports, cls) => `<div class="pin t-${tier}${cls}">
  <svg class="pin-shape" viewBox="0 0 32 40" aria-hidden="true"><path d="M16 39C16 39 29 26.6 29 16A13 13 0 0 0 3 16C3 26.6 16 39 16 39Z"/></svg>
  <b>!</b>${reports ? `<span class="pin-tab">${reportsText(reports)}</span>` : ''}</div>`
// One piece of equipment: a capsule with its own mark and its number, and a label beside it.
// The picked one gets the full two-line label.
const equipment = (kind, badge, job, line, flip, on) => {
  const big = kind === 'first'
  return L.divIcon({
    className: '', iconSize: big ? [68, 40] : [56, 32], iconAnchor: big ? [34, 20] : [28, 16],
    html: `<div class="rk rk-${kind}${flip ? ' flip' : ''}${on ? ' on' : ''}"><b class="cap"><i>${mark(job, big ? 18 : 15)}</i><em>${badge}</em></b>${on
      ? `<span><strong>${esc(poleName(job))}</strong>${esc(line)}</span>`
      : `<span class="mini">${esc(job.facility_label)}</span>`}</div>`,
  })
}

export default function CaseLayer({ cases, areas, offices, openId, active, resolved, onOpen, onPickPole }) {
  const map = useMap()
  const pick = useRef(onPickPole)
  pick.current = onPickPole
  const version = JSON.stringify([openId, active, resolved, offices.length, cases.map((c) => [c.id, c.decision?.key])])
  useEffect(() => {
    const group = L.layerGroup().addTo(map)
    cases.forEach((c, index) => {
      const open = c.id === openId
      if (openId && !open) return                                        // one interruption at a time
      const plan = layout(c, index, areas, offices)
      L.marker(plan.center, {
        keyboard: true, title: c.title, zIndexOffset: open ? 200 : (4 - tierOf(c)) * 20,
        icon: L.divIcon({ className: '', iconSize: [32, 40], iconAnchor: [16, 39], html: pin(TIER_CLASS[tierOf(c)], reportsOf(c), open ? ' sel' : '') }),
      }).on('click', () => onOpen(c.id)).addTo(group)
      if (!open) return

      const r = ranking(c, resolved)
      const at = (job) => plan.poles.find((p) => p.job.pole_id === job.pole_id).pos
      const flip = (pos) => pos[1] < plan.center[1]                      // labels point away from the middle
      const put = (job, icon, z, click) => {
        const m = L.marker(at(job), { icon, interactive: Boolean(click), keyboard: false, zIndexOffset: z, title: click ? `Show the crew's route to ${poleName(job)}` : '' }).addTo(group)
        if (click) m.on('click', click)
      }
      if (!r) {
        plan.poles.forEach(({ job, pos }) => put(job, equipment('wait', '?', job, '', flip(pos), false), 300))
      } else {
        r.done.forEach(({ job }) => put(job, equipment('done', TICK, job, '', flip(at(job)), false), 250))
        r.held.forEach(({ job }) => put(job, equipment('hold', PAUSE, job, '', flip(at(job)), false), 300))
        r.go.forEach((job, i) => {
          const on = job.pole_id === active
          const eta = minutes(job.eta_seconds)
          const line = i === 0 ? `Check first${eta ? `, crew ETA ${eta}` : ''}` : eta ? `Crew ETA ${eta}` : 'Next'
          put(job, equipment(i === 0 ? 'first' : 'next', i + 1, job, line, flip(at(job)), on), (on ? 900 : 600) - i * 10, () => pick.current(job.pole_id))
        })
      }
      if (plan.office) {
        L.marker(plan.office.pos, {
          icon: L.divIcon({ className: '', iconSize: [150, 26], iconAnchor: [13, 13], html: `<div class="office-mk"><i>M</i><span>${esc(plan.office.name)}</span></div>` }),
          interactive: false, keyboard: false, zIndexOffset: 450,
        }).addTo(group)
      }
    })
    return () => { map.removeLayer(group) }
  }, [map, version]) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}
