import { useState } from 'react';
import { api, useApi } from '../api.js';
import { ErrorState, Skeleton } from '../ui.jsx';

function Text({ id }) {
  const p = useApi(() => api.passage(id), [id]);
  if (p.loading && !p.data) return <Skeleton lines={4} />;
  if (p.error) return <ErrorState compact message={p.error} onRetry={p.reload} />;
  return <pre className="passage">{p.data.text}</pre>;
}
export default function Passage({ chunkId }) {
  const [on, setOn] = useState(false);
  if (!chunkId) return null;
  return <div><button className="link sm" onClick={() => setOn(!on)}>{on ? 'Hide passage' : 'View passage'}</button>{on && <Text id={chunkId} />}</div>;
}
