from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import os
import uuid
import logging
import requests

from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from emergentintegrations.llm.chat import LlmChat, UserMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jarvis")

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
ALLOWED_EMAILS = [e.strip().lower() for e in os.environ.get("ALLOWED_EMAILS", "").split(",") if e.strip()]
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
    return user


async def _enforce_owner(email: str) -> None:
    """Only the owner (first login, or an ALLOWED_EMAILS entry) may access."""
    if ALLOWED_EMAILS:
        if email.lower() not in ALLOWED_EMAILS:
            raise HTTPException(status_code=403, detail="Access restricted to the owner.")
        return
    owner = await db.app_settings.find_one({"key": "owner"})
    if owner is None:
        await db.app_settings.insert_one({"key": "owner", "email": email})
    elif owner["email"].lower() != email.lower():
        raise HTTPException(status_code=403, detail="Access restricted to the owner.")


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
    await _enforce_owner(email)

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one({"user_id": user_id},
                                  {"$set": {"name": data.get("name", ""),
                                            "picture": data.get("picture", "")}})
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id, "email": email, "name": data.get("name", ""),
            "picture": data.get("picture", ""), "created_at": datetime.now(timezone.utc)})

    session_token = data["session_token"]
    await db.user_sessions.insert_one({
        "user_id": user_id, "session_token": session_token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc)})

    response.set_cookie("session_token", session_token, httponly=True, secure=True,
                        samesite="none", path="/", max_age=7 * 24 * 3600)
    return {"user_id": user_id, "email": email, "name": data.get("name", ""),
            "picture": data.get("picture", "")}


@api_router.get("/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    return {"user_id": user["user_id"], "email": user["email"],
            "name": user.get("name", ""), "picture": user.get("picture", "")}


@api_router.post("/auth/logout")
async def auth_logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
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
    fence = re.search(r"```(?:html)?\s*(<!DOCTYPE html.*?</html>)\s*```", raw,
                      re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    doc = re.search(r"(<!DOCTYPE html.*?</html>)", raw, re.DOTALL | re.IGNORECASE)
    if doc:
        return doc.group(1).strip()
    return raw.strip()


@api_router.post("/build")
async def build(req: BuildRequest, user: dict = Depends(get_current_user)):
    system = ("You are an elite full-stack engineer. Build a COMPLETE, production-quality, "
              "SELF-CONTAINED single-file web app as ONE HTML document with inline <style> and "
              "<script> (vanilla JS, no build step). It must actually WORK: real interactivity, "
              "sensible sample data, polished modern responsive UI. You MAY use CDN links "
              "(Tailwind CDN, Chart.js, font CDNs). Return ONLY the HTML from <!DOCTYPE html> "
              "to </html>. No commentary.")
    if req.refine and req.current_html:
        user_text = (f"Current app:\n```html\n{req.current_html[:6000]}\n```\n\n"
                     f"Apply this change and return the full updated HTML:\n{req.refine}")
    else:
        user_text = f"App idea: {req.idea}\n\nBuild the full working app now."
    html = _extract_html(await llm(system, user_text, max_tokens=4000))
    doc = {"id": str(uuid.uuid4()), "user_id": user["user_id"], "idea": req.idea,
           "html": html, "created_at": datetime.now(timezone.utc)}
    await db.apps.insert_one(dict(doc))
    return {"html": html, "id": doc["id"]}


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
