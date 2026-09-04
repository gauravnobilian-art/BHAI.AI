"""Auth + access-control tests: unauthenticated 401s, /api/auth/me roles, session validation."""
import uuid

import pytest

from conftest import BASE_URL, SUPER_ADMIN

PROTECTED = [
    ("GET", "/api/auth/me", None),
    ("GET", "/api/stats", None),
    ("GET", "/api/admin/users", None),
    ("POST", "/api/admin/users", {"email": "x@test.com", "role": "user"}),
    ("DELETE", "/api/admin/users/x@test.com", None),
    ("POST", "/api/chat", {"messages": [{"role": "user", "content": "hi"}]}),
    ("GET", "/api/history/chat", None),
    ("POST", "/api/email", {"context": "hi"}),
    ("POST", "/api/build", {"idea": "todo app"}),
    ("GET", "/api/history/emails", None),
    ("GET", "/api/history/apps", None),
]


# --- Public routes ---
class TestPublic:
    def test_root(self, anon_client):
        r = anon_client.get(f"{BASE_URL}/api/", timeout=30)
        assert r.status_code == 200
        assert r.json()["ai"] is True

    def test_api_health(self, anon_client):
        r = anon_client.get(f"{BASE_URL}/api/health", timeout=30)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# --- Unauthenticated access must be rejected ---
class TestUnauthenticated:
    @pytest.mark.parametrize("method,path,body", PROTECTED)
    def test_requires_auth(self, anon_client, method, path, body):
        r = anon_client.request(method, f"{BASE_URL}{path}", json=body, timeout=60)
        assert r.status_code == 401, f"{method} {path} -> {r.status_code}: {r.text[:200]}"
        assert "detail" in r.json()

    def test_invalid_bearer_token(self, anon_client):
        r = anon_client.get(f"{BASE_URL}/api/auth/me",
                            headers={"Authorization": f"Bearer bogus_{uuid.uuid4().hex}"},
                            timeout=30)
        assert r.status_code == 401
        assert r.json()["detail"] == "Invalid session"

    def test_expired_session(self, anon_client, mongo):
        from datetime import datetime, timezone, timedelta
        uid = f"user_TEST_exp_{uuid.uuid4().hex[:8]}"
        tok = f"TEST_exp_{uuid.uuid4().hex}"
        mongo.users.insert_one({"user_id": uid, "email": "test_exp@test.com",
                               "name": "TEST", "role": "user"})
        mongo.user_sessions.insert_one({
            "user_id": uid, "session_token": tok,
            "expires_at": datetime.now(timezone.utc) - timedelta(days=1)})
        try:
            r = anon_client.get(f"{BASE_URL}/api/auth/me",
                                headers={"Authorization": f"Bearer {tok}"}, timeout=30)
            assert r.status_code == 401
            assert r.json()["detail"] == "Session expired"
        finally:
            mongo.users.delete_many({"user_id": uid})
            mongo.user_sessions.delete_many({"user_id": uid})

    def test_auth_session_missing_header(self, anon_client):
        r = anon_client.post(f"{BASE_URL}/api/auth/session", timeout=30)
        assert r.status_code == 400
        assert "X-Session-ID" in r.json()["detail"]


# --- /api/auth/me role reporting ---
class TestAuthMe:
    def test_super_admin_me(self, super_admin):
        r = super_admin["client"].get(f"{BASE_URL}/api/auth/me", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["email"] == SUPER_ADMIN
        assert d["role"] == "super_admin"
        assert d["is_admin"] is True
        assert d["user_id"] == super_admin["user_id"]
        assert "_id" not in d

    def test_cookie_auth_works(self, super_admin):
        import requests
        r = requests.get(f"{BASE_URL}/api/auth/me",
                         cookies={"session_token": super_admin["token"]}, timeout=30)
        assert r.status_code == 200
        assert r.json()["is_admin"] is True


class TestAuthMeRegular:
    def test_regular_user_me(self, regular_user):
        r = regular_user["client"].get(f"{BASE_URL}/api/auth/me", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["email"] == regular_user["email"]
        assert d["role"] == "user"
        assert d["is_admin"] is False
