"""The rank tracker from the article, unchanged.

Checks two keywords in Austin, Texas, through the HasData Google SERP API, stores the position of
DOMAIN, how many organic results the page held and the set of hosts, and marks a run as suspect
when it shares fewer than half of its hosts with the previous run of the same keyword.

    pip install requests
    export HASDATA_API_KEY=...
    python scripts/rank_tracker.py

Each run writes to ranks.db in the current folder. Four checks cost 20 credits (5 per request).
"""
import os, sqlite3, datetime, requests
from urllib.parse import urlsplit

API = "https://api.hasdata.com/scrape/google/serp"
KEY = os.environ["HASDATA_API_KEY"]
DOMAIN = "yelp.com"
LOCATION = "Austin,Texas,United States"
KEYWORDS = ["dentist", "pizza near me"]

db = sqlite3.connect("ranks.db")
db.execute("CREATE TABLE IF NOT EXISTS ranks (checked TEXT, keyword TEXT, location TEXT,"
           " position INTEGER, parsed INTEGER, hosts TEXT, status TEXT)")

def host(url):
    return urlsplit(url).netloc.lower().removeprefix("www.").removeprefix("m.")

for kw in KEYWORDS:
    r = requests.get(API, headers={"x-api-key": KEY}, timeout=60,
                     params={"q": kw, "location": LOCATION, "gl": "us", "hl": "en"})
    if not r.ok or not r.content:
        print(f"{kw!r}: HTTP {r.status_code}, {len(r.content)} bytes, skipped")
        continue
    organic = r.json().get("organicResults", [])
    hosts = {host(o["link"]) for o in organic if o.get("link")}
    position = next((o.get("position") for o in organic if host(o.get("link", "")) == DOMAIN), None)

    prev = db.execute("SELECT hosts FROM ranks WHERE keyword = ? AND location = ? AND parsed > 0"
                      " ORDER BY checked DESC LIMIT 1", (kw, LOCATION)).fetchone()
    status = "ok" if organic else "empty"
    if prev and organic:
        before = set(prev[0].split())
        if len(hosts & before) * 2 < min(len(hosts), len(before)):
            status = "suspect"  # shares under half of the last list, recheck before reporting

    checked = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    db.execute("INSERT INTO ranks VALUES (?, ?, ?, ?, ?, ?, ?)",
               (checked, kw, LOCATION, position, len(organic), " ".join(sorted(hosts)), status))
    db.commit()
    print(f"{kw!r}: position {position}, parsed {len(organic)}, {status}")
