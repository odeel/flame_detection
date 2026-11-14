import { local, useApi } from '../api.js';
export default function GravityPanel() {
  const g = useApi(() => local('gravity'), []);
  if (g.loading) return <p className="mu">Loading…</p>;
  if (g.error) return <p className="err">{g.error}</p>;
  const d = g.data;
  return (
    <div className="col">
      <p className="mu sm">PSI has no partial-gravity data yet. These figures come from NASA publications (NTRS), mainly the LUCI flight and review papers.</p>
      <div className="grid4">{d.bodies.map((b) => <div className="card" key={b.body}><h3>{b.body}</h3><b className="big">{b.g} g</b><p className="mu sm">{b.ms2} m/s² {b.note && `· ${b.note}`}</p><p className="mu sm">{b.source}</p></div>)}</div>
      <h3>Test platforms and durations</h3>
      <div className="tbl"><table><thead><tr><th>Platform</th><th>Duration</th><th>Gravity</th><th>Note</th></tr></thead><tbody>{d.durations.map((r) => <tr key={r.platform}><td>{r.platform}</td><td>{r.seconds ? `${r.seconds} s` : '—'}</td><td>{r.type}</td><td>{r.note} <span className="mu sm">({r.source})</span></td></tr>)}</tbody></table></div>
      <h3>What is known about partial gravity</h3>
      <div className="tbl"><table><thead><tr><th>Topic</th><th>Finding</th><th>Setup</th><th>Quantified</th><th>Caution</th></tr></thead><tbody>{d.findings.map((r) => <tr key={r.finding}><td>{r.topic}</td><td>{r.finding}</td><td>{r.config}</td><td>{r.quantified}</td><td>{r.caution} <span className="mu sm">({r.source})</span></td></tr>)}</tbody></table></div>
    </div>
  );
}
