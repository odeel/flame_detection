const P = [['flammability', 'Prevention', 'Material selection and flammability limits'], ['detection', 'Detection', 'Smoke and particle sensing'], ['suppression', 'Suppression', 'Extinguishing agents and dilution']];
export default function FireControls({ rank, onOpen }) {
  const res = rank.data?.results || [];
  return (
    <section className="card"><h2>Fire controls</h2><p className="mu sm">Investigations that score 50% or higher on each safety pillar for the selected habitat.</p>
      {rank.loading && <p className="mu">Loading…</p>}
      <div className="tiles">{P.map(([k, l, d]) => { const hit = res.filter((r) => r.criteria[k].score >= 0.5).sort((a, b) => b.criteria[k].score - a.criteria[k].score);
        return <div className="tile" key={k}><h3>{l}</h3><p className="mu sm">{d}</p><b className="big">{rank.data ? hit.length : '—'}</b><span className="mu sm"> studies</span>
          <div>{hit.slice(0, 3).map((r) => <button key={r.id} className="chip" onClick={() => onOpen(r.id)}>{r.acronym}</button>)}</div></div>; })}</div></section>
  );
}
