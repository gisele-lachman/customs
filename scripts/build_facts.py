"""Build static/facts.json and static/flags/ once.

Run: .venv/bin/python -I scripts/build_facts.py
- Facts: bulk Wikidata SPARQL queries (by ISO code and by Natural Earth's Wikidata ID) (capital, official languages, currency, population, driving side,
  English Wikipedia article) for every country code in static/places.json.
- Signature dish: the country's entry in English Wikipedia's "National dish" article (first dish listed).
- Flags: the MIT-licensed flag-icons package (4x3 SVGs), only the codes we need, plus its LICENSE.
Missing facts are left out. Nothing is filled in by hand.
"""

import io
import json
import re
import sys
import tarfile
import time
from datetime import date
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".build_cache"
OUT = ROOT / "static" / "facts.json"
FLAGS = ROOT / "static" / "flags"
USER_AGENT = "Customs/0.1 (cultural situation coach; student course project) build-script"
SPARQL_URL = "https://query.wikidata.org/sparql"
WIKI_API = "https://en.wikipedia.org/w/api.php"
DISH_PAGE = "National dish"
FLAG_ICONS_URL = "https://registry.npmjs.org/flag-icons/-/flag-icons-7.6.0.tgz"
SOVEREIGN, COUNTRY = "Q3624078", "Q6256"

QUERY = """
SELECT ?code ?item ?title
  (GROUP_CONCAT(DISTINCT ?typeId; separator="|") AS ?types)
  (GROUP_CONCAT(DISTINCT ?capLabel; separator="|") AS ?capitals)
  (GROUP_CONCAT(DISTINCT ?langLabel; separator="|") AS ?languages)
  (GROUP_CONCAT(DISTINCT ?curLabel; separator="|") AS ?currencies)
  (GROUP_CONCAT(DISTINCT ?popStr; separator="|") AS ?pops)
  (GROUP_CONCAT(DISTINCT ?driveLabel; separator="|") AS ?drive)
WHERE {
  { VALUES ?code { %s } ?item wdt:P297 ?code . }
  UNION { VALUES (?item ?code) { %s } }  # Natural Earth's Wikidata ID for the same country, when known
  OPTIONAL { ?article schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?title . }
  OPTIONAL { ?item wdt:P31 ?type . BIND(STRAFTER(STR(?type), "entity/") AS ?typeId) }
  OPTIONAL { ?item p:P36 ?capSt . ?capSt ps:P36 ?cap ; wikibase:rank ?capRank .
             FILTER(?capRank != wikibase:DeprecatedRank) FILTER NOT EXISTS { ?capSt pq:P582 [] }
             OPTIONAL { ?cap rdfs:label ?capEn . FILTER(LANG(?capEn) = "en") } OPTIONAL { ?cap rdfs:label ?capMul . FILTER(LANG(?capMul) = "mul") } BIND(COALESCE(?capEn, ?capMul) AS ?capLabel) }
  OPTIONAL { ?item wdt:P37 ?lang . OPTIONAL { ?lang rdfs:label ?langEn . FILTER(LANG(?langEn) = "en") } OPTIONAL { ?lang rdfs:label ?langMul . FILTER(LANG(?langMul) = "mul") } BIND(COALESCE(?langEn, ?langMul) AS ?langLabel) }
  OPTIONAL { ?item p:P38 ?curSt . ?curSt ps:P38 ?cur ; wikibase:rank ?curRank .
             FILTER(?curRank != wikibase:DeprecatedRank) FILTER NOT EXISTS { ?curSt pq:P582 [] }
             OPTIONAL { ?cur rdfs:label ?curEn . FILTER(LANG(?curEn) = "en") } OPTIONAL { ?cur rdfs:label ?curMul . FILTER(LANG(?curMul) = "mul") } BIND(COALESCE(?curEn, ?curMul) AS ?curLabel) }
  OPTIONAL { ?item p:P1082 ?popSt . ?popSt ps:P1082 ?pop ; wikibase:rank ?popRank .
             FILTER(?popRank != wikibase:DeprecatedRank) OPTIONAL { ?popSt pq:P585 ?popDate }
             BIND(CONCAT(STR(?pop), "@", COALESCE(STR(?popDate), ""), "@",
                         IF(?popRank = wikibase:PreferredRank, "P", "N")) AS ?popStr) }
  OPTIONAL { ?item wdt:P1622 ?driveV . OPTIONAL { ?driveV rdfs:label ?driveVEn . FILTER(LANG(?driveVEn) = "en") } OPTIONAL { ?driveV rdfs:label ?driveVMul . FILTER(LANG(?driveVMul) = "mul") } BIND(COALESCE(?driveVEn, ?driveVMul) AS ?driveLabel) }
}
GROUP BY ?code ?item ?title
"""


def split(s: str) -> list[str]:
    return sorted({x for x in (s or "").split("|") if x})


def pick_population(pops: list[str]) -> dict | None:
    parsed = []
    for p in pops:
        value, when, rank = p.split("@")
        try:
            parsed.append((rank == "P", when[:10], int(float(value))))
        except ValueError:
            continue
    if not parsed:
        return None
    preferred, when, value = max(parsed)  # preferred rank first, then the latest date
    return {"value": value, "year": int(when[:4]) if when else None}


def choose_item(rows: list[dict], name: str, ne_qid: str | None = None) -> dict:
    """Pick the Wikidata item with the most facts; ties go to Natural Earth's ID, then a matching title."""
    def score(r):
        has = sum(bool(r.get(k, {}).get("value")) for k in ("capitals", "languages", "currencies", "pops", "drive"))
        types = split(r.get("types", {}).get("value"))
        title = r.get("title", {}).get("value", "")
        is_ne = bool(ne_qid) and r["item"]["value"].endswith("/" + ne_qid)
        return (has, is_ne, title == name, SOVEREIGN in types or COUNTRY in types, bool(title))
    return max(rows, key=score)


def natural_earth_qids() -> dict[str, str]:
    """{ISO code: Wikidata ID} from the Natural Earth file the map build downloaded (if present)."""
    src = CACHE / "naturalearth" / "ne_110m_admin_0_countries.geojson"
    if not src.exists():
        return {}
    out = {}
    for f in json.loads(src.read_text())["features"]:
        pr = f["properties"]
        code = pr.get("ISO_A2_EH") if pr.get("ISO_A2_EH", "-99") != "-99" else pr.get("ISO_A2")
        if code and code != "-99" and re.fullmatch(r"Q\d+", pr.get("WIKIDATAID") or ""):
            out[code] = pr["WIKIDATAID"]
    return out


def wikidata_facts(client: httpx.Client, places: dict[str, str]) -> dict:
    ne = {c: q for c, q in natural_earth_qids().items() if c in places}
    by_code = " ".join(f'"{c}"' for c in sorted(places))
    by_ne = " ".join(f'(wd:{q} "{c}")' for c, q in sorted(ne.items()))
    # Two light bulk queries (a single combined one timed out): by ISO code, and by Natural Earth's Wikidata ID.
    bindings = []
    for values, pairs in ((by_code, '(wd:Q0 "--")'), ('"--"', by_ne or '(wd:Q0 "--")')):
        for attempt in range(2):  # the public endpoint sometimes times out; retry once
            r = client.post(SPARQL_URL, data={"query": QUERY % (values, pairs)},
                            headers={"Accept": "application/sparql-results+json"}, timeout=180)
            if r.status_code not in (429, 500, 502, 503, 504):
                break
            print(f"  Wikidata returned HTTP {r.status_code}; retrying once…", flush=True)
            time.sleep(20)
        r.raise_for_status()
        bindings += r.json()["results"]["bindings"]
    rows_by_code: dict[str, list] = {}
    for row in bindings:
        rows_by_code.setdefault(row["code"]["value"], []).append(row)
    facts = {}
    for code, name in places.items():
        rows = rows_by_code.get(code)
        if not rows:
            continue
        row = choose_item(rows, name, ne.get(code))
        v = lambda k: row.get(k, {}).get("value", "")  # noqa: E731
        title = v("title")
        entry = {"name": name, "wikidata": v("item").rsplit("/", 1)[-1]}
        if title:
            entry["wikipedia_title"] = title
            entry["wikipedia_url"] = "https://en.wikipedia.org/wiki/" + title.replace(" ", "_")
        for key, field in (("capital", "capitals"), ("languages", "languages"), ("currency", "currencies")):
            if split(v(field)):
                entry[key] = split(v(field))
        pop = pick_population(split(v("pops")))
        if pop:
            entry["population"] = pop
        if split(v("drive")):
            entry["driving_side"] = split(v("drive"))
        facts[code] = entry
    return facts


def dishes(client: httpx.Client) -> dict[str, str]:
    """{country article title (lowercase): first dish} from the 'National dish' article's bullet list."""
    r = client.get(WIKI_API, params={"action": "parse", "page": DISH_PAGE, "prop": "wikitext", "format": "json",
                                     "formatversion": 2}, headers={"Accept-Encoding": "gzip"}, timeout=60)
    r.raise_for_status()
    text = r.json()["parse"]["wikitext"]
    text = re.sub(r"<ref[^>/]*/>", "", text)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    out = {}
    for line in text.splitlines():
        # "* [[Afghanistan]]: [[kabuli palaw]], ..." or "* [[cuisine of Spain|Spain]]: [[paella]], ..."
        m = re.match(r"^\*\s*\[\[([^\]|#]+)(?:\|([^\]]+))?\]\]\s*:\s*(.*)$", line)
        if not m:
            continue
        keys = {m.group(1).strip().lower(), (m.group(2) or "").strip().lower()} - {""}
        keys |= {k.removeprefix("cuisine of ").removeprefix("the ") for k in keys}  # "[[cuisine of Sweden]]"
        rest = re.sub(r"\([^()]*\)", "", m.group(3))  # drop parenthetical notes before splitting
        first = re.split(r",|;| and ", rest, maxsplit=1)[0]  # the first dish listed
        link = re.search(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", first)
        if link:
            dish = (link.group(2) or link.group(1)).strip()
        else:  # unlinked dish name, e.g. "La bandera (rice, beans and meat)"
            dish = re.sub(r"\{\{[^}]*\}\}|\(.*?\)|'{2,}", "", first).strip(" .")
        if dish and not dish.lower().startswith(("file:", "image:")) and len(dish) < 60:
            for k in keys:
                out.setdefault(k, dish[0].upper() + dish[1:])
    return out


def bundle_flags(client: httpx.Client, codes: list[str]) -> list[str]:
    cache = CACHE / "flag-icons"
    cache.mkdir(parents=True, exist_ok=True)
    tgz = cache / "flag-icons-7.6.0.tgz"
    if not tgz.exists():
        r = client.get(FLAG_ICONS_URL, timeout=120, follow_redirects=True)
        r.raise_for_status()
        tgz.write_bytes(r.content)
    FLAGS.mkdir(parents=True, exist_ok=True)
    wanted = {f"package/flags/4x3/{c.lower()}.svg": FLAGS / f"{c.lower()}.svg" for c in codes}
    wanted["package/LICENSE"] = FLAGS / "LICENSE-flag-icons.txt"
    found = set()
    with tarfile.open(fileobj=io.BytesIO(tgz.read_bytes()), mode="r:gz") as tar:
        for member in tar.getmembers():  # copy exact names only; nothing is extracted by path
            if member.name in wanted and member.isfile():
                wanted[member.name].write_bytes(tar.extractfile(member).read())
                found.add(member.name)
    return sorted(c for c in codes if f"package/flags/4x3/{c.lower()}.svg" not in found)


def main() -> None:
    places = {p["code"]: p["name"] for p in json.loads((ROOT / "static" / "places.json").read_text()) if p.get("code")}
    with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:
        print("querying Wikidata (two bulk queries)…", flush=True)
        facts = wikidata_facts(client, places)
        print(f"  got {len(facts)} of {len(places)} places", flush=True)
        try:
            dish_by_title = dishes(client)
            print(f"  'National dish' article: {len(dish_by_title)} country entries", flush=True)
        except Exception as exc:  # the dish is optional; skip it rather than guess
            dish_by_title = {}
            print(f"  dish step skipped: {exc!r}", flush=True)
        dish_url = "https://en.wikipedia.org/wiki/" + DISH_PAGE.replace(" ", "_")
        for code, entry in facts.items():
            keys = {entry.get("wikipedia_title", "").lower(), entry["name"].lower()}
            dish = next((dish_by_title[k] for k in keys if k in dish_by_title), None)
            if dish:
                entry["dish"] = {"name": dish, "source_url": dish_url}
        missing_flags = bundle_flags(client, sorted(places))

    OUT.write_text(json.dumps({"_meta": {
        "built": date.today().isoformat(),
        "sources": ["Wikidata (query.wikidata.org)", f"English Wikipedia: {DISH_PAGE}",
                    "flag-icons 7.6.0 (MIT)"]}, **dict(sorted(facts.items()))}, ensure_ascii=False, indent=1))

    fields = ["wikipedia_url", "capital", "languages", "currency", "population", "driving_side", "dish"]
    print(f"wrote {OUT.relative_to(ROOT)}: {len(facts)} countries; flags bundled in static/flags/")
    print("no Wikidata item:", sorted(places[c] for c in places if c not in facts))
    for f in fields:
        gaps = sorted(places[c] for c in places if c in facts and f not in facts[c])
        print(f"missing {f} [{len(gaps)}]:", gaps)
    print("missing flag:", missing_flags)


if __name__ == "__main__":
    sys.exit(main())
