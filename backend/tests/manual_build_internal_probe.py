"""Measure the REAL backend build duration internally (bypassing the 60s ingress proxy)
plus the public-URL result, to separate LLM latency from gateway timeouts."""
import time
import uuid
from datetime import datetime, timezone, timedelta

import requests
from dotenv import dotenv_values
from pymongo import MongoClient

be = dotenv_values("/app/backend/.env")
db = MongoClient(be["MONGO_URL"])[be["DB_NAME"]]
INTERNAL = "http://localhost:8001"

email = f"test_probe_{uuid.uuid4().hex[:6]}@test.com"
uid = f"user_TEST_{uuid.uuid4().hex[:10]}"
tok = f"TEST_{uuid.uuid4().hex}"
db.allowed_users.update_one({"email": email}, {"$set": {"email": email, "role": "user",
                            "added_at": datetime.now(timezone.utc)}}, upsert=True)
db.users.insert_one({"user_id": uid, "email": email, "name": "TEST", "picture": "",
                     "role": "user", "created_at": datetime.now(timezone.utc)})
db.user_sessions.insert_one({"user_id": uid, "session_token": tok,
                             "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
                             "created_at": datetime.now(timezone.utc)})
s = requests.Session()
s.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {tok}"})
try:
    t0 = time.time()
    r = s.post(f"{INTERNAL}/api/build",
               json={"idea": "a task manager with projects and a dashboard"}, timeout=900)
    dt = time.time() - t0
    print(f"INTERNAL STATUS={r.status_code} ELAPSED={dt:.1f}s")
    if r.status_code == 200:
        d = r.json()
        paths = [f["path"] for f in d["files"]]
        html = d["preview_html"]
        print("N_FILES:", len(paths), "DUPES:", [p for p in set(paths) if paths.count(p) > 1])
        print("SERVER_PY:", [p for p in paths if p.lower().endswith("server.py")])
        print("APP_JS:", [p for p in paths if p.lower().endswith(("app.js", "app.jsx"))])
        print("README:", [p for p in paths if p.lower().endswith("readme.md")])
        print("COMPOSE:", [p for p in paths if "docker-compose" in p.lower()])
        print("PREVIEW LEN:", len(html), "STARTS:", html[:16],
              "ENDS </html>:", html.rstrip().lower().endswith("</html>"))
        print("PREVIEW TAIL:", repr(html[-220:]))
        s.delete(f"{INTERNAL}/api/history/apps/{d['id']}", timeout=30)
finally:
    db.users.delete_many({"user_id": uid})
    db.user_sessions.delete_many({"user_id": uid})
    db.apps.delete_many({"user_id": uid})
    db.allowed_users.delete_many({"email": email})
    print("cleaned up")
