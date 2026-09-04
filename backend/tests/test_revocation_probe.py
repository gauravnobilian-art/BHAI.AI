"""Probe: what happens to an existing session after the user is removed from the allow-list?

Documents observed behaviour (revocation gap) rather than asserting a desired one; the
result is reported to the developer agent.
"""
from conftest import BASE_URL


def test_revoked_user_session_behaviour(regular_user, mongo, record_property):
    c = regular_user["client"]
    assert c.get(f"{BASE_URL}/api/stats", timeout=30).status_code == 200

    # super admin removes them from the allow-list
    mongo.allowed_users.delete_many({"email": regular_user["email"]})

    me = c.get(f"{BASE_URL}/api/auth/me", timeout=30)
    stats = c.get(f"{BASE_URL}/api/stats", timeout=30)
    chat = c.post(f"{BASE_URL}/api/chat",
                  json={"messages": [{"role": "user", "content": "hi"}]}, timeout=120)
    record_property("revoked_auth_me", f"{me.status_code} {me.text[:120]}")
    record_property("revoked_stats", str(stats.status_code))
    record_property("revoked_chat", str(chat.status_code))
    print("REVOKED -> /auth/me:", me.status_code, me.text[:200])
    print("REVOKED -> /stats:", stats.status_code, "/chat:", chat.status_code)
