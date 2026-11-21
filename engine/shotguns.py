"""Who counts as a Shotgun, under the league's rule: a starter (not a defense) who scores exactly 0.0, unless he was ruled OUT.

The 2024 rule says "a 0 or less from a non-DST"; it was entered wrongly and is now "exactly 0.0", so only a 0.0 counts (never a negative
score). The 2025 amendment excludes a player ruled OUT (Doubtful does not count as OUT unless the pending 2026 proposal passes). So a starter
who scored 0.0 is a Shotgun even if he never took the field (a healthy scratch, a Questionable player who sat, a bye week), unless the
NFL's final injury report for that week listed him as Out. nflverse publishes that report (injuries_<season>.csv); this keeps just the
Sleeper ids of the players listed Out, per season-week, in data/cache/out_status.json. (A player ruled out during his game is handled by
Rumble Central's in-game injury log and the commissioner's overrides, applied by the Hub and by qb_out in moments.py.)
"""
import csv, io, json, os, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = f"{ROOT}/data/cache/out_status.json"
INJ = "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.csv"
IDS = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv"
SLEEPER_PLAYERS = "https://api.sleeper.app/v1/players/nfl"
_XW = {}

def _get(url, tries=3):
    for i in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "dtf-record-book"}), timeout=180).read()
        except Exception:
            if i == tries - 1: raise

def crosswalk():
    """gsis id -> Sleeper id (the community table first, then Sleeper's own gsis_id, which has the newest players)."""
    if _XW: return _XW
    for row in csv.DictReader(io.StringIO(_get(IDS).decode("utf-8", "ignore"))):
        g, s = row.get("gsis_id"), row.get("sleeper_id")
        if g and s and g != "NA" and s != "NA": _XW[g] = s
    try:
        for pid, p in json.loads(_get(SLEEPER_PLAYERS)).items():
            if p.get("gsis_id") and p["gsis_id"] not in _XW: _XW[p["gsis_id"]] = pid
    except Exception as e:
        print("WARN Sleeper player list:", e)
    return _XW

def load():
    try: return json.load(open(OUT))
    except Exception: return {}

def save(o):
    json.dump(o, open(OUT, "w"), separators=(",", ":"), sort_keys=True)

def refresh(seasons, current=None, force=False):
    """Fills data/cache/out_status.json for the seasons given (a finished season once; the current season each run, since weeks are added)."""
    o = load(); changed = False
    for s in seasons:
        have = [k for k in o if k.startswith(f"{s}-")]
        if have and s != current and not force: continue
        try: text = _get(INJ.format(season=s)).decode("utf-8", "ignore")
        except Exception as e:
            print("WARN injuries", s, e); continue
        xw = crosswalk(); per = {}
        for row in csv.DictReader(io.StringIO(text)):
            if row.get("game_type") not in (None, "", "REG") and row.get("season_type") not in (None, "", "REG"): continue
            if (row.get("report_status") or "").strip().lower() != "out": continue
            sid = xw.get(row.get("gsis_id"))
            if sid: per.setdefault(f"{s}-{int(float(row['week']))}", set()).add(sid)
        for k, v in per.items():
            new = sorted(v, key=str)
            if o.get(k) != new: o[k] = new; changed = True
    if changed: save(o)
    return o

def shot_list(zeros, out_ids):
    """[[player id, 0.0]] for the starters who scored exactly 0.0 and were not ruled out (a defense or an empty slot never counts)."""
    return [[p, 0.0] for p in zeros if p != "0" and not (len(p) <= 3 and p.isalpha()) and p not in out_ids]

def recompute(cache):
    """Rewrites every cached week's `shot` list from its zeros under the rule above. Returns {season: (before, after)}."""
    o = load(); stat = {}
    for key, wk in cache["weeks"].items():
        s = int(key.split("-")[0]); outs = set(o.get(key, []))
        for rid, t in wk["teams"].items():
            before = len(t.get("shot") or []); t["shot"] = shot_list(t.get("zeros") or [], outs)
            a, b = stat.get(s, (0, 0)); stat[s] = (a + before, b + len(t["shot"]))
    return stat
