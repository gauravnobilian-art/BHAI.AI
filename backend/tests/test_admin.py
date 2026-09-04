"""Admin allow-list management: /api/admin/users GET/POST/DELETE + role enforcement."""
import uuid

from conftest import BASE_URL, SUPER_ADMIN


# --- Super admin can manage the allow-list ---
class TestAdminAllowList:
    def test_list_users_super_admin_first(self, super_admin):
        r = super_admin["client"].get(f"{BASE_URL}/api/admin/users", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["super_admin"] == SUPER_ADMIN
        assert isinstance(d["users"], list) and len(d["users"]) >= 1
        assert d["users"][0]["email"] == SUPER_ADMIN
        assert d["users"][0]["role"] == "super_admin"
        for u in d["users"]:
            assert "_id" not in u

    def test_add_list_and_delete_user(self, super_admin, mongo):
        email = f"test_add_{uuid.uuid4().hex[:6]}@test.com"
        c = super_admin["client"]
        try:
            # ADD
            r = c.post(f"{BASE_URL}/api/admin/users",
                       json={"email": email.upper(), "role": "user"}, timeout=30)
            assert r.status_code == 200, r.text
            assert r.json()["ok"] is True

            # GET verifies persistence (email normalised to lowercase)
            r = c.get(f"{BASE_URL}/api/admin/users", timeout=30)
            assert r.status_code == 200
            emails = [u["email"] for u in r.json()["users"]]
            assert email.lower() in emails, emails
            entry = next(u for u in r.json()["users"] if u["email"] == email.lower())
            assert entry["role"] == "user"
            assert entry["added_at"] != ""

            # DELETE
            r = c.delete(f"{BASE_URL}/api/admin/users/{email.lower()}", timeout=30)
            assert r.status_code == 200
            assert r.json()["ok"] is True

            # GET verifies removal
            r = c.get(f"{BASE_URL}/api/admin/users", timeout=30)
            assert email.lower() not in [u["email"] for u in r.json()["users"]]
        finally:
            mongo.allowed_users.delete_many({"email": email.lower()})

    def test_add_upsert_updates_role(self, super_admin, mongo):
        email = f"test_upsert_{uuid.uuid4().hex[:6]}@test.com"
        c = super_admin["client"]
        try:
            assert c.post(f"{BASE_URL}/api/admin/users",
                          json={"email": email, "role": "user"}, timeout=30).status_code == 200
            # role is now a Literal["user","admin"] -> upsert to a valid role
            assert c.post(f"{BASE_URL}/api/admin/users",
                          json={"email": email, "role": "admin"}, timeout=30).status_code == 200
            users = c.get(f"{BASE_URL}/api/admin/users", timeout=30).json()["users"]
            matches = [u for u in users if u["email"] == email]
            assert len(matches) == 1, f"duplicate allow-list entries: {matches}"
            assert matches[0]["role"] == "admin"
            # invalid / escalating roles must be rejected
            for bad in ("editor", "super_admin", ""):
                r = c.post(f"{BASE_URL}/api/admin/users",
                           json={"email": email, "role": bad}, timeout=30)
                assert r.status_code == 422, f"role={bad!r} -> {r.status_code}"
        finally:
            mongo.allowed_users.delete_many({"email": email})

    def test_cannot_delete_super_admin(self, super_admin):
        r = super_admin["client"].delete(f"{BASE_URL}/api/admin/users/{SUPER_ADMIN}", timeout=30)
        assert r.status_code == 400, r.text
        assert "super admin" in r.json()["detail"].lower()

    def test_cannot_add_super_admin(self, super_admin):
        r = super_admin["client"].post(f"{BASE_URL}/api/admin/users",
                                       json={"email": SUPER_ADMIN, "role": "user"}, timeout=30)
        assert r.status_code == 400
        assert "super admin" in r.json()["detail"].lower()

    def test_invalid_email_rejected(self, super_admin):
        r = super_admin["client"].post(f"{BASE_URL}/api/admin/users",
                                       json={"email": "not-an-email"}, timeout=30)
        assert r.status_code == 400
        assert "Valid email" in r.json()["detail"]

    def test_missing_email_field(self, super_admin):
        r = super_admin["client"].post(f"{BASE_URL}/api/admin/users", json={}, timeout=30)
        assert r.status_code == 422


# --- Non-super-admin must be blocked from every admin endpoint ---
class TestAdminForbiddenForRegularUser:
    def test_get_forbidden(self, regular_user):
        r = regular_user["client"].get(f"{BASE_URL}/api/admin/users", timeout=30)
        assert r.status_code == 403, r.text
        assert "Super admin" in r.json()["detail"]

    def test_post_forbidden(self, regular_user, mongo):
        email = f"test_forbidden_{uuid.uuid4().hex[:6]}@test.com"
        r = regular_user["client"].post(f"{BASE_URL}/api/admin/users",
                                        json={"email": email, "role": "user"}, timeout=30)
        assert r.status_code == 403, r.text
        # ensure nothing was written
        assert mongo.allowed_users.find_one({"email": email}) is None

    def test_delete_forbidden(self, regular_user, mongo):
        r = regular_user["client"].delete(
            f"{BASE_URL}/api/admin/users/{regular_user['email']}", timeout=30)
        assert r.status_code == 403, r.text
        # allow-list entry still intact
        assert mongo.allowed_users.find_one({"email": regular_user["email"]}) is not None
