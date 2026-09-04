"""Shared fixtures: base URL + Mongo-seeded sessions for auth-gated Jarvis endpoints."""
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

frontend_env = dotenv_values("/app/frontend/.env")
backend_env = dotenv_values("/app/backend/.env")

_base = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not _base:
    raise RuntimeError("REACT_APP_BACKEND_URL missing from env and /app/frontend/.env")
BASE_URL = _base.rstrip("/")

MONGO_URL = os.environ.get("MONGO_URL") or backend_env.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME") or backend_env.get("DB_NAME")
if not MONGO_URL or not DB_NAME:
    raise RuntimeError("MONGO_URL / DB_NAME missing from /app/backend/.env")

SUPER_ADMIN = "gauravklegacy@gmail.com"
LONG = 240


@pytest.fixture(scope="session")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


def _seed(db, email, role):
    """Insert a user + valid session directly in Mongo, return (user_id, token)."""
    user_id = f"user_TEST_{uuid.uuid4().hex[:10]}"
    token = f"TEST_{uuid.uuid4().hex}"
    db.users.insert_one({"user_id": user_id, "email": email, "name": "TEST User",
                         "picture": "", "role": role,
                         "created_at": datetime.now(timezone.utc)})
    db.user_sessions.insert_one({"user_id": user_id, "session_token": token,
                                 "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
                                 "created_at": datetime.now(timezone.utc)})
    return user_id, token


def _purge(db, user_id, email):
    db.users.delete_many({"user_id": user_id})
    db.user_sessions.delete_many({"user_id": user_id})
    db.chats.delete_many({"user_id": user_id})
    db.emails.delete_many({"user_id": user_id})
    db.apps.delete_many({"user_id": user_id})
    if email and email.lower() != SUPER_ADMIN.lower():
        db.allowed_users.delete_many({"email": email.lower()})


@pytest.fixture(scope="class")
def anon_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="class")
def super_admin(mongo):
    """Authenticated session for the hard-coded SUPER_ADMIN email."""
    user_id, token = _seed(mongo, SUPER_ADMIN, "super_admin")
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json",
                      "Authorization": f"Bearer {token}"})
    yield {"client": s, "user_id": user_id, "token": token, "email": SUPER_ADMIN}
    _purge(mongo, user_id, SUPER_ADMIN)


@pytest.fixture(scope="class")
def regular_user(mongo):
    """Authenticated session for an allow-listed non-admin user."""
    email = f"test_regular_{uuid.uuid4().hex[:6]}@test.com"
    mongo.allowed_users.update_one({"email": email},
                                   {"$set": {"email": email, "role": "user",
                                             "added_at": datetime.now(timezone.utc)}},
                                   upsert=True)
    user_id, token = _seed(mongo, email, "user")
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json",
                      "Authorization": f"Bearer {token}"})
    yield {"client": s, "user_id": user_id, "token": token, "email": email}
    _purge(mongo, user_id, email)


def poll_build(client, base_url, app_id, timeout=180, interval=3):
    """Poll GET /api/apps/{id} until status is done/error. Returns the final doc."""
    import time
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = client.get(f"{base_url}/api/apps/{app_id}", timeout=60)
        assert r.status_code == 200, f"poll -> {r.status_code} {r.text[:300]}"
        last = r.json()
        if last.get("status") in ("done", "error"):
            return last
        time.sleep(interval)
    raise AssertionError(f"build {app_id} did not finish in {timeout}s; last={str(last)[:300]}")
