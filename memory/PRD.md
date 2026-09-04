# Jarvis Personal OS — PRD

## Original Problem
Build "Jarvis Personal OS" — a premium, secure daily AI assistant (ChatGPT/Emergent-like) with
Google login, dark neon UI, and 5 workspaces: AI Chat & Rewriter, Email Generator, Smart Web
Research, Image Generator, Project/App Builder. Intended domain: apnabihar.online.

## Architecture (current — deployed on Emergent)
- **Frontend**: React (CRA) at /app/frontend — dark neon "Command Center" with 5 tabs.
- **Backend**: FastAPI at /app/backend/server.py, all routes under /api, port 8001.
- **AI**: Emergent Universal LLM key (EMERGENT_LLM_KEY, model gpt-5.4) via emergentintegrations.
- **Web search**: DuckDuckGo (ddgs). **Images**: Pollinations (free, client-side URL).
- Stateless (no DB currently).

### Pivot note
The app was FIRST built as a standalone Streamlit app (/app/app.py) per the user's initial
request to self-host on apnabihar.online. That file is retained but is NOT what Emergent deploys.
Because Emergent deploys React+FastAPI (not Streamlit), the user saw only the default placeholder,
so Jarvis was rebuilt natively on React+FastAPI to be usable at the emergent.host URL.

## Deploy fix history
- Backend crashed on deploy (`Router.__init__() ... 'on_startup'`): fastapi/starlette mismatch.
  Fixed by pinning fastapi==0.128.3, starlette==0.49.2, uvicorn==0.34.0. Added /health + /api/health.

## Implemented (2026-09-04)
- AI Chat + rewrite presets (Professional / Summarize / Change Tone).
- Email Generator (recipient/tone/context → draft + safe Copy).
- Smart Web Research (DuckDuckGo → cited summary + sources).
- Image Generator (Pollinations, download).
- App Builder (LLM single-file HTML rendered live in a sandboxed iframe, with Refine).
- Robust error states, backend 502 propagation, empty-input validation, mobile-responsive.
- Verified: backend 100%, frontend 100% (test_reports iteration_3).

## Backlog / remaining (P1/P2)
- P1: Google login wall (Emergent-managed OAuth) — currently open access.
- P1: Persist chat history / saved apps in MongoDB.
- P2: Multi-file production export + GitHub/Netlify/Vercel deploy (exist in the Streamlit build).
- P2: Distinguish DuckDuckGo outage from empty results.
- P2: Split App.js tabs into separate component files.

## Test credentials
None (no auth yet). EMERGENT_LLM_KEY in /app/backend/.env.

## Update 2026-06 (d) — Deploy, Save Crew, Restyle presets, per-agent voices
- **Netlify one-click deploy**: `POST /api/apps/{id}/deploy` {netlify_token} zips the demo (index.html)
  and pushes to Netlify (`POST /api/v1/sites`, Content-Type application/zip) → returns live *.netlify.app
  URL (stored as `netlify_url`). UI: "Publish live" panel in preview header (token saved to localStorage).
  Deploys the interactive static demo (full FastAPI+Mongo apps can't run on Netlify).
- **Save My Crew**: `crew_presets` collection + GET/POST/DELETE `/api/crew-presets` (name + models map).
  Team tab UI to save/apply/delete favourite model line-ups.
- **Photo restyle presets**: 6 one-tap chips (Madhubani, Cartoon, Festive Diwali, 3D Pixar, Watercolor,
  Pencil Sketch) in the Photo→Image mode; sets prompt and runs the Nano Banana edit instantly.
- **Per-agent voices**: ChatterFeed assigns each crew member a distinct voice/pitch/rate (hash of name)
  so the Bhojpuri banter sounds like different people.
- Verified via curl (presets CRUD, endpoints wired); user testing UI manually. No testing agent run.
- **Project-themed crew + animation**: `_plan_crew()` (LLM) casts a Bihari crew whose role titles
  match the app domain (banking → Manager Babu, Cashier Bhaiya, Tijori Tufani…) + picks an
  animation `theme` (bank/shop/food/health/school/app) + 6 Bhojpuri banter lines. Stored on the
  app doc; `GET /api/apps/{id}` returns theme/theme_label/banter and themed agent name/title/quip.
- **Dynamic construction animation** `BuildScene.jsx` swaps the building (sign/emblem/accent/stage
  labels) by theme, driven by real build %. Crew now shown as a **horizontal row** below the
  animation; a live **Bhojpuri banter feed** (with optional hi-IN voice) reveals lines as progress
  climbs; an **"Aur koi instruction?"** box appends to the build.
- **Shareable live preview**: public `GET /api/apps/{id}/preview` (no auth, unlisted uuid) serves
  the demo HTML → "Open in new tab" button. Preview agent now renders the MAIN screen (no login
  gate) with realistic non-empty sample data + inline SVG charts.
- **GitHub-ready repo**: zip includes root `index.html` (GitHub Pages entry) + `preview/index.html`
  + always a rich `DOCUMENTATION.md` (what the app does, how to view live, how to run, file tree).
- **Photo → Image** (NEW): `POST /api/image/edit` uses Gemini Nano Banana
  (`gemini-3.1-flash-image-preview`) via Emergent Universal Key to edit an uploaded photo
  (camera or gallery) by prompt. Frontend Image tab has Text→Image (Pollinations) and Photo→Image
  (camera/gallery upload, client-side resize) modes. Verified working via curl.
- Note: verified via curl + manual (user opted to test the UI manually; no testing agent run).
Renamed **Jarvis → Bhai.AI** (Traditional Bihari theme, "Bhaiya" mascot + logo in /frontend/public).
Turned the builder into an Emergent-style full-stack CREATOR:
- **8-agent team** (Architect/Naksi, Database/Khatiyan, Backend/Kariya, Frontend/Chhotu,
  Designer/Rangi, DevOps/Mistry, Preview/Pradarshan, QA/Jaanch). Architect runs first, then
  6 agents in parallel, then QA. `GET /api/models` exposes 6 models (OpenAI gpt-5.4/mini/5.5 +
  Claude sonnet-4-6/haiku-4-5/opus-4-6). `POST /api/build {idea, models:{agentId:modelId}}`.
- **Live per-agent status + progress**: doc stores `agents[]` (queued→working→done + contribution
  + model) and `progress` 0-100 via `_set_agent()`; `GET /api/apps/{id}` returns them for polling.
- **Frontend**: `BuilderProvider` (shared state), `HouseBuild.jsx` (SVG house-construction
  animation, stages Buniyaad→Deewar→Chhat→Sajaawat→Griha Pravesh mapped to build %),
  `AgentPanel.jsx` (agent cards + per-agent model picker) shown BOTH as a live Builder
  side-panel AND a dedicated **Team** tab. Model changes sync across both.
- **Runnable output guard** `_ensure_scaffold()`: always injects requirements.txt, .env.example,
  docker-compose.yml, backend/frontend Dockerfiles, README if agents omit them.
- Verified iteration_8: backend 96% (new pipeline suite 11/11), frontend 100% (rebrand, house
  animation, live 8-agent status, model sync, non-blank preview, zip, team/chat/research/admin).
- Known P2/P3 (open): build latency ~100s isolated / >180s for big ideas or concurrent builds;
  stale 'running' docs not reaped on restart; HUD stats refresh only on mount.
- `POST /api/build` is now an ASYNC background job: inserts an app doc `status:"running"`,
  spawns `asyncio.create_task(_run_build)` (strong ref kept in `_BUILD_TASKS`), and returns
  `{id, status:"running"}` in ~0.1s. Frontend `build()` polls `GET /api/apps/{id}` every 3s
  until `done`/`error`. This removed the 60s ingress **502 timeout** (P0). Verified E2E.
- Preview quality guard: `_bad_preview()` retries the Preview agent when the HTML is truncated
  OR uses React/JSX without Babel. Preview agent prompt now forces VANILLA HTML/CSS/JS only, so
  the live iframe renders (was blank before). Verified: Kanban/todo previews render fully.
- ZIP: global path de-dupe (`_dedupe_files`) + zip-slip sanitisation; `frontend/Dockerfile`
  auto-added when `docker-compose.yml` is present. Backend/frontend agent tokens raised to 8000.
- Remaining minor (P2/P3): occasional backend-agent file truncation; stale "running" docs on
  process restart aren't reaped.
