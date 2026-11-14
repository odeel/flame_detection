import { useEffect, useRef, useState } from 'react';
import { api, useApi } from '../api.js';

// Modal that shows the exact passage behind a citation. source = { label?, acronym, file, pages?, hit?, chunk_ids?, url? }
export function SourceViewer({ source, onClose }) {
  const id = source.hit || source.chunk_ids?.[0];
  const p = useApi(() => api.passage(id), [id]);
  const btn = useRef(null);
  useEffect(() => { btn.current?.focus(); const k = (e) => e.key === 'Escape' && onClose(); addEventListener('keydown', k); return () => removeEventListener('keydown', k); }, [onClose]);
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal card" role="dialog" aria-modal="true" aria-label="Source passage" onClick={(e) => e.stopPropagation()}>
        <header><div><b>{source.label ? `${source.label} · ` : ''}{source.acronym}</b><p className="mu sm">{source.file}{source.pages?.length ? ` · page ${source.pages.join(', ')}` : ''}</p></div>
          <button ref={btn} className="x" onClick={onClose} aria-label="Close">×</button></header>
        {p.loading && <p className="mu">Loading passage…</p>}
        {p.error && <p className="err" role="alert">{p.error}</p>}
        {p.data && <pre className="passage">{p.data.text}</pre>}
        {source.url && <a href={source.url} target="_blank" rel="noreferrer">Open PSI record</a>}
      </div>
    </div>
  );
}
export default function SourceLink({ source, children }) {
  const [on, setOn] = useState(false);
  return <>{<button className="link sm" onClick={() => setOn(true)}>{children}</button>}{on && <SourceViewer source={source} onClose={() => setOn(false)} />}</>;
}
