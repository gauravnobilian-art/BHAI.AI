"""Iteration-7: /api/build ASYNC background-job refactor (P0 502 fix).

Covers: instant POST (no 60s ingress timeout), polling GET /api/apps/{id} to 'done',
file de-duplication, frontend/Dockerfile when docker-compose exists, non-truncated
preview_html, and a valid zip with unique entries.
"""
import io
import time
import zipfile

from conftest import BASE_URL, poll_build


class TestBuildAsyncJob:
    def test_build_is_async_and_completes(self, regular_user):
        c = regular_user["client"]
        t0 = time.time()
        r = c.post(f"{BASE_URL}/api/build",
                   json={"idea": "a task manager with projects and a dashboard"}, timeout=120)
        elapsed = time.time() - t0
        assert r.status_code == 200, f"build POST -> {r.status_code} {r.text[:300]}"
        d = r.json()
        print(f"POST /api/build returned {r.status_code} in {elapsed:.2f}s -> {d}")

        problems = []

        def check(cond, msg):
            if not cond:
                problems.append(msg)
                print("FAIL:", msg)

        # --- P0: instant async response ---
        check(elapsed < 5, f"POST /api/build took {elapsed:.1f}s (expected <5s, async)")
        check(d.get("status") == "running", f"status not 'running': {d.get('status')}")
        check(isinstance(d.get("id"), str) and d["id"], f"no app id: {d}")
        check(d.get("files") is None, f"POST unexpectedly returned files: {d.get('files')}")
        app_id = d["id"]

        # --- polling to done ---
        t1 = time.time()
        final = poll_build(c, BASE_URL, app_id, timeout=180)
        build_secs = time.time() - t1
        print(f"build finished status={final['status']} after {build_secs:.1f}s of polling")
        check(final["status"] == "done", f"status={final['status']} err={final.get('error')!r}")
        check(build_secs < 120, f"build took {build_secs:.1f}s of polling (expected <120s)")

        html = final.get("preview_html") or ""
        files = final.get("files") or []
        paths = [f["path"] for f in files]
        print(f"FILES ({len(paths)}):", paths)
        print("PREVIEW LEN:", len(html), "TAIL:", repr(html[-120:]))

        check(isinstance(final.get("plan"), str) and len(final["plan"].strip()) > 100,
              f"plan too short: {str(final.get('plan'))[:150]!r}")

        # --- preview_html completeness ---
        check(html.lower().startswith("<!doctype html"), f"preview start: {html[:80]!r}")
        check(html.lower().rstrip().endswith("</html>"),
              f"preview does NOT end with </html>, tail={html[-160:]!r}")
        check("</body>" in html.lower(), "preview missing </body>")
        check(html.lower().count("</html>") == 1,
              f"preview has {html.lower().count('</html>')} </html> tags")
        check("preview unavailable" not in html.lower(), "preview fell back to placeholder")

        # --- de-duplication + path safety ---
        dupes = sorted({p for p in paths if paths.count(p) > 1})
        check(not dupes, f"duplicate file paths -> duplicate zip entries: {dupes}")
        for f in files:
            check(isinstance(f.get("content"), str) and f["content"].strip(),
                  f"empty content for {f.get('path')}")
            check(not f["path"].startswith("/") and ".." not in f["path"].split("/"),
                  f"unsafe path in output: {f['path']}")

        # --- required entrypoints ---
        lower = [p.lower() for p in paths]
        check(len(files) >= 6, f"only {len(files)} files: {paths}")
        check(any(p.startswith("backend/") and p.endswith("server.py") for p in lower),
              f"backend/server.py missing: {paths}")
        check(any(p.startswith("frontend/") and p.endswith(("app.js", "app.jsx"))
                  for p in lower), f"frontend/src/App.js missing: {paths}")
        check(any(p.endswith("requirements.txt") for p in lower), f"no requirements.txt: {paths}")
        check(any(p.endswith("package.json") for p in lower), f"no package.json: {paths}")
        check(any("readme.md" in p for p in lower), f"no README.md: {paths}")

        # --- frontend/Dockerfile whenever docker-compose.yml exists ---
        has_compose = any("docker-compose" in p for p in lower)
        print("has docker-compose:", has_compose)
        if has_compose:
            check("frontend/dockerfile" in lower,
                  f"docker-compose present but frontend/Dockerfile missing: {paths}")
            check(any(p == "backend/dockerfile" for p in lower),
                  f"docker-compose present but backend/Dockerfile missing: {paths}")

        # --- zip ---
        z = c.get(f"{BASE_URL}/api/apps/{app_id}/zip", timeout=120)
        check(z.status_code == 200, f"zip status {z.status_code}")
        if z.status_code == 200:
            zf = zipfile.ZipFile(io.BytesIO(z.content))
            names = zf.namelist()
            print("ZIP ENTRIES:", len(names), names)
            check(zf.testzip() is None, "zip CRC failure")
            check(len(names) == len(set(names)), f"duplicate zip entries: {names}")
            check("preview/index.html" in names, f"preview/index.html missing: {names}")
            if "preview/index.html" in names:
                inner = zf.read("preview/index.html").decode("utf-8", "replace")
                check(inner.lower().rstrip().endswith("</html>"),
                      f"zip preview/index.html not closed, tail={inner[-120:]!r}")
            missing = [p for p in paths if p not in names]
            check(not missing, f"files missing from zip: {missing}")

        c.delete(f"{BASE_URL}/api/history/apps/{app_id}", timeout=30)
        assert not problems, "\n".join(problems)
