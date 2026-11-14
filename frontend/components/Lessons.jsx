import { local, useApi } from '../api.js';
const COL = { Incident: 'var(--err)', Investigation: 'var(--mu)', Detection: 'var(--pr)', 'Firefighter equipment': 'var(--acc)' };
export default function Lessons() {
  const h = useApi(() => local('history'), []);
  return (
    <section className="card"><h2>Historical space lessons</h2>
      <div className="timeline" role="list">{(h.data || []).map((e) => (
        <div className="ev" role="listitem" key={e.date + e.event}><i style={{ background: COL[e.category] || 'var(--pr)' }} /><b>{e.year}</b><p className="sm">{e.event}</p>
          {e.key_number && <p className="sm"><b>{e.key_number}</b></p>}<p className="mu sm">{e.category} · {e.source}</p></div>))}</div></section>
  );
}
