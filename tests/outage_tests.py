"""Outage and edge-case tests through the real HTTP endpoint (FastAPI TestClient, in-process).

1. Wikipedia down (every Wikipedia request raises a connection error).
2. The model call failing (Portkey unreachable).
3. The model check failing (checker call raises) -> tips shown as "not fully checked".
4. A zero-tip result (the checker removes every tip) -> Visa's limited-coverage note, not an empty card.
Each response is saved to tests/outages/<name>.json (status + body) so the page rendering can be checked in a
browser; each run must also add a usage_log.json entry. Run: .venv/bin/python tests/outage_tests.py
"""

import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import app.agent as agent_mod  # noqa: E402
import app.checker as checker_mod  # noqa: E402
import app.config as config_mod  # noqa: E402
import app.wiki as wiki_mod  # noqa: E402
from app.main import app  # noqa: E402

TESTS = Path(__file__).resolve().parent
OUT = TESTS / "outages"
PAUSE = 20


def log_len() -> int:
    return len(json.loads(config_mod.USAGE_LOG.read_text())) if config_mod.USAGE_LOG.exists() else 0


def post(client: TestClient, name: str, situation: str) -> dict:
    n0 = log_len()
    resp = client.post("/api/coach", json={"situation": situation})
    body = resp.json()
    OUT.mkdir(exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps({"status": resp.status_code, "body": body}, ensure_ascii=False, indent=2))
    entries = json.loads(config_mod.USAGE_LOG.read_text())[n0:]
    return {"status": resp.status_code, "body": body, "logged": [e.get("outcome") for e in entries]}


def main() -> None:
    with TestClient(app) as client:  # one event loop for all requests, like the real server
        run_all(client)


def run_all(client: TestClient) -> None:
    results = []

    # 1. Wikipedia down
    real_get = wiki_mod._get

    async def wikipedia_down(params):
        raise httpx.ConnectError("simulated: Wikipedia is down")
    wiki_mod._get = wikipedia_down
    try:
        r = post(client, "wikipedia_down", "Attending a wedding in India")
    finally:
        wiki_mod._get = real_get
    results.append({"test": "Wikipedia down", "status": r["status"], "message": r["body"].get("error"),
                    "logged": r["logged"],
                    "pass": r["status"] >= 400 and "Wikipedia" in (r["body"].get("error") or "") and bool(r["logged"])})
    print(results[-1], flush=True)
    time.sleep(PAUSE)

    # 2. Model call failing (Portkey unreachable)
    real_url, agent_mod._agent = config_mod.PORTKEY_BASE_URL, None
    config_mod.PORTKEY_BASE_URL = "http://127.0.0.1:9/v1"  # nothing listens here
    try:
        r = post(client, "model_down", "Business dinner with my client's boss in Seoul")
    finally:
        config_mod.PORTKEY_BASE_URL, agent_mod._agent = real_url, None
    results.append({"test": "model call failing", "status": r["status"], "message": r["body"].get("error"),
                    "logged": r["logged"],
                    "pass": r["status"] >= 400 and "couldn't reach the ai model" in (r["body"].get("error") or "").lower()
                    and bool(r["logged"])})
    print(results[-1], flush=True)

    # 3. Model check failing
    class BrokenChecker:
        async def run(self, *a, **k):
            raise RuntimeError("simulated: checker call failed")
    real_gca = checker_mod.get_check_agent
    checker_mod.get_check_agent = lambda: BrokenChecker()
    try:
        r = post(client, "model_check_failed", "Having tea with my host family in Morocco")
    finally:
        checker_mod.get_check_agent = real_gca
    chk = r["body"].get("check") or {}
    tips = (r["body"].get("card") or {}).get("tips", [])
    results.append({"test": "model check failing", "status": r["status"], "fully_checked": chk.get("fully_checked"),
                    "tips_shown": len(tips), "supports": sorted({t.get("support") for t in tips}), "logged": r["logged"],
                    "pass": r["status"] == 200 and chk.get("fully_checked") is False and len(tips) > 0
                    and all(t.get("support") == "unchecked" for t in tips) and bool(r["logged"])})
    print(results[-1], flush=True)
    time.sleep(PAUSE)

    # 4. Zero tips after checking
    real_check = agent_mod.check_tips

    async def remove_everything(situation, tips, pages):
        res = await real_check(situation, [], pages)  # nothing passes
        res["before"] = len(tips)
        res["removed"] = [{"kind": t["kind"], "tip": t["tip"], "source_title": t["source_title"], "evidence": t["evidence"],
                           "stage": "code", "reason": "simulated: removed for the zero-tip test"} for t in tips]
        return res
    agent_mod.check_tips = remove_everything
    try:
        r = post(client, "zero_tips", "Attending a funeral in Nauru")
    finally:
        agent_mod.check_tips = real_check
    cov = r["body"].get("coverage") or {}
    results.append({"test": "zero-tip result", "status": r["status"], "tips_shown": len((r["body"].get("card") or {}).get("tips", [])),
                    "coverage": cov, "logged": r["logged"],
                    "pass": r["status"] == 200 and cov.get("limited") is True and bool(cov.get("note")) and bool(r["logged"])})
    print(results[-1], flush=True)

    (TESTS / "outage_tests.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
