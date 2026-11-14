const PILL = [['flammability', 'Prevention'], ['detection', 'Detection'], ['suppression', 'Suppression']];
const CRIT = [['flammability', 'Flammability'], ['detection', 'Detection'], ['suppression', 'Suppression'], ['physics', 'Physics'], ['closeness', 'Closeness to habitat']];
const rg = (a, u = '') => (a ? (a[0] === a[1] ? `${a[0]}${u}` : `${a[0]}–${a[1]}${u}`) : '—');

export function Gauge({ value, label = 'Relevance' }) {
  const r = 26, c = 2 * Math.PI * r, col = value >= 75 ? 'var(--pr)' : value >= 50 ? 'var(--acc)' : 'var(--mu)';
  return (
    <div className="gauge" role="img" aria-label={`${label} ${value} out of 100`}>
      <svg viewBox="0 0 64 64" width="68" height="68"><circle cx="32" cy="32" r={r} className="g-bg" /><circle cx="32" cy="32" r={r} className="g-fg" stroke={col} strokeDasharray={`${(value / 100) * c} ${c}`} transform="rotate(-90 32 32)" /><text x="32" y="38" textAnchor="middle">{value}</text></svg>
      <span>{label}</span>
    </div>
  );
}

// One investigation in the "mission control" style: thumbnail, tags, ranges, relevance gauge, summary.
export default function InvestigationCard({ inv, r, cov, pinned, onPin, onOpen, onAsk }) {
  const fuel = cov?.fuels?.[0] || 'Gas', pills = r ? PILL.filter(([k]) => r.criteria[k].score >= 0.5) : [];
  return (
    <article className="invc">
      <div className={'thumb ' + fuel.toLowerCase()} aria-hidden>{r && <span className="rkb">#{r.rank}</span>}</div>
      <div className="invc-main">
        <h3>{inv.acronym}</h3><p className="mu sm">{inv.name}</p>
        <div>{[inv.platform?.replace(/\s*\(.*\)/, ''), ...(cov?.fuels || []), 'µg', ...pills.map((p) => p[1])].filter(Boolean).map((t) => <span className="tag" key={t}>{t}</span>)}</div>
      </div>
      <div className="stat"><span>O₂ range</span><b>{rg(cov?.o2, '%')}</b><i className="bar"><u style={{ left: `${cov?.o2?.[0] ?? 0}%`, width: `${cov?.o2 ? Math.max(2, cov.o2[1] - cov.o2[0]) : 0}%` }} /></i></div>
      <div className="stat"><span>Pressure</span><b>{rg(cov?.p, ' kPa')}</b><span className="mu">{cov ? `${cov.n} test rows` : ''}</span></div>
      {r ? <Gauge value={Math.round(r.score * 100)} /> : <span />}
      <div className="invc-side">
        <p>{inv.one_sentence_pitch}</p>
        <div className="actions"><button className="link" onClick={() => onOpen(inv.id)}>View details →</button>
          {onPin && <label className="sm"><input type="checkbox" checked={pinned} onChange={() => onPin(inv.id)} /> Compare</label>}
          {onAsk && <button className="link" onClick={() => onAsk(`What did ${inv.acronym} find that matters for fire safety?`)}>Ask</button>}</div>
      </div>
      {r && <details className="why"><summary>Why this rank</summary>
        <div className="crit">{CRIT.map(([k, l]) => <div key={k}><span className="mu sm">{l}</span><i><u style={{ width: `${r.criteria[k].score * 100}%` }} /></i><span className="sm">{Math.round(r.criteria[k].score * 100)}</span><p className="mu sm">{r.criteria[k].reason}</p></div>)}</div></details>}
    </article>
  );
}
