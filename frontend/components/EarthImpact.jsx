import { local, useApi } from '../api.js';
export default function EarthImpact() {
  const e = useApi(() => local('earth-impact'), []);
  const a = useApi(() => local('acme'), []);
  if (e.loading) return <p className="mu">Loading…</p>;
  if (e.error) return <p className="err">{e.error}</p>;
  return (
    <div className="col">
      <h2>Why flames matter on Earth</h2>
      <div className="grid4">{e.data.combustion.map((m) => <div className="card" key={m.text}><b className="big">{m.value}{m.unit}</b><p className="sm">{m.text}</p><p className="mu sm">{m.note} · {m.source}</p></div>)}</div>
      <h2>Space research that protects people</h2>
      <div className="grid4">{e.data.spinoffs.map((s) => (
        <div className="card" key={s.tech}><h3>{s.tech}</h3><p className="mu sm">{s.year}</p>
          {s.items.map((i) => <p className="sm" key={i.metric}>{i.metric}: <b>{i.value} {i.unit}</b>{i.derived && <span className="mu"> (calculated)</span>}</p>)}
          <p className="mu sm">{s.source}</p></div>))}</div>
      <h2>Cleaner, more efficient combustion</h2>
      <div className="grid4">{(a.data || []).map((x) => <div className="card" key={x.key}><h3>{x.name}</h3><p className="sm">{x.studies}</p><p className="mu sm">{x.link}</p></div>)}</div>
    </div>
  );
}
