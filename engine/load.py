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

def load():
    hist = fetch("sleepersheet", "data/history.json")["seasons"]
    play = fetch("sleepersheet", "data/playoffs_history.json")["games"]
    idx = fetch("sleeperliverumbles", "seasons/index.json")
    games, rosters, seasons = [], {}, {int(y): v for y, v in hist.items()}
    cur = int(idx["current"])
    for y in sorted({int(s["season"]) for s in idx["seasons"]} | {cur}):
        try:
            d = fetch("sleeperliverumbles", "rumbles_history.json" if y == cur else f"seasons/{y}/rumbles_history.json")
        except Exception:
            continue
        name = {int(s["roster_id"]): s["manager"] for s in d["standings"]}
        rosters[y] = name
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
    return {"seasons": seasons, "playoffs": play, "games": games, "rosters": rosters, "current": cur, **extra}
