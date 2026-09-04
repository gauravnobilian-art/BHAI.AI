"""Bhai.AI 8-agent pipeline: GET /api/models, per-agent model selection, live progress, zip."""
import io
import time
import zipfile

import pytest

from conftest import BASE_URL

AGENT_IDS = ["architect", "database", "backend", "frontend",
             "designer", "devops", "preview", "qa"]
MODEL_IDS = ["gpt-5.4", "gpt-5.4-mini", "gpt-5.5",
             "claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-6"]

OVERRIDES = {"backend": "gpt-5.4-mini", "frontend": "claude-sonnet-4-6",
             "preview": "gpt-5.4", "qa": "gpt-5.4-mini"}


# --------------------------- GET /api/models --------------------------- #
class TestModelsEndpoint:
    def test_models_and_agents_config(self, regular_user):
        r = regular_user["client"].get(f"{BASE_URL}/api/models", timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert isinstance(data.get("models"), list) and isinstance(data.get("agents"), list)

        ids = [m["id"] for m in data["models"]]
        for mid in MODEL_IDS:
            assert mid in ids, f"missing model {mid}; got {ids}"
        providers = {m["id"]: m["provider"] for m in data["models"]}
        assert providers["gpt-5.4"] == "openai"
        assert providers["claude-sonnet-4-6"] == "anthropic"
        for m in data["models"]:
            assert m.get("name") and m.get("badge")

        agents = data["agents"]
        assert len(agents) == 8, [a["id"] for a in agents]
        assert [a["id"] for a in agents] == AGENT_IDS
        for a in agents:
            assert a["default_model"] in MODEL_IDS
            assert a.get("name") and a.get("role") and a.get("icon") and a.get("desc")

    def test_models_requires_auth(self, anon_client):
        r = anon_client.get(f"{BASE_URL}/api/models", timeout=30)
        assert r.status_code == 401, r.status_code


# ------------------- POST /api/build (8 agents, async) ------------------- #
class TestEightAgentBuild:
    """One shared build: latency, live progress, per-agent models, files, preview, zip."""

    @pytest.fixture(scope="class")
    def build_run(self, regular_user):
        client = regular_user["client"]
        t0 = time.time()
        r = client.post(f"{BASE_URL}/api/build",
                        json={"idea": "TEST_ a simple todo list app", "models": OVERRIDES},
                        timeout=60)
        elapsed = time.time() - t0
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        post = r.json()
        app_id = post["id"]

        # poll and record the live timeline
        snapshots = []
        deadline = time.time() + 240
        final = None
        while time.time() < deadline:
            p = client.get(f"{BASE_URL}/api/apps/{app_id}", timeout=60)
            assert p.status_code == 200, p.text[:200]
            doc = p.json()
            snapshots.append({"progress": doc.get("progress"),
                              "statuses": {a["id"]: a["status"] for a in doc.get("agents", [])}})
            if doc.get("status") in ("done", "error"):
                final = doc
                break
            time.sleep(3)
        assert final is not None, f"build did not finish in 240s; last={snapshots[-1]}"
        return {"post": post, "elapsed": elapsed, "final": final,
                "snapshots": snapshots, "app_id": app_id}

    def test_post_build_is_fast_and_queues_8_agents(self, build_run):
        assert build_run["elapsed"] < 5, f"POST /api/build took {build_run['elapsed']:.1f}s"
        post = build_run["post"]
        assert post["status"] == "running"
        assert isinstance(post["id"], str) and post["id"]
        agents = post["agents"]
        assert len(agents) == 8, [a["id"] for a in agents]
        assert [a["id"] for a in agents] == AGENT_IDS
        assert all(a["status"] == "queued" for a in agents), agents

    def test_progress_climbs_and_agents_transition(self, build_run):
        progresses = [s["progress"] for s in build_run["snapshots"]]
        assert progresses[0] is not None
        assert progresses == sorted(progresses), f"progress not monotonic: {progresses}"
        assert max(progresses) == 100, progresses
        assert len(set(progresses)) > 2, f"progress never moved incrementally: {progresses}"
        # every agent must have been observed in a non-queued state
        seen = {aid: set() for aid in AGENT_IDS}
        for s in build_run["snapshots"]:
            for aid, st in s["statuses"].items():
                seen[aid].add(st)
        for aid in AGENT_IDS:
            assert seen[aid] - {"queued"}, f"agent {aid} never left 'queued': {seen[aid]}"

    def test_final_agents_done_with_contribution_and_model(self, build_run):
        final = build_run["final"]
        assert final["status"] == "done", final.get("error", "")[:300]
        assert final["progress"] == 100
        agents = {a["id"]: a for a in final["agents"]}
        assert set(agents) == set(AGENT_IDS)
        for aid, a in agents.items():
            assert a["status"] == "done", f"{aid} -> {a['status']} ({a.get('contribution')})"
            assert a.get("contribution"), f"{aid} has no contribution string"
            assert a["model"] in MODEL_IDS

    def test_per_agent_model_override_applied(self, build_run):
        agents = {a["id"]: a for a in build_run["final"]["agents"]}
        for aid, mid in OVERRIDES.items():
            assert agents[aid]["model"] == mid, f"{aid}: {agents[aid]['model']} != {mid}"
        # non-overridden agents keep their defaults
        assert agents["architect"]["model"] == "gpt-5.4"
        assert agents["database"]["model"] == "gpt-5.4"

    def test_plan_and_files_generated(self, build_run):
        final = build_run["final"]
        assert len(final["plan"]) > 500, len(final["plan"])
        files = final["files"]
        paths = [f["path"] for f in files]
        assert len(paths) == len(set(paths)), "duplicate paths in files[]"
        assert len(files) >= 30, f"only {len(files)} files: {paths}"
        assert all(f.get("content") for f in files), "empty file content"
        assert any(p.endswith("README.md") for p in paths)
        assert any(p.startswith("backend/") for p in paths)
        assert any(p.startswith("frontend/") for p in paths)

    def test_preview_html_is_vanilla_and_complete(self, build_run):
        html = build_run["final"]["preview_html"]
        assert html, "preview_html empty"
        assert html.strip().lower().endswith("</html>")
        assert "Preview unavailable" not in html
        low = html.lower()
        uses_react = ("reactdom" in low) or ("createroot" in low) or ("react-dom" in low)
        assert not (uses_react and "babel" not in low), "JSX/React preview without babel"
        assert low.count("</html>") == 1

    def test_zip_download(self, build_run, regular_user):
        r = regular_user["client"].get(
            f"{BASE_URL}/api/apps/{build_run['app_id']}/zip", timeout=120)
        assert r.status_code == 200, r.status_code
        assert "zip" in r.headers.get("content-type", "")
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        assert zf.testzip() is None, "zip CRC failure"
        names = zf.namelist()
        assert len(names) == len(set(names)), "duplicate zip entries"
        assert "preview/index.html" in names
        for f in build_run["final"]["files"]:
            assert f["path"] in names, f"{f['path']} missing from zip"

    def test_app_scoping_and_auth(self, build_run, super_admin, anon_client):
        app_id = build_run["app_id"]
        other = super_admin["client"]
        assert other.get(f"{BASE_URL}/api/apps/{app_id}", timeout=30).status_code == 404
        assert other.get(f"{BASE_URL}/api/apps/{app_id}/zip", timeout=30).status_code == 404
        assert anon_client.get(f"{BASE_URL}/api/apps/{app_id}", timeout=30).status_code == 401
        assert anon_client.get(f"{BASE_URL}/api/apps/{app_id}/zip", timeout=30).status_code == 401

    def test_invalid_model_id_falls_back_to_default(self, regular_user):
        r = regular_user["client"].post(
            f"{BASE_URL}/api/build",
            json={"idea": "TEST_ fallback check", "models": {"backend": "not-a-model"}},
            timeout=60)
        assert r.status_code == 200, r.text[:300]
        agents = {a["id"]: a for a in r.json()["agents"]}
        assert agents["backend"]["model"] == "claude-sonnet-4-6"
