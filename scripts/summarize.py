"""Rebuilds the tables of the rank tracker API comparison from data/raw.

Standard library only. Run from the repository root:

    python scripts/summarize.py

Three passes feed it. "country" is the US-wide desktop page, "austin" the same 20 keywords
with the city set to Austin, Texas, about an hour later, and "mobile" the US-wide page on a
phone. The two Chrome windows (real_clean, real_account) are in "country" and "austin";
in Austin they stopped on a challenge page after k03, so the Chrome pair is read on "country".
"""
import itertools
import json
import pathlib
import statistics
from collections import Counter
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
NAMES = {
    "hasdata": "HasData", "serpapi": "SerpApi", "brightdata": "Bright Data", "serper": "Serper",
    "searchapi": "SearchAPI", "scrapingdog": "Scrapingdog", "scraperapi": "ScraperAPI",
    "real_clean": "Chrome, signed out", "real_account": "Chrome, signed in",
}
CHROME = ("real_clean", "real_account")
LOCAL = ["k11", "k12", "k17"]
BINS = ["same position", "off by 1", "off by 2 or more", "not in the other top 10"]


def load(block):
    """{keyword id: {vendor: norm}} for the delivered records of one pass."""
    data = {}
    for vdir in sorted((RAW / block).iterdir()):
        for f in sorted(vdir.glob("k*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            status = d.get("status")
            if not (isinstance(status, int) and 200 <= status < 300):
                continue
            if isinstance(d.get("norm"), dict):
                data.setdefault(f.stem, {})[vdir.name] = d["norm"]
    return data


def seconds(block):
    """{vendor: [seconds of every delivered record]}"""
    out = {}
    for vdir in sorted((RAW / block).iterdir()):
        for f in vdir.glob("k*.json"):
            d = json.loads(f.read_text(encoding="utf-8"))
            status = d.get("status")
            if isinstance(status, int) and 200 <= status < 300 and d.get("seconds") is not None:
                out.setdefault(vdir.name, []).append(d["seconds"])
    return out


def host(o):
    h = o.get("host") or urlparse(o.get("url") or "").netloc
    h = (h or "").lower()
    return h[4:] if h.startswith("www.") else h


def organic(block, vendor, kw):
    return (block.get(kw, {}).get(vendor) or {}).get("organic") or []


def keys(items, n=10):
    """(host, occurrence) pairs in rank order, so a site that ranks twice counts twice."""
    seen, out = Counter(), []
    for o in sorted(items, key=lambda o: o.get("pos") or 99)[:n]:
        h = host(o)
        if h:
            out.append((h, seen[h]))
            seen[h] += 1
    return out


def overlap(t, x, k=10):
    t, x = t[:k], x[:k]
    return len(set(t) & set(x)) / min(k, len(t)) if t and x else None


def mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def austin_hits(block, vendor, kw):
    """How many of the top 10 name Austin in the title, URL or snippet, and how many there were."""
    o = organic(block, vendor, kw)[:10]
    if not o:
        return None
    hit = sum("austin" in " ".join(str(x.get(f, "")) for f in ("title", "url", "snippet")).lower() for x in o)
    return hit, len(o)


def moves(block, a, b, ids):
    """Each site of one top 10 binned by its position in the other, both directions."""
    c = dict.fromkeys(BINS, 0)
    for kw in ids:
        for x, y in ((a, b), (b, a)):
            t, u = keys(organic(block, x, kw)), keys(organic(block, y, kw))
            if not t or not u:
                continue
            for p, h in enumerate(t):
                c[BINS[3] if h not in u else BINS[min(abs(u.index(h) - p), 2)]] += 1
    tot = sum(c.values())
    return ({k: c[k] / tot for k in BINS}, tot) if tot else (None, 0)


def table(header, rows):
    widths = [max(len(str(r[i])) for r in [header] + rows) for i in range(len(header))]
    line = lambda r: "  ".join(str(x).ljust(w) for x, w in zip(r, widths))
    print(line(header))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print(line(r))
    print()


def pc(x):
    return "" if x is None else f"{x:.0%}"


def main():
    kw = {}
    for line in (ROOT / "data" / "keywords.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            kw[d["id"]] = d["q"]
    ids = sorted(kw)
    country, austin, mobile = load("country"), load("austin"), load("mobile")
    api = sorted({v for per in austin.values() for v in per} - set(CHROME))

    print("1. Organic results naming Austin, local keywords, US-wide page and Austin page\n")
    named = {v: {i: {b: austin_hits(country if b == "country" else austin, v, i) for b in ("country", "Austin")}
                 for i in LOCAL} for v in api}
    rows = []
    for v in sorted(api, key=lambda v: -sum((named[v][i]["Austin"] or (0, 1))[0] for i in LOCAL)):
        row = [NAMES.get(v, v)]
        for i in LOCAL:
            for b in ("country", "Austin"):
                x = named[v][i][b]
                row.append("empty" if x is None else f"{x[0]} of {x[1]}")
        rows.append(row)
    table(["API"] + [f"{kw[i]}, {b}" for i in LOCAL for b in ("US", "Austin")], rows)
    applied = [v for v in api if sum((named[v][i]["Austin"] or (0, 1))[0] for i in LOCAL) > 0
               or all(named[v][i]["Austin"] is None for i in LOCAL)]
    print("Applied the city:", ", ".join(NAMES.get(v, v) for v in applied), "\n")

    print("2. Share of each API's US-wide top 10 still in its own Austin top 10 (keywords with both pages)\n")
    kept_city = {}
    for v in api:
        vals = [overlap(keys(organic(country, v, i)), keys(organic(austin, v, i))) for i in ids]
        vals = [x for x in vals if x is not None]
        if len(vals) >= 5:
            kept_city[v] = vals
    table(["API", "kept", "keywords"],
          [[NAMES.get(v, v), pc(mean(x)), len(x)] for v, x in sorted(kept_city.items(), key=lambda kv: mean(kv[1]))])

    print("3. Where a site from one API's Austin top 10 sits at the other API, both directions\n")
    pairs = {}
    for a, b in itertools.combinations(sorted(applied), 2):
        sh, n = moves(austin, a, b, ids)
        if sh:
            pairs[f"{NAMES[a]} and {NAMES[b]}"] = (sh, n)
    chrome = "Chrome signed in and signed out"
    pairs[chrome] = moves(country, CHROME[0], CHROME[1], ids)
    order = sorted([p for p in pairs if p != chrome], key=lambda p: -pairs[p][0][BINS[0]]) + [chrome]
    table(["Pair", *BINS, "sites"], [[p, *(pc(pairs[p][0][k]) for k in BINS), pairs[p][1]] for p in order])

    print("4. Share of the desktop top 10 also in the mobile top 10, US-wide, same API\n")
    kept_mobile = {}
    for v in sorted({v for per in mobile.values() for v in per}):
        vals = [overlap(keys(organic(country, v, i)), keys(organic(mobile, v, i))) for i in ids]
        vals = [x for x in vals if x is not None]
        if len(vals) >= 5:
            kept_mobile[v] = vals
    rows = []
    for v, x in sorted(kept_mobile.items(), key=lambda kv: mean(kv[1])):
        mob = [len(organic(mobile, v, i)) for i in ids if organic(mobile, v, i)]
        desk = [len(organic(country, v, i)) for i in ids if organic(country, v, i)]
        rows.append([NAMES.get(v, v), pc(mean(x)), len(x), statistics.median(mob), statistics.median(desk)])
    table(["API", "kept", "keywords", "organic per mobile page (median)", "organic per desktop page (median)"], rows)

    print("5. Seconds per delivered request, Austin pass\n")
    sec = seconds("austin")
    table(["API", "p50", "p95", "requests"],
          [[NAMES.get(v, v), f"{pct(x, 0.5):.1f}", f"{pct(x, 0.95):.1f}", len(x)]
           for v, x in sorted(sec.items(), key=lambda kv: pct(kv[1], 0.5)) if v not in CHROME])


if __name__ == "__main__":
    main()
