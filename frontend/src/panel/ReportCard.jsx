// One customer report, shown the way its own channel shows it: a Facebook post or comment, an X
// post, a text message, a hotline call ticket, or a Meralco App report. The messages are invented.
import { Comment, Globe, Heart, Repost, SOURCE_ICON, Share, ThumbUp, Views } from '../icons'

const AVATAR = ['#5B6EAE', '#3E8E7E', '#A0522D', '#7A5BA6', '#2F7FB5', '#8C6D1F', '#B5476A', '#4F7A3A']
const avatarColor = (id) => AVATAR[[...id].reduce((s, c) => s + c.charCodeAt(0), 0) % AVATAR.length]
export const clock = (t) => new Date(t).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
const day = (t) => new Date(t).toLocaleDateString([], { month: 'short', day: 'numeric' })
const fmt = (n) => Number(n).toLocaleString()

// Who a report came from, the way that channel names them.
export function sender(r) {
  if (r.source === 'hotline') return `Call ${r.meta.ticket}`
  if (r.source === 'sms') return r.meta.from
  if (r.source === 'app') return `Account ${r.meta.service_id}`
  if (r.source === 'x') return r.meta.handle
  return r.person.name
}

export function SourceBadge({ source, size = 26 }) {
  const Icon = SOURCE_ICON[source]
  return <span className={`src s-${source}`} style={{ width: size, height: size }}><Icon size={Math.round(size * 0.55)} /></span>
}

function Avatar({ r, size = 40 }) {
  return <span className="avatar" style={{ width: size, height: size, background: avatarColor(r.id) }}>{r.person.initials}</span>
}

// Mentions and hashtags in the channel's link colour, the way the apps show them.
function Rich({ text }) {
  return text.split(/(@\w+|#\w+)/g).map((part, i) => (/^[@#]\w+/.test(part) ? <span key={i} className="mention">{part}</span> : part))
}

function Picture({ r, flush }) {
  if (!r.photo) return null
  return <img className={flush ? 'sc-photo flush' : 'sc-photo'} src={r.photo.url} alt={r.photo.shows} />
}

function FacebookPost({ r }) {
  const m = r.meta
  return (
    <article className="sc fb">
      <header className="fb-head">
        <Avatar r={r} />
        <div><strong>{r.person.name}</strong><span className="muted small fb-meta">{day(r.time)} at {clock(r.time)} <Globe size={12} /></span></div>
      </header>
      <p className="fb-text"><Rich text={r.text} /></p>
      <Picture r={r} flush />
      <div className="fb-counts muted small">
        <span className="fb-reacts"><i className="re like"><ThumbUp size={10} /></i><i className="re sad">😢</i>{fmt(m.reactions)}</span>
        <span>{fmt(m.comments)} comments  {fmt(m.shares)} shares</span>
      </div>
      <footer className="fb-actions muted"><span><ThumbUp size={16} />Like</span><span><Comment size={16} />Comment</span><span><Share size={16} />Share</span></footer>
    </article>
  )
}

function FacebookComment({ r }) {
  const m = r.meta
  return (
    <article className="sc fbc">
      <div className="fbc-parent">
        <span className="avatar meralco">M</span>
        <div><strong>Meralco</strong><p className="muted small">{m.on_post}</p></div>
      </div>
      <div className="fbc-comment">
        <Avatar r={r} size={32} />
        <div>
          <div className="fbc-bubble">
            <strong>{r.person.name}</strong>
            <p><Rich text={r.text} /></p>
            {m.reactions > 0 && <span className="fbc-react"><i className="re like"><ThumbUp size={9} /></i>{m.reactions}</span>}
          </div>
          <div className="fbc-links muted small"><span>{clock(r.time)}</span><b>Like</b><b>Reply</b>{m.replies > 0 && <span>{m.replies} replies</span>}</div>
        </div>
      </div>
    </article>
  )
}

function XPost({ r }) {
  const m = r.meta
  return (
    <article className="sc x">
      <Avatar r={r} />
      <div className="x-body">
        <div className="x-head"><strong>{r.person.name}</strong><span className="muted">{m.handle}</span><span className="muted">{clock(r.time)}</span></div>
        <p><Rich text={r.text} /></p>
        <Picture r={r} />
        <footer className="x-actions muted small">
          <span><Comment size={15} />{m.replies}</span><span><Repost size={15} />{m.reposts}</span>
          <span><Heart size={15} />{m.likes}</span><span><Views size={15} />{fmt(m.views)}</span>
        </footer>
      </div>
    </article>
  )
}

function Sms({ r }) {
  const m = r.meta
  return (
    <article className="sc sms">
      <header className="sms-head">
        <span className="avatar sms-av">#</span>
        <div><strong>{m.from}</strong><span className="muted small">to Meralco {m.to}</span></div>
      </header>
      <div className="sms-thread">
        <span className="sms-day muted small">{day(r.time)}, {clock(r.time)}</span>
        <p className="sms-bubble">{r.text}</p>
        <span className="muted small sms-status">Received</span>
      </div>
    </article>
  )
}

function Hotline({ r, place }) {
  const m = r.meta
  return (
    <article className="sc ticket">
      <header className="tk-head">
        <div><span className="muted small">Hotline 16211 call ticket</span><strong>{m.ticket}</strong></div>
        <span className={`tk-cat${r.hazard ? ' em' : ''}`}>{r.hazard ? 'Emergency' : 'No power'}</span>
      </header>
      <dl className="tk-grid">
        <dt>Caller</dt><dd>{m.caller}</dd>
        <dt>Logged</dt><dd>{day(r.time)}, {clock(r.time)}</dd>
        <dt>Call length</dt><dd>{m.duration}</dd>
        <dt>Agent</dt><dd>{m.agent}</dd>
        <dt>Location</dt><dd>{place}</dd>
      </dl>
      <div className="tk-notes"><span className="muted small">Agent notes</span><p>{r.text}</p></div>
    </article>
  )
}

function AppReport({ r, place }) {
  const m = r.meta
  return (
    <article className="sc app">
      <header className="app-head"><SourceBadge source="app" size={24} /><strong>Report an outage</strong><span className="app-ok small">Submitted</span></header>
      <dl className="tk-grid">
        <dt>Reference no.</dt><dd>{m.ref}</dd>
        <dt>Service ID</dt><dd>{m.service_id}</dd>
        <dt>Account name</dt><dd>{m.account}</dd>
        <dt>Problem</dt><dd>{r.hazard ? 'Hazard' : 'No power'}</dd>
        <dt>Address</dt><dd>{place}</dd>
        <dt>Submitted</dt><dd>{day(r.time)}, {clock(r.time)}</dd>
      </dl>
      <div className="tk-notes"><span className="muted small">Description</span><p>{r.text}</p></div>
      {r.photo && <div className="tk-notes"><span className="muted small">Photo attached</span><Picture r={r} /></div>}
    </article>
  )
}

const CARDS = { facebook_post: FacebookPost, facebook_comment: FacebookComment, x: XPost, sms: Sms, hotline: Hotline, app: AppReport }

// The whole report: the channel's own card, then what it is linked to and how it counts.
export function ReportFull({ r, place, about, unsafe }) {
  const Card = CARDS[r.source]
  return (
    <div className="report-full">
      <div className="rf-source"><SourceBadge source={r.source} size={30} /><div><strong>{r.label}</strong><span className="muted small">{day(r.time)}, {clock(r.time)}</span></div></div>
      <Card r={r} place={place} />
      {r.photo && <p className="muted small">The photo is a stand-in for the demo: {r.photo.shows.charAt(0).toLowerCase() + r.photo.shows.slice(1)}. It is not of this place.</p>}
      <section className="rf-triage">
        <h3>How this report counts</h3>
        <p className="rf-flags">
          <span className="tag noise">{about}</span>
          {r.hazard && <span className="tag hazard">{r.hazard}</span>}
          {r.vulnerable && <span className="tag clue">Depends on power</span>}
        </p>
        <p>
          It is one of the reports linked to {about.charAt(0).toLowerCase() + about.slice(1)}.
          {r.hazard && unsafe ? ' It describes a hazard, which agrees with this equipment being marked not safe for the crew.' : ''}
          {r.hazard && !unsafe ? ' It describes a hazard at equipment marked safe, so Liwa notes it for the crew to confirm on arrival.' : ''}
          {r.vulnerable ? ' It mentions someone who depends on power, so Liwa notes it for the crew and customer care.' : ''}
          {' '}One report does not move anything up the order by itself.
        </p>
      </section>
    </div>
  )
}
