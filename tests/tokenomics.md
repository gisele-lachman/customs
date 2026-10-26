# Customs tokenomics

All numbers come from real runs of gpt-6-luna through Portkey (no estimates): the 10-situation test set (`checker_results.json`) and the 4-situation cache comparison (`cache_runs.json`). Token counts are the ones the API reported.

Prices (per 1M tokens, `prices.json`): input $0.100, cached input $0.010, cache write $0.125, output $0.500.

## 1. Average per run (10 situations, checker on)

| | input tokens | cached tokens | output tokens | model requests | cost | share of cost | seconds |
|---|---|---|---|---|---|---|---|
| Agent | 11,493 | 6,663 | 695 | 3.5 | $0.00101 | 88% | 22.3 |
| Checker | 661 | 0 | 137 | 0.9 | $0.00013 | 12% | 2.1 |
| **Total** | 12,154 | 6,663 | 831 | | **$0.00114** | 100% | 24.4 (end to end) |

## 2. Cache comparison (same 4 situations, run twice)

The second set ran with `CUSTOMS_DEFEAT_CACHE=on`, which puts a random line at the very start of every model call (agent and checker), so no prompt prefix can be reused. The switch is off by default.

| | runs | cached tokens (agent + checker) | input tokens | output tokens | total cost | avg cost/run | avg seconds | tips kept / before | partly | removed |
|---|---|---|---|---|---|---|---|---|---|---|
| Normal | 4 | 20,431 | 43,214 | 3,848 | $0.00486 | $0.00121 | 19.4 | 20 / 21 | 9 | 1 |
| Cache defeated | 4 | 0 | 41,913 | 3,694 | $0.00697 | $0.00174 | 18.5 | 20 / 21 | 8 | 1 |

- Cached tokens with caching defeated: **zero**.
- Defeating the cache cost **$0.00211 more** over 4 runs (**+43%**).

| situation | normal cost | cached | kept | defeated cost | cached | kept |
|---|---|---|---|---|---|---|
| Business dinner with my client's boss in Seoul | $0.00139 | 3,413 | 6 | $0.00205 | 0 | 8 |
| Attending a wedding in India | $0.00104 | 7,841 | 5 | $0.00160 | 0 | 5 |
| First business meeting with a German company in Munich | $0.00114 | 4,555 | 4 | $0.00149 | 0 | 3 |
| Having tea with my host family in Morocco | $0.00129 | 4,622 | 5 | $0.00183 | 0 | 4 |

Answer quality is compared by tips kept after the checker, partly-supported tags and removals (see the table above); caching only changes how the prompt prefix is billed, not what the model sees.

## 3. Checker on vs off (same agent output, 10 situations)

| | total cost | tips shown | removed | tagged partly | avg seconds/run |
|---|---|---|---|---|---|
| Checker off | $0.01007 | 45 | 0 | 0 | 22.3 |
| Checker on | $0.01141 | 39 | 6 | 25 | 24.3 |

The checker adds 13% to the cost and removes 6 of 45 tips (13%).

## 4. Cost per user per month

Assumption: 5 situations per user per month. Cost per run = measured average (agent + checker) = $0.001141.

- Per user per month = 5 × $0.001141 = **$0.00571**

| users | runs/month | cost/month (with cache) | cost/month (cache defeated, for comparison) |
|---|---|---|---|
| 1 | 5 | $0.01 | $0.01 |
| 100 | 500 | $0.57 | $0.87 |
| 10,000 | 50,000 | $57.05 | $87.06 |

Math: 100 users × 5 runs × $0.001141 = $0.5705; 10,000 users × 5 runs × $0.001141 = $57.05. The daily budget cap ($2.00 by default) also bounds spending: at most about $60 a month, whatever the traffic.

## 5. Cost-saving steps already built

| step | what it does |
|---|---|
| Brief answers | The prompt asks for one-sentence tips and 1-2 sentence why lines, keeping output tokens (the most expensive at $0.50/1M) low. |
| Low reasoning effort | `reasoning_effort = "low"` limits hidden reasoning tokens, which are billed as output. |
| Token cap per request | `max_output_tokens_per_request = 4000` (agent) and 2500 (checker) stop any runaway answer. |
| Prompt cache | The long instructions sit first and never change, so repeat calls read them as cached input (10× cheaper). Measured in section 2. |
| Tool-call and request caps | At most 8 Wikipedia lookups and 10 model requests per run; each lookup adds page text to every later request. |
| Capped page text | Each fetched page is cut to about 6,000 characters (intro ≤1,500, sections ≤800), and reference sections are skipped. |
| One-call checker | The checker judges all tips in one call, sees only tips, why lines and excerpts (no pages), and uses no tools. |
| Code check first | Unsourced or misquoted tips are dropped in code before the model check, so they cost nothing to judge. |
| Budget guard | Daily spending cap, 15 runs per visitor per hour, and the 500-character input limit refuse before any model call. |
| Static map and facts | `map.svg`, `facts.json` and the flags were built once; showing the map or a country's passport makes no model or API call. |
| No model call for page features | The welcome, the A-to-Z list, the map, the facts panel and "Back to the map" are all plain page code. |
| Off-topic redirect | Non-situations get a short redirect instead of research (one small call). |
