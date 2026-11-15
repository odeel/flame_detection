import { local, useApi } from '../api.js';
import { Async, Card, Section, Skeleton } from '../ui.jsx';

/** Student panels: why combustion matters on Earth, NASA spinoffs, cleaner combustion research. */
export default function EarthImpact() {
  const e = useApi(() => local('earth-impact'), []), a = useApi(() => local('acme'), []), f = useApi(() => local('findings'), []);
  const gen = (f.data || []).find((x) => x.key === 'General');
  return (
    <>
      <Section id="earth" eyebrow="Back on Earth" title="Why flames matter at home" desc="Most of the energy we use still comes from burning things. Space research helps make that cleaner and safer.">
        <Async state={e} skeleton={<Skeleton lines={4} />}>
          {(d) => (
            <div className="bento">
              {d.combustion.map((m) => (
                <Card key={m.text} span={6} className="stat-card">
                  <b className="big">{m.value}{m.unit}</b>
                  <p>{m.text}</p>
                  <p className="subtle text-xs">{m.note} · {m.source}</p>
                </Card>))}
              {d.spinoffs.map((s) => (
                <Card key={s.tech} span={4} interactive>
                  <div className="stack-xs"><span className="spin-year">{s.year} · NASA SPINOFF</span><h3>{s.tech}</h3></div>
                  <ul className="spin-list">{s.items.slice(0, 3).map((i) => <li key={i.metric}><span className="muted">{i.metric}</span><b>{i.value} {i.unit}{i.derived && '*'}</b></li>)}</ul>
                  <p className="subtle text-xs">{s.source}{s.items.some((i) => i.derived) && ' · * calculated'}</p>
                </Card>))}
            </div>
          )}
        </Async>
      </Section>
      <Section id="cleaner" eyebrow="Research on the ISS" title="Cleaner, more efficient combustion" desc="ACME experiments burn flames without gravity so scientists can see the chemistry clearly.">
        <Async state={a} skeleton={<Skeleton lines={4} />}>
          {(list) => (
            <div className="tiles">{list.map((x) => (
              <Card key={x.key} interactive title={x.name} icon="flame">
                <p className="text-sm">{x.studies}</p>
                <p className="muted text-sm">{x.link}</p>
              </Card>))}
            </div>
          )}
        </Async>
        {gen && <p className="subtle text-sm">{gen.finding} ({gen.source})</p>}
      </Section>
    </>
  );
}
