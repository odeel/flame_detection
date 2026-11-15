// Panel registry: each id listed in ROLES[role].sections maps to one dashboard section here.
// A panel receives the shared context `c` built in homepage.jsx.
import { Card, ErrorState, Icon, Section, Skeleton, Tabs } from './ui.jsx';
import Simulator from './simulator/Simulator.jsx';
import Gaps from './simulator/Gaps.jsx';
import Playground from './simulator/Playground.jsx';
import HabitatGlobe from './HabitatGlobe.jsx';
import InvestigationExplorer from './components/InvestigationExplorer.jsx';
import InvestigationDetail from './components/InvestigationDetail.jsx';
import ComparePanel from './components/ComparePanel.jsx';
import EarthImpact from './components/EarthImpact.jsx';
import GravityPanel from './components/GravityPanel.jsx';
import FireControls from './components/FireControls.jsx';
import FireBasics from './components/FireBasics.jsx';
import Lessons from './components/Lessons.jsx';
import MaterialsAnalyzer from './components/MaterialsAnalyzer.jsx';
import { CoverageChart } from './components/Coverage.jsx';

function Library(c) {
  const { cfg, lib, setLib, detail, setDetail, habitat } = c;
  let body;
  if (detail) body = <InvestigationDetail id={detail} onBack={() => setDetail(null)} onAsk={c.go} />;
  else if (lib === 'Explorer') body = <InvestigationExplorer habitat={habitat} rank={c.rank} invs={c.inv.data} cov={c.cov} draft={c.draft} setDraft={c.setDraft} pinned={c.pinned} onPin={c.pin} onOpen={setDetail} onAsk={c.go} />;
  else if (lib === 'Compare') body = <ComparePanel ids={c.pinned} onBrowse={() => setLib('Explorer')} />;
  else if (lib === 'Habitats') body = <HabitatGlobe habitat={habitat} onAsk={c.go} />;
  else if (lib === 'Partial gravity') body = <GravityPanel />;
  return (
    <Section id="library" eyebrow="NASA PSI data" title="Investigation library" desc="24 microgravity combustion investigations, ranked for the selected habitat. Pin up to three to compare them.">
      <Card>
        <Tabs label="Library views" value={detail ? null : lib} onChange={(t) => { setLib(t); setDetail(null); }}
          items={cfg.library.map((t) => ({ id: t, label: t === 'Compare' && c.pinned.length ? `Compare (${c.pinned.length})` : t }))} />
        <div className="fade-in" key={detail || lib}>{body}</div>
      </Card>
    </Section>
  );
}

export const PANELS = {
  simulator: (c) => (
    <Section id="simulator" eyebrow="Predictive model" title="Flame simulator"
      desc="A droplet-flame model trained on the FLEX and CFI droplet tests flown on the ISS. Change the conditions and every card below recomputes. Free, no AI calls.">
      <Simulator sim={c.sim} mode="researcher" />
    </Section>
  ),
  scenario: (c) => (
    <Section id="simulator" eyebrow="Scenario planner" title="What if the cabin atmosphere changes?"
      desc={`Start from ${c.habitat.name} and adjust oxygen, pressure or diluent. See the fire-risk change and how the supporting research shifts.`}>
      <Simulator sim={c.sim} mode="engineer" />
    </Section>
  ),
  gaps: (c) => (
    <Section id="gaps" eyebrow="Research planning" title="Where NASA should test next"
      desc="Conditions near the habitat where a new experiment would teach the model the most, next to the conditions already tested.">
      <div className="bento">
        <Gaps habitat={c.habitat} span={7} onLoad={(s) => { c.sim.load(s); document.getElementById('simulator')?.scrollIntoView({ behavior: 'smooth' }); }} />
        <Card span={5} title="Tested conditions vs habitat" icon="chart" sub="Every test row with both O₂ and pressure" stale={c.cov.loading && !!c.cov.map}>
          {c.cov.error ? <ErrorState compact message={c.cov.error} /> : c.cov.map ? <CoverageChart cov={c.cov} habitat={c.habitat} /> : <Skeleton height={240} />}
        </Card>
      </div>
    </Section>
  ),
  controls: (c) => (
    <Section id="controls" eyebrow="Safety pillars" title={`Fire controls for ${c.habitat.name}`}
      desc="How many NASA investigations score 50 % or more on each pillar for this habitat. Click a study to open it.">
      <div className="bento"><FireControls rank={c.rank} onOpen={c.openStudy} /></div>
    </Section>
  ),
  materials: (c) => (
    <Section id="materials" eyebrow="Material analysis" title="Material fire-risk analysis"
      desc="Upload a materials dataset. Each material is matched to what NASA burned in orbit, checked against every habitat’s cabin oxygen, and given a cited risk level with the data still missing.">
      <MaterialsAnalyzer habitat={c.habitat} />
    </Section>
  ),
  library: Library,
  lessons: () => (
    <Section id="lessons" eyebrow="History" title="Historical space lessons">
      <div className="bento"><Lessons /></div>
    </Section>
  ),
  playground: () => (
    <Section id="playground" eyebrow="Try it yourself" title="Flame playground" desc="This uses the same prediction model the researchers use, explained in plain words.">
      <div className="bento"><Playground /></div>
    </Section>
  ),
  basics: () => (
    <Section id="basics" eyebrow="Fire basics" title="Why is a flame round in space?">
      <FireBasics />
    </Section>
  ),
  earth: () => <EarthImpact />,
  globe: (c) => (
    <Section id="globe" eyebrow="Our lab in orbit" title="The International Space Station" desc="Spin the globe. Highlighted countries are ISS partners; the dashed line is the station's orbit.">
      <Card><HabitatGlobe habitat={c.iss} onAsk={c.go} /></Card>
    </Section>
  ),
  askai: (c) => (
    <Section id="askai" eyebrow="Curious?" title="Ask the AI about fire in space">
      <Card variant="accent">
        <div className="row between" style={{ flexWrap: 'wrap' }}>
          <p className="muted" style={{ maxWidth: '60ch' }}>Ask any question. The answer comes from real NASA documents, and every sentence links to the page it came from.</p>
          <button type="button" className="cta" onClick={c.onOpenChats}><Icon name="chat" /> Open my questions</button>
        </div>
      </Card>
    </Section>
  ),
};
