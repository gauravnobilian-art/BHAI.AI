"""Standalone single-build probe (sequential, timed) to diagnose latency/truncation."""
import io
import json
import sys
import time
import uuid
import zipfile
from datetime import datetime, timezone, timedelta

import requests
from dotenv import dotenv_values
from pymongo import MongoClient

fe = dotenv_values("/app/frontend/.env")
be = dotenv_values("/app/backend/.env")
BASE = fe["REACT_APP_BACKEND_URL"].rstrip("/")
db = MongoClient(be["MONGO_URL"])[be["DB_NAME"]]

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
    r = s.post(f"{BASE}/api/build",
               json={"idea": "a task manager with projects and a dashboard"}, timeout=900)
    dt = time.time() - t0
    print(f"STATUS={r.status_code} ELAPSED={dt:.1f}s")
    if r.status_code != 200:
        print(r.text[:400])
        sys.exit(1)
    d = r.json()
    html = d["preview_html"]
    paths = [f["path"] for f in d["files"]]
    print("AGENTS:", d.get("agents"))
    print("PLAN LEN:", len(d.get("plan") or ""))
    print("FILES:", json.dumps(paths, indent=0))
    print("SIZES:", {f["path"]: len(f["content"]) for f in d["files"]})
    print("PREVIEW LEN:", len(html))
    print("PREVIEW START:", repr(html[:60]))
    print("PREVIEW TAIL:", repr(html[-200:]))
    print("ENDS_WITH_HTML:", html.rstrip().lower().endswith("</html>"))
    print("HAS_SERVER_PY:", [p for p in paths if p.lower().endswith("server.py")])
    print("HAS_APP_JS:", [p for p in paths if p.lower().endswith(("app.js", "app.jsx"))])
    srv = next((f for f in d["files"] if f["path"].lower().endswith("server.py")), None)
    if srv:
        print("SERVER.PY TAIL:", repr(srv["content"][-120:]))
    appjs = next((f for f in d["files"] if f["path"].lower().endswith(("app.js", "app.jsx"))), None)
    if appjs:
        print("APP.JS TAIL:", repr(appjs["content"][-120:]))
    z = s.get(f"{BASE}/api/apps/{d['id']}/zip", timeout=180)
    print("ZIP STATUS:", z.status_code, z.headers.get("content-type"))
    if z.status_code == 200:
        zf = zipfile.ZipFile(io.BytesIO(z.content))
        print("ZIP ENTRIES:", zf.namelist())
        print("ZIP CRC OK:", zf.testzip() is None)
        inner = zf.read("preview/index.html").decode("utf-8", "replace")
        print("ZIP PREVIEW ENDS </html>:", inner.rstrip().lower().endswith("</html>"))
    s.delete(f"{BASE}/api/history/apps/{d['id']}", timeout=30)
finally:
    db.users.delete_many({"user_id": uid})
    db.user_sessions.delete_many({"user_id": uid})
    db.apps.delete_many({"user_id": uid})
    db.allowed_users.delete_many({"email": email})
    print("cleaned up")
