from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal
import os
import io
import uuid
import zipfile
import asyncio
import logging
import json
import re
import requests

from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jarvis")

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
SUPER_ADMIN = "gauravklegacy@gmail.com"
SESSION_API = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="Bhai.AI")
api_router = APIRouter(prefix="/api")


# --------------------------------------------------------------------------- #
#  LLM helper
# --------------------------------------------------------------------------- #

async def llm(system: str, user: str, provider: str = "openai",
              model: str = "gpt-5.4", max_tokens: int = 2000) -> str:
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=503, detail="AI is not configured.")
    try:
        chat = (LlmChat(api_key=EMERGENT_LLM_KEY, session_id=str(uuid.uuid4()),
                        system_message=system)
                .with_model(provider, model).with_params(max_tokens=max_tokens))
        resp = await chat.send_message(UserMessage(text=user))
        return resp if isinstance(resp, str) else str(resp)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("LLM error")
        raise HTTPException(status_code=502, detail=f"AI service error: {exc}")


# --------------------------------------------------------------------------- #
#  Auth
# --------------------------------------------------------------------------- #

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("session_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    sess = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not sess:
        raise HTTPException(status_code=401, detail="Invalid session")
    exp = sess["expires_at"]
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp)
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    user = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    # enforce allow-list on every request so revocation is immediate
    await _enforce_access(user["email"])
    return user


async def _role_for(email: str) -> str:
    if email.lower() == SUPER_ADMIN.lower():
        return "super_admin"
    doc = await db.allowed_users.find_one({"email": email.lower()}, {"_id": 0})
    return doc["role"] if doc else ""


async def _enforce_access(email: str) -> str:
    """Only the super admin or explicitly allowed users may access. Returns role."""
    role = await _role_for(email)
    if not role:
        raise HTTPException(status_code=403, detail="Access restricted. Ask the admin for access.")
    return role


async def require_super_admin(user: dict = Depends(get_current_user)) -> dict:
    if (user.get("email", "").lower() != SUPER_ADMIN.lower()
            and user.get("role") != "super_admin"):
        raise HTTPException(status_code=403, detail="Super admin only.")
    return user


@api_router.post("/auth/session")
async def auth_session(request: Request, response: Response):
    session_id = request.headers.get("X-Session-ID")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing X-Session-ID")
    try:
        r = requests.get(SESSION_API, headers={"X-Session-ID": session_id}, timeout=20)
    except requests.exceptions.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Auth service error: {exc}")
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session id")
    data = r.json()
    email = data["email"]
    role = await _enforce_access(email)

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one({"user_id": user_id},
                                  {"$set": {"name": data.get("name", ""),
                                            "picture": data.get("picture", ""), "role": role}})
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id, "email": email, "name": data.get("name", ""),
            "picture": data.get("picture", ""), "role": role,
            "created_at": datetime.now(timezone.utc)})

    session_token = data["session_token"]
    await db.user_sessions.insert_one({
        "user_id": user_id, "session_token": session_token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc)})

    response.set_cookie("session_token", session_token, httponly=True, secure=True,
                        samesite="none", path="/", max_age=7 * 24 * 3600)
    return {"user_id": user_id, "email": email, "name": data.get("name", ""),
            "picture": data.get("picture", ""), "role": role}


@api_router.get("/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    role = await _role_for(user["email"])
    return {"user_id": user["user_id"], "email": user["email"],
            "name": user.get("name", ""), "picture": user.get("picture", ""),
            "role": role, "is_admin": role == "super_admin"}


@api_router.post("/auth/logout")
async def auth_logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if token:
        await db.user_sessions.delete_many({"session_token": token})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}


# --------------------------------------------------------------------------- #
#  Models
# --------------------------------------------------------------------------- #

class Msg(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Msg]
    style: str = ""


class EmailRequest(BaseModel):
    recipient: str = ""
    context: str
    tone: str = "Polite"


class ResearchRequest(BaseModel):
    query: str


class BuildRequest(BaseModel):
    idea: str
    refine: str = ""
    current_html: str = ""
    models: dict = {}


# --------------------------------------------------------------------------- #
#  Public routes
# --------------------------------------------------------------------------- #

@api_router.get("/")
async def root():
    return {"message": "Bhai.AI API", "ai": bool(EMERGENT_LLM_KEY)}


@app.get("/health")
async def health():
    return {"status": "ok"}


@api_router.get("/health")
async def api_health():
    return {"status": "ok"}


STYLE_PREFIX = {
    "professional": "Rewrite/answer in a clear, professional and polished tone.\n\n",
    "summarize": "Summarize the following into concise bullet points.\n\n",
    "tone": "Rewrite in a warmer, friendly, engaging tone.\n\n",
}


# --------------------------------------------------------------------------- #
#  Core (auth-protected) routes with persistence
# --------------------------------------------------------------------------- #

@api_router.post("/chat")
async def chat(req: ChatRequest, user: dict = Depends(get_current_user)):
    if not req.messages:
        raise HTTPException(status_code=400, detail="No messages provided.")
    transcript = "\n".join(f"{m.role.upper()}: {m.content}" for m in req.messages)
    prefix = STYLE_PREFIX.get(req.style, "")
    user_text = (f"{prefix}Conversation so far:\n{transcript}\n\n"
                 "Reply as the assistant to the latest user message.")
    reply = await llm("You are Jarvis, a sharp, concise and helpful personal assistant.", user_text)
    full = [m.dict() for m in req.messages] + [{"role": "assistant", "content": reply}]
    await db.chats.update_one({"user_id": user["user_id"]},
                              {"$set": {"messages": full,
                                        "updated_at": datetime.now(timezone.utc)}},
                              upsert=True)
    return {"reply": reply}


@api_router.get("/history/chat")
async def get_chat(user: dict = Depends(get_current_user)):
    doc = await db.chats.find_one({"user_id": user["user_id"]}, {"_id": 0})
    return {"messages": doc.get("messages", []) if doc else []}


@api_router.delete("/history/chat")
async def clear_chat(user: dict = Depends(get_current_user)):
    await db.chats.delete_many({"user_id": user["user_id"]})
    return {"ok": True}


@api_router.post("/email")
async def email(req: EmailRequest, user: dict = Depends(get_current_user)):
    user_text = (f"Write a {req.tone.lower()} email to "
                 f"'{req.recipient or 'the recipient'}'. Goal/context: {req.context}")
    draft = await llm("You are an expert email copywriter. Return ONLY the email "
                      "(subject line + body), no commentary.", user_text, max_tokens=1200)
    doc = {"id": str(uuid.uuid4()), "user_id": user["user_id"], "recipient": req.recipient,
           "tone": req.tone, "context": req.context, "draft": draft,
           "created_at": datetime.now(timezone.utc)}
    await db.emails.insert_one(dict(doc))
    return {"draft": draft, "id": doc["id"]}


@api_router.get("/history/emails")
async def get_emails(user: dict = Depends(get_current_user)):
    docs = await db.emails.find({"user_id": user["user_id"]}, {"_id": 0}) \
        .sort("created_at", -1).to_list(50)
    for d in docs:
        d["created_at"] = str(d.get("created_at", ""))
    return {"emails": docs}


@api_router.post("/research")
async def research(req: ResearchRequest, user: dict = Depends(get_current_user)):
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(req.query, max_results=6))
    except Exception:  # noqa: BLE001
        logger.exception("search error")
        results = []
    if not results:
        return {"summary": "No live web results were found. Try rephrasing your question.",
                "sources": []}
    snippets = "\n\n".join(
        f"[{i+1}] {r.get('title','')}\n{r.get('body','')}\nSource: {r.get('href','')}"
        for i, r in enumerate(results))
    summary = await llm(
        "You are a rigorous research analyst. Using ONLY the provided web snippets, write a "
        "factual, well-structured summary. Cite sources as [n]. If sources conflict, say so.",
        f"Question: {req.query}\n\nWeb snippets:\n{snippets}", max_tokens=1600)
    sources = [{"title": r.get("title", ""), "href": r.get("href", "")} for r in results]
    return {"summary": summary, "sources": sources}


def _extract_html(raw: str) -> str:
    txt = raw.strip()
    fence = re.search(r"```(?:html)?\s*(<!DOCTYPE html.*?</html>)\s*```", txt,
                      re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    doc = re.search(r"(<!DOCTYPE html.*?</html>)", txt, re.DOTALL | re.IGNORECASE)
    if doc:
        return doc.group(1).strip()
    # strip a leading/trailing code fence if present
    if txt.startswith("```"):
        txt = re.sub(r"^```[a-zA-Z]*\n", "", txt)
        txt = txt.rsplit("```", 1)[0]
    low = txt.lower()
    start = low.find("<!doctype html")
    if start == -1:
        start = low.find("<html")
    if start > 0:
        txt = txt[start:]
        low = txt.lower()
    # auto-close a truncated document so the preview still renders
    if ("<!doctype html" in low or "<html" in low) and "</html>" not in low:
        if "</body>" not in low:
            txt += "\n</body>"
        txt += "\n</html>"
    return txt.strip()


def _parse_files(raw: str) -> List[dict]:
    files = []
    seen = set()
    for m in re.finditer(r"===\s*(.+?)\s*===\s*```[a-zA-Z0-9.+-]*\n(.*?)```", raw, re.DOTALL):
        path, code = m.group(1).strip(), m.group(2).strip()
        if path and code and path not in seen:
            files.append({"path": path, "content": code}); seen.add(path)
    # tolerate a final UNTERMINATED code block (truncated output): scan from the LAST marker
    markers = list(re.finditer(r"===\s*(.+?)\s*===\s*```[a-zA-Z0-9.+-]*\n", raw))
    if markers:
        last = markers[-1]
        path = last.group(1).strip()
        code = raw[last.end():]
        # only accept if this block was NOT already terminated/captured above
        if path and path not in seen and "```" not in code and code.strip():
            files.append({"path": path, "content": code.strip()})
    return files


def _sanitize_path(path: str) -> str:
    """Prevent zip-slip: strip leading slashes and any '..' traversal segments."""
    parts = [p for p in path.replace("\\", "/").split("/") if p not in ("", ".", "..")]
    return "/".join(parts)


def _dedupe_files(files: List[dict]) -> List[dict]:
    seen, out = set(), []
    for f in files:
        p = _sanitize_path(f.get("path", ""))
        if p and p not in seen:
            f["path"] = p
            out.append(f)
            seen.add(p)
    return out


DEFAULT_FRONTEND_DOCKERFILE = (
    "FROM node:20-alpine\n"
    "WORKDIR /app\n"
    "COPY package.json ./\n"
    "RUN yarn install\n"
    "COPY . .\n"
    "EXPOSE 3000\n"
    'CMD ["yarn", "start"]\n'
)

DEFAULT_BACKEND_DOCKERFILE = (
    "FROM python:3.11-slim\n"
    "WORKDIR /app\n"
    "COPY requirements.txt ./\n"
    "RUN pip install --no-cache-dir -r requirements.txt\n"
    "COPY . .\n"
    "EXPOSE 8001\n"
    'CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]\n'
)

DEFAULT_REQUIREMENTS = (
    "fastapi>=0.110\nuvicorn[standard]>=0.29\nmotor>=3.4\n"
    "pydantic>=2.6\npython-dotenv>=1.0\n"
)

DEFAULT_BACKEND_ENV = "MONGO_URL=mongodb://mongo:27017\nDB_NAME=app_database\n"

DEFAULT_COMPOSE = (
    "version: '3.8'\n"
    "services:\n"
    "  mongo:\n"
    "    image: mongo:7\n"
    "    ports: ['27017:27017']\n"
    "  backend:\n"
    "    build: ./backend\n"
    "    env_file: ./backend/.env\n"
    "    ports: ['8001:8001']\n"
    "    depends_on: [mongo]\n"
    "  frontend:\n"
    "    build: ./frontend\n"
    "    ports: ['3000:3000']\n"
    "    depends_on: [backend]\n"
)


def _ensure_scaffold(files: List[dict], idea: str, plan: str) -> List[dict]:
    """Guarantee a runnable project: inject any essential file the agents omitted."""
    have = {f["path"] for f in files}
    essentials = [
        ("backend/requirements.txt", DEFAULT_REQUIREMENTS),
        ("backend/.env.example", DEFAULT_BACKEND_ENV),
        ("docker-compose.yml", DEFAULT_COMPOSE),
        ("backend/Dockerfile", DEFAULT_BACKEND_DOCKERFILE),
        ("frontend/Dockerfile", DEFAULT_FRONTEND_DOCKERFILE),
    ]
    for path, content in essentials:
        if path not in have:
            files.append({"path": path, "content": content})
    if not any(f["path"].lower().endswith("readme.md") for f in files):
        files.append({"path": "README.md", "content": f"# {idea}\n\n{plan}\n"})
    return _dedupe_files(files)


def _is_truncated_html(raw: str) -> bool:
    return "</html>" not in (raw or "").lower()


def _bad_preview(raw: str) -> bool:
    """A preview is unusable if truncated OR if it uses JSX/React without a transpiler."""
    if _is_truncated_html(raw):
        return True
    low = (raw or "").lower()
    uses_react = ("reactdom" in low) or ("react-dom" in low) or ("createroot" in low)
    has_babel = "babel" in low
    return uses_react and not has_babel


FILE_FMT = ("Output EACH file STRICTLY as:\n=== relative/path/file.ext ===\n"
            "```lang\n<code>\n```\nRepeat for every file. No prose outside the blocks.")

_BUILD_TASKS: set = set()

# ------------------------- Multi-agent team config ------------------------- #
MODELS = [
    {"id": "gpt-5.4", "provider": "openai", "name": "OpenAI GPT-5.4", "badge": "Balanced"},
    {"id": "gpt-5.4-mini", "provider": "openai", "name": "OpenAI GPT-5.4 Mini", "badge": "Fast"},
    {"id": "gpt-5.5", "provider": "openai", "name": "OpenAI GPT-5.5", "badge": "Powerful"},
    {"id": "claude-sonnet-4-6", "provider": "anthropic", "name": "Claude Sonnet 4.6", "badge": "High Precision"},
    {"id": "claude-haiku-4-5-20251001", "provider": "anthropic", "name": "Claude Haiku 4.5", "badge": "Fast"},
    {"id": "claude-opus-4-6", "provider": "anthropic", "name": "Claude Opus 4.6", "badge": "Elite"},
]
MODEL_PROVIDER = {m["id"]: m["provider"] for m in MODELS}
MODEL_IDS = {m["id"] for m in MODELS}

AGENTS_CFG = [
    {"id": "architect", "name": "Naksi Bhai", "role": "Architect", "icon": "Compass",
     "default_model": "gpt-5.4", "desc": "System architecture, stack, API contracts"},
    {"id": "database", "name": "Khatiyan Bhai", "role": "Database", "icon": "Database",
     "default_model": "gpt-5.4", "desc": "Schemas, data models, indexes, seed data"},
    {"id": "backend", "name": "Kariya Bhai", "role": "Backend", "icon": "Server",
     "default_model": "claude-sonnet-4-6", "desc": "FastAPI routes, business logic, auth"},
    {"id": "frontend", "name": "Chhotu Bhai", "role": "Frontend", "icon": "Code2",
     "default_model": "claude-sonnet-4-6", "desc": "React components, state, hooks, fetch"},
    {"id": "designer", "name": "Rangi Bhai", "role": "Designer", "icon": "Palette",
     "default_model": "gpt-5.4", "desc": "Design system, Tailwind theme, styling"},
    {"id": "devops", "name": "Mistry Bhai", "role": "DevOps", "icon": "Terminal",
     "default_model": "claude-sonnet-4-6", "desc": "Docker, compose, env, run scripts"},
    {"id": "preview", "name": "Pradarshan Bhai", "role": "Preview", "icon": "MonitorPlay",
     "default_model": "claude-sonnet-4-6", "desc": "Live single-file interactive preview"},
    {"id": "qa", "name": "Jaanch Bhai", "role": "QA/Tester", "icon": "CheckCircle2",
     "default_model": "gpt-5.4", "desc": "Review, repair, e2e tests, verification"},
]
AGENT_IDS = [a["id"] for a in AGENTS_CFG]


def _resolve_model(models: dict, agent_id: str) -> tuple:
    default = next(a["default_model"] for a in AGENTS_CFG if a["id"] == agent_id)
    mid = models.get(agent_id, default)
    if mid not in MODEL_IDS:
        mid = default
    return MODEL_PROVIDER[mid], mid


async def _set_agent(app_id: str, aid: str, **fields):
    setter = {f"agents.$[a].{k}": v for k, v in fields.items()}
    await db.apps.update_one({"id": app_id}, {"$set": setter}, array_filters=[{"a.id": aid}])
    doc = await db.apps.find_one({"id": app_id}, {"_id": 0, "agents": 1})
    if doc and doc.get("agents"):
        ags = doc["agents"]
        done = sum(1 for a in ags if a.get("status") in ("done", "error"))
        await db.apps.update_one({"id": app_id},
                                 {"$set": {"progress": int(done / len(ags) * 100)}})


class ImageEditRequest(BaseModel):
    image_base64: str
    prompt: str


@api_router.post("/image/edit")
async def image_edit(req: ImageEditRequest, user: dict = Depends(get_current_user)):
    raw = req.image_base64 or ""
    b64 = raw.split(",", 1)[1] if raw.startswith("data:") else raw
    if not b64 or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="A photo and a prompt are both required.")
    try:
        chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=str(uuid.uuid4()),
                       system_message="You are an expert image editor. Edit the given photo.")
        chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(
            modalities=["image", "text"])
        msg = UserMessage(text=req.prompt.strip(), file_contents=[ImageContent(b64)])
        text, images = await chat.send_message_multimodal_response(msg)
        if not images:
            raise HTTPException(status_code=502, detail="No image was returned. Try another prompt.")
        img = images[0]
        return {"image": f"data:{img['mime_type']};base64,{img['data']}", "text": text or ""}
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001
        logger.exception("image edit error")
        raise HTTPException(status_code=502, detail="Image edit failed. Please try again.")


@api_router.get("/models")
async def list_models(_: dict = Depends(get_current_user)):
    return {"models": MODELS, "agents": AGENTS_CFG}


THEME_KEYS = ["bank", "shop", "food", "health", "school", "app"]


def _parse_json(raw: str):
    if not raw:
        return None
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    for candidate in (m.group(0), m.group(0).replace("\n", " ")):
        try:
            return json.loads(candidate)
        except Exception:  # noqa: BLE001
            continue
    return None


async def _plan_crew(idea: str, models: dict):
    """Ask the LLM to cast a fun, project-themed Bihari crew + pick an animation theme."""
    p, m = _resolve_model(models, "architect")
    sys = (
        "You are the FUN cast director of a Bihari-themed app-building studio. Given the app idea, "
        "(1) pick a THEME from exactly: bank, shop, food, health, school, app (use 'app' if none fit); "
        "(2) name an 8-person crew whose ROLE TITLES match the app's real-world domain (e.g. a banking "
        "app -> Manager Babu, Cashier Bhaiya, Clerk, Chaprasi; a food app -> Head Bawarchi, Waiter "
        "Bhaiya). Each crew member maps to a FIXED technical id. Give each a warm Bihari name and one "
        "short, funny Bhojpuri quip. Also write 6 lines of playful Bhojpuri banter between them about "
        "building THIS app. Reply with ONLY strict minified JSON, no markdown, exactly this shape:\n"
        '{"theme":"bank","theme_label":"short Hindi label e.g. Bank Nirman",'
        '"crew":[{"id":"architect","name":"","title":"","quip":""},'
        '{"id":"database","name":"","title":"","quip":""},'
        '{"id":"backend","name":"","title":"","quip":""},'
        '{"id":"frontend","name":"","title":"","quip":""},'
        '{"id":"designer","name":"","title":"","quip":""},'
        '{"id":"devops","name":"","title":"","quip":""},'
        '{"id":"preview","name":"","title":"","quip":""},'
        '{"id":"qa","name":"","title":"","quip":""}],'
        '"banter":[{"from":"","text":""}]}'
    )
    try:
        raw = await llm(sys, f"App idea: {idea}", p, m, max_tokens=1400)
        data = _parse_json(raw)
        if data and isinstance(data.get("crew"), list):
            return data
    except Exception:  # noqa: BLE001
        pass
    return None


def _build_documentation(idea: str, plan: str, files: List[dict]) -> str:
    tree = "\n".join(f"- `{f['path']}`" for f in sorted(files, key=lambda x: x["path"]))
    return f"""# {idea}

> Generated by **Bhai.AI** — Bihar ka apna full-stack builder.

## What is this app?
{plan}

## 🚀 See it live (no coding needed)
1. **Instant demo:** open `index.html` (or `preview/index.html`) in any web browser — the full
   interactive demo runs immediately, no installation required.
2. **Publish free on GitHub Pages:** push this folder to a GitHub repo →
   **Settings → Pages → Source: `main` branch, `/root`** → Save. Your live demo will be online at
   `https://<your-username>.github.io/<repo-name>/`.

## 🛠 Run the full-stack app locally
Requires Docker. From this folder:
```bash
docker compose up --build
```
- Frontend → http://localhost:3000
- Backend API → http://localhost:8001

Manual: copy `backend/.env.example` to `backend/.env`, then
`pip install -r backend/requirements.txt && uvicorn server:app --port 8001`
and `cd frontend && yarn && yarn start`.

## 📁 Project structure
{tree}

## 🧰 Tech stack
React (frontend) · FastAPI (backend) · MongoDB (database) · Docker.

---
Built with ❤️ by the Bhai.AI crew.
"""


@api_router.post("/build")
async def build(req: BuildRequest, user: dict = Depends(get_current_user)):
    # ---- refine path: iterate on the existing live preview ----
    if req.refine and req.current_html:
        html = _extract_html(await llm(
            "You are an elite engineer. Return ONLY the full updated HTML document.",
            f"Current app:\n```html\n{req.current_html[:6000]}\n```\n\n"
            f"Apply this change and return the full HTML:\n{req.refine}", max_tokens=4000))
        return {"plan": "", "files": [], "preview_html": html}

    idea = req.idea
    app_id = str(uuid.uuid4())
    agents = [{
        "id": a["id"], "name": a["name"], "role": a["role"], "icon": a["icon"],
        "desc": a["desc"], "model": _resolve_model(req.models, a["id"])[1],
        "status": "queued", "contribution": "",
    } for a in AGENTS_CFG]
    await db.apps.insert_one({
        "id": app_id, "user_id": user["user_id"], "idea": idea, "status": "running",
        "progress": 0, "agents": agents, "plan": "", "files": [],
        "preview_html": "", "html": "", "created_at": datetime.now(timezone.utc)})
    task = asyncio.create_task(_run_build(app_id, idea, req.models))
    _BUILD_TASKS.add(task)
    task.add_done_callback(_BUILD_TASKS.discard)
    return {"id": app_id, "status": "running", "agents": agents}


async def _run_build(app_id: str, idea: str, models: dict):
    try:
        # ---- Phase 0: cast a fun, project-themed Bihari crew + animation theme ----
        crew = await _plan_crew(idea, models)
        if crew:
            theme = crew.get("theme") if crew.get("theme") in THEME_KEYS else "app"
            await db.apps.update_one({"id": app_id}, {"$set": {
                "theme": theme,
                "theme_label": (crew.get("theme_label") or "")[:40],
                "banter": (crew.get("banter") or [])[:8]}})
            for c in crew.get("crew", []):
                if c.get("id") in AGENT_IDS:
                    await _set_agent(app_id, c["id"],
                                     name=(c.get("name") or "")[:40],
                                     title=(c.get("title") or "")[:44],
                                     quip=(c.get("quip") or "")[:160])

        # ---- Phase 1: Architect (spec everyone else depends on) ----
        await _set_agent(app_id, "architect", status="working")
        ap, am = _resolve_model(models, "architect")
        plan = await llm(
            "You are a senior software ARCHITECT for ENTERPRISE-GRADE apps. Produce a crisp, "
            "concrete production spec for a FULL-STACK app: purpose, key features, tech stack "
            "(React + FastAPI + MongoDB), data models, REST API endpoints, and folder structure. "
            "Be specific and production-minded.", f"App idea: {idea}", ap, am, max_tokens=1800)
        await _set_agent(app_id, "architect", status="done",
                         contribution=f"Architecture spec ({len(plan)} chars)")
        ctx = f"App idea: {idea}\n\nArchitecture spec:\n{plan}"

        async def run_files_agent(aid, system, max_tokens, extra_ctx=""):
            await _set_agent(app_id, aid, status="working")
            p, m = _resolve_model(models, aid)
            try:
                out = await llm(system, ctx + extra_ctx, p, m, max_tokens=max_tokens)
                fs = _parse_files(out)
                await _set_agent(app_id, aid, status="done",
                                 contribution=f"{len(fs)} file(s) generated")
                return fs
            except Exception as exc:  # noqa: BLE001
                await _set_agent(app_id, aid, status="error", contribution=str(exc)[:120])
                return []

        async def run_preview_agent():
            await _set_agent(app_id, "preview", status="working")
            p, m = _resolve_model(models, "preview")
            preview_sys = ("You are a FRONTEND engineer. Build a COMPLETE self-contained SINGLE-FILE "
                           "working demo as ONE HTML document. Use ONLY vanilla HTML, inline CSS, and "
                           "plain vanilla JavaScript (DOM APIs) with in-memory sample data. ABSOLUTELY "
                           "NO React, JSX, Vue, Angular, or any library that needs a build/transpile "
                           "step; NEVER use <script type='text/babel'>. Render the MAIN working screen "
                           "of the app DIRECTLY with realistic, NON-EMPTY sample data — real-looking "
                           "names, amounts, dates and several table/list rows (never all zeros or empty "
                           "states) — and do NOT show a login or sign-in gate as the first screen. Draw "
                           "any charts with inline SVG/CSS (no external chart libs). Make it look polished "
                           "and enterprise-grade. Keep it compact so it fits, and ALWAYS finish with "
                           "</body></html>. Return ONLY the HTML from <!DOCTYPE html> to </html>.")
            try:
                prev_raw = await llm(preview_sys, ctx, p, m, max_tokens=7000)
                if _bad_preview(prev_raw):
                    lean = (preview_sys + " CRITICAL: keep it MINIMAL — a single screen with a tiny "
                            "sample dataset — vanilla JS ONLY, ending with </body></html>.")
                    retry = await llm(lean, ctx + "\n\nKeep the demo very compact, vanilla JS only.",
                                      p, m, max_tokens=6000)
                    if not _bad_preview(retry):
                        prev_raw = retry
                html = _extract_html(prev_raw)
                await _set_agent(app_id, "preview", status="done",
                                 contribution="Interactive live preview ready")
                return html
            except Exception as exc:  # noqa: BLE001
                await _set_agent(app_id, "preview", status="error", contribution=str(exc)[:120])
                return ""

        database_sys = ("You are a DATABASE engineer. Design the persistence layer. Include "
                        "backend/models.py (Pydantic + Mongo document models), backend/db.py (Motor "
                        "client + indexes) and backend/seed.py (sample seed data). Every file under a "
                        "'backend/' prefix. Real, complete code. " + FILE_FMT)
        backend_sys = ("You are a BACKEND engineer. Write a COMPLETE production FastAPI backend. "
                       "ALWAYS include backend/server.py (FastAPI, routes under /api, Motor/MongoDB, "
                       "Pydantic models, CORS, real business logic), backend/requirements.txt and "
                       "backend/.env.example. Every backend file under a 'backend/' prefix. No TODOs. "
                       + FILE_FMT)
        frontend_sys = ("You are a FRONTEND engineer. Write a COMPLETE React frontend. ALWAYS include "
                        "frontend/src/App.js, frontend/src/api.js (env base URL) and "
                        "frontend/package.json. Real components with state, hooks and fetch calls. "
                        "Every frontend file under a 'frontend/' prefix. " + FILE_FMT)
        designer_sys = ("You are a UI/UX DESIGNER-engineer. Produce the design system: "
                        "frontend/src/styles/theme.css (CSS variables, typography, buttons, cards) and "
                        "frontend/tailwind.config.js. Modern, distinctive, accessible. Every file under "
                        "a 'frontend/' prefix. " + FILE_FMT)
        devops_sys = ("You are a DEVOPS engineer. Produce README.md (overview, setup, run), a root "
                      "docker-compose.yml wiring frontend + backend + mongo, plus backend/Dockerfile "
                      "and frontend/Dockerfile (paths match backend/ and frontend/). " + FILE_FMT)

        db_files, be, fe, dz, ops, preview_html = await asyncio.gather(
            run_files_agent("database", database_sys, 4000),
            run_files_agent("backend", backend_sys, 8000),
            run_files_agent("frontend", frontend_sys, 8000),
            run_files_agent("designer", designer_sys, 3500),
            run_files_agent("devops", devops_sys, 2500),
            run_preview_agent())

        files = _dedupe_files(db_files + be + fe + dz + ops)
        files.insert(0, {"path": "ARCHITECTURE.md", "content": plan})
        files = _ensure_scaffold(files, idea, plan)

        # ---- Phase 3: QA reviews the project + writes tests ----
        await _set_agent(app_id, "qa", status="working")
        qp, qm = _resolve_model(models, "qa")
        try:
            manifest = "\n".join(f"- {f['path']}" for f in files)
            qa_out = await llm(
                "You are a QA/TEST engineer. Given the project file manifest and spec, write "
                "backend/tests/test_api.py (pytest, hitting the /api endpoints) and a concise "
                "QA_REPORT.md summarising coverage, risks and a verification checklist. " + FILE_FMT,
                f"{ctx}\n\nGenerated files:\n{manifest}", qp, qm, max_tokens=3000)
            qa_files = _parse_files(qa_out)
            files = _dedupe_files(files + qa_files)
            await _set_agent(app_id, "qa", status="done",
                             contribution=f"{len(qa_files)} test/report file(s)")
        except Exception as exc:  # noqa: BLE001
            await _set_agent(app_id, "qa", status="error", contribution=str(exc)[:120])

        files = _dedupe_files(files + [{"path": "DOCUMENTATION.md",
                                        "content": _build_documentation(idea, plan, files)}])
        preview_html = preview_html or "<!DOCTYPE html><html><body><h1>Preview unavailable</h1></body></html>"
        await db.apps.update_one({"id": app_id}, {"$set": {
            "status": "done", "progress": 100, "plan": plan, "files": files,
            "preview_html": preview_html, "html": preview_html}})
    except Exception as exc:  # noqa: BLE001
        logger.exception("build error")
        await db.apps.update_one({"id": app_id}, {"$set": {"status": "error", "error": str(exc)}})


@api_router.get("/apps/{app_id}")
async def get_app(app_id: str, user: dict = Depends(get_current_user)):
    doc = await db.apps.find_one({"user_id": user["user_id"], "id": app_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="App not found")
    return {"id": doc["id"], "status": doc.get("status", "done"), "idea": doc.get("idea", ""),
            "progress": doc.get("progress", 0), "agents": doc.get("agents", []),
            "theme": doc.get("theme", "app"), "theme_label": doc.get("theme_label", ""),
            "banter": doc.get("banter", []),
            "plan": doc.get("plan", ""), "files": doc.get("files", []),
            "preview_html": doc.get("preview_html", ""), "error": doc.get("error", "")}


@api_router.get("/apps/{app_id}/preview")
async def app_preview(app_id: str):
    """Public, shareable live preview of a generated app (unlisted by uuid)."""
    from fastapi.responses import HTMLResponse
    doc = await db.apps.find_one({"id": app_id}, {"_id": 0, "preview_html": 1})
    html = doc and doc.get("preview_html")
    if not html:
        return HTMLResponse("<h1 style='font-family:sans-serif'>Preview not ready yet…</h1>",
                            status_code=404)
    return HTMLResponse(html)


@api_router.get("/apps/{app_id}/zip")
async def app_zip(app_id: str, user: dict = Depends(get_current_user)):
    from fastapi.responses import StreamingResponse
    doc = await db.apps.find_one({"user_id": user["user_id"], "id": app_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="App not found")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in doc.get("files", []):
            zf.writestr(f["path"], f["content"])
        if doc.get("preview_html"):
            zf.writestr("preview/index.html", doc["preview_html"])
            zf.writestr("index.html", doc["preview_html"])  # GitHub Pages entry
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": 'attachment; filename="bhai-app.zip"'})


class DeployRequest(BaseModel):
    netlify_token: str


@api_router.post("/apps/{app_id}/deploy")
async def deploy_app(app_id: str, body: DeployRequest, user: dict = Depends(get_current_user)):
    doc = await db.apps.find_one({"user_id": user["user_id"], "id": app_id},
                                 {"_id": 0, "preview_html": 1})
    if not doc or not doc.get("preview_html"):
        raise HTTPException(status_code=404, detail="App not found or not ready.")
    token = (body.netlify_token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="A Netlify access token is required.")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.html", doc["preview_html"])
    payload = buf.getvalue()
    try:
        r = await asyncio.to_thread(
            requests.post, "https://api.netlify.com/api/v1/sites",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/zip"},
            data=payload, timeout=90)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="Could not reach Netlify. Try again.")
    if r.status_code in (401, 403):
        raise HTTPException(status_code=400, detail="Netlify rejected the token. Check it and retry.")
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail="Netlify deploy failed. Please try again.")
    data = r.json()
    url = data.get("ssl_url") or data.get("url") or data.get("admin_url")
    await db.apps.update_one({"id": app_id}, {"$set": {"netlify_url": url}})
    return {"url": url}


class CrewPreset(BaseModel):
    name: str
    models: dict


@api_router.get("/crew-presets")
async def list_presets(user: dict = Depends(get_current_user)):
    docs = await db.crew_presets.find({"user_id": user["user_id"]}, {"_id": 0}) \
        .sort("created_at", -1).to_list(50)
    for d in docs:
        d["created_at"] = str(d.get("created_at", ""))
    return {"presets": docs}


@api_router.post("/crew-presets")
async def add_preset(body: CrewPreset, user: dict = Depends(get_current_user)):
    pid = str(uuid.uuid4())
    await db.crew_presets.insert_one({
        "id": pid, "user_id": user["user_id"], "name": (body.name or "My Crew")[:40],
        "models": body.models or {}, "created_at": datetime.now(timezone.utc)})
    return {"id": pid}


@api_router.delete("/crew-presets/{pid}")
async def del_preset(pid: str, user: dict = Depends(get_current_user)):
    await db.crew_presets.delete_many({"user_id": user["user_id"], "id": pid})
    return {"ok": True}


@api_router.get("/history/apps")
async def get_apps(user: dict = Depends(get_current_user)):
    docs = await db.apps.find({"user_id": user["user_id"]}, {"_id": 0}) \
        .sort("created_at", -1).to_list(30)
    for d in docs:
        d["created_at"] = str(d.get("created_at", ""))
    return {"apps": docs}


@api_router.delete("/history/apps/{app_id}")
async def delete_app(app_id: str, user: dict = Depends(get_current_user)):
    await db.apps.delete_many({"user_id": user["user_id"], "id": app_id})
    return {"ok": True}


class AllowedUser(BaseModel):
    email: str
    role: Literal["user", "admin"] = "user"


@api_router.get("/admin/users")
async def admin_list(_: dict = Depends(require_super_admin)):
    docs = await db.allowed_users.find({}, {"_id": 0}).sort("added_at", -1).to_list(200)
    for d in docs:
        d["added_at"] = str(d.get("added_at", ""))
    users = [{"email": SUPER_ADMIN, "role": "super_admin", "added_at": ""}] + \
            [d for d in docs if d["email"].lower() != SUPER_ADMIN.lower()]
    return {"users": users, "super_admin": SUPER_ADMIN}


@api_router.post("/admin/users")
async def admin_add(body: AllowedUser, _: dict = Depends(require_super_admin)):
    email = body.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required.")
    if email == SUPER_ADMIN.lower():
        raise HTTPException(status_code=400, detail="That is already the super admin.")
    await db.allowed_users.update_one(
        {"email": email},
        {"$set": {"email": email, "role": body.role or "user",
                  "added_at": datetime.now(timezone.utc)}}, upsert=True)
    return {"ok": True}


@api_router.delete("/admin/users/{email}")
async def admin_remove(email: str, _: dict = Depends(require_super_admin)):
    if email.strip().lower() == SUPER_ADMIN.lower():
        raise HTTPException(status_code=400, detail="Cannot remove the super admin.")
    em = email.strip().lower()
    await db.allowed_users.delete_many({"email": em})
    # immediate revocation: kill the user's active sessions
    user = await db.users.find_one({"email": em}, {"_id": 0})
    if user:
        await db.user_sessions.delete_many({"user_id": user["user_id"]})
    return {"ok": True}


@api_router.get("/stats")
async def stats(user: dict = Depends(get_current_user)):
    chat = await db.chats.find_one({"user_id": user["user_id"]}, {"_id": 0})
    chat_count = len(chat.get("messages", [])) if chat else 0
    emails = await db.emails.count_documents({"user_id": user["user_id"]})
    apps = await db.apps.count_documents({"user_id": user["user_id"]})
    recent = await db.apps.find({"user_id": user["user_id"]}, {"_id": 0, "id": 1, "idea": 1}) \
        .sort("created_at", -1).to_list(5)
    return {"chat_messages": chat_count, "emails": emails, "apps": apps, "recent_apps": recent}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origin_regex=".*",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown():
    client.close()
