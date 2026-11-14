# Data contract: frontend <-> backend/data team
Please reply with SAMPLE JSON files (5-10 records each) for every item below within 24h. Field names below are what the frontend reads; extra fields are fine. Use null, not missing, for unknown values. Units in field names or a `units` object.

## 1. GET /api/investigations
[{ "id":"bass2", "name":"BASS-II", "subtitle":"Solid fuel combustion", "hardware":"MSG", "platform":"MSG",
   "fuelClass":"Solid", "fuelDetail":"cotton-fiberglass, PMMA...", "geometry":"thin sheet",
   "objective":"...", "pillar":["prevention"],           // prevention | detection | suppression | other
   "gravity":"microgravity",                              // microgravity | partial | normal
   "o2Range":[21,30], "pressureRangePsi":[10.2,14.7], "flowRangeCms":[0,50],
   "variables":["O2","flow","thickness"], "sensors":["camera","thermocouple"],
   "extinctionNote":"...", "relevanceTags":["lunar","iss","eva"], "earthApplication":null,
   "doi":"...", "psiUrl":"...", "dataSizeGB":null }]

## 2. GET /api/investigations/:id/tests   (one row per test run: feeds charts and the modeling export)
[{ "testId":"...", "investigationId":"bass2", "o2Pct":21, "pressurePsi":14.7, "flowCms":10, "gravity":"microgravity",
   "fuel":"...", "thicknessMm":0.2, "outcome":"extinguished|steady|quenched|null", "spreadRateMmS":null }]

## 3. GET /api/habitats
[{ "id":"lunar", "name":"Lunar base / rover", "o2Pct":30, "pressurePsi":10.2 }]

## 4. POST /api/chat   (the RAG)
Request:  { "question":"...", "conversationId":"uuid|null", "role":"researcher|engineer|student", "habitat":"Lunar base / rover|null" }
Response: { "conversationId":"uuid", "answer":"plain text or markdown",
            "citations":[{ "investigationId":"cfig","title":"ACME CFI-G","snippet":"...","url":"..." }],
            "followups":["..."], "confidence":"high|medium|low|none" }
Rules: answer ONLY from indexed data; if nothing supports it, return confidence "none" and say so. Student role = simpler language.
Optional later: streaming via Server-Sent Events.

## 5. Conversations (replaces browser localStorage)
GET /api/conversations -> [{id,title,habitat,created}] | GET /api/conversations/:id -> {..., messages:[{role,text,citations,ts}]} | DELETE /api/conversations/:id

## 6. Auth
POST /api/auth/signup {email,password,role} and POST /api/auth/login {email,password,role} -> { token, user:{email,role} }
401 on bad credentials; 403 if the role does not match the account. Role enforced server-side on every endpoint.

## 7. GET /api/kpis?role=researcher
{ "kpis":[["12 TB","Combustion data"],["24","Investigations"]] }   // computed from the real data, not hardcoded

## Also needed
CORS enabled for http://localhost:5173 | JSON error shape { "error":"message" } | stable ids | a data dictionary (what each field means, units) | which investigations have partial-gravity data (we believe none).
