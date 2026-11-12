import { CATEGORY, SOURCES, ago, clock, day, fmt } from '../theme'
import {
  Comment, Globe, Heart, Photo, Repost, SOURCE_ICON, Share, ThumbUp, Views,
} from '../icons'

const AVATAR = ['#5B6EAE', '#3E8E7E', '#A0522D', '#7A5BA6', '#2F7FB5', '#8C6D1F', '#B5476A', '#4F7A3A']
const avatarColor = (id) => AVATAR[[...id].reduce((s, c) => s + c.charCodeAt(0), 0) % AVATAR.length]

export function SourceBadge({ source, size = 26 }) {
  const Icon = SOURCE_ICON[source]
  return (
    <span className={`src s-${source}`} style={{ width: size, height: size }} title={SOURCES[source].label}>
      <Icon size={Math.round(size * 0.55)} />
    </span>
  )
}

function Avatar({ r, size = 40 }) {
  return <span className="avatar" style={{ width: size, height: size, background: avatarColor(r.person_id) }}>{r.initials}</span>
}

// Mentions and hashtags in the channel's link color, the way the apps show them.
function Rich({ text }) {
  return text.split(/(@\w+|#\w+)/g).map((part, i) => (/^[@#]\w+/.test(part) ? <span key={i} className="mention">{part}</span> : part))
}

export function Tag({ r }) {
  if (r.category === 'hazard') return <span className="tag hazard">{r.tag_label}</span>
  if (r.category === 'clue') return <span className="tag clue">{r.tag_label}</span>
  if (r.category === 'noise') return <span className="tag noise">{r.tag_label}</span>
  if (r.category === 'restored') return <span className="tag back">Power is back</span>
  if (r.after_repair) return <span className="tag noise">Still dark after repair</span>
  return null
}

// One line in a list: channel, who, when, what they said.
export function ReportRow({ r, now, onOpen, showPlace = true }) {
  return (
    <li>
      <button className="report-row" onClick={onOpen}>
        <SourceBadge source={r.source} />
        <span className="rr-body">
          <span className="rr-head">
            <strong>{r.author}</strong>
            <span className="muted">{SOURCES[r.source].short}</span>
            <span className="muted rr-time">{ago(r.time, now)}</span>
          </span>
          <span className="rr-text">{r.text || <em className="muted">No description. Outage type: {r.meta.outage_type}</em>}</span>
          <span className="rr-foot">
            <Tag r={r} />
            {r.vulnerable && <span className="tag care">Vulnerable person mentioned</span>}
            {showPlace && <span className="muted">Brgy. {r.barangay}, {r.city.split(',')[0]}</span>}
          </span>
        </span>
      </button>
    </li>
  )
}

function FacebookPost({ r, now }) {
  const m = r.meta
  return (
    <article className="sc fb">
      <header className="fb-head">
        <Avatar r={r} />
        <div>
          <strong>{r.author}</strong>
          <span className="muted small fb-meta">{ago(r.time, now)} <Globe size={12} /></span>
        </div>
      </header>
      <p className="fb-text"><Rich text={r.text} /></p>
      <div className="fb-counts muted small">
        <span className="fb-reacts"><i className="re like"><ThumbUp size={10} /></i><i className="re sad">😢</i>{fmt(m.reactions)}</span>
        <span>{fmt(m.comments)} comments  {fmt(m.shares)} shares</span>
      </div>
      <footer className="fb-actions muted">
        <span><ThumbUp size={16} />Like</span><span><Comment size={16} />Comment</span><span><Share size={16} />Share</span>
      </footer>
    </article>
  )
}

function FacebookComment({ r, now }) {
  const m = r.meta
  return (
    <article className="sc fbc">
      <div className="fbc-parent">
        <span className="avatar meralco">M</span>
        <div>
          <strong>Meralco</strong>
          <p className="muted small">{m.on_post}</p>
        </div>
      </div>
      <div className="fbc-comment">
        <Avatar r={r} size={32} />
        <div>
          <div className="fbc-bubble">
            <strong>{r.author}</strong>
            <p><Rich text={r.text} /></p>
            {m.reactions > 0 && <span className="fbc-react"><i className="re like"><ThumbUp size={9} /></i>{m.reactions}</span>}
          </div>
          <div className="fbc-links muted small"><span>{ago(r.time, now)}</span><b>Like</b><b>Reply</b>{m.replies > 0 && <span>{m.replies} replies</span>}</div>
        </div>
      </div>
    </article>
  )
}

function XPost({ r, now }) {
  const m = r.meta
  return (
    <article className="sc x">
      <Avatar r={r} />
      <div className="x-body">
        <div className="x-head"><strong>{r.author}</strong><span className="muted">{m.handle}</span><span className="muted">{ago(r.time, now)}</span></div>
        <p><Rich text={r.text} /></p>
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

function Hotline({ r }) {
  const m = r.meta
  const emergency = m.call_category.startsWith('Emergency')
  return (
    <article className="sc ticket">
      <header className="tk-head">
        <div><span className="muted small">Hotline 16211 call ticket</span><strong>{m.ticket}</strong></div>
        <span className={`tk-cat${emergency ? ' em' : ''}`}>{m.call_category}</span>
      </header>
      <dl className="tk-grid">
        <dt>Caller</dt><dd>{m.caller}</dd>
        <dt>Logged</dt><dd>{day(r.time)}, {clock(r.time)}</dd>
        <dt>Call length</dt><dd>{m.duration}</dd>
        <dt>Agent</dt><dd>{m.agent}</dd>
        <dt>Location</dt><dd>Brgy. {r.barangay}, {r.city}</dd>
      </dl>
      <div className="tk-notes"><span className="muted small">Agent notes</span><p>{r.text}</p></div>
    </article>
  )
}

function AppReport({ r }) {
  const m = r.meta
  return (
    <article className="sc app">
      <header className="app-head"><SourceBadge source="app" size={24} /><strong>Report an outage</strong><span className="app-ok small">Submitted</span></header>
      <dl className="tk-grid">
        <dt>Reference no.</dt><dd>{m.ref}</dd>
        <dt>Service ID</dt><dd>{m.service_id}</dd>
        <dt>Account name</dt><dd>{m.account}</dd>
        <dt>Problem</dt><dd>{m.outage_type}</dd>
        <dt>Address</dt><dd>Brgy. {r.barangay}, {r.city}</dd>
        <dt>Submitted</dt><dd>{day(r.time)}, {clock(r.time)}</dd>
      </dl>
      <div className="tk-notes"><span className="muted small">Description</span><p>{r.text || <em className="muted">None given</em>}</p></div>
      {m.photo && <div className="app-photo"><Photo size={22} /><span>Photo attached</span></div>}
    </article>
  )
}

const CARDS = { facebook_post: FacebookPost, facebook_comment: FacebookComment, x: XPost, sms: Sms, hotline: Hotline, app: AppReport }

export function ReportFull({ r, now, also, onOpen, onArea }) {
  const Card = CARDS[r.source]
  return (
    <div className="report-full">
      <div className="rf-source"><SourceBadge source={r.source} size={30} /><div><strong>{SOURCES[r.source].label}</strong><span className="muted small">{clock(r.time)}, {ago(r.time, now)}</span></div></div>
      <Card r={r} now={now} />
      <section className="rf-triage">
        <h3>What FirstLook read from this</h3>
        <p><strong>{r.category === 'hazard' || r.category === 'clue' || r.category === 'noise' || r.category === 'restored' ? r.tag_label : r.after_repair ? 'Still no power after a repair' : CATEGORY[r.category]}</strong>
          {r.category === 'hazard' && '. Pinned to the top of the list until someone marks it made safe.'}
          {r.category === 'clue' && '. Hints at what broke, so whoever goes brings the right equipment.'}
          {r.category === 'noise' && '. Counts very little, because it may be one house, not the whole area.'}
          {r.category === 'restored' && '. Confirms the repair worked for this barangay.'}
          {r.after_repair && r.category !== 'restored' && '. Tells FirstLook another break is likely, so the area goes back on the Check next list.'}
          {!r.after_repair && (r.category === 'outage' || r.category === 'follow_up') && '. Counts as one more person without power in this barangay.'}
        </p>
        {r.vulnerable && <p>Mentions someone vulnerable (elderly, sick or a baby).</p>}
        {also.length > 0 ? (
          <div className="rf-also">
            <p>The same person also reported through {also.length === 1 ? 'one other channel' : `${also.length} other channels`}. FirstLook counts them once.</p>
            <ul>{also.map((o) => (
              <li key={o.id}><button className="chip-btn" onClick={() => onOpen(o.id)}><SourceBadge source={o.source} size={18} />{SOURCES[o.source].short}, {clock(o.time)}</button></li>
            ))}</ul>
          </div>
        ) : <p className="muted">Only report from this person.</p>}
        <button className="btn" onClick={onArea}>See all reports from Brgy. {r.barangay}</button>
      </section>
    </div>
  )
}
