// Liwa's framework, drawn as a retrieval-augmented generation diagram: the interruption is the
// prompt, the reference database is the document store, Claude is the generator.
import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Close } from '../icons'

const INK = '#1f1f1f'
const MUTED = '#5e6368'

function Lines({ x, y, lines, size = 13, color = MUTED, weight = 400, gap = 17 }) {
  return (
    <text x={x} y={y} textAnchor="middle" fontSize={size} fill={color} fontWeight={weight}>
      {lines.map((l, i) => <tspan key={i} x={x} dy={i ? gap : 0}>{l}</tspan>)}
    </text>
  )
}

function Diagram({ model, policies, examples }) {
  const arrow = { stroke: INK, strokeWidth: 2, markerEnd: 'url(#fw-arrow)' }
  const dashed = { stroke: MUTED, strokeWidth: 1.6, strokeDasharray: '5 4', fill: 'none', markerEnd: 'url(#fw-arrow-muted)' }
  return (
    <svg className="fw-svg" viewBox="0 0 960 490" role="img"
      aria-label="Liwa's retrieval augmented generation. The interruption's facts are used as a search query on the reference database; keyword and meaning search, merged by reciprocal rank fusion, return the policy records and the three closest worked examples. These are added to the prompt for Claude, whose reply is validated; if it is unusable twice, the database's own SQL rule answers.">
      <defs>
        <marker id="fw-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0 0 10 5 0 10Z" fill={INK} />
        </marker>
        <marker id="fw-arrow-muted" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0 0 10 5 0 10Z" fill={MUTED} />
        </marker>
      </defs>

      {/* Title */}
      <rect x="300" y="16" width="360" height="46" rx="10" fill="#cfe8fb" />
      <Lines x={480} y={46} lines={['Retrieval Augmented Generation']} size={20} color="#0b57d0" weight={600} />

      {/* Prompt */}
      <rect x="20" y="106" width="200" height="104" rx="4" fill="#fff" stroke={INK} strokeWidth="2" />
      <Lines x={120} y={134} lines={['Prompt']} size={17} color={INK} weight={700} />
      <Lines x={120} y={156} lines={['the interruption: every pole’s', 'safety, flood, tier, customers,', 'driving ETA, and what', 'customers reported']} size={11.5} gap={14} />

      {/* Generator */}
      <rect x="290" y="112" width="200" height="92" rx="6" fill="#a3157e" />
      <Lines x={390} y={143} lines={['Generator']} size={17} color="#fff" weight={700} />
      <Lines x={390} y={165} lines={[model || 'Claude Opus 5.5', 'Claude Code CLI, no tools']} size={12.5} color="#fbe3f3" gap={17} />

      {/* Validator */}
      <rect x="560" y="118" width="170" height="80" rx="4" fill="#fff" stroke={INK} strokeWidth="2" />
      <Lines x={645} y={145} lines={['Validator']} size={15} color={INK} weight={700} />
      <Lines x={645} y={165} lines={['readable JSON, real poles only;', 'if not, asked once more']} size={11.5} gap={14} />

      {/* Response */}
      <rect x="790" y="118" width="155" height="80" rx="4" fill="#b9f0b3" stroke={INK} strokeWidth="2" />
      <Lines x={867} y={145} lines={['Response']} size={16} color={INK} weight={700} />
      <Lines x={867} y={165} lines={['dispatch or hold, the', 'order, a reason for each']} size={11.5} color="#2d4a2b" gap={14} />

      <line x1="220" y1="158" x2="286" y2="158" {...arrow} />
      <line x1="490" y1="158" x2="556" y2="158" {...arrow} />
      <line x1="730" y1="158" x2="786" y2="158" {...arrow} />

      {/* SQL rule: fallback, and shown beside her answer */}
      <path d="M645 198 V286" {...dashed} />
      <text x="653" y="246" fontSize="11" fill={MUTED}>still unusable</text>
      <rect x="560" y="290" width="170" height="80" rx="8" fill="#fff" stroke={MUTED} strokeWidth="1.6" strokeDasharray="5 4" />
      <Lines x={645} y={315} lines={['SQL rule']} size={14} color={INK} weight={700} />
      <Lines x={645} y={334} lines={['the test database’s own query;', 'shown beside her answer']} size={11.5} gap={14} />
      <path d="M730 330 H867 V202" {...dashed} />

      {/* Search query */}
      <line x1="120" y1="210" x2="120" y2="272" {...arrow} />
      <text x="128" y="234" fontSize="11.5" fill={INK} fontWeight="600">search query</text>
      <text x="128" y="249" fontSize="11" fill={MUTED}>the case and each pole’s</text>
      <text x="128" y="263" fontSize="11" fill={MUTED}>place, safety, flood, tier</text>

      {/* Document store */}
      <path d="M80 290 v62 a40 12 0 0 0 80 0 v-62" fill="#2b9fd8" />
      <ellipse cx="120" cy="290" rx="40" ry="12" fill="#6cc4ee" />
      <Lines x={120} y={392} lines={['Document store']} size={14} color={INK} weight={700} />
      <Lines x={120} y={411} lines={['reference database (SQLite):', `${policies || 'the'} policy records,`, `${examples || 'the'} worked examples`]} size={11.5} gap={14} />

      {/* Hybrid search */}
      <line x1="176" y1="322" x2="342" y2="322" {...arrow} />
      <Lines x={259} y={286} lines={['keyword search (FTS5)', '+ meaning search (sqlite-vec)']} size={11.5} color={INK} gap={14} />
      <Lines x={259} y={343} lines={['bge-small embeddings,', 'run on this computer;', 'merged by rank fusion']} size={11} gap={13} />

      {/* Retrieved documents */}
      {[0, 1, 2, 3].map((i) => {
        const x = 350 + i * 7
        const y = 284 + i * 6
        return (
          <g key={i}>
            <rect x={x} y={y} width="56" height="68" rx="3" fill="#fff" stroke="#3c3f8f" strokeWidth="1.6" />
            {i === 3 && [0, 1, 2, 3, 4, 5].map((k) => (
              <line key={k} x1={x + 9} x2={x + (k % 2 ? 38 : 47)} y1={y + 13 + k * 8.5} y2={y + 13 + k * 8.5} stroke="#3c3f8f" strokeWidth="1.4" />
            ))}
          </g>
        )
      })}
      <line x1="390" y1="278" x2="390" y2="208" {...arrow} />
      <text x="398" y="246" fontSize="11" fill={MUTED}>added to the prompt</text>
      <Lines x={390} y={392} lines={['Retrieved documents']} size={14} color={INK} weight={700} />
      <Lines x={390} y={411} lines={['every policy record, most', 'relevant first, and the 3 closest', 'worked examples (never the', 'case’s own)']} size={11.5} gap={14} />
    </svg>
  )
}

export default function Framework({ model, policies, examples, onClose }) {
  const closeBtn = useRef(null)
  useEffect(() => {
    closeBtn.current?.focus({ preventScroll: true })
    const esc = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', esc)
    return () => window.removeEventListener('keydown', esc)
  }, [onClose])

  return createPortal(
    <div className="fw-back" onClick={onClose}>
      <section className="fw" role="dialog" aria-modal="true" aria-label="Liwa's framework" onClick={(e) => e.stopPropagation()}>
        <button ref={closeBtn} className="icon-btn fw-close" onClick={onClose} aria-label="Close the framework"><Close size={16} /></button>
        <div className="fw-scroll"><Diagram model={model} policies={policies} examples={examples} /></div>
      </section>
    </div>,
    document.body,
  )
}
