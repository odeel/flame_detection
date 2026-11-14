import { api, useApi } from '../api.js';
const rg = (a) => { const v = a.filter((n) => n != null); return v.length ? `${Math.min(...v)}–${Math.max(...v)}` : '—'; };
export default function ComparePanel({ ids }) {
  const c = useApi(() => (ids.length > 1 ? api.compare(ids) : Promise.resolve([])), [ids.join(',')]);
  if (ids.length < 2) return <p className="mu">Tick “Compare” on two or three investigations in the Explorer, then come back here.</p>;
  if (c.loading) return <p className="mu">Loading comparison…</p>;
  if (c.error) return <p className="err" role="alert">{c.error}</p>;
  const rows = [
    ['Platform', (x) => x.platform], ['Years', (x) => (x.years ? x.years.join('–') : '—')],
    ['Fuel types', (x) => [...new Set(x.experiments.map((e) => e.fuel_type).filter(Boolean))].join(', ') || '—'],
    ['O₂ tested, %', (x) => rg(x.experiments.flatMap((e) => [e.oxygen_pct_min, e.oxygen_pct_max]))],
    ['Pressure tested, kPa', (x) => rg(x.experiments.flatMap((e) => [e.pressure_kpa_min, e.pressure_kpa_max]))],
    ['Objectives', (x) => x.objectives?.join(' · ')], ['Main finding', (x) => x.main_findings?.[0]], ['Safety relevance', (x) => x.safety_relevance],
  ];
  return (
    <div className="tbl"><table><thead><tr><th />{c.data.map((x) => <th key={x.id}>{x.acronym}</th>)}</tr></thead>
      <tbody>{rows.map(([l, f]) => <tr key={l}><th scope="row">{l}</th>{c.data.map((x) => <td key={x.id}>{f(x)}</td>)}</tr>)}</tbody></table></div>
  );
}
