"""Run every situation in tests/situations.json once through the agent, then the Checker on that same output.

Run (takes a few minutes; pauses between runs so Wikipedia doesn't rate-limit us):
    .venv/bin/python tests/run_checker_tests.py
Writes tests/checker_results.json and tests/checker_results.md, and keeps each run's raw output
(unchecked tips + fetched page text) in tests/raw/ for the planted-bad-tip test.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.agent import CoachError, coach  # noqa: E402

TESTS = Path(__file__).resolve().parent
PAUSE_SECONDS = 20


def tokens(u: dict) -> dict:
    return {k: u[k] for k in ("input", "cached", "cache_write", "output", "requests", "cost_usd")}


async def run_one(case: dict) -> dict:
    t0 = time.monotonic()
    try:
        r = await coach(case["situation"], checker=True, source="test-set", debug=True)
    except CoachError as exc:
        return {**case, "error": str(exc), "seconds_total": round(time.monotonic() - t0, 2)}
    d, chk = r["debug"], r["check"]
    (TESTS / "raw").mkdir(exist_ok=True)
    (TESTS / "raw" / f"{case['id']}.json").write_text(json.dumps(
        {"situation": case["situation"], "raw_tips": d["raw_tips"], "pages": d["pages"], "trail": r["trail"]},
        ensure_ascii=False, indent=1))
    removed_code = [{"tip": x["tip"], "source_title": x["source_title"], "reason": x["reason"]}
                    for x in chk["removed"] if x["stage"] == "code"]
    removed_model = [{"tip": x["tip"], "source_title": x["source_title"], "reason": x["reason"],
                      "which": "not supported" if x["verdict"]["support"] == "not" else "not a custom"}
                     for x in chk["removed"] if x["stage"] == "model"]
    return {
        **case,
        "tips_before": chk["before"],
        "removed_by_code_check": removed_code,
        "removed_by_model_check": removed_model,
        "partly_supported": [t["tip"] for t in r["card"]["tips"] if t.get("support") == "partly"],
        "tips_after": chk["kept"],
        "fully_checked": chk["fully_checked"],
        "model_check_error": chk["model_error"],
        "limited_coverage": (r.get("coverage") or {}).get("limited"),
        "agent": {**tokens(d["agent_usage"]), "seconds": d["agent_seconds"]},
        "checker": {**tokens(d["checker_usage"]), "seconds": chk["seconds"]},
        "models": r["usage"]["models"],
        "seconds_total": round(time.monotonic() - t0, 2),
    }


def report(results: list[dict]) -> str:
    ok = [r for r in results if "error" not in r]
    before = sum(r["tips_before"] for r in ok)
    code = sum(len(r["removed_by_code_check"]) for r in ok)
    model = sum(len(r["removed_by_model_check"]) for r in ok)
    partly = sum(len(r["partly_supported"]) for r in ok)
    after = sum(r["tips_after"] for r in ok)
    pct = lambda n: f"{100 * n / before:.0f}%" if before else "n/a"  # noqa: E731
    a_cost = sum(r["agent"]["cost_usd"] for r in ok)
    c_cost = sum(r["checker"]["cost_usd"] for r in ok)
    lines = [
        "# Checker results", "",
        f"{len(results)} situations, each run once; the Checker was applied to that same agent output.", "",
        "## Totals", "",
        "| | count | share of tips |", "|---|---|---|",
        f"| Tips from the agent (before) | {before} | 100% |",
        f"| Removed by the code check | {code} | {pct(code)} |",
        f"| Removed by the model check | {model} | {pct(model)} |",
        f"| Kept (shown) | {after} | {pct(after)} |",
        f"| ...of which tagged \"partly supported\" | {partly} | {pct(partly)} |", "",
        f"- Runs with errors: {len(results) - len(ok)}",
        f"- Runs where the model check did not finish (not fully checked): {sum(not r['fully_checked'] for r in ok)}",
        f"- Agent cost: ${a_cost:.5f} total, ${a_cost / max(len(ok), 1):.5f} per run",
        f"- Checker cost: ${c_cost:.5f} total, ${c_cost / max(len(ok), 1):.5f} per run "
        f"({100 * c_cost / max(a_cost + c_cost, 1e-12):.0f}% of the total)",
        f"- Average seconds: agent {sum(r['agent']['seconds'] for r in ok) / max(len(ok), 1):.1f}, "
        f"checker {sum(r['checker']['seconds'] for r in ok) / max(len(ok), 1):.1f}", "",
        "## Per situation", "",
        "| situation | before | code removed | model removed | partly | kept | agent $ | checker $ | seconds |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        if "error" in r:
            lines.append(f"| {r['situation']} | error: {r['error']} | | | | | | | {r['seconds_total']} |")
            continue
        lines.append(f"| {r['situation']} | {r['tips_before']} | {len(r['removed_by_code_check'])} | "
                     f"{len(r['removed_by_model_check'])} | {len(r['partly_supported'])} | {r['tips_after']} | "
                     f"{r['agent']['cost_usd']:.5f} | {r['checker']['cost_usd']:.5f} | {r['seconds_total']} |")
    lines += ["", "## Every removed tip", ""]
    for r in ok:
        for x in r["removed_by_code_check"]:
            lines.append(f"- **{r['situation']}**, code check: \"{x['tip']}\" ({x['source_title']}): {x['reason']}")
        for x in r["removed_by_model_check"]:
            lines.append(f"- **{r['situation']}**, model check ({x['which']}): \"{x['tip']}\" ({x['source_title']}): {x['reason']}")
    if not any(r["removed_by_code_check"] or r["removed_by_model_check"] for r in ok):
        lines.append("- None.")
    lines += ["", "## Partly supported (kept, tagged)", ""]
    lines += [f"- **{r['situation']}**: \"{t}\"" for r in ok for t in r["partly_supported"]] or ["- None."]
    return "\n".join(lines) + "\n"


async def main() -> None:
    cases = json.loads((TESTS / "situations.json").read_text())
    results = []
    for i, case in enumerate(cases):
        if i:
            await asyncio.sleep(PAUSE_SECONDS)
        print(f"[{i + 1}/{len(cases)}] {case['situation']}", flush=True)
        res = await run_one(case)
        results.append(res)
        print("   ", "error: " + res["error"] if "error" in res else
              f"before {res['tips_before']}, code -{len(res['removed_by_code_check'])}, "
              f"model -{len(res['removed_by_model_check'])}, partly {len(res['partly_supported'])}, "
              f"kept {res['tips_after']}, {res['seconds_total']}s", flush=True)
        (TESTS / "checker_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    (TESTS / "checker_results.md").write_text(report(results))
    print("wrote tests/checker_results.json and tests/checker_results.md")


if __name__ == "__main__":
    asyncio.run(main())
