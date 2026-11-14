import { useState } from 'react';
import { ROLES } from './roles.js';
import { Corner } from './components.jsx';
import HabitatGlobe from './HabitatGlobe.jsx';

const HABITATS = ['Spacecraft / ISS', 'Lunar base / rover', 'EVA spacesuit'];

export default function HomePage({ user, onLogout, onAsk, onOpenChats, theme, toggle }) {
  const [viewAs, setViewAs] = useState(null);          // researcher <-> engineer
  const role = viewAs || user.role;
  const cfg = ROLES[role];
  const other = ROLES[user.role].canViewAs;
  const [opt, setOpt] = useState(0);
  const [hab, setHab] = useState(1);
  const [ask, setAsk] = useState('');
  const [q, setQ] = useState('');
  const swap = (r) => { setViewAs(r); setOpt(0); };
  const habitat = HABITATS[hab];
  const submit = (e) => { e.preventDefault(); if (ask.trim()) onAsk(ask.trim(), cfg.habitats ? habitat : undefined); };
  const globe = cfg.habitats && opt === 0 && hab < 2;

  return (
    <div className="page">
      <Corner theme={theme} toggle={toggle}>
        <span className="mu sm">{cfg.label}</span>
        <button className="link" onClick={onOpenChats}>My questions</button>
        {other && <button className="link" onClick={() => swap(viewAs ? null : other)}>{viewAs ? 'Back to my view' : `View as ${ROLES[other].label}`}</button>}
        <button className="link" onClick={onLogout}>Log out</button>
      </Corner>
      <main className="home">
        <h1 className="hero">{cfg.headline[0]} <em>{cfg.headline[1]}</em></h1>
        <form className="askbar" onSubmit={submit}>
          <input value={ask} onChange={(e) => setAsk(e.target.value)} placeholder={cfg.search} aria-label="Search or ask" />
          <button className="btn amber" type="submit">{role === 'student' ? 'Ask' : 'Analyze'}</button>
        </form>
        <div className="queries"><span className="mu sm">Try a mission query:</span>
          {cfg.queries.map((x) => <button key={x} className="chip" onClick={() => onAsk(x, cfg.habitats ? habitat : undefined)}>{x}</button>)}
        </div>
        <div className="grid">
          <section className="card dash" aria-label={cfg.title}>
            <h2>{cfg.title}</h2>
            <div className="tabs" role="tablist">
              {cfg.options.map((o, i) => <button key={o} role="tab" aria-selected={i === opt} className={i === opt ? 'on' : ''} onClick={() => setOpt(i)}>{o}</button>)}
            </div>
            {cfg.habitats && <div className="chips">{HABITATS.map((h, i) => <button key={h} className={'chip' + (i === hab ? ' on' : '')} aria-pressed={i === hab} onClick={() => setHab(i)}>{h}</button>)}</div>}
            <input className="field" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…" aria-label="Filter this dashboard" />
            {globe ? <HabitatGlobe habitat={habitat} onAsk={(t) => onAsk(t, habitat)} />
              : <div className="placeholder mu">{cfg.options[opt]} content goes here{cfg.habitats ? ` · ${habitat}` : ''}</div>}
          </section>
          <aside className="kpis" aria-label="Key numbers">
            {cfg.kpis.map(([v, l], i) => <div key={l} className={'card kpi' + (role === 'researcher' && i === 3 ? ' warn' : '')}><b>{v}</b><span>{l}</span></div>)}
          </aside>
        </div>
      </main>
    </div>
  );
}
