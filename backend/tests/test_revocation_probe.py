"""Revocation: removing a user from the allow-list must invalidate existing sessions."""
from conftest import BASE_URL


def test_revoked_user_session_is_rejected(regular_user, mongo):
    c = regular_user["client"]
    assert c.get(f"{BASE_URL}/api/stats", timeout=30).status_code == 200

    # super admin removes them from the allow-list
    mongo.allowed_users.delete_many({"email": regular_user["email"]})

    me = c.get(f"{BASE_URL}/api/auth/me", timeout=30)
    stats = c.get(f"{BASE_URL}/api/stats", timeout=30)
    chat = c.post(f"{BASE_URL}/api/chat",
                  json={"messages": [{"role": "user", "content": "hi"}]}, timeout=120)
    print("REVOKED -> /auth/me:", me.status_code, "/stats:", stats.status_code,
          "/chat:", chat.status_code)
    assert me.status_code == 403, f"/auth/me -> {me.status_code}: {me.text[:200]}"
    assert stats.status_code == 403, f"/stats -> {stats.status_code}"
    assert chat.status_code == 403, f"/chat -> {chat.status_code}"
