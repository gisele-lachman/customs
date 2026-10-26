"""Build tests/tokenomics.json and tests/tokenomics.md from real runs only (no estimates):
- tests/checker_results.json: 10 situations, agent + checker on the same output
- tests/cache_runs.json: 4 situations normally and with caching defeated
Prices come from prices.json. Run: .venv/bin/python tests/tokenomics.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
RUNS_PER_USER_PER_MONTH = 5
USER_COUNTS = [1, 100, 10_000]


def avg(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def main() -> None:
    prices = json.loads((ROOT / "prices.json").read_text())["gpt-6-luna"]
    test_set = [r for r in json.loads((TESTS / "checker_results.json").read_text()) if "error" not in r]
    cache_runs = [r for r in json.loads((TESTS / "cache_runs.json").read_text()) if "error" not in r]

    # ---- 1. per-run averages (10-situation test set) ----
    def part(key):
        return {k: avg(r[key][k] for r in test_set) for k in ("input", "cached", "output", "cost_usd", "seconds", "requests")}
    agent, checker = part("agent"), part("checker")
    total_cost = agent["cost_usd"] + checker["cost_usd"]
    per_run = {
        "runs": len(test_set),
        "agent": {**agent, "share_of_cost": agent["cost_usd"] / total_cost},
        "checker": {**checker, "share_of_cost": checker["cost_usd"] / total_cost},
        "total": {"cost_usd": total_cost, "seconds": avg(r["seconds_total"] for r in test_set),
                  "input": agent["input"] + checker["input"], "cached": agent["cached"] + checker["cached"],
                  "output": agent["output"] + checker["output"]},
    }

    # ---- 2. cache comparison ----
    by_mode = {m: [r for r in cache_runs if r["mode"] == m] for m in ("normal", "cache defeated")}
    def mode_stats(rows):
        return {"runs": len(rows),
                "agent_cached_tokens": sum(r["agent"]["cached"] for r in rows),
                "checker_cached_tokens": sum(r["checker"]["cached"] for r in rows),
                "input_tokens": sum(r["agent"]["input"] + r["checker"]["input"] for r in rows),
                "output_tokens": sum(r["agent"]["output"] + r["checker"]["output"] for r in rows),
                "total_cost_usd": sum(r["total_cost_usd"] for r in rows),
                "avg_cost_usd": avg(r["total_cost_usd"] for r in rows),
                "avg_seconds": avg(r["seconds"] for r in rows),
                "tips_kept": sum(r["tips_kept"] for r in rows), "tips_before": sum(r["tips_before"] for r in rows),
                "partly": sum(r["partly"] for r in rows), "removed": sum(r["removed"] for r in rows),
                "limited_coverage_runs": sum(bool(r["limited_coverage"]) for r in rows)}
    normal, defeated = mode_stats(by_mode["normal"]), mode_stats(by_mode["cache defeated"])
    diff = defeated["total_cost_usd"] - normal["total_cost_usd"]
    cache = {"normal": normal, "cache_defeated": defeated,
             "zero_cached_when_defeated": defeated["agent_cached_tokens"] == 0 and defeated["checker_cached_tokens"] == 0,
             "extra_cost_without_cache_usd": diff,
             "extra_cost_without_cache_pct": 100 * diff / normal["total_cost_usd"] if normal["total_cost_usd"] else None,
             "per_situation": [{"situation": s,
                                **{m: next(({"cost_usd": r["total_cost_usd"], "cached": r["agent"]["cached"] + r["checker"]["cached"],
                                             "tips_kept": r["tips_kept"], "partly": r["partly"], "removed": r["removed"]}
                                            for r in by_mode[m] if r["situation"] == s), None)
                                   for m in ("normal", "cache defeated")}}
                               for s in dict.fromkeys(r["situation"] for r in cache_runs)]}

    # ---- 3. checker on vs off, same agent output ----
    on_off = {"runs": len(test_set),
              "cost_off_usd": sum(r["agent"]["cost_usd"] for r in test_set),
              "cost_on_usd": sum(r["agent"]["cost_usd"] + r["checker"]["cost_usd"] for r in test_set),
              "tips_shown_off": sum(r["tips_before"] for r in test_set),
              "tips_shown_on": sum(r["tips_after"] for r in test_set),
              "removed_on": sum(len(r["removed_by_code_check"]) + len(r["removed_by_model_check"]) for r in test_set),
              "partly_tagged_on": sum(len(r["partly_supported"]) for r in test_set),
              "seconds_off": avg(r["agent"]["seconds"] for r in test_set),
              "seconds_on": avg(r["agent"]["seconds"] + r["checker"]["seconds"] for r in test_set)}
    on_off["extra_cost_pct"] = 100 * (on_off["cost_on_usd"] - on_off["cost_off_usd"]) / on_off["cost_off_usd"]

    # ---- 4. per user per month ----
    monthly = {"runs_per_user_per_month": RUNS_PER_USER_PER_MONTH, "cost_per_run_usd": total_cost,
               "cost_per_user_per_month_usd": total_cost * RUNS_PER_USER_PER_MONTH,
               "by_users": {n: total_cost * RUNS_PER_USER_PER_MONTH * n for n in USER_COUNTS},
               "without_cache_by_users": {n: defeated["avg_cost_usd"] * RUNS_PER_USER_PER_MONTH * n for n in USER_COUNTS},
               "note": "cost_per_run is the measured average of the 10-situation test set (agent + checker)."}

    out = {"prices_per_1m_tokens": prices, "per_run": per_run, "cache_comparison": cache,
           "checker_on_vs_off": on_off, "per_user_per_month": monthly}
    (TESTS / "tokenomics.json").write_text(json.dumps(out, indent=2))
    (TESTS / "tokenomics.md").write_text(render_md(out))
    print("wrote tests/tokenomics.json and tests/tokenomics.md")


def money(x, d=5):
    return f"${x:,.{d}f}"


def render_md(o: dict) -> str:
    p, pr, c, oo, m = o["prices_per_1m_tokens"], o["per_run"], o["cache_comparison"], o["checker_on_vs_off"], o["per_user_per_month"]
    a, k, t = pr["agent"], pr["checker"], pr["total"]
    n, d = c["normal"], c["cache_defeated"]
    L = [
        "# Customs tokenomics", "",
        "All numbers come from real runs of gpt-6-luna through Portkey (no estimates): the 10-situation test set "
        "(`checker_results.json`) and the 4-situation cache comparison (`cache_runs.json`). Token counts are the ones the "
        "API reported.", "",
        f"Prices (per 1M tokens, `prices.json`): input {money(p['input_per_1m'], 3)}, cached input "
        f"{money(p['cached_input_per_1m'], 3)}, cache write {money(p['cache_write_per_1m'], 3)}, output {money(p['output_per_1m'], 3)}.", "",
        "## 1. Average per run (10 situations, checker on)", "",
        "| | input tokens | cached tokens | output tokens | model requests | cost | share of cost | seconds |",
        "|---|---|---|---|---|---|---|---|",
        f"| Agent | {a['input']:,.0f} | {a['cached']:,.0f} | {a['output']:,.0f} | {a['requests']:.1f} | {money(a['cost_usd'])} | {100 * a['share_of_cost']:.0f}% | {a['seconds']:.1f} |",
        f"| Checker | {k['input']:,.0f} | {k['cached']:,.0f} | {k['output']:,.0f} | {k['requests']:.1f} | {money(k['cost_usd'])} | {100 * k['share_of_cost']:.0f}% | {k['seconds']:.1f} |",
        f"| **Total** | {t['input']:,.0f} | {t['cached']:,.0f} | {t['output']:,.0f} | | **{money(t['cost_usd'])}** | 100% | {t['seconds']:.1f} (end to end) |", "",
        "## 2. Cache comparison (same 4 situations, run twice)", "",
        "The second set ran with `CUSTOMS_DEFEAT_CACHE=on`, which puts a random line at the very start of every model call "
        "(agent and checker), so no prompt prefix can be reused. The switch is off by default.", "",
        "| | runs | cached tokens (agent + checker) | input tokens | output tokens | total cost | avg cost/run | avg seconds | tips kept / before | partly | removed |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
        f"| Normal | {n['runs']} | {n['agent_cached_tokens'] + n['checker_cached_tokens']:,} | {n['input_tokens']:,} | {n['output_tokens']:,} | {money(n['total_cost_usd'])} | {money(n['avg_cost_usd'])} | {n['avg_seconds']:.1f} | {n['tips_kept']} / {n['tips_before']} | {n['partly']} | {n['removed']} |",
        f"| Cache defeated | {d['runs']} | {d['agent_cached_tokens'] + d['checker_cached_tokens']:,} | {d['input_tokens']:,} | {d['output_tokens']:,} | {money(d['total_cost_usd'])} | {money(d['avg_cost_usd'])} | {d['avg_seconds']:.1f} | {d['tips_kept']} / {d['tips_before']} | {d['partly']} | {d['removed']} |", "",
        f"- Cached tokens with caching defeated: **{'zero' if c['zero_cached_when_defeated'] else 'NOT zero'}**.",
        f"- Defeating the cache cost **{money(c['extra_cost_without_cache_usd'])} more** over 4 runs "
        f"(**{c['extra_cost_without_cache_pct']:+.0f}%**).", "",
        "| situation | normal cost | cached | kept | defeated cost | cached | kept |", "|---|---|---|---|---|---|---|",
    ]
    for s in c["per_situation"]:
        nn, dd = s["normal"], s["cache defeated"]
        L.append(f"| {s['situation']} | {money(nn['cost_usd'])} | {nn['cached']:,} | {nn['tips_kept']} | "
                 f"{money(dd['cost_usd'])} | {dd['cached']:,} | {dd['tips_kept']} |")
    L += ["", "Answer quality is compared by tips kept after the checker, partly-supported tags and removals "
          "(see the table above); caching only changes how the prompt prefix is billed, not what the model sees.", "",
          "## 3. Checker on vs off (same agent output, 10 situations)", "",
          "| | total cost | tips shown | removed | tagged partly | avg seconds/run |", "|---|---|---|---|---|---|",
          f"| Checker off | {money(oo['cost_off_usd'])} | {oo['tips_shown_off']} | 0 | 0 | {oo['seconds_off']:.1f} |",
          f"| Checker on | {money(oo['cost_on_usd'])} | {oo['tips_shown_on']} | {oo['removed_on']} | {oo['partly_tagged_on']} | {oo['seconds_on']:.1f} |", "",
          f"The checker adds {oo['extra_cost_pct']:.0f}% to the cost and removes {oo['removed_on']} of {oo['tips_shown_off']} tips "
          f"({100 * oo['removed_on'] / oo['tips_shown_off']:.0f}%).", "",
          "## 4. Cost per user per month", "",
          f"Assumption: {m['runs_per_user_per_month']} situations per user per month. Cost per run = measured average "
          f"(agent + checker) = {money(m['cost_per_run_usd'], 6)}.", "",
          f"- Per user per month = {m['runs_per_user_per_month']} × {money(m['cost_per_run_usd'], 6)} = "
          f"**{money(m['cost_per_user_per_month_usd'], 5)}**", "",
          "| users | runs/month | cost/month (with cache) | cost/month (cache defeated, for comparison) |", "|---|---|---|---|"]
    for users in m["by_users"]:
        L.append(f"| {int(users):,} | {int(users) * m['runs_per_user_per_month']:,} | {money(m['by_users'][users], 2)} | "
                 f"{money(m['without_cache_by_users'][users], 2)} |")
    L += ["", f"Math: 100 users × 5 runs × {money(m['cost_per_run_usd'], 6)} = {money(m['by_users']['100'] if '100' in m['by_users'] else m['by_users'][100], 4)}; "
          f"10,000 users × 5 runs × {money(m['cost_per_run_usd'], 6)} = "
          f"{money(m['by_users']['10000'] if '10000' in m['by_users'] else m['by_users'][10000], 2)}. "
          "The daily budget cap ($2.00 by default) also bounds spending: at most about $60 a month, whatever the traffic.", "",
          "## 5. Cost-saving steps already built", "",
          "| step | what it does |", "|---|---|",
          "| Brief answers | The prompt asks for one-sentence tips and 1-2 sentence why lines, keeping output tokens (the most expensive at $0.50/1M) low. |",
          "| Low reasoning effort | `reasoning_effort = \"low\"` limits hidden reasoning tokens, which are billed as output. |",
          "| Token cap per request | `max_output_tokens_per_request = 4000` (agent) and 2500 (checker) stop any runaway answer. |",
          "| Prompt cache | The long instructions sit first and never change, so repeat calls read them as cached input (10× cheaper). Measured in section 2. |",
          "| Tool-call and request caps | At most 8 Wikipedia lookups and 10 model requests per run; each lookup adds page text to every later request. |",
          "| Capped page text | Each fetched page is cut to about 6,000 characters (intro ≤1,500, sections ≤800), and reference sections are skipped. |",
          "| One-call checker | The checker judges all tips in one call, sees only tips, why lines and excerpts (no pages), and uses no tools. |",
          "| Code check first | Unsourced or misquoted tips are dropped in code before the model check, so they cost nothing to judge. |",
          "| Budget guard | Daily spending cap, 15 runs per visitor per hour, and the 500-character input limit refuse before any model call. |",
          "| Static map and facts | `map.svg`, `facts.json` and the flags were built once; showing the map or a country's passport makes no model or API call. |",
          "| No model call for page features | The welcome, the A-to-Z list, the map, the facts panel and \"Back to the map\" are all plain page code. |",
          "| Off-topic redirect | Non-situations get a short redirect instead of research (one small call). |"]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
