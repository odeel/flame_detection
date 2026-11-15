import { useMemo, useState } from 'react';
import { Async, Card, Segmented, Skeleton } from '../ui.jsx';
import { fix, nearestIndex, ramp, rampCss } from './scale.js';

const LAYERS = {
  fuel_burned: { label: 'Fuel burned', ramp: 'heat', fmt: (v) => `${Math.round(v * 100)} %`, max: () => 1 },
  uncertainty: { label: 'Uncertainty', ramp: 'cool', fmt: (v) => fix(v, 2), max: (m) => Math.max(...m.uncertainty.flat()) },
  distance_to_tests: { label: 'Distance to tests', ramp: 'cool', fmt: (v) => fix(v, 2), max: (m) => Math.max(...m.distance_to_tests.flat()) },
};
const W = 540, H = 340, L = 48, R = 12, T = 12, B = 40;
const star = (x, y, r) => Array.from({ length: 10 }, (_, i) => { const a = (Math.PI / 5) * i - Math.PI / 2, rr = i % 2 ? r * 0.45 : r; return `${x + rr * Math.cos(a)},${y + rr * Math.sin(a)}`; }).join(' ');

function useScales(m) {
  return useMemo(() => {
    const o2 = m.axes.o2_pct, pr = m.axes.pressure_kpa, pw = W - L - R, ph = H - T - B;
    const [o0, o1] = [o2[0], o2[o2.length - 1]], [l0, l1] = [Math.log(pr[0]), Math.log(pr[pr.length - 1])];
    const X = (v) => L + ((v - o0) / (o1 - o0)) * pw, Y = (v) => T + ph - ((Math.log(v) - l0) / (l1 - l0)) * ph;
    const cw = pw / o2.length, ch = ph / pr.length;
    return { o2, pr, X, Y, cw, ch, pw, ph, inX: (v) => v >= o0 && v <= o1, inY: (v) => v >= pr[0] && v <= pr[pr.length - 1] };
  }, [m]);
}

/** Oxygen x pressure flammability heatmap. Click or use arrow keys to move the simulator to a cell. */
export function FlamMapCard({ sim, span = 7, title = 'Flammability map' }) {
  const [layer, setLayer] = useState('fuel_burned');
  return (
    <Card span={span} title={title} icon="layers" sub={`${sim.fuel} droplets · O₂ vs pressure · click a cell to simulate it`} stale={sim.map.loading && !!sim.map.data}
      actions={<Segmented label="Map layer" value={layer} onChange={setLayer} options={Object.entries(LAYERS).map(([value, l]) => ({ value, label: l.label }))} />}>
      <Async state={sim.map} skeleton={<Skeleton height={300} />}>
        {(d) => <Heatmap m={d.map} layer={layer} sim={sim} />}
      </Async>
    </Card>
  );
}

function Heatmap({ m, layer, sim }) {
  const s = useScales(m), Lr = LAYERS[layer], max = Lr.max(m) || 1;
  const [hover, setHover] = useState(null);
  const grid = m[layer];
  const cells = useMemo(() => {
    const out = [], hatch = [];
    s.pr.forEach((_, i) => s.o2.forEach((__, j) => {
      const v = grid[i][j], nd = m.no_data[i][j];
      const x = L + j * s.cw, y = T + s.ph - (i + 1) * s.ch;
      out.push(<rect key={`${i}-${j}`} className="cell" x={x} y={y} width={s.cw + 0.5} height={s.ch + 0.5} fill={ramp(Lr.ramp, v / max)} opacity={nd ? 0.35 : 1} />);
      if (nd) hatch.push(<rect key={`n${i}-${j}`} x={x} y={y} width={s.cw + 0.5} height={s.ch + 0.5} fill="url(#hatch)" />);
    }));
    return [out, hatch];
  }, [grid, m.no_data, s, Lr.ramp, max]);
  const pt = (e) => { const r = e.currentTarget.getBoundingClientRect(); const x = ((e.clientX - r.left) / r.width) * W, y = ((e.clientY - r.top) / r.height) * H; const j = Math.floor((x - L) / s.cw), i = Math.floor((T + s.ph - y) / s.ch); return i >= 0 && j >= 0 && i < s.pr.length && j < s.o2.length ? [i, j] : null; };
  const cur = { i: nearestIndex(s.pr, sim.p.pressure, true), j: nearestIndex(s.o2, sim.p.o2) };
  const go = (i, j) => sim.set({ o2: +s.o2[j].toFixed(1), pressure: +s.pr[i].toFixed(1) });
  const key = (e) => {
    const d = { ArrowLeft: [0, -1], ArrowRight: [0, 1], ArrowUp: [1, 0], ArrowDown: [-1, 0] }[e.key]; if (!d) return;
    e.preventDefault(); go(Math.max(0, Math.min(s.pr.length - 1, cur.i + d[0])), Math.max(0, Math.min(s.o2.length - 1, cur.j + d[1])));
  };
  const h = hover || [cur.i, cur.j];
  const cx = s.X(Math.min(Math.max(sim.p.o2, s.o2[0]), s.o2[s.o2.length - 1])), cy = s.Y(Math.min(Math.max(sim.p.pressure, s.pr[0]), s.pr[s.pr.length - 1]));
  const yt = [50, 70, 100, 150, 200, 300].filter(s.inY), xt = s.o2.filter((_, k) => k % Math.ceil(s.o2.length / 7) === 0);
  return (
    <div className="stack">
      <svg className="heat" viewBox={`0 0 ${W} ${H}`} tabIndex={0} role="application"
        aria-label={`Flammability map for ${m.fuel}. Arrow keys move the simulated point; current ${Lr.label} ${Lr.fmt(grid[cur.i][cur.j])}.`}
        onKeyDown={key} onMouseLeave={() => setHover(null)} onMouseMove={(e) => setHover(pt(e))} onClick={(e) => { const c = pt(e); if (c) go(...c); }}>
        <defs><pattern id="hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="5" stroke="rgba(255,255,255,.35)" strokeWidth="1.2" /></pattern></defs>
        <g className="hit">{cells[0]}</g>
        <g pointerEvents="none">{cells[1]}</g>
        {yt.map((v) => <text key={v} className="axis" x={L - 6} y={s.Y(v) + 3} textAnchor="end">{v}</text>)}
        {xt.map((v) => <text key={v} className="axis" x={s.X(v)} y={H - B + 14} textAnchor="middle">{Math.round(v)}</text>)}
        <text className="axis-title" x={L + s.pw / 2} y={H - 6} textAnchor="middle">Oxygen (%)</text>
        <text className="axis-title" transform={`translate(12 ${T + s.ph / 2}) rotate(-90)`} textAnchor="middle">Pressure (kPa, log)</text>
        <g pointerEvents="none">
          {m.tests.filter((t) => s.inX(t.o2_pct) && s.inY(t.pressure_kpa)).map((t) => <circle key={t.test_id} cx={s.X(t.o2_pct)} cy={s.Y(t.pressure_kpa)} r="2.6" fill="#fff" stroke="#000" strokeWidth=".6" opacity={t.diluent ? 0.35 : 0.9}><title>{t.test_id}</title></circle>)}
          {m.habitats.filter((x) => s.inX(x.o2_pct) && s.inY(x.pressure_kpa)).map((x) => <g key={x.id}><polygon className="hab-star" points={star(s.X(x.o2_pct), s.Y(x.pressure_kpa), 8)} fill={x.id === sim.habitat.id ? 'var(--accent)' : '#fff'} /><text className="hab-label" x={s.X(x.o2_pct) + 10} y={s.Y(x.pressure_kpa) - 6}>{x.name.replace(/ (surface )?base$/i, '').replace('International Space Station', 'ISS')}</text></g>)}
          <line className="cross" x1={cx} x2={cx} y1={T} y2={T + s.ph} strokeDasharray="3 3" opacity=".7" />
          <line className="cross" x1={L} x2={L + s.pw} y1={cy} y2={cy} strokeDasharray="3 3" opacity=".7" />
          <circle className="cross-dot" cx={cx} cy={cy} r="6" />
        </g>
      </svg>
      <p className="text-sm num" aria-live="polite">
        <span className="muted">{hover ? 'Hover' : 'Simulated point'}:</span> {fix(s.o2[h[1]], 1)} % O₂ · {fix(s.pr[h[0]], 0)} kPa → <b>{Lr.label.toLowerCase()} {Lr.fmt(grid[h[0]][h[1]])}</b>
        {m.no_data[h[0]][h[1]] && <span className="tone-warning"> · far from any test, colour not trustworthy</span>}
      </p>
      <div className="legend">
        <span>{Lr.fmt(0)}</span><span className="legend-ramp" style={{ background: rampCss(Lr.ramp) }} /><span>{Lr.fmt(max)}</span>
        <span className="legend-sw"><i className="hatch" /> no data</span>
        <span className="legend-sw"><i className="dot" /> NASA test</span>
        <span className="legend-sw"><i className="star" /> habitat</span>
      </div>
    </div>
  );
}

/** Fuel burned vs O2 at the current pressure, read from the flammap grid (no extra request). */
export function SensitivityCard({ sim, span = 5 }) {
  return (
    <Card span={span} title="Oxygen sensitivity" icon="chart" sub={`${sim.fuel} at ${fix(sim.p.pressure, 0)} kPa: how fuel burned changes with O₂`} stale={sim.map.loading && !!sim.map.data}>
      <Async state={sim.map} skeleton={<Skeleton height={200} />}>{(d) => <Line m={d.map} sim={sim} />}</Async>
    </Card>
  );
}

function Line({ m, sim }) {
  const w = 420, h = 220, l = 40, r = 12, t = 12, b = 32, o2 = m.axes.o2_pct, i = nearestIndex(m.axes.pressure_kpa, sim.p.pressure, true);
  const X = (v) => l + ((v - o2[0]) / (o2[o2.length - 1] - o2[0])) * (w - l - r), Y = (v) => t + (1 - v) * (h - t - b);
  const row = m.fuel_burned[i], lo = m.fuel_burned_low[i], hi = m.fuel_burned_high[i], nd = m.no_data[i];
  const line = row.map((v, j) => `${j ? 'L' : 'M'}${X(o2[j])},${Y(v)}`).join('');
  const band = `${hi.map((v, j) => `${j ? 'L' : 'M'}${X(o2[j])},${Y(v)}`).join('')}${lo.map((v, j) => `L${X(o2[lo.length - 1 - j])},${Y(lo[lo.length - 1 - j])}`).join('')}Z`;
  const jn = nearestIndex(o2, sim.p.o2), cw = (w - l - r) / o2.length;
  return (
    <svg className="chart" viewBox={`0 0 ${w} ${h}`} role="img" aria-label={`Fuel burned rises from ${Math.round(row[0] * 100)}% at ${o2[0]}% O2 to ${Math.round(row[row.length - 1] * 100)}% at ${o2[o2.length - 1]}% O2.`}>
      {nd.map((n, j) => n && <rect key={j} x={X(o2[j]) - cw / 2} y={t} width={cw + 0.5} height={h - t - b} fill="var(--nodata)" />)}
      {[0, 0.25, 0.5, 0.75, 1].map((v) => <g key={v}><line className="grid-l" x1={l} x2={w - r} y1={Y(v)} y2={Y(v)} /><text className="axis" x={l - 6} y={Y(v) + 3} textAnchor="end">{v * 100}%</text></g>)}
      {o2.filter((_, k) => k % Math.ceil(o2.length / 6) === 0).map((v) => <text key={v} className="axis" x={X(v)} y={h - b + 14} textAnchor="middle">{Math.round(v)}</text>)}
      <text className="axis-title" x={l + (w - l - r) / 2} y={h - 4} textAnchor="middle">Oxygen (%) · grey = no nearby test</text>
      <path className="band" d={band} />
      <path className="line" d={line} />
      <line className="now-l" x1={X(o2[jn])} x2={X(o2[jn])} y1={t} y2={h - b} />
      <circle className="now" cx={X(o2[jn])} cy={Y(row[jn])} r="6" />
    </svg>
  );
}
