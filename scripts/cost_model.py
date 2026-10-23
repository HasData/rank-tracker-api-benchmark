"""Cheapest monthly cost per vendor for N desktop checks a month, monthly and annual billing.
Price ladders as read from each vendor's pricing page on the day of the comparison (October 22, 2026)."""
import math

def ladder(n, tiers, per_check=1):
    """tiers: (units, price). Cheapest single tier that covers n*per_check units."""
    need = n * per_check
    ok = [p for u, p in tiers if u >= need]
    return min(ok) if ok else None

HD = [(200_000, 59), (1_000_000, 119), (3_000_000, 249), (5_000_000, 415), (10_000_000, 830), (20_000_000, 1660)]
SD = [(200_000, 40), (1_000_000, 90), (3_000_000, 200), (6_000_000, 350), (9_000_000, 500), (19_000_000, 1000),
      (29_000_000, 1500), (42_000_000, 2000), (55_000_000, 2500), (65_000_000, 3000)]
SAPI = [(1_000, 25), (5_000, 75), (15_000, 150), (30_000, 275), (100_000, 725), (250_000, 1475), (500_000, 2750),
        (1_000_000, 3750), (2_000_000, 5675), (3_000_000, 7600), (4_000_000, 9550), (5_000_000, 11475),
        (6_000_000, 13400), (10_000_000, 21125)]
SRCH = [(10_000, 40), (35_000, 100), (100_000, 250), (250_000, 500), (500_000, 900), (1_000_000, 1500),
        (2_000_000, 2800), (5_000_000, 5000)]
SCRA = [(100_000, 49), (1_000_000, 149), (3_000_000, 299), (5_000_000, 475)]  # 25 credits a Google search
SERPER = [(50_000, 50), (500_000, 375), (2_500_000, 1250), (12_500_000, 3750)]  # packs, 6 months

def hasdata(n, annual=False):
    p = ladder(n, HD, 5)
    return None if p is None else (p * 10 / 12 if annual else p)

def scrapingdog(n, annual=False):
    p = ladder(n, SD, 5)
    return None if p is None else (p * 10 / 12 if annual else p)

def scraperapi(n, annual=False):
    p = ladder(n, SCRA, 25)
    return None if p is None else (p * 0.9 if annual else p)

def serpapi(n, annual=False):
    return ladder(n, SAPI)

def searchapi(n, annual=False):
    return ladder(n, SRCH)

def brightdata(n, annual=False):
    return min(1.5 * n / 1000, 499 + max(0, n - 380_000) * 1.3 / 1000)

def serper(n, annual=False):
    best = None
    for c, p in SERPER:  # packs bought for a 6-month window, mixed packs ignored
        k = math.ceil(6 * n / c)
        cost = k * p / 6
        best = cost if best is None else min(best, cost)
    return best

VENDORS = {"HasData": hasdata, "Scrapingdog": scrapingdog, "Bright Data": brightdata, "SerpApi": serpapi,
           "SearchAPI": searchapi, "Serper": serper, "ScraperAPI": scraperapi}
CITY = {"HasData", "Scrapingdog", "Bright Data", "SerpApi", "SearchAPI"}

def table(annual):
    rows = []
    for kw in sorted(set(list(range(20, 2001, 20)) + list(range(2000, 200_001, 500)))):
        n = kw * 30
        costs = {v: f(n, annual) for v, f in VENDORS.items()}
        costs = {v: c for v, c in costs.items() if c is not None}
        best_all = min(costs, key=costs.get)
        city = {v: c for v, c in costs.items() if v in CITY}
        best_city = min(city, key=city.get)
        rows.append((kw, best_all, best_city, costs))
    return rows

for annual in (False, True):
    print("\n=== annual" if annual else "=== monthly")
    prev = None
    for kw, ba, bc, costs in table(annual):
        key = (ba, bc)
        if key != prev:
            s = ", ".join(f"{v} {c:,.0f}" for v, c in sorted(costs.items(), key=lambda x: x[1]))
            print(f"from {kw:>7,} kw/day: cheapest {ba:<12} city-applying {bc:<12} | {s}")
            prev = key
