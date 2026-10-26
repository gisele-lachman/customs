"""Build static/map.svg once from Natural Earth 1:110m countries (public domain).

Run: .venv/bin/python -I scripts/build_map.py   (needs shapely: pip install -r requirements-build.txt)
Downloads the source into .build_cache/naturalearth/ (gitignored); the SVG output is committed.
Neutral on disputed borders: geometry is the data's default, and only features matching a place in
static/places.json are clickable. Areas without a place entry are drawn plain, with no label.
"""

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import httpx
from shapely.geometry import shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".build_cache" / "naturalearth"
SOURCE_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
              "ne_110m_admin_0_countries.geojson")
OUT = ROOT / "static" / "map.svg"
USER_AGENT = "Customs/0.1 (cultural situation coach; student course project) build-script"

WIDTH = 1000.0
LAT_MIN, LAT_MAX = -57.0, 84.0  # Antarctica left out to keep the map compact
CONTINENT_LABELS = {  # label anchor (lon, lat); soft labels only, no country or disputed-area labels
    "North America": (-102, 47), "South America": (-60, -14), "Europe": (16, 55),
    "Africa": (18, 6), "Asia": (88, 47), "Oceania": (134, -24),
}


def equal_earth(lon: float, lat: float) -> tuple[float, float]:
    a1, a2, a3, a4 = 1.340264, -0.081106, 0.000893, 0.003796
    lam, phi = math.radians(lon), math.radians(lat)
    theta = math.asin(math.sqrt(3) / 2 * math.sin(phi))
    t2 = theta * theta; t6 = t2 ** 3
    x = 2 * math.sqrt(3) * lam * math.cos(theta) / (3 * (9 * a4 * t6 * t2 + 7 * a3 * t6 + 3 * a2 * t2 + a1))
    y = theta * (a4 * t6 * t2 + a3 * t6 + a2 * t2 + a1)
    return x, y


X_MAX = equal_earth(180, 0)[0]
Y_TOP, Y_BOTTOM = equal_earth(0, LAT_MAX)[1], equal_earth(0, LAT_MIN)[1]
SCALE = WIDTH / (2 * X_MAX)
HEIGHT = (Y_TOP - Y_BOTTOM) * SCALE


def project(lon: float, lat: float) -> tuple[float, float]:
    x, y = equal_earth(lon, max(min(lat, LAT_MAX), LAT_MIN))
    return (x + X_MAX) * SCALE, (Y_TOP - y) * SCALE


def ring_path(coords) -> str:
    pts = [project(lon, lat) for lon, lat in coords]
    return "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z"


def geom_path(geom) -> str:
    polys = [geom] if geom.geom_type == "Polygon" else list(getattr(geom, "geoms", []))
    out = []
    for poly in polys:
        if poly.geom_type != "Polygon":
            continue
        out.append(ring_path(poly.exterior.coords))
        out.extend(ring_path(r.coords) for r in poly.interiors)
    return "".join(out)


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    src = CACHE / "ne_110m_admin_0_countries.geojson"
    if not src.exists():
        print("downloading", SOURCE_URL, flush=True)
        r = httpx.get(SOURCE_URL, headers={"User-Agent": USER_AGENT}, timeout=60, follow_redirects=True)
        r.raise_for_status()
        src.write_bytes(r.content)
    data = json.loads(src.read_text())
    places = {p["code"]: p["name"] for p in json.loads((ROOT / "static" / "places.json").read_text()) if p.get("code")}

    countries, plain, by_continent = [], [], defaultdict(list)
    on_map, unmatched = set(), []
    for f in data["features"]:
        props, geom = f["properties"], shape(f["geometry"])
        continent = props.get("CONTINENT")
        if continent == "Antarctica":
            continue
        code = props.get("ISO_A2_EH") if props.get("ISO_A2_EH", "-99") != "-99" else props.get("ISO_A2")
        d = geom_path(geom)
        if continent in CONTINENT_LABELS:
            by_continent[continent].append(geom.buffer(0))
        if code in places and code not in on_map:
            on_map.add(code)
            name = places[code]
            countries.append(f'<path class="country" d="{d}" data-code="{code}" data-name="{esc(name)}" '
                             f'tabindex="0" role="button" aria-label="{esc(name)}"><title>{esc(name)}</title></path>')
        else:
            plain.append(f'<path class="land" d="{d}"/>')
            unmatched.append(props.get("NAME"))

    outlines = [f'<path class="continent" d="{geom_path(unary_union(geoms).simplify(0.05))}"/>'
                for geoms in by_continent.values()]
    labels = []
    for name, (lon, lat) in CONTINENT_LABELS.items():
        x, y = project(lon, lat)
        labels.append(f'<text x="{x:.0f}" y="{y:.0f}">{name.upper()}</text>')

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH:.0f} {HEIGHT:.0f}" class="world" '
           f'role="group" aria-label="World map: choose a country">\n'
           f'<!-- Built by scripts/build_map.py from Natural Earth 1:110m admin-0 countries (public domain). -->\n'
           f'<g class="lands">{"".join(plain)}</g>\n<g class="countries">\n' + "\n".join(countries) +
           f'\n</g>\n<g class="continents" aria-hidden="true">{"".join(outlines)}</g>\n'
           f'<g class="continent-labels" aria-hidden="true">{"".join(labels)}</g>\n</svg>\n')
    OUT.write_text(svg)

    off_map = sorted(n for c, n in places.items() if c not in on_map)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(svg) // 1024} KB, {len(countries)} clickable countries, "
          f"{len(plain)} plain areas")
    print("plain (no place entry, unlabeled):", sorted(unmatched))
    print(f"list-only places (too small for 1:110m) [{len(off_map)}]:", off_map)


if __name__ == "__main__":
    sys.exit(main())
