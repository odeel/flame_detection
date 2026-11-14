import { useEffect, useRef, useState } from 'react';
import { ROLES } from './roles.js';
import { Corner } from './components.jsx';
import Passage from './components/Passage.jsx';

function Answer({ text, onCite }) {
  return text.split(/(\[S\d+\])/g).map((p, i) => (/^\[S\d+\]$/.test(p) ? <button key={i} className="cite" onClick={() => onCite(p.slice(1, -1))}>{p.slice(1, -1)}</button> : <span key={i}>{p}</span>));
}
export default function ChatPage({ user, chats, onBack, theme, toggle }) {
  const { chats: list, active, setActive, ask, busy, remove } = chats;
  const [text, setText] = useState('');
  const [pick, setPick] = useState(null);
  const [label, setLabel] = useState(null);
  const chat = list.find((c) => c.id === active);
  const end = useRef(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth' }); setPick(null); setLabel(null); }, [chat?.messages.length, active]);
  const lastA = chat ? [...chat.messages.keys()].reverse().find((i) => chat.messages[i].role === 'assistant') : null;
  const shown = chat?.messages[pick ?? lastA];
  const send = () => { const v = text.trim(); if (!v || busy) return; setText(''); ask(v, { id: active, habitat: chat?.habitat }); };

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
          <div className="ctx"><span className="tag">{ROLES[user.role].label}</span>{chat?.habitat && <span className="tag">{chat.habitat.name}</span>}</div>
          {!chat && <p className="mu">Ask a question about NASA’s combustion data to start a discussion. Answers cite their sources.</p>}
          {chat?.messages.map((m, i) => (
            <div key={i} className={'msg ' + m.role + (m.error ? ' err' : '')} onClick={() => m.role === 'assistant' && setPick(i)}>
              <p>{m.role === 'assistant' && !m.error ? <Answer text={m.text} onCite={(l) => { setPick(i); setLabel(l); }} /> : m.text}</p>
              {m.role === 'assistant' && !m.error && (m.answerable === false || m.removed > 0 || m.status) && (
                <p className="mu sm">{m.answerable === false ? 'The indexed data may not fully answer this. ' : ''}{m.removed > 0 ? `${m.removed} statement(s) were removed because the sources did not support them. ` : ''}{m.status ? `Fact-check: ${m.status}.` : ''}</p>)}
            </div>))}
          {busy && <div className="msg assistant mu">Searching the data… this can take 10–20 seconds.</div>}
          <div ref={end} />
          <form className="askbar" onSubmit={(e) => { e.preventDefault(); send(); }}>
            <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask a follow-up or a new question…" aria-label="Your question" />
            <button className="btn amber" type="submit" disabled={busy}>Send</button>
          </form>
        </section>
        <aside className="src" aria-label="Sources">
          <h3>Sources</h3>
          {!shown?.sources?.length && <p className="mu sm">Click an answer to see where it came from.</p>}
          {shown?.sources?.map((s) => (
            <div className={'card' + (s.label === label ? ' hl' : '')} key={s.label}>
              <b>{s.label} · {s.acronym}</b>{s.used && <span className="tag">cited</span>}
              <p className="mu sm">{s.file}</p>
              <Passage chunkId={s.hit || s.chunk_ids?.[0]} />
              {s.url && <a className="sm" href={s.url} target="_blank" rel="noreferrer">PSI record</a>}
            </div>))}
        </aside>
      </div>
    </div>
  );
}
