import { useEffect, useRef, useState } from 'react';
import { ROLES } from './roles.js';
import { Corner } from './components.jsx';

export default function ChatPage({ user, chats, onBack, theme, toggle }) {
  const { chats: list, active, setActive, ask, busy, remove } = chats;
  const [text, setText] = useState('');
  const [pick, setPick] = useState(null);                 // assistant message index shown in Sources
  const chat = list.find((c) => c.id === active);
  const end = useRef(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth' }); setPick(null); }, [chat?.messages.length, active]);
  const lastA = chat ? [...chat.messages.keys()].reverse().find((i) => chat.messages[i].role === 'assistant') : null;
  const shown = chat?.messages[pick ?? lastA];
  const send = (t) => { const v = (t ?? text).trim(); if (!v || busy) return; setText(''); ask(v, { id: active, habitat: chat?.habitat }); };

  return (
    <div className="page">
      <Corner theme={theme} toggle={toggle}><button className="link" onClick={onBack}>← Back to dashboard</button></Corner>
      <div className="chat">
        <aside className="hist" aria-label="Previous questions">
          <button className="btn" onClick={() => setActive(null)}>+ New question</button>
          {list.length === 0 && <p className="mu sm">No questions yet.</p>}
          {list.map((c) => (
            <div key={c.id} className={'hist-item' + (c.id === active ? ' on' : '')}>
              <button onClick={() => setActive(c.id)}><b>{c.title}</b><span className="mu sm">{new Date(c.created).toLocaleDateString()}</span></button>
              <button className="x" aria-label={`Delete ${c.title}`} onClick={() => remove(c.id)}>×</button>
            </div>))}
        </aside>
        <section className="thread" aria-live="polite">
          <div className="ctx"><span className="tag">{ROLES[user.role].label}</span>{chat?.habitat && <span className="tag">{chat.habitat}</span>}</div>
          {!chat && <p className="mu">Ask a question about NASA’s combustion data to start a discussion.</p>}
          {chat?.messages.map((m, i) => (
            <div key={i} className={'msg ' + m.role + (m.error ? ' err' : '')} onClick={() => m.role === 'assistant' && setPick(i)}>
              <p>{m.text}</p>
              {m.followups?.length > 0 && i === lastA && <div className="chips">{m.followups.map((f) => <button key={f} className="chip" onClick={() => send(f)}>{f}</button>)}</div>}
            </div>))}
          {busy && <div className="msg assistant mu">Searching the data…</div>}
          <div ref={end} />
          <form className="askbar" onSubmit={(e) => { e.preventDefault(); send(); }}>
            <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask a follow-up or a new question…" aria-label="Your question" />
            <button className="btn amber" type="submit" disabled={busy}>Send</button>
          </form>
        </section>
        <aside className="src" aria-label="Sources">
          <h3>Sources</h3>
          {!shown?.citations?.length && <p className="mu sm">Sources for an answer appear here. Click an answer to see its sources.</p>}
          {shown?.citations?.map((c, i) => (
            <div className="card" key={i}><b>{c.title}</b><p className="mu sm">{c.snippet}</p>{c.url && <a href={c.url} target="_blank" rel="noreferrer">Open record</a>}</div>))}
        </aside>
      </div>
    </div>
  );
}