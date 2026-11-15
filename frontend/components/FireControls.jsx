import { Card, ErrorState, Skeleton } from '../ui.jsx';

const P = [
  ['flammability', 'Prevention', 'Material selection and flammability limits', 'shield'],
  ['detection', 'Detection', 'Smoke and particle sensing', 'eye'],
  ['suppression', 'Suppression', 'Extinguishing agents and dilution', 'flame'],
];

/** Three separate pillar cards: how many studies score ≥ 50 % on each safety pillar for the habitat. Place inside a .bento. */
export default function FireControls({ rank, onOpen }) {
  const res = rank.data?.results || [];
  return P.map(([k, l, d, icon]) => {
    const hit = res.filter((r) => r.criteria[k].score >= 0.5).sort((a, b) => b.criteria[k].score - a.criteria[k].score);
    return (
      <Card key={k} span={4} title={l} sub={d} icon={icon} className="fire-pillar" interactive stale={rank.loading && !!rank.data}>
        {rank.error && !rank.data ? <ErrorState compact message={rank.error} onRetry={rank.reload} />
          : !rank.data ? <Skeleton lines={2} />
            : (<>
              <div className="row" style={{ alignItems: 'baseline' }}><b className="big gradient-text">{hit.length}</b><span className="muted text-sm">supporting studies</span></div>
              <div className="cluster">{hit.slice(0, 4).map((r) => <button type="button" key={r.id} className="chip" onClick={() => onOpen(r.id)} title={`${r.name}: ${Math.round(r.criteria[k].score * 100)} %`}>{r.acronym}</button>)}
                {!hit.length && <span className="muted text-sm">No study scores 50 % or more here: a gap to raise with the research team.</span>}</div>
            </>)}
      </Card>
    );
  });
}
