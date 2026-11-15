import { useState } from 'react';
import { api, useApi } from '../api.js';
import { Badge, Card, EmptyState, ErrorState, Icon, Note, Skeleton } from '../ui.jsx';
import { fix } from './scale.js';

/**
 * Before/after comparison: habitat baseline vs the simulator's current atmosphere (free, values mode),
 * or a typed sentence parsed by the LLM (~$0.01, only on submit).
 */
export default function WhatIf({ sim, span = 12 }) {
  const { habitat, p, changed, invalid } = sim;
  const live = useApi(
    () => (!changed || invalid ? Promise.resolve(null) : api.whatif({ habitat_id: habitat.id, o2_pct: p.o2, pressure_kpa: p.pressure, co2_pct: p.co2, he_pct: p.he, explain: false })),
    [habitat.id, p.o2, p.pressure, p.co2, p.he, changed, !!invalid], { debounce: 500 },
  );
  const [text, setText] = useState(''), [typed, setTyped] = useState(null);
  const submit = async (e) => {
    e.preventDefault(); if (!text.trim()) return;
    setTyped({ loading: true });
    try { setTyped({ data: await api.whatif({ text: text.trim(), explain: true }) }); } catch (err) { setTyped({ error: err.message }); }
  };
  const res = typed?.data?.status === 'ok' ? typed.data : live.data;

  let body;
  if (typed?.loading) body = <Skeleton lines={5} />;
  else if (typed?.error) body = <ErrorState compact message={typed.error} onRetry={() => setTyped(null)} />;
  else if (typed?.data && typed.data.status !== 'ok') body = <Note>{typed.data.status === 'invalid' ? `Impossible values: ${(typed.data.errors || []).join('; ')}` : `Not understood as a habitat scenario: ${typed.data.problem}`}</Note>;
  else if (!res) body = live.error ? <ErrorState compact message={live.error} onRetry={live.reload} />
    : invalid ? <p className="muted text-sm">Fix the gas mix to compare.</p>
      : live.loading && changed ? <Skeleton lines={5} />
        : <EmptyState compact icon="sparkle" title="Change the atmosphere to compare" hint={`Move any slider away from ${habitat.name}'s values, or describe a scenario below. You will see how each fuel and the study ranking shift.`} />;
  else body = <Result r={res} typed={typed?.data?.status === 'ok'} onApply={() => sim.load(res.scenario)} onClear={() => { setTyped(null); setText(''); }} />;

  return (
    <Card span={span} title="What-if scenario" icon="sparkle" variant="accent" stale={live.loading && !!live.data && !typed}
      sub={`Baseline: ${habitat.name} (${habitat.o2_pct} % O₂, ${habitat.pressure_kpa} kPa) vs your simulated atmosphere`}>
      {body}
      <form className="whatif-form" onSubmit={submit}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder='Describe a scenario, e.g. "Mars base raises oxygen to 30 %"' aria-label="Describe a scenario" />
        <button className="btn" type="submit" disabled={typed?.loading || !text.trim()}><Icon name="sparkle" /> Analyze</button>
      </form>
      <p className="subtle text-xs">Slider comparisons are free and instant. A typed scenario uses the AI model (about $0.01, cached afterwards).</p>
    </Card>
  );
}

function Result({ r, typed, onApply, onClear }) {
  const changes = Object.entries(r.changes || {});
  return (
    <div className="bento fade-in">
      <div className="span-7 stack">
        {typed && <Note tone="info"><b>{r.parsed?.summary}</b> <span className="cluster" style={{ marginTop: 6 }}><button type="button" className="btn-quiet btn-sm" onClick={onApply}>Load into simulator</button><button type="button" className="link text-sm" onClick={onClear}>Back to live comparison</button></span></Note>}
        <div className="cluster">{changes.map(([k, v]) => <Badge key={k} tone="primary" plain>{k.replace('_pct', ' %').replace('_kpa', ' kPa').replace('pressure', 'pressure')}: {fix(v.before, 1)} → {fix(v.after, 1)}</Badge>)}</div>
        <div className="stack">
          {r.fuels.map((f) => {
            const d = f.change_fuel_burned, tone = d > 0.005 ? 'tone-danger' : d < -0.005 ? 'tone-success' : 'muted';
            return (
              <div className="delta-row" key={f.fuel}>
                <b className="text-sm">{f.fuel}</b>
                <div className="delta-bars" title="Fuel burned before (grey) and after (flame)">
                  <i className="before" style={{ width: `${f.before.fuel_burned.mean * 100}%` }} />
                  <i className="after" style={{ width: `${f.after.fuel_burned.mean * 100}%` }} />
                </div>
                <span className={`delta ${tone}`}>{d > 0 ? '+' : ''}{fix(d * 100, 1)} pts</span>
              </div>
            );
          })}
          <p className="subtle text-xs">Bars: share of fuel burned before (grey) and after (flame). Up = more dangerous.</p>
        </div>
        {r.explanation && <p className="text-sm">{r.explanation}</p>}
        {r.warnings?.length > 0 && <ul className="warn-list">{r.warnings.map((w) => <li key={w}><Icon name="alert" /><span>{w}</span></li>)}</ul>}
      </div>
      <div className="span-5 stack">
        <h4>Study ranking after the change</h4>
        <ol className="rank-list">
          {r.ranking_top.map((x) => (
            <li key={x.id}>
              <span className="rk">#{x.rank_after}</span>
              <span><b>{x.acronym}</b> <span className="muted text-xs">{fix(x.score_after * 100, 0)} pts</span></span>
              <span className={x.rank_change > 0 ? 'mv-up' : x.rank_change < 0 ? 'mv-down' : 'subtle'}>{x.rank_change > 0 ? <><Icon name="up" />{x.rank_change}</> : x.rank_change < 0 ? <><Icon name="down" />{-x.rank_change}</> : '—'}</span>
            </li>))}
        </ol>
        {r.ranking_big_moves?.length > 0 && <div className="cluster text-sm"><span className="muted">Big moves:</span>{r.ranking_big_moves.map((x) => <Badge key={x.id} tone={x.rank_after < x.rank_before ? 'success' : 'danger'}>{x.acronym} #{x.rank_before}→#{x.rank_after}</Badge>)}</div>}
      </div>
    </div>
  );
}
