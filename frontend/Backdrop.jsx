import { useMemo } from 'react';

function Satellite() {
  return (
    <div className="sat" aria-hidden>
      <svg viewBox="0 0 220 120" width="220" height="120">
        <defs><linearGradient id="pn" x1="0" x2="1"><stop offset="0" stopColor="#3b82f6" /><stop offset="1" stopColor="#7c3aed" /></linearGradient></defs>
        <g stroke="#cfe0ff" strokeWidth="1" opacity=".9">
          <rect x="4" y="38" width="70" height="44" rx="3" fill="url(#pn)" /><rect x="146" y="38" width="70" height="44" rx="3" fill="url(#pn)" />
          {[18, 32, 46, 60].map((x) => <line key={x} x1={x} y1="38" x2={x} y2="82" />)}{[160, 174, 188, 202].map((x) => <line key={x} x1={x} y1="38" x2={x} y2="82" />)}
          <line x1="4" y1="60" x2="74" y2="60" /><line x1="146" y1="60" x2="216" y2="60" />
        </g>
        <rect x="74" y="50" width="72" height="20" rx="4" fill="#e5ecff" stroke="#94a3b8" /><rect x="96" y="44" width="28" height="32" rx="5" fill="#fff" stroke="#94a3b8" />
        <path d="M110 44 L110 24" stroke="#cbd5e1" strokeWidth="2" /><path d="M96 24 Q110 12 124 24 Q110 30 96 24Z" fill="#f1f5f9" stroke="#94a3b8" />
        <circle cx="110" cy="60" r="4" fill="#FF9100" />
      </svg>
    </div>
  );
}

// Starfield + blurred nebula glows (+ optional floating satellite). Colors come from CSS variables, so it works in dark and light mode.
export default function Backdrop({ satellite = false }) {
  const stars = useMemo(() => [60, 35, 18].map((n) => Array.from({ length: n }, () => `${(Math.random() * 100).toFixed(1)}vw ${(Math.random() * 100).toFixed(1)}vh 0 0 var(--star)`).join(',')), []);
  return (
    <div className="bg" aria-hidden>
      <div className="bg-grid" /><div className="nebula n1" /><div className="nebula n2" /><div className="nebula n3" /><div className="horizon" />
      {stars.map((s, i) => <i key={i} className={'stars s' + i} style={{ boxShadow: s }} />)}
      {satellite && <><svg className="orbit" viewBox="0 0 600 300" preserveAspectRatio="none"><path d="M0 260 Q300 -60 600 200" fill="none" stroke="var(--line)" strokeDasharray="4 8" /></svg><Satellite /></>}
    </div>
  );
}
