import meralco from './assets/meralco.png'

// FirstLook mark: a scan ring closing in on the one point worth looking at first.
export function Mark({ size = 30 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="9" fill="#f47b20" />
      <path d="M16 7a9 9 0 1 0 9 9" stroke="#fff" strokeWidth="3" fill="none" strokeLinecap="round" />
      <circle cx="16" cy="16" r="3" fill="#fff" />
      <circle cx="23.5" cy="8.5" r="2.5" fill="#fff" />
    </svg>
  )
}

export function Wordmark() {
  return <span className="wordmark"><Mark />First<b>Look</b></span>
}

export function Meralco() {
  return <img className="meralco" src={meralco} alt="Meralco" title="Built for the Meralco IDOL Hackathon" />
}
