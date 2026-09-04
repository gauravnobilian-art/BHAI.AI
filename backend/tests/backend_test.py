import os
import re
from datetime import datetime

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL is missing")
BASE_URL = base_url.rstrip("/")

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# Module: server.py root endpoint
class TestRoot:
    def test_root(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/", timeout=30)
        assert r.status_code == 200, r.text
        assert r.json() == {"message": "Hello World"}

    def test_root_repeated_calls_stable(self, api_client):
        # guards against startup/shutdown regressions (on_startup TypeError bug)
        for _ in range(3):
            r = api_client.get(f"{BASE_URL}/api/", timeout=30)
            assert r.status_code == 200
            assert r.json()["message"] == "Hello World"


# Module: status_checks CRUD + pagination
class TestStatusChecks:
    def test_create_and_read_back(self, api_client):
        name = f"TEST_client_{datetime.utcnow().timestamp()}"
        r = api_client.post(f"{BASE_URL}/api/status", json={"client_name": name}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data["id"], str) and len(data["id"]) == 36
        assert data["client_name"] == name
        assert ISO_RE.match(data["timestamp"])

        # verify persistence via paginated GET (scan a few pages)
        found = None
        for skip in range(0, 300, 100):
            g = api_client.get(f"{BASE_URL}/api/status", params={"skip": skip, "limit": 100}, timeout=30)
            assert g.status_code == 200, g.text
            items = g.json()
            match = [i for i in items if i["id"] == data["id"]]
            if match:
                found = match[0]
                break
            if len(items) < 100:
                break
        assert found is not None, "created status check not found in GET /api/status"
        assert found["client_name"] == name

    def test_list_no_mongo_id(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/status", timeout=30)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        for i in items:
            assert "_id" not in i
            assert set(i.keys()) == {"id", "client_name", "timestamp"}

    def test_pagination_limit_respected(self, api_client):
        # seed enough rows
        for n in range(3):
            api_client.post(f"{BASE_URL}/api/status", json={"client_name": f"TEST_page_{n}"}, timeout=30)
        r = api_client.get(f"{BASE_URL}/api/status", params={"skip": 0, "limit": 2}, timeout=30)
        assert r.status_code == 200, r.text
        assert len(r.json()) <= 2

    def test_limit_capped_at_100(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/status", params={"limit": 1000}, timeout=30)
        assert r.status_code == 200, r.text
        assert len(r.json()) <= 100

    def test_skip_offsets_results(self, api_client):
        first = api_client.get(f"{BASE_URL}/api/status", params={"skip": 0, "limit": 2}, timeout=30).json()
        second = api_client.get(f"{BASE_URL}/api/status", params={"skip": 1, "limit": 2}, timeout=30).json()
        if len(first) == 2 and len(second) >= 1:
            assert first[1]["id"] == second[0]["id"]

    def test_negative_skip_and_limit_handled(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/status", params={"skip": -5, "limit": -3}, timeout=30)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_create_missing_field_422(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/status", json={}, timeout=30)
        assert r.status_code == 422, r.text

    def test_create_wrong_type_422(self, api_client):
        r = api_client.post(f"{BASE_URL}/api/status", json={"client_name": 123}, timeout=30)
        assert r.status_code == 422, r.text

    def test_unknown_route_404(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/does-not-exist", timeout=30)
        assert r.status_code == 404


# Module: CORS middleware
class TestCors:
    def test_cors_headers(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/", headers={"Origin": "https://example.com"}, timeout=30)
        assert r.status_code == 200
        assert "access-control-allow-origin" in {k.lower() for k in r.headers}
