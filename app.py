"""
Jarvis Personal OS — A premium, secure daily assistant built with Streamlit.

Architecture
------------
- Secure Google OAuth login wall (native Streamlit OIDC auth, tied to a custom domain).
- Minimalist dark UI with neon accents.
- Sidebar: Google profile + masked credential inputs (LLM key, provider select).
- Command Center with 5 workspaces:
    1. AI Chat & Rewriter        (Groq / SambaNova  ->  llama-3.3-70b)
    2. Email Generator
    3. Smart Web Research        (DuckDuckGo live search)
    4. Image Generator           (Pollinations AI, free/unlimited)
    5. Project Agent             (2-step Planner -> Coder flow)

Run locally:      streamlit run app.py
Deploy:           point https://apnabihar.online at this app (see README.md)
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import time
import urllib.parse
import zipfile
from datetime import datetime, timezone
from typing import Generator, List

import requests
import streamlit as st

# ----------------------------------------------------------------------------- #
#  Global configuration
# ----------------------------------------------------------------------------- #

APP_NAME = "Jarvis Personal OS"
CUSTOM_DOMAIN = "https://apnabihar.online"

PROVIDERS = {
    "Groq": {
        "base_url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "llama-3.3-70b-specdec",
        "stt_url": "https://api.groq.com/openai/v1/audio/transcriptions",
        "stt_model": "whisper-large-v3",
        "signup": "https://console.groq.com/keys",
    },
    "SambaNova": {
        "base_url": "https://api.sambanova.ai/v1/chat/completions",
        "model": "Meta-Llama-3.3-70B-Instruct",
        "stt_url": "https://api.sambanova.ai/v1/audio/transcriptions",
        "stt_model": "Whisper-Large-v3",
        "signup": "https://cloud.sambanova.ai/apis",
    },
}

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ----------------------------------------------------------------------------- #
#  Styling — minimalist dark mode with neon accents
# ----------------------------------------------------------------------------- #

def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

        :root {
            --bg: #07090d;
            --panel: #0f141c;
            --panel-2: #141b26;
            --border: #1e2937;
            --neon: #00f5d4;
            --neon-2: #7b61ff;
            --text: #e6edf3;
            --muted: #7d8896;
        }

        .stApp {
            background:
                radial-gradient(900px 500px at 12% -10%, rgba(123,97,255,.14), transparent 60%),
                radial-gradient(800px 500px at 100% 0%, rgba(0,245,212,.10), transparent 55%),
                var(--bg);
            color: var(--text);
            font-family: 'Sora', sans-serif;
        }
        #MainMenu, footer, header {visibility: hidden;}

        h1, h2, h3, h4 { font-family: 'Sora', sans-serif; letter-spacing: -.02em; }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0b0f16, #090c11);
            border-right: 1px solid var(--border);
        }

        /* Neon gradient buttons */
        .stButton > button, .stDownloadButton > button {
            background: linear-gradient(135deg, var(--neon), var(--neon-2));
            color: #04070b;
            border: none;
            border-radius: 12px;
            font-weight: 600;
            padding: .55rem 1rem;
            transition: transform .15s ease, box-shadow .15s ease, filter .15s ease;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 26px rgba(0,245,212,.25);
            filter: brightness(1.06);
            color: #04070b;
        }

        /* Inputs */
        .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {
            background: var(--panel-2) !important;
            border: 1px solid var(--border) !important;
            border-radius: 12px !important;
            color: var(--text) !important;
        }
        .stTextInput input:focus, .stTextArea textarea:focus {
            border-color: var(--neon) !important;
            box-shadow: 0 0 0 2px rgba(0,245,212,.18) !important;
        }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: .35rem;
            background: var(--panel);
            padding: .35rem;
            border-radius: 14px;
            border: 1px solid var(--border);
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 10px;
            color: var(--muted);
            font-weight: 600;
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, rgba(0,245,212,.16), rgba(123,97,255,.16));
            color: var(--neon) !important;
        }

        .jv-card {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 1.4rem 1.6rem;
        }
        .jv-hero {
            font-size: 2.6rem; font-weight: 700; line-height: 1.05;
            background: linear-gradient(120deg, var(--neon), var(--neon-2));
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .jv-muted { color: var(--muted); }
        .jv-chip {
            display:inline-block; padding:.2rem .7rem; margin:.15rem;
            border:1px solid var(--border); border-radius:999px;
            font-size:.75rem; color:var(--neon); background:rgba(0,245,212,.06);
        }
        .jv-profile {
            display:flex; align-items:center; gap:.75rem;
            padding:.8rem; border:1px solid var(--border);
            border-radius:14px; background:var(--panel-2);
        }
        .jv-profile img { width:44px; height:44px; border-radius:50%; border:2px solid var(--neon); }
        .stChatMessage { background: var(--panel); border:1px solid var(--border); border-radius:14px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------------- #
#  Authentication — native Streamlit OIDC (Google), tied to the custom domain
# ----------------------------------------------------------------------------- #

def is_authenticated() -> bool:
    user = getattr(st, "user", None)
    return bool(user and getattr(user, "is_logged_in", False))


def login_screen() -> None:
    """Full-screen login wall. No workspace is reachable without auth."""
    inject_css()
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        st.markdown("<div style='height:8vh'></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='jv-hero'>🤖 {APP_NAME}</div>", unsafe_allow_html=True)
        st.markdown(
            "<p class='jv-muted'>Your private, secure command center for daily AI work. "
            "Chat, research the live web, draft emails, generate images and ship "
            "projects — all in one place.</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<span class='jv-chip'>AI Chat</span><span class='jv-chip'>Web Research</span>"
            "<span class='jv-chip'>Email</span><span class='jv-chip'>Images</span>"
            "<span class='jv-chip'>Project Agent</span>",
            unsafe_allow_html=True,
        )
        st.write("")
        with st.container(border=True):
            st.markdown("#### 🔐 Secure access")
            st.caption(f"Authorized for **{CUSTOM_DOMAIN}**")
            has_auth = "auth" in getattr(st, "secrets", {})
            if not has_auth:
                st.warning(
                    "Google OAuth is not configured yet. Add your credentials to "
                    "`.streamlit/secrets.toml` (see the template) and restart.",
                    icon="⚠️",
                )
            if st.button("Sign in with Google", use_container_width=True,
                         disabled=not has_auth, key="google-signin-btn"):
                st.login()  # -> Google via OIDC, redirects back to CUSTOM_DOMAIN
        st.caption("🔒 We only read your name, email and avatar. Nothing is stored.")


# ----------------------------------------------------------------------------- #
#  LLM helpers  (OpenAI-compatible endpoints for Groq + SambaNova)
# ----------------------------------------------------------------------------- #

def llm_chat(messages: List[dict], temperature: float = 0.7, max_tokens: int = 1500) -> str:
    """Non-streaming completion. Returns the assistant text or an error string."""
    provider = st.session_state.get("provider", "Groq")
    api_key = st.session_state.get("llm_key", "").strip()
    if not api_key:
        return "⚠️ Please add your LLM API key in the sidebar to activate the brain."

    cfg = PROVIDERS[provider]
    try:
        resp = requests.post(
            cfg["base_url"],
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={
                "model": cfg["model"],
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=90,
        )
        if resp.status_code != 200:
            return f"⚠️ {provider} error {resp.status_code}: {resp.text[:300]}"
        return resp.json()["choices"][0]["message"]["content"].strip()
    except requests.exceptions.RequestException as exc:
        return f"⚠️ Network error talking to {provider}: {exc}"


def llm_stream(messages: List[dict], temperature: float = 0.7) -> Generator[str, None, None]:
    """Streaming generator for the chat UI."""
    provider = st.session_state.get("provider", "Groq")
    api_key = st.session_state.get("llm_key", "").strip()
    if not api_key:
        yield "⚠️ Please add your LLM API key in the sidebar to activate the brain."
        return

    cfg = PROVIDERS[provider]
    try:
        with requests.post(
            cfg["base_url"],
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={"model": cfg["model"], "messages": messages,
                  "temperature": temperature, "stream": True},
            stream=True,
            timeout=90,
        ) as resp:
            if resp.status_code != 200:
                yield f"⚠️ {provider} error {resp.status_code}: {resp.text[:300]}"
                return
            import json as _json
            for raw in resp.iter_lines():
                if not raw:
                    continue
                line = raw.decode("utf-8").removeprefix("data: ").strip()
                if line in ("", "[DONE]"):
                    continue
                try:
                    delta = _json.loads(line)["choices"][0]["delta"].get("content")
                    if delta:
                        yield delta
                except (ValueError, KeyError, IndexError):
                    continue
    except requests.exceptions.RequestException as exc:
        yield f"⚠️ Network error talking to {provider}: {exc}"


# ----------------------------------------------------------------------------- #
#  Web search  (DuckDuckGo, no API key)
# ----------------------------------------------------------------------------- #

def web_search(query: str, max_results: int = 6) -> List[dict]:
    try:
        from ddgs import DDGS  # newer package name
    except ImportError:  # pragma: no cover
        from duckduckgo_search import DDGS  # legacy fallback
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


# ----------------------------------------------------------------------------- #
#  Speech-to-text  (voice input via provider Whisper endpoint)
# ----------------------------------------------------------------------------- #

def transcribe_audio(audio_bytes: bytes) -> str:
    provider = st.session_state.get("provider", "Groq")
    api_key = st.session_state.get("llm_key", "").strip()
    if not api_key:
        return ""
    cfg = PROVIDERS[provider]
    try:
        resp = requests.post(
            cfg["stt_url"],
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": ("voice.wav", audio_bytes, "audio/wav")},
            data={"model": cfg["stt_model"]},
            timeout=90,
        )
        if resp.status_code != 200:
            st.error(f"Transcription error {resp.status_code}: {resp.text[:200]}")
            return ""
        return resp.json().get("text", "").strip()
    except requests.exceptions.RequestException as exc:
        st.error(f"Voice transcription failed: {exc}")
        return ""


# ----------------------------------------------------------------------------- #
#  Per-user persistent storage helpers
# ----------------------------------------------------------------------------- #

def _user_key() -> str:
    email = getattr(st.user, "email", "anon") or "anon"
    return hashlib.sha256(email.encode()).hexdigest()[:16]


def _user_dir(sub: str) -> str:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".jarvis", sub, _user_key())
    os.makedirs(path, exist_ok=True)
    return path


def _read_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (ValueError, OSError):
            return default
    return default


def _write_json(path: str, data) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
    except OSError:
        pass


# ---- chat conversations ----
def load_conversations() -> List[dict]:
    return _read_json(os.path.join(_user_dir("history"), "conversations.json"), [])


def save_conversations(conversations: List[dict]) -> None:
    _write_json(os.path.join(_user_dir("history"), "conversations.json"), conversations)


# ---- email templates ----
def load_templates() -> List[dict]:
    return _read_json(os.path.join(_user_dir("templates"), "email.json"), [])


def save_templates(templates: List[dict]) -> None:
    _write_json(os.path.join(_user_dir("templates"), "email.json"), templates)


# ---- image gallery (base64 stored in a single JSON data file) ----
def save_image_to_gallery(image_bytes: bytes, prompt: str) -> None:
    path = os.path.join(_user_dir("gallery"), "gallery.json")
    meta = _read_json(path, [])
    meta.insert(0, {
        "b64": base64.b64encode(image_bytes).decode("ascii"),
        "prompt": prompt,
        "time": datetime.now(timezone.utc).isoformat(),
    })
    _write_json(path, meta[:40])


def load_gallery() -> List[dict]:
    items = []
    for m in _read_json(os.path.join(_user_dir("gallery"), "gallery.json"), []):
        try:
            items.append({**m, "bytes": base64.b64decode(m["b64"])})
        except (KeyError, ValueError):
            continue
    return items


# ---- built-app gallery (live App Builder) ----
def save_app(idea: str, spec: str, html: str, app_id: str = "") -> str:
    path = os.path.join(_user_dir("apps"), "apps.json")
    apps = _read_json(path, [])
    if app_id:
        for a in apps:
            if a["id"] == app_id:
                a.update({"idea": idea, "spec": spec, "html": html,
                          "time": datetime.now(timezone.utc).isoformat()})
                _write_json(path, apps)
                return app_id
    app_id = str(int(time.time() * 1000))
    apps.insert(0, {"id": app_id, "idea": idea, "spec": spec, "html": html,
                    "time": datetime.now(timezone.utc).isoformat()})
    _write_json(path, apps[:30])
    return app_id


def load_apps() -> List[dict]:
    return _read_json(os.path.join(_user_dir("apps"), "apps.json"), [])


def delete_app(app_id: str) -> None:
    path = os.path.join(_user_dir("apps"), "apps.json")
    _write_json(path, [a for a in _read_json(path, []) if a["id"] != app_id])


# ---- research history ----
def load_research() -> List[dict]:
    return _read_json(os.path.join(_user_dir("research"), "reports.json"), [])


def add_research(query: str, summary: str, sources: List[dict]) -> None:
    path = os.path.join(_user_dir("research"), "reports.json")
    reports = _read_json(path, [])
    reports.insert(0, {
        "id": str(int(time.time() * 1000)),
        "query": query, "summary": summary,
        "sources": [{"title": s.get("title", ""), "href": s.get("href", "")} for s in sources],
        "time": datetime.now(timezone.utc).isoformat(),
    })
    _write_json(path, reports[:40])


def delete_research(rid: str) -> None:
    path = os.path.join(_user_dir("research"), "reports.json")
    _write_json(path, [r for r in _read_json(path, []) if r["id"] != rid])


def toggle_research_pin(rid: str) -> None:
    path = os.path.join(_user_dir("research"), "reports.json")
    reports = _read_json(path, [])
    for r in reports:
        if r["id"] == rid:
            r["pinned"] = not r.get("pinned", False)
    _write_json(path, reports)


def set_research_tags(rid: str, tags: List[str]) -> None:
    path = os.path.join(_user_dir("research"), "reports.json")
    reports = _read_json(path, [])
    for r in reports:
        if r["id"] == rid:
            r["tags"] = tags
    _write_json(path, reports)


# ---- self-upgrade log + pending proposals + settings ----
def load_upgrade_log() -> List[dict]:
    return _read_json(os.path.join(_user_dir("upgrades"), "log.json"), [])


def save_upgrade_log(log: List[dict]) -> None:
    _write_json(os.path.join(_user_dir("upgrades"), "log.json"), log[:80])


def load_pending() -> List[dict]:
    return _read_json(os.path.join(_user_dir("upgrades"), "pending.json"), [])


def save_pending(items: List[dict]) -> None:
    _write_json(os.path.join(_user_dir("upgrades"), "pending.json"), items[:20])


def load_settings() -> dict:
    return _read_json(os.path.join(_user_dir("upgrades"), "settings.json"),
                      {"auto_scan": False, "interval_hours": 24, "last_scan": "",
                       "digest_email": False, "smtp_host": "", "smtp_port": 587,
                       "smtp_user": "", "digest_to": "", "last_digest": ""})


def save_settings(settings: dict) -> None:
    _write_json(os.path.join(_user_dir("upgrades"), "settings.json"), settings)


# ----------------------------------------------------------------------------- #
#  Email digest  (SMTP, user-provided credentials)
# ----------------------------------------------------------------------------- #

def build_digest_text(proposals: List[dict]) -> str:
    lines = [f"Jarvis weekly digest — {datetime.now(timezone.utc):%Y-%m-%d}",
             f"{len(proposals)} upgrade proposal(s) awaiting your review:\n"]
    for i, p in enumerate(proposals, 1):
        lines.append(f"{i}. [{p.get('type','')}] {p.get('title','')}")
        lines.append(f"   Why: {p.get('rationale','')}")
    lines.append("\nOpen Jarvis to Approve or Deny each one.")
    return "\n".join(lines)


def send_digest_email(host: str, port: int, user: str, password: str,
                      to_addr: str, body: str) -> tuple[bool, str]:
    import smtplib
    from email.mime.text import MIMEText
    try:
        msg = MIMEText(body)
        msg["Subject"] = "🧬 Jarvis — Weekly Upgrade Digest"
        msg["From"] = user
        msg["To"] = to_addr
        with smtplib.SMTP(host, int(port), timeout=30) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(user, [to_addr], msg.as_string())
        return True, "Sent"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


# ----------------------------------------------------------------------------- #
#  Preview build  (apply approved upgrades to a safe copy)
# ----------------------------------------------------------------------------- #

def _app_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def build_preview_copy(approved: List[dict]) -> str:
    """Create app_preview.py = current app + an appended, clearly-marked upgrades section."""
    base_path = os.path.join(_app_dir(), "app.py")
    with open(base_path, "r", encoding="utf-8") as fh:
        base = fh.read()
    header = ("\n\n# ===================================================================\n"
              f"# JARVIS PREVIEW BUILD — {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}\n"
              f"# {len(approved)} approved upgrade(s) staged below for review.\n"
              "# Review, then run:  streamlit run app_preview.py\n"
              "# ===================================================================\n")
    blocks = []
    for x in approved:
        blocks.append(f"\n# --- {x.get('title','')} ({x.get('type','')}) ---\n"
                      f"# note: {x.get('note','') or '-'}\n"
                      f"# rationale: {x.get('rationale','')}\n"
                      f"{x.get('code','')}\n")
    preview = base + header + "\n".join(blocks)
    out_path = os.path.join(_app_dir(), "app_preview.py")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(preview)
    return out_path


def promote_preview_to_live() -> tuple[bool, str]:
    """Back up live app.py then replace it with the previewed copy."""
    app_path = os.path.join(_app_dir(), "app.py")
    preview_path = os.path.join(_app_dir(), "app_preview.py")
    if not os.path.exists(preview_path):
        return False, "Build a preview first."
    bdir = _user_dir("backups")
    backup = os.path.join(bdir, f"app_{int(time.time())}.py")
    try:
        with open(app_path, "r", encoding="utf-8") as fh:
            live = fh.read()
        with open(backup, "w", encoding="utf-8") as fh:
            fh.write(live)
        with open(preview_path, "r", encoding="utf-8") as fh:
            preview = fh.read()
        with open(app_path, "w", encoding="utf-8") as fh:
            fh.write(preview)
        return True, backup
    except OSError as exc:
        return False, str(exc)


def list_backups() -> List[dict]:
    bdir = _user_dir("backups")
    labels = _read_json(os.path.join(bdir, "labels.json"), {})
    items = []
    for name in sorted(os.listdir(bdir), reverse=True):
        if name.startswith("app_") and name.endswith(".py"):
            fpath = os.path.join(bdir, name)
            ts = name[4:-3]
            try:
                when = datetime.fromtimestamp(int(ts), timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            except ValueError:
                when = ts
            items.append({"name": name, "path": fpath, "when": when,
                          "label": labels.get(name, ""), "size": os.path.getsize(fpath)})
    return items


def set_backup_label(name: str, label: str) -> None:
    bdir = _user_dir("backups")
    labels = _read_json(os.path.join(bdir, "labels.json"), {})
    labels[name] = label
    _write_json(os.path.join(bdir, "labels.json"), labels)


def restore_backup(path: str) -> tuple[bool, str]:
    app_path = os.path.join(_app_dir(), "app.py")
    if not os.path.exists(path):
        return False, "Backup not found."
    try:
        # snapshot current before restoring, so a bad restore is also reversible
        with open(app_path, "r", encoding="utf-8") as fh:
            live = fh.read()
        with open(os.path.join(_user_dir("backups"), f"app_{int(time.time())}.py"), "w",
                  encoding="utf-8") as fh:
            fh.write(live)
        with open(path, "r", encoding="utf-8") as fh:
            restored = fh.read()
        with open(app_path, "w", encoding="utf-8") as fh:
            fh.write(restored)
        return True, "Restored"
    except OSError as exc:
        return False, str(exc)


def build_preview_diff() -> str:
    """Side-by-side HTML diff between live app.py and app_preview.py."""
    import difflib
    app_path = os.path.join(_app_dir(), "app.py")
    preview_path = os.path.join(_app_dir(), "app_preview.py")
    if not os.path.exists(preview_path):
        return ""
    with open(app_path, encoding="utf-8") as fh:
        live = fh.read().splitlines()
    with open(preview_path, encoding="utf-8") as fh:
        preview = fh.read().splitlines()
    return difflib.HtmlDiff(wrapcolumn=70).make_table(
        live, preview, "Live app.py", "app_preview.py", context=True, numlines=2)


# ----------------------------------------------------------------------------- #
#  Text-to-speech  (free, in-browser SpeechSynthesis)
# ----------------------------------------------------------------------------- #

def speak(text: str) -> None:
    import streamlit.components.v1 as components
    payload = json.dumps(text[:3000])
    lang = st.session_state.get("voice_lang", "en-US")
    rate = st.session_state.get("voice_rate", 1.02)
    components.html(
        f"""
        <script>
            function jvSpeak() {{
                const synth = window.speechSynthesis;
                const u = new SpeechSynthesisUtterance({payload});
                u.lang = "{lang}"; u.rate = {rate}; u.pitch = 1.0;
                const voices = synth.getVoices();
                const match = voices.find(v => v.lang === "{lang}")
                              || voices.find(v => v.lang.startsWith("{lang}".slice(0,2)));
                if (match) u.voice = match;
                synth.cancel(); synth.speak(u);
            }}
            if (window.speechSynthesis.getVoices().length) {{ jvSpeak(); }}
            else {{ window.speechSynthesis.onvoiceschanged = jvSpeak; }}
        </script>
        """,
        height=0,
    )


# ----------------------------------------------------------------------------- #
#  PDF export  (research summaries)
# ----------------------------------------------------------------------------- #

def build_pdf(title: str, body: str, sources: List[dict]) -> bytes:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    def latin(text: str) -> str:
        return text.encode("latin-1", "replace").decode("latin-1")

    pdf = FPDF()
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    w = pdf.epw  # effective page width

    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(w, 9, latin(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(w, 6, latin(f"Jarvis Personal OS | {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}"),
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)

    pdf.set_text_color(20, 20, 20)
    pdf.set_font("Helvetica", "", 11)
    for line in body.split("\n"):
        if line.strip():
            pdf.multi_cell(w, 6, latin(line), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        else:
            pdf.ln(4)

    if sources:
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(w, 7, "Sources", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(60, 60, 160)
        for i, s in enumerate(sources):
            pdf.multi_cell(w, 5, latin(f"[{i+1}] {s.get('title','')} - {s.get('href','')}"),
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    out = pdf.output()
    return bytes(out)


# ----------------------------------------------------------------------------- #
#  Sidebar — profile + credentials
# ----------------------------------------------------------------------------- #

def render_sidebar() -> None:
    with st.sidebar:
        user = st.user
        name = getattr(user, "name", "User")
        email = getattr(user, "email", "")
        picture = getattr(user, "picture", "") or "https://ui-avatars.com/api/?name=J"

        st.markdown(
            f"""
            <div class="jv-profile" data-testid="sidebar-profile">
                <img src="{picture}" alt="avatar"/>
                <div>
                    <div style="font-weight:700">{name}</div>
                    <div class="jv-muted" style="font-size:.78rem">{email}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Log out", use_container_width=True, key="logout-btn"):
            st.logout()

        st.divider()
        st.markdown("### 🧠 LLM Brain")
        provider = st.selectbox(
            "Provider", list(PROVIDERS.keys()),
            key="provider", help="Both use a free Llama-3.3-70B model.",
        )
        st.text_input(
            f"{provider} API Key", type="password", key="llm_key",
            placeholder="sk-...", help=f"Get one at {PROVIDERS[provider]['signup']}",
        )
        st.caption(f"Model: `{PROVIDERS[provider]['model']}`")

        st.divider()
        st.markdown("### 🎨 Image Engine")
        st.text_input(
            "Pollinations token (optional)", type="password", key="img_key",
            placeholder="leave empty — free & unlimited",
            help="Pollinations AI is free and needs no key.",
        )
        st.caption("Powered by Pollinations AI · free & unlimited")

        st.divider()
        st.markdown("### 🔊 Voice")
        st.checkbox("Read replies aloud", key="read_aloud",
                    help="Jarvis speaks its chat answers using your browser's voice.")
        accents = {
            "English (US)": "en-US", "English (UK)": "en-GB", "English (India)": "en-IN",
            "English (Australia)": "en-AU", "Hindi": "hi-IN", "Spanish": "es-ES",
            "French": "fr-FR", "German": "de-DE",
        }
        accent = st.selectbox("Accent / voice", list(accents.keys()), key="voice_accent")
        st.session_state["voice_lang"] = accents[accent]
        st.session_state["voice_rate"] = st.slider("Speaking speed", 0.5, 1.6, 1.02, 0.02,
                                                    key="voice_rate_slider")
        if st.button("🔊 Test voice", use_container_width=True, key="voice-test"):
            speak(f"Hello, I am Jarvis, speaking with a {accent} accent. This is my current speed.")

        st.divider()
        status = "🟢 Online" if st.session_state.get("llm_key") else "🔴 Add key"
        st.markdown(f"**Brain status:** {status}")
        pending = load_pending()
        if pending:
            st.warning(f"🔔 {len(pending)} upgrade(s) to review in Self-Upgrade tab.", icon="🧬")


# ----------------------------------------------------------------------------- #
#  Workspace 1 — AI Chat & Rewriter
# ----------------------------------------------------------------------------- #

def _new_conversation() -> dict:
    return {"id": str(int(time.time() * 1000)),
            "title": "New chat",
            "created": datetime.now(timezone.utc).isoformat(),
            "messages": []}


def workspace_chat() -> None:
    st.subheader("💬 AI Chat & Rewriter")
    st.caption("Talk to Jarvis or transform any text with one click. Conversations are saved.")

    # ---- load persisted conversations once per session ----
    if "conversations" not in st.session_state:
        st.session_state.conversations = load_conversations()
    if "active_conv" not in st.session_state:
        if st.session_state.conversations:
            st.session_state.active_conv = st.session_state.conversations[0]["id"]
        else:
            conv = _new_conversation()
            st.session_state.conversations = [conv]
            st.session_state.active_conv = conv["id"]

    def _get_active() -> dict:
        for c in st.session_state.conversations:
            if c["id"] == st.session_state.active_conv:
                return c
        st.session_state.active_conv = st.session_state.conversations[0]["id"]
        return st.session_state.conversations[0]

    # ---- conversation manager ----
    top = st.columns([3, 1, 1])
    labels = {c["id"]: f"{c['title']}  ·  {c['created'][:10]}"
              for c in st.session_state.conversations}
    ids = list(labels.keys())
    selected = top[0].selectbox(
        "Conversation", ids,
        index=ids.index(st.session_state.active_conv) if st.session_state.active_conv in ids else 0,
        format_func=lambda i: labels.get(i, "chat"),
        key="conv-picker", label_visibility="collapsed",
    )
    st.session_state.active_conv = selected
    if top[1].button("➕ New", use_container_width=True, key="new-chat"):
        conv = _new_conversation()
        st.session_state.conversations.insert(0, conv)
        st.session_state.active_conv = conv["id"]
        save_conversations(st.session_state.conversations)
        st.rerun()
    if top[2].button("🗑️ Delete", use_container_width=True, key="del-chat"):
        st.session_state.conversations = [
            c for c in st.session_state.conversations if c["id"] != st.session_state.active_conv]
        if not st.session_state.conversations:
            st.session_state.conversations = [_new_conversation()]
        st.session_state.active_conv = st.session_state.conversations[0]["id"]
        save_conversations(st.session_state.conversations)
        st.rerun()

    active = _get_active()

    # ---- rewriter presets ----
    presets = {
        "✍️ Make it Professional": "Rewrite the following text to be clear, professional and polished. Keep the meaning:\n\n",
        "📝 Summarize Text": "Summarize the following text into concise bullet points capturing the key ideas:\n\n",
        "🎭 Change Tone": "Rewrite the following text in a warmer, more engaging and friendly tone:\n\n",
    }
    cols = st.columns(len(presets))
    for col, (label, prefix) in zip(cols, presets.items()):
        if col.button(label, use_container_width=True, key=f"preset-{label}"):
            st.session_state["preset_prefix"] = prefix
            st.session_state["preset_label"] = label
    if st.session_state.get("preset_prefix"):
        st.info(f"Preset active: **{st.session_state['preset_label']}** — "
                "type, paste or speak your text below.", icon="⚡")

    # ---- transcript ----
    for msg in active["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ---- voice input ----
    voice_text = ""
    with st.expander("🎙️ Voice input"):
        audio = st.audio_input("Record a message", key=f"mic-{active['id']}")
        if audio is not None and st.button("Transcribe & send", key="voice-send"):
            with st.spinner("Transcribing…"):
                voice_text = transcribe_audio(audio.getvalue())
            if not voice_text:
                st.warning("Could not transcribe (check your LLM key supports Whisper).")

    prompt = st.chat_input("Message Jarvis…") or voice_text
    if prompt:
        prefix = st.session_state.pop("preset_prefix", "")
        st.session_state.pop("preset_label", None)
        full_prompt = f"{prefix}{prompt}" if prefix else prompt

        active["messages"].append({"role": "user", "content": prompt})
        if active["title"] == "New chat":
            active["title"] = (prompt[:40] + "…") if len(prompt) > 40 else prompt
        with st.chat_message("user"):
            st.markdown(prompt)

        history = [{"role": "system",
                    "content": "You are Jarvis, a sharp, concise personal assistant."}]
        history += [{"role": m["role"], "content": m["content"]}
                    for m in active["messages"][:-1]]
        history.append({"role": "user", "content": full_prompt})

        with st.chat_message("assistant"):
            reply = st.write_stream(llm_stream(history))
        active["messages"].append({"role": "assistant", "content": reply})
        save_conversations(st.session_state.conversations)
        if st.session_state.get("read_aloud"):
            speak(reply)
        if voice_text:
            st.rerun()

    if active["messages"] and active["messages"][-1]["role"] == "assistant":
        if st.button("🔊 Read last answer", key="read-last"):
            speak(active["messages"][-1]["content"])


# ----------------------------------------------------------------------------- #
#  Workspace 2 — Email Generator
# ----------------------------------------------------------------------------- #

def workspace_email() -> None:
    st.subheader("✉️ Email Generator")
    st.caption("Generate a perfectly formatted email draft in seconds.")

    if "email_templates" not in st.session_state:
        st.session_state.email_templates = load_templates()

    # ---- saved templates (one-tap reuse) ----
    if st.session_state.email_templates:
        st.markdown("**⭐ Saved templates**")
        tcols = st.columns(min(4, len(st.session_state.email_templates)) or 1)
        for idx, tpl in enumerate(st.session_state.email_templates):
            col = tcols[idx % len(tcols)]
            if col.button(f"⭐ {tpl['name']}", key=f"tpl-use-{idx}", use_container_width=True):
                st.session_state["email-recipient"] = tpl["recipient"]
                st.session_state["email-tone"] = tpl["tone"]
                st.session_state["email-context"] = tpl["context"]
                st.rerun()
            if col.button("🗑️", key=f"tpl-del-{idx}", use_container_width=True):
                st.session_state.email_templates.pop(idx)
                save_templates(st.session_state.email_templates)
                st.rerun()

    c1, c2 = st.columns(2)
    recipient = c1.text_input("Recipient", placeholder="e.g. Hiring Manager, Acme Corp",
                              key="email-recipient")
    tone = c2.selectbox("Tone", ["Polite", "Urgent", "Casual", "Formal", "Persuasive"],
                        key="email-tone")
    context = st.text_area("Context / Goal",
                           placeholder="What is this email about? What do you want to achieve?",
                           height=140, key="email-context")

    b1, b2 = st.columns([1, 1])
    if b1.button("✨ Generate Email", key="email-generate", use_container_width=True):
        if not context.strip():
            st.warning("Please describe the context/goal of the email.", icon="⚠️")
        else:
            with st.spinner("Drafting your email…"):
                msgs = [
                    {"role": "system",
                     "content": "You are an expert email copywriter. Return ONLY the email "
                                "(subject line + body), no commentary."},
                    {"role": "user",
                     "content": f"Write a {tone.lower()} email to '{recipient or 'the recipient'}'. "
                                f"Goal/context: {context}"},
                ]
                st.session_state["email_result"] = llm_chat(msgs, temperature=0.6)

    with b2.popover("⭐ Save as template", use_container_width=True):
        tpl_name = st.text_input("Template name", key="tpl-name",
                                 placeholder="e.g. Job follow-up")
        if st.button("Save", key="tpl-save"):
            if tpl_name.strip() and context.strip():
                st.session_state.email_templates.insert(0, {
                    "name": tpl_name.strip(), "recipient": recipient,
                    "tone": tone, "context": context,
                })
                save_templates(st.session_state.email_templates)
                st.success("Template saved!")
                st.rerun()
            else:
                st.warning("Give it a name and fill the context first.")

    if st.session_state.get("email_result"):
        st.markdown("#### 📋 Draft")
        st.code(st.session_state["email_result"], language="text")
        st.caption("Use the copy icon on the top-right of the block above.")


# ----------------------------------------------------------------------------- #
#  Workspace 3 — Smart Web Research
# ----------------------------------------------------------------------------- #

def workspace_research() -> None:
    st.subheader("🔎 Smart Web Research")
    st.caption("Jarvis searches the live web and compiles an absolute-truth summary.")

    query = st.text_input("Ask anything", placeholder="e.g. Latest AI regulations in the EU 2026",
                          key="research-query")
    if st.button("🌐 Search & Summarize", key="research-go"):
        if not query.strip():
            st.warning("Enter a question to research.", icon="⚠️")
            return
        with st.spinner("Searching the live web…"):
            try:
                results = web_search(query, max_results=6)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Search failed: {exc}")
                return

        if not results:
            st.info("No results found. Try rephrasing your question.")
            return

        snippets = "\n\n".join(
            f"[{i+1}] {r.get('title','')}\n{r.get('body','')}\nSource: {r.get('href','')}"
            for i, r in enumerate(results)
        )
        with st.spinner("Reading snippets and compiling the truth…"):
            msgs = [
                {"role": "system",
                 "content": "You are a rigorous research analyst. Using ONLY the provided web "
                            "snippets, write a factual, well-structured summary. Cite sources "
                            "as [n]. If sources conflict, say so."},
                {"role": "user",
                 "content": f"Question: {query}\n\nWeb snippets:\n{snippets}"},
            ]
            summary = llm_chat(msgs, temperature=0.3, max_tokens=1800)

        st.markdown("#### 🧾 Absolute-Truth Summary")
        with st.container(border=True):
            st.markdown(summary)

        st.session_state["research_summary"] = summary
        st.session_state["research_sources"] = results
        st.session_state["research_query"] = query
        add_research(query, summary, results)

    if st.session_state.get("research_summary"):
        pdf_bytes = build_pdf(
            f"Research: {st.session_state.get('research_query','')}",
            st.session_state["research_summary"],
            st.session_state.get("research_sources", []),
        )
        st.download_button("📄 Save as PDF", data=pdf_bytes,
                           file_name="jarvis-research.pdf", mime="application/pdf",
                           key="research-pdf")
        with st.expander("🔗 Sources"):
            for i, r in enumerate(st.session_state.get("research_sources", [])):
                st.markdown(f"**[{i+1}] {r.get('title','')}**  \n{r.get('href','')}")

    # ---- research history ----
    reports = load_research()
    if reports:
        st.divider()
        st.markdown(f"#### 🗂️ Research History ({len(reports)})")
        fcol1, fcol2 = st.columns([2, 1])
        term = fcol1.text_input("🔍 Search past reports", key="research-search",
                                placeholder="Filter by keyword…").strip().lower()
        all_tags = sorted({t for r in reports for t in r.get("tags", [])})
        tag_filter = fcol2.multiselect("🏷️ Filter by tag", all_tags, key="research-tag-filter")
        if term:
            reports = [r for r in reports
                       if term in r["query"].lower() or term in r["summary"].lower()]
        if tag_filter:
            reports = [r for r in reports
                       if set(tag_filter).issubset(set(r.get("tags", [])))]
        if term or tag_filter:
            st.caption(f"{len(reports)} match(es)")
        reports = sorted(reports, key=lambda r: not r.get("pinned", False))
        for rep in reports:
            pin = "📌 " if rep.get("pinned") else ""
            tag_str = ("  " + " ".join(f"`{t}`" for t in rep.get("tags", []))) if rep.get("tags") else ""
            with st.expander(f"{pin}🔎 {rep['query']}  ·  {rep['time'][:10]}"):
                if tag_str.strip():
                    st.markdown("🏷️" + tag_str)
                st.markdown(rep["summary"])
                cols = st.columns([1, 1, 1])
                cols[0].download_button(
                    "📄 PDF",
                    data=build_pdf(f"Research: {rep['query']}", rep["summary"], rep["sources"]),
                    file_name="jarvis-research.pdf", mime="application/pdf",
                    key=f"rehist-pdf-{rep['id']}", use_container_width=True)
                pin_label = "📌 Unpin" if rep.get("pinned") else "📌 Pin"
                if cols[1].button(pin_label, key=f"rehist-pin-{rep['id']}",
                                  use_container_width=True):
                    toggle_research_pin(rep["id"])
                    st.rerun()
                if cols[2].button("🗑️ Delete", key=f"rehist-del-{rep['id']}",
                                  use_container_width=True):
                    delete_research(rep["id"])
                    st.rerun()
                tcol1, tcol2 = st.columns([3, 1])
                new_tags = tcol1.text_input("🏷️ Tags (comma separated)",
                                            value=", ".join(rep.get("tags", [])),
                                            key=f"rehist-tags-{rep['id']}",
                                            label_visibility="collapsed",
                                            placeholder="e.g. ai, policy, europe")
                if tcol2.button("Save tags", key=f"rehist-savetags-{rep['id']}",
                                use_container_width=True):
                    tags = [t.strip() for t in new_tags.split(",") if t.strip()]
                    set_research_tags(rep["id"], tags)
                    st.rerun()


# ----------------------------------------------------------------------------- #
#  Workspace 4 — Image Generator (Pollinations)
# ----------------------------------------------------------------------------- #

def workspace_image() -> None:
    st.subheader("🖼️ Image Generator")
    st.caption("Free & unlimited image generation via Pollinations AI.")

    prompt = st.text_area("Describe your image",
                          placeholder="e.g. a neon cyberpunk city in the rain, cinematic, 8k",
                          height=110, key="img-prompt")
    c1, c2, c3 = st.columns(3)
    width = c1.selectbox("Width", [512, 768, 1024], index=2, key="img-w")
    height = c2.selectbox("Height", [512, 768, 1024], index=2, key="img-h")
    model = c3.selectbox("Style model", ["flux", "flux-realism", "turbo"], key="img-model")

    if st.button("🎨 Generate Image", key="img-generate"):
        if not prompt.strip():
            st.warning("Describe the image you want.", icon="⚠️")
            return
        with st.spinner("Painting your vision…"):
            encoded = urllib.parse.quote(prompt.strip())
            url = POLLINATIONS_URL.format(prompt=encoded)
            params = {"width": width, "height": height, "model": model,
                      "nologo": "true", "seed": int(time.time())}
            token = st.session_state.get("img_key", "").strip()
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            try:
                resp = requests.get(url, params=params, headers=headers, timeout=120)
                resp.raise_for_status()
                st.session_state["img_bytes"] = resp.content
                st.session_state["img_caption"] = prompt.strip()
                save_image_to_gallery(resp.content, prompt.strip())
            except requests.exceptions.RequestException as exc:
                st.error(f"Image generation failed: {exc}")
                return

    if st.session_state.get("img_bytes"):
        st.image(st.session_state["img_bytes"],
                 caption=st.session_state.get("img_caption", ""),
                 use_container_width=True)
        st.download_button("⬇️ Download image", data=st.session_state["img_bytes"],
                           file_name="jarvis-image.png", mime="image/png",
                           key="img-download")

    # ---- saved gallery ----
    gallery = load_gallery()
    if gallery:
        st.divider()
        st.markdown(f"#### 🖼️ Your Gallery ({len(gallery)})")
        cols = st.columns(3)
        for idx, item in enumerate(gallery):
            with cols[idx % 3]:
                st.image(item["bytes"], caption=item.get("prompt", "")[:60],
                         use_container_width=True)
                st.download_button("⬇️", data=item["bytes"],
                                   file_name=f"jarvis-{idx}.png", mime="image/png",
                                   key=f"gal-dl-{idx}")


# ----------------------------------------------------------------------------- #
#  Workspace 5 — Project Agent (Planner -> Coder)
# ----------------------------------------------------------------------------- #

def _parse_files(raw: str) -> List[dict]:
    """Parse the coder output of the form:  === path ===\n```lang\ncode``` ."""
    import re
    files = []
    pattern = re.compile(r"===\s*(.+?)\s*===\s*```[a-zA-Z0-9]*\n(.*?)```", re.DOTALL)
    for match in pattern.finditer(raw):
        files.append({"path": match.group(1).strip(), "code": match.group(2).strip()})
    return files


def _extract_html(raw: str) -> str:
    """Pull a full self-contained HTML document out of an LLM reply."""
    import re
    fence = re.search(r"```(?:html)?\s*(<!DOCTYPE html.*?</html>)\s*```", raw,
                      re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    doc = re.search(r"(<!DOCTYPE html.*?</html>)", raw, re.DOTALL | re.IGNORECASE)
    if doc:
        return doc.group(1).strip()
    return raw.strip()


def generate_live_app(idea: str, refine: str = "", current_html: str = "") -> str:
    """Generate/iterate a single-file, self-contained, runnable web app (HTML+CSS+JS)."""
    sys = ("You are an elite full-stack engineer. Build a COMPLETE, production-quality, "
           "SELF-CONTAINED single-file web app as ONE HTML document with inline <style> and "
           "<script> (vanilla JS, no external build step). It must actually WORK when opened: "
           "real interactivity, sensible sample data, polished modern UI, responsive layout. "
           "You MAY use CDN links (e.g. Tailwind via CDN, Chart.js, font CDNs). "
           "Return ONLY the HTML document from <!DOCTYPE html> to </html>. No commentary.")
    if refine and current_html:
        user = (f"Here is the current app:\n```html\n{current_html[:6000]}\n```\n\n"
                f"Apply this change and return the full updated HTML document:\n{refine}")
    else:
        user = f"App idea: {idea}\n\nBuild the full working app now."
    raw = llm_chat([{"role": "system", "content": sys},
                    {"role": "user", "content": user}], temperature=0.4, max_tokens=4000)
    return _extract_html(raw)


def _render_live_preview(html: str, height: int = 520) -> None:
    import streamlit.components.v1 as components
    components.html(html, height=height, scrolling=True)


def _fullscreen_button(html: str) -> None:
    """Render an anchor that opens the generated app in a new full-screen browser tab."""
    import streamlit.components.v1 as components
    b64 = base64.b64encode(html.encode("utf-8")).decode("ascii")
    components.html(
        f"""
        <a href="data:text/html;base64,{b64}" target="_blank" rel="noopener"
           style="display:inline-block;padding:.55rem 1rem;border-radius:12px;
                  background:linear-gradient(135deg,#00f5d4,#7b61ff);color:#04070b;
                  font-family:sans-serif;font-weight:700;text-decoration:none;">
            ⛶ Open full-screen preview
        </a>
        """,
        height=60,
    )


def deploy_configs(idea: str) -> dict:
    """Return static-hosting deploy config files for the generated single-file app."""
    return {
        "netlify.toml": (
            "# Netlify config for a static single-file app\n"
            "[build]\n  publish = \".\"\n\n"
            "[[redirects]]\n  from = \"/*\"\n  to = \"/index.html\"\n  status = 200\n"
        ),
        "vercel.json": json.dumps({
            "version": 2,
            "builds": [{"src": "index.html", "use": "@vercel/static"}],
            "routes": [{"src": "/(.*)", "dest": "/index.html"}],
        }, indent=2),
        "DEPLOY.md": (
            f"# Deploying \"{idea[:60]}\"\n\n"
            "This is a self-contained static app (`index.html`). Deploy in seconds:\n\n"
            "## Netlify (drag & drop)\n"
            "1. Go to https://app.netlify.com/drop\n"
            "2. Drag the folder (with `index.html` + `netlify.toml`) onto the page. Done.\n\n"
            "## Netlify (CLI)\n```bash\nnpm i -g netlify-cli\nnetlify deploy --prod --dir .\n```\n\n"
            "## Vercel (CLI)\n```bash\nnpm i -g vercel\nvercel --prod\n```\n\n"
            "Both host the app for free on a public URL.\n"
        ),
    }


def workspace_project() -> None:
    st.subheader("🚀 Project Agent — Live App Builder")
    st.caption("Drop an idea. Watch Jarvis plan, build and render a WORKING app live — "
               "then download the production files.")

    idea = st.text_area("Your app idea",
                        placeholder="e.g. A habit tracker with streaks, charts and dark mode",
                        height=90, key="proj-idea")

    if st.button("🤖 Build it live", key="proj-run"):
        if not idea.strip():
            st.warning("Describe your idea first.", icon="⚠️")
            return

        progress = st.progress(0, text="Starting agents…")

        # Agent 1 — Planner (Expected spec)
        with st.status("🧭 Planner — designing the spec…", expanded=True) as status:
            plan = llm_chat([
                {"role": "system",
                 "content": "You are a senior product architect. Produce a crisp spec for the app: "
                            "purpose, key features (bullet list), main UI sections, and tech notes. "
                            "This is the EXPECTED outcome. Be concise."},
                {"role": "user", "content": f"App idea: {idea}"},
            ], temperature=0.4)
            st.markdown(plan)
            status.update(label="✅ Spec ready (Expected)", state="complete")
        st.session_state["proj_plan"] = plan
        progress.progress(35, text="Spec ready — building the working app…")

        # Agent 2 — Builder (live working app)
        with st.status("👨‍💻 Builder — writing a working app…", expanded=False) as status:
            html = generate_live_app(idea)
            status.update(label="✅ Working app built (Current)", state="complete")
        st.session_state["live_app_html"] = html
        progress.progress(80, text="Rendering live preview…")

        # Agent 3 — Packager (production multi-file)
        with st.status("📦 Packager — production files…", expanded=False) as status:
            code_raw = llm_chat([
                {"role": "system",
                 "content": "You are an expert engineer. Turn the app into a COMPLETE runnable "
                            "project folder: all source files, a dependency manifest, and a "
                            "README.md (Overview, Setup, Run). Output EACH file STRICTLY as:\n"
                            "=== relative/path/file.ext ===\n```lang\n<code>\n```\n"
                            "No prose outside the blocks."},
                {"role": "user", "content": f"Idea: {idea}\n\nSpec:\n{plan}\n\n"
                                             f"Reference working app:\n{html[:3000]}"},
            ], temperature=0.3, max_tokens=3500)
            status.update(label="✅ Production files ready", state="complete")
        st.session_state["proj_files"] = _parse_files(code_raw)
        st.session_state["proj_raw"] = code_raw
        progress.progress(100, text="Done!")
        st.session_state["active_app_id"] = save_app(idea, plan, html)

    # ---- Current vs Expected + live preview ----
    if st.session_state.get("live_app_html"):
        st.divider()
        st.markdown("### 🔴 Live Preview — Current vs Expected")
        left, right = st.columns([3, 2])
        with left:
            st.markdown("**🟢 Current (working app)**")
            _render_live_preview(st.session_state["live_app_html"])
            lc1, lc2 = st.columns(2)
            with lc1:
                st.download_button("⬇️ Download index.html",
                                   data=st.session_state["live_app_html"],
                                   file_name="index.html", mime="text/html",
                                   use_container_width=True, key="live-html-dl")
            with lc2:
                _fullscreen_button(st.session_state["live_app_html"])
        with right:
            st.markdown("**🎯 Expected (spec)**")
            with st.container(border=True, height=520):
                st.markdown(st.session_state.get("proj_plan", "_No spec yet._"))

        # ---- live iteration ----
        st.markdown("#### ✏️ Refine the app (updates the live preview)")
        refine = st.text_input("Describe a change",
                               placeholder="e.g. add a dark mode toggle and a summary chart",
                               key="proj-refine")
        if st.button("🔁 Apply change & re-render", key="proj-refine-btn"):
            if refine.strip():
                with st.status("👨‍💻 Applying your change…", expanded=False) as status:
                    st.session_state["live_app_html"] = generate_live_app(
                        idea, refine, st.session_state["live_app_html"])
                    status.update(label="✅ Updated — preview refreshed", state="complete")
                st.session_state["active_app_id"] = save_app(
                    idea, st.session_state.get("proj_plan", ""),
                    st.session_state["live_app_html"], st.session_state.get("active_app_id", ""))
                st.rerun()

        # ---- deploy helper ----
        with st.expander("🚀 Deploy this app (Netlify / Vercel)"):
            st.caption("Your app is a self-contained static file — deploy it free in seconds.")
            cfgs = deploy_configs(idea)
            dbuf = io.BytesIO()
            with zipfile.ZipFile(dbuf, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("index.html", st.session_state["live_app_html"])
                for fname, content in cfgs.items():
                    zf.writestr(fname, content)
            st.download_button("⬇️ Download deploy bundle (.zip)", data=dbuf.getvalue(),
                               file_name="jarvis-deploy.zip", mime="application/zip",
                               key="deploy-zip")
            st.markdown("**Netlify:** drag the unzipped folder onto "
                        "[app.netlify.com/drop](https://app.netlify.com/drop) — instant live URL.")
            st.markdown("**Vercel:** run `vercel --prod` inside the unzipped folder.")
            for fname, content in cfgs.items():
                with st.popover(f"📄 {fname}"):
                    st.code(content, language="json" if fname.endswith(".json") else "text")

    # ---- production files ----
    if st.session_state.get("proj_files"):
        files = st.session_state["proj_files"]
        st.divider()
        head = st.columns([3, 1])
        head[0].markdown(f"#### 📦 Production files ({len(files)})")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                zf.writestr(f["path"], f["code"])
            if st.session_state.get("proj_plan"):
                zf.writestr("PLAN.md", st.session_state["proj_plan"])
            if st.session_state.get("live_app_html"):
                zf.writestr("preview/index.html", st.session_state["live_app_html"])
        head[1].download_button("⬇️ Download ZIP", data=buf.getvalue(),
                                file_name="jarvis-project.zip", mime="application/zip",
                                use_container_width=True, key="proj-zip")

        readme = next((f for f in files if f["path"].lower().endswith("readme.md")), None)
        if readme:
            with st.expander("📖 Setup & Run instructions", expanded=False):
                st.markdown(readme["code"])

        for f in files:
            with st.expander(f"📄 {f['path']}"):
                lang = f["path"].split(".")[-1] if "." in f["path"] else "text"
                st.code(f["code"], language=lang)
                st.download_button("⬇️ Download", data=f["code"],
                                   file_name=f["path"].split("/")[-1],
                                   key=f"dl-{f['path']}")

    # ---- saved apps gallery ----
    apps = load_apps()
    if apps:
        st.divider()
        st.markdown(f"#### 🗂️ Your Apps ({len(apps)})")
        st.caption("Reopen any app to keep iterating on it.")
        for a in apps:
            with st.container(border=True):
                ac1, ac2, ac3 = st.columns([3, 1, 1])
                ac1.markdown(f"**{a['idea'][:70]}**  \n_{a['time'][:16].replace('T',' ')} UTC_")
                if ac2.button("📂 Open", key=f"app-open-{a['id']}", use_container_width=True):
                    st.session_state["live_app_html"] = a["html"]
                    st.session_state["proj_plan"] = a.get("spec", "")
                    st.session_state["active_app_id"] = a["id"]
                    st.session_state["proj-idea"] = a["idea"]
                    st.rerun()
                if ac3.button("🗑️ Delete", key=f"app-del-{a['id']}", use_container_width=True):
                    delete_app(a["id"])
                    st.rerun()


# ----------------------------------------------------------------------------- #
#  Workspace 6 — Self-Upgrade Center (self-heal / bug-fix / evolve)
# ----------------------------------------------------------------------------- #

JARVIS_CAPABILITIES = (
    "Jarvis Personal OS — a Streamlit app with: Google OAuth login; AI Chat & Rewriter "
    "(Groq/SambaNova Llama-3.3-70B) with voice input and read-aloud; Email Generator with "
    "saved templates; Smart Web Research (DuckDuckGo) with PDF export, history, tags & pins; "
    "Image Generator (Pollinations) with a saved gallery; a live App Builder (Planner->Builder"
    "->Packager) with real-time preview; and a Self-Upgrade Center with preview/rollback."
)


def _extract_json(raw: str):
    import re
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return []
    try:
        return json.loads(match.group(0))
    except ValueError:
        return []


def run_upgrade_scan(focus: str = "") -> List[dict]:
    """Gather free web intel + reason with the LLM. Returns a list of proposals."""
    queries = [
        "latest Streamlit features 2026",
        "best free python AI libraries 2026",
        f"improve {focus}" if focus.strip() else "AI assistant app improvement ideas",
    ]
    findings = []
    for q in queries:
        try:
            findings += web_search(q, max_results=3)
        except Exception:  # noqa: BLE001
            continue
    snippets = "\n".join(f"- {r.get('title','')}: {r.get('body','')[:200]}"
                         for r in findings) or "No web data available."
    raw = llm_chat([
        {"role": "system",
         "content": "You are Jarvis's self-improvement engine. Given the app's current "
                    "capabilities and fresh web findings, propose 3-4 concrete upgrades. "
                    "Return ONLY a JSON array. Each item: "
                    '{"title": str, "type": "Bug Fix"|"Upgrade"|"New Capability", '
                    '"rationale": str, "change": str, "code": str}. '
                    "The 'code' is a short Python/Streamlit snippet to apply the idea."},
        {"role": "user",
         "content": f"App capabilities:\n{JARVIS_CAPABILITIES}\n\n"
                    f"Focus: {focus or 'general'}\n\nWeb findings:\n{snippets}"},
    ], temperature=0.5, max_tokens=2500)
    return _extract_json(raw)


def maybe_auto_scan() -> None:
    """Run a background scan on a schedule if enabled and the interval has elapsed."""
    settings = load_settings()
    if not settings.get("auto_scan") or not st.session_state.get("llm_key"):
        return
    if st.session_state.get("_auto_scanned"):
        return
    now = datetime.now(timezone.utc)
    last = settings.get("last_scan")
    due = True
    if last:
        try:
            elapsed = (now - datetime.fromisoformat(last)).total_seconds() / 3600
            due = elapsed >= settings.get("interval_hours", 24)
        except ValueError:
            due = True
    st.session_state["_auto_scanned"] = True
    if not due:
        return
    proposals = run_upgrade_scan()
    if proposals:
        existing = load_pending()
        titles = {p.get("title") for p in existing}
        merged = existing + [p for p in proposals if p.get("title") not in titles]
        save_pending(merged)
        st.toast(f"🔔 Jarvis found {len(proposals)} upgrade idea(s) to review!", icon="🧬")
    settings["last_scan"] = now.isoformat()
    save_settings(settings)

    # optional weekly digest email (needs SMTP password held in this session)
    pw = st.session_state.get("digest-pw", "")
    if settings.get("digest_email") and pw and settings.get("smtp_user") and settings.get("digest_to"):
        last_digest = settings.get("last_digest")
        send_due = True
        if last_digest:
            try:
                send_due = (now - datetime.fromisoformat(last_digest)).days >= 7
            except ValueError:
                send_due = True
        pending = load_pending()
        if send_due and pending:
            ok, _ = send_digest_email(settings["smtp_host"], settings["smtp_port"],
                                      settings["smtp_user"], pw, settings["digest_to"],
                                      build_digest_text(pending))
            if ok:
                settings["last_digest"] = now.isoformat()
                save_settings(settings)
                st.toast("📧 Weekly upgrade digest emailed to you!", icon="📧")


def workspace_upgrade() -> None:
    st.subheader("🛠️ Self-Upgrade Center")
    st.caption("Jarvis researches the live web to propose fixes & upgrades. "
               "Nothing changes without YOUR approval.")

    st.info("Jarvis gathers ideas from free public sources, then reasons about how to improve "
            "itself. Each proposal is a suggestion you can **Approve** or **Deny** — approved "
            "items are logged with ready-to-apply code. Jarvis never edits its own code "
            "automatically.", icon="🧬")

    # ---- auto-scan schedule ----
    settings = load_settings()
    with st.expander("⏰ Auto-scan schedule", expanded=False):
        a1, a2 = st.columns([1, 1])
        auto = a1.toggle("Enable auto-scan", value=settings.get("auto_scan", False),
                         key="auto-scan-toggle")
        interval = a2.selectbox("Check every", [6, 12, 24, 48, 168],
                                index=[6, 12, 24, 48, 168].index(settings.get("interval_hours", 24)),
                                format_func=lambda h: f"{h} hours" if h < 168 else "1 week",
                                key="auto-scan-interval")
        if auto != settings.get("auto_scan") or interval != settings.get("interval_hours"):
            settings.update({"auto_scan": auto, "interval_hours": interval})
            save_settings(settings)
        if settings.get("last_scan"):
            st.caption(f"Last auto-scan: {settings['last_scan'][:16].replace('T',' ')} UTC")
        st.caption("Auto-scan runs quietly when you open the app after the interval elapses, "
                   "then notifies you here.")

    with st.expander("📧 Weekly digest email", expanded=False):
        st.caption("Have Jarvis email you a summary of new upgrade proposals (uses your SMTP, "
                   "e.g. Gmail with an App Password). Password is kept only in this session.")
        d_on = st.toggle("Email me a weekly digest", value=settings.get("digest_email", False),
                         key="digest-toggle")
        dc1, dc2 = st.columns(2)
        host = dc1.text_input("SMTP host", value=settings.get("smtp_host", "smtp.gmail.com"),
                              key="digest-host")
        port = dc2.number_input("Port", value=int(settings.get("smtp_port", 587)),
                                key="digest-port")
        user = dc1.text_input("From email", value=settings.get("smtp_user", ""),
                              key="digest-user", placeholder="you@gmail.com")
        to_addr = dc2.text_input("Send to", value=settings.get("digest_to", ""),
                                 key="digest-to", placeholder="you@gmail.com")
        pw = st.text_input("SMTP password / app password", type="password", key="digest-pw")
        if (d_on != settings.get("digest_email") or host != settings.get("smtp_host")
                or int(port) != settings.get("smtp_port") or user != settings.get("smtp_user")
                or to_addr != settings.get("digest_to")):
            settings.update({"digest_email": d_on, "smtp_host": host, "smtp_port": int(port),
                             "smtp_user": user, "digest_to": to_addr})
            save_settings(settings)
        if st.checkbox("👁️ Preview digest content", key="digest-preview"):
            items = load_pending()
            if items:
                st.code(build_digest_text(items), language="text")
            else:
                st.info("No pending proposals to summarise yet.")
        if st.button("📧 Send digest now", key="digest-send"):
            items = load_pending()
            if not items:
                st.info("No pending proposals to summarise yet.")
            elif not (host and user and to_addr and pw):
                st.warning("Fill SMTP host, from, to and password first.", icon="⚠️")
            else:
                ok, msg = send_digest_email(host, int(port), user, pw, to_addr,
                                            build_digest_text(items))
                if ok:
                    settings["last_digest"] = datetime.now(timezone.utc).isoformat()
                    save_settings(settings)
                    st.success(f"Digest sent to {to_addr}!")
                else:
                    st.error(f"Send failed: {msg}")
        if settings.get("last_digest"):
            st.caption(f"Last digest sent: {settings['last_digest'][:16].replace('T',' ')} UTC")

    mode = st.radio("Mode", ["🔍 Scan for upgrades", "🩺 Self-heal (fix an error)"],
                    horizontal=True, key="upg-mode")

    if mode == "🔍 Scan for upgrades":
        focus = st.text_input("Focus area (optional)", key="upg-focus",
                              placeholder="e.g. faster image generation, better research accuracy")
        if st.button("🔍 Scan the web & propose upgrades", key="upg-scan"):
            with st.spinner("Gathering intel & reasoning about self-improvements…"):
                proposals = run_upgrade_scan(focus)
            existing = load_pending()
            titles = {p.get("title") for p in existing}
            save_pending(existing + [p for p in proposals if p.get("title") not in titles])
            if not proposals:
                st.warning("Couldn't parse proposals. Try again or add an LLM key.")

    else:  # Self-heal
        err = st.text_area("Paste an error message / traceback", key="upg-err", height=140,
                           placeholder="Paste the Python traceback or bug description here…")
        if st.button("🩺 Diagnose & propose a fix", key="upg-heal"):
            if not err.strip():
                st.warning("Paste the error first.", icon="⚠️")
            else:
                with st.spinner("Diagnosing…"):
                    raw = llm_chat([
                        {"role": "system",
                         "content": "You are Jarvis's self-healing engine. Diagnose the error and "
                                    "return ONLY a JSON array with ONE item: "
                                    '{"title": str, "type": "Bug Fix", "rationale": str, '
                                    '"change": str, "code": str} where code is the corrected snippet.'},
                        {"role": "user",
                         "content": f"App:\n{JARVIS_CAPABILITIES}\n\nError:\n{err}"},
                    ], temperature=0.2, max_tokens=1800)
                fix = _extract_json(raw)
                save_pending(load_pending() + fix)

    # ---- render proposals with approve/deny (+ personal note) ----
    proposals = load_pending()
    if proposals:
        st.markdown(f"#### 📋 Proposals awaiting your decision ({len(proposals)})")
        badge = {"Bug Fix": "🐞", "Upgrade": "⬆️", "New Capability": "✨"}
        for idx, p in enumerate(list(proposals)):
            with st.container(border=True):
                st.markdown(f"**{badge.get(p.get('type'),'🔧')} {p.get('title','Untitled')}** "
                            f"· _{p.get('type','')}_")
                st.markdown(f"**Why:** {p.get('rationale','')}")
                st.markdown(f"**Change:** {p.get('change','')}")
                if p.get("code"):
                    st.code(p["code"], language="python")
                note = st.text_input("📝 Add a note (optional)", key=f"upg-note-{idx}",
                                     placeholder="Why you're approving/denying — for future you")
                c1, c2 = st.columns(2)
                if c1.button("✅ Approve", key=f"upg-appr-{idx}", use_container_width=True):
                    log = load_upgrade_log()
                    log.insert(0, {**p, "status": "approved", "note": note,
                                   "time": datetime.now(timezone.utc).isoformat()})
                    save_upgrade_log(log)
                    save_pending([x for i, x in enumerate(proposals) if i != idx])
                    st.toast(f"Approved: {p.get('title','')}", icon="✅")
                    st.rerun()
                if c2.button("❌ Deny", key=f"upg-deny-{idx}", use_container_width=True):
                    log = load_upgrade_log()
                    log.insert(0, {**p, "status": "denied", "note": note,
                                   "time": datetime.now(timezone.utc).isoformat()})
                    save_upgrade_log(log)
                    save_pending([x for i, x in enumerate(proposals) if i != idx])
                    st.toast(f"Denied: {p.get('title','')}", icon="❌")
                    st.rerun()

    # ---- changelog ----
    log = load_upgrade_log()
    if log:
        st.divider()
        approved = [x for x in log if x["status"] == "approved"]
        st.markdown(f"#### 🧬 Evolution Log  ·  {len(approved)} approved / {len(log)} total")
        if approved:
            patch = "\n\n".join(
                f"# === {x['title']} ({x['type']}) — {x['time'][:10]} ===\n"
                f"# note: {x.get('note','') or '-'}\n{x.get('code','')}"
                for x in approved)
            st.download_button("⬇️ Download approved upgrades patch", data=patch,
                               file_name="jarvis_upgrades.py", mime="text/x-python",
                               key="upg-patch")

            # ---- Apply to a safe preview copy ----
            st.markdown("##### 🧪 Apply to a safe preview")
            st.caption("Stage all approved upgrades into `app_preview.py` — run and test it "
                       "before promoting it to your live app.")
            pc1, pc2 = st.columns(2)
            if pc1.button("🧪 Build preview copy", key="upg-build-preview",
                          use_container_width=True):
                path = build_preview_copy(approved)
                st.session_state["preview_built"] = True
                st.success(f"Preview built → `{os.path.basename(path)}`. "
                           "Test it with `streamlit run app_preview.py`.")
            if st.session_state.get("preview_built"):
                with st.expander("🔍 Diff viewer — preview vs live app"):
                    diff_html = build_preview_diff()
                    if diff_html:
                        import streamlit.components.v1 as components
                        components.html(
                            "<style>table.diff{font-family:monospace;font-size:12px;width:100%}"
                            ".diff_header{background:#1e2937;color:#7d8896}"
                            "td{padding:1px 6px}.diff_next{background:#141b26}"
                            ".diff_add{background:#0f3a2f;color:#00f5d4}"
                            ".diff_chg{background:#3a340f;color:#ffd166}"
                            ".diff_sub{background:#3a0f1e;color:#ff6b81}</style>" + diff_html,
                            height=460, scrolling=True)
                    else:
                        st.info("Build a preview first to see the diff.")
                with st.popover("🚀 Promote preview to live", use_container_width=True):
                    st.warning("This replaces your live `app.py` (a timestamped backup is saved "
                               "first). The app will reload.", icon="⚠️")
                    label = st.text_input("Label this backup (optional)", key="promote-label",
                                          placeholder="e.g. before dark-mode change")
                    if st.checkbox("I've previewed it and want to go live", key="promote-confirm"):
                        if st.button("Confirm promote", key="promote-go"):
                            ok, info = promote_preview_to_live()
                            if ok:
                                if label.strip():
                                    set_backup_label(os.path.basename(info), label.strip())
                                st.success(f"Live app updated. Backup: `{os.path.basename(info)}`")
                            else:
                                st.error(info)
        for x in log:
            icon = "✅" if x["status"] == "approved" else "❌"
            with st.expander(f"{icon} {x.get('title','')}  ·  {x['time'][:10]}"):
                st.markdown(f"**Type:** {x.get('type','')}  \n**Why:** {x.get('rationale','')}")
                if x.get("note"):
                    st.markdown(f"📝 **Your note:** {x['note']}")
                if x.get("code"):
                    st.code(x["code"], language="python")
        if st.button("🗑️ Clear evolution log", key="upg-clear"):
            save_upgrade_log([])
            st.rerun()

    # ---- rollback: restore any previous app.py backup ----
    backups = list_backups()
    if backups:
        st.divider()
        st.markdown(f"#### ↩️ Rollback  ·  {len(backups)} backup(s)")
        st.caption("Restore your live app to any previous version. The current app is snapshotted "
                   "before restoring, so you can always go back.")
        for b in backups:
            with st.container(border=True):
                title = f"🏷️ **{b['label']}**  ·  " if b["label"] else "🗄️ "
                rc1, rc2 = st.columns([3, 1])
                rc1.markdown(f"{title}{b['when']}  ·  {b['size']//1000} KB")
                if rc2.button("↩️ Restore", key=f"rollback-{b['name']}", use_container_width=True):
                    ok, msg = restore_backup(b["path"])
                    if ok:
                        st.success(f"Restored to {b['when']}. App will reload.")
                    else:
                        st.error(msg)
                lc1, lc2 = st.columns([3, 1])
                new_label = lc1.text_input("Label", value=b["label"], key=f"blabel-{b['name']}",
                                           label_visibility="collapsed",
                                           placeholder="Name this backup…")
                if lc2.button("Save", key=f"blabel-save-{b['name']}", use_container_width=True):
                    set_backup_label(b["name"], new_label.strip())
                    st.rerun()


# ----------------------------------------------------------------------------- #
#  Main
# ----------------------------------------------------------------------------- #

def main() -> None:
    if not is_authenticated():
        login_screen()
        return

    inject_css()
    render_sidebar()
    maybe_auto_scan()

    st.markdown(f"<div class='jv-hero'>Command Center</div>", unsafe_allow_html=True)
    st.markdown(f"<p class='jv-muted'>Welcome back, {getattr(st.user,'name','')}. "
                "Pick a workspace below.</p>", unsafe_allow_html=True)

    pending = load_pending()
    upgrade_label = f"🛠️ Self-Upgrade ({len(pending)})" if pending else "🛠️ Self-Upgrade"
    tabs = st.tabs([
        "💬 AI Chat", "✉️ Email", "🔎 Research", "🖼️ Images",
        "🚀 Project Agent", upgrade_label,
    ])
    with tabs[0]:
        workspace_chat()
    with tabs[1]:
        workspace_email()
    with tabs[2]:
        workspace_research()
    with tabs[3]:
        workspace_image()
    with tabs[4]:
        workspace_project()
    with tabs[5]:
        workspace_upgrade()


if __name__ == "__main__":
    main()
