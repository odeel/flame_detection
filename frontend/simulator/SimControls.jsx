import { useState } from 'react';
import { Badge, Card, Icon, Segmented, Slider, cx } from '../ui.jsx';
import { LIMITS } from './useSimulator.js';
import { fix } from './scale.js';

/** Left rail of the simulator. `full` adds droplet size (researcher). */
export default function SimControls({ sim, full = true }) {
  const { p, set, fuel, setFuel, fuels, base, habitat, invalid, changed, reset, map } = sim;
  const [open, setOpen] = useState(true);
  const tr = map.data?.map?.tested_range;
  return (
    <div className={cx('sim-rail', !open && 'collapsed')}>
      <Card
        title="Conditions"
        icon="target"
        sub={<>Starting from <b>{habitat.name}</b></>}
        actions={<button type="button" className="ghost sim-controls-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? 'Hide' : 'Show'}</button>}
      >
        <div className="sim-body">
          <div className="stack-sm">
            <span className="field">Fuel droplet</span>
            <Segmented block label="Fuel" options={fuels} value={fuel} onChange={setFuel} />
          </div>
          <Slider label="Oxygen" unit="%" value={p.o2} min={LIMITS.o2[0]} max={LIMITS.o2[1]} step={0.5} onChange={(v) => set({ o2: v })}
            band={tr?.o2_pct} marker={base.o2} format={(v) => fix(v, 1)} hint={tr ? 'Green band: tested by NASA' : null} foot={`habitat ${base.o2} %`} />
          <Slider label="Cabin pressure" unit="kPa" log value={p.pressure} min={LIMITS.pressure[0]} max={LIMITS.pressure[1]} step={0.5} onChange={(v) => set({ pressure: v })}
            band={tr?.pressure_kpa} marker={base.pressure} format={(v) => fix(v, 1)} foot={`habitat ${base.pressure} kPa`} />
          <Slider label="CO₂ added" unit="%" value={p.co2} min={LIMITS.co2[0]} max={LIMITS.co2[1]} step={1} onChange={(v) => set({ co2: v })} format={(v) => fix(v, 0)} hint="ISS suppressant" />
          <Slider label="Helium added" unit="%" value={p.he} min={LIMITS.he[0]} max={LIMITS.he[1]} step={1} onChange={(v) => set({ he: v })} format={(v) => fix(v, 0)} hint="Inert diluent" />
          {full && <Slider label="Droplet diameter d₀" unit="mm" value={p.d0 ?? 3} min={LIMITS.d0[0]} max={LIMITS.d0[1]} step={0.1} onChange={(v) => set({ d0: v })}
            format={(v) => fix(v, 1)} hint={p.d0 == null ? 'Model median used' : null} />}
          {invalid && <p className="field-err" role="alert"><Icon name="alert" />{invalid}</p>}
          <div className="row between">
            <span className="cluster">
              <Badge tone="info" title="Gravity is not a model input">{habitat.gravity_g} g</Badge>
              <Badge plain>O₂ partial {fix((p.o2 / 100) * p.pressure, 1)} kPa</Badge>
            </span>
            <button type="button" className="btn-quiet btn-sm" onClick={reset} disabled={!changed && p.d0 == null}><Icon name="refresh" /> Reset</button>
          </div>
        </div>
      </Card>
    </div>
  );
}
