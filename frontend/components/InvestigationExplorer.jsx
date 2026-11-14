import { useEffect, useMemo, useState } from 'react';
import { api, useApi } from '../api.js';

const CRIT = [['flammability', 'Flammability'], ['detection', 'Detection'], ['suppression', 'Suppression'], ['physics', 'Physics'], ['closeness', 'Closeness to habitat']];
const DEF = { researcher: { flammability: 2, detection: 2, suppression: 2, physics: 3, closeness: 3 }, engineer: { flammability: 3, detection: 3, suppression: 3, physics: 1, closeness: 3 } };
const LVL = { 1: 'Low', 2: 'Medium', 3: 'High' };

export default function InvestigationExplorer({ habitat, role, pinned, onPin, onOpen, onAsk }) {
  const [draft, setDraft] = useState(DEF[role] || DEF.researcher);
  const [pr, setPr] = useState(draft);
  useEffect(() => { const t = setTimeout(() => setPr(draft), 400); return () => clearTimeout(t); }, [draft]);
  const [q, setQ] = useState(''); const [plat, setPlat] = useState('All'); const [open, setOpen] = useState(null);
  const rank = useApi(() => api.rank({ habitat_id: habitat.id, priorities: pr, top: 24 }), [habitat.id, pr]);
  const list = useApi(api.investigations, []);
  const meta = useMemo(() => Object.fromEntries((list.data || []).map((i) => [i.id, i])), [list.data]);
  const all = rank.data?.results || [];
  const plats = [...new Set(all.map((r) => r.platform))];
  const rows = all.filter((r) => (plat === 'All' || r.platform === plat) && `${r.acronym} ${r.name} ${meta[r.id]?.one_sentence_pitch || ''} ${(meta[r.id]?.tags || []).join(' ')}`.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="explorer">
      <p className="mu sm">Ranked for <b>{habitat.name}</b> ({habitat.o2_pct}% O₂, {habitat.pressure_kpa} kPa, {habitat.gravity_g} g). {habitat.status === 'assumption' && 'This habitat atmosphere is an assumption.'}</p>
      <details className="prio"><summary>What matters most to you?</summary>
        <div className="prio-grid">{CRIT.map(([k, l]) => (
          <label key={k}>{l}<select value={draft[k]} onChange={(e) => setDraft({ ...draft, [k]: +e.target.value })}>{[1, 2, 3].map((n) => <option key={n} value={n}>{LVL[n]}</option>)}</select></label>))}</div>
      </details>
      <div className="filters">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter by name, topic or tag…" aria-label="Filter investigations" />
        <select value={plat} onChange={(e) => setPlat(e.target.value)} aria-label="Platform"><option>All</option>{plats.map((p) => <option key={p}>{p}</option>)}</select>
      </div>
      {rank.loading && <p className="mu">Ranking investigations…</p>}
      {rank.error && <p className="err" role="alert">{rank.error}</p>}
      {!rank.loading && !rows.length && !rank.error && <p className="mu">No investigations match.</p>}
      {rows.map((r) => {
        const m = meta[r.id] || {}, on = open === r.id;
        return (
          <article className="inv" key={r.id}>
            <button className="inv-head" aria-expanded={on} onClick={() => setOpen(on ? null : r.id)}>
              <span className="rk">#{r.rank}</span>
              <span className="inv-name"><b>{r.acronym}</b><span className="mu sm">{r.name}</span><span className="mu sm">{r.platform}{m.years ? ` · ${m.years[0]}–${m.years[1]}` : ''}</span></span>
              <span className="score" aria-label={`Score ${Math.round(r.score * 100)} out of 100`}>{Math.round(r.score * 100)}</span>
            </button>
            {on && (
              <div className="inv-body">
                {m.one_sentence_pitch && <p>{m.one_sentence_pitch}</p>}
                <div className="crit">{CRIT.map(([k, l]) => { const c = r.criteria[k]; return (
                  <div key={k} title={c.reason}><span className="mu sm">{l}</span><i><u style={{ width: `${c.score * 100}%` }} /></i><span className="sm">{Math.round(c.score * 100)}</span></div>); })}</div>
                {r.criteria.closeness?.reason && <p className="mu sm">{r.criteria.closeness.reason}</p>}
                <div className="actions">
                  <button className="btn" onClick={() => onOpen(r.id)}>Details</button>
                  <label className="sm"><input type="checkbox" checked={pinned.includes(r.id)} onChange={() => onPin(r.id)} /> Compare</label>
                  <button className="link" onClick={() => onAsk(`What did ${r.acronym} find that matters for fire safety?`)}>Ask about this</button>
                  <a href={r.url} target="_blank" rel="noreferrer">PSI record</a>
                </div>
              </div>)}
          </article>);
      })}
    </div>
  );
}
