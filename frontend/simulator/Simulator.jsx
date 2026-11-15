import SimControls from './SimControls.jsx';
import { ConfidenceCard, OutcomeTiles } from './Outcome.jsx';
import { FlamMapCard, SensitivityCard } from './FlamMap.jsx';
import NearestTests from './NearestTests.jsx';
import WhatIf from './WhatIf.jsx';

/**
 * Simulator dashboard: a sticky control rail plus separate bento cards.
 * mode="researcher": every model output, uncertainty and the tests behind it.
 * mode="engineer": decision view (outcomes, what-if first, map).
 */
export default function Simulator({ sim, mode = 'researcher' }) {
  const research = mode === 'researcher';
  return (
    <div className="sim">
      <SimControls sim={sim} full={research} />
      <div className="bento">
        {research ? <OutcomeTiles sim={sim} /> : <><OutcomeTiles sim={sim} which={['burned', 'rate']} /><ConfidenceCard sim={sim} span={4} /></>}
        {!research && <WhatIf sim={sim} />}
        <FlamMapCard sim={sim} span={7} />
        {research ? <ConfidenceCard sim={sim} span={5} /> : <SensitivityCard sim={sim} span={5} />}
        {research && <SensitivityCard sim={sim} span={7} />}
        {research && <NearestTests sim={sim} span={5} />}
        {research && <WhatIf sim={sim} />}
      </div>
    </div>
  );
}
