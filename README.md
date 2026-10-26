# Customs

**Customs** is an AI etiquette coach for travelers and hosts. Describe a situation, such as a business dinner with a client's boss in Seoul or a wedding in India, and Visa, a vintage flight attendant, researches Wikipedia and returns a short card of polite do's and don'ts. Each tip links to its source, explains the history behind the custom, and quotes the page word for word. Every quote is checked against what was actually fetched before you see it.

## Setup (about 5 minutes)

Run these commands from inside this folder (`customs/`). They are written for macOS/Linux; on Windows, use `.venv\Scripts\python` instead of `.venv/bin/python`.

1. Install Python 3.11 or newer, and check it with `python3 --version`.
2. Create a virtual environment and install the dependencies. This takes about 15 seconds when pip has the packages cached, and a minute or two on a fresh machine:
   ```bash
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   ```
3. Add your Portkey key. Copy `.env.example` to `.env` and set `PORTKEY_API_KEY`. The app looks for `.env` in this folder first, then in the folder above it, so a `.env` one level up also works.
4. Start the app (one command), then open http://127.0.0.1:8000. Stop it with Ctrl+C.
   ```bash
   .venv/bin/python -m uvicorn app.main:app --port 8000
   ```
   If port 8000 is already in use, pick another (for example `--port 8001`) and open that address instead.
5. Optional checks (the second makes one tiny paid model call):
   ```bash
   .venv/bin/python scripts/check_wiki.py
   ```
   ```bash
   .venv/bin/python scripts/check_model.py
   ```

## Notes

- Model: `gpt-6-luna` only, through Portkey's Responses route. A reply from any other model is rejected.
- Limits (all in `app/config.py`): 8 tool calls and 10 model requests per run, an output-token cap on each request, and situations up to 500 characters.
- Each run appends its time, situation, tool calls, token counts and dollar cost to `usage_log.json`. Prices come from `prices.json`.
- Wikipedia text is treated as data, never as instructions.
- When the page opens, Visa, a made-up vintage flight attendant, welcomes you with fixed text (no AI call). Once a result shows, her welcome shrinks. Advice is introduced by Visa. Her lines carry no facts. If fewer than 2 pages were fetched or fewer than 4 tips are shown, the code adds a limited-coverage note.
- The "Where to next?" panel lists about 200 countries and regions. Clicking one, or clicking a country on the world map, fills the text box; press Go to send. Countries also show a passport-style facts panel: flag, capital, languages, currency, population, driving side and signature dish, with a link to Wikipedia.

## Limits and budget

All limits are in `app/config.py`:
- A daily spending cap of $2.00, counted from `usage_log.json`.
- 15 questions per visitor per hour.
- 500 characters per situation.
- 8 Wikipedia lookups and 10 model requests per question.

When a budget limit or the length limit is hit, Visa politely refuses before any AI call is made.

Test reports are in `tests/`:
- `checker_results.md`: the Checker on 10 situations.
- `safety_tests.md`: prompt injection, jailbreak attempts, tools and links.
- `tokenomics.md`: measured costs, the cache comparison, checker on vs off, and cost per user.

## The Checker

After the agent answers, every tip is checked before it is shown:
1. **Code check:** the tip must cite a page the agent actually fetched, and its excerpt must appear word for word on that page (ignoring case and spacing; excerpts are trimmed to 30 words).
2. **Model check:** one extra gpt-6-luna call sees only each tip, its "why" line and its excerpt. It asks whether the excerpt supports the tip and whether the tip is a real custom rather than a fact. Unsupported tips and non-customs are removed; partly supported tips get a small tag.

The page shows "Checked against Wikipedia: N of M tips verified" with a list of removed tips, and the token panel shows the checker's cost on its own line. The checker is on by default. To measure without it, add `CUSTOMS_CHECKER=off` to `.env` and restart.

Tests (each writes its results to `tests/`):
- **Paid model calls**, run with `.venv/bin/python`:
  - `tests/run_checker_tests.py` runs the 10 situations. Run it first, because the planted test reuses its saved output.
  - `tests/planted_test.py`
  - `tests/safety_tests.py`
  - `tests/outage_tests.py`
  - `tests/cache_test.py`
- **Reports:** `tests/tokenomics.py` rebuilds the cost report from the saved runs, with no new calls.
- **Browser tests:** `tests/limits_test.py` and `tests/outage_page_test.py` drive the page in Google Chrome. They need Playwright, which the app itself doesn't (`pip install playwright` in any Python). `limits_test.py` starts and stops its own server on port 8001; `outage_page_test.py` needs the app running on port 8000.

```bash
.venv/bin/python tests/run_checker_tests.py
```

## Data and credits

- **World map:** [Natural Earth](https://www.naturalearthdata.com/) 1:110m Admin 0 countries (public domain). `static/map.svg` is built once with `scripts/build_map.py`. Borders are approximate and imply no position.
- **Country facts:** [Wikidata](https://www.wikidata.org/) (CC0) and English Wikipedia's [National dish](https://en.wikipedia.org/wiki/National_dish) article (CC BY-SA). `static/facts.json` is built once with `scripts/build_facts.py`. Missing facts are left out.
- **Flags:** [flag-icons](https://github.com/lipis/flag-icons) by Panayiotis Lipiridis (MIT; license in `static/flags/LICENSE-flag-icons.txt`).

To rebuild the data (optional; the built files are committed):
```bash
.venv/bin/pip install -r requirements-build.txt
```
```bash
.venv/bin/python -I scripts/build_map.py
```
```bash
.venv/bin/python -I scripts/build_facts.py
```
