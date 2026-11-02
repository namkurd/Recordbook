"""Trade, FAB and sit/start records (data since 2021).  Sources: SleeperTradeNodes data.json (trades, PAR swing) and
FAB-Management data.json (pickups, drops, lineup decisions).  PAR = points above replacement (see those repos' READMEs)."""
import collections, re
from metrics import norm

def N(x): return {"Rohaan": "Haan"}.get(norm(x), norm(x))
def _c(value, holders, season, week=None, rid=None, opp_rid=None, detail="", when=None, holder_text=None, card=None):
    return {"value": value, "holders": holders if isinstance(holders, list) else [holders], "season": season, "week": week, "rid": rid, "opp_rid": opp_rid,
            "detail": detail, "when": when, "holder_text": holder_text, "card": card}
def wk(s, w): return f"Week {w} - {s}"

def _rids(d):
    out = {}
    for y, m in d.raw["rosters"].items(): out[y] = {N(n): r for r, n in m.items()}
    return out

def trades(d):
    return [t for t in ((d.raw.get("nodes") or {}).get("trades") or []) if t.get("a") and t.get("b")]

def _assets(lst): return [{"n": re.sub(r" - [A-Z]{2,3}$", "", x["n"]), "v": x.get("v")} for x in lst]
def trade_card(t, hl=None):
    """Both sides of a trade as a 'fact card'."""
    def side(name, got, gave, par, fp, vgot, vgave):
        return {"head": name, "chip": "WON" if hl == name else None, "rows": [
            ["Got", ", ".join(f'{x["n"]} ({x["v"]})' for x in _assets(got))], ["Gave", ", ".join(f'{x["n"]} ({x["v"]})' for x in _assets(gave))],
            ["Value in / out", f"{vgot} / {vgave}"], ["PAR since", f"{par:+.1f}" if par is not None else "–"]]}
    return {"kind": "trade", "title": f'Trade · Week {t["w"]}, {t["s"]}', "blocks": [
        side(N(t["a"]), t["bg"], t["ag"], t.get("lga"), t.get("fpa"), t["vb"], t["va"]),
        side(N(t["b"]), t["ag"], t["bg"], t.get("lgb"), t.get("fpb"), t["va"], t["vb"])]}
def _tc(value, t, who, loser, detail=""):
    return _c(value, [who], t["s"], t["w"], when=wk(t["s"], t["w"]), holder_text=f"{who} over {loser}", detail=detail, card=trade_card(t, who))

def _sides(t):
    return [(N(t["a"]), N(t["b"]), t.get("lga")), (N(t["b"]), N(t["a"]), t.get("lgb"))]

def trade_net(d): return [_tc(round(t["lgNet"], 1), t, N(t["a"]), N(t["b"])) if t["lgNet"] > 0 else _tc(round(-t["lgNet"], 1), t, N(t["b"]), N(t["a"]))
                          for t in trades(d) if t.get("lgNet") is not None]
def trade_best_side(d): return [_tc(round(p, 1), t, w, l) for t in trades(d) for w, l, p in _sides(t) if p is not None]
def trade_worst_side(d): return [_c(round(p, 1), [w], t["s"], t["w"], when=wk(t["s"], t["w"]), holder_text=f"{w} (vs {l})", card=trade_card(t, l)) for t in trades(d) for w, l, p in _sides(t) if p is not None]
def trade_value_gap(d):
    out = []
    for t in trades(d):
        gap = t["vb"] - t["va"]          # a gave va, got vb
        if gap: w, l = (N(t["a"]), N(t["b"])) if gap > 0 else (N(t["b"]), N(t["a"])); out.append(_tc(round(abs(gap), 1), t, w, l))
    return out
def trade_blockbuster(d): return [_c(round(t["tv"], 1), [N(t["a"]), N(t["b"])], t["s"], t["w"], when=wk(t["s"], t["w"]), holder_text=f'{N(t["a"])} & {N(t["b"])}', card=trade_card(t)) for t in trades(d)]
def trade_assets(d): return [_c(len(t["ag"]) + len(t["bg"]), [N(t["a"]), N(t["b"])], t["s"], t["w"], when=wk(t["s"], t["w"]), holder_text=f'{N(t["a"])} & {N(t["b"])}', card=trade_card(t)) for t in trades(d)]

def _count_rows(cnt, when_fn=None):
    return [_c(v, [k] if not isinstance(k, tuple) else list(k), 0, when=when_fn(k) if when_fn else None, holder_text=" & ".join(k) if isinstance(k, tuple) else None) for k, v in cnt.items()]
def trades_career(d):
    c = collections.Counter(); first = {}
    for t in trades(d):
        for m in (N(t["a"]), N(t["b"])): c[m] += 1
    return [dict(x, season=2021, when="2021-") for x in _count_rows(c)]
def trades_partner(d):
    c = collections.Counter(tuple(sorted((N(t["a"]), N(t["b"])))) for t in trades(d))
    return [dict(x, season=2021, when="2021-") for x in _count_rows(c)]
def _season_done(d, y): return y < d.cur
def trades_league_season(d):
    c = collections.Counter(t["s"] for t in trades(d))
    return [_c(v, ["DTFClub"], y, when=str(y)) for y, v in c.items() if _season_done(d, y)]
def trades_team_season(d):
    c = collections.Counter()
    for t in trades(d):
        for m in (N(t["a"]), N(t["b"])): c[(t["s"], m)] += 1
    return [_c(v, [m], y, when=str(y)) for (y, m), v in c.items() if _season_done(d, y)]
def trader_net(d, sign):
    tot = collections.defaultdict(lambda: [0.0, 0])
    for t in trades(d):
        if t.get("lgNet") is None: continue
        for w, l, p in _sides(t):
            if p is not None: tot[w][0] += p; tot[w][1] += 1
    return [_c(round(v, 1), [m], 2021, when=f"{n} trades, 2021-", detail=str(n)) for m, (v, n) in tot.items() if n >= 3]

# ---------------- FAB ----------------
def fab(d): return d.raw.get("fab") or {}
def claims(d): return [a for a in fab(d).get("adds", []) if a.get("ty") == "W"]
def free_agents(d): return [a for a in fab(d).get("adds", []) if a.get("ty") == "F"]
def pickup_card(a, rid_map=None):
    rows = [["Pickup", f'{a["pl"]} ({a["pos"]})'], ["Winning bid", f'${a["b"]}'], ["Points above replacement", f'{a["par"]:+.1f} started · {a["parR"]:+.1f} rostered'],
            ["Weeks started / benched", f'{a.get("ws", 0)} / {a.get("wb", 0)}'], ["Outcome", {"kept": "Kept", "dropped": "Later dropped"}.get(a.get("end"), str(a.get("end") or ""))]]
    return {"kind": "pickup", "title": f'Pickup · Week {a["w"]}, {a["s"]}', "blocks": [{"head": N(a["m"]), "chip": None, "rows": rows}]}
def _pc(value, a, who=None):
    return _c(value, [N(a["m"])], a["s"], a["w"], when=wk(a["s"], a["w"]), holder_text=f'{N(a["m"])} — {a["pl"]}', card=pickup_card(a))
def fab_best_par(d): return [_pc(a["par"], a) for a in claims(d) if a.get("par") is not None]
def fab_best_fa(d): return [_pc(a["par"], a) for a in free_agents(d) if a.get("par") is not None]
def fab_bid(d): return [_pc(a["b"], a) for a in claims(d)]
def fab_worst(d): return [_pc(a["par"], a) for a in claims(d) if a.get("par") is not None and a["b"] >= 40]
def fab_value(d): return [_pc(round(a["par"] / a["b"], 2), a) for a in claims(d) if a.get("par") is not None and a["b"] >= 10]
def _fin(d): return {s["s"] for s in fab(d).get("seasons", []) if s.get("finished")}
def fab_spent(d):
    return [_c(t["bids"], [N(t["m"])], s["s"], when=str(s["s"])) for s in fab(d).get("seasons", []) if s["s"] in _fin(d) for t in s["teams"]]
def _summ(d, key, sub="all"):
    out = []
    for y, ms in fab(d).get("summary", {}).items():
        if int(y) not in _fin(d): continue
        for m, v in ms.items():
            x = (v.get(sub) if sub in v else None)
            if isinstance(x, dict) and key in x: out.append((int(y), N(m), x[key]))
    return out
def _sc(rows, nd=1): return [_c(round(v, nd) if isinstance(v, float) else v, [m], y, when=str(y)) for y, m, v in rows]
def fab_season_par(d): return _sc(_summ(d, "par"))
def fab_season_net(d): return _sc(_summ(d, "net"))
def fab_season_hits(d): return _sc(_summ(d, "hits"))
def fab_season_adds(d): return _sc(_summ(d, "adds"))
def fab_season_regret(d): return _sc(_summ(d, "regret"))
def fab_regret_drop(d):
    out = []
    for x in fab(d).get("drops", []):
        if not x.get("sbp"): continue
        who = ", ".join(sorted({N(b[2]) for b in (x.get("sbl") or [])})) or "others"
        card = {"kind": "drop", "title": f'Drop · Week {x["w"]}, {x["s"]}', "blocks": [{"head": N(x["m"]), "chip": None, "rows": [
            ["Dropped", f'{x["pl"]} ({x["pos"]})'], ["Started PAR for others after the drop", f'{x["sbp"]:+.1f}'], ["Picked up by", who]]}]}
        out.append(_c(round(x["sbp"], 1), [N(x["m"])], x["s"], x["w"], when=wk(x["s"], x["w"]), holder_text=f'{N(x["m"])} — {x["pl"]}', card=card))
    return out

# ---------------- sit / start ----------------
def _swap_card(l, brain=False):
    o, i = l["out"], l["inn"] if "inn" in l else None
    if brain: i = l["inn"]
    ctx = f'{l["my"]:.2f} vs {l["opp"]:.2f} against {N(l["oppm"])}'
    return {"kind": "swap", "title": f'{"Call" if brain else "Miss"} · {l["slot"]}, Week {l["w"]}, {l["s"]}', "blocks": [{"head": N(l["m"]), "chip": None, "rows": [
        ["Started" if not brain else "Started (right call)", f'{o["pl"]} — {o["pts"]:.1f} pts (proj {o["proj"]})'],
        ["Benched" if not brain else "Benched", f'{i["pl"]} — {i["pts"]:.1f} pts (proj {i["proj"]})'],
        ["Matchup", ctx]]}]}
def _ref(d, l):
    r = _rids(d).get(l["s"], {}); return r.get(N(l["m"])), r.get(N(l["oppm"]))
def lineup_rows(d, tier): return [l for l in fab(d).get("lineup", []) if l.get("tier") == tier and l.get("lost") is not None]
def sit_start_miss(d):
    out = []
    for l in lineup_rows(d, "clear"):
        rid, opp = _ref(d, l); out.append(_c(round(l["lost"], 1), [N(l["m"])], l["s"], l["w"], rid, opp, when=wk(l["s"], l["w"]), holder_text=f'{N(l["m"])} — sat {l["inn"]["pl"]}', card=_swap_card(l)))
    return out
def sit_start_call(d):
    out = []
    for c in fab(d).get("calls", []):
        if c.get("tier") != "brain" or c.get("gain") is None: continue
        rid, opp = _ref(d, c); out.append(_c(round(c["gain"], 1), [N(c["m"])], c["s"], c["w"], rid, opp, when=wk(c["s"], c["w"]), holder_text=f'{N(c["m"])} — started {c["out"]["pl"]}', card=_swap_card(c, True)))
    return out
def worst_week(d):
    best = {}
    for l in fab(d).get("lineup", []):
        if l.get("tier") != "clear" or l.get("wkLost") is None: continue
        k = (l["s"], l["w"], l["m"]); best[k] = max(best.get(k, 0), l["wkLost"])
    out = []
    for (s, w, m), v in best.items():
        l = next(x for x in fab(d)["lineup"] if (x["s"], x["w"], x["m"]) == (s, w, m)); rid, opp = _ref(d, l)
        out.append(_c(round(v, 1), [N(m)], s, w, rid, opp, when=wk(s, w), holder_text=N(m)))
    return out
def _lsumm(d, key): return _sc([(y, m, v) for y, m, v in _summ_l(d, key)])
def _summ_l(d, key):
    out = []
    for y, ms in fab(d).get("summary", {}).items():
        if int(y) not in _fin(d): continue
        for m, v in ms.items():
            x = v.get("lineup") or {}
            if key in x: out.append((int(y), N(m), x[key]))
    return out
def season_bench(d): return _lsumm(d, "lost")
def season_wins_lost(d): return _lsumm(d, "winsLost")
def season_rumbles_lost(d): return _lsumm(d, "rumblesLost")
def season_brain(d):
    out = []
    for y, ms in fab(d).get("summary", {}).items():
        if int(y) in _fin(d):
            for m, v in ms.items():
                x = v.get("calls") or {}
                if "bigBrain" in x: out.append(_c(x["bigBrain"], [N(m)], int(y), when=y))
    return out

REG = {k: v for k, v in globals().items() if k in {
 "trade_net","trade_best_side","trade_worst_side","trade_value_gap","trade_blockbuster","trade_assets","trades_career","trades_partner","trades_league_season","trades_team_season",
 "fab_best_par","fab_best_fa","fab_bid","fab_worst","fab_value","fab_spent","fab_season_par","fab_season_net","fab_season_hits","fab_season_adds","fab_season_regret","fab_regret_drop",
 "sit_start_miss","sit_start_call","worst_week","season_bench","season_wins_lost","season_rumbles_lost","season_brain"}}
REG["trader_best"] = lambda d: trader_net(d, 1)
REG["trader_worst"] = lambda d: trader_net(d, -1)

FORMAT = {
 "trade_net": lambda v: f"+{v:.1f} PAR", "trade_best_side": lambda v: f"+{v:.1f} PAR", "trade_worst_side": lambda v: f"{v:.1f} PAR",
 "trade_value_gap": lambda v: f"{v:.1f} pts", "trade_blockbuster": lambda v: f"{v:.1f}", "trade_assets": lambda v: f"{v} players",
 "trades_career": lambda v: f"{v:.0f} trades", "trades_partner": lambda v: f"{v:.0f} trades", "trader_best": lambda v: f"{v:+.1f} PAR", "trader_worst": lambda v: f"{v:+.1f} PAR",
 "fab_best_par": lambda v: f"{v:+.1f} PAR", "fab_best_fa": lambda v: f"{v:+.1f} PAR", "fab_bid": lambda v: f"${v:.0f}", "fab_worst": lambda v: f"{v:+.1f} PAR",
 "fab_value": lambda v: f"{v:.2f} PAR per $", "fab_spent": lambda v: f"${v:.0f}", "fab_season_par": lambda v: f"{v:+.1f} PAR", "fab_season_net": lambda v: f"{v:+.1f} PAR",
 "fab_season_hits": lambda v: f"{v:.0f}", "fab_season_adds": lambda v: f"{v:.0f}", "fab_season_regret": lambda v: f"{v:.1f} PAR", "fab_regret_drop": lambda v: f"{v:.1f} PAR",
 "sit_start_miss": lambda v: f"{v:.1f} pts", "sit_start_call": lambda v: f"{v:.1f} pts", "worst_week": lambda v: f"{v:.1f} pts",
 "season_bench": lambda v: f"{v:.1f} pts", "season_wins_lost": lambda v: f"{v:.0f}", "season_rumbles_lost": lambda v: f"{v:.0f}", "season_brain": lambda v: f"{v:.0f}",
}
