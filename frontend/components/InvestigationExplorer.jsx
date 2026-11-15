import { useMemo, useState } from 'react';
import { Badge, EmptyState, ErrorState, Skeleton, Slider, Tabs } from '../ui.jsx';
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
  const filtered = q || plat !== 'All' || fuel !== 'All' || o2 !== 'All' || safe !== 'All';
  const clear = () => { setQ(''); setPlat('All'); setFuel('All'); setO2('All'); setSafe('All'); };
  return (
    <div className="explorer">
      {plats.length > 0 && <Tabs label="Platform" value={plat} onChange={setPlat} items={['All', ...plats].map((p) => ({ id: p, label: p.replace(/\s*\(.*\)/, '') }))} />}
      <div className="filters">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search investigations…" aria-label="Search investigations" />
        <select value={fuel} onChange={(e) => setFuel(e.target.value)} aria-label="Fuel"><option value="All">Any fuel</option>{fuels.map((f) => <option key={f}>{f}</option>)}</select>
        <select value={o2} onChange={(e) => setO2(e.target.value)} aria-label="O₂ range"><option value="All">Any O₂ range</option>{Object.keys(O2B).map((f) => <option key={f}>{f}</option>)}</select>
        <select value={safe} onChange={(e) => setSafe(e.target.value)} aria-label="Safety focus"><option value="All">Any safety focus</option><option value="flammability">Prevention</option><option value="detection">Detection</option><option value="suppression">Suppression</option></select>
      </div>
      <details className="prio"><summary>What matters most to you? (changes the ranking)</summary>
        <div className="prio-grid">{CRIT.map(([k, l]) => <Slider key={k} label={l} value={draft[k]} min={1} max={3} step={1} format={(v) => LVL[v]} onChange={(v) => setDraft({ ...draft, [k]: v })} />)}</div>
        {rank.data?.ahp && !rank.data.ahp.consistent && <p className="field-err">These priorities contradict each other (AHP consistency ratio {rank.data.ahp.cr}).</p>}
      </details>
      <div className="meta-line">
        <span>Ranked for <b>{habitat.name}</b></span>
        <Badge plain>{habitat.o2_pct}% O₂ · {habitat.pressure_kpa} kPa · {habitat.gravity_g} g</Badge>
        {habitat.status === 'assumption' && <Badge tone="warning">assumed atmosphere</Badge>}
        <span className="grow" />
        <span className="num">{rows.length} of {all.length} shown</span>
        {filtered && <button type="button" className="link text-sm" onClick={clear}>Clear filters</button>}
      </div>
      {rank.loading && !rank.data && <Skeleton lines={6} />}
      {rank.error && <ErrorState message={`Ranking failed: ${rank.error}`} onRetry={rank.reload} />}
      {rank.data && !rows.length && <EmptyState title="No investigations match these filters" hint="Try a wider O₂ range or another platform." action={<button type="button" className="btn-quiet btn-sm" onClick={clear}>Clear filters</button>} />}
      <div className="invlist">
        {rows.map((r) => <InvestigationCard key={r.id} inv={meta[r.id] || { id: r.id, acronym: r.acronym, name: r.name, platform: r.platform }} r={r} cov={map[r.id]} pinned={pinned.includes(r.id)} onPin={onPin} onOpen={onOpen} onAsk={onAsk} />)}
      </div>
    </div>
  );
}
