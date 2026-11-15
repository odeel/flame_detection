import { useState } from 'react';
import { api, useApi } from '../api.js';
import { Async, Badge, Card, EmptyState, Icon, Note, Skeleton } from '../ui.jsx';
import { fix } from './scale.js';

/** Test-gap finder: untested conditions near the habitat where a new NASA test would teach the model most. */
export default function Gaps({ habitat, onLoad, span = 7 }) {
  const [explain, setExplain] = useState(false);
  const q = useApi(() => api.gaps(habitat.id, 6, explain), [habitat.id, explain]);
  return (
    <Card span={span} title="Suggested next tests" icon="target" sub={`Highest model uncertainty near ${habitat.name}`} stale={q.loading && !!q.data}
      actions={!explain && <button type="button" className="btn-quiet btn-sm" onClick={() => setExplain(true)} title="One AI call, about $0.005, cached afterwards"><Icon name="sparkle" /> Explain</button>}>
      <Async state={q} skeleton={<Skeleton lines={6} />} isEmpty={(d) => !d.suggestions?.length} empty={<EmptyState compact icon="check" title="No gaps found" hint="The model is confident around this habitat." />}>
        {(d) => (
          <div className="stack">
            {d.explanation && <Note tone="info">{d.explanation}</Note>}
            <ol className="gap-list">
              {d.suggestions.map((s) => (
                <li className="gap" key={s.rank}>
                  <span className="gap-rk">{s.rank}</span>
                  <div className="stack-xs">
                    <b className="num">{s.fuel} · {fix(s.o2_pct, 1)} % O₂ · {fix(s.pressure_kpa, 1)} kPa</b>
                    <span className="cluster text-xs">
                      <Badge plain>uncertainty {fix(s.uncertainty, 2)}</Badge>
                      <Badge plain>predicted burn {Math.round(s.predicted_fuel_burned.mean * 100)} %</Badge>
                      {s.outside_tested_range?.map((o) => <Badge key={o} tone="warning">new {o}</Badge>)}
                    </span>
                    <span className="subtle text-xs">Nearest test {s.nearest_test?.test_id} ({fix(s.nearest_test?.o2_pct, 1)} %, {fix(s.nearest_test?.pressure_kpa, 0)} kPa)</span>
                  </div>
                  <button type="button" className="btn-quiet btn-sm" onClick={() => onLoad(s)}>Simulate <Icon name="arrowRight" /></button>
                </li>))}
            </ol>
            <p className="subtle text-xs">{d.caveat} {d.gravity_note}</p>
          </div>
        )}
      </Async>
    </Card>
  );
}
