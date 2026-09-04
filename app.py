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


# ----------------------------------------------------------------------------- #
#  Text-to-speech  (free, in-browser SpeechSynthesis)
# ----------------------------------------------------------------------------- #

def speak(text: str) -> None:
    import streamlit.components.v1 as components
    payload = json.dumps(text[:3000])
    components.html(
        f"""
        <script>
            const u = new SpeechSynthesisUtterance({payload});
            u.rate = 1.02; u.pitch = 1.0;
            window.speechSynthesis.cancel();
            window.speechSynthesis.speak(u);
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

        st.divider()
        status = "🟢 Online" if st.session_state.get("llm_key") else "🔴 Add key"
        st.markdown(f"**Brain status:** {status}")


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


def workspace_project() -> None:
    st.subheader("🚀 Project Agent (Mini-Emergent)")
    st.caption("Drop an idea. A Planner agent designs it, then a Coder agent writes the files.")

    idea = st.text_area("Your software idea",
                        placeholder="e.g. A CLI tool that converts CSV files to a nice HTML report",
                        height=110, key="proj-idea")

    if st.button("🤖 Activate Agents", key="proj-run"):
        if not idea.strip():
            st.warning("Describe your idea first.", icon="⚠️")
            return

        # Agent 1 — Planner
        with st.status("🧭 Planner agent designing the architecture…", expanded=True) as status:
            plan = llm_chat([
                {"role": "system",
                 "content": "You are a senior software architect. Produce a crisp technical "
                            "plan: tech stack, file structure, and what each file does. "
                            "Be concise and actionable."},
                {"role": "user", "content": f"Project idea: {idea}"},
            ], temperature=0.4)
            st.markdown(plan)
            status.update(label="✅ Planner finished", state="complete")
        st.session_state["proj_plan"] = plan

        # Agent 2 — Coder
        with st.status("👨‍💻 Coder agent writing the files…", expanded=False) as status:
            code_raw = llm_chat([
                {"role": "system",
                 "content": "You are an expert engineer. Implement the plan as a COMPLETE, "
                            "RUNNABLE project folder. You MUST include:\n"
                            "  - all source files\n"
                            "  - a dependency manifest (requirements.txt / package.json)\n"
                            "  - a README.md with an Overview, Setup steps, and Run commands\n"
                            "Output EACH file STRICTLY in this format and nothing else:\n"
                            "=== relative/path/file.ext ===\n```lang\n<code>\n```\n"
                            "Repeat for every file. No prose outside the blocks."},
                {"role": "user", "content": f"Idea: {idea}\n\nPlan:\n{plan}"},
            ], temperature=0.3, max_tokens=3500)
            status.update(label="✅ Coder finished", state="complete")
        st.session_state["proj_files"] = _parse_files(code_raw)
        st.session_state["proj_raw"] = code_raw

    if st.session_state.get("proj_files"):
        files = st.session_state["proj_files"]
        head = st.columns([3, 1])
        head[0].markdown(f"#### 📦 Generated files ({len(files)})")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                zf.writestr(f["path"], f["code"])
            if st.session_state.get("proj_plan"):
                zf.writestr("PLAN.md", st.session_state["proj_plan"])
        head[1].download_button("⬇️ Download ZIP", data=buf.getvalue(),
                                file_name="jarvis-project.zip", mime="application/zip",
                                use_container_width=True, key="proj-zip")

        readme = next((f for f in files if f["path"].lower().endswith("readme.md")), None)
        if readme:
            with st.expander("📖 Setup & Run instructions", expanded=True):
                st.markdown(readme["code"])

        for f in files:
            with st.expander(f"📄 {f['path']}"):
                lang = f["path"].split(".")[-1] if "." in f["path"] else "text"
                st.code(f["code"], language=lang)
                st.download_button("⬇️ Download", data=f["code"],
                                   file_name=f["path"].split("/")[-1],
                                   key=f"dl-{f['path']}")
    elif st.session_state.get("proj_raw"):
        st.markdown("#### 📦 Coder output")
        st.code(st.session_state["proj_raw"])


# ----------------------------------------------------------------------------- #
#  Main
# ----------------------------------------------------------------------------- #

def main() -> None:
    if not is_authenticated():
        login_screen()
        return

    inject_css()
    render_sidebar()

    st.markdown(f"<div class='jv-hero'>Command Center</div>", unsafe_allow_html=True)
    st.markdown(f"<p class='jv-muted'>Welcome back, {getattr(st.user,'name','')}. "
                "Pick a workspace below.</p>", unsafe_allow_html=True)

    tabs = st.tabs([
        "💬 AI Chat", "✉️ Email", "🔎 Research", "🖼️ Images", "🚀 Project Agent",
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


if __name__ == "__main__":
    main()
