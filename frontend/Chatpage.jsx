import { useEffect, useRef, useState } from 'react';
import { ROLES } from './roles.js';
import { Corner } from './components.jsx';
import { SourceViewer } from './components/SourceViewer.jsx';

const turnsOf = (msgs) => { const t = []; msgs.forEach((m) => { if (m.role === 'user') t.push({ q: m }); else if (t.length) t[t.length - 1].a = m; }); return t; };
function Body({ text, onCite }) {
  return text.split(/\n+/).filter(Boolean).map((line, i) => {
    const li = /^\s*[-*•]\s+/.test(line);
    const parts = line.replace(/^\s*[-*•]\s+/, '').split(/(\[S\d+\])/g).map((p, j) => (/^\[S\d+\]$/.test(p) ? <button key={j} className="cite" onClick={() => onCite(p.slice(1, -1))} aria-label={`Open source ${p.slice(1, -1)}`}>{p.slice(2, -1)}</button> : <span key={j}>{p}</span>));
    return <p key={i} className={li ? 'bul' : ''}>{parts}</p>;
  });
}

export default function ChatPage({ user, chats, onBack, theme, toggle }) {
  const { chats: list, active, setActive, ask, busy, remove } = chats;
  const [text, setText] = useState(''), [view, setView] = useState(null);
  const chat = list.find((c) => c.id === active), turns = chat ? turnsOf(chat.messages) : [];
  const last = useRef(null);
  useEffect(() => { last.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, [turns.length, active]);
  const send = (t) => { const v = (t ?? text).trim(); if (!v || busy) return; setText(''); ask(v, { id: active, habitat: chat?.habitat }); };
  const open = (s) => setView(s);

  return (
    <div className="page">
      <Corner theme={theme} toggle={toggle}><button className="link" onClick={onBack}>← Back to dashboard</button></Corner>
      <div className="chat2">
        <aside className="hist" aria-label="Previous questions">
          <button className="btn" onClick={() => setActive(null)}>+ New question</button>
          {list.length === 0 && <p className="mu sm">No questions yet.</p>}
          {list.map((c) => (
            <div key={c.id} className={'hist-item' + (c.id === active ? ' on' : '')}>
              <button onClick={() => setActive(c.id)}><b>{c.title}</b><span className="mu sm">{new Date(c.created).toLocaleDateString()}{c.habitat ? ` · ${c.habitat.name}` : ''}</span></button>
              <button className="x" aria-label={`Delete ${c.title}`} onClick={() => remove(c.id)}>×</button>
            </div>))}
        </aside>
        <section className="convo">
          <div className="scroller">
            {!chat && <div className="welcome"><h1>Ask the combustion data</h1><p className="mu">Every answer cites its sources. Click a source number to read the passage it came from.</p>
              <div className="chips">{ROLES[user.role].queries.map((q) => <button key={q} className="chip" onClick={() => send(q)}>{q}</button>)}</div></div>}
            {turns.map((t, i) => {
              const a = t.a, isLast = i === turns.length - 1, src = a?.sources || [];
              return (
                <article className="turn" key={i} ref={isLast ? last : null}>
                  <header className="q"><span className="qmark">Q</span><div><h2>{t.q.text}</h2>{chat.habitat && <span className="tag">{chat.habitat.name}</span>}</div></header>
                  <div className={'ans card' + (a?.error ? ' bad' : '')} aria-live="polite">
                    {!a && <div className="skel" aria-label="Searching the data"><i /><i /><i /><p className="mu sm">Searching the data… this can take 10–20 seconds.</p></div>}
                    {a && !a.error && <Body text={a.text} onCite={(l) => { const s = src.find((x) => x.label === l); if (s) open(s); }} />}
                    {a?.error && <p>{a.text}</p>}
                    {a && !a.error && (a.answerable === false || a.removed > 0) && <p className="note sm">{a.answerable === false ? 'The indexed data may not fully answer this. ' : ''}{a.removed > 0 ? `${a.removed} statement(s) were removed because the sources did not support them.` : ''}</p>}
                    {src.length > 0 && <div className="srcrow"><span className="mu sm">Sources</span>{src.map((s) => <button key={s.label} className={'srcchip' + (s.used ? ' used' : '')} onClick={() => open(s)} title={s.file}>{s.label} · {s.acronym}{s.pages?.length ? ` · p. ${s.pages[0]}` : ''}</button>)}</div>}
                  </div>
                </article>);
            })}
          </div>
          <form className="composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
            <textarea rows={1} value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }} placeholder="Ask a follow-up or a new question… (Enter to send)" aria-label="Your question" />
            <button className="cta" type="submit" disabled={busy}>{busy ? 'Searching…' : 'Send'}</button>
          </form>
        </section>
      </div>
      {view && <SourceViewer source={view} onClose={() => setView(null)} />}
    </div>
  );
}
