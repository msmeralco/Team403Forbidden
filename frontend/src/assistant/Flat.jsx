// Liwa drawn flat with CSS: used in the panel, while the 3D code loads, and when WebGL is unavailable.
export function Bolt({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M13.4 2 5.5 13.2h5.2L9.6 22l8.9-12.4h-5.4L13.4 2Z" fill="currentColor" />
    </svg>
  )
}

// `state` matches the 3D states: idle, listening, thinking, speaking, alert, success.
export function Flat({ state = 'idle', size = 40 }) {
  return (
    <span className={`flat is-${state}`} style={{ '--s': `${size}px` }} aria-hidden="true">
      <span className="flat-top" />
      <span className="flat-body">
        <span className="flat-visor"><i /><i /></span>
        <span className="flat-bolt"><Bolt size={Math.round(size * 0.3)} /></span>
      </span>
    </span>
  )
}
