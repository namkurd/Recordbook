"""Team (franchise) names by season and manager, from Sleeper's league users. Past seasons are cached; the current one is refreshed every run."""
import json, os, time, urllib.request
from load import fetch
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = f"{ROOT}/data/cache/teams.json"

def _get(path):
    for i in range(3):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request("https://api.sleeper.app/v1" + path, headers={"User-Agent": "dtf-record-book"}), timeout=60))
        except Exception:
            if i == 2: raise
            time.sleep(2)

def teams(d):
    try: cache = json.load(open(CACHE))
    except Exception: cache = {}
    try: owners = fetch("sleepersheet", "data/owners.json")["owners"]
    except Exception: owners = {}
    changed = False
    for s in ((d.raw.get("fab") or {}).get("seasons") or []):
        y = str(s["s"])
        if y in cache and int(y) != d.cur: continue
        try:
            users = _get(f"/league/{s['league_id']}/users")
        except Exception as e:
            print("WARN team names", y, e); continue
        cache[y] = {(owners.get(u["user_id"]) or u.get("display_name")): ((u.get("metadata") or {}).get("team_name") or "").strip() for u in users}
        changed = True
    if changed:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True); json.dump(cache, open(CACHE, "w"), ensure_ascii=False, indent=0)
    return {int(y): v for y, v in cache.items()}
