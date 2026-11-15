# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

"Flame in Freefall" — a React frontend for exploring NASA microgravity combustion (PSI) investigations and asking a RAG backend ("FlameAtlas") questions about fire safety in space habitats. **The backend is not in this repo**; this repo is the frontend only (in `frontend/`). The root `package.json` is a stray duplicate of a few frontend deps; work in `frontend/`.

## Commands

Run from `frontend/`:

```
npm install
npm run dev      # Vite dev server at http://localhost:5173
npm run build    # production build to dist/
```

There are no tests, linter, or TypeScript. Copy `.env.example` to `.env` and set `VITE_API_URL` (defaults to `http://localhost:8000`). Without the backend, most panels show errors; the homepage falls back to built-in `OFFLINE` habitats.

Demo logins (in-memory, defined in `App.jsx`): `researcher@nasa.gov`, `engineer@nasa.gov`, `student@nasa.gov`, password `space123`.

## Architecture

- **No router.** `App.jsx` switches between login/signup/shell via state; `Shell` switches between `homepage.jsx` and `chatpage.jsx`. Auth is fake (seed users in memory, signups lost on reload). Theme is stored in `localStorage` and applied as `data-theme` on `<html>`; `style.css` holds all styles with CSS variables.
- **Roles drive the UI.** `roles.js` defines per-role (`researcher` / `engineer` / `student`) headlines, sample queries, dashboard tab names (`options`), whether habitats are shown, and `canViewAs` (researcher and engineer can preview each other's view). `homepage.jsx` maps the active tab name to a panel component in `components/` — adding a tab means adding it to `roles.js` *and* the `if/else` chain in `homepage.jsx`.
- **All data access goes through `api.js`.**
  - `api.*` calls the live backend: `/habitats`, `/investigations`, `/investigation/{id}`, `/compare?ids=`, `/rank`, `/ask`, `/retrieve`, `/passage?id=`. `/predict` and `/fuels` exist but are intentionally unused.
  - `local(name)` loads static JSON from `public/data/<name>.json` (acme, earth-impact, findings, gravity, history, luci, ...), used for curated content the backend doesn't serve.
  - `useApi(fn, deps)` is the shared fetch hook returning `{ data, error, loading }`; components use it rather than raw `fetch`.
- **Chat** (`chatstore.js` → `useChats`) persists conversations in `localStorage` keyed by user email and calls `api.ask({ question, habitat, k: 5, check: true })`; responses carry `sources`, `answerable`, `removed_sentences`. `/ask` takes 10–20 s uncached.
- **Ranking**: the Explorer tab calls `api.rank` with a habitat and priority weights (`flammability, detection, suppression, physics, closeness`, UI range 1–3), debounced 400 ms in `homepage.jsx`. Rank results lack some fields and are joined with `/investigations` on the frontend.
- **Globes** (`Globe.jsx`, `HabitatGlobe.jsx`, `Backdrop.jsx`) render with `d3-geo` + `topojson-client` + `world-atlas` as SVG.

## Backend contract docs

- `frontend/BACKEND_NOTES.md` — the API actually used today plus open requests to the backend team (CORS, auth, conversations, `audience` param, `/stats`). Treat it as the source of truth for current endpoints and response shapes (habitats use `o2_pct`, `pressure_kpa`, `gravity_g`).
- `frontend/DATA_CONTRACT.md` — the original desired `/api/...` contract (auth, conversations, KPIs). It does **not** match the current backend; it describes planned features.

## Gotchas

- **Filename casing:** git tracks `Chatpage.jsx` and `Chatstore.js`, but imports use `./chatpage.jsx` / `./chatstore.js`. This works on Windows (case-insensitive) but will break a build on Linux/macOS CI. Use `git mv` if fixing.
- `frontend/node_modules/` is committed to git despite `.gitignore`; avoid adding further changes there.
- KPIs on the homepage are partly hardcoded (e.g. "12 TB", "0 partial-g datasets") pending a backend `/stats` endpoint.
- `frontend/README.md` mentions `modelpage.jsx`; that file does not exist. The "Modeling data" tab is a "coming soon" placeholder.
