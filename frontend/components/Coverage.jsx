import { useEffect, useState } from 'react';
import { api } from '../api.js';

export const kind = (t = '') => (/solid/i.test(t) ? 'Solid' : /liquid|droplet/i.test(t) ? 'Liquid' : /gas/i.test(t) ? 'Gas' : /smoke|aerosol/i.test(t) ? 'Smoke' : null);

// Aggregates every investigation's test rows (via /compare, 6 ids per call): per-investigation ranges + scatter points.
export function useCoverage(invs) {
  const [s, set] = useState({ map: null, points: [], rows: 0, loading: false, error: null });
  useEffect(() => {
    if (!invs?.length) return undefined;
    let ok = true; set((x) => ({ ...x, loading: true }));
    const ids = invs.map((i) => i.id), ch = [];
    for (let i = 0; i < ids.length; i += 6) ch.push(ids.slice(i, i + 6));
    Promise.all(ch.map((c) => api.compare(c))).then((rs) => {
      if (!ok) return;
      const map = {}, points = []; let rows = 0;
      rs.flat().forEach((x) => {
        const e = x.experiments || [], nums = (k) => e.flatMap((r) => [r[k + '_min'], r[k + '_max']]).filter((v) => v != null);
        const o = nums('oxygen_pct'), p = nums('pressure_kpa');
        map[x.id] = { fuels: [...new Set(e.map((r) => kind(r.fuel_type) || kind(r.fuel)).filter(Boolean))], o2: o.length ? [Math.min(...o), Math.max(...o)] : null, p: p.length ? [Math.min(...p), Math.max(...p)] : null, n: x.n_experiments ?? e.length };
        e.forEach((r) => { rows += 1; if (r.oxygen_pct_min != null && r.pressure_kpa_min != null) points.push({ id: x.id, o2: (r.oxygen_pct_min + (r.oxygen_pct_max ?? r.oxygen_pct_min)) / 2, p: (r.pressure_kpa_min + (r.pressure_kpa_max ?? r.pressure_kpa_min)) / 2 }); });
      });
      set({ map, points, rows, loading: false, error: null });
    }).catch((e) => ok && set({ map: null, points: [], rows: 0, loading: false, error: e.message }));
    return () => { ok = false; };
  }, [invs]);
  return s;
}

export function CoverageChart({ cov, habitat }) {
  const W = 420, H = 260, L = 40, B = 30, X = (o) => L + (o / 100) * (W - L - 10), Y = (p) => H - B - (p / 220) * (H - B - 10);
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Tested oxygen and pressure conditions compared with the selected habitat" className="cov">
        {[0, 50, 100, 150, 200].map((p) => <g key={p}><line x1={L} x2={W - 10} y1={Y(p)} y2={Y(p)} stroke="var(--border)" /><text x="4" y={Y(p) + 4} className="axis">{p}</text></g>)}
        {[0, 20, 40, 60, 80, 100].map((o) => <text key={o} x={X(o) - 8} y={H - 10} className="axis">{o}</text>)}
        {cov.points.map((pt, i) => <circle key={i} cx={X(pt.o2)} cy={Y(pt.p)} r="4" fill="var(--primary)" opacity=".45"><title>{pt.id}</title></circle>)}
        <line x1={X(habitat.o2_pct)} x2={X(habitat.o2_pct)} y1="10" y2={H - B} stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="4 3" />
        <line x1={L} x2={W - 10} y1={Y(habitat.pressure_kpa)} y2={Y(habitat.pressure_kpa)} stroke="var(--acc)" strokeWidth="1.5" strokeDasharray="4 3" />
        <circle cx={X(habitat.o2_pct)} cy={Y(habitat.pressure_kpa)} r="7" fill="var(--accent)" stroke="var(--surface-raised)" strokeWidth="2" />
        <text x={W / 2} y={H - 1} className="axis-title" textAnchor="middle">O₂ (%)</text><text x="4" y="10" className="axis-title">kPa</text>
      </svg>
      <p className="muted text-sm">Blue: tested conditions. Amber: {habitat.name}. {cov.points.length} of {cov.rows} test rows list both O₂ and pressure; the rest are not plotted.</p>
    </div>
  );
}
