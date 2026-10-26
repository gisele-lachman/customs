"""Planted-bad-tip test: take one real run's output (tests/raw/<id>.json), add four fake tips, run the Checker.

Run: .venv/bin/python tests/planted_test.py [run-id]   (default: seoul-dinner; one checker model call)
Writes tests/planted_test.json.
"""

import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.agent import combine_usage, usage_summary  # noqa: E402
from app.checker import check_tips, norm  # noqa: E402

TESTS = Path(__file__).resolve().parent
FOOD_OR_HISTORY = re.compile(r"\b(dish|dishes|food|cuisine|rice|kimchi|soup|noodles?|meat|century|centuries|dynasty|"
                             r"history|historically|ancient|era|period)\b", re.I)


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.replace("\n", " ")) if len(s.split()) >= 8]


def short(sentence: str, n: int = 22) -> str:
    return " ".join(sentence.split()[:n])


async def main(run_id: str) -> None:
    raw = json.loads((TESTS / "raw" / f"{run_id}.json").read_text())
    pages, real = raw["pages"], raw["raw_tips"]
    used = {norm(t["evidence"]) for t in real}
    page = pages[0]
    all_sentences = [(p, s) for p in pages for s in sentences(p["text"]) if norm(short(s)) not in used]
    food = next((p, s) for p, s in all_sentences if FOOD_OR_HISTORY.search(short(s)))
    unrelated = next((p, s) for p, s in all_sentences if (p, s) != food)

    base = {"why": "Planted for testing.", "variation": "widely followed"}
    planted = [
        {"label": "invented excerpt (not on the page)", "expect": "removed by code check",
         "tip": {**base, "kind": "do", "tip": "Bring a small potted cactus as a gift for your host.",
                 "source_title": page["title"], "source_url": page["url"],
                 "evidence": "Guests customarily present a small potted cactus to the host as a sign of lasting friendship."}},
        {"label": "real excerpt that doesn't support the tip", "expect": "removed by model check (not supported)",
         "tip": {**base, "kind": "do", "tip": "Wear bright red shoes to show respect to the most senior guest.",
                 "source_title": unrelated[0]["title"], "source_url": unrelated[0]["url"],
                 "evidence": short(unrelated[1])}},
        {"label": "cites a page that wasn't fetched", "expect": "removed by code check",
         "tip": {**base, "kind": "dont", "tip": "It is considered more courteous not to arrive early.",
                 "source_title": "Etiquette in France", "source_url": "https://en.wikipedia.org/wiki/Etiquette_in_France",
                 "evidence": short(sentences(page["text"])[0])}},
        {"label": "real food/history excerpt that isn't a custom", "expect": "removed by model check (not a custom)",
         # the tip restates its own excerpt, so it is fully supported: only the "is it a custom?" question can catch it
         "tip": {**base, "kind": "do", "tip": short(food[1]).rstrip(".,;:") + ".",
                 "source_title": food[0]["title"], "source_url": food[0]["url"], "evidence": short(food[1])}},
    ]
    tips = real + [p["tip"] for p in planted]
    check = await check_tips(raw["situation"], tips, pages)

    removed = {r["tip"]: r for r in check["removed"]}
    kept = {t["tip"]: t for t in check["tips"]}
    for p in planted:
        r = removed.get(p["tip"]["tip"])
        p["result"] = f"removed by {r['stage']} check: {r['reason']}" if r else "KEPT (checker missed it)"
        p["dropped"] = r is not None
    real_rows = [{"tip": t["tip"], "kept": t["tip"] in kept,
                  "support": kept.get(t["tip"], {}).get("support"),
                  "removed_reason": removed[t["tip"]]["reason"] if t["tip"] in removed else None} for t in real]
    usage = usage_summary(check["responses"])
    out = {
        "source_run": run_id, "situation": raw["situation"],
        "all_planted_dropped": all(p["dropped"] for p in planted),
        "real_tips": len(real), "real_kept": sum(r["kept"] for r in real_rows),
        "planted": planted, "real": real_rows,
        "fully_checked": check["fully_checked"], "model_error": check["model_error"],
        "checker_usage": {k: usage[k] for k in ("input", "cached", "output", "requests", "cost_usd", "models")},
        "seconds": check["seconds"],
    }
    (TESTS / "planted_test.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(json.dumps({k: out[k] for k in ("all_planted_dropped", "real_tips", "real_kept", "fully_checked",
                                         "checker_usage", "seconds")}, indent=1))
    for p in planted:
        print("-", p["label"], "->", p["result"])
    for r in real_rows:
        print("  real:", "kept" if r["kept"] else "REMOVED", r["support"] or r["removed_reason"], "|", r["tip"][:70])


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "seoul-dinner"))
