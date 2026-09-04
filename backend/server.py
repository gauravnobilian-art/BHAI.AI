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
import requests

from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from emergentintegrations.llm.chat import LlmChat, UserMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jarvis")

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
SUPER_ADMIN = "gauravklegacy@gmail.com"
SESSION_API = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="Jarvis")
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


# --------------------------------------------------------------------------- #
#  Public routes
# --------------------------------------------------------------------------- #

@api_router.get("/")
async def root():
    return {"message": "Jarvis API", "ai": bool(EMERGENT_LLM_KEY)}


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
    import re
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
    import re
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
    await db.apps.insert_one({
        "id": app_id, "user_id": user["user_id"], "idea": idea, "status": "running",
        "plan": "", "files": [], "preview_html": "", "html": "",
        "created_at": datetime.now(timezone.utc)})
    task = asyncio.create_task(_run_build(app_id, user["user_id"], idea))
    _BUILD_TASKS.add(task)
    task.add_done_callback(_BUILD_TASKS.discard)
    return {"id": app_id, "status": "running",
            "agents": ["Architect", "Backend", "Frontend", "DevOps", "Preview"]}


async def _run_build(app_id: str, user_id: str, idea: str):
    try:
        plan = await llm(
            "You are a senior software ARCHITECT. Produce a crisp production spec for a FULL-STACK "
            "app: purpose, features, tech stack (React + FastAPI + MongoDB), data models, and API "
            "endpoints. Be concrete and concise.", f"App idea: {idea}", max_tokens=1500)
        ctx = f"App idea: {idea}\n\nArchitecture spec:\n{plan}"
        backend_sys = ("You are a BACKEND engineer. Write a COMPLETE production FastAPI backend. "
                       "ALWAYS include backend/server.py (FastAPI, routes under /api, Motor/MongoDB, "
                       "Pydantic models, CORS), backend/requirements.txt and backend/.env.example. "
                       "Every backend file under a 'backend/' prefix. Real logic, no TODOs. " + FILE_FMT)
        frontend_sys = ("You are a FRONTEND engineer. Write a COMPLETE React frontend. ALWAYS include "
                        "frontend/src/App.js, frontend/src/api.js (env base URL) and "
                        "frontend/package.json. Every frontend file under a 'frontend/' prefix. "
                        "Real components with state and fetch calls. " + FILE_FMT)
        devops_sys = ("You are a DEVOPS engineer. Produce README.md (overview, setup, run), a root "
                      "docker-compose.yml wiring frontend + backend + mongo, plus backend/Dockerfile "
                      "and frontend/Dockerfile (paths match backend/ and frontend/). " + FILE_FMT)
        preview_sys = ("You are a FRONTEND engineer. Build a COMPLETE self-contained SINGLE-FILE "
                       "working demo as ONE HTML document. Use ONLY vanilla HTML, inline CSS, and "
                       "plain vanilla JavaScript (DOM APIs) with in-memory sample data. ABSOLUTELY "
                       "NO React, JSX, Vue, Angular, or any library that needs a build/transpile "
                       "step; NEVER use <script type='text/babel'>. Small pure-JS CDN utilities are "
                       "fine. Keep it compact so it fits, and ALWAYS finish with </body></html>. "
                       "Return ONLY the HTML from <!DOCTYPE html> to </html>.")
        be, fe, ops, prev = await asyncio.gather(
            llm(backend_sys, ctx, max_tokens=8000),
            llm(frontend_sys, ctx, max_tokens=8000),
            llm(devops_sys, ctx, max_tokens=2500),
            llm(preview_sys, ctx, max_tokens=7000),
            return_exceptions=True)

        def _safe(x):
            return "" if isinstance(x, Exception) else x

        files = _parse_files(_safe(be)) + _parse_files(_safe(fe)) + _parse_files(_safe(ops))
        files = _dedupe_files(files)
        if not any(f["path"].lower().endswith("readme.md") for f in files):
            files.insert(0, {"path": "README.md", "content": f"# {idea}\n\n{plan}\n"})
        files.insert(0, {"path": "ARCHITECTURE.md", "content": plan})
        # ensure a frontend/Dockerfile exists when docker-compose references it
        has_compose = any("docker-compose" in f["path"].lower() for f in files)
        if has_compose and not any(f["path"] == "frontend/Dockerfile" for f in files):
            files.append({"path": "frontend/Dockerfile", "content": DEFAULT_FRONTEND_DOCKERFILE})
        files = _dedupe_files(files)

        # preview: retry if truncated OR if it uses JSX/React without a transpiler (blank iframe)
        prev_raw = _safe(prev)
        if _bad_preview(prev_raw):
            lean_sys = (preview_sys + " CRITICAL: keep it MINIMAL — a single screen with a tiny "
                        "sample dataset — and use VANILLA JavaScript ONLY (no frameworks/JSX) so it "
                        "runs directly in a browser and fits in full, ending with </body></html>.")
            retry = _safe(await llm(lean_sys, ctx + "\n\nKeep the demo very compact, vanilla JS only.",
                                    max_tokens=6000))
            if not _bad_preview(retry):
                prev_raw = retry
        preview_html = _extract_html(prev_raw) or "<!DOCTYPE html><html><body><h1>Preview unavailable</h1></body></html>"
        await db.apps.update_one({"id": app_id}, {"$set": {
            "status": "done", "plan": plan, "files": files,
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
            "plan": doc.get("plan", ""), "files": doc.get("files", []),
            "preview_html": doc.get("preview_html", ""), "error": doc.get("error", "")}


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
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": 'attachment; filename="jarvis-app.zip"'})


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
