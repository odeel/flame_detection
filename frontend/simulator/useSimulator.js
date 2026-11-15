import { useEffect, useMemo, useState } from 'react';
import { api, useApi } from '../api.js';

export const FALLBACK_FUELS = ['Dodecane', 'Heptane', 'Methanol'];
export const LIMITS = { o2: [10, 45], pressure: [30, 320], co2: [0, 60], he: [0, 60], d0: [1, 6] };

const fromHabitat = (h) => ({ o2: h.o2_pct, pressure: h.pressure_kpa, co2: 0, he: 0, d0: null });

/**
 * Simulator state for one habitat: the parameters, debounced /predict, the /flammap grid
 * and helpers to load a scenario. All calls are free (no LLM). `enabled=false` skips requests.
 */
export function useSimulator(habitat, enabled = true) {
  const base = useMemo(() => fromHabitat(habitat), [habitat.id, habitat.o2_pct, habitat.pressure_kpa]); // eslint-disable-line react-hooks/exhaustive-deps
  const [p, setP] = useState(base);
  const [fuel, setFuel] = useState('Heptane');
  useEffect(() => setP(base), [base]);

  const fuelsQ = useApi(() => (enabled ? api.fuels() : Promise.resolve(null)), [enabled]);
  const fuels = fuelsQ.data?.length ? fuelsQ.data : FALLBACK_FUELS;
  useEffect(() => { if (fuelsQ.data?.length && !fuelsQ.data.includes(fuel)) setFuel(fuelsQ.data.includes('Heptane') ? 'Heptane' : fuelsQ.data[0]); }, [fuelsQ.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const total = p.o2 + p.co2 + p.he;
  const invalid = total > 100 ? `O₂ + CO₂ + He add up to ${Math.round(total)} %. Lower one of them to 100 % or less.` : null;

  const pred = useApi(
    () => (!enabled || invalid ? Promise.resolve(null) : api.predict({ fuel, o2_pct: p.o2, pressure_kpa: p.pressure, co2_pct: p.co2, he_pct: p.he, d0_mm: p.d0 })),
    [enabled, fuel, p.o2, p.pressure, p.co2, p.he, p.d0, !!invalid], { debounce: 300, keepOnError: false },
  );
  const map = useApi(() => (enabled ? api.flammap(habitat.id, fuel, 40) : Promise.resolve(null)), [enabled, habitat.id, fuel]);

  const set = (patch) => setP((x) => ({ ...x, ...patch }));
  const changed = ['o2', 'pressure', 'co2', 'he'].some((k) => Math.abs((p[k] ?? 0) - (base[k] ?? 0)) > 1e-6);
  return {
    habitat, base, p, set, fuel, setFuel, fuels, invalid, pred, map, changed,
    reset: () => setP(base),
    /** Load a scenario (gap suggestion, what-if result...) into the controls. */
    load: (s) => {
      if (s.fuel && fuels.includes(s.fuel)) setFuel(s.fuel);
      setP((x) => ({ o2: s.o2_pct ?? x.o2, pressure: s.pressure_kpa ?? x.pressure, co2: s.co2_pct ?? 0, he: s.he_pct ?? 0, d0: s.d0_mm ?? x.d0 }));
    },
  };
}
