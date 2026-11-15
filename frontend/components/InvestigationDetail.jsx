import { api, local, useApi } from '../api.js';
import { Async, Badge, Card, Icon, Skeleton } from '../ui.jsx';
import SourceLink from './SourceViewer.jsx';

const rg = (a, b) => (a == null && b == null ? '—' : a === b || b == null ? `${a}` : `${a}–${b}`);

export default function InvestigationDetail({ id, onBack, onAsk }) {
  const d = useApi(() => api.investigation(id), [id]);
  const acme = useApi(() => local('acme'), []), fin = useApi(() => local('findings'), []);
  return (
    <div className="detail fade-in">
      <button type="button" className="link" onClick={onBack}>← Back to list</button>
      <Async state={d} skeleton={<Skeleton lines={8} />}>
        {(x) => {
          const has = (k) => x.acronym.toLowerCase().includes(k.toLowerCase());
          const extra = acme.data?.find((a) => has(a.key)), finds = (fin.data || []).filter((f) => f.key !== 'General' && has(f.key));
          return (
            <div className="stack-lg">
              <div className="stack-sm">
                <h2>{x.acronym} <span className="muted">· {x.name}</span></h2>
                <div className="cluster"><Badge plain>{x.platform}</Badge>{x.years && <Badge plain>{x.years[0]}–{x.years[1]}</Badge>}{x.tags?.map((t) => <Badge key={t} tone="primary" plain>{t}</Badge>)}
                  <a href={x.url} target="_blank" rel="noreferrer" className="text-sm">NASA PSI record ↗</a></div>
              </div>
              <p className="text-lg" style={{ maxWidth: '75ch' }}>{x.plain_summary}</p>
              {extra && <Card variant="inset"><p className="text-sm"><b>Principal investigators:</b> {extra.pis}</p><p className="text-sm"><b>Stated link to efficiency or pollution:</b> {extra.link} <span className="subtle">({extra.source})</span></p></Card>}
              <div className="bento">
                <Card span={6} variant="inset" title="Objectives" icon="target"><ul>{x.objectives?.map((o) => <li key={o}>{o}</li>)}</ul></Card>
                <Card span={6} variant="inset" title="Main findings" icon="sparkle"><ul>{x.main_findings?.map((o) => <li key={o}>{o}</li>)}</ul></Card>
              </div>
              {finds.length > 0 && <><h3>Reported in NASA publications</h3><ul>{finds.map((f) => <li key={f.finding}>{f.finding} <span className="subtle text-sm">({f.quantified.startsWith('Yes') ? 'quantified' : 'not quantified'} · {f.source})</span></li>)}</ul></>}
              {x.safety_relevance && <Card variant="accent" title="Safety relevance" icon="shield"><p>{x.safety_relevance}</p></Card>}
              <h3>Test conditions <span className="muted">({x.n_experiments} rows)</span></h3>
              <div className="tbl" style={{ maxHeight: 420 }}><table><thead><tr><th>Fuel</th><th>Type</th><th className="num">O₂ %</th><th className="num">Pressure kPa</th><th className="num">Flow cm/s</th><th className="num">Gravity g</th><th>Result</th></tr></thead>
                <tbody>{x.experiments?.map((e, i) => <tr key={i} title={e.evidence || ''}><td>{e.fuel}</td><td>{e.fuel_type}</td><td className="num">{rg(e.oxygen_pct_min, e.oxygen_pct_max)}</td><td className="num">{rg(e.pressure_kpa_min, e.pressure_kpa_max)}</td><td className="num">{e.flow_velocity_cm_s ?? '—'}</td><td className="num">{e.gravity_g ?? '—'}</td><td>{e.key_result}</td></tr>)}</tbody></table></div>
              <p className="subtle text-xs">Dashes mean the value was not stated in the source. Hover a row to see the extracted evidence. Some rows were extracted by an LLM, so check the source passage.</p>
              <h3>Sources <span className="muted text-sm">(click to read the passage)</span></h3>
              <ul>{x.sources?.slice(0, 6).map((s) => <li key={s.chunk_id}><SourceLink source={{ acronym: x.acronym, file: s.file, pages: s.page ? [s.page] : [], hit: s.chunk_id, url: x.url }}>{s.file.split('/').pop()}{s.page ? ` · p. ${s.page}` : ''}</SourceLink></li>)}</ul>
              <div><button type="button" className="cta" onClick={() => onAsk(`What are the main safety takeaways from ${x.acronym}?`)}><Icon name="chat" /> Ask about this</button></div>
            </div>
          );
        }}
      </Async>
    </div>
  );
}
