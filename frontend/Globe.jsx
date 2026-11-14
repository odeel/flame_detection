import { useEffect, useRef } from 'react';
import { geoOrthographic, geoPath, geoGraticule10, geoContains, geoDistance, geoCircle } from 'd3-geo';
import { feature, mesh } from 'topojson-client';
import world from 'world-atlas/countries-110m.json';

// Same technique as TrendScope: canvas + d3-geo orthographic projection, drag to rotate, click to select.
const countries = feature(world, world.objects.countries).features;
const borders = mesh(world, world.objects.countries, (a, b) => a !== b);
const grat = geoGraticule10();
const ORBIT = geoCircle().center([20, 38.4]).radius(90)();          // 51.6° inclination great circle
const rnd = (i, k) => { const v = Math.sin(i * k) * 43758.5453; return v - Math.floor(v); };
const CRATERS = Array.from({ length: 45 }, (_, i) => geoCircle().center([rnd(i, 12.9) * 360 - 180, rnd(i, 78.2) * 160 - 80]).radius(1 + rnd(i, 39.3) * 6)());
const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

/** props: body 'earth'|'moon'|'mars', highlight Map(countryName -> any), pins [{id,name,ll:[lon,lat]}],
 *  selected (country name or pin id), onSelect(key), orbit (draw ISS orbit) */
export default function Globe({ body = 'earth', highlight = new Map(), pins = [], selected, onSelect, orbit = false }) {
  const cv = useRef(null);
  const live = useRef({});
  live.current = { body, highlight, pins, selected, onSelect, orbit };

  useEffect(() => {
    const c = cv.current, ctx = c.getContext('2d'), dpr = Math.min(2, devicePixelRatio || 1);
    const proj = geoOrthographic().clipAngle(90), path = geoPath(proj, ctx);
    const s = { rot: [-10, -20, 0], k: 1, drag: null, moved: false, hover: null };
    const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
    let W = 0, H = 0, R = 0, raf;
    const size = () => { const r = c.parentElement.getBoundingClientRect(); W = r.width; H = r.height; c.width = W * dpr; c.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); R = Math.min(W, H) * 0.42; };
    const hit = (x, y) => {
      const { pins, body } = live.current;
      for (const p of pins) { if (geoDistance(p.ll, [-s.rot[0], -s.rot[1]]) > Math.PI / 2) continue; const [px, py] = proj(p.ll); if (Math.hypot(px - x, py - y) < 11) return { pin: p.id }; }
      if (body === 'earth' && Math.hypot(x - W / 2, y - H / 2) <= proj.scale()) { const ll = proj.invert([x, y]); const f = ll && countries.find((f) => geoContains(f, ll)); if (f) return { country: f.properties.name }; }
      return null;
    };
    const frame = () => {
      const { body, highlight, pins, selected, orbit } = live.current;
      if (!s.drag && !still) s.rot[0] += 0.12;
      proj.translate([W / 2, H / 2]).scale(R * s.k).rotate(s.rot); ctx.clearRect(0, 0, W, H);
      const pr = css('--pr'), acc = css('--acc'), line = css('--line'), bg = css('--bg'), bg2 = css('--bg2'), tx = css('--tx');
      const g = ctx.createRadialGradient(W / 2 - R * 0.35, H / 2 - R * 0.4, R * 0.1, W / 2, H / 2, R * 1.05);
      if (body === 'earth') { g.addColorStop(0, bg2); g.addColorStop(1, bg); } else if (body === 'mars') { g.addColorStop(0, '#e8a27c'); g.addColorStop(1, '#5e2a18'); } else { g.addColorStop(0, '#cfcfd8'); g.addColorStop(1, '#4b4b5a'); }
      ctx.beginPath(); path({ type: 'Sphere' }); ctx.fillStyle = g; ctx.fill();
      if (body === 'earth') {
        ctx.globalAlpha = 0.4; ctx.beginPath(); path(grat); ctx.strokeStyle = line; ctx.lineWidth = 0.6; ctx.stroke();
        for (const f of countries) {
          const n = f.properties.name, on = highlight.has(n), sel = n === selected, hov = n === s.hover;
          ctx.globalAlpha = on || sel || hov ? 1 : 0.55; ctx.beginPath(); path(f);
          ctx.fillStyle = sel ? acc : on ? pr : hov ? tx : line; ctx.fill();
        }
        ctx.globalAlpha = 1; ctx.beginPath(); path(borders); ctx.strokeStyle = bg; ctx.lineWidth = 0.5; ctx.stroke();
        if (orbit) { ctx.beginPath(); path(ORBIT); ctx.setLineDash([5, 5]); ctx.strokeStyle = acc; ctx.lineWidth = 1.4; ctx.stroke(); ctx.setLineDash([]); }
      } else { for (const cr of CRATERS) { ctx.beginPath(); path(cr); ctx.fillStyle = 'rgba(0,0,0,.18)'; ctx.fill(); } }
      for (const p of pins) {
        if (geoDistance(p.ll, [-s.rot[0], -s.rot[1]]) > Math.PI / 2) continue; const [x, y] = proj(p.ll), on = p.id === selected;
        ctx.beginPath(); ctx.arc(x, y, on ? 8 : 6, 0, 7); ctx.fillStyle = on ? acc : pr; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = '#fff'; ctx.stroke();
        ctx.font = '600 11px Inter, sans-serif'; ctx.fillStyle = body !== 'earth' ? '#fff' : tx; ctx.fillText(p.name, x + 10, y - 8);
      }
      raf = requestAnimationFrame(frame);
    };
    const pos = (e) => { const r = c.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    const down = (e) => { c.setPointerCapture(e.pointerId); s.drag = { x: e.clientX, y: e.clientY }; s.moved = false; };
    const move = (e) => {
      if (s.drag) { const dx = e.clientX - s.drag.x, dy = e.clientY - s.drag.y; if (Math.abs(dx) + Math.abs(dy) > 2) s.moved = true; s.rot[0] += dx * 0.4; s.rot[1] = Math.max(-80, Math.min(80, s.rot[1] - dy * 0.4)); s.drag = { x: e.clientX, y: e.clientY }; }
      else { const h = hit(...pos(e)); s.hover = h?.country || null; c.style.cursor = h ? 'pointer' : 'grab'; }
    };
    const up = (e) => { if (s.drag && !s.moved) { const h = hit(...pos(e)); if (h) live.current.onSelect?.(h.pin || h.country); } s.drag = null; };
    const wheel = (e) => { e.preventDefault(); s.k = Math.max(0.7, Math.min(2, s.k * (e.deltaY < 0 ? 1.08 : 0.92))); };
    const key = (e) => { const d = { ArrowLeft: [-8, 0], ArrowRight: [8, 0], ArrowUp: [0, 8], ArrowDown: [0, -8] }[e.key]; if (d) { e.preventDefault(); s.rot[0] += d[0]; s.rot[1] = Math.max(-80, Math.min(80, s.rot[1] + d[1])); } };
    const ro = new ResizeObserver(size); ro.observe(c.parentElement); size();
    c.addEventListener('pointerdown', down); c.addEventListener('pointermove', move); c.addEventListener('pointerup', up); c.addEventListener('wheel', wheel, { passive: false }); c.addEventListener('keydown', key);
    raf = requestAnimationFrame(frame);
    return () => { cancelAnimationFrame(raf); ro.disconnect(); c.removeEventListener('pointerdown', down); c.removeEventListener('pointermove', move); c.removeEventListener('pointerup', up); c.removeEventListener('wheel', wheel); c.removeEventListener('keydown', key); };
  }, []);

  return <canvas ref={cv} tabIndex={0} aria-label={body === 'earth' ? 'Interactive Earth globe. Drag to rotate, click a country, arrow keys also rotate.' : `Interactive ${body}. Drag to rotate, click a marker.`} />;
}
