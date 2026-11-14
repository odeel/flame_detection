import { useEffect, useState } from 'react';
import { api } from './api.js';
// History lives in localStorage per user until the backend provides /api/conversations (see DATA_CONTRACT.md).
const key = (u) => `chats:${u}`;
const load = (u) => { try { return JSON.parse(localStorage.getItem(key(u)) || '[]'); } catch { return []; } };

export function useChats(user) {
  const [chats, setChats] = useState(() => load(user.email));
  const [active, setActive] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { localStorage.setItem(key(user.email), JSON.stringify(chats)); }, [chats, user.email]);
  const upd = (id, fn) => setChats((cs) => cs.map((c) => (c.id === id ? fn(c) : c)));

  async function ask(text, { id = null, habitat } = {}) {
    const cid = id || crypto.randomUUID();
    const hab = chats.find((c) => c.id === cid)?.habitat || habitat;
    if (!id) setChats((cs) => [{ id: cid, title: text.slice(0, 50), habitat: hab, created: Date.now(), messages: [] }, ...cs]);
    setActive(cid);
    upd(cid, (c) => ({ ...c, messages: [...c.messages, { role: 'user', text, ts: Date.now() }] }));
    setBusy(true);
    try {
      const r = await api.ask({ question: text, conversationId: cid, role: user.role, habitat: hab });
      upd(cid, (c) => ({ ...c, messages: [...c.messages, { role: 'assistant', text: r.answer, citations: r.citations || [], followups: r.followups || [], ts: Date.now() }] }));
    } catch {
      upd(cid, (c) => ({ ...c, messages: [...c.messages, { role: 'assistant', text: 'Sorry, I could not reach the data service. Please try again.', error: true, citations: [], ts: Date.now() }] }));
    } finally { setBusy(false); }
  }
  const remove = (id) => { setChats((cs) => cs.filter((c) => c.id !== id)); if (active === id) setActive(null); };
  return { chats, active, setActive, ask, busy, remove };
}
