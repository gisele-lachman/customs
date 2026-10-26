"""Show each saved outage response (tests/outages/*.json, from outage_tests.py) on the real page in headless Chrome
by intercepting /api/coach, and check what the visitor sees. No model calls.
Run with a Python that has Playwright installed. Writes tests/outage_page_test.json.
"""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

TESTS = Path(__file__).resolve().parent
URL = "http://127.0.0.1:8000/"
EXPECT = {
    "wikipedia_down": ("#error", "Wikipedia couldn't be reached"),
    "model_down": ("#error", "couldn't reach the AI model"),
    "model_check_failed": ("#result", "Not fully checked"),
    "zero_tips": ("#result", "Wikipedia has limited coverage of this topic"),
}

def serve(saved: dict):
    def handler(route, request):
        route.fulfill(status=saved["status"], content_type="application/json", body=json.dumps(saved["body"]))
    return handler


results = []
with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    for name, (where, text) in EXPECT.items():
        saved = json.loads((TESTS / "outages" / f"{name}.json").read_text())
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.route("**/api/coach", serve(saved))
        page.goto(URL)
        page.wait_for_selector(".country")
        page.fill("#situation", "test")
        page.click("#go")
        page.wait_for_selector(f"{where}:not([hidden])", timeout=10_000)
        page.wait_for_timeout(500)
        shown = page.inner_text(where)
        extra = page.evaluate("""() => ({cardTitle: document.querySelector('.card h2')?.textContent || null,
          tips: document.querySelectorAll('.tip').length, goEnabled: !document.querySelector('#go').disabled,
          backButton: !document.querySelector('#back').hidden})""")
        ok = text.lower() in shown.lower() and not errors and extra["goEnabled"]
        if name == "zero_tips":
            ok = ok and extra["cardTitle"] is not None  # a titled card with Visa's note, not an empty card
        results.append({"case": name, "http_status": saved["status"], "expected_text": text, "pass": ok,
                        "page_text": shown[:600], **extra, "page_errors": errors})
        print("PASS" if ok else "FAIL", name, "|", shown.replace("\n", " ")[:160])
        page.close()
    browser.close()
(TESTS / "outage_page_test.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
