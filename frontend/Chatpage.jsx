import { useEffect, useRef, useState } from 'react';
import { ROLES } from './roles.js';
import { Corner } from './components.jsx';
import { SourceViewer } from './components/SourceViewer.jsx';
import { Badge, Icon } from './ui.jsx';

const turnsOf = (msgs) => { const t = []; msgs.forEach((m) => { if (m.role === 'user') t.push({ q: m }); else if (t.length) t[t.length - 1].a = m; }); return t; };
function Body({ text, onCite }) {
  return text.split(/\n+/).filter(Boolean).map((line, i) => {
    const li = /^\s*[-*•]\s+/.test(line);
    const parts = line.replace(/^\s*[-*•]\s+/, '').split(/(\[S\d+\])/g).map((p, j) => (/^\[S\d+\]$/.test(p) ? <button key={j} className="cite" onClick={() => onCite(p.slice(1, -1))} aria-label={`Open source ${p.slice(1, -1)}`}>{p.slice(2, -1)}</button> : <span key={j}>{p}</span>));
    return <p key={i} className={li ? 'bul' : ''}>{parts}</p>;
  });
}

export default function ChatPage({ user, chats, onBack, onHome, theme, toggle }) {
  const { chats: list, active, setActive, ask, busy, remove } = chats;
  const [text, setText] = useState(''), [view, setView] = useState(null), [drawer, setDrawer] = useState(false);
  const canGraph = user.role === 'researcher', [graph, setGraph] = useState(false);   // Graph-RAG: researcher only
  const chat = list.find((c) => c.id === active), turns = chat ? turnsOf(chat.messages) : [];
  const last = useRef(null);
  useEffect(() => { last.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, [turns.length, active]);
  const send = (t) => { const v = (t ?? text).trim(); if (!v || busy) return; setText(''); ask(v, { id: active, habitat: chat?.habitat, graph: canGraph && graph }); };
  const open = (s) => setView(s);

  return (
    <div className="page">
      <Corner theme={theme} toggle={toggle} onHome={onHome}><button type="button" className="navbtn" onClick={onBack}>← Back to dashboard</button></Corner>
      <div className="chat2 container">
        {drawer && <div className="hist-scrim" onClick={() => setDrawer(false)} aria-hidden />}
        <aside className={'hist' + (drawer ? ' open' : '')} aria-label="Previous questions" onClick={(e) => e.target.closest('button') && setDrawer(false)}>
          <div className="hist-h"><span className="eyebrow">Your questions</span><span className="subtle text-xs">{list.length}</span></div>
          <button type="button" className="btn" onClick={() => setActive(null)}>+ New question</button>
          {list.length === 0 && <p className="muted text-sm">No questions yet. Ask one to start.</p>}
          {list.map((c) => (
            <div key={c.id} className={'hist-item' + (c.id === active ? ' on' : '')}>
              <button type="button" onClick={() => setActive(c.id)}><b>{c.title}</b><span className="subtle text-xs">{new Date(c.created).toLocaleDateString()}{c.habitat ? ` · ${c.habitat.name}` : ''}</span></button>
              <button type="button" className="x" aria-label={`Delete ${c.title}`} onClick={() => remove(c.id)}>×</button>
            </div>))}
        </aside>
        <section className="convo">
          <button type="button" className="ghost hist-toggle" onClick={() => setDrawer(true)}><Icon name="history" /> History ({list.length})</button>
          <div className="scroller">
            {!chat && <div className="welcome fade-in"><span className="kpi-ic"><Icon name="chat" /></span><h1>Ask the combustion data</h1><p className="muted">Every answer cites its sources. Click a source number to read the passage it came from.</p>
              <div className="chips">{ROLES[user.role].queries.map((q) => <button key={q} className="chip" onClick={() => send(q)}>{q}</button>)}</div></div>}
            {turns.map((t, i) => {
              const a = t.a, isLast = i === turns.length - 1, src = a?.sources || [];
              return (
                <article className="turn" key={i} ref={isLast ? last : null}>
                  <header className="q"><span className="qmark">Q</span><div><h2>{t.q.text}</h2>{chat.habitat && <Badge tone="accent">{chat.habitat.name}</Badge>}</div></header>
                  <div className={'ans card' + (a?.error ? ' bad' : '')} aria-live="polite">
                    {!a && <div className="skel" aria-label="Searching the data"><i /><i /><i /><p className="muted text-sm">Searching the data and checking every sentence… this can take 10–20 seconds.</p></div>}
                    {a && !a.error && <Body text={a.text} onCite={(l) => { const s = src.find((x) => x.label === l); if (s) open(s); }} />}
                    {a?.error && <p>{a.text}</p>}
                    {a && !a.error && (a.status === 'partial' || a.graph) && <div className="cluster">{a.status === 'partial' && <Badge tone="warning">Partial answer</Badge>}{a.graph && <Badge tone="info"><Icon name="graph" /> Knowledge graph{a.graphFacts ? ` · ${a.graphFacts} facts` : ''}</Badge>}</div>}
                    {a && !a.error && (a.answerable === false || a.removed > 0) && <p className="note">{a.answerable === false ? 'The indexed data may not fully answer this. ' : ''}{a.removed > 0 ? `${a.removed} statement(s) were removed because the sources did not support them.` : ''}</p>}
                    {src.length > 0 && <div className="srcrow"><span className="subtle text-xs">Sources</span>{src.map((s) => <button type="button" key={s.label} className={'srcchip' + (s.used ? ' used' : '')} onClick={() => open(s)} title={s.file || 'Knowledge graph facts'}>{s.label} · {s.kind === 'graph' ? 'graph facts' : s.acronym}{s.pages?.length ? ` · p. ${s.pages[0]}` : ''}</button>)}</div>}
                  </div>
                </article>);
            })}
          </div>
          <form className="composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
            <textarea rows={1} value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }} placeholder="Ask a follow-up or a new question… (Enter to send)" aria-label="Your question" />
            {canGraph && <label className="graph-toggle" title="Adds linked facts from the knowledge graph. Best for questions like: which fuels were tested with both CO₂ and helium?"><input type="checkbox" checked={graph} onChange={(e) => setGraph(e.target.checked)} /><Icon name="graph" /><span>Graph</span></label>}
            <button className="cta" type="submit" disabled={busy || !text.trim()}>{busy ? 'Searching…' : <>Send <Icon name="arrowRight" /></>}</button>
          </form>
        </section>
      </div>
      {view && <SourceViewer source={view} onClose={() => setView(null)} />}
    </div>
  );
}
