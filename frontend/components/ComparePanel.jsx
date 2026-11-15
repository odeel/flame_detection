import { api, useApi } from '../api.js';
import { Async, EmptyState, Skeleton } from '../ui.jsx';

const rg = (a) => { const v = a.filter((n) => n != null); return v.length ? `${Math.min(...v)}–${Math.max(...v)}` : '—'; };

export default function ComparePanel({ ids, onBrowse }) {
  const c = useApi(() => (ids.length > 1 ? api.compare(ids) : Promise.resolve([])), [ids.join(',')]);
  if (ids.length < 2) {
    return <EmptyState icon="layers" title="Pick two or three investigations"
      hint={`Tick “Compare” on investigations in the Explorer, then come back here. ${ids.length ? '1 selected so far.' : ''}`}
      action={onBrowse && <button type="button" className="btn-quiet btn-sm" onClick={onBrowse}>Open Explorer</button>} />;
  }
  const rows = [
    ['Platform', (x) => x.platform], ['Years', (x) => (x.years ? x.years.join('–') : '—')],
    ['Fuel types', (x) => [...new Set(x.experiments.map((e) => e.fuel_type).filter(Boolean))].join(', ') || '—'],
    ['O₂ tested, %', (x) => rg(x.experiments.flatMap((e) => [e.oxygen_pct_min, e.oxygen_pct_max]))],
    ['Pressure tested, kPa', (x) => rg(x.experiments.flatMap((e) => [e.pressure_kpa_min, e.pressure_kpa_max]))],
    ['Test rows', (x) => x.n_experiments ?? x.experiments.length],
    ['Objectives', (x) => x.objectives?.join(' · ')], ['Main finding', (x) => x.main_findings?.[0]], ['Safety relevance', (x) => x.safety_relevance],
  ];
  return (
    <Async state={c} skeleton={<Skeleton lines={8} />}>
      {(data) => (
        <div className="tbl"><table><thead><tr><th />{data.map((x) => <th key={x.id}>{x.acronym}</th>)}</tr></thead>
          <tbody>{rows.map(([l, f]) => <tr key={l}><th scope="row">{l}</th>{data.map((x) => <td key={x.id}>{f(x)}</td>)}</tr>)}</tbody></table></div>
      )}
    </Async>
  );
}
