// Color ramps for the flammability map and shared formatting helpers.
// "heat": deep indigo -> violet -> magenta -> orange -> amber -> white-hot (perceptually increasing lightness).
export const RAMPS = {
  heat: ['#140f3a', '#3b1f7a', '#7a2a9a', '#c2357d', '#f0594a', '#ff9a3b', '#ffe08a'],
  cool: ['#0b1236', '#1e3a8a', '#2563eb', '#0ea5e9', '#5eead4', '#e0fbff'],
};

const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
export function ramp(name, t) {
  const s = RAMPS[name], x = Math.max(0, Math.min(1, Number.isFinite(t) ? t : 0)) * (s.length - 1);
  const i = Math.min(s.length - 2, Math.floor(x)), f = x - i, a = hex(s[i]), b = hex(s[i + 1]);
  return `rgb(${a.map((v, k) => Math.round(v + (b[k] - v) * f)).join(',')})`;
}
export const rampCss = (name) => `linear-gradient(90deg, ${RAMPS[name].join(', ')})`;

export const pct = (v, d = 0) => (v == null ? '—' : `${(v * 100).toFixed(d)}`);
export const fix = (v, d = 1) => (v == null || Number.isNaN(v) ? '—' : (+v).toFixed(d));

/** Risk tone for "share of fuel burned" (1 = flame sustains itself = most dangerous). */
export function burnTone(v) {
  if (v == null) return { tone: 'info', label: 'No prediction' };
  if (v >= 0.9) return { tone: 'danger', label: 'Flame sustains itself' };
  if (v >= 0.6) return { tone: 'warning', label: 'Burns most of the fuel' };
  if (v >= 0.3) return { tone: 'info', label: 'Flame struggles' };
  return { tone: 'success', label: 'Flame goes out early' };
}

export const nearestIndex = (arr, v, log) => {
  let best = 0, d = Infinity;
  arr.forEach((a, i) => { const e = log ? Math.abs(Math.log(a) - Math.log(v)) : Math.abs(a - v); if (e < d) { d = e; best = i; } });
  return best;
};
