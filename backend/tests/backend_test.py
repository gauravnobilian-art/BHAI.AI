"""Jarvis core endpoints (auth-protected) + /api/stats. Requires a seeded Mongo session.

Auth is now mandatory on chat/email/research/build/history/stats, so every test here
uses the `regular_user` fixture (Mongo-seeded session -> Authorization: Bearer <token>).
"""
import pytest

from conftest import BASE_URL, LONG


# --- Chat (LLM) + persistence ---
class TestChat:
    def test_chat_persists_and_history_returns_messages(self, regular_user, mongo):
        c = regular_user["client"]
        r = c.post(f"{BASE_URL}/api/chat", json={
            "messages": [{"role": "user", "content": "Say only the word PONG"}],
            "style": ""}, timeout=LONG)
        assert r.status_code == 200, r.text
        reply = r.json()["reply"]
        assert isinstance(reply, str) and len(reply) > 0
        assert "AI error" not in reply and "not configured" not in reply, reply

        # persisted in db.chats
        doc = mongo.chats.find_one({"user_id": regular_user["user_id"]})
        assert doc is not None, "chat not persisted to db.chats"
        assert len(doc["messages"]) == 2
        assert doc["messages"][0]["content"] == "Say only the word PONG"
        assert doc["messages"][-1]["role"] == "assistant"

        # readable via API
        h = c.get(f"{BASE_URL}/api/history/chat", timeout=30)
        assert h.status_code == 200
        msgs = h.json()["messages"]
        assert len(msgs) == 2
        assert msgs[-1]["content"] == reply

    def test_chat_empty_messages(self, regular_user):
        r = regular_user["client"].post(f"{BASE_URL}/api/chat", json={"messages": []}, timeout=60)
        assert r.status_code == 400, r.text
        assert "No messages" in r.json().get("detail", "")

    def test_chat_validation_error(self, regular_user):
        r = regular_user["client"].post(f"{BASE_URL}/api/chat",
                                        json={"style": "professional"}, timeout=30)
        assert r.status_code == 422

    def test_clear_chat_history(self, regular_user):
        c = regular_user["client"]
        r = c.delete(f"{BASE_URL}/api/history/chat", timeout=30)
        assert r.status_code == 200 and r.json()["ok"] is True
        assert c.get(f"{BASE_URL}/api/history/chat", timeout=30).json()["messages"] == []


# --- Email ---
class TestEmail:
    def test_email_generate_and_history(self, regular_user):
        c = regular_user["client"]
        r = c.post(f"{BASE_URL}/api/email", json={
            "recipient": "Hiring Manager", "tone": "Formal",
            "context": "TEST_ asking for an update on my job application for QA engineer"},
            timeout=LONG)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "AI error" not in d["draft"], d["draft"]
        assert len(d["draft"]) > 40
        assert "subject" in d["draft"].lower()
        assert isinstance(d["id"], str)

        h = c.get(f"{BASE_URL}/api/history/emails", timeout=30)
        assert h.status_code == 200
        emails = h.json()["emails"]
        assert any(e["id"] == d["id"] for e in emails)
        assert all("_id" not in e for e in emails)

    def test_email_missing_context(self, regular_user):
        r = regular_user["client"].post(f"{BASE_URL}/api/email",
                                        json={"recipient": "x"}, timeout=30)
        assert r.status_code == 422


# --- Research (DuckDuckGo + LLM) ---
class TestResearch:
    def test_research(self, regular_user):
        r = regular_user["client"].post(f"{BASE_URL}/api/research",
                                        json={"query": "who is the CEO of OpenAI"}, timeout=LONG)
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d["summary"], str) and len(d["summary"]) > 20
        assert isinstance(d["sources"], list)
        if not d["sources"]:
            pytest.fail(f"No sources returned: {d['summary'][:200]}")
        assert d["sources"][0]["href"].startswith("http")

    def test_research_validation(self, regular_user):
        r = regular_user["client"].post(f"{BASE_URL}/api/research", json={}, timeout=30)
        assert r.status_code == 422


# --- App Builder + /api/stats ---
class TestBuildAndStats:
    def test_build_returns_html_and_stats_reflect_it(self, regular_user, mongo):
        c = regular_user["client"]
        before = c.get(f"{BASE_URL}/api/stats", timeout=30)
        assert before.status_code == 200
        b = before.json()
        for key in ("chat_messages", "emails", "apps"):
            assert isinstance(b[key], int), f"{key} not an int: {b[key]!r}"
        assert isinstance(b["recent_apps"], list)

        r = c.post(f"{BASE_URL}/api/build",
                   json={"idea": "a simple counter app with + and - buttons"}, timeout=300)
        assert r.status_code == 200, r.text
        html = r.json()["html"]
        app_id = r.json()["id"]
        assert html.lower().startswith("<!doctype html")
        assert "</html>" in html.lower()
        assert mongo.apps.find_one({"id": app_id}) is not None

        after = c.get(f"{BASE_URL}/api/stats", timeout=30).json()
        assert after["apps"] == b["apps"] + 1
        assert any(a["id"] == app_id for a in after["recent_apps"])
        assert all("_id" not in a for a in after["recent_apps"])
        assert len(after["recent_apps"]) <= 5

        # history + delete
        apps = c.get(f"{BASE_URL}/api/history/apps", timeout=30).json()["apps"]
        assert any(a["id"] == app_id for a in apps)
        assert c.delete(f"{BASE_URL}/api/history/apps/{app_id}", timeout=30).status_code == 200
        assert mongo.apps.find_one({"id": app_id}) is None

    def test_build_refine(self, regular_user):
        base = ("<!DOCTYPE html><html><head><title>Counter</title></head>"
                "<body><h1 id='v'>0</h1></body></html>")
        r = regular_user["client"].post(f"{BASE_URL}/api/build", json={
            "idea": "counter app", "refine": "add a reset button",
            "current_html": base}, timeout=300)
        assert r.status_code == 200, r.text
        html = r.json()["html"]
        assert html.lower().startswith("<!doctype html")
        assert "reset" in html.lower()

    def test_stats_isolated_per_user(self, super_admin):
        """A fresh user must see zeroed counters (no cross-user leakage)."""
        r = super_admin["client"].get(f"{BASE_URL}/api/stats", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d == {"chat_messages": 0, "emails": 0, "apps": 0, "recent_apps": []}, d
