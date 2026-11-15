import { local, useApi } from '../api.js';
import { Async, Card, Skeleton } from '../ui.jsx';

const COL = { Incident: 'var(--danger)', Investigation: 'var(--text-subtle)', Detection: 'var(--primary)', 'Firefighter equipment': 'var(--accent)' };

export default function Lessons() {
  const h = useApi(() => local('history'), []);
  const cats = [...new Set((h.data || []).map((e) => e.category))];
  return (
    <Card span={12} actions={<div className="legend">{cats.map((c) => <span key={c} className="legend-sw"><i style={{ background: COL[c] || 'var(--primary)', borderRadius: '50%' }} />{c}</span>)}</div>}
      title="From Apollo 1 to today" icon="history" sub="Every NASA fire rule has a story. Scroll the timeline.">
      <Async state={h} skeleton={<Skeleton lines={3} />}>
        {(data) => (
          <div className="timeline" role="list">{data.map((e) => (
            <div className="ev" role="listitem" key={e.date + e.event}>
              <i style={{ background: COL[e.category] || 'var(--primary)' }} />
              <b>{e.year}</b><p className="text-sm">{e.event}</p>
              {e.key_number && <p className="text-sm"><b>{e.key_number}</b></p>}
              <p className="subtle text-xs">{e.category} · {e.source}</p>
            </div>))}
          </div>
        )}
      </Async>
    </Card>
  );
}
