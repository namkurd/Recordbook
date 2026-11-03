"""Per-team, per-week facts the archive doesn't hold, cached in data/cache/facts.json so each run only fetches new weeks.
  * Sleeper matchups  -> every rostered player's points (bench!), starters, zeros, top-player share
  * Sleeper stats     -> who actually took the field (for Shotguns)
  * Rumble Central wp_timeline -> play-by-play fantasy points on a real clock: leads, comebacks, Thursday/Saturday/Monday points, projections
A week is only ingested once it is finished (it is in the Rumble Central archive); finished weeks are never refetched."""
import collections, datetime, json, os, time, urllib.request
from zoneinfo import ZoneInfo
import cards as C
from load import fetch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = f"{ROOT}/data/cache/facts.json"; NAMES = f"{ROOT}/data/cache/names.json"
ET = ZoneInfo("America/New_York")
API = "https://api.sleeper.app/v1"

def api(path, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(API + path, headers={"User-Agent": "dtf-record-book"})
            return json.load(urllib.request.urlopen(req, timeout=90))
        except Exception:
            if i == tries - 1: raise
            time.sleep(2 * (i + 1))

def load_cache():
    try: return json.load(open(CACHE))
    except Exception: return {"v": 2, "weeks": {}}
def load_names():
    try: return json.load(open(NAMES))
    except Exception: return {}

def day_of(t0_ms, ko_s):
    dt = datetime.datetime.fromtimestamp(t0_ms / 1000 + ko_s, tz=ET)
    return dt.weekday(), dt.hour + dt.minute / 60            # Mon=0 ... Sun=6

def timeline_facts(d, season, week, lineups, pairs):
    """lineups {rid: [(pid, pts)]}, pairs {rid: opp_rid}. Returns per-team dict + week-level dict."""
    path = f"wp_timeline/week_{week}.json" if season == d.cur else f"seasons/{season}/wp_timeline/week_{week}.json"
    try: t = fetch("sleeperliverumbles", path)
    except Exception: return {}, {}
    games = t.get("g") or {}; tg = t.get("tg") or {}; tm = t.get("tm") or {}; t0 = t["t0"]
    gday = {}
    for g, v in games.items(): gday[g] = day_of(t0, v["ko"]) + (v["ko"],)
    thu = [(v[2], g) for g, v in gday.items() if v[0] == 3 and v[1] >= 19]         # Thursday-night game: the latest evening kickoff on a Thursday
    tnf = max(thu)[1] if thu else None
    mon_ko = min([v[2] for g, v in gday.items() if v[0] == 0] or [None]) if any(v[0] == 0 for v in gday.values()) else None
    def bucket(pid):
        g = tg.get(tm.get(pid)); 
        if not g or g not in gday: return "sun"
        if g == tnf: return "thu"
        wd = gday[g][0]
        return {5: "sat", 0: "mon", 4: "fri"}.get(wd, "sun")
    per = {}; evs = sorted(t.get("ev") or [], key=lambda e: e[0])
    pid_team = {}
    for rid, lu in lineups.items():
        for pid, _ in lu: pid_team[str(pid)] = rid
    # points by bucket per team; league total in the Thursday-night game
    tnf_total = 0.0; tnf_names = None
    for rid in lineups: per[rid] = {"thu": 0.0, "sat": 0.0, "mon": 0.0, "proj": round(sum((t.get("pre") or {}).get(str(p), 0) for p, _ in lineups[rid]), 2)}
    for s, pid, pts, lab in evs:
        pid = str(pid); rid = pid_team.get(pid)
        if rid is None: continue
        b = bucket(pid)
        if b in ("thu", "sat", "mon"): per[rid][b] += pts
        if b == "thu": tnf_total += pts
    for rid in per:
        for k in ("thu", "sat", "mon"): per[rid][k] = round(per[rid][k], 2)
    # leads
    done = set()
    for rid, opp in pairs.items():
        if (opp, rid) in done or opp not in lineups or rid not in lineups: continue
        done.add((rid, opp)); mine = {str(p) for p, _ in lineups[rid]}; theirs = {str(p) for p, _ in lineups[opp]}
        a = b = 0.0; lead_max = lead_min = 0.0; chg = 0; sign = 0; mnf_lead = None
        for s, pid, pts, lab in evs:
            pid = str(pid)
            if mon_ko is not None and mnf_lead is None and s >= mon_ko: mnf_lead = round(a - b, 2)
            if pid in mine: a += pts
            elif pid in theirs: b += pts
            else: continue
            diff = a - b; lead_max = max(lead_max, diff); lead_min = min(lead_min, diff)
            sg = 1 if diff > 0.005 else -1 if diff < -0.005 else 0
            if sg and sign and sg != sign: chg += 1
            if sg: sign = sg
        if mnf_lead is None and mon_ko is not None: mnf_lead = round(a - b, 2)
        per[rid].update(lead_max=round(lead_max, 2), lead_min=round(lead_min, 2), chg=chg, mnf=mnf_lead)
        per[opp].update(lead_max=round(-lead_min, 2), lead_min=round(-lead_max, 2), chg=chg, mnf=None if mnf_lead is None else round(-mnf_lead, 2))
    return per, {"tnf_total": round(tnf_total, 2), "tnf": tnf, "psrc": t.get("preSrc")}

def ingest(d, budget_weeks=400):
    cache = load_cache(); names = load_names(); need_names = set(); added = 0
    lids = {s["s"]: s["league_id"] for s in ((d.raw.get("fab") or {}).get("seasons") or [])}
    games = collections.defaultdict(dict)
    for g in d.games: games[(g["season"], g["week"])][g["rid"]] = g
    for (season, week) in sorted(games):
        key = f"{season}-{week}"
        if key in cache["weeks"] or season not in lids or week > 17: continue
        if added >= budget_weeks: break
        rows = games[(season, week)]
        e = C.epa_file(season, d.cur)
        if not e: continue
        lu_raw = (e["lineups"].get(str(week)) or {})
        if not lu_raw: continue
        lineups = {int(r): [(str(p), x) for p, x in l] for r, l in lu_raw.items()}
        pairs = {rid: g["opp_rid"] for rid, g in rows.items()}
        try:
            M = api(f"/league/{lids[season]}/matchups/{week}"); S = api(f"/stats/nfl/regular/{season}/{week}")
        except Exception as ex:
            print("WARN ingest", key, ex); continue
        per_t, wk = timeline_facts(d, season, week, lineups, pairs)
        teams = {}
        for m in M:
            rid = m["roster_id"]; st = [str(x) for x in (m.get("starters") or [])]; pp = {str(k): v for k, v in (m.get("players_points") or {}).items()}
            if not st or rid not in rows: continue
            bench = sorted([(k, v) for k, v in pp.items() if k not in set(st)], key=lambda x: -x[1])
            starters = list(zip(st, [x or 0 for x in (m.get("starters_points") or [])]))
            def took_field(pid):
                x = S.get(pid) or {}
                return bool(x.get("gp")) and (x.get("off_snp", 0) + x.get("def_snp", 0) + x.get("st_snp", 0)) > 0
            def pos(pid): return (e["names"].get(pid) or ["", ""])[1] if pid in e["names"] else ""
            zeros = [(p, v) for p, v in starters if v == 0]
            shot = [(p, v) for p, v in starters if v <= 0 and not (len(p) <= 3 and p.isalpha()) and took_field(p)]   # DEF ids are team letters
            top = max(starters, key=lambda x: x[1]) if starters else ("", 0); tot = sum(v for _, v in starters)
            teams[str(rid)] = {"bench": round(sum(v for _, v in bench), 2), "bench_top": [[k, v] for k, v in bench[:6]],
                               "zeros": [p for p, _ in zeros], "shot": [[p, v] for p, v in shot],
                               "top": [top[0], round(top[1], 2), round(100 * top[1] / tot, 1) if tot > 0 else 0]}
            for p in [k for k, _ in bench[:6]] + [p for p, _ in zeros] + [p for p, _ in shot] + [top[0]]:
                if p not in names: need_names.add(p)
            teams[str(rid)].update(per_t.get(rid, {}))
        cache["weeks"][key] = {"teams": teams, **wk}; added += 1
        print("ingested", key)
    # player names (one big call only when some are missing)
    miss = {p for p in need_names if p not in names and not (len(p) <= 3 and p.isalpha())}
    if miss:
        try:
            db = api("/players/nfl")
            for p in miss:
                x = db.get(p) or {}; names[p] = [((x.get("first_name") or "") + " " + (x.get("last_name") or "")).strip() or p, x.get("position") or ""]
        except Exception as ex: print("WARN players db", ex)
    for k, v in C._cache.items(): pass
    if added or miss:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        json.dump(cache, open(CACHE, "w"), separators=(",", ":")); json.dump(names, open(NAMES, "w"), separators=(",", ":"), ensure_ascii=False)
    return cache, names
