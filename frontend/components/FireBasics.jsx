import { Card, Icon } from '../ui.jsx';

const FACTS = [
  ['globe', 'No up, no down', 'Without gravity, hot gas does not rise, so the flame becomes a round, blue ball.'],
  ['flame', 'Oxygen arrives slowly', 'The flame only gets oxygen by diffusion, so it burns slower and cooler than a candle on Earth.'],
  ['beaker', 'Perfect for science', 'No flicker means simple, spherical flames that are easier to model (NTRS 20210015913).'],
  ['shield', 'Keeping crews safe', 'NASA studies prevention, detection and suppression so astronauts can live safely with fire risk.'],
];

/** Student "fire basics": an Earth candle vs a space flame, plus four short facts. */
export default function FireBasics() {
  return (
    <div className="bento">
      <Card span={6} title="Same fuel, two worlds" icon="sparkle" sub="Left: a candle on Earth. Right: the same candle in microgravity.">
        <div className="compare-flames">
          <figure className="flame-fig" style={{ margin: 0 }}>
            <svg viewBox="0 0 80 140" role="img" aria-label="Teardrop-shaped yellow candle flame on Earth">
              <defs><radialGradient id="fb-c" cx=".5" cy=".75" r=".7"><stop offset="0" stopColor="#fff7d6" /><stop offset=".35" stopColor="#ffd34d" /><stop offset=".75" stopColor="#ff8a00" /><stop offset="1" stopColor="#ff5f1f" stopOpacity="0" /></radialGradient></defs>
              <path className="candle-flame" d="M40 8 C56 40 62 62 58 78 C55 92 25 92 22 78 C18 62 24 40 40 8Z" fill="url(#fb-c)" />
              <ellipse cx="40" cy="80" rx="6" ry="9" fill="#3b82f6" opacity=".6" />
              <rect x="38.5" y="86" width="3" height="10" fill="#222" />
              <rect x="26" y="96" width="28" height="40" rx="3" fill="#e9e3f5" />
            </svg>
            <b>On Earth</b><span className="muted text-sm">Hot air rises and pulls the flame into a tall teardrop.</span>
          </figure>
          <figure className="flame-fig" style={{ margin: 0 }}>
            <svg viewBox="0 0 80 140" role="img" aria-label="Round blue flame in microgravity">
              <defs><radialGradient id="fb-s"><stop offset="0" stopColor="#ffffff" stopOpacity=".2" /><stop offset=".55" stopColor="#60a5fa" stopOpacity=".55" /><stop offset=".8" stopColor="#2563eb" stopOpacity=".9" /><stop offset="1" stopColor="#1e3a8a" stopOpacity="0" /></radialGradient></defs>
              <circle className="sphere-flame" cx="40" cy="72" r="30" fill="url(#fb-s)" />
              <rect x="38.5" y="70" width="3" height="10" fill="#222" />
              <rect x="26" y="96" width="28" height="40" rx="3" fill="#e9e3f5" />
            </svg>
            <b>In space</b><span className="muted text-sm">No buoyancy: the flame is a dim, round, blue sphere.</span>
          </figure>
        </div>
      </Card>
      <div className="span-6 tiles">
        {FACTS.map(([icon, t, d]) => (
          <Card key={t} interactive>
            <div className="fact"><span className="kpi-ic"><Icon name={icon} /></span><div className="stack-xs"><h4>{t}</h4><p className="muted text-sm">{d}</p></div></div>
          </Card>))}
      </div>
    </div>
  );
}
