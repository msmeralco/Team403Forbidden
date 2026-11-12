// Small icon set. Stroke icons for the interface, filled marks for the report channels.
const S = { fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' }
const icon = (body, filled = false) => function Icon({ size = 18, ...rest }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" {...(filled ? { fill: 'currentColor' } : S)} {...rest}>
      {body}
    </svg>
  )
}

export const Search = icon(<><circle cx="11" cy="11" r="6.5" /><path d="m20 20-4.2-4.2" /></>)
export const Back = icon(<path d="M19 12H5m6-6-6 6 6 6" />)
export const Close = icon(<path d="M6 6l12 12M18 6 6 18" />)
export const Menu = icon(<path d="M4 7h16M4 12h16M4 17h16" />)
export const Bell = icon(<><path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15L6 16Z" /><path d="M10 21h4" /></>)
export const People = icon(<><circle cx="9" cy="8" r="3.2" /><path d="M3 20c0-3.3 2.7-5.5 6-5.5s6 2.2 6 5.5" /><path d="M16 4.8a3.2 3.2 0 0 1 0 6.3M18 14.8c1.8.7 3 2.4 3 5.2" /></>)
export const Home = icon(<><path d="M4 11 12 4l8 7" /><path d="M6 10v10h12V10" /></>)
export const Hospital = icon(<><rect x="4" y="4" width="16" height="16" rx="3" /><path d="M12 8v8M8 12h8" /></>)
export const Alert = icon(<><path d="M12 3.5 2.5 20h19L12 3.5Z" /><path d="M12 10v4.5M12 17.5v.01" /></>)
export const Truck = icon(<><path d="M3 6h11v10H3zM14 10h4l3 3v3h-7" /><circle cx="7" cy="17.5" r="1.8" /><circle cx="17" cy="17.5" r="1.8" /></>)
export const Pin = icon(<><path d="M12 21s7-6.2 7-11.5a7 7 0 0 0-14 0C5 14.8 12 21 12 21Z" /><circle cx="12" cy="9.5" r="2.5" /></>)
export const External = icon(<><path d="M14 4h6v6M20 4l-9 9" /><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></>)
export const Route = icon(<><circle cx="6" cy="18" r="2" /><circle cx="18" cy="6" r="2" /><path d="M8 18h6.5a3.5 3.5 0 0 0 0-7h-5a3.5 3.5 0 0 1 0-7H16" /></>)
export const Check = icon(<path d="m5 12.5 4.5 4.5L19 7.5" />)
export const Shield = icon(<><path d="M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6l-7-3Z" /><path d="m9 12 2 2 4-4" /></>)
export const Quiet = icon(<><path d="M5 9h3l5-4v14l-5-4H5z" /><path d="m17 9 4 6m0-6-4 6" /></>)
export const Landmark = icon(<><path d="M4 20h16M6 20V10M10 20V10M14 20V10M18 20V10" /><path d="M3 10h18L12 4 3 10Z" /></>)
export const Camera = icon(<><path d="M4 8h3l1.5-2h7L17 8h3v11H4z" /><circle cx="12" cy="13" r="3.2" /></>)
export const Pencil = icon(<><path d="M4 20h4L19 9l-4-4L4 16v4Z" /><path d="m13.5 6.5 4 4" /></>)
export const Layers = icon(<><path d="m12 4 9 5-9 5-9-5 9-5Z" /><path d="m3 14 9 5 9-5" /></>)
export const Pylon = icon(<path d="M9 21 11 3h2l2 18M5.5 8h13M7.5 13.5h9M10.5 8l3.5 5.5M13.5 8 10 13.5" />)
export const Office = icon(<><path d="M5 21V5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v16M15 10h3a1 1 0 0 1 1 1v10M3 21h18" /><path d="M8.5 8h3M8.5 12h3M8.5 16h3" /></>)
export const Road = icon(<><path d="M8 3 4 21M16 3l4 18" /><path d="M12 5v2m0 4v2m0 4v2" /></>)
export const Download = icon(<><path d="M12 4v11m-5-5 5 5 5-5" /><path d="M5 20h14" /></>)
export const Mail = icon(<><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m4 7 8 6 8-6" /></>)
export const Play = icon(<path d="M8 5v14l11-7L8 5Z" />, true)
export const Pause = icon(<path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z" />, true)
export const Clock = icon(<><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></>)
export const Spark = icon(<path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" />, true)
export const Photo = icon(<><rect x="3" y="5" width="18" height="14" rx="2" /><circle cx="9" cy="10" r="1.8" /><path d="m21 16-5-5-9 8" /></>)
export const Globe = icon(<><circle cx="12" cy="12" r="8.5" /><path d="M3.5 12h17M12 3.5c2.5 2.6 2.5 14.4 0 17M12 3.5c-2.5 2.6-2.5 14.4 0 17" /></>)
export const ThumbUp = icon(<><path d="M7 11v9H4v-9h3Z" /><path d="M7 11 11 4c1.5 0 2.5 1 2.2 2.5L12.5 10H19a2 2 0 0 1 2 2.3l-1.2 6A2 2 0 0 1 17.8 20H7" /></>)
export const Comment = icon(<path d="M4 5h16v11H9l-5 4V5Z" />)
export const Share = icon(<><path d="M14 5l6 6-6 6" /><path d="M20 11H10a6 6 0 0 0-6 6v2" /></>)
export const Repost = icon(<><path d="M7 7h11l-3-3M17 17H6l3 3" /><path d="M18 7v5M6 17v-5" /></>)
export const Heart = icon(<path d="M12 20s-7.5-4.6-7.5-10A4.3 4.3 0 0 1 12 7.4 4.3 4.3 0 0 1 19.5 10c0 5.4-7.5 10-7.5 10Z" />)
export const Views = icon(<path d="M5 20V12M10 20V6M15 20v-9M20 20V4" />)

// Channel marks (generic glyphs, filled).
export const FacebookMark = icon(<path d="M14 8.2h2.6V5H14c-2.4 0-4 1.8-4 4.2V11H8v3.2h2V21h3.3v-6.8h2.6l.5-3.2h-3.1V9.4c0-.7.3-1.2.7-1.2Z" />, true)
export const XMark = icon(<path d="M17.7 3.5h3l-6.6 7.6 7.8 9.4h-6.1l-4.8-5.8-5.5 5.8h-3l7-8.1L2.2 3.5h6.2l4.3 5.3 5-5.3Zm-1 15.2h1.7L7.4 5.2H5.6l11.1 13.5Z" />, true)
export const SmsMark = icon(<path d="M5 4h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9.5L5 20.5V17a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Zm3 6.2a1.2 1.2 0 1 0 0 .01Zm4 0a1.2 1.2 0 1 0 0 .01Zm4 0a1.2 1.2 0 1 0 0 .01Z" />, true)
export const PhoneMark = icon(<path d="M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1A17 17 0 0 1 3 4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.3 0 .7-.2 1l-2.3 2.2Z" />, true)
export const AppMark = Spark

export const SOURCE_ICON = {
  facebook_post: FacebookMark, facebook_comment: FacebookMark, x: XMark,
  sms: SmsMark, hotline: PhoneMark, app: AppMark,
}

// Raw SVG strings for Leaflet markers, which take HTML rather than React elements.
export const svg = {
  people: '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.3 2.7-5.5 6-5.5s6 2.2 6 5.5"/><path d="M16 4.8a3.2 3.2 0 0 1 0 6.3M18 14.8c1.8.7 3 2.4 3 5.2"/></svg>',
  truck: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h11v10H3zM14 10h4l3 3v3h-7"/><circle cx="7" cy="17.5" r="1.8"/><circle cx="17" cy="17.5" r="1.8"/></svg>',
  hospital: '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"><path d="M12 6v12M6 12h12"/></svg>',
  target: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2.2" fill="currentColor"/><path d="M12 1.5v3M12 19.5v3M1.5 12h3M19.5 12h3"/></svg>',
  closed: '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round"><path d="M6 12h12"/></svg>',
  source: {
    facebook_post: '<svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M14 8.2h2.6V5H14c-2.4 0-4 1.8-4 4.2V11H8v3.2h2V21h3.3v-6.8h2.6l.5-3.2h-3.1V9.4c0-.7.3-1.2.7-1.2Z"/></svg>',
    x: '<svg viewBox="0 0 24 24" width="11" height="11" fill="currentColor"><path d="M17.7 3.5h3l-6.6 7.6 7.8 9.4h-6.1l-4.8-5.8-5.5 5.8h-3l7-8.1L2.2 3.5h6.2l4.3 5.3 5-5.3Z"/></svg>',
    sms: '<svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M5 4h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9.5L5 20.5V17a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z"/></svg>',
    hotline: '<svg viewBox="0 0 24 24" width="11" height="11" fill="currentColor"><path d="M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1A17 17 0 0 1 3 4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.3 0 .7-.2 1l-2.3 2.2Z"/></svg>',
    app: '<svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z"/></svg>',
  },
}
svg.source.facebook_comment = svg.source.facebook_post
