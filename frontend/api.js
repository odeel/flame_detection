// ONE place for all data access. No VITE_API_URL -> mock/static files. Set it in .env to use the real backend:
//   VITE_API_URL=http://localhost:8000
const BASE = import.meta.env.VITE_API_URL || '';
const token = () => localStorage.getItem('token');
async function j(path, opts = {}) {
  const r = await fetch(BASE + path, { ...opts, headers: { 'Content-Type': 'application/json', ...(token() && { Authorization: `Bearer ${token()}` }), ...opts.headers } });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}
// Mock answer in the same shape as the real /api/chat response (see DATA_CONTRACT.md).
const mockAsk = async ({ question, habitat }) => {
  await new Promise((r) => setTimeout(r, 700));
  const partial = /partial|moon|lunar gravity/i.test(question);
  return {
    answer: partial ? 'PSI has no partial-gravity combustion data yet. LUCI and FM2 are expected to add some; microgravity and normal-gravity results can bound intermediate levels.'
      : `Demo answer for "${question}" in the ${habitat || 'selected'} habitat. The real RAG backend is not connected yet.`,
    citations: [{ investigationId: 'cfig', title: 'ACME CFI-G', snippet: 'Placeholder passage from the indexed record.', url: '' }],
    followups: ['Which tests used the highest oxygen levels?', 'What does this mean for materials selection?'],
  };
};
export const api = {
  ask: (b) => (BASE ? j('/api/chat', { method: 'POST', body: JSON.stringify(b) }) : mockAsk(b)),
  investigations: () => (BASE ? j('/api/investigations') : fetch('/data/investigations.json').then((r) => r.json())),
  kpis: (role) => (BASE ? j(`/api/kpis?role=${role}`) : fetch('/data/kpis.json').then((r) => r.json()).then((k) => k[role])),
};