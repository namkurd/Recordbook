"""Load league data from local checkouts (dev) or raw GitHub URLs (CI) into one normalized structure."""
import json, os, urllib.request

SRC = os.environ.get("RB_SRC")  # dir containing sleeperliverumbles/ and sleepersheet/ checkouts
RAW = {"sleeperliverumbles": "https://raw.githubusercontent.com/namkurd/SleeperLiveRumbles/main/",
       "sleepersheet": "https://raw.githubusercontent.com/namkurd/sleepersheet/main/",
       "sleepertradenodes": "https://raw.githubusercontent.com/namkurd/SleeperTradeNodes/main/",
       "fab-management": "https://raw.githubusercontent.com/namkurd/FAB-Management/main/",
       "sleeperauction": "https://raw.githubusercontent.com/namkurd/SleeperAuction/main/"}

def fetch(repo, path):
    if SRC:
        with open(os.path.join(SRC, repo, path)) as f: return json.load(f)
    req = urllib.request.Request(RAW[repo] + path, headers={"User-Agent": "recordbook"})
    with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)

def fetch_text(repo, path):
    if SRC:
        with open(os.path.join(SRC, repo, path), encoding="utf-8") as f: return f.read()
    req = urllib.request.Request(RAW[repo] + path, headers={"User-Agent": "recordbook"})
    with urllib.request.urlopen(req, timeout=60) as r: return r.read().decode("utf-8")

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cache", "txns.json")
def _slim(t):
    n = (t.get("metadata") or {}).get("notes") if t.get("status") == "failed" else None
    return {"i": t["transaction_id"], "ty": t["type"], "st": t["status"], "c": t.get("created"), "u": t.get("status_updated"), "leg": t.get("leg"), "r": t.get("roster_ids") or [],
            "bid": (t.get("settings") or {}).get("waiver_bid"), "fab": [[w["sender"], w["receiver"], w["amount"]] for w in (t.get("waiver_budget") or [])],
            "adds": list((t.get("adds") or {}).keys()) if t["type"] == "waiver" else [], **({"n": n} if n else {})}
def transactions(leagues, cur):
    """Every transaction of every Sleeper season (waiver claims incl. the failed ones with their bids, trades incl. FAB moved), trimmed;
    finished seasons come from data/cache/txns.json once fetched, the current one is always read fresh."""
    try: cache = json.load(open(CACHE))
    except Exception: cache = {}
    out = {}
    for y, lid in sorted(leagues.items()):
        if y < 2021 or not lid: continue
        if str(y) in cache and y != cur: out[y] = cache[str(y)]; continue
        try:
            seen = {}
            for leg in range(1, 19):
                req = urllib.request.Request(f"https://api.sleeper.app/v1/league/{lid}/transactions/{leg}", headers={"User-Agent": "recordbook"})
                for t in json.load(urllib.request.urlopen(req, timeout=60)): seen[t["transaction_id"]] = t
            out[y] = [_slim(t) for t in seen.values()]
        except Exception as e:
            print("WARN could not read Sleeper transactions for", y, e)
            if str(y) in cache: out[y] = cache[str(y)]
    try:
        json.dump({str(y): v for y, v in out.items()}, open(CACHE, "w"), separators=(",", ":"))
    except Exception: pass
    return out

def load():
    hist = fetch("sleepersheet", "data/history.json")["seasons"]
    play = fetch("sleepersheet", "data/playoffs_history.json")["games"]
    idx = fetch("sleeperliverumbles", "seasons/index.json")
    games, rosters, seasons, epa, leagues, qb_out = [], {}, {int(y): v for y, v in hist.items()}, {}, {}, set()
    cur = int(idx["current"])
    for y in sorted({int(s["season"]) for s in idx["seasons"]} | {cur}):
        try:
            d = fetch("sleeperliverumbles", "rumbles_history.json" if y == cur else f"seasons/{y}/rumbles_history.json")
        except Exception:
            continue
        try: epa[y] = fetch("sleeperliverumbles", "epa_weekly.json" if y == cur else f"seasons/{y}/epa_weekly.json")
        except Exception: pass
        name = {int(s["roster_id"]): s["manager"] for s in d["standings"]}
        rosters[y] = name; leagues[y] = d.get("league_id")
        for e in d.get("qb_adjustments") or []:      # a starting QB ruled out in his game, whose backup's points the league credited (confirmed, or likely: the status flipped to Out in the game)
            if e.get("confidence") in ("confirmed", "likely") and e.get("injured_qb"):
                qb_out.add((y, int(e["week"]), int(e["roster_id"]), str(e["injured_qb"]["player_id"])))
        allw = dict(d["weekly"])
        for wk, rows in (d.get("extra_weekly") or {}).items(): allw[wk] = rows
        n_reg = len(d["weekly"])
        for wk, rows in allw.items():
            wk = int(wk); n = len(rows)
            for rid, g in rows.items():
                games.append({"season": y, "week": wk, "m": name.get(int(rid), f"roster{rid}"), "rid": int(rid),
                              "pts": g["points"], "opp": name.get(g["opponent_roster_id"]), "opp_rid": g["opponent_roster_id"],
                              "opp_pts": g["opponent_points"], "win": g["h2h_win"], "n": n,
                              "outscored": g["teams_outscored"], "rumbles": g["rumbles"],
                              "reg": str(wk) in d["weekly"] and wk <= n_reg})
    extra = {}
    for key, repo, path in (("nodes", "sleepertradenodes", "data.json"), ("fab", "fab-management", "data.json"), ("fab_po", "fab-management", "playoff_teams.json")):
        try: extra[key] = fetch(repo, path)
        except Exception as e: print("WARN could not load", repo, path, e); extra[key] = None
    try:
        import csv, io
        extra_picks = list(csv.DictReader(io.StringIO(fetch_text("sleeperauction", "data/picks.csv"))))
    except Exception as e: print("WARN could not load auction picks", e); extra_picks = None
    extra["picks"] = extra_picks
    try: extra["auction_slots"] = fetch("sleeperauction", "site/data.json").get("pos_slots") or {}
    except Exception as e: print("WARN could not load auction pos_slots", e); extra["auction_slots"] = {}
    # Starters of any position Rumble Central logged as ruled out during their own game (capture_live_qb_injuries.py), or that are entered by hand
    for name, key, pick in (("live_injury_captures.json", "captures", lambda e: (e.get("player") or {}).get("player_id")),
                            ("injury_overrides.json", "ruled_out", lambda e: e.get("player_id"))):
        try:
            for e in fetch("sleeperliverumbles", name).get(key) or []:
                if pick(e) is not None: qb_out.add((int(e["season"]), int(e["week"]), int(e["roster_id"]), str(pick(e))))
        except Exception: pass
    return {"qb_out": qb_out, "txns": transactions(leagues, cur), "epa": epa, "seasons": seasons, "playoffs": play, "games": games, "rosters": rosters, "current": cur, **extra}
