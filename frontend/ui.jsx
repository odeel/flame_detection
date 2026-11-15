// Shared UI primitives. Styling lives in styles/components.css.
import { useId } from 'react';

export const cx = (...a) => a.filter(Boolean).join(' ');

/* ------------------------------------------------------------------ icons */
const PATHS = {
  flame: 'M12 2c1 3 4 5 4 9a4 4 0 0 1-8 0c0-1.5.5-2.5 1.2-3.4C9.5 9 10 10 11 10.5 11 7 11 4.5 12 2Zm0 20a7 7 0 0 1-7-7c0-2 .8-3.6 1.8-5',
  globe: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm-9 9h18M12 3c2.5 2.7 3.5 5.7 3.5 9S14.5 18.3 12 21c-2.5-2.7-3.5-5.7-3.5-9S9.5 5.7 12 3Z',
  beaker: 'M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4a2 2 0 0 0 1.8-3l-5-9V3M7.5 14h9',
  shield: 'M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6l-8-3Zm-3 9 2 2 4-4',
  chart: 'M4 20V10m6 10V4m6 16v-7m4 7H2',
  alert: 'M12 9v4m0 4h.01M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z',
  check: 'M5 12.5 10 17 19 7',
  refresh: 'M20 11a8 8 0 0 0-14.9-3M4 4v4h4m-4 5a8 8 0 0 0 14.9 3M20 20v-4h-4',
  sparkle: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Zm7 12 .8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z',
  book: 'M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5Zm0 16a2 2 0 0 1 2-2h13',
  rocket: 'M5 15c-1.5 1.5-2 5-2 5s3.5-.5 5-2m-1-4 3 3m1-10c3-3 7-3.5 9-3-.5 2-1 6-4 9l-4 3-4-4 3-5Zm2.5 1.5h.01',
  menu: 'M4 7h16M4 12h16M4 17h16',
  close: 'M6 6l12 12M18 6 6 18',
  up: 'M12 19V5m-6 6 6-6 6 6',
  down: 'M12 5v14m6-6-6 6-6-6',
  target: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 4a5 5 0 1 0 0 10 5 5 0 0 0 0-10Zm0 4a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z',
  layers: 'm12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5',
  gauge: 'M12 14l4-4M4.9 19a9 9 0 1 1 14.2 0',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 9a7 7 0 0 1 14 0',
  chat: 'M21 12a8 8 0 0 1-11.8 7L4 20l1.2-4.4A8 8 0 1 1 21 12Z',
  wrench: 'M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.6 2.6-2.4-.6-.6-2.4 2.6-2.6Z',
  grad: 'M2 9l10-5 10 5-10 5L2 9Zm4 2v5c3 2 9 2 12 0v-5M22 9v6',
  sun: 'M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10Zm0-5v2m0 16v2M4.2 4.2l1.4 1.4m12.8 12.8 1.4 1.4M2 12h2m16 0h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4',
  moon: 'M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z',
  logout: 'M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l5-5-5-5m5 5H3',
  eye: 'M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Zm10-3a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z',
  info: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 8v5m0-8h.01',
  arrowRight: 'M5 12h14m-6-6 6 6-6 6',
  history: 'M3 12a9 9 0 1 0 3-6.7L3 8m0-5v5h5m4-1v5l3 2',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14Zm9 16-4-4',
  upload: 'M12 16V4m-5 5 5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3',
  file: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Zm0 0v5h5M9 13h6m-6 4h6',
  download: 'M12 4v12m-5-5 5 5 5-5M4 20h16',
  external: 'M14 4h6v6m0-6-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5',
  graph: 'M6 6a2 2 0 1 0 0 .01M18 6a2 2 0 1 0 0 .01M12 18a2 2 0 1 0 0 .01M7.5 7.5 11 16m5.5-8.5L13 16M8 6h8',
};
export function Icon({ name, className = '', title }) {
  return (
    <svg className={cx('icon', className)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden={title ? undefined : true} role={title ? 'img' : undefined}>
      {title && <title>{title}</title>}<path d={PATHS[name] || PATHS.info} />
    </svg>
  );
}

/* ------------------------------------------------------------------ layout */
export function Card({ title, sub, eyebrow, icon, actions, span, variant, stale, interactive, className, children, as: Tag = 'section', ...rest }) {
  return (
    <Tag className={cx('card', span && `span-${span}`, variant && `card--${variant}`, interactive && 'card--interactive', stale && 'is-stale', className)} aria-busy={stale || undefined} {...rest}>
      {(title || actions || eyebrow) && (
        <header className="card-h">
          <div>
            {eyebrow && <p className="eyebrow">{eyebrow}</p>}
            {title && <h3 className="card-t">{icon && <Icon name={icon} />}{title}</h3>}
            {sub && <p className="card-sub">{sub}</p>}
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      {children}
    </Tag>
  );
}

export function SectionHeader({ eyebrow, title, desc, actions, id }) {
  return (
    <header className="section-h">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h2 id={id}>{title}</h2>
        {desc && <p className="lead">{desc}</p>}
      </div>
      {actions && <div className="cluster">{actions}</div>}
    </header>
  );
}

export function Section({ id, eyebrow, title, desc, actions, children }) {
  const hid = id ? `${id}-h` : undefined;
  return (
    <section className="section" id={id} aria-labelledby={hid}>
      <SectionHeader id={hid} eyebrow={eyebrow} title={title} desc={desc} actions={actions} />
      {children}
    </section>
  );
}

export function Badge({ tone, plain, children, title }) {
  return <span className={cx('badge', tone && `badge--${tone}`, plain && 'plain')} title={title}>{children}</span>;
}

/* ------------------------------------------------------------------ inputs */
export function Tabs({ items, value, onChange, label }) {
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {items.map((it) => {
        const id = typeof it === 'string' ? it : it.id, text = typeof it === 'string' ? it : it.label;
        return <button key={id} type="button" role="tab" aria-selected={value === id} className={value === id ? 'on' : ''} onClick={() => onChange(id)}>{text}</button>;
      })}
    </div>
  );
}

export function Segmented({ options, value, onChange, label, block }) {
  return (
    <div className={cx('seg', block && 'block')} role="group" aria-label={label}>
      {options.map((o) => {
        const v = typeof o === 'string' ? o : o.value, l = typeof o === 'string' ? o : o.label;
        return <button key={v} type="button" className={v === value ? 'on' : ''} aria-pressed={v === value} onClick={() => onChange(v)}>{l}</button>;
      })}
    </div>
  );
}

/**
 * Range slider with a value readout, filled track, optional "tested range" band and marker.
 * log=true maps the track logarithmically (for pressure).
 */
export function Slider({ label, value, min, max, step = 1, unit, onChange, band, marker, log, format = (v) => v, foot, hint }) {
  const id = useId();
  const L = (v) => Math.log(v), toPos = (v) => (log ? (L(v) - L(min)) / (L(max) - L(min)) : (v - min) / (max - min));
  const clamp = (p) => Math.max(0, Math.min(1, p));
  const pos = clamp(toPos(value ?? min));
  const fromTrack = (t) => (log ? Math.exp(L(min) + (t / 1000) * (L(max) - L(min))) : +t);
  const round = (v) => Math.round(v / step) * step;
  const pct = (v) => `${clamp(toPos(v)) * 100}%`;
  return (
    <div className="slider">
      <div className="slider-top">
        <label htmlFor={id}>{label}</label>
        <output htmlFor={id} className="slider-val">{format(value)}{unit && <small>{unit}</small>}</output>
      </div>
      <div className="slider-track">
        {band && <span className="slider-band" style={{ left: pct(band[0]), width: `calc(${pct(band[1])} - ${pct(band[0])})` }} title="Range covered by NASA tests" />}
        {marker != null && <span className="slider-marker" style={{ left: pct(marker) }} title="Habitat value" />}
        <input
          id={id}
          type="range"
          min={log ? 0 : min}
          max={log ? 1000 : max}
          step={log ? 1 : step}
          value={log ? Math.round(pos * 1000) : value ?? min}
          onChange={(e) => onChange(+round(fromTrack(e.target.value)).toFixed(4))}
          style={{ '--fill': `${pos * 100}%` }}
          aria-valuetext={`${format(value)} ${unit || ''}`}
          aria-describedby={hint ? id + '-h' : undefined}
        />
      </div>
      {(foot || hint) && <div className="slider-foot"><span id={id + '-h'}>{hint}</span><span>{foot}</span></div>}
    </div>
  );
}

/* ------------------------------------------------------------------ data display */
export function KpiTile({ icon = 'chart', value, label, note, tone }) {
  return (
    <div className={cx('card kpi', tone && `kpi--${tone}`)}>
      <span className="kpi-ic"><Icon name={icon} /></span>
      <b className="kpi-v">{value}</b>
      <span className="kpi-l">{label}</span>
      {note && <span className="kpi-n">{note}</span>}
    </div>
  );
}

/** Horizontal meter: shaded low–high band (90 % interval) plus a mean marker. */
export function IntervalMeter({ mean, low, high, min = 0, max = 1, color = 'var(--accent)', format = (v) => v, labels, caption }) {
  const p = (v) => `${Math.max(0, Math.min(1, (v - min) / (max - min))) * 100}%`;
  return (
    <div className="meter">
      <div className="meter-track" role="img" aria-label={`Mean ${format(mean)}, 90% interval ${format(low)} to ${format(high)}`}>
        <span className="meter-band" style={{ left: p(low), width: `calc(${p(high)} - ${p(low)})`, background: color }} />
        <span className="meter-mean" style={{ left: p(mean), background: color, color }} />
      </div>
      <div className="meter-scale"><span>{labels?.[0] ?? format(min)}</span><span>{caption ?? `90 %: ${format(low)} – ${format(high)}`}</span><span>{labels?.[1] ?? format(max)}</span></div>
    </div>
  );
}

export function Gauge({ value, label = 'Relevance', size = 68 }) {
  const r = 26, c = 2 * Math.PI * r, col = value >= 75 ? 'var(--primary)' : value >= 50 ? 'var(--accent)' : 'var(--text-subtle)';
  return (
    <div className="gauge" role="img" aria-label={`${label} ${value} out of 100`}>
      <svg viewBox="0 0 64 64" width={size} height={size}><circle cx="32" cy="32" r={r} className="g-bg" /><circle cx="32" cy="32" r={r} className="g-fg" stroke={col} strokeDasharray={`${(value / 100) * c} ${c}`} transform="rotate(-90 32 32)" /><text x="32" y="38" textAnchor="middle">{value}</text></svg>
      <span>{label}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ states */
export function Skeleton({ lines = 3, height }) {
  if (height) return <div className="skel" aria-label="Loading" role="status"><i className="skel-block" style={{ height }} /></div>;
  return <div className="skel" aria-label="Loading" role="status">{Array.from({ length: lines }, (_, i) => <i key={i} />)}</div>;
}

export function EmptyState({ icon = 'search', title, hint, action, compact }) {
  return (
    <div className={cx('state', compact && 'compact')}>
      <span className="state-ic"><Icon name={icon} /></span>
      {title && <h4>{title}</h4>}
      {hint && <p>{hint}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry, compact }) {
  return (
    <div className={cx('state state--error', compact && 'compact')} role="alert">
      <span className="state-ic"><Icon name="alert" /></span>
      <h4>Couldn’t load this</h4>
      <p>{message}</p>
      {onRetry && <button type="button" className="btn-quiet btn-sm" onClick={onRetry}><Icon name="refresh" /> Retry</button>}
    </div>
  );
}

/**
 * Renders the right state for a useApi() result:
 *   first load -> skeleton, error -> ErrorState with Retry, empty -> EmptyState, else children(data).
 */
export function Async({ state, skeleton, empty, isEmpty, compact, children }) {
  if (state.error && !state.data) return <ErrorState message={state.error} onRetry={state.reload} compact={compact} />;
  if (state.data == null) return state.loading ? (skeleton || <Skeleton />) : null;
  if (empty && (isEmpty ? isEmpty(state.data) : Array.isArray(state.data) && !state.data.length)) return empty;
  return children(state.data);
}

export function Note({ tone = 'warning', icon = 'alert', children }) {
  return <div className={cx('note', tone === 'info' && 'note--info')}><Icon name={tone === 'info' ? 'info' : icon} /><div>{children}</div></div>;
}
