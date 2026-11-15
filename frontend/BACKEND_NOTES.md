# Frontend <-> FlameAtlas API notes
Used now: GET /habitats, /investigations, /investigation/{id}, /compare, /passage, /fuels, /flammap/{habitat}, /gaps/{habitat}; POST /rank, /ask (also with graph: true), /predict, /whatif, /materials/upload; /materials/report/{name} opened as a link. Not used yet: /retrieve, /graph, /graph/facts.
Base URL: VITE_API_URL (default http://localhost:8000).

Requests to the backend team
1. CORS: allow http://localhost:5173.
2. Auth and accounts (signup, login, role) and conversation history: no endpoints yet; the frontend uses demo accounts and browser storage. Please add them (see DATA_CONTRACT.md section 5-6).
3. /ask: add an optional `audience` ("student" | "researcher" | "engineer") so student answers use simpler language. Optional: `followups` suggestions, and streaming (answers take 10-20 s).
4. /habitats: iss and gateway have lat/lon 0,0 (placeholders). Consider adding an EVA suit habitat (100% O2, 4.3 psi).
5. /rank results lack one_sentence_pitch, years and tags; the frontend joins them from /investigations. Adding them would save a call.
6. Document the allowed range of /rank `priorities` (the UI sends 1 to 3).
7. KPIs (investigation count, highest O2 tested, partial-gravity count) are hardcoded or counted in the frontend. A /stats endpoint would be better.
