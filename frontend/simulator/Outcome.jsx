import { Badge, Card, ErrorState, Icon, IntervalMeter, Skeleton, cx } from '../ui.jsx';
import { burnTone, fix } from './scale.js';

const TONE_COLOR = { danger: 'var(--danger)', warning: 'var(--warning)', info: 'var(--info)', success: 'var(--success)' };

function Tile({ q, title, icon, render, invalid, span = 4 }) {
  const r = q.data;
  let body;
  if (invalid) body = <p className="muted text-sm">Fix the gas mix to see a prediction.</p>;
  else if (q.error && !r) body = <ErrorState compact message={q.error} onRetry={q.reload} />;
  else if (!r) body = <Skeleton lines={3} />;
  else body = render(r);
  return <Card span={span} className="outcome" title={title} icon={icon} stale={q.loading && !!r}>{body}</Card>;
}

/** Three outcome cards from /predict: fuel burned, extinction diameter, burning rate. */
export function OutcomeTiles({ sim, which = ['burned', 'dext', 'rate'], span = 4 }) {
  const q = sim.pred, inv = sim.invalid;
  const tiles = {
    burned: <Tile key="burned" q={q} invalid={inv} span={span} title="Fuel burned" icon="flame" render={(r) => {
      const t = burnTone(r.fuel_burned.mean);
      return (<>
        <div className="row between"><span className={cx('outcome-v num', `tone-${t.tone}`)}>{Math.round(r.fuel_burned.mean * 100)}<small>%</small></span><Badge tone={t.tone}>{t.label}</Badge></div>
        <p className="outcome-l">Share of the droplet burned before the flame went out.</p>
        <IntervalMeter {...r.fuel_burned} color={TONE_COLOR[t.tone]} format={(v) => `${Math.round(v * 100)}%`} labels={['0', '100%']} />
      </>);
    }} />,
    dext: <Tile key="dext" q={q} invalid={inv} span={span} title="Extinction diameter" icon="target" render={(r) => (<>
      <span className="outcome-v num">{fix(r.dext_ratio.mean, 2)}<small>D/D₀</small></span>
      <p className="outcome-l">Droplet size when the flame went out, relative to the start. 0 = burned completely.</p>
      <IntervalMeter {...r.dext_ratio} color="var(--primary)" format={(v) => fix(v, 2)} />
    </>)} />,
    rate: <Tile key="rate" q={q} invalid={inv} span={span} title="Burning rate" icon="gauge" render={(r) => (<>
      <span className="outcome-v num">{fix(r.burning_rate_mm2_s.mean, 2)}<small>mm²/s</small></span>
      <p className="outcome-l">How fast the droplet surface shrinks (d²-law constant).</p>
      <IntervalMeter {...r.burning_rate_mm2_s} max={1.2} color="var(--accent-2)" format={(v) => fix(v, 2)} />
    </>)} />,
  };
  return which.map((k) => tiles[k]);
}

/** Confidence: in range, distance to nearest real test, warnings, gravity note. */
export function ConfidenceCard({ sim, span = 5 }) {
  const q = sim.pred, r = q.data;
  const dist = r?.distance_to_nearest_test, conf = dist == null ? null : dist < 0.5 ? ['success', 'High'] : dist < 1.5 ? ['warning', 'Medium'] : ['danger', 'Low'];
  return (
    <Card span={span} title="How much to trust this" icon="shield" stale={q.loading && !!r}>
      {sim.invalid ? <p className="muted text-sm">Waiting for a valid gas mix.</p>
        : q.error && !r ? <ErrorState compact message={q.error} onRetry={q.reload} />
          : !r ? <Skeleton lines={4} />
            : (
              <div className="stack">
                <div className="cluster">
                  <Badge tone={conf[0]}>{conf[1]} confidence</Badge>
                  <Badge tone={r.in_range ? 'success' : 'warning'}>{r.in_range ? 'Inside tested range' : 'Extrapolation'}</Badge>
                </div>
                <div className="row between text-sm"><span className="muted">Distance to nearest NASA test</span><b className="num">{fix(dist, 2)}</b></div>
                <IntervalMeter mean={Math.min(dist, 4)} low={0} high={Math.min(dist, 4)} max={4} color={`var(--${conf[0]})`} format={(v) => fix(v, 1)} labels={['on a test', 'far']} caption="" />
                {r.warnings?.length > 0 && <ul className="warn-list">{r.warnings.map((w) => <li key={w}><Icon name="alert" className="tone-warning" /><span>{w}</span></li>)}</ul>}
                <p className="muted text-xs">{r.gravity_note}</p>
              </div>
            )}
    </Card>
  );
}
