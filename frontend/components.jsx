import { ROLES } from './roles.js';

// Stylized placeholder. For the real thing, download the official NASA insignia from NASA's brand page
// and swap this for <img src="/nasa-logo.svg" alt="NASA" />.
export function NasaLogo({ size = 44 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" role="img" aria-label="NASA">
      <circle cx="50" cy="50" r="48" fill="#0B3D91" />
      <path d="M8 62 C30 20 70 20 94 30 C62 28 36 40 8 62Z" fill="#FC3D21" />
      <text x="50" y="58" textAnchor="middle" fontFamily="Space Grotesk, sans-serif" fontWeight="700" fontStyle="italic" fontSize="24" fill="#fff">NASA</text>
    </svg>
  );
}
export function Corner({ theme, toggle, children }) {
  return (
    <header className="corner">
      <NasaLogo /><span className="brandtxt">Nasa flame smart detection</span>
      <div className="corner-r">{children}
        <button className="ghost" onClick={toggle} aria-label="Switch between light and dark mode">{theme === 'dark' ? '☀ Light' : '☾ Dark'}</button>
      </div>
    </header>
  );
}
export function RoleChips({ value, onChange }) {
  return (
    <div className="seg" role="group" aria-label="Mission profile">
      {Object.entries(ROLES).map(([k, r]) => (
        <button type="button" key={k} className={k === value ? 'on' : ''} aria-pressed={k === value} onClick={() => onChange(k)}>{r.label}</button>
      ))}
    </div>
  );
}
