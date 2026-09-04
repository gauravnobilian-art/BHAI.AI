# 🤖 Jarvis Personal OS

A premium, secure daily assistant built with **Streamlit** — your private command
center for AI chat, live web research, email drafting, image generation and
project scaffolding. Designed to run on your custom domain **https://apnabihar.online**.

![theme](https://img.shields.io/badge/theme-dark%20%2B%20neon-00f5d4) ![python](https://img.shields.io/badge/python-3.10%2B-7b61ff)

---

## ✨ Features

| Workspace | What it does |
|-----------|--------------|
| 💬 **AI Chat & Rewriter** | Streaming chat + saved history + voice input & read-aloud + 1-click rewrite presets |
| ✉️ **Email Generator** | Recipient + goal + tone → formatted draft, with saveable ⭐ templates |
| 🔎 **Smart Web Research** | Live DuckDuckGo search → cited summary, PDF export + searchable history |
| 🖼️ **Image Generator** | Free & unlimited Pollinations images + persistent gallery |
| 🚀 **Project Agent** | Live App Builder: Planner→Builder→Packager with a **real-time working preview** (Current vs Expected), inline iteration, and production ZIP |
| 🛠️ **Self-Upgrade Center** | Web-researched upgrade proposals you approve/deny, weekly email digest, safe preview + diff, promote-to-live and one-click rollback |

- 🔐 **Google login wall** — nobody reaches the app without signing in.
- 🧠 Free **Llama-3.3-70B** brain via **Groq** or **SambaNova** (pick in sidebar).
- 🎨 Minimalist dark UI with neon accents.

---

## 🚀 Quick start (local)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure Google OAuth
mkdir -p .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
#   → edit .streamlit/secrets.toml and paste your Google Client ID / Secret
#   → generate a cookie_secret:
python -c "import secrets; print(secrets.token_hex(32))"

# 3. Run
streamlit run app.py
```

Open http://localhost:8501

---

## 🌐 Deploy on your custom domain (apnabihar.online)

1. **Google Cloud Console → Credentials → OAuth client ID (Web application).**
   Add this **exact** authorized redirect URI:
   ```
   https://apnabihar.online/oauth2callback
   ```
2. Put the same values in your production `.streamlit/secrets.toml`
   (`redirect_uri = "https://apnabihar.online/oauth2callback"`).
3. Run behind HTTPS on your server (e.g. Nginx reverse-proxy → `streamlit run app.py`
   on port 8501). Ensure your domain's SSL is valid.
4. Restart the app. The **Sign in with Google** button now returns users to your domain.

---

## 🔑 API keys (entered in the sidebar at runtime — never stored)

| Key | Where to get it | Free? |
|-----|-----------------|-------|
| Groq API key | https://console.groq.com/keys | ✅ |
| SambaNova API key | https://cloud.sambanova.ai/apis | ✅ |
| Pollinations | not required | ✅ |

---

## 🗂️ Project structure

```
.
├── app.py                          # full application (modular sections)
├── requirements.txt                # exact dependencies
├── README.md
└── .streamlit/
    ├── config.toml                 # dark + neon theme
    └── secrets.toml.example        # OAuth template → copy to secrets.toml
```

## 🔒 Security notes
- Login uses Streamlit's native **OIDC** auth (Authlib) — profile is kept only in
  session state and cleared on logout.
- API keys are masked password inputs held in session memory, never written to disk.
