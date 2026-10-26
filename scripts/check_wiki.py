"""Manual check: run both Wikipedia tools on two sample topics."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.wiki import fetch_wikipedia_page, search_wikipedia  # noqa: E402

TOPICS = ["Japanese business card etiquette", "Korean honorifics"]


async def main() -> None:
    for topic in TOPICS:
        print(f"\n=== search: {topic!r}")
        results = await search_wikipedia(topic)
        for r in results:
            print(f"- {r['title']}  ({r['url']})\n    {r['snippet'][:160]}")
        if not results:
            continue
        page = await fetch_wikipedia_page(results[0]["title"])
        size = len(page["intro"]) + sum(len(s["text"]) for s in page["sections"])
        print(f"--- fetch: {page['title']}  found={page['found']}  url={page['url']}")
        print(f"    chars={size}  sections={len(page['sections'])}  truncated={page['truncated']}")
        print(f"    headings: {[s['heading'] for s in page['sections']]}")
        print(f"    intro: {page['intro'][:300]}")
        missing = [h for h in page["all_headings"] if h not in {s["heading"] for s in page["sections"]}]
        print(f"    cut by cap: {missing}")
        if "Business cards" in missing:
            one = await fetch_wikipedia_page(page["title"], section="Business cards")
            print(f"--- fetch section 'Business cards': {one['sections'][0]['text'][:400]}")


if __name__ == "__main__":
    asyncio.run(main())
