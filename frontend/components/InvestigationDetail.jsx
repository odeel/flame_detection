import { api, local, useApi } from '../api.js';
import SourceLink from './SourceViewer.jsx';

const rg = (a, b) => (a == null && b == null ? '—' : a === b || b == null ? `${a}` : `${a}–${b}`);
export default function InvestigationDetail({ id, onBack, onAsk }) {
  const d = useApi(() => api.investigation(id), [id]);
  const acme = useApi(() => local('acme'), []), fin = useApi(() => local('findings'), []);
  if (d.loading) return <p className="mu">Loading investigation…</p>;
  if (d.error) return <div><button className="link" onClick={onBack}>← Back</button><p className="err" role="alert">{d.error}</p></div>;
  const x = d.data, has = (k) => x.acronym.toLowerCase().includes(k.toLowerCase());
  const extra = acme.data?.find((a) => has(a.key)), finds = (fin.data || []).filter((f) => f.key !== 'General' && has(f.key));
  return (
    <div className="detail">
      <button className="link" onClick={onBack}>← Back to list</button>
      <h2>{x.acronym} · {x.name}</h2>
      <p className="mu sm">{x.platform}{x.years ? ` · ${x.years[0]}–${x.years[1]}` : ''} · <a href={x.url} target="_blank" rel="noreferrer">PSI record</a></p>
      <p>{x.plain_summary}</p>
      {extra && <div className="card"><p className="sm"><b>Principal investigators:</b> {extra.pis}</p><p className="sm"><b>Stated link to efficiency or pollution:</b> {extra.link} <span className="mu">({extra.source})</span></p></div>}
      <h3>Objectives</h3><ul>{x.objectives?.map((o) => <li key={o}>{o}</li>)}</ul>
      <h3>Main findings</h3><ul>{x.main_findings?.map((o) => <li key={o}>{o}</li>)}</ul>
      {finds.length > 0 && <><h3>Reported in NASA publications</h3><ul>{finds.map((f) => <li key={f.finding}>{f.finding} <span className="mu sm">({f.quantified.startsWith('Yes') ? 'quantified' : 'not quantified'} · {f.source})</span></li>)}</ul></>}
      {x.safety_relevance && <><h3>Safety relevance</h3><p>{x.safety_relevance}</p></>}
      <h3>Test conditions ({x.n_experiments} rows)</h3>
      <div className="tbl"><table><thead><tr><th>Fuel</th><th>Type</th><th>O₂ %</th><th>Pressure kPa</th><th>Flow cm/s</th><th>Gravity g</th><th>Result</th></tr></thead>
        <tbody>{x.experiments?.map((e, i) => <tr key={i} title={e.evidence || ''}><td>{e.fuel}</td><td>{e.fuel_type}</td><td>{rg(e.oxygen_pct_min, e.oxygen_pct_max)}</td><td>{rg(e.pressure_kpa_min, e.pressure_kpa_max)}</td><td>{e.flow_velocity_cm_s ?? '—'}</td><td>{e.gravity_g ?? '—'}</td><td>{e.key_result}</td></tr>)}</tbody></table></div>
      <p className="mu sm">Dashes mean the value was not stated in the source. Hover a row to see the extracted evidence. Some rows were extracted by an LLM, so check the source passage.</p>
      <h3>Sources (click to read the passage)</h3>
      <ul>{x.sources?.slice(0, 6).map((s) => <li key={s.chunk_id}><SourceLink source={{ acronym: x.acronym, file: s.file, pages: s.page ? [s.page] : [], hit: s.chunk_id, url: x.url }}>{s.file.split('/').pop()}{s.page ? ` · p. ${s.page}` : ''}</SourceLink></li>)}</ul>
      <button className="cta" onClick={() => onAsk(`What are the main safety takeaways from ${x.acronym}?`)}>Ask about this</button>
    </div>
  );
}
