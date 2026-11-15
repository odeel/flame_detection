import { useEffect, useRef, useState } from 'react';
import { api, useApi } from '../api.js';
import { ErrorState, Skeleton } from '../ui.jsx';

// Modal that shows the exact passage behind a citation. source = { label?, acronym, file, pages?, hit?, chunk_ids?, url? }
export function SourceViewer({ source, onClose }) {
  // Graph-RAG facts arrive with their text and no passage id: show the text instead of calling /passage.
  const inline = source.text && !source.hit;
  const id = inline ? null : source.hit || source.chunk_ids?.[0];
  const p = useApi(() => (id ? api.passage(id) : Promise.resolve(inline ? { text: source.text } : null)), [id, inline]);
  const btn = useRef(null);
  useEffect(() => { btn.current?.focus(); const k = (e) => e.key === 'Escape' && onClose(); addEventListener('keydown', k); return () => removeEventListener('keydown', k); }, [onClose]);
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal card" role="dialog" aria-modal="true" aria-label="Source passage" onClick={(e) => e.stopPropagation()}>
        <header><div><b>{source.label ? `${source.label} · ` : ''}{source.acronym || (source.kind === 'graph' ? 'Knowledge graph facts' : 'Source')}</b><p className="mu sm">{source.file}{source.pages?.length ? ` · page ${source.pages.join(', ')}` : ''}</p></div>
          <button type="button" ref={btn} className="x" onClick={onClose} aria-label="Close">×</button></header>
        {p.loading && !p.data && <Skeleton lines={6} />}
        {p.error && <ErrorState compact message={p.error} onRetry={p.reload} />}
        {p.data && <pre className="passage">{p.data.text}</pre>}
        {!id && !inline && <p className="muted text-sm">No passage is linked to this source.</p>}
        {source.url && <a href={source.url} target="_blank" rel="noreferrer">Open NASA PSI record ↗</a>}
      </div>
    </div>
  );
}
export default function SourceLink({ source, children }) {
  const [on, setOn] = useState(false);
  return <>{<button type="button" className="link text-sm" onClick={() => setOn(true)}>{children}</button>}{on && <SourceViewer source={source} onClose={() => setOn(false)} />}</>;
}
