"""Wikipedia tools. Everything returned here is untrusted text: data for the agent, never instructions."""

import asyncio
import html
import re

import httpx

API_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "Customs/0.1 (cultural situation coach; student course project) python-httpx"
TIMEOUT = 15.0
MAX_ATTEMPTS = 4
MAX_WAIT_SECONDS = 15.0
MIN_GAP_SECONDS = 1.0  # space out all Wikipedia requests app-wide; bursts of parallel fetches trigger 429s

_pace_lock = asyncio.Lock()
_last_request = 0.0


async def _pace() -> None:
    global _last_request
    async with _pace_lock:
        loop = asyncio.get_running_loop()
        wait = _last_request + MIN_GAP_SECONDS - loop.time()
        if wait > 0:
            await asyncio.sleep(wait)
        _last_request = loop.time()

MAX_RESULTS = 5
MAX_INTRO_CHARS = 1500
MAX_SECTION_CHARS = 800
MAX_TOTAL_CHARS = 6000
SKIP_SECTIONS = {"see also", "references", "notes", "further reading", "external links", "bibliography",
                 "sources", "citations", "footnotes"}


async def _get(params: dict) -> dict:
    """GET the API with a short retry on 429/5xx (honoring Retry-After, capped)."""
    # Wikimedia blocks httpx's default Accept-Encoding (br/zstd) with a 403 robot-policy error; gzip is accepted.
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"},
                                 timeout=TIMEOUT) as client:
        for attempt in range(MAX_ATTEMPTS):
            await _pace()
            resp = await client.get(API_URL, params=params)
            if resp.status_code != 429 and resp.status_code < 500 or attempt == MAX_ATTEMPTS - 1:
                break
            retry_after = resp.headers.get("retry-after", "")
            await asyncio.sleep(min(float(retry_after) if retry_after.isdigit() else 2 ** (attempt + 1), MAX_WAIT_SECONDS))
    resp.raise_for_status()
    return resp.json()


def _clean_snippet(snippet: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", snippet)).strip()


def _cap(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " …"


async def search_wikipedia(query: str, limit: int = MAX_RESULTS) -> list[dict]:
    """Search English Wikipedia. Returns up to `limit` results: title, short snippet, url."""
    params = {"action": "query", "list": "search", "srsearch": query, "srlimit": min(limit, MAX_RESULTS),
              "format": "json", "formatversion": 2}
    hits = (await _get(params)).get("query", {}).get("search", [])
    return [{"title": h["title"], "snippet": _clean_snippet(h.get("snippet", "")),
             "url": "https://en.wikipedia.org/wiki/" + h["title"].replace(" ", "_")} for h in hits]


def _split_sections(extract: str) -> tuple[str, list[dict]]:
    """Split a plain-text extract on '== Heading ==' lines into the intro and top-level-or-deeper sections."""
    parts = re.split(r"^(={2,})\s*(.+?)\s*\1\s*$", extract, flags=re.M)
    intro = parts[0].strip()
    sections = []
    for i in range(1, len(parts) - 2, 3):
        heading, body = parts[i + 1].strip(), parts[i + 2].strip()
        if body and heading.lower() not in SKIP_SECTIONS:
            sections.append({"heading": heading, "text": body})
    return intro, sections


async def fetch_wikipedia_page(title: str, section: str | None = None) -> dict:
    """Fetch a page's plain-text intro and sections (length-capped) plus its canonical URL.

    `all_headings` always lists every section, so a section cut by the cap can be fetched by name via `section`.
    """
    params = {"action": "query", "prop": "extracts|info", "explaintext": 1, "inprop": "url", "titles": title,
              "redirects": 1, "format": "json", "formatversion": 2}
    pages = (await _get(params)).get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return {"title": title, "found": False, "url": None, "intro": "", "sections": [], "all_headings": [],
                "truncated": False}
    page = pages[0]
    intro, sections = _split_sections(page.get("extract", ""))
    all_headings = [s["heading"] for s in sections]
    intro = _cap(intro, MAX_INTRO_CHARS)
    if section:
        sections = [s for s in sections if s["heading"].lower() == section.strip().lower()]
    budget = MAX_TOTAL_CHARS - len(intro)
    kept, truncated = [], False
    for sec in sections:
        text = _cap(sec["text"], MAX_SECTION_CHARS)
        if len(text) < len(sec["text"]):
            truncated = True
        if budget - len(text) < 0:
            truncated = True
            break
        budget -= len(text)
        kept.append({"heading": sec["heading"], "text": text})
    return {"title": page["title"], "found": True, "url": page.get("fullurl"), "intro": intro,
            "sections": kept, "all_headings": all_headings, "truncated": truncated}
