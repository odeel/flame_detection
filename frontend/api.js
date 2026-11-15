import { useCallback, useEffect, useState } from 'react';
// Real RAG backend (FlameAtlas). Set VITE_API_URL in .env if it is not on localhost:8000.
export const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
async function j(path, opts) {
  let r;
  try { r = await fetch(BASE + path, { headers: { 'Content-Type': 'application/json' }, ...opts }); }
  catch { throw new Error(`Cannot reach the data service at ${BASE}. Is the backend running?`); }
  if (!r.ok) {
    let d = ''; try { d = (await r.json()).detail; } catch { /* no body */ }
    if (Array.isArray(d)) d = d.map((x) => x.msg).join('; ');
    throw new Error(r.status === 503 ? 'The AI service has no API key configured (503).' : d || `Request failed (${r.status})`);
  }
  return r.json();
}
const post = (p, b) => j(p, { method: 'POST', body: JSON.stringify(b) });
const qs = (o) => new URLSearchParams(Object.entries(o).filter(([, v]) => v != null && v !== '')).toString();
export const api = {
  habitats: () => j('/habitats'),
  investigations: () => j('/investigations'),
  investigation: (id) => j('/investigation/' + encodeURIComponent(id)),
  compare: (ids) => j('/compare?ids=' + ids.map(encodeURIComponent).join(',')),
  rank: (b) => post('/rank', b),          // { habitat_id, priorities:{flammability,detection,suppression,physics,closeness}, top }
  ask: (b) => post('/ask', b),            // { question, habitat, k, check } - takes 10-20 s when not cached
  retrieve: (b) => post('/retrieve', b),
  passage: (id) => j('/passage?id=' + encodeURIComponent(id)),
  // Prediction model (droplet flames, free, < 1 s)
  fuels: () => j('/fuels'),
  predict: (b) => post('/predict', b),    // { fuel, o2_pct, pressure_kpa, co2_pct, he_pct, d0_mm } or { habitat_id, fuel }
  flammap: (hid, fuel, n = 40) => j(`/flammap/${encodeURIComponent(hid)}?${qs({ fuel, n })}`),
  gaps: (hid, n = 6, explain = false) => j(`/gaps/${encodeURIComponent(hid)}?${qs({ n, explain })}`), // explain=true costs ~$0.005
  whatif: (b) => post('/whatif', b),      // values mode is free; { text } mode uses the LLM (~$0.01)
  // Materials fire-risk screening: multipart upload of one CSV (field "file"); ~$0.005 per new row, cached rows free.
  materialsUpload: (file, report = true) => {
    const fd = new FormData(); fd.append('file', file);
    return j(`/materials/upload?report=${report}`, { method: 'POST', body: fd, headers: {} });   // empty headers: browser sets the multipart boundary
  },
  absolute: (path) => (path ? BASE + path : null),   // turns a backend path such as report_url into a full link
};
export const local = (name) => fetch(`/data/${name}.json`).then((r) => r.json());   // static files in public/data

/**
 * Shared fetch hook. Returns { data, error, loading, reload }.
 * While a new request runs, the previous data is kept (so UIs can show it as "stale").
 * opts.debounce (ms) waits before firing, useful for sliders.
 */
export function useApi(fn, deps, opts = {}) {
  const [s, set] = useState({ data: null, error: null, loading: true });
  const [tick, setTick] = useState(0);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  const wait = opts.debounce || 0;
  useEffect(() => {
    let ok = true; set((x) => ({ ...x, loading: true, error: null }));
    const run = () => fn().then((data) => ok && set({ data, error: null, loading: false })).catch((e) => ok && set((x) => ({ data: opts.keepOnError ? x.data : null, error: e.message, loading: false })));
    const t = wait ? setTimeout(run, wait) : (run(), null);
    return () => { ok = false; if (t) clearTimeout(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { ...s, reload };
}
