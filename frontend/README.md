# FlameX: frontend

*Exploring combustion beyond Earth.*

A React app for exploring NASA microgravity combustion research (the PSI investigations), simulating how flames behave in habitat atmospheres, and asking a RAG backend (FlameAtlas) cited questions about fire safety in space.


- [Quick start](#quick-start)
- [What the app does](#what-the-app-does)
- [Roles and dashboards](#roles-and-dashboards)
- [The Flame Simulator](#the-flame-simulator)
- [Materials risk screening](#materials-risk-screening)
- [Project structure](#project-structure)
- [How it works](#how-it-works)
- [Backend API used](#backend-api-used)
- [Design system](#design-system)
- [Common tasks](#common-tasks)
- [Known limitations and gotchas](#known-limitations-and-gotchas)

---

## Quick start

Requirements: Node.js 18 or newer.

```bash
cd frontend
npm install
cp .env.example .env    # then set VITE_API_URL if the backend isn't on localhost:8000
npm run dev             # http://localhost:5173
```

Start the backend too, from the FlameAtlas repo root: `python api.py`. It takes about 20 s to be ready. Without it, the app still loads, but data cards show an error with a **Retry** button, and the habitat bar falls back to four built-in habitats.

| Command | What it does |
|---|---|
| `npm run dev` | Vite dev server with hot reload on port 5173 |
| `npm run build` | Production build into `dist/` |

There are no tests, no linter and no TypeScript.

### Demo accounts

Password `space123` for all three:

| Email | Dashboard |
|---|---|
| `researcher@nasa.gov` | Research lab |
| `engineer@nasa.gov` | Habitat safety |
| `student@nasa.gov` | Learn |

Accounts live in memory (`App.jsx`). New sign-ups are lost on reload.

---

## What the app does

1. **Log in or sign up.** The role (researcher, engineer or student) is chosen **once, at sign-up**. Login only asks for email and password, and the account's role decides which dashboard opens.
2. **Role dashboard.** Each role gets its own workspace, built from the same NASA data. See [Roles and dashboards](#roles-and-dashboards).
3. **Ask a question.** The ask bar on every dashboard sends the question to `/ask`. The chat page shows the answer:
   - citations like `[S1]` that open the source passage;
   - a "Partial answer" badge when the sources only partly answer it;
   - a note when the fact-check pass removed unsupported sentences.
   - History is kept per user in `localStorage`.
   - Researchers get a **Graph** toggle in the composer. It sends `graph: true` (Graph-RAG), which adds knowledge-graph facts as one extra source. It is best for questions like "which fuels were tested with both CO₂ and helium?". The answer shows a "Knowledge graph" badge, and the graph source opens its fact text instead of a passage. Engineers and students don't see the toggle.
4. **Go home at any time.** Clicking the NASA logo or the title returns to a fresh home page. That resets tabs, the open investigation and the "View as" preview.
5. **Theme.** Dark or light, saved in `localStorage`. The toggle is in the header.

---

## Roles and dashboards

Roles are configuration, not separate pages. `roles.js` defines, per role:
- its label, icon and workspace name;
- its headline and sample questions;
- whether the habitat bar is shown;
- `sections`: the ordered list of dashboard panels;
- `library`: the tabs of the investigation library.

| | Researcher · Research lab | Engineer · Habitat safety | Student · Learn |
|---|---|---|---|
| Habitat bar | yes | yes | no |
| KPIs | investigations, test rows, highest O₂ tested, partial-gravity datasets | habitat O₂, pressure, gravity, worst-case droplet burn | Earth and history facts |
| Sections | `simulator`, `gaps`, `materials`, `library`, `lessons` | `controls`, `scenario`, `library`, `lessons` | `playground`, `basics`, `earth`, `globe`, `lessons`, `askai` |
| Simulator | full: all controls, intervals, nearest tests, sensitivity | decision view: what-if first, flammability map | Playground: one O₂ slider, plain-language result |
| Can preview | engineer view | researcher view | — |

**What each section shows** (all defined in `sections.jsx`):

| Section id | Content |
|---|---|
| `simulator` | Flame simulator, researcher layout |
| `scenario` | Flame simulator, engineer layout ("What if the cabin atmosphere changes?") |
| `gaps` | Test-gap finder plus the chart of tested conditions vs the habitat |
| `controls` | Three fire-control pillar cards: prevention, detection, suppression |
| `materials` | Materials risk screening: upload a CSV of cabin materials, get a cited risk level per material (researcher only) |
| `library` | Tabbed card: Explorer, Compare, Habitats (3D globe), Partial gravity |
| `lessons` | Historical timeline, from Apollo 1 onwards |
| `playground` | Student flame playground |
| `basics` | Candle on Earth vs round flame in space, plus four facts |
| `earth` | Earth impact: combustion stats, NASA spinoffs, cleaner-combustion research |
| `globe` | ISS globe with partner countries and the orbit |
| `askai` | Call to action that opens the chat |

---

## The Flame Simulator

The simulator lives in `simulator/` and uses the backend's droplet-flame model. The model is trained on FLEX and CFI droplet tests flown on the ISS. All simulator calls are **free** (no LLM); only the two opt-in buttons noted below cost anything.

State is owned by `useSimulator(habitat)` in `simulator/useSimulator.js`:
- **Parameters:** fuel, O₂ %, pressure kPa, CO₂ %, He %, droplet diameter d₀. They start from the selected habitat and reset when the habitat changes.
- **Validation:** O₂ + CO₂ + He must be 100 % or less.
- **Prediction:** `/predict` is called 300 ms after the last slider change (debounced). The previous result stays on screen, dimmed, while the new one loads.
- **Flammability grid:** `/flammap` is fetched only when the habitat or fuel changes.
- **`load(scenario)`:** puts a gap suggestion or a what-if result into the controls.

The cards are separate, and each has its own loading, error and Retry state:

| Card | File | Endpoint |
|---|---|---|
| Conditions (sticky control rail; green bands show the range NASA tested) | `SimControls.jsx` | `/fuels`, `/flammap` |
| Fuel burned · Extinction diameter · Burning rate, each with a 90 % interval meter | `Outcome.jsx` | `/predict` |
| How much to trust this: confidence, in/out of range, warnings | `Outcome.jsx` | `/predict` |
| Flammability map: O₂ × log-pressure heatmap | `FlamMap.jsx` | `/flammap` |
| Oxygen sensitivity: fuel burned vs O₂ at the current pressure, read from the map grid (no extra request) | `FlamMap.jsx` | `/flammap` |
| Nearest NASA tests: test ids open the source passage | `NearestTests.jsx` | `/predict`, `/passage` |
| What-if scenario: habitat baseline vs your sliders | `WhatIf.jsx` | `/whatif` |
| Suggested next tests, with "Simulate" to load one into the controls | `Gaps.jsx` | `/gaps` |
| Student playground | `Playground.jsx` | `/predict` |

**Flammability map details:**
- Click a cell, or use the arrow keys, to move the simulated point there.
- Layers: fuel burned, uncertainty, or distance to tests.
- Hatched cells are far from any NASA test, so their colour isn't trustworthy.
- White dots are real tests (faded if run with a diluent). Stars mark the habitats.

**What-if details:**
- With sliders it is free and instant.
- A typed sentence ("Mars base raises oxygen to 30 %") uses the LLM, about $0.01 for a new sentence.

**Test-gap details:** "Explain" adds an LLM explanation, about $0.005, cached afterwards.

Composition per role is in `simulator/Simulator.jsx` (`mode="researcher"` or `"engineer"`).

## Materials risk screening

Researcher only, in `components/MaterialsAnalyzer.jsx`. It works on a materials dataset against NASA's test evidence, so it sits in the research lab after the test-gap finder. Engineers can open it with "View as Researcher".

1. **Upload.** Drop or browse for a CSV: one material per row, an `id` column, comma, semicolon or tab separated.
   - The browser checks the file first, so nothing is sent (or paid for) when it would be rejected: the extension, 5 MB or less, an `id` column, and 1–200 rows.
   - A template CSV is available to download.
2. **Screen.** `POST /materials/upload` takes about 10–30 s for new rows and about 2 s for cached ones.
3. **Results.**
   - **Summary:** the file name, row count, AI cost, and any duplicate ids.
   - **Risk counts:** tiles for high, medium, low and unknown, plus how many materials were flagged.
   - **Cabin oxygen check:** a materials × habitats table from `loi_by_habitat`. It shows "Self-extinguishes" or "May burn", and the selected habitat's column is highlighted.
   - **Material by material:** expandable rows you can filter by risk and search. Each shows:
     - the risk and confidence;
     - the matched NASA material and how close the match is;
     - contradiction flags;
     - the reasons, with source chips: "your data" for the CSV row, `G` for the knowledge graph, `E1…E4` for passages, which open in the source viewer;
     - what NASA tested;
     - the data that would sharpen the result.
   - **Ignored columns:** the list of dropped columns, each with its reason.
   - **Open full report:** the backend's HTML report with charts.

Errors from the backend (422 bad file, 413 too big, 503 no AI key) show in an error state with Retry.

---

## Project structure

```
frontend/
├─ index.html              page shell, Google Fonts (Space Grotesk, Inter, JetBrains Mono)
├─ main.jsx                React entry
├─ App.jsx                 auth state, theme, demo accounts, Shell (home ⇄ chat, brand → home)
├─ loginpage.jsx           email + password only
├─ signuppage.jsx          role cards + email + password
├─ homepage.jsx            header, hero, ask bar, habitat bar, KPIs, then the role's sections
├─ sections.jsx            PANELS registry: section id → JSX (see "Add a dashboard section")
├─ roles.js                per-role configuration
├─ chatpage.jsx            questions history (drawer on mobile), answers, citations
│                          (git tracks it as Chatpage.jsx: see gotchas)
├─ chatstore.js            useChats(): conversations in localStorage, calls /ask
│                          (git tracks it as Chatstore.js)
├─ api.js                  every backend call + useApi() hook + local() for static JSON
├─ ui.jsx                  shared UI primitives and icons (see "Design system")
├─ components.jsx          NasaLogo, Corner (header), RoleCards, AuthHero
├─ Backdrop.jsx            animated space background (grid, nebula, stars, satellite)
├─ Globe.jsx               canvas d3-geo globe (Earth / Moon / Mars), drag, zoom, click
├─ HabitatGlobe.jsx        globe + habitat info, ISS partners, landing sites, LUCI notes
├─ simulator/              Flame Simulator (see above) + scale.js colour ramps and helpers
├─ components/             dashboard panels
│  ├─ InvestigationExplorer.jsx   filters, priority sliders, ranked list
│  ├─ InvestigationCard.jsx       one ranked investigation, "why this rank"
│  ├─ InvestigationDetail.jsx     summary, findings, test-conditions table, sources
│  ├─ ComparePanel.jsx            side-by-side table for 2–3 pinned investigations
│  ├─ Coverage.jsx                useCoverage() + tested-conditions scatter chart
│  ├─ FireControls.jsx            three safety-pillar cards
│  ├─ MaterialsAnalyzer.jsx       materials CSV upload + risk screening (researcher)
│  ├─ GravityPanel.jsx            partial-gravity facts (NTRS)
│  ├─ EarthImpact.jsx             student Earth sections
│  ├─ FireBasics.jsx              candle vs space-flame illustration + facts
│  ├─ Lessons.jsx                 history timeline
│  ├─ SourceViewer.jsx            modal with the passage behind a citation
│  └─ Passage.jsx                 inline "View passage"
├─ styles/                 the stylesheet, split by layer (see "Design system")
├─ style.css               imports styles/* in order
└─ public/data/*.json      curated static content the backend doesn't serve
```

### Static data (`public/data/`)

Loaded with `local(name)` from `api.js`:

| File | Used by |
|---|---|
| `acme.json` | ACME experiments (Earth impact, investigation detail) |
| `earth-impact.json` | combustion stats and NASA spinoffs |
| `findings.json` | findings reported in NASA publications |
| `gravity.json` | gravity of bodies, test platforms, partial-gravity findings |
| `history.json` | historical timeline |
| `luci.json` | LUCI lunar-gravity flight notes (Moon globe) |

`investigations.json` and `kpis.json` are currently unused.

---

## How it works

- **No router.**
  - `App.jsx` switches between login, signup and the logged-in `Shell` using state.
  - `Shell` switches between the home page and the chat page.
  - Clicking the brand bumps a `homeKey`, which remounts `HomePage` so it starts fresh.
- **Data access.** All backend calls go through `api.js`. Components use the shared hook:

  ```js
  const q = useApi(() => api.rank(body), [deps], { debounce: 0 });
  // q = { data, error, loading, reload }
  ```

  - The previous `data` is kept while a new request runs, so cards can show stale results dimmed instead of flashing empty.
  - `reload()` re-runs the request. It powers every Retry button.
  - `debounce` delays the request, for sliders.
- **Rendering states.** Wrap a `useApi` result in `<Async state={q}>{(data) => …}</Async>`. It renders a skeleton on first load, an `ErrorState` with Retry on failure, an optional `EmptyState`, or your content.
- **Ranking.**
  - The Explorer's priority sliders (Low, Medium, High = 1–3) update a draft. `/rank` fires 400 ms after the last change.
  - The backend ranks with AHP weights and OWA aggregation.
  - A warning shows if the AHP consistency check fails.
  - Rank results lack some fields, so they are joined with `/investigations` on the frontend.
- **Coverage.** `useCoverage()` calls `/compare` in chunks of 6 ids. It builds the O₂ and pressure ranges per investigation, plus the scatter points for the coverage chart.
- **Chat.**
  - `chatstore.js` stores conversations in `localStorage` under `chats:<email>`.
  - It calls `/ask` with `{ question, habitat, k: 5, check: true }`.
  - A new question takes 10–20 s (about $0.015); a cached one takes about 0.5 s.
- **Theme.** `data-theme` on `<html>`; every colour comes from CSS variables that switch with it.

---

## Backend API used

Base URL: `VITE_API_URL` (default `http://localhost:8000`). Full request and response examples are in the backend's `API_EXAMPLES.md`. Current shapes are also in [BACKEND_NOTES.md](BACKEND_NOTES.md).

| Method | Route | Used by | LLM cost |
|---|---|---|---|
| GET | `/habitats` | habitat bar, KPIs, simulator presets | free |
| GET | `/investigations` | explorer, KPIs, coverage | free |
| GET | `/investigation/{id}` | investigation detail | free |
| GET | `/compare?ids=` | compare tab, coverage | free |
| POST | `/rank` | explorer, fire controls | free |
| POST | `/ask` | chat | ~$0.015 new, free cached |
| GET | `/passage?id=` | source viewer | free |
| GET | `/fuels` | simulator, playground | free |
| POST | `/predict` | simulator, playground | free |
| GET | `/flammap/{habitat}?fuel=&n=40` | flammability map, sensitivity, engineer KPI | free |
| GET | `/gaps/{habitat}?n=6&explain=` | test-gap finder | free; ~$0.005 with `explain=true` |
| POST | `/whatif` | what-if card | free with values; ~$0.01 for typed text |
| POST | `/ask` + `graph: true` | chat Graph toggle | like `/ask` |
| POST | `/materials/upload?report=true` | materials screening | ~$0.005 per new row, free cached |
| GET | `/materials/report/{name}` | "Open full report" link (opens in a new tab) | free |

`/retrieve`, `/graph` and `/graph/facts` exist on the backend but aren't called directly yet.

The backend must allow CORS from `http://localhost:5173`. Errors arrive as `{"detail": "…"}` and are shown in the error states. A 503 means no LLM key is configured.

---

## Design system

All styling is plain CSS with variables. There is no CSS framework.

| File | Contains |
|---|---|
| `styles/tokens.css` | **every value**: spacing (4 px scale `--s-1…--s-9`), radius, type scale (`--fs-xs…--fs-display`), fonts, motion (`--ease`, `--dur`), z-index, and semantic colours for dark (default) and `[data-theme=light]`. Old names (`--pr`, `--mu`, `--acc`…) are kept as aliases for `Globe.jsx`. |
| `styles/base.css` | reset, typography, focus ring, scrollbars, reduced-motion rule |
| `styles/layout.css` | `.container`, 12-column `.bento` grid with `.span-3…12`, `.tiles`, stack and cluster utilities, text utilities, section rhythm |
| `styles/background.css` | animated space backdrop |
| `styles/components.css` | buttons, cards, badges, chips, inputs, slider, tabs, segmented control, KPI tiles, meters, states, tables, header, hero, habitat pills, auth pages, modal |
| `styles/dashboard.css` | explorer, investigation cards, globe, timeline, Earth and basics panels |
| `styles/simulator.css` | simulator rail, outcome tiles, heatmap, charts, what-if, gaps, playground |
| `styles/chat.css` | chat layout, history drawer, citations, composer |

**Colour tokens.** Use the semantic names, never hex values, in new CSS:
- surfaces and borders: `--surface-0/1/2/raised`, `--border`, `--border-strong`;
- text: `--text`, `--text-muted`, `--text-subtle`;
- brand: `--primary`, `--accent`, `--accent-2`;
- status: `--success`, `--warning`, `--danger`, `--info`, each with a `-soft` tint.

The heatmap colour ramps are in `simulator/scale.js`.

**Breakpoints:** `sm 480`, `md 768`, `lg 1024`, `xl 1280`.
- Below 768 px, the header actions collapse into a menu and the bento grid becomes one column.
- Below 1024 px, the simulator controls stack on top and can be collapsed.
- Below 900 px, chat history becomes a drawer.

**Shared components in `ui.jsx`:**

| Component | Use |
|---|---|
| `Card` | `title`, `sub`, `icon`, `actions`, `span` (bento columns), `variant="inset" \| "accent"`, `stale`, `interactive` |
| `Section`, `SectionHeader` | dashboard section with eyebrow, title, description |
| `Tabs`, `Segmented` | tab list with animated underline; segmented control |
| `Slider` | label, value readout, unit, filled track, tested-range `band`, habitat `marker`, `log` scale |
| `KpiTile`, `Badge`, `Note` | KPI with icon, status pill, inline note |
| `IntervalMeter`, `Gauge` | mean + 90 % band; circular score |
| `Skeleton`, `EmptyState`, `ErrorState`, `Async` | loading, empty and error states |
| `Icon` | inline SVG icon set (`name="flame"`, `"globe"`, `"chart"`…) |

**Accessibility:**
- Text contrast targets 4.5:1 in both themes.
- Every control is a real `<button>` or `<input>` with a label, and there is a visible `:focus-visible` ring.
- The heatmap is operable with arrow keys.
- Tabs use `role="tablist"`. Modals close on Escape.
- Animation is disabled under `prefers-reduced-motion`.

---

## Common tasks

**Add a dashboard section**
1. Add an entry in `PANELS` in `sections.jsx`. It receives the context `c` built in `homepage.jsx`: habitat, sim, rank, inv, cov, go, and so on.
2. Add its id to the `sections` list of the roles that should see it, in `roles.js`.

**Add a library tab**
1. Add the tab name to `library` in `roles.js`.
2. Add a branch in `Library()` in `sections.jsx`.

**Add a backend call**
1. Add a method to `api` in `api.js`.
2. Use it with `useApi(...)` and render it with `<Async>`.

**Change colours or spacing**
- Edit `styles/tokens.css`.
- For light-mode values, edit the `[data-theme=light]` block.

**Add a role**
1. Add an entry to `ROLES` in `roles.js`, with `label`, `icon`, `workspace`, `blurb`, `headline`, `lead`, `search`, `queries`, `habitats`, `sections` and `library`.
2. Add its KPIs in `homepage.jsx`.
3. Add a demo account in `App.jsx` if needed.

---

## Known limitations and gotchas

- **Fake auth.** Accounts are in memory and conversations are in `localStorage`. The backend has no auth or conversations endpoints yet (see `BACKEND_NOTES.md`).
- **Filename casing.** Git tracks `Chatpage.jsx` and `Chatstore.js`, but imports use `./chatpage.jsx` and `./chatstore.js`. This works on Windows but breaks a build on Linux or macOS CI. Fix with `git mv Chatpage.jsx chatpage.jsx` (same for `Chatstore.js`).
- **`node_modules/` is committed** despite `.gitignore`. Avoid committing further changes there.
- **Model scope.** The prediction model covers droplet flames, trained in microgravity. Gravity is not an input, so Moon and Mars results show O₂ and pressure effects only. The UI says so in its warnings.
- **Hardcoded KPIs.** "0 partial-gravity datasets" and the student facts are static, pending a backend `/stats` endpoint.
- **Assumed atmospheres.** Gateway, Moon and Mars atmospheres are NASA-considered candidates, not confirmed setpoints. The habitat bar shows the backend's note for each.
