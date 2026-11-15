import { useState } from 'react';
import { Card, ErrorState, Skeleton } from '../ui.jsx';
import { SourceViewer } from '../components/SourceViewer.jsx';
import { fix } from './scale.js';

/** The real NASA tests closest to the simulated point. Test ids open the source passage. */
export default function NearestTests({ sim, span = 5 }) {
  const q = sim.pred, r = q.data, [view, setView] = useState(null);
  return (
    <Card span={span} title="Nearest NASA tests" icon="beaker" sub="The measurements the prediction leans on" stale={q.loading && !!r}>
      {sim.invalid ? <p className="muted text-sm">Waiting for a valid gas mix.</p>
        : q.error && !r ? <ErrorState compact message={q.error} onRetry={q.reload} />
          : !r ? <Skeleton lines={5} />
            : (
              <div className="tbl">
                <table>
                  <thead><tr><th>Test</th><th className="num">O₂ %</th><th className="num">kPa</th><th className="num">CO₂/He</th><th className="num">k mm²/s</th><th className="num">Dist.</th></tr></thead>
                  <tbody>{r.nearest_tests.map((t) => (
                    <tr key={t.test_id}>
                      <td><button type="button" className="link mono text-xs" onClick={() => setView({ acronym: t.investigation_id, file: t.test_id, hit: t.chunk_id, url: t.url })}>{t.test_id}</button></td>
                      <td className="num">{fix(t.o2_pct, 1)}</td><td className="num">{fix(t.pressure_kpa, 0)}</td>
                      <td className="num">{fix(t.co2_pct, 0)}/{fix(t.he_pct, 0)}</td><td className="num">{fix(t.k_mm2_s, 2)}</td><td className="num">{fix(t.distance, 2)}</td>
                    </tr>))}
                  </tbody>
                </table>
              </div>
            )}
      {view && <SourceViewer source={view} onClose={() => setView(null)} />}
    </Card>
  );
}
