import { useEffect, useState } from 'react';
import { api } from './api.js';
// History is kept in the browser per user. The backend has no conversations endpoint yet (see BACKEND_NOTES.md).
const key = (u) => `chats:${u}`;
const load = (u) => { try { return JSON.parse(localStorage.getItem(key(u)) || '[]'); } catch { return []; } };

export function useChats(user) {
  const [chats, setChats] = useState(() => load(user.email));
  const [active, setActive] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { localStorage.setItem(key(user.email), JSON.stringify(chats)); }, [chats, user.email]);
  const upd = (id, fn) => setChats((cs) => cs.map((c) => (c.id === id ? fn(c) : c)));

  async function ask(text, { id = null, habitat, graph = false } = {}) {
    const cid = id || crypto.randomUUID();
    const hab = chats.find((c) => c.id === cid)?.habitat || habitat || null;      // { id, name }
    if (!id) setChats((cs) => [{ id: cid, title: text.slice(0, 50), habitat: hab, created: Date.now(), messages: [] }, ...cs]);
    setActive(cid);
    upd(cid, (c) => ({ ...c, messages: [...c.messages, { role: 'user', text, ts: Date.now() }] }));
    setBusy(true);
    try {
      const r = await api.ask({ question: text, habitat: hab?.id || null, k: 5, check: true, graph });   // graph: Graph-RAG adds knowledge-graph facts as one extra source
      upd(cid, (c) => ({ ...c, messages: [...c.messages, { role: 'assistant', text: r.answer, sources: r.sources || [], status: r.status, answerable: r.answerable, removed: r.removed_sentences?.length || 0, graph: !!r.graph, graphFacts: r.graph?.n_facts ?? null, ts: Date.now() }] }));
    } catch (e) {
      upd(cid, (c) => ({ ...c, messages: [...c.messages, { role: 'assistant', text: e.message, error: true, sources: [], ts: Date.now() }] }));
    } finally { setBusy(false); }
  }
  const remove = (id) => { setChats((cs) => cs.filter((c) => c.id !== id)); if (active === id) setActive(null); };
  return { chats, active, setActive, ask, busy, remove };
}
