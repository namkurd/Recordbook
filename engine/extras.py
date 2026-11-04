"""Rivalries, playoff/championship records, draft & auction records, and trade/FAB records tied to champions and Sackos."""
import collections, itertools, os, re
from urllib.parse import quote
from metrics import norm
import market as MK
import cards as C

ALIAS = {"Rohaan": "Haan"}
AUCTION = os.environ.get("AUCTION_BASE", "https://namkurd.github.io/SleeperAuction/")
def alinks(season, page=None):
    """Links into the SleeperAuction tool: the season's draft board (every manager's sheet) and, optionally, a player or manager page."""
    out = {"sheet": {"label": f"{season} auction sheet", "url": f"{AUCTION}#drafts/{season}"}}
    if page: out["page"] = page
    return out
def N(x): return ALIAS.get(norm(x), norm(x))
def wk(s, w): return f"Week {w} - {s}"
def _c(value, holders, s, w=None, rid=None, opp=None, when=None, ht=None, card=None, display=None):
    return {"value": value, "holders": holders if isinstance(holders, list) else [holders], "season": s, "week": w, "rid": rid, "opp_rid": opp,
            "detail": "", "when": when, "holder_text": ht, "card": card, "display": display}
def fact(title, head, rows, chip=None): return {"kind": "facts", "title": title, "blocks": [{"head": head, "chip": chip, "rows": rows}]}

def make(d):
    R = {}; L = getattr(d, "_ledger", {}) or {}
    def rid_of(season, name):
        for rid, n in (d.raw["rosters"].get(season) or {}).items():
            if N(norm(n, season)) == N(name): return rid
        return None
    def refs(season, a, b): return (rid_of(season, a), rid_of(season, b)) if season >= 2021 else (None, None)
    play = d.raw["playoffs"]; seasons = {int(y): v for y, v in d.raw["seasons"].items()}
    fabs = ((d.raw.get("fab") or {}).get("seasons")) or []
    # ---------------- rivalries (2021+ games; weekly archive) ----------------
    pair = collections.defaultdict(list)
    for g in sorted(d.games, key=lambda g: (g["season"], g["week"])):
        if g["opp"] and g["m"] < g["opp"] and (g["reg"] or g["week"] >= 16):
            res = 1 if g["win"] else (-1 if g["pts"] < g["opp_pts"] else 0)
            pair[(g["m"], g["opp"])].append((g["season"], g["week"], res))
    def streaks():
        out = []
        for (a, b), L_ in pair.items():
            for who, sign in ((a, 1), (b, -1)):
                best = []; cur = []
                for x in L_:
                    if x[2] * sign == 1: cur.append(x)
                    else:
                        if len(cur) > len(best): best = cur
                        cur = []
                if len(cur) > len(best): best = cur
                if best:
                    o = b if who == a else a
                    out.append(_c(len(best), [who], best[0][0], best[0][1], when=f"Week {best[0][1]} {best[0][0]} - Week {best[-1][1]} {best[-1][0]}", ht=f"{who} over {o}"))
        return out
    R["rivalry_streak"] = streaks
    R["rivalry_meetings"] = lambda: [_c(len(v), [a, b], 2021, when="2021-", ht=f"{a} & {b}") for (a, b), v in pair.items()]
    def onesided():
        out = []
        for (a, b), v in pair.items():
            w = sum(1 for x in v if x[2] == 1); l = sum(1 for x in v if x[2] == -1)
            if len(v) < 6: continue
            win, lose, wins, losses = (a, b, w, l) if w >= l else (b, a, l, w)
            out.append(_c(round(100 * wins / (wins + losses), 1) + wins / 1000 if wins + losses else 0, [win], 2021, when="2021-", ht=f"{win} vs {lose}", display=f"{wins}-{losses}"))
        return out
    R["rivalry_onesided"] = onesided
    def po_meetings():
        seen = set(); cnt = collections.Counter()
        for p in play:
            k = (p["season"], p["week"], N(p["winner"]), N(p["loser"]))
            if k in seen: continue
            seen.add(k); cnt[tuple(sorted((N(p["winner"]), N(p["loser"]))))] += 1
        return [_c(v, list(k), 2013, when="2013-", ht=f"{k[0]} & {k[1]}") for k, v in cnt.items()]
    R["playoff_meetings"] = po_meetings
    # ---------------- playoffs & titles ----------------
    def lowest_seed():
        out = []
        for s in fabs:
            if not s.get("finished"): continue
            for t in s["teams"]:
                if t.get("finish") == "Champion" and t.get("seed"): out.append(_c(t["seed"], [N(t["m"])], s["s"], when=str(s["s"]), display=f'#{t["seed"]} seed'))
        return out
    R["lowest_seed_champ"] = lowest_seed
    def hi_playoff():
        out = []
        for p in play:
            for who, sc, opp, sc2 in ((p["winner"], p["winner_score"], p["loser"], p["loser_score"]), (p["loser"], p["loser_score"], p["winner"], p["winner_score"])):
                if sc: out.append(_c(sc, [N(who)], p["season"], p["week"], *refs(p["season"], who, opp), when=wk(p["season"], p["week"]), ht=f"{N(who)} ({'won' if sc > sc2 else 'lost'} vs {N(opp)})"))
        return out
    R["highest_playoff_score"] = hi_playoff
    def finals(sign):
        out = []; last = {}
        for p in play: last[p["season"]] = max(last.get(p["season"], 0), p["week"])
        for p in play:
            if p["week"] == last[p["season"]] and p.get("winner_score") and p.get("loser_score"):
                out.append(_c(round(p["winner_score"] - p["loser_score"], 1), [N(p["winner"])], p["season"], p["week"], *refs(p["season"], p["winner"], p["loser"]), when=f'{p["season"]} final', ht=f'{N(p["winner"])} over {N(p["loser"])}',
                              display=f'{p["winner_score"]:.1f} to {p["loser_score"]:.1f}'))
        return out
    R["closest_final"] = lambda: finals(1); R["biggest_final"] = lambda: finals(1)
    def pwins():
        seen = set(); cnt = collections.Counter(); yrs = collections.defaultdict(set)
        for p in play:
            k = (p["season"], p["week"], N(p["winner"]))
            if k in seen: continue
            seen.add(k); cnt[N(p["winner"])] += 1; yrs[N(p["winner"])].add(p["season"])
        return [_c(v, [m], max(yrs[m]), when=f"{min(yrs[m])}-{max(yrs[m])}") for m, v in cnt.items()]
    R["playoff_wins"] = pwins
    def no_title():
        c = collections.defaultdict(list); t = collections.Counter()
        for y, ms in L.items():
            for m, fl in ms.items():
                if "playoff" in fl: c[m].append(y)
                if "champ" in fl: t[m] += 1
        return [_c(len(v), [m], v[-1], when="/".join("'%02d" % (y % 100) for y in sorted(v))) for m, v in c.items() if not t[m]]
    R["playoffs_no_title"] = no_title
    def wins_rows():
        part = collections.defaultdict(set)
        for p in play: part[p["season"]] |= {N(p["winner"]), N(p["loser"])}
        return part
    def fewest_wins_in():
        part = wins_rows(); out = []
        for y, sv in seasons.items():
            if y >= d.cur or y not in part: continue
            for r in sv["rows"]:
                if N(r["name"]) in part[y]: out.append(_c(r["w"], [N(r["name"])], y, when=str(y), display=f'{r["w"]}-{r["l"]}'))
        return out
    def most_wins_out():
        part = wins_rows(); out = []
        for y, sv in seasons.items():
            if y >= d.cur or y not in part: continue
            for r in sv["rows"]:
                if N(r["name"]) not in part[y]: out.append(_c(r["w"], [N(r["name"])], y, when=str(y), display=f'{r["w"]}-{r["l"]}'))
        return out
    R["fewest_wins_playoffs"] = fewest_wins_in; R["most_wins_miss"] = most_wins_out
    def ranks():
        r = {}
        for y, sv in seasons.items():
            if y >= d.cur and not any(s["s"] == y and s.get("finished") for s in fabs): continue
            for i, row in enumerate(sv["rows"], 1): r[(y, N(row["name"]))] = i
        return r
    def jump(sign):
        rk = ranks(); out = []
        for (y, m), v in rk.items():
            p = rk.get((y - 1, m))
            if p: out.append(_c(sign * (p - v), [m], y, when=f"{y - 1} to {y}", display=f"{p}th to {v}th".replace("1th", "1st").replace("2th", "2nd").replace("3th", "3rd")))
        return out
    R["standings_jump"] = lambda: jump(1); R["standings_drop"] = lambda: jump(-1)
    # ---------------- draft & auction ----------------
    picks = d.raw.get("picks") or []
    def P():
        for x in picks:
            try: price = float(x["price"]); s = int(x["season"])
            except Exception: continue
            yield x, s, price, N(x["manager"])
    def pcard(x, s, price, m):
        rk = f'{x["pos_rank"]} of {x["pos_n"]}' if x.get("pos_rank") else "not yet ranked"
        return fact(f'Auction · {s}', m, [["Player", f'{x["player"]} ({x["position"]})'], ["Price", f"${price:.0f}"], ["Finish at position", rk], ["Points", x.get("pts") or "–"], ["Games", x.get("games") or "–"]])
    def pc(val, x, s, price, m, disp=None):
        c = _c(val, [m], s, when=str(s), ht=f'{m} — {x["player"]}', card=pcard(x, s, price, m), display=disp)
        pk = x.get("player_key")
        c["links"] = alinks(s, {"label": f'{x["player"]} in the Auction tool', "url": f"{AUCTION}#players/{quote(pk, safe='')}"} if pk else None)
        return c
    R["auction_price"] = lambda: [pc(price, x, s, price, m) for x, s, price, m in P() if x["position"] not in ("K", "DEF")]
    for pos in ("QB", "RB", "WR", "TE"):
        R[f"auction_{pos.lower()}"] = (lambda pos: lambda: [pc(price, x, s, price, m) for x, s, price, m in P() if x["position"] == pos])(pos)
    def graded(x): return bool(x.get("pos_rank")) and bool(x.get("pos_n"))
    def bust():
        return [pc(price, x, s, price, m) for x, s, price, m in P() if graded(x) and x["position"] in ("QB", "RB", "WR", "TE") and float(x["games"] or 0) >= 8 and float(x["pos_rank"]) > float(x["pos_n"]) / 2]
    def injury():
        return [pc(price, x, s, price, m) for x, s, price, m in P() if graded(x) and x["position"] in ("QB", "RB", "WR", "TE") and float(x["games"] or 0) <= 7 and price >= 10]
    def steal():
        return [pc(price - float(x["pts"] or 0) / 1e5, x, s, price, m, f"${price:.0f}") for x, s, price, m in P() if graded(x) and x["position"] in ("QB", "RB", "WR", "TE") and float(x["pos_rank"]) <= 3]
    R["auction_bust"] = bust; R["auction_injury"] = injury; R["auction_steal"] = steal
    def spend():
        a = collections.defaultdict(float)
        for x, s, price, m in P(): a[(s, m, x["position"])] += price
        out = []
        for (s, m, pos), v in a.items():
            if pos not in ("QB", "RB", "WR", "TE"): continue
            c = _c(v, [m], s, when=f"{s} {pos}", ht=f"{m} — {pos}")
            c["links"] = alinks(s, {"label": f"{m}'s spending in the Auction tool", "url": f"{AUCTION}#managers/{quote(m, safe='')}"})
            out.append(c)
        return out
    R["auction_pos_spend"] = spend
    # ---------------- trades & FAB tied to champions / Sackos ----------------
    def season_flag(y, m, flag): return flag in (L.get(y, {}).get(m, set()))
    def champ_trade():
        out = []
        for t in MK.trades(d):
            for who, other, par in MK._sides(t):
                if par is not None and season_flag(t["s"], who, "champ"): out.append(MK._tc(round(par, 1), t, who, other))
        return out
    def sacko_trade():
        out = []
        for t in MK.trades(d):
            for who, other, par in MK._sides(t):
                if par is not None and season_flag(t["s"], who, "sacko"): out.append(MK._c(round(par, 1), [who], t["s"], t["w"], when=wk(t["s"], t["w"]), holder_text=f"{who} (vs {other})", card=MK.trade_card(t, other)))
        return out
    R["trade_champ_best"] = lambda: MK.add_links(champ_trade(), "trade"); R["trade_champ_worst"] = lambda: MK.add_links(champ_trade(), "trade"); R["trade_sacko_worst"] = lambda: MK.add_links(sacko_trade(), "trade")
    def champ_fab():
        out = []
        for s in fabs:
            if not s.get("finished"): continue
            for t in s["teams"]:
                if t.get("finish") == "Champion": out.append(_c(t["bids"], [N(t["m"])], s["s"], when=str(s["s"])))
        return out
    R["fab_champ_spent"] = lambda: MK.add_links(champ_fab(), "fab"); R["fab_champ_least"] = lambda: MK.add_links(champ_fab(), "fab")
    return R

def _ord(n): return f"{n}th"
FORMAT = {
 "rivalry_streak": lambda v: f"{v:.0f} straight", "rivalry_meetings": lambda v: f"{v:.0f} games", "rivalry_onesided": lambda v: f"{v:.1f}%", "playoff_meetings": lambda v: f"{v:.0f} meetings",
 "lowest_seed_champ": lambda v: f"#{v:.0f} seed", "highest_playoff_score": lambda v: f"{v:.2f}", "closest_final": lambda v: f"{v:.1f} pts", "biggest_final": lambda v: f"{v:.1f} pts",
 "playoff_wins": lambda v: f"{v:.0f} wins", "playoffs_no_title": lambda v: f"{v:.0f} trips", "fewest_wins_playoffs": lambda v: f"{v:.0f} wins", "most_wins_miss": lambda v: f"{v:.0f} wins",
 "standings_jump": lambda v: f"+{v:.0f} spots", "standings_drop": lambda v: f"-{v:.0f} spots",
 "auction_price": lambda v: f"${v:.0f}", "auction_qb": lambda v: f"${v:.0f}", "auction_rb": lambda v: f"${v:.0f}", "auction_wr": lambda v: f"${v:.0f}", "auction_te": lambda v: f"${v:.0f}",
 "auction_bust": lambda v: f"${v:.0f}", "auction_injury": lambda v: f"${v:.0f}", "auction_steal": lambda v: f"${round(v):.0f}", "auction_pos_spend": lambda v: f"${v:.0f}",
 "trade_champ_best": lambda v: f"{v:+.1f} PAR", "trade_champ_worst": lambda v: f"{v:.1f} PAR", "trade_sacko_worst": lambda v: f"{v:.1f} PAR", "fab_champ_spent": lambda v: f"${v:.0f}", "fab_champ_least": lambda v: f"${v:.0f}",
}
