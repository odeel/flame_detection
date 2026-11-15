import { local, useApi } from '../api.js';
import { Async, Card, Note, Skeleton } from '../ui.jsx';

export default function GravityPanel() {
  const g = useApi(() => local('gravity'), []);
  return (
    <Async state={g} skeleton={<Skeleton lines={6} />}>
      {(d) => (
        <div className="stack-lg">
          <Note tone="info">PSI has no partial-gravity data yet. These figures come from NASA publications (NTRS), mainly the LUCI flight and review papers.</Note>
          <div className="tiles">{d.bodies.map((b) => (
            <Card key={b.body} variant="inset">
              <p className="eyebrow">{b.body}</p>
              <b className="big">{b.g} g</b>
              <p className="muted text-sm">{b.ms2} m/s²{b.note && ` · ${b.note}`}</p>
              <p className="subtle text-xs">{b.source}</p>
            </Card>))}
          </div>
          <h3>Test platforms and durations</h3>
          <div className="tbl"><table><thead><tr><th>Platform</th><th className="num">Duration</th><th>Gravity</th><th>Note</th></tr></thead>
            <tbody>{d.durations.map((r) => <tr key={r.platform}><td>{r.platform}</td><td className="num">{r.seconds ? `${r.seconds} s` : '—'}</td><td>{r.type}</td><td>{r.note} <span className="subtle text-xs">({r.source})</span></td></tr>)}</tbody></table></div>
          <h3>What is known about partial gravity</h3>
          <div className="tbl"><table><thead><tr><th>Topic</th><th>Finding</th><th>Setup</th><th>Quantified</th><th>Caution</th></tr></thead>
            <tbody>{d.findings.map((r) => <tr key={r.finding}><td>{r.topic}</td><td>{r.finding}</td><td>{r.config}</td><td>{r.quantified}</td><td>{r.caution} <span className="subtle text-xs">({r.source})</span></td></tr>)}</tbody></table></div>
        </div>
      )}
    </Async>
  );
}
