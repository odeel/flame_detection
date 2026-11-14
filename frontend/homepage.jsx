import { useState } from 'react';
import { ROLES } from './roles.js';
import { Corner } from './components.jsx';
import { api, useApi } from './api.js';
import HabitatGlobe from './HabitatGlobe.jsx';
import InvestigationExplorer from './components/InvestigationExplorer.jsx';
import InvestigationDetail from './components/InvestigationDetail.jsx';
import ComparePanel from './components/ComparePanel.jsx';
import EarthImpact from './components/EarthImpact.jsx';

// Used only when the backend is unreachable, so the UI can still be developed offline. Values from the API doc.
const OFFLINE = [
  { id: 'iss', name: 'International Space Station', body: 'Earth orbit', o2_pct: 21, pressure_kpa: 101.3, gravity_g: 0, status: 'baseline', description: 'Offline placeholder.' },
  { id: 'gateway', name: 'Lunar Gateway', body: 'Lunar orbit', o2_pct: 26.5, pressure_kpa: 70.3, gravity_g: 0, status: 'assumption', description: 'Offline placeholder.' },
  { id: 'moon_base', name: 'Moon base', body: 'Moon', o2_pct: 34, pressure_kpa: 56.5, gravity_g: 0.166, status: 'assumption', description: 'Offline placeholder.' },
  { id: 'mars_base', name: 'Mars surface base', body: 'Mars', o2_pct: 34, pressure_kpa: 56.5, gravity_g: 0.378, status: 'assumption', description: 'Offline placeholder.' },
];
const BASICS = ['Without gravity, hot gas does not rise, so a flame becomes a round, blue ball.', 'The flame gets oxygen only by diffusion, so it burns differently from a candle on Earth.', 'NASA studies prevention, detection and suppression to keep crews safe.'];

export default function HomePage({ user, onLogout, onAsk, onOpenChats, theme, toggle }) {
  const [viewAs, setViewAs] = useState(null);
  const role = viewAs || user.role, cfg = ROLES[role], other = ROLES[user.role].canViewAs;
  const [opt, setOpt] = useState(0), [hid, setHid] = useState('moon_base'), [ask, setAsk] = useState('');
  const [pinned, setPinned] = useState([]), [detail, setDetail] = useState(null);
  const hs = useApi(api.habitats, []), inv = useApi(api.investigations, []);
  const habitats = hs.data || OFFLINE, habitat = habitats.find((h) => h.id === hid) || habitats[0];
  const hab = cfg.habitats ? { id: habitat.id, name: habitat.name } : undefined;
  const go = (t) => onAsk(t, hab);
  const swap = (r) => { setViewAs(r); setOpt(0); setDetail(null); };
  const pin = (id) => setPinned((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id].slice(-3)));
  const tab = cfg.options[opt], n = inv.data?.length ?? '—';
  const kpis = role === 'student' ? [['4', 'Earth technologies'], ['3', 'Safety pillars'], ['0 g', 'Why flames turn round']]
    : role === 'engineer' ? [[habitats.length, 'Habitats'], ['3', 'Safety pillars'], [`${habitat.o2_pct}% O₂`, habitat.name], [`${habitat.pressure_kpa} kPa`, 'Habitat pressure']]
    : [['12 TB', 'Combustion data'], [n, 'Investigations'], ['85%', 'Highest O₂ tested'], ['0', 'Partial-g datasets in PSI']];

  let body;
  if (detail) body = <InvestigationDetail id={detail} onBack={() => setDetail(null)} onAsk={go} />;
  else if (tab === 'Explorer') body = <InvestigationExplorer key={role + habitat.id} habitat={habitat} role={role} pinned={pinned} onPin={pin} onOpen={setDetail} onAsk={go} />;
  else if (tab === 'Compare') body = <ComparePanel ids={pinned} />;
  else if (tab === 'Habitats') body = <HabitatGlobe habitat={habitat} onAsk={go} />;
  else if (tab === 'Earth impact') body = <EarthImpact />;
  else if (tab === 'Fire basics') body = <ul>{BASICS.map((b) => <li key={b}>{b}</li>)}</ul>;
  else if (tab === 'Ask AI') body = <div><p className="mu">Ask a question and get an answer with sources.</p><button className="btn" onClick={onOpenChats}>Open my questions</button></div>;
  else body = <p className="mu">Modeling data: coming soon (predictive features are not connected yet).</p>;

  return (
    <div className="page">
      <Corner theme={theme} toggle={toggle}>
        <span className="mu sm">{cfg.label}</span>
        <button className="link" onClick={onOpenChats}>My questions</button>
        {other && <button className="link" onClick={() => swap(viewAs ? null : other)}>{viewAs ? 'Back to my view' : `View as ${ROLES[other].label}`}</button>}
        <button className="link" onClick={onLogout}>Log out</button>
      </Corner>
      <main className="home">
        {hs.error && cfg.habitats && <p className="err" role="alert">{hs.error} Showing built-in habitats.</p>}
        <h1 className="hero">{cfg.headline[0]} <em>{cfg.headline[1]}</em></h1>
        <form className="askbar" onSubmit={(e) => { e.preventDefault(); if (ask.trim()) go(ask.trim()); }}>
          <input value={ask} onChange={(e) => setAsk(e.target.value)} placeholder={cfg.search} aria-label="Ask a question" />
          <button className="btn amber" type="submit">{role === 'student' ? 'Ask' : 'Analyze'}</button>
        </form>
        <div className="queries"><span className="mu sm">Try a mission query:</span>{cfg.queries.map((x) => <button key={x} className="chip" onClick={() => go(x)}>{x}</button>)}</div>
        <div className="grid">
          <section className="card dash" aria-label={cfg.title}>
            <h2>{cfg.title}</h2>
            <div className="tabs" role="tablist">{cfg.options.map((o, i) => <button key={o} role="tab" aria-selected={i === opt} className={i === opt ? 'on' : ''} onClick={() => { setOpt(i); setDetail(null); }}>{o}</button>)}</div>
            {cfg.habitats && <div className="chips">{habitats.map((h) => <button key={h.id} className={'chip' + (h.id === habitat.id ? ' on' : '')} aria-pressed={h.id === habitat.id} onClick={() => setHid(h.id)}>{h.name}</button>)}</div>}
            {body}
          </section>
          <aside className="kpis" aria-label="Key numbers">{kpis.map(([v, l], i) => <div key={l + i} className={'card kpi' + (role === 'researcher' && i === 3 ? ' warn' : '')}><b>{v}</b><span>{l}</span></div>)}</aside>
        </div>
      </main>
    </div>
  );
}
