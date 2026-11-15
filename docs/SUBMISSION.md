# NASA Space Apps 2026 submission kit: FlameX (Flame in Freefall)

Deadline: **Sunday, November 15, 2026, 11:59 p.m. local time** (the Team Owner's local time).
Everything here is in English, as the rules require. The previous version of this file is in
`backups/submission-old/SUBMISSION-before-flamex.md`.

---

## 0. Requirements from the official "Project Submission and Judging" video, and our status

| Requirement | Status | What to do |
|---|---|---|
| **Demo**: 7 slides or fewer (including title and intro) **or** a video of 30 seconds or less | To check | Count the slides in the final deck: 7 maximum. Time the video: 30 s maximum. |
| **Demo link is public**: no password, permission or registration | To do | YouTube (public or unlisted), or Google Drive / OneDrive / Dropbox set to "Anyone with the link". Open the link in a private browser window to check. |
| **Final project link is public** and opens for judges without a password or registration | To do | Best: a **public GitHub repository** with this code. If you also share the live dashboard, use the judge link `https://<your-address>/?demo=researcher`: it opens the Researcher dashboard with no password to type. Test it in a private window. |
| **Full URL format**: `https://...` | To do | Paste the whole link, starting with `https://`. |
| **No names, voices or faces of people under 18** in the demo | To check | Check the slides and the video. |
| **Project details** answer the six "Questions to consider" | Done | Section 1 below. |
| **SI use**: say clearly where and how SI was used | Done | `SI-DISCLOSURE.md`, the README, `package.json` metadata, labels in the app, a notice on the PDF covers. Section 1 has the text for the form. |
| **SI images and video**: visible watermark saying they are SI-generated | To check | Any slide or video frame made with an SI tool needs a visible "SI-generated" watermark. The deck made on claude.ai is SI-generated: add the watermark on every slide. |
| **SI audio, code and data**: acknowledged in descriptive text and metadata | Done | Code: README + `SI-DISCLOSURE.md` + `siGenerated` in both `package.json` files. Data: the chat answers and materials screenings are labelled "SI-generated" in the app. A voice-over made with SI must be named in the video description. |
| **SI content may not use, contain or modify NASA branding** | **Risk (team decision)** | The dashboard header draws a NASA-insignia look-alike (`frontend/components.jsx`, `NasaLogo`). The team chose to keep it (15 Nov 2026), accepting the risk. At least keep the NASA logo out of the slides and the video. |
| **NASA data** listed with links | Done | Section 1 and `REFERENCES.md`. |
| Submit with **Submit for Judging** (not only "Save progress") | To do | Before 11:59 p.m. |

---

## 1. Submission fields (ready to paste)

**Project name**
FlameX: SI-Powered Fire Safety Insights from Microgravity Combustion (Flame in Freefall)

**High-level summary**
FlameX turns NASA's microgravity combustion research into fire-safety answers for crews on the ISS, the Lunar Gateway,
the Moon and Mars. It brings the 24 combustion investigations of NASA's Physical Sciences Informatics (PSI) database into
one web dashboard. You can simulate how a flame behaves in each habitat's atmosphere, find the conditions NASA has never
tested, screen cabin materials for fire risk, and ask questions that are answered with citations to the NASA documents.

**Project details**

*What does it do, and how does it work?*
- **Three dashboards, one per role**, built from the same NASA data: Research lab (researchers), Habitat safety (engineers)
  and Learn (students).
- **Habitats**: the ISS, the Lunar Gateway, a Moon base and a Mars base, each with its oxygen level, pressure and gravity.
  Every tool on the page uses the habitat you pick.
- **Flame simulator**: a droplet-flame model trained on the FLEX and CFI droplet tests flown on the ISS. You change oxygen,
  pressure, CO₂, helium and droplet size, and it predicts whether the flame survives and how long it burns, with the
  closest real NASA tests shown next to it. A flammability map shows where flames sustain themselves.
- **Test-gap finder**: compares the conditions NASA has tested with each habitat's atmosphere and shows what has never
  been tested, for example no partial-gravity data sets in PSI.
- **Materials risk screening**: upload a CSV of cabin materials. Each one gets a risk level and the NASA evidence behind
  it (the materials NASA burned in SAFFIRE, BASS and other experiments), a habitat-by-habitat oxygen check, and a report
  you can download as a PDF.
- **Cited answers**: ask a question in plain English. The answer comes from the NASA documents, each sentence cites its
  source, and sentences the sources do not support are removed. Researchers can add facts from a **knowledge graph**
  (442 items and 678 links: investigations, materials, gases, instruments, conditions and findings), drawn as an
  interactive graph.
- **Library**: explore, compare and read all 24 investigations, with a 3D habitat globe and a timeline of fire incidents
  from Apollo 1 onwards.
- **How it is built**: a React dashboard; a FastAPI server; a PostgreSQL 17 database (19 tables, versioned migrations)
  that holds the NASA data, the accounts, the trained models and the saved conversations; and FlameAtlas, our
  retrieval service that searches the NASA documents and builds the answers. Accounts are real: passwords are stored as
  scrypt hashes and email addresses must be verified.

*What benefits does it have?*
- Engineers see in seconds which NASA experiments apply to a cabin at, for example, 34% oxygen and 56.5 kPa, and which
  materials in their list are risky in that air.
- Researchers find the gaps in NASA's tests and get cited, comparable data instead of thousands of raw files.
- Students learn why a flame is round in space, with a simple playground.
- Every answer is traceable to a NASA passage, so users can check it.

*What is the intended impact?*
Safer missions: the Moon and Mars habitats will use more oxygen and lower pressure than the ISS, and NASA has very few
tests in those conditions. FlameX shows the evidence that exists and where new tests are needed. On Earth, the same
findings help fire-safe materials, smoke detection, suppression and firefighter equipment.

*What tools, coding languages, hardware or software did you use?*
JavaScript and React (Vite) for the dashboard; Python 3.13 and FastAPI for the server; PostgreSQL 17 (psycopg 3);
FlameAtlas (Python) for retrieval-augmented answers, the knowledge graph and the materials screening; a large language
model for the written answers; Node.js for the model training scripts; Microsoft Edge (headless) to make the PDFs;
ngrok to connect the team's services.

*How is your project creative?*
It looks at fire safety through each habitat's real atmosphere instead of Earth's air. It checks every SI sentence
against NASA sources and removes the ones that are not supported. It turns a materials list into a cited risk report,
and it shows the knowledge graph as a picture you can explore.

*What factors did your team consider?*
- **Accuracy and honesty**: every answer cites NASA sources; the models show their limits (droplet flames only, gravity
  is not an input).
- **Security**: hashed passwords, verified email, hashed session tokens, rate limits, no secrets in the code.
- **Accessibility**: light and dark themes, keyboard use, readable text sizes, phone layout.
- **Cost**: answers and screenings are cached so a repeated question costs nothing.

**Use of Super Intelligence (SI)** (select the matching options on the form, then paste this)
- **Code**: parts of the code were generated with SI assistance (Claude, by Anthropic, through Claude Code) and reviewed
  and tested by the team. This is stated in the README, in `SI-DISCLOSURE.md` and in the `package.json` metadata.
- **Text and data**: chat answers and materials screenings are generated at run time by a large language model from
  NASA PSI passages. The app labels them "SI-generated" and shows their sources. Some knowledge-graph links were extracted
  by a language model. Our documentation and the two PDFs were drafted with SI assistance and say so on their cover.
- **Images, audio, video**: [fill in: e.g. "No SI-generated images or audio", or "The demo slides were made with SI and
  carry a visible SI-generated watermark".]
- [Confirm before pasting: whether the NASA-style logo in the header was drawn by the team or with an SI tool.]

**NASA data** (Link text, then URL)
- NASA Physical Sciences Informatics (PSI): https://psi.nasa.gov
- PSI combustion investigations (all 24), for example FLEX (PSI-69): https://psi.nasa.gov/physci/repo/data/investigations/PSI-69
- CFI, Cool Flames Investigation (PSI-39): https://psi.nasa.gov/physci/repo/data/investigations/PSI-39
- BASS (PSI-26) and BASS-II (PSI-25): https://psi.nasa.gov/physci/repo/data/investigations/PSI-26
- SAFFIRE (PSI-98 to PSI-100): https://psi.nasa.gov/physci/repo/data/investigations/PSI-99
- SAME (PSI-102): https://psi.nasa.gov/physci/repo/data/investigations/PSI-102
- ACME suite (PSI-10, PSI-20 to PSI-23): https://psi.nasa.gov/physci/repo/data/investigations/PSI-20
The full list, with DOIs, is in `REFERENCES.md`. Check each link opens before pasting.

**Space agency partner data**
JAXA: public descriptions of the FLARE investigation (only if you keep it in the final project).

**References**
Paste the contents of `REFERENCES.md` (code libraries, text and images, including open-source items).

**Links**
- Final project: `https://github.com/<your-team>/<repo>` (public) and, if live, `https://<your-address>/?demo=researcher`
- Demo: `https://...` (YouTube / Drive link, public)

---

## 2. Judging criteria: where each one is answered

| Criterion | Evidence |
|---|---|
| **Impact** | Fire is a top risk for Artemis, Moon and Mars crews. FlameX gives each habitat its own answers, shows the gaps in NASA's tests, and screens real materials lists. |
| **Creativity** | The habitat-atmosphere lens, sentence-level checking of SI answers, the materials-to-NASA-evidence report, the explorable knowledge graph. |
| **Validity** | Models trained on real ISS tests and labelled with their limits; every answer cited; a real database, accounts and automated tests. |
| **Relevance** | All 24 PSI combustion investigations are the core of every page. |
| **Presentation** | A role-based dashboard, the demo deck and the 30-second video below. |

---

## 3. Demo: 7-slide deck (7 slides maximum, including title and intro)

If any slide was made with an SI tool, add a visible "SI-generated" watermark to it. Do not use the NASA logo.

1. **Title.** FlameX: fire safety beyond Earth. Team, Local Event, challenge name.
2. **The problem.** Fire in a spacecraft is lethal (Apollo 1, Mir). Moon and Mars habitats will run with more oxygen and
   lower pressure than the ISS, and NASA has few tests there.
3. **Our solution.** One dashboard on all 24 NASA PSI combustion investigations, with a view for researchers, engineers
   and students.
4. **Simulate and find the gaps.** Screenshot: the flame simulator and the test-gap finder for the Moon base.
5. **Screen materials.** Screenshot: the materials risk results with their NASA evidence and the PDF report.
6. **Ask the data.** Screenshot: a cited answer and the knowledge graph.
7. **Impact and next steps.** Who it helps; next: lunar-gravity data when NASA releases it. Links to the project.

## 4. Demo: 30-second video script (30 seconds maximum; English subtitles if spoken in another language)

| Time | Screen | Voice-over / subtitle |
|---|---|---|
| 0–5 s | Login, then the Moon base habitat | "On the Moon, cabins will have more oxygen and less pressure. How will fire behave?" |
| 5–12 s | Flame simulator and test-gap finder | "FlameX simulates flames with models trained on real ISS tests, and shows what NASA has never tested." |
| 12–19 s | Materials screening and PDF | "Upload your cabin materials and get a fire-risk report backed by NASA experiments." |
| 19–26 s | Chat answer and knowledge graph | "Ask any question: every answer cites NASA's own documents." |
| 26–30 s | Home page | "FlameX: fire safety beyond Earth." |

If the voice-over is SI-generated, say so in the video description.

---

## 5. Final checklist

- [ ] All team members registered on the same Local Event and listed on the Members tab
- [ ] NASA logo kept out of the slides and the video (the header logo was kept by team decision)
- [ ] Repository public, link starts with `https://`, opens in a private browser window
- [ ] Live dashboard (if shared): server and FlameAtlas running during judging; the `?demo=researcher` link opens without a password
- [ ] Demo: 7 slides or 30 s maximum, public link, no people under 18, SI watermark where needed
- [ ] Project details, SI use and NASA data fields filled in (section 1)
- [ ] References field: contents of `REFERENCES.md`
- [ ] Both required checkboxes ticked
- [ ] **Submit for Judging** clicked before 11:59 p.m. local time
