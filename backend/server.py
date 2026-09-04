from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path
from typing import List
import os
import uuid
import logging

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from emergentintegrations.llm.chat import LlmChat, UserMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jarvis")

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")

app = FastAPI(title="Jarvis Personal OS")
api_router = APIRouter(prefix="/api")


# --------------------------------------------------------------------------- #
#  LLM helper (Emergent Universal Key)
# --------------------------------------------------------------------------- #

async def llm(system: str, user: str, provider: str = "openai",
              model: str = "gpt-5.4", max_tokens: int = 2000) -> str:
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=503, detail="AI is not configured (missing key).")
    try:
        chat = (LlmChat(api_key=EMERGENT_LLM_KEY, session_id=str(uuid.uuid4()),
                        system_message=system)
                .with_model(provider, model)
                .with_params(max_tokens=max_tokens))
        resp = await chat.send_message(UserMessage(text=user))
        return resp if isinstance(resp, str) else str(resp)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("LLM error")
        raise HTTPException(status_code=502, detail=f"AI service error: {exc}")


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
#  Routes
# --------------------------------------------------------------------------- #

@api_router.get("/")
async def root():
    return {"message": "Jarvis Personal OS API", "ai": bool(EMERGENT_LLM_KEY)}


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


@api_router.post("/chat")
async def chat(req: ChatRequest):
    if not req.messages:
        raise HTTPException(status_code=400, detail="No messages provided.")
    transcript = "\n".join(f"{m.role.upper()}: {m.content}" for m in req.messages)
    prefix = STYLE_PREFIX.get(req.style, "")
    user = (f"{prefix}Conversation so far:\n{transcript}\n\n"
            "Reply as the assistant to the latest user message.")
    reply = await llm("You are Jarvis, a sharp, concise and helpful personal assistant.",
                      user)
    return {"reply": reply}


@api_router.post("/email")
async def email(req: EmailRequest):
    user = (f"Write a {req.tone.lower()} email to "
            f"'{req.recipient or 'the recipient'}'. Goal/context: {req.context}")
    draft = await llm("You are an expert email copywriter. Return ONLY the email "
                      "(subject line + body), no commentary.", user, max_tokens=1200)
    return {"draft": draft}


@api_router.post("/research")
async def research(req: ResearchRequest):
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(req.query, max_results=6))
    except Exception as exc:  # noqa: BLE001
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
async def build(req: BuildRequest):
    system = ("You are an elite full-stack engineer. Build a COMPLETE, production-quality, "
              "SELF-CONTAINED single-file web app as ONE HTML document with inline <style> and "
              "<script> (vanilla JS, no build step). It must actually WORK: real interactivity, "
              "sensible sample data, polished modern responsive UI. You MAY use CDN links "
              "(Tailwind CDN, Chart.js, font CDNs). Return ONLY the HTML from <!DOCTYPE html> "
              "to </html>. No commentary.")
    if req.refine and req.current_html:
        user = (f"Current app:\n```html\n{req.current_html[:6000]}\n```\n\n"
                f"Apply this change and return the full updated HTML:\n{req.refine}")
    else:
        user = f"App idea: {req.idea}\n\nBuild the full working app now."
    raw = await llm(system, user, max_tokens=4000)
    return {"html": _extract_html(raw)}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
