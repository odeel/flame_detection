import { useState } from 'react';
import { api, useApi } from '../api.js';

function Text({ id }) {
  const p = useApi(() => api.passage(id), [id]);
  if (p.loading) return <p className="mu sm">Loading passage…</p>;
  if (p.error) return <p className="err sm">{p.error}</p>;
  return <pre className="passage">{p.data.text}</pre>;
}
export default function Passage({ chunkId }) {
  const [on, setOn] = useState(false);
  if (!chunkId) return null;
  return <div><button className="link sm" onClick={() => setOn(!on)}>{on ? 'Hide passage' : 'View passage'}</button>{on && <Text id={chunkId} />}</div>;
}
