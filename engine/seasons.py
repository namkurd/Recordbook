"""Season-end counts: titles, finals, playoff trips, #1 seeds, Sackos, scoring crowns, streaks of good/bad seasons.
Ledger = one row per manager per season. 2013+ comes from data (history.json, playoff bracket results, trade-nodes podium, FAB finishes);
2011-12 and the 2013-2020 #1 seeds are only in the old sheet, so they are seeded below (see SEED_*). Data beats the sheet where both exist."""
import collections
from metrics import norm

ALIAS = {"Rohaan": "Haan"}
# Only in the old hand-kept sheet (no Sleeper/bracket data exists for these):
SEED_EARLY = {   # (season, manager) -> flags.  2011: Ryan over Alex in the final; 2012: Steven lost the final (champion not recorded)
    (2011, "Ryan"): {"champ", "playoff", "seed1"}, (2011, "Alex"): {"runner", "playoff"},
    (2012, "Ryan"): {"playoff", "seed1"}, (2012, "Steven"): {"runner", "playoff"},
}
SEED_NO1 = {2013: [], 2014: [], 2015: [], 2016: ["Ryan"], 2017: [], 2018: [], 2019: ["Ryan"], 2020: []}   # #1 seeds 2013-20 known from the sheet only for Ryan
def _n(x): return ALIAS.get(norm(x), norm(x))

def build(d):
    raw = d.raw; cur = raw["current"]; L = collections.defaultdict(lambda: collections.defaultdict(set)); meta = {}
    fab = raw.get("fab") or {}; nodes = raw.get("nodes") or {}; fpo = raw.get("fab_po") or {}
    for (y, m), fl in SEED_EARLY.items(): L[y][m] |= fl
    seasons = {int(y): v for y, v in raw["seasons"].items()}
    finished = {s["s"] for s in (fab.get("seasons") or []) if s.get("finished")} or {y for y in seasons if y < cur}
    for y, sv in seasons.items():
        if y >= cur and y not in finished: continue
        rows = [dict(r, name=_n(r["name"])) for r in sv["rows"]]
        meta[y] = {"teams": len(rows)}
        for r in rows: L[y][r["name"]].add("played")
        pf = {r["name"]: r["pf"] for r in rows}; pa = {r["name"]: r["pa"] for r in rows}
        for m in (n for n, v in pf.items() if v == max(pf.values())): L[y][m].add("top_pf")
        for m in (n for n, v in pf.items() if v == min(pf.values())): L[y][m].add("bottom_pf")
        for m in (n for n, v in pa.items() if v == max(pa.values())): L[y][m].add("high_pa")
        for r in rows:
            L[y][r["name"]].add("winning" if r["w"] >= r["l"] else "losing")
        part = {_n(x) for p in raw["playoffs"] if p["season"] == y for x in (p["winner"], p["loser"])}
        for m in part: L[y][m].add("playoff")
        for m, v in (nodes.get("standings") or {}).get(str(y), {}).items():
            m = _n(m)
            if v.get("p") == "c": L[y][m] |= {"champ", "playoff"}
            if v.get("p") == "s": L[y][m] |= {"runner", "playoff"}
        fin = next((s for s in (fab.get("seasons") or []) if s["s"] == y), None)
        if fin and fin.get("finished"):
            for t in fin["teams"]:
                if t.get("finish") == "Sacko": L[y][_n(t["m"])].add("sacko")
                if t.get("seed") == 1: L[y][_n(t["m"])].add("seed1")
        elif sv.get("order") == "manual" and rows:
            L[y][rows[-1]["name"]].add("sacko")
        for m in SEED_NO1.get(y, []): L[y][m].add("seed1")
        if str(y) in fpo and not fin:
            if fpo[str(y)]: L[y][_n(fpo[str(y)][0])].add("seed1")
    return L

def _count(L, flag, label=None):
    by = collections.defaultdict(list)
    for y in sorted(L):
        for m, fl in L[y].items():
            if flag in fl: by[m].append(y)
    return by
def _fmt_years(ys): return "/".join("'%02d" % (y % 100) for y in ys)
def _cands_count(L, flag):
    out = []
    for m, ys in _count(L, flag).items():
        out.append({"value": len(ys), "holders": [m], "season": ys[-1], "week": None, "rid": None, "opp_rid": None, "detail": _fmt_years(ys), "when": _fmt_years(ys)})
    return out

def _runs(L, pred, flagged_years=None):
    """Longest runs of consecutive seasons for which pred(flags) is True, per manager (a season the manager didn't play breaks the run)."""
    out = []; ms = {m for y in L for m in L[y]}
    for m in ms:
        run = []
        for y in sorted(L) + [None]:
            if y is not None and m in L[y] and pred(L[y][m]) and (not run or y == run[-1] + 1): run.append(y); continue
            if run: out.append({"value": len(run), "holders": [m], "season": run[0], "week": None, "rid": None, "opp_rid": None,
                               "detail": f"{run[0]}-{run[-1]}", "when": f"{run[0]}-{run[-1]}" if len(run) > 1 else str(run[0])})
            run = [y] if (y is not None and m in L[y] and pred(L[y][m])) else []
    return out

def make(d):
    L = build(d); d._ledger = L; R = {}
    R["titles"] = lambda: _cands_count(L, "champ")
    R["finals"] = lambda: _cands_count({y: {m: (f | {"final"} if f & {"champ", "runner"} else f) for m, f in v.items()} for y, v in L.items()}, "final")
    R["final_losses"] = lambda: _cands_count(L, "runner")
    R["final_streak"] = lambda: _runs(L, lambda f: bool(f & {"champ", "runner"}))
    R["playoff_apps"] = lambda: _cands_count(L, "playoff")
    R["playoff_streak"] = lambda: _runs(L, lambda f: "playoff" in f)
    def drought():
        pred = lambda f: "playoff" not in f and "played" in f
        return _runs({y: v for y, v in L.items() if y >= 2013}, pred)
    R["drought"] = drought
    R["sackos"] = lambda: _cands_count(L, "sacko")
    R["seed1"] = lambda: _cands_count(L, "seed1")
    R["top_pf_seasons"] = lambda: _cands_count(L, "top_pf")
    R["bottom_pf_seasons"] = lambda: _cands_count(L, "bottom_pf")
    R["high_pa_seasons"] = lambda: _cands_count(L, "high_pa")
    R["winning_streak_seasons"] = lambda: _runs(L, lambda f: "winning" in f)
    R["losing_streak_seasons"] = lambda: _runs(L, lambda f: "losing" in f)
    # per-season parts, so the page can re-add these records for an era (see eraParts in index.html)
    def flagged(pred, y0=0):
        return [[y, m, 1, 1] for y in sorted(L) if y >= y0 for m, f in L[y].items() if pred(f)]
    def counts(pred): return {"agg": "sum", "fmt": "int", "when": "years", "min": 1, "rows": flagged(pred)}
    def streak(pred, y0=0): return {"agg": "streak", "fmt": "int", "min": 1, "rows": flagged(pred, y0)}
    d._era_parts = {
        "titles": lambda: counts(lambda f: "champ" in f), "finals": lambda: counts(lambda f: bool(f & {"champ", "runner"})), "final_losses": lambda: counts(lambda f: "runner" in f),
        "playoff_apps": lambda: counts(lambda f: "playoff" in f), "sackos": lambda: counts(lambda f: "sacko" in f), "seed1": lambda: counts(lambda f: "seed1" in f),
        "top_pf_seasons": lambda: counts(lambda f: "top_pf" in f), "bottom_pf_seasons": lambda: counts(lambda f: "bottom_pf" in f), "high_pa_seasons": lambda: counts(lambda f: "high_pa" in f),
        "final_streak": lambda: streak(lambda f: bool(f & {"champ", "runner"})), "playoff_streak": lambda: streak(lambda f: "playoff" in f),
        "drought": lambda: streak(lambda f: "playoff" not in f and "played" in f, 2013),
        "winning_streak_seasons": lambda: streak(lambda f: "winning" in f), "losing_streak_seasons": lambda: streak(lambda f: "losing" in f),
    }
    return R

COMPLETE = {"titles", "finals", "final_losses", "final_streak", "playoff_apps", "playoff_streak", "drought", "sackos", "top_pf_seasons", "bottom_pf_seasons", "high_pa_seasons", "winning_streak_seasons", "losing_streak_seasons"}
