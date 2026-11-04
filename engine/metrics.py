"""Metric functions. Each returns a list of candidates (best-first not required):
   {value, holders:[...], season, week|None, rid|None, detail, complete}
   `scope`: 'all' = data covers every season (2013+), 'weekly' = only 2021+ weekly data exists (can challenge, can't prove)."""
import collections

ALIASES = {"tkitaev": "Tommy", "Ozviagin": "Oleg"}   # Sleeper usernames Rumble Central shows for some old rosters
MAX_WEEK = 17                                          # fantasy weeks; Sleeper week 18 is not a league week

OVERRIDES = {(2023, "Roster 9"): "Tommy"}              # roster whose owner left Sleeper (see Head-to-Head README, ROSTER_OVERRIDES)
def norm(n, season=None): return OVERRIDES.get((season, n)) or ALIASES.get(n, n)

class Data:
    def __init__(self, raw):
        self.raw = raw; cur = raw["current"]; self.cur = cur
        self.games = []
        for g in raw["games"]:
            if g["week"] > MAX_WEEK: continue
            g = dict(g, m=norm(g["m"], g["season"]), opp=norm(g["opp"], g["season"]) if g["opp"] else None); self.games.append(g)
        self.reg = [g for g in self.games if g["reg"]]
        sa = collections.defaultdict(list)
        for g in self.reg: sa[g["season"]].append(g["pts"])
        self.season_avg = {y: sum(v) / len(v) for y, v in sa.items()}
        wk = collections.defaultdict(list)
        for g in self.reg: wk[(g["season"], g["week"])].append(g["pts"])
        self.week_avg = {k: sum(v) / len(v) for k, v in wk.items()}
        self.done = {y for y in sa if y < cur}            # seasons that are over
        # season rows 2013..: frozen history + 2021+ rebuilt from weekly (so both agree on one shape)
        self.srows = []
        for y, s in raw["seasons"].items():
            n = s["teams"]; mpf = sum(r["pf"] for r in s["rows"]) / n; mpa = sum(r["pa"] for r in s["rows"]) / n
            for r in s["rows"]:
                gp = r["w"] + r["l"]
                self.srows.append(dict(season=int(y), m=norm(r["name"]), w=r["w"], l=r["l"], pf=r["pf"], pa=r["pa"], fw=r["fw"], fl=r["fl"],
                    pf_plus=100 * r["pf"] / mpf, pa_plus=100 * r["pa"] / mpa, gp=gp, weeks=s["weeks"]))
        self.playoff_teams = collections.defaultdict(set)
        for p in raw["playoffs"]:
            self.playoff_teams[p["season"]] |= {norm(p["winner"]), norm(p["loser"])}

def _c(value, holders, season, week=None, rid=None, detail="", opp_rid=None):
    return {"value": value, "holders": holders if isinstance(holders, list) else [holders], "season": season, "week": week, "rid": rid, "opp_rid": opp_rid, "detail": detail}

# ---------- season-level (complete: 2013+) ----------
def season_pf(d): return [_c(r["pf"], r["m"], r["season"]) for r in d.srows if r["season"] in d.done_all]
def season_pa(d): return [_c(r["pa"], r["m"], r["season"]) for r in d.srows if r["season"] in d.done_all]
def pf_plus(d): return [_c(round(r["pf_plus"], 1), r["m"], r["season"]) for r in d.srows if r["season"] in d.done_all]
def pa_plus(d): return [_c(round(r["pa_plus"], 1), r["m"], r["season"]) for r in d.srows if r["season"] in d.done_all]
def field_pct(d): return [_c(round(100 * r["fw"] / (r["fw"] + r["fl"]), 1), r["m"], r["season"], detail=f'{r["fw"]}-{r["fl"]}') for r in d.srows if r["season"] in d.done_all]
def reg_wins(d): return [_c(r["w"], r["m"], r["season"]) for r in d.srows if r["season"] in d.done_all]
def luck(d): return [_c(round(100 * (r["w"] / r["gp"] - r["fw"] / (r["fw"] + r["fl"])), 1), r["m"], r["season"]) for r in d.srows if r["season"] in d.done_all]
def pts_missed_playoffs(d):
    return [_c(r["pf"], r["m"], r["season"]) for r in d.srows if r["season"] in d.done_all and r["season"] in d.playoff_teams and r["m"] not in d.playoff_teams[r["season"]]]
def pts_made_playoffs(d):
    return [_c(r["pf"], r["m"], r["season"]) for r in d.srows if r["season"] in d.done_all and r["m"] in d.playoff_teams.get(r["season"], ())]

# ---------- weekly-level (2021+) ----------
def _gref(g, v, detail=""): return _c(v, g["m"], g["season"], g["week"], g["rid"], detail, g["opp_rid"])
def game_pts(d): return [_gref(g, g["pts"], f'vs {g["opp"]} {g["opp_pts"]}') for g in d.games if g["reg"] or g["week"] >= 16]
def game_pts_adj(d): return [_gref(g, round(100 * g["pts"] / d.season_avg[g["season"]], 2), f'{g["pts"]} pts') for g in d.reg]
def margin(d): return [_gref(g, round(g["pts"] - g["opp_pts"], 2), f'{g["pts"]} vs {g["opp_pts"]} over {g["opp"]}') for g in d.games if g["win"] and (g["reg"] or g["week"] >= 16)]
def multiple(d): return [_gref(g, round(g["pts"] / g["opp_pts"], 2), f'{g["pts"]} vs {g["opp_pts"]} over {g["opp"]}') for g in d.games if g["win"] and g["opp_pts"] > 0 and (g["reg"] or g["week"] >= 16)]
def win_pts(d): return [_gref(g, g["pts"], f'over {g["opp"]} {g["opp_pts"]}') for g in d.games if g["win"] and (g["reg"] or g["week"] >= 16)]
def loss_pts(d): return [_gref(g, g["pts"], f'lost to {g["opp"]} {g["opp_pts"]}') for g in d.games if not g["win"] and (g["reg"] or g["week"] >= 16)]
def league_week(d): return [_c(round(v, 2), "DTFClub", k[0], k[1]) for k, v in d.week_avg.items()]
def league_week_adj(d): return [_c(round(100 * v / d.season_avg[k[0]], 1), "DTFClub", k[0], k[1]) for k, v in d.week_avg.items()]

def _per_season(d, pred):
    by = collections.defaultdict(lambda: collections.defaultdict(int))
    for g in d.reg:
        if g["season"] in d.done and pred(g): by[g["season"]][g["m"]] += 1
    return [_c(n, m, y) for y, ms in by.items() for m, n in ms.items()]
def top_weeks(d): return _per_season(d, lambda g: g["outscored"] == g["n"] - 1)
def bottom_weeks(d): return _per_season(d, lambda g: g["outscored"] == 0)

def _streaks(d, pred, games=None):
    out = []; by = collections.defaultdict(list)
    for g in (games or d.games):
        if g["reg"] or g["week"] >= 16: by[g["m"]].append(g)
    for m, gs in by.items():
        gs.sort(key=lambda g: (g["season"], g["week"])); run = []
        for g in gs + [None]:
            if g is not None and pred(g): run.append(g); continue
            if run: out.append(_c(len(run), m, run[0]["season"], run[0]["week"], run[0]["rid"], f'Week {run[0]["week"]} {run[0]["season"]} - Week {run[-1]["week"]} {run[-1]["season"]}', run[0]["opp_rid"]))
            run = []
    return out
def win_streak(d): return _streaks(d, lambda g: g["win"])
def loss_streak(d): return _streaks(d, lambda g: not g["win"])
def top_streak(d): return [c for c in _streaks(d, lambda g: g["outscored"] == g["n"] - 1, d.reg)]
def bottom_streak(d): return [c for c in _streaks(d, lambda g: g["outscored"] == 0, d.reg)]

def composite(d):
    """A 'composite win' each week for a H2H win AND a second one for scoring in the top half of the league that week."""
    by = collections.defaultdict(int)
    for g in d.reg:
        if g["season"] in d.done: by[(g["season"], g["m"])] += int(g["win"]) + int(g["outscored"] >= g["n"] / 2)
    return [_c(v, m, y) for (y, m), v in by.items()]

def rumble_margin(d):
    """Smallest gap between two teams' scores in the same week: a 'Rumble win' is beating any team, not just your opponent."""
    by = collections.defaultdict(list)
    for g in d.reg: by[(g["season"], g["week"])].append(g)
    out = []
    for (y, w), gs in by.items():
        gs = sorted(gs, key=lambda g: -g["pts"])
        for hi, lo in zip(gs, gs[1:]):
            if hi["pts"] - lo["pts"] < 0.005: continue          # an exact tie is not a win
            out.append(_c(round(hi["pts"] - lo["pts"], 2), hi["m"], y, w, hi["rid"], f'{hi["pts"]} vs {lo["pts"]} over {lo["m"]}', lo["rid"]))
    return out

def rumble_pct(d):
    out = []; by = collections.defaultdict(lambda: [0, 0])
    for g in d.reg:
        if g["season"] in d.done: by[(g["season"], g["m"])][0] += g["rumbles"]; by[(g["season"], g["m"])][1] += (g["n"] - 1) + 9
    return [_c(round(100 * a / b, 1), m, y) for (y, m), (a, b) in by.items()]

SEASON_ALL = {"season_pf", "season_pa", "pf_plus", "pa_plus", "field_pct", "reg_wins", "luck", "pts_missed_playoffs", "pts_made_playoffs"}
REGISTRY = {k: v for k, v in globals().items() if callable(v) and k in {
    "season_pf","season_pa","pf_plus","pa_plus","field_pct","reg_wins","luck","pts_missed_playoffs","pts_made_playoffs","game_pts","game_pts_adj",
    "margin","multiple","win_pts","loss_pts","league_week","league_week_adj","top_weeks","bottom_weeks","win_streak","loss_streak","top_streak","bottom_streak","rumble_pct","composite","rumble_margin"}}
