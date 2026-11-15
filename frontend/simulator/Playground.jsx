import { useState } from 'react';
import { api, useApi } from '../api.js';
import { Badge, Card, ErrorState, Segmented, Slider } from '../ui.jsx';
import { FALLBACK_FUELS } from './useSimulator.js';

const PLACES = [{ value: 101.3, label: 'Space station' }, { value: 56.5, label: 'Moon base' }];
const FRIENDLY = { Heptane: 'Heptane (like petrol)', Methanol: 'Methanol (alcohol)', Dodecane: 'Dodecane (like jet fuel)' };
function story(b) {
  if (b == null) return ['…', ''];
  if (b >= 0.9) return ['The droplet burns almost completely.', 'The flame has enough oxygen to keep itself going until the fuel is gone.'];
  if (b >= 0.6) return ['Most of the droplet burns, then the flame goes out.', 'The flame is getting weaker as it shrinks.'];
  if (b >= 0.3) return ['The flame struggles and goes out early.', 'Less oxygen means the flame can’t sustain itself for long.'];
  return ['The flame goes out almost straight away.', 'There isn’t enough oxygen for a flame to survive here.'];
}

/** Student version of the simulator: one slider, one picture, plain words. Uses the real /predict model. */
export default function Playground({ span = 12 }) {
  const fuelsQ = useApi(api.fuels, []);
  const fuels = fuelsQ.data?.length ? fuelsQ.data : FALLBACK_FUELS;
  const [fuel, setFuel] = useState('Heptane'), [o2, setO2] = useState(21), [pk, setPk] = useState(101.3);
  const q = useApi(() => api.predict({ fuel, o2_pct: o2, pressure_kpa: pk }), [fuel, o2, pk], { debounce: 250 });
  const b = q.data?.fuel_burned.mean, [msg, why] = story(b), r = 26 + (b ?? 0.5) * 62;
  return (
    <Card span={span} variant="accent" stale={q.loading && !!q.data}>
      <div className="play">
        <div className="play-stage" aria-hidden>
          <Badge tone="info">0 g · no up or down</Badge>
          <svg viewBox="0 0 240 240">
            <defs>
              <radialGradient id="pg-ball"><stop offset="0" stopColor="#ffffff" stopOpacity=".95" /><stop offset=".35" stopColor="#7dd3fc" stopOpacity=".9" /><stop offset=".7" stopColor="#3b82f6" stopOpacity=".55" /><stop offset="1" stopColor="#ff8a3d" stopOpacity="0" /></radialGradient>
              <radialGradient id="pg-halo"><stop offset=".6" stopColor="#ff8a3d" stopOpacity="0" /><stop offset=".85" stopColor="#ff8a3d" stopOpacity=".35" /><stop offset="1" stopColor="#ff5fa8" stopOpacity="0" /></radialGradient>
            </defs>
            <circle className="play-ball sphere-flame" cx="120" cy="120" r={r + 18} fill="url(#pg-halo)" opacity={b ?? 0.5} />
            <circle className="play-ball sphere-flame" cx="120" cy="120" r={r} fill="url(#pg-ball)" opacity={0.35 + (b ?? 0.5) * 0.65} />
            <circle cx="120" cy="120" r="9" fill="#1e1b4b" stroke="#a5b4fc" strokeWidth="1.5" />
          </svg>
        </div>
        <div className="stack-lg">
          <div className="stack-sm">
            <p className="eyebrow">Flame playground · real NASA model</p>
            <h3 className="text-lg">What happens to a burning fuel droplet in space?</h3>
            <p className="muted">Astronauts on the ISS lit tiny fuel droplets and watched them burn. Our model learned from those tests. Change the oxygen and see what it predicts.</p>
          </div>
          <div className="stack-sm"><span className="field">Fuel</span><Segmented label="Fuel" value={fuel} onChange={setFuel} options={fuels.map((f) => ({ value: f, label: FRIENDLY[f] || f }))} /></div>
          <div className="stack-sm"><span className="field">Where?</span><Segmented label="Place" value={pk} onChange={setPk} options={PLACES} /></div>
          <Slider label="Oxygen in the air" unit="%" value={o2} min={12} max={40} step={1} onChange={setO2} marker={21} foot="Earth’s air: 21 %" />
          <div className="stack-xs" aria-live="polite">
            {q.error && !q.data ? <ErrorState compact message={q.error} onRetry={q.reload} /> : <>
              <p className="play-msg">{msg}</p>
              <p className="muted text-sm">{why} {b != null && <>The model says about <b>{Math.round(b * 100)} %</b> of the droplet burns.</>}</p>
            </>}
          </div>
        </div>
      </div>
    </Card>
  );
}
