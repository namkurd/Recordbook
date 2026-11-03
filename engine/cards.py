"""Rebuild Rumble Central's full Rumble Card (both teams' starters, points, Rumbles) for a matchup since 2021."""
import re
from load import fetch

GAME_METRICS = {"game_pts", "game_pts_adj", "margin", "multiple", "win_pts", "loss_pts", "sit_start_miss", "sit_start_call", "worst_week",
                "comeback", "blown_lead", "lead_changes", "upset_proj", "over_proj", "under_proj", "thu_pts", "mon_pts", "sat_pts", "mnf_overcome", "bench", "shot_week", "zeros_win", "top_share", "high_proj", "high_proj_adj"}
EXTRA_IDS = {"most-points-on-a-saturday", "largest-monday-night-deficit-overcome"}   # seeded single-game records with a known week
_cache = {}

def _json(path, default=None):
    if path not in _cache:
        try: _cache[path] = fetch("sleeperliverumbles", path)
        except Exception: _cache[path] = default
    return _cache[path]

def epa_file(season, cur): return _json("epa_weekly.json" if season == cur else f"seasons/{season}/epa_weekly.json")
def has_replay(season, week, cur):
    idx = _json("wp_timeline/index.json" if season == cur else f"seasons/{season}/wp_timeline/index.json", {}) or {}
    return week in (idx.get("weeks") or [])

def card(d, season, week, rid):
    g = next((x for x in d.games if x["season"] == season and x["week"] == week and x["rid"] == rid), None)
    e = epa_file(season, d.cur)
    if not g or not e: return None
    lineup = (e["lineups"].get(str(week)) or {}).get(str(rid))
    if not lineup: return None
    players = []
    for pid, pts in lineup:
        nm, pos = e["names"].get(str(pid), [str(pid), ""])
        players.append({"pos": pos, "name": nm, "pts": pts})
    prior = [x for x in d.reg if x["season"] == season and x["rid"] == rid and x["week"] <= min(week, max(y["week"] for y in d.reg if y["season"] == season))]
    return {"rid": rid, "name": g["m"], "won": bool(g["win"]), "act": g["pts"], "rumbles": g["rumbles"], "vs_field": g["outscored"],
            "season_rumbles": sum(x["rumbles"] for x in prior), "w": sum(1 for x in prior if x["win"]), "l": sum(1 for x in prior if not x["win"]),
            "players": players}

def attach(d, rec):
    """Set rec['cards'] (or drop it). Returns True if a card was produced."""
    sw = None
    rp = rec.get("replay")
    if rec.get("metric") in GAME_METRICS or rec["id"] in EXTRA_IDS:
        if rp and rp.get("rid") and rp.get("opp_rid"): sw = (rp["season"], rp["week"], rp["rid"], rp["opp_rid"])
        else:
            m = re.match(r"Week (\d+) - (\d{4})", rec.get("when", ""))
            if m and int(m.group(2)) >= 2021 and rec.get("holders"):
                wk, y = int(m.group(1)), int(m.group(2))
                g = next((x for x in d.games if x["season"] == y and x["week"] == wk and x["m"] == rec["holders"][0]), None)
                if g: sw = (y, wk, g["rid"], g["opp_rid"])
    if not sw:
        rec.pop("cards", None); return False
    y, wk, rid, opp = sw
    a, b = card(d, y, wk, rid), card(d, y, wk, opp)
    if not a or not b:
        rec.pop("cards", None); return False
    rec["cards"] = {"season": y, "week": wk, "teams": [a, b]}
    if not rec.get("replay") and has_replay(y, wk, d.cur):
        from run_util import replay_url
        rec["replay"] = replay_url(y, wk, rid, opp, d.cur)
    if rec.get("evidence"):                       # the card replaces the cached screenshots
        rec["legacy_evidence"] = rec.get("legacy_evidence", []) + [u for u in rec["evidence"] if u not in rec.get("legacy_evidence", [])]
        rec["evidence"] = []
    return True
