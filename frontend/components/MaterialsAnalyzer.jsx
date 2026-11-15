import { useMemo, useRef, useState } from 'react';
import { api } from '../api.js';
import { Badge, Card, EmptyState, ErrorState, Icon, KpiTile, Note, Segmented, Skeleton, cx } from '../ui.jsx';
import { SourceViewer } from './SourceViewer.jsx';

// Researcher tool: upload a materials CSV, get a cited fire-risk screening per material (POST /materials/upload).
const MAX_ROWS = 200, MAX_BYTES = 5 * 1024 * 1024;
const RISK = { high: ['danger', 'High risk'], medium: ['warning', 'Medium risk'], low: ['success', 'Low risk'], unknown: [null, 'Unknown'] };
const MATCH = { same: 'same material', similar: 'similar material', none: 'no NASA match' };
// Template built from the two rows shown in the backend's API examples (Nomex, PMMA).
const TEMPLATE = 'id,material,category,thickness_mm,LOI_pct,nasa_std_6001_test1\nM-001,Nomex III fabric,textile,0.4,29,pass\nM-002,PMMA sheet (acrylic),polymer,2.0,17.3,fail\n';

/** Reads the header and row count in the browser, so obvious problems are caught before any paid call. */
async function inspect(file) {
  if (!/\.(csv|tsv|txt)$/i.test(file.name)) return { error: 'Choose a .csv, .tsv or .txt file.' };
  if (file.size > MAX_BYTES) return { error: `The file is ${(file.size / 1048576).toFixed(1)} MB; the limit is 5 MB.` };
  const lines = (await file.text()).split(/\r?\n/).filter((l) => l.trim());
  if (!lines.length) return { error: 'The file is empty.' };
  const head = lines[0], delim = [',', ';', '\t'].sort((a, b) => head.split(b).length - head.split(a).length)[0];
  const cols = head.split(delim).map((c) => c.trim().replace(/^"|"$/g, ''));
  if (!cols.some((c) => c.toLowerCase() === 'id')) return { error: 'The first row must include an “id” column (one material per row).', cols };
  const rows = lines.length - 1;
  if (!rows) return { error: 'The file has a header but no material rows.', cols };
  if (rows > MAX_ROWS) return { error: `${rows} rows found; the limit is ${MAX_ROWS}. Split the file.`, cols };
  return { cols, rows, delim: delim === '\t' ? 'tab' : delim };
}

const habStatus = (s = '') => (/extinguish/i.test(s) ? ['success', 'Self-extinguishes'] : /burn/i.test(s) ? ['danger', 'May burn'] : [null, s || '—']);

export default function MaterialsAnalyzer({ habitat }) {
  const input = useRef(null);
  const [file, setFile] = useState(null), [info, setInfo] = useState(null), [drag, setDrag] = useState(false);
  const [run, setRun] = useState({ status: 'idle' });   // idle | loading | done | error
  const pick = async (f) => { if (!f) return; setFile(f); setRun({ status: 'idle' }); setInfo({ checking: true }); setInfo(await inspect(f)); };
  const analyze = async () => {
    setRun({ status: 'loading' });
    try { setRun({ status: 'done', data: await api.materialsUpload(file, true) }); } catch (e) { setRun({ status: 'error', error: e.message }); }
  };
  const reset = () => { setFile(null); setInfo(null); setRun({ status: 'idle' }); if (input.current) input.current.value = ''; };
  const template = useMemo(() => URL.createObjectURL(new Blob([TEMPLATE], { type: 'text/csv' })), []);

  return (
    <div className="stack-lg">
      <div className="bento">
        <Card span={7} title="Upload a materials dataset" icon="upload" sub="One material per row. Any properties you have: LOI, NASA-STD-6001 result, thickness, density…">
          <label
            className={cx('dropzone', drag && 'on', info?.error && 'bad', file && !info?.error && 'ok')}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files?.[0]); }}>
            <input ref={input} type="file" accept=".csv,.tsv,.txt,text/csv" className="sr-only" onChange={(e) => pick(e.target.files?.[0])} />
            <span className="state-ic"><Icon name={file ? 'file' : 'upload'} /></span>
            {file ? <b>{file.name}</b> : <b>Drop a CSV here or <u>browse</u></b>}
            <span className="muted text-sm">{file ? `${(file.size / 1024).toFixed(1)} KB` : 'Comma, semicolon or tab separated · up to 200 rows · 5 MB'}</span>
          </label>
          {info?.error && <p className="field-err" role="alert"><Icon name="alert" />{info.error}</p>}
          {info?.rows && (
            <div className="cluster text-sm fade-in">
              <Badge tone="success">{info.rows} material{info.rows > 1 ? 's' : ''}</Badge>
              <Badge plain>{info.cols.length} columns · {info.delim} separated</Badge>
              <span className="subtle text-xs">{info.cols.slice(0, 6).join(' · ')}{info.cols.length > 6 ? ' …' : ''}</span>
            </div>
          )}
          <div className="row between" style={{ flexWrap: 'wrap' }}>
            <a className="btn-quiet btn-sm" href={template} download="materials_template.csv"><Icon name="download" /> Template CSV</a>
            <div className="cluster">
              {file && <button type="button" className="link text-sm" onClick={reset}>Clear</button>}
              <button type="button" className="cta" disabled={!info?.rows || run.status === 'loading'} onClick={analyze}>
                <Icon name="shield" /> {run.status === 'loading' ? 'Screening…' : 'Screen materials'}
              </button>
            </div>
          </div>
        </Card>
        <Card span={5} title="How the screening works" icon="info" variant="inset">
          <ol className="stack-sm text-sm" style={{ paddingLeft: '1.2em' }}>
            <li>Columns with no fire-safety value are dropped, each with a reason.</li>
            <li>Each material is matched to materials NASA burned (SAFFIRE, BASS…), using the knowledge graph and the PSI passages.</li>
            <li>Its oxygen index (LOI) is checked against every habitat’s cabin oxygen.</li>
            <li>You get a risk level, confidence, cited reasons and what data is missing.</li>
          </ol>
          <p className="subtle text-xs">Uses the AI model: about $0.005 and 10–30 s per new material; materials already screened are free and take about 2 s. A screening is a decision aid, not a certification.</p>
        </Card>
      </div>

      {run.status === 'loading' && <Card><Skeleton lines={6} /><p className="muted text-sm">Matching each material to NASA tests and checking it against the four cabin atmospheres…</p></Card>}
      {run.status === 'error' && <ErrorState message={run.error} onRetry={analyze} />}
      {run.status === 'done' && <Results r={run.data} habitat={habitat} />}
    </div>
  );
}

export function Results({ r, habitat }) {
  const [risk, setRisk] = useState('all'), [q, setQ] = useState(''), [view, setView] = useState(null);
  const s = r.summary || {}, report = api.absolute(r.report_url);
  const habs = r.results.find((m) => m.loi_by_habitat?.length)?.loi_by_habitat.map((h) => ({ id: h.habitat_id, name: h.habitat, o2: h.o2_pct })) || [];
  const rows = useMemo(() => r.results.filter((m) => (risk === 'all' || m.risk_level === risk)
    && `${m.id} ${m.material || ''} ${m.material_class || ''} ${m.matched_nasa_material || ''}`.toLowerCase().includes(q.toLowerCase())), [r, risk, q]);

  return (
    <div className="stack-lg fade-in">
      <div className="row between" style={{ flexWrap: 'wrap' }}>
        <div className="cluster text-sm">
          <Badge plain><Icon name="file" /> {r.file}</Badge>
          <Badge plain>{r.n_rows} materials</Badge>
          <Badge plain>{r.new_llm_calls ? `${r.new_llm_calls} new AI calls · $${(r.cost_usd || 0).toFixed(3)}` : 'all cached · $0'}</Badge>
          {r.duplicate_ids?.length > 0 && <Badge tone="warning">duplicate ids: {r.duplicate_ids.join(', ')}</Badge>}
        </div>
        {report && <a className="btn" href={report} target="_blank" rel="noreferrer"><Icon name="external" /> Open full report</a>}
      </div>

      <div className="kpis">
        <KpiTile icon="alert" tone="danger" value={s.high ?? 0} label="high risk" note="review these first" />
        <KpiTile icon="flame" tone="warning" value={s.medium ?? 0} label="medium risk" note="check against your habitat" />
        <KpiTile icon="check" tone="success" value={s.low ?? 0} label="low risk" note="lower concern" />
        <KpiTile icon="search" value={(s.unknown ?? 0) + (r.flagged?.length ? ` · ${r.flagged.length} flagged` : '')} label="unknown" note="not enough data to judge" />
      </div>

      {habs.length > 0 && (
        <Card title="Cabin oxygen check" icon="globe" sub="Each material’s oxygen index (LOI) against each habitat’s cabin oxygen. Below the cabin O₂, a material can keep burning.">
          <div className="tbl" style={{ maxHeight: 420 }}>
            <table className="matrix">
              <thead><tr><th>Material</th><th className="num">LOI %</th>{habs.map((h) => <th key={h.id} className={h.id === habitat?.id ? 'cur' : ''}>{h.name.replace('International Space Station', 'ISS')}<br /><span className="subtle">{h.o2} % O₂</span></th>)}</tr></thead>
              <tbody>{r.results.map((m) => (
                <tr key={m.id}>
                  <td><b>{m.id}</b> <span className="muted">{m.material}</span></td>
                  <td className="num">{m.loi_pct ?? '—'}</td>
                  {habs.map((h) => { const st = m.loi_by_habitat?.find((x) => x.habitat_id === h.id), [tone, label] = habStatus(st?.status); return <td key={h.id} className={h.id === habitat?.id ? 'cur' : ''}>{st ? <Badge tone={tone}>{label}</Badge> : <span className="subtle">no LOI</span>}</td>; })}
                </tr>))}
              </tbody>
            </table>
          </div>
          <p className="subtle text-xs">The highlighted column is the habitat selected above. This is a simple rule (LOI vs cabin O₂); the risk level below also weighs NASA test evidence.</p>
        </Card>
      )}

      <Card title="Material by material" icon="layers" sub="Open a material to see why it got its level and which NASA sources back it."
        actions={<div className="cluster">
          <Segmented label="Risk filter" value={risk} onChange={setRisk} options={['all', 'high', 'medium', 'low', 'unknown'].map((k) => ({ value: k, label: k === 'all' ? `All ${r.results.length}` : `${RISK[k][1].replace(' risk', '')} ${s[k] ?? 0}` }))} />
        </div>}>
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by id, name, class or NASA match…" aria-label="Search materials" />
        {!rows.length && <EmptyState compact title="No materials match" hint="Change the risk filter or the search." />}
        <div className="mat-list">
          {rows.map((m) => <Material key={m.id} m={m} onSource={setView} />)}
        </div>
      </Card>

      {r.columns_dropped?.length > 0 && (
        <details className="prio"><summary>{r.columns_dropped.length} column{r.columns_dropped.length > 1 ? 's' : ''} ignored</summary>
          <ul className="text-sm" style={{ marginTop: 8 }}>{r.columns_dropped.map((c) => <li key={c.column}><b>{c.column}</b> <span className="muted">· {c.reason}</span></li>)}</ul>
        </details>
      )}
      {view && <SourceViewer source={view} onClose={() => setView(null)} />}
    </div>
  );
}

function Material({ m, onSource }) {
  const [tone, label] = RISK[m.risk_level] || RISK.unknown;
  const src = Object.fromEntries((m.sources || []).map((x) => [x.label, x]));
  const open = (l) => { const x = src[l]; if (x) onSource({ label: l, acronym: x.acronym || (x.kind === 'graph' ? 'Knowledge graph' : x.investigation_id), file: x.file || (x.investigation_ids || []).join(', '), pages: x.pages, hit: x.chunk_id, chunk_ids: x.chunk_ids, url: x.url }); };
  return (
    <details className={cx('mat', `mat--${m.risk_level}`)}>
      <summary>
        <Badge tone={tone}>{label}</Badge>
        <span className="mat-name"><b>{m.id}</b> {m.material}<span className="subtle text-xs">{m.material_class}</span></span>
        <span className="cluster text-xs">
          {m.matched_nasa_material ? <Badge plain tone="primary">NASA: {m.matched_nasa_material} · {MATCH[m.match_quality] || m.match_quality}</Badge> : <Badge plain>{MATCH.none}</Badge>}
          <Badge plain>{m.confidence} confidence</Badge>
          {m.flags?.length > 0 && <Badge tone="warning">check data</Badge>}
        </span>
      </summary>
      <div className="mat-body">
        {m.flags?.map((f) => <Note key={f}>{f}</Note>)}
        <div className="stack-sm">
          <h4>Why</h4>
          <ul className="reasons">{m.reasons?.map((x, i) => (
            <li key={i}><span>{x.text}</span> {x.sources?.map((l) => (l === 'row'
              ? <span key={l} className="srcchip" title="From your CSV row">your data</span>
              : <button type="button" key={l} className="srcchip used" onClick={() => open(l)} title={src[l]?.file || 'Open source'}>{l}{src[l]?.acronym ? ` · ${src[l].acronym}` : l === 'G' ? ' · graph' : ''}</button>))}</li>))}
          </ul>
        </div>
        {m.nasa_relevance && <div className="stack-xs"><h4>What NASA tested</h4><p className="text-sm muted">{m.nasa_relevance}</p></div>}
        {m.missing_data?.length > 0 && <div className="stack-xs"><h4>Data that would sharpen this</h4><ul className="text-sm muted">{m.missing_data.map((d) => <li key={d}>{d}</li>)}</ul></div>}
      </div>
    </details>
  );
}
