import { useEffect, useRef, useState } from 'react';
import { ROLES } from './roles.js';
import { Icon, cx } from './ui.jsx';

// Stylized placeholder. For the real thing, download the official NASA insignia from NASA's brand page
// and swap this for <img src="/nasa-logo.svg" alt="NASA" />.
export function NasaLogo({ size = 40 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" aria-hidden="true">
      <circle cx="50" cy="50" r="48" fill="#0B3D91" />
      <path d="M8 62 C30 20 70 20 94 30 C62 28 36 40 8 62Z" fill="#FC3D21" />
      <text x="50" y="58" textAnchor="middle" fontFamily="Space Grotesk, sans-serif" fontWeight="700" fontStyle="italic" fontSize="24" fill="#fff">NASA</text>
    </svg>
  );
}

/** Sticky top bar. The logo + title is a button that goes home. Children are nav items (collapse into a menu on mobile). */
export function Corner({ theme, toggle, onHome, children }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => { if (e.key === 'Escape' || (e.type === 'pointerdown' && !ref.current?.contains(e.target))) setOpen(false); };
    addEventListener('keydown', close); addEventListener('pointerdown', close);
    return () => { removeEventListener('keydown', close); removeEventListener('pointerdown', close); };
  }, [open]);
  return (
    <header className="corner" ref={ref}>
      <div className="container corner-in">
      <button type="button" className="brand" onClick={onHome} aria-label="NASA Flame Smart Detection, go to home">
        <NasaLogo />
        <span className="brandtxt"><b>NASA Flame Smart Detection</b><span>Flame in Freefall</span></span>
      </button>
      <div className="corner-r">
        <nav className={cx('nav-links', open && 'open')} aria-label="Main" onClick={(e) => e.target.closest('button') && setOpen(false)}>
          {children}
          <button type="button" className="navbtn" onClick={toggle} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} />{theme === 'dark' ? 'Light' : 'Dark'}
          </button>
        </nav>
        <button type="button" className="ghost menu-btn" aria-expanded={open} aria-label="Menu" onClick={() => setOpen(!open)}><Icon name={open ? 'close' : 'menu'} /></button>
      </div>
      </div>
    </header>
  );
}

/** Role picker for signup: one card per role with a preview of its dashboard. */
export function RoleCards({ value, onChange }) {
  return (
    <div className="rolecards" role="radiogroup" aria-label="Mission profile">
      {Object.entries(ROLES).map(([k, r]) => (
        <button type="button" key={k} role="radio" aria-checked={k === value} className={cx('rolecard', k === value && 'on')} onClick={() => onChange(k)}>
          <span className="kpi-ic"><Icon name={r.icon} /></span>
          <span><b>{r.label}</b> <span className="muted text-xs">· {r.workspace}</span><p>{r.blurb}</p></span>
          <span className="tick" aria-hidden />
        </button>
      ))}
    </div>
  );
}

/** Left-hand brand panel on the auth pages. */
export function AuthHero() {
  return (
    <div className="auth-hero">
      <p className="eyebrow">Flame in Freefall · NASA PSI data</p>
      <h1>Fire behaves differently in space. <em>So should fire safety.</em></h1>
      <p className="hero-lead">Explore 24 NASA microgravity combustion investigations, simulate how flames behave in habitat atmospheres, and get cited answers from the data.</p>
      <ul className="auth-feats">
        <li><span className="kpi-ic"><Icon name="flame" /></span><span><b>Flame simulator</b>Predict droplet burning for any oxygen, pressure and diluent mix.</span></li>
        <li><span className="kpi-ic"><Icon name="globe" /></span><span><b>Habitat atmospheres</b>ISS, Gateway, Moon and Mars bases side by side.</span></li>
        <li><span className="kpi-ic"><Icon name="chat" /></span><span><b>Cited answers</b>Every AI answer links to the NASA passage it came from.</span></li>
      </ul>
    </div>
  );
}
