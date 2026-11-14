import { useEffect, useState } from 'react';
// Real RAG backend (FlameAtlas). Set VITE_API_URL in .env if it is not on localhost:8000.
export const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
async function j(path, opts) {
  let r;
  try { r = await fetch(BASE + path, { headers: { 'Content-Type': 'application/json' }, ...opts }); }
  catch { throw new Error(`Cannot reach the data service at ${BASE}. Is the backend running?`); }
  if (!r.ok) {
    let d = ''; try { d = (await r.json()).detail; } catch { /* no body */ }
    throw new Error(r.status === 503 ? 'The AI service has no API key configured (503).' : d || `Request failed (${r.status})`);
  }
  return r.json();
}
const post = (p, b) => j(p, { method: 'POST', body: JSON.stringify(b) });
export const api = {
  habitats: () => j('/habitats'),
  investigations: () => j('/investigations'),
  investigation: (id) => j('/investigation/' + encodeURIComponent(id)),
  compare: (ids) => j('/compare?ids=' + ids.map(encodeURIComponent).join(',')),
  rank: (b) => post('/rank', b),          // { habitat_id, priorities:{flammability,detection,suppression,physics,closeness}, top }
  ask: (b) => post('/ask', b),            // { question, habitat, k, check } - takes 10-20 s when not cached
  retrieve: (b) => post('/retrieve', b),
  passage: (id) => j('/passage?id=' + encodeURIComponent(id)),
  // /predict, /fuels: predictive features are intentionally not used yet.
};
export const local = (name) => fetch(`/data/${name}.json`).then((r) => r.json());   // static files in public/data

export function useApi(fn, deps) {
  const [s, set] = useState({ data: null, error: null, loading: true });
  useEffect(() => {
    let ok = true; set((x) => ({ ...x, loading: true, error: null }));
    fn().then((data) => ok && set({ data, error: null, loading: false })).catch((e) => ok && set({ data: null, error: e.message, loading: false }));
    return () => { ok = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return s;
}
