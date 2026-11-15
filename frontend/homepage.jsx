import { Fragment, useEffect, useState } from 'react';
import { ROLES } from './roles.js';
import { Corner } from './components.jsx';
import { api, useApi } from './api.js';
import { Badge, Icon, KpiTile, Note } from './ui.jsx';
import { useCoverage } from './components/Coverage.jsx';
import { useSimulator } from './simulator/useSimulator.js';
import { PANELS } from './sections.jsx';

// Used only when the backend is unreachable. Values from the API doc.
const OFFLINE = [
  { id: 'iss', name: 'International Space Station', body: 'Earth orbit', o2_pct: 21, pressure_kpa: 101.3, gravity_g: 0, status: 'baseline', description: 'Offline placeholder.' },
  { id: 'gateway', name: 'Lunar Gateway', body: 'Lunar orbit', o2_pct: 26.5, pressure_kpa: 70.3, gravity_g: 0, status: 'assumption', description: 'Offline placeholder.' },
  { id: 'moon_base', name: 'Moon base', body: 'Moon', o2_pct: 34, pressure_kpa: 56.5, gravity_g: 0.166, status: 'assumption', description: 'Offline placeholder.' },
  { id: 'mars_base', name: 'Mars surface base', body: 'Mars', o2_pct: 34, pressure_kpa: 56.5, gravity_g: 0.378, status: 'assumption', description: 'Offline placeholder.' },
];
const DEF = { researcher: { flammability: 2, detection: 2, suppression: 2, physics: 3, closeness: 3 }, engineer: { flammability: 3, detection: 3, suppression: 3, physics: 1, closeness: 3 } };

export default function HomePage({ user, onLogout, onAsk, onOpenChats, onHome, theme, toggle }) {
  const [viewAs, setViewAs] = useState(null);
  const role = viewAs || user.role, cfg = ROLES[role], other = ROLES[user.role].canViewAs, student = role === 'student';
  const [hid, setHid] = useState('moon_base'), [ask, setAsk] = useState('');
  const [pinned, setPinned] = useState([]), [detail, setDetail] = useState(null), [lib, setLib] = useState(cfg.library[0]);
  const hs = useApi(api.habitats, []), inv = useApi(() => (student ? Promise.resolve(null) : api.investigations()), [student]);
  const habitats = hs.data || OFFLINE, habitat = habitats.find((h) => h.id === hid) || habitats[0];
  const iss = habitats.find((h) => h.id === 'iss') || OFFLINE[0];

  // Ranking priorities: sliders update `draft`; the request fires 400 ms after the last change.
  const [draft, setDraft] = useState(DEF[role] || DEF.researcher), [pr, setPr] = useState(draft);
  useEffect(() => { const d = DEF[role] || DEF.researcher; setDraft(d); setPr(d); setLib(cfg.library[0]); setDetail(null); }, [role]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { const t = setTimeout(() => setPr(draft), 400); return () => clearTimeout(t); }, [draft]);
  const rank = useApi(() => (student ? Promise.resolve(null) : api.rank({ habitat_id: habitat.id, priorities: pr, orness: 0.5, top: 24 })), [habitat.id, pr, student]);
  const cov = useCoverage(student ? null : inv.data);
  const sim = useSimulator(habitat, !student);

  const hab = cfg.habitats ? { id: habitat.id, name: habitat.name } : undefined, go = (t) => onAsk(t, hab);
  const pin = (id) => setPinned((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id].slice(-3)));
  const openStudy = (id) => { setLib('Explorer'); setDetail(id); document.getElementById('library')?.scrollIntoView({ behavior: 'smooth' }); };

  const maxO2 = cov.map ? Math.max(0, ...Object.values(cov.map).map((m) => m.o2?.[1] ?? 0)) : 0;
  const worst = sim.map.data?.summary?.find((s) => s.id === habitat.id) || sim.map.data?.summary?.[0];
  const kpis = {
    student: [
      ['flame', '85 %', 'of the energy we use comes from combustion', 'phys.org, 2018', 'accent'],
      ['rocket', '3', 'NASA fire-safety technologies firefighters use', 'NASA Spinoff'],
      ['globe', '0 g', 'is why flames turn into round, blue balls', 'no buoyancy in orbit'],
      ['history', '1967', 'Apollo 1: why fire safety matters in space', 'sma.nasa.gov'],
    ],
    researcher: [
      ['book', inv.data?.length ?? '—', 'PSI investigations indexed', 'NASA Physical Sciences Informatics'],
      ['layers', cov.rows ? cov.rows.toLocaleString() : '—', 'experiment rows extracted', 'tables, reports and test sheets'],
      ['flame', maxO2 ? `${maxO2} %` : '—', 'highest O₂ tested', 'across all investigations', 'accent'],
      ['alert', '0', 'partial-gravity datasets in PSI', 'Moon/Mars risk is extrapolated', 'warning'],
    ],
    engineer: [
      ['target', `${habitat.o2_pct} %`, `cabin O₂ · ${habitat.name}`, habitat.status === 'assumption' ? 'assumed atmosphere' : 'baseline'],
      ['gauge', `${habitat.pressure_kpa} kPa`, 'cabin pressure', habitat.o2_partial_kpa ? `O₂ partial pressure ${habitat.o2_partial_kpa} kPa` : null],
      ['globe', `${habitat.gravity_g} g`, 'gravity', habitat.gravity_g > 0 ? 'not modelled: tests ran in µg' : 'microgravity'],
      ['flame', worst ? `${Math.round(worst.fuel_burned.mean * 100)} %` : '—', 'worst-case droplet burn', worst ? `${worst.fuel} at habitat air` : 'from the flame model', worst?.fuel_burned.mean >= 0.9 ? 'danger' : 'accent'],
    ],
  }[role];

  const ctx = { cfg, role, habitat, habitats, iss, sim, rank, inv, cov, draft, setDraft, pinned, pin, detail, setDetail, lib, setLib, go, openStudy, onOpenChats };

  return (
    <div className="page">
      <Corner theme={theme} toggle={toggle} onHome={onHome}>
        <Badge tone="primary"><Icon name={ROLES[user.role].icon} /> {ROLES[user.role].label}</Badge>
        <button type="button" className="navbtn" onClick={onOpenChats}><Icon name="chat" /> My questions</button>
        {other && <button type="button" className="navbtn" onClick={() => setViewAs(viewAs ? null : other)}><Icon name="eye" />{viewAs ? 'Back to my view' : `View as ${ROLES[other].label}`}</button>}
        <button type="button" className="navbtn" onClick={onLogout}><Icon name="logout" /> Log out</button>
      </Corner>
      <main className="container home">
        <div className="stack-lg">
          <header className="hero-wrap fade-in">
            <div className="cluster">
              <p className="eyebrow">FlameX · {cfg.workspace}</p>
              {viewAs && <Badge tone="warning">Previewing the {cfg.label.toLowerCase()} view</Badge>}
            </div>
            <h1 className="hero">{cfg.headline[0]} <em>{cfg.headline[1]}</em></h1>
            <p className="hero-lead">{cfg.lead}</p>
            <form className="askbar" onSubmit={(e) => { e.preventDefault(); if (ask.trim()) go(ask.trim()); }} role="search">
              <input value={ask} onChange={(e) => setAsk(e.target.value)} placeholder={cfg.search} aria-label="Ask a question" />
              <button className="cta" type="submit"><Icon name="sparkle" /> {student ? 'Ask' : 'Analyze'}</button>
            </form>
            <div className="queries"><span className="subtle text-sm">Try:</span>{cfg.queries.map((x) => <button type="button" key={x} className="chip" onClick={() => go(x)}>{x}</button>)}</div>
          </header>

          {cfg.habitats && (
            <div className="stack-sm">
              <div className="row between"><span className="eyebrow">Mission habitat</span>{hs.error && <span className="text-xs tone-warning">Backend offline: built-in habitats</span>}</div>
              <div className="habbar" role="group" aria-label="Habitat">
                {habitats.map((h) => (
                  <button type="button" key={h.id} className={'hpill' + (h.id === habitat.id ? ' on' : '')} aria-pressed={h.id === habitat.id} onClick={() => setHid(h.id)}>
                    <span className={`orb ${h.id}`} /><b>{h.name}</b><span>{h.o2_pct}% O₂ · {h.pressure_kpa} kPa · {h.gravity_g} g</span>
                  </button>))}
              </div>
              {habitat.status === 'assumption' && habitat.note && <Note tone="info">{habitat.note}</Note>}
            </div>
          )}

          <div className="kpis">{kpis.map(([icon, v, l, n, tone]) => <KpiTile key={l} icon={icon} value={v} label={l} note={n} tone={tone} />)}</div>
        </div>

        {cfg.sections.map((id) => <Fragment key={id}>{PANELS[id]?.(ctx)}</Fragment>)}
      </main>
    </div>
  );
}
