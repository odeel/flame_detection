import { useEffect, useMemo, useState } from 'react';
import Globe from './Globe.jsx';
import { local, useApi } from './api.js';
import { Badge } from './ui.jsx';

const BODY = { iss: 'earth', gateway: 'moon', moon_base: 'moon', mars_base: 'mars' };
const ESA = ['France', 'Germany', 'Italy', 'Spain', 'Belgium', 'Netherlands', 'Switzerland', 'Denmark', 'Norway', 'Sweden', 'United Kingdom'];
const PARTNERS = new Map([
  ['United States of America', ['NASA', 'Leads the program; Destiny laboratory module.']], ['Russia', ['Roscosmos', 'Russian segment modules.']],
  ['Japan', ['JAXA', 'Kibo laboratory module.']], ['Canada', ['CSA', 'Canadarm2 robotic arm.']],
  ...ESA.map((n) => [n, ['ESA member', 'Takes part through ESA, which provides the Columbus laboratory.']]),
]);
// Approximate [lon, lat]; verify before publishing.
const SITES = [
  { id: 'a11', name: 'Apollo 11', ll: [23.47, 0.67], note: 'USA · 1969' }, { id: 'a15', name: 'Apollo 15', ll: [3.63, 26.13], note: 'USA · 1971' },
  { id: 'a17', name: 'Apollo 17', ll: [30.77, 20.19], note: 'USA · 1972' }, { id: 'c3', name: 'Chang’e-3', ll: [-19.51, 44.12], note: 'China · 2013' },
  { id: 'c4', name: 'Chang’e-4', ll: [177.59, -45.46], note: 'China · 2019' }, { id: 'ch3', name: 'Chandrayaan-3', ll: [32.32, -69.37], note: 'India · 2023' },
  { id: 'slim', name: 'SLIM', ll: [25.25, -13.3], note: 'Japan · 2024' },
];

export default function HabitatGlobe({ habitat, onAsk }) {
  const body = BODY[habitat.id] || 'earth';
  const [sel, setSel] = useState(null);
  useEffect(() => setSel(null), [habitat.id]);
  const luci = useApi(() => local('luci'), []);
  const hp = habitat.lat != null && habitat.lon != null && body !== 'earth' && habitat.id !== 'gateway' ? [{ id: habitat.id, name: habitat.name, ll: [habitat.lon, habitat.lat] }] : [];
  const pins = body === 'moon' ? [...SITES.filter(() => habitat.id !== 'gateway'), ...hp] : hp;
  const info = useMemo(() => {
    if (!sel) return null;
    const s = SITES.find((x) => x.id === sel); if (s) return [s.name, s.note, 'Past landing site, shown for orientation.'];
    const p = PARTNERS.get(sel); if (p || body === 'earth') return [sel, p ? p[0] : 'Not an ISS partner nation', p ? p[1] : ''];
    return null;
  }, [sel, body]);
  return (
    <div className="globe-wrap">
      <div className="globe-box"><Globe key={body} body={body} highlight={body === 'earth' ? PARTNERS : new Map()} pins={pins} orbit={body === 'earth'} selected={sel} onSelect={setSel} /></div>
      <div className="globe-side">
        <div className="card card--inset info">
          <h3>{habitat.name}</h3>
          <div className="cluster"><Badge plain>{habitat.body}</Badge><Badge plain>{habitat.o2_pct}% O₂</Badge><Badge plain>{habitat.pressure_kpa} kPa</Badge><Badge plain>{habitat.gravity_g} g</Badge>{habitat.status === 'assumption' && <Badge tone="warning">assumption</Badge>}</div>
          <p>{habitat.description}</p>
          {habitat.note && <p className="muted text-sm">{habitat.note}</p>}
          <p className="subtle text-xs">{habitat.source}</p>
          <button type="button" className="btn" onClick={() => onAsk(`What fire-safety research is relevant to ${habitat.name}?`)}>Ask about this habitat</button>
        </div>
        {info && <div className="card card--inset info fade-in" aria-live="polite"><b>{info[0]}</b><p className="mu sm">{info[1]}</p><p className="sm">{info[2]}</p></div>}
        {body === 'moon' && luci.data && (
          <div className="card card--inset info"><h3>{luci.data.title}</h3><p className="mu sm">{luci.data.note}</p>
            <ul className="sm">{luci.data.points.map((p) => <li key={p}>{p}</li>)}</ul><p className="mu sm">Not reported: {luci.data.notReported} · {luci.data.source}</p></div>)}
        <p className="mu sm">Drag to rotate, scroll to zoom, click a marker{body === 'earth' ? ' or country' : ''}.</p>
      </div>
    </div>
  );
}
