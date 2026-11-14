import { useMemo, useState } from 'react';
import { api, useApi } from '../api.js';
import InvestigationCard from './InvestigationCard.jsx';

const CRIT = [['flammability', 'Flammability'], ['detection', 'Detection'], ['suppression', 'Suppression'], ['physics', 'Physics'], ['closeness', 'Closeness to habitat']];
const LVL = { 1: 'Low', 2: 'Medium', 3: 'High' };
const O2B = { 'Air (<22%)': [0, 22], '22–30%': [22, 30], '30–50%': [30, 50], '50%+': [50, 101] };

export default function InvestigationExplorer({ habitat, rank, invs, cov, draft, setDraft, pinned, onPin, onOpen, onAsk }) {
  const [q, setQ] = useState(''), [plat, setPlat] = useState('All'), [fuel, setFuel] = useState('All'), [o2, setO2] = useState('All'), [safe, setSafe] = useState('All');
  const meta = useMemo(() => Object.fromEntries((invs || []).map((i) => [i.id, i])), [invs]);
  const all = rank.data?.results || [], map = cov.map || {};
  const plats = [...new Set(all.map((r) => r.platform))];
  const fuels = [...new Set(Object.values(map).flatMap((m) => m.fuels))];
  const rows = all.filter((r) => {
    const m = meta[r.id] || {}, c = map[r.id];
    if (plat !== 'All' && r.platform !== plat) return false;
    if (fuel !== 'All' && !c?.fuels.includes(fuel)) return false;
    if (o2 !== 'All') { const [a, b] = O2B[o2]; if (!c?.o2 || c.o2[1] < a || c.o2[0] >= b) return false; }
    if (safe !== 'All' && r.criteria[safe].score < 0.5) return false;
    return `${r.acronym} ${r.name} ${m.one_sentence_pitch || ''} ${(m.tags || []).join(' ')}`.toLowerCase().includes(q.toLowerCase());
  });
  return (
    <div className="explorer">
      <div className="tabs" role="tablist" aria-label="Platform">{['All', ...plats].map((p) => <button key={p} role="tab" aria-selected={plat === p} className={plat === p ? 'on' : ''} onClick={() => setPlat(p)}>{p.replace(/\s*\(.*\)/, '')}</button>)}</div>
      <div className="filters">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search investigations…" aria-label="Search investigations" />
        <select value={fuel} onChange={(e) => setFuel(e.target.value)} aria-label="Fuel"><option value="All">Fuel</option>{fuels.map((f) => <option key={f}>{f}</option>)}</select>
        <select value={o2} onChange={(e) => setO2(e.target.value)} aria-label="O₂ range"><option value="All">O₂ range</option>{Object.keys(O2B).map((f) => <option key={f}>{f}</option>)}</select>
        <select value={safe} onChange={(e) => setSafe(e.target.value)} aria-label="Safety focus"><option value="All">Safety</option><option value="flammability">Prevention</option><option value="detection">Detection</option><option value="suppression">Suppression</option></select>
      </div>
      <details className="prio"><summary>What matters most to you? (changes the ranking)</summary>
        <div className="prio-grid">{CRIT.map(([k, l]) => <label key={k}>{l}<select value={draft[k]} onChange={(e) => setDraft({ ...draft, [k]: +e.target.value })}>{[1, 2, 3].map((n) => <option key={n} value={n}>{LVL[n]}</option>)}</select></label>)}</div></details>
      <p className="mu sm">Ranked for <b>{habitat.name}</b> ({habitat.o2_pct}% O₂, {habitat.pressure_kpa} kPa, {habitat.gravity_g} g){habitat.status === 'assumption' ? ' · atmosphere is an assumption' : ''} · {rows.length} of {all.length} shown</p>
      {rank.loading && <p className="mu">Ranking investigations… <span className="sm">(first load can take a moment)</span></p>}
      {rank.error && <div className="err" role="alert"><p>Ranking failed: {rank.error}</p><p className="sm">Open the browser console (F12) and check the /rank request. Send the error to the backend team.</p></div>}
      {!rank.loading && !rank.error && !rows.length && <p className="mu">No investigations match these filters.</p>}
      {rows.map((r) => <InvestigationCard key={r.id} inv={meta[r.id] || { id: r.id, acronym: r.acronym, name: r.name, platform: r.platform }} r={r} cov={map[r.id]} pinned={pinned.includes(r.id)} onPin={onPin} onOpen={onOpen} onAsk={onAsk} />)}
    </div>
  );
}
