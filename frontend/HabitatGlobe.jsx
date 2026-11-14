import { useMemo, useState } from 'react';
import Globe from './Globe.jsx';

// Static reference content (frontend-owned). Country names match the world-atlas dataset.
const ESA = ['France', 'Germany', 'Italy', 'Spain', 'Belgium', 'Netherlands', 'Switzerland', 'Denmark', 'Norway', 'Sweden', 'United Kingdom'];
const PARTNERS = new Map([
  ['United States of America', { agency: 'NASA', fact: 'Leads the program; Destiny laboratory module.' }],
  ['Russia', { agency: 'Roscosmos', fact: 'Provides core Russian segment modules.' }],
  ['Japan', { agency: 'JAXA', fact: 'Kibo laboratory module.' }],
  ['Canada', { agency: 'CSA', fact: 'Canadarm2 robotic arm.' }],
  ...ESA.map((n) => [n, { agency: 'ESA member', fact: 'Takes part through ESA, which provides the Columbus laboratory.' }]),
]);
// Approximate coordinates [lon, lat]; verify before publishing.
const SITES = [
  { id: 'a11', name: 'Apollo 11', country: 'USA', year: 1969, ll: [23.47, 0.67] },
  { id: 'a15', name: 'Apollo 15', country: 'USA', year: 1971, ll: [3.63, 26.13] },
  { id: 'a17', name: 'Apollo 17', country: 'USA', year: 1972, ll: [30.77, 20.19] },
  { id: 'c3', name: 'Chang’e-3', country: 'China', year: 2013, ll: [-19.51, 44.12] },
  { id: 'c4', name: 'Chang’e-4', country: 'China', year: 2019, ll: [177.59, -45.46] },
  { id: 'ch3', name: 'Chandrayaan-3', country: 'India', year: 2023, ll: [32.32, -69.37] },
  { id: 'slim', name: 'SLIM', country: 'Japan', year: 2024, ll: [25.25, -13.3] },
];

export default function HabitatGlobe({ habitat, onAsk }) {
  const moon = habitat.includes('Lunar');
  const [sel, setSel] = useState(null);
  const info = useMemo(() => {
    if (!sel) return null;
    if (moon) { const s = SITES.find((x) => x.id === sel); return s && { title: s.name, sub: `${s.country} · ${s.year}`, text: 'Landing site on the Moon. Lunar-gravity combustion data is not in PSI yet.', q: `What fire-safety research is relevant to ${s.name}-type lunar surface missions?` }; }
    const p = PARTNERS.get(sel);
    return { title: sel, sub: p ? p.agency : 'Not an ISS partner nation', text: p ? p.fact : 'This country is not one of the ISS partner nations.', q: p ? `Which ISS combustion experiments involved ${p.agency === 'ESA member' ? 'ESA' : p.agency}?` : null };
  }, [sel, moon]);
  return (
    <div className="globe-wrap">
      <div className="globe-box">
        <Globe key={moon ? 'moon' : 'earth'} body={moon ? 'moon' : 'earth'} highlight={moon ? new Map() : PARTNERS} pins={moon ? SITES : []} orbit={!moon} selected={sel} onSelect={setSel} />
      </div>
      <div className="globe-side">
        <h3>{moon ? 'Lunar landing sites' : 'ISS partner nations'}</h3>
        <p className="mu sm">Drag to rotate, scroll to zoom, click {moon ? 'a site' : 'a country'}.</p>
        {moon && <div className="chips">{SITES.map((s) => <button key={s.id} className={'chip' + (sel === s.id ? ' on' : '')} onClick={() => setSel(s.id)}>{s.name}</button>)}</div>}
        <div className="card info" aria-live="polite">
          {info ? (<><b>{info.title}</b><p className="mu sm">{info.sub}</p><p>{info.text}</p>{info.q && <button className="btn" onClick={() => onAsk(info.q)}>Ask about this</button>}</>)
            : <p className="mu">Nothing selected yet.</p>}
        </div>
      </div>
    </div>
  );
}
