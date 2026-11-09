"""Records built from the per-week facts cache (facts.py): bench, shotguns, zeros, comebacks, lead changes, projections, Thursday/Saturday/Monday."""
import collections, json
from metrics import norm
import cards as C

def wk(s, w): return f"Week {w} - {s}"
def _c(value, holders, s, w=None, rid=None, opp=None, when=None, ht=None, card=None):
    return {"value": value, "holders": holders if isinstance(holders, list) else [holders], "season": s, "week": w, "rid": rid, "opp_rid": opp,
            "detail": "", "when": when, "holder_text": ht, "card": card}
def _isdef(p): return len(p) <= 3 and p.isalpha()

def make(d, cache, names):
    nm = lambda p: (names.get(p) or [p, ""])[0]
    G = {(g["season"], g["week"], g["rid"]): g for g in d.games}
    rows = []
    for k, w in cache["weeks"].items():
        s, week = map(int, k.split("-"))
        for rid, t in w["teams"].items():
            g = G.get((s, week, int(rid)))
            if g: rows.append({"s": s, "w": week, "rid": int(rid), "g": g, "t": t, "wk": w, "m": g["m"]})
    rows_all = rows
    rows = [r for r in rows if True]
    by = {(r["s"], r["w"], r["rid"]): r for r in rows}
    sl = [r for r in rows if r["wk"].get("psrc") == "sleeper"]          # weeks whose pre-game numbers are Sleeper's own projections (not an average fallback)
    def mine(r, key): return by.get((r["s"], r["w"], r["g"]["opp_rid"]))

    def zeros(r): return [p for p in r["t"]["zeros"] if p != "0" and not _isdef(p)]
    qb_out = d.raw.get("qb_out") or set()
    def shots(r): return [x for x in r["t"]["shot"] if x[0] != "0" and (r["s"], r["w"], r["rid"], str(x[0])) not in qb_out]      # a starter ruled out in his game is not a Shotgun
    def fact(title, who, rows_):
        return {"kind": "facts", "title": title, "blocks": [{"head": who, "chip": None, "rows": rows_}]}
    def ref(r): return r["rid"], r["g"]["opp_rid"]

    R = {}
    # ---- bench ----
    def bench():
        out = []
        for r in rows:
            top = [[nm(p), f"{v:.1f}"] for p, v in r["t"]["bench_top"][:6]]
            out.append(_c(round(r["t"]["bench"], 2), [r["m"]], r["s"], r["w"], *ref(r), when=wk(r["s"], r["w"]), ht=r["m"],
                          card=fact(f'Bench · Week {r["w"]}, {r["s"]}', r["m"], [[a, b + " pts"] for a, b in top] + [["All bench", f'{r["t"]["bench"]:.1f} pts']])))
        return out
    R["bench"] = bench
    def bench_season():
        a = collections.defaultdict(float)
        for r in rows:
            if r["s"] < d.cur and r["w"] <= 15: a[(r["s"], r["m"])] += r["t"]["bench"]
        return [_c(round(v, 1), [m], s, when=str(s)) for (s, m), v in a.items()]
    R["bench_season"] = bench_season
    # ---- shotguns ----
    def shot_league():
        a = collections.Counter()
        for r in rows:
            if r["s"] < d.cur: a[r["s"]] += len(shots(r))
        return [_c(v, ["DTFClub"], s, when=str(s)) for s, v in a.items()]
    R["shot_league"] = shot_league
    def shot_week():
        return [_c(len(shots(r)), [r["m"]], r["s"], r["w"], *ref(r), when=wk(r["s"], r["w"]), ht=r["m"],
                   card=fact(f'Shotguns · Week {r["w"]}, {r["s"]}', r["m"], [[nm(p), f"{v:.1f} pts"] for p, v in shots(r)])) for r in rows if shots(r)]
    R["shot_week"] = shot_week
    def shot_season():
        a = collections.Counter()
        for r in rows:
            if r["s"] < d.cur: a[(r["s"], r["m"])] += len(shots(r))
        return [_c(v, [m], s, when=str(s)) for (s, m), v in a.items()]
    R["shot_season"] = shot_season
    # ---- zeros in a win, top-player share ----
    def zeros_win():
        out = []
        for r in rows:
            z = zeros(r)
            if r["g"]["win"] and z: out.append(_c(len(z), [r["m"]], r["s"], r["w"], *ref(r), when=wk(r["s"], r["w"]), ht=f'{r["m"]} — {", ".join(nm(p) for p in z)}'))
        return out
    R["zeros_win"] = zeros_win
    def top_share():
        return [_c(r["t"]["top"][2], [r["m"]], r["s"], r["w"], *ref(r), when=wk(r["s"], r["w"]), ht=f'{r["m"]} — {nm(r["t"]["top"][0])}') for r in rows if r["t"]["top"][2]]
    R["top_share"] = top_share
    # ---- clock: Thursday night, Saturday, Monday night ----
    def thu_league():
        out = []
        for k, w in cache["weeks"].items():
            if w.get("tnf"): s, week = map(int, k.split("-")); out.append(_c(w["tnf_total"], ["DTFClub"], s, week, when=f'{wk(s, week)} {w["tnf"].replace("@", " at ")}'))
        return out
    R["thu_league"] = thu_league
    def clock(key):
        return lambda: [_c(r["t"][key], [r["m"]], r["s"], r["w"], *ref(r), when=wk(r["s"], r["w"]), ht=r["m"]) for r in rows if r["t"].get(key)]
    R["sat_pts"] = clock("sat"); R["thu_pts"] = clock("thu"); R["mon_pts"] = clock("mon")
    def mnf_overcome():
        out = []
        for r in rows:
            m = r["t"].get("mnf")
            if r["g"]["win"] and m is not None and m < 0:
                o = mine(r, "t"); out.append(_c(round(-m, 2), [r["m"]], r["s"], r["w"], *ref(r), when=wk(r["s"], r["w"]), ht=f'{r["m"]} over {r["g"]["opp"]}'))
        return out
    R["mnf_overcome"] = mnf_overcome
    # ---- comebacks, blown leads, lead changes ----
    def comeback():
        return [_c(round(-r["t"]["lead_min"], 2), [r["m"]], r["s"], r["w"], *ref(r), when=wk(r["s"], r["w"]), ht=f'{r["m"]} over {r["g"]["opp"]}') for r in rows if r["g"]["win"] and r["t"].get("lead_min", 0) < 0]
    def blown():
        return [_c(round(r["t"]["lead_max"], 2), [r["m"]], r["s"], r["w"], *ref(r), when=wk(r["s"], r["w"]), ht=f'{r["m"]} (lost to {r["g"]["opp"]})') for r in rows if not r["g"]["win"] and r["t"].get("lead_max", 0) > 0]
    def changes():
        seen = set(); out = []
        for r in rows:
            k = (r["s"], r["w"], min(r["rid"], r["g"]["opp_rid"]))
            if k in seen or "chg" not in r["t"]: continue
            seen.add(k); w_ = r if r["g"]["win"] else mine(r, "t")
            if w_: out.append(_c(r["t"]["chg"], [w_["m"]], r["s"], r["w"], *ref(w_), when=wk(r["s"], r["w"]), ht=f'{w_["m"]} over {w_["g"]["opp"]}'))
        return out
    R["comeback"] = comeback; R["blown_lead"] = blown; R["lead_changes"] = changes
    # ---- projections ----
    def upset():
        out = []
        for r in sl:
            o = mine(r, "t")
            if r["g"]["win"] and o and r["t"].get("proj") and o["t"].get("proj"):
                gap = o["t"]["proj"] - r["t"]["proj"]
                if gap > 0: out.append(_c(round(gap, 2), [r["m"]], r["s"], r["w"], *ref(r), when=wk(r["s"], r["w"]), ht=f'{r["m"]} over {r["g"]["opp"]}'))
        return out
    def over_proj(sign):
        return lambda: [_c(round(sign * (r["g"]["pts"] - r["t"]["proj"]), 2), [r["m"]], r["s"], r["w"], *ref(r), when=wk(r["s"], r["w"]), ht=r["m"]) for r in sl if r["t"].get("proj")]
    R["upset_proj"] = upset; R["over_proj"] = over_proj(1); R["under_proj"] = over_proj(-1)
    def hp(adj):
        out = []
        for r in sl:
            pj = r["t"].get("proj")
            if not pj or r["s"] not in d.season_avg: continue
            pct = 100 * pj / d.season_avg[r["s"]] - 100
            c = _c(round(100 * pj / d.season_avg[r["s"]], 2) if adj else pj, [r["m"]], r["s"], r["w"], *ref(r), when=wk(r["s"], r["w"]), ht=r["m"])
            c["display"] = f"{pj:.2f} ({pct:.0f}% above league average score)"; out.append(c)
        return out
    R["high_proj"] = lambda: hp(False); R["high_proj_adj"] = lambda: hp(True)
    return R

FORMAT = {
 "bench": lambda v: f"{v:.2f}", "bench_season": lambda v: f"{v:.1f} pts", "shot_league": lambda v: f"{v:.0f}", "shot_week": lambda v: f"{v:.0f}", "shot_season": lambda v: f"{v:.0f}",
 "zeros_win": lambda v: f"{v:.0f}", "top_share": lambda v: f"{v:.1f}%", "thu_league": lambda v: f"{v:.1f}", "sat_pts": lambda v: f"{v:.2f}", "thu_pts": lambda v: f"{v:.2f}", "mon_pts": lambda v: f"{v:.2f}",
 "mnf_overcome": lambda v: f"{v:.2f}", "comeback": lambda v: f"{v:.1f} pts", "blown_lead": lambda v: f"{v:.1f} pts", "lead_changes": lambda v: f"{v:.0f}",
 "upset_proj": lambda v: f"{v:.1f} pts", "over_proj": lambda v: f"+{v:.1f} pts", "under_proj": lambda v: f"-{v:.1f} pts", "high_proj": lambda v: f"{v:.2f}", "high_proj_adj": lambda v: f"{v:.2f}",
}
