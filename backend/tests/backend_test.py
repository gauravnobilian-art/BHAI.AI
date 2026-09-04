"""Jarvis core endpoints (auth-protected) + /api/stats. Requires a seeded Mongo session.

Auth is now mandatory on chat/email/research/build/history/stats, so every test here
uses the `regular_user` fixture (Mongo-seeded session -> Authorization: Bearer <token>).
"""
import io
import uuid
import zipfile
from datetime import datetime, timezone

import pytest

from conftest import BASE_URL, LONG, poll_build


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
    def test_multiagent_build_zip_stats_and_history(self, regular_user, mongo):
        """One (expensive) build call: multi-file full-stack output, zip, stats, history, delete."""
        c = regular_user["client"]
        before = c.get(f"{BASE_URL}/api/stats", timeout=30)
        assert before.status_code == 200
        b = before.json()
        for key in ("chat_messages", "emails", "apps"):
            assert isinstance(b[key], int), f"{key} not an int: {b[key]!r}"
        assert isinstance(b["recent_apps"], list)

        r = c.post(f"{BASE_URL}/api/build",
                   json={"idea": "a recipe sharing app with ratings"}, timeout=120)
        assert r.status_code == 200, r.text[:800]
        posted = r.json()
        app_id = posted["id"]

        # Soft assertions: one expensive build call must surface ALL findings.
        problems = []

        def check(cond, msg):
            if not cond:
                problems.append(msg)
                print("FAIL:", msg)

        check(posted.get("status") == "running", f"POST status: {posted.get('status')}")
        check(isinstance(posted.get("agents"), list) and len(posted["agents"]) >= 4,
              f"agents list unexpected: {posted.get('agents')}")

        # --- poll the async job ---
        d = poll_build(c, BASE_URL, app_id, timeout=180)
        check(d["status"] == "done", f"build status={d['status']} error={d.get('error')!r}")

        # --- plan ---
        check(isinstance(d.get("plan"), str) and len(d["plan"].strip()) > 100,
              f"plan too short/missing: {str(d.get('plan'))[:150]!r}")

        # --- preview html ---
        html = d.get("preview_html") or ""
        check(html.lower().startswith("<!doctype html"), f"preview_html start: {html[:80]!r}")
        check("</html>" in html.lower(),
              f"preview_html TRUNCATED - no closing </html> (len={len(html)}), tail={html[-120:]!r}")

        # --- multi-file full-stack project ---
        files = d.get("files") or []
        paths = [f["path"] for f in files]
        print(f"GENERATED {len(files)} FILES:", paths)
        print("PREVIEW LEN:", len(html), "PLAN LEN:", len(d.get("plan") or ""))
        check(len(files) >= 6, f"only {len(files)} files: {paths}")
        check(all(isinstance(f.get("content"), str) and f["content"].strip() for f in files),
              f"empty file content in {paths}")
        check(not (len(paths) == 1 and paths[0].lower().endswith(".html")),
              f"single-html output only: {paths}")

        lower = [p.lower() for p in paths]
        backend_files = [p for p in lower if "server.py" in p or "requirements.txt" in p
                         or "models.py" in p or p.startswith("backend/")]
        frontend_files = [p for p in lower if "app.js" in p or "package.json" in p
                          or p.startswith("frontend/") or "/components/" in p]
        check(bool(backend_files), f"no backend files: {paths}")
        check(any(p.endswith(("server.py", "main.py")) for p in lower),
              f"no FastAPI entrypoint (server.py/main.py) generated: {paths}")
        check(bool(frontend_files), f"no frontend files: {paths}")
        check(any(p.endswith("app.js") or p.endswith("app.jsx") for p in lower),
              f"no React entrypoint (src/App.js) generated: {paths}")
        check(any("readme.md" in p for p in lower), f"no README.md: {paths}")
        check(any("docker-compose" in p for p in lower), f"no docker-compose: {paths}")
        srv = next((f for f in files if f["path"].lower().endswith("server.py")), None)
        if srv:
            check("fastapi" in srv["content"].lower(), "server.py has no FastAPI usage")
            check(len(srv["content"]) > 400, f"server.py too small ({len(srv['content'])} chars)")
            check(srv["content"].rstrip().endswith((")", "}", ":", '"', "'", "]", "e", "0", "1")),
                  f"server.py may be truncated, tail={srv['content'][-80:]!r}")

        # --- persistence ---
        stored = mongo.apps.find_one({"id": app_id})
        check(stored is not None, "app not persisted in db.apps")
        if stored:
            check(len(stored.get("files", [])) == len(files), "persisted file count mismatch")
            check(bool(stored.get("preview_html")), "persisted preview_html empty")

        # --- zip download ---
        z = c.get(f"{BASE_URL}/api/apps/{app_id}/zip", timeout=120)
        check(z.status_code == 200, f"zip status {z.status_code}: {z.text[:200]}")
        if z.status_code == 200:
            check("application/zip" in z.headers.get("content-type", ""),
                  f"zip content-type {z.headers.get('content-type')}")
            check("attachment" in z.headers.get("content-disposition", ""),
                  f"zip disposition {z.headers.get('content-disposition')}")
            zf = zipfile.ZipFile(io.BytesIO(z.content))
            names = zf.namelist()
            print("ZIP ENTRIES:", names)
            check(zf.testzip() is None, "zip CRC failure")
            check("preview/index.html" in names, f"preview/index.html missing: {names}")
            missing = [p for p in paths if p not in names]
            check(not missing, f"files missing from zip: {missing}")

        # zip for unknown id -> 404
        unknown = c.get(f"{BASE_URL}/api/apps/{uuid.uuid4()}/zip", timeout=60)
        check(unknown.status_code == 404, f"unknown zip id -> {unknown.status_code}")

        after = c.get(f"{BASE_URL}/api/stats", timeout=30).json()
        check(after["apps"] == b["apps"] + 1, f"stats apps {b['apps']} -> {after['apps']}")
        check(any(a["id"] == app_id for a in after["recent_apps"]), "app not in recent_apps")
        check(all("_id" not in a for a in after["recent_apps"]), "_id leaked in recent_apps")
        check(len(after["recent_apps"]) <= 5, "recent_apps > 5")

        # history + delete
        apps = c.get(f"{BASE_URL}/api/history/apps", timeout=30).json()["apps"]
        check(any(a["id"] == app_id for a in apps), "app not in /api/history/apps")
        check(c.delete(f"{BASE_URL}/api/history/apps/{app_id}", timeout=30).status_code == 200,
              "delete app failed")
        check(mongo.apps.find_one({"id": app_id}) is None, "app still in db after delete")

        assert not problems, "\n".join(problems)

    def test_zip_is_scoped_to_owner(self, regular_user, super_admin, mongo):
        """Another user's app id must 404 (no cross-user access)."""
        app_id = f"TEST_{uuid.uuid4().hex}"
        mongo.apps.insert_one({"id": app_id, "user_id": regular_user["user_id"],
                               "idea": "TEST scoping", "plan": "p",
                               "files": [{"path": "a.txt", "content": "hello"}],
                               "preview_html": "<!DOCTYPE html><html></html>",
                               "created_at": datetime.now(timezone.utc)})
        try:
            ok = regular_user["client"].get(f"{BASE_URL}/api/apps/{app_id}/zip", timeout=60)
            assert ok.status_code == 200
            assert "a.txt" in zipfile.ZipFile(io.BytesIO(ok.content)).namelist()
            other = super_admin["client"].get(f"{BASE_URL}/api/apps/{app_id}/zip", timeout=60)
            assert other.status_code == 404, other.status_code
        finally:
            mongo.apps.delete_many({"id": app_id})

    def test_build_refine(self, regular_user):
        base = ("<!DOCTYPE html><html><head><title>Counter</title></head>"
                "<body><h1 id='v'>0</h1></body></html>")
        r = regular_user["client"].post(f"{BASE_URL}/api/build", json={
            "idea": "counter app", "refine": "add a dark mode toggle",
            "current_html": base}, timeout=300)
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        html = d["preview_html"]
        assert html.lower().startswith("<!doctype html"), html[:120]
        assert "</html>" in html.lower()
        assert "dark" in html.lower()
        assert d["files"] == []

    def test_stats_isolated_per_user(self, super_admin):
        """A fresh user must see zeroed counters (no cross-user leakage)."""
        r = super_admin["client"].get(f"{BASE_URL}/api/stats", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d == {"chat_messages": 0, "emails": 0, "apps": 0, "recent_apps": []}, d
