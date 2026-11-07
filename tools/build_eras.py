#!/usr/bin/env python3
"""Builds data/eras.json: which league format each season had, and the eras that follow from it.

From 2021 on the format is read from each season's Sleeper league (scoring settings and roster slots), so a new season picks up
its era by itself; earlier seasons were not on Sleeper and keep the hand-set entries already in eras.json (source "sheet").

  ppr        'ppr' when every reception tier pays 1 point (or `rec` >= 1), else 'nppr' (2021's tiered 0.25-0.5 is no-PPR on purpose)
  superflex  a SUPER_FLEX slot in the lineup
  fd         points per first down (bonus_fd_rb / wr / te; QB's is smaller) when any is above 0

An era is a run of seasons with the same scoring and lineup: No PPR, PPR, Superflex no PPFD, Superflex + 0.5 PPFD.

    python3 tools/build_eras.py                       # Rumble Central's league ids from GitHub, settings from Sleeper
    RB_SRC=/path python3 tools/build_eras.py          # league ids from local checkouts (/path/sleeperliverumbles)
"""
import json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "data", "eras.json")
RAW = "https://raw.githubusercontent.com/namkurd/SleeperLiveRumbles/main/"
SRC = os.environ.get("RB_SRC")
TIERS = ("rec_0_4", "rec_5_9", "rec_10_19", "rec_20_29", "rec_30_39", "rec_40p")

def get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "recordbook"}), timeout=60))

def rc(path):
    if SRC: return json.load(open(os.path.join(SRC, "sleeperliverumbles", path), encoding="utf-8"))
    return get(RAW + path)

def fmt_pts(v): return ("%g" % v)

def season_format(league):
    sc = league.get("scoring_settings") or {}
    ppr = "ppr" if (sc.get("rec", 0) >= 1 or all(sc.get(k, 0) >= 1 for k in TIERS)) else "nppr"
    fd = max(sc.get("bonus_fd_rb", 0), sc.get("bonus_fd_wr", 0), sc.get("bonus_fd_te", 0))
    out = {"teams": league.get("total_rosters"), "ppr": ppr, "superflex": "SUPER_FLEX" in (league.get("roster_positions") or []), "source": "sleeper"}
    if fd > 0: out["fd"] = fmt_pts(fd)
    return out

def era_of(f):
    if f["ppr"] == "nppr": return "nppr"
    if not f["superflex"]: return "ppr"
    return "sffd" if f.get("fd") else "sf"

def main():
    doc = json.load(open(P, encoding="utf-8")); seasons = doc["seasons"]
    idx = rc("seasons/index.json"); cur = int(idx["current"])
    for y in sorted({int(s["season"]) for s in idx["seasons"]} | {cur}):
        try:
            lid = rc("rumbles_history.json" if y == cur else "seasons/%d/rumbles_history.json" % y)["league_id"]
            seasons[str(y)] = season_format(get("https://api.sleeper.app/v1/league/%s" % lid))
        except Exception as e:
            print("could not read the Sleeper league for %d (%s); keeping the old entry" % (y, e), file=sys.stderr)
    for v in seasons.values(): v.setdefault("source", "sheet")
    fd_pts = sorted({f["fd"] for f in seasons.values() if f.get("fd")})
    names = {"nppr": "No PPR", "ppr": "PPR", "sf": "Superflex no PPFD", "sffd": "Superflex + %s PPFD" % (fd_pts[-1] if fd_pts else "0.5")}
    eras, last = {}, max(int(y) for y in seasons)
    for y in sorted(seasons, key=int):
        f = seasons[y]; f["era"] = era_of(f); eras.setdefault(f["era"], []).append(int(y))
    order = ["nppr", "ppr", "sf", "sffd"]
    doc["eras"] = [{"id": k, "name": names[k], "seasons": eras[k], "label": ("%d-%d" % (eras[k][0], eras[k][-1]) if eras[k][0] != eras[k][-1] else str(eras[k][0])) if eras[k][-1] != last or k == "nppr" else "%d-" % eras[k][0]} for k in order if k in eras]
    doc["_comment"] = ("League format by season. 2021 on is read from each season's Sleeper league settings by tools/build_eras.py (reception tiers, SUPER_FLEX slot, first-down bonuses, number of teams); "
                       "2011-2020 were not on Sleeper and are hand-set (source 'sheet'). An era is a run of seasons with the same scoring and lineup. 2021 paid reception tiers of 0.25-0.5 and counts as No PPR on purpose.")
    json.dump(doc, open(P, "w", encoding="utf-8"), indent=1, ensure_ascii=False); open(P, "a").write("\n")
    for e in doc["eras"]: print(e["id"], e["name"], e["label"])

main()
