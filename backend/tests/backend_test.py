"""Jarvis Personal OS - backend API tests (pytest)."""
import os
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

LONG = 180


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# --- Health / root ---
class TestHealth:
    def test_root(self, client):
        r = client.get(f"{BASE_URL}/api/", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["message"] == "Jarvis Personal OS API"
        assert d["ai"] is True

    def test_api_health(self, client):
        r = client.get(f"{BASE_URL}/api/health", timeout=30)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# --- Chat (LLM) ---
class TestChat:
    def test_chat_basic(self, client):
        r = client.post(f"{BASE_URL}/api/chat", json={
            "messages": [{"role": "user", "content": "Say only the word PONG"}],
            "style": ""}, timeout=LONG)
        assert r.status_code == 200
        reply = r.json()["reply"]
        assert isinstance(reply, str) and len(reply) > 0
        assert "AI error" not in reply and "not configured" not in reply, reply

    def test_chat_style_summarize(self, client):
        r = client.post(f"{BASE_URL}/api/chat", json={
            "messages": [{"role": "user", "content":
                          "Cats are mammals. They sleep a lot. They hunt mice. They purr."}],
            "style": "summarize"}, timeout=LONG)
        assert r.status_code == 200
        reply = r.json()["reply"]
        assert "AI error" not in reply, reply
        assert len(reply) > 10

    def test_chat_empty_messages(self, client):
        # Fixed in iteration_3: empty messages must be rejected with 400
        r = client.post(f"{BASE_URL}/api/chat", json={"messages": []}, timeout=LONG)
        assert r.status_code == 400, r.text
        assert "No messages" in r.json().get("detail", "")

    def test_chat_validation_error(self, client):
        r = client.post(f"{BASE_URL}/api/chat", json={"style": "professional"}, timeout=30)
        assert r.status_code == 422


# --- Email ---
class TestEmail:
    def test_email_generate(self, client):
        r = client.post(f"{BASE_URL}/api/email", json={
            "recipient": "Hiring Manager", "tone": "Formal",
            "context": "TEST_ asking for an update on my job application for QA engineer"},
            timeout=LONG)
        assert r.status_code == 200
        draft = r.json()["draft"]
        assert "AI error" not in draft, draft
        assert len(draft) > 40
        assert "subject" in draft.lower()

    def test_email_missing_context(self, client):
        r = client.post(f"{BASE_URL}/api/email", json={"recipient": "x"}, timeout=30)
        assert r.status_code == 422


# --- Research (DuckDuckGo + LLM) ---
class TestResearch:
    def test_research(self, client):
        r = client.post(f"{BASE_URL}/api/research",
                        json={"query": "who is the CEO of OpenAI"}, timeout=LONG)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d["summary"], str) and len(d["summary"]) > 20
        assert "AI error" not in d["summary"], d["summary"]
        assert isinstance(d["sources"], list)
        if d["sources"]:
            assert d["sources"][0]["href"].startswith("http")
        else:
            pytest.fail(f"No sources returned: {d['summary'][:200]}")

    def test_research_validation(self, client):
        r = client.post(f"{BASE_URL}/api/research", json={}, timeout=30)
        assert r.status_code == 422


# --- App Builder ---
class TestBuild:
    def test_build_returns_html(self, client):
        r = client.post(f"{BASE_URL}/api/build",
                        json={"idea": "a simple counter app with + and - buttons"},
                        timeout=300)
        assert r.status_code == 200
        html = r.json()["html"]
        assert "AI error" not in html, html[:300]
        assert html.lower().startswith("<!doctype html")
        assert "</html>" in html.lower()

    def test_build_refine(self, client):
        base = ("<!DOCTYPE html><html><head><title>Counter</title></head>"
                "<body><h1 id='v'>0</h1><button onclick=\"document.getElementById('v')"
                ".textContent=+document.getElementById('v').textContent+1\">+</button>"
                "</body></html>")
        r = client.post(f"{BASE_URL}/api/build", json={
            "idea": "counter app", "refine": "add a reset button",
            "current_html": base}, timeout=300)
        assert r.status_code == 200
        html = r.json()["html"]
        assert "AI error" not in html, html[:300]
        assert html.lower().startswith("<!doctype html")
        assert "reset" in html.lower()
