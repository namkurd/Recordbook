"""Records built from Sleeper's own transaction list (2021+): every trade (FAB-only ones too, with the FAB that moved) and every waiver claim,
including the failed claims with their bids.  Week = Sleeper's `leg` for the transaction."""
import collections
from metrics import norm

def N(x, y=None): return {"Rohaan": "Haan"}.get(norm(x, y), norm(x, y))

import datetime as dt
KICKOFF = {2021: (9, 9), 2022: (9, 8), 2023: (9, 7), 2024: (9, 5), 2025: (9, 4), 2026: (9, 10)}     # Thursday of NFL week 1

def fweek(y, ts):
    """The fantasy week a transaction belongs to, the way the sheet counts it: a claim or trade made after Monday night is for the *next* week's games
    (Sleeper's own `leg` calls it the week just played); anything before the season is week 1."""
    m, dd = KICKOFF.get(y, (9, 8))
    tue = dt.datetime(y, m, dd, 5, 0, tzinfo=dt.timezone.utc) - dt.timedelta(days=2)       # 1 a.m. ET Tuesday before kickoff
    return max(1, min(18, int((ts / 1000 - tue.timestamp()) // (7 * 86400)) + 1))

def make(d):
    R = {}; T = d.raw.get("txns") or {}
    names = {y: {rid: N(n, y) for rid, n in m.items()} for y, m in d.raw["rosters"].items()}
    def who(y, rid): return names.get(y, {}).get(rid, f"Roster {rid}")
    def wk(y, w): return f"Week {w} - {y}"
    def card(title, head, rows): return {"kind": "facts", "title": title, "blocks": [{"head": head, "chip": None, "rows": rows}]}
    def W(y, t): return fweek(y, t["c"] or t["u"] or 0)
    def trades(y): return [t for t in T.get(y, []) if t["ty"] == "trade" and t["st"] == "complete"]
    def done(y): return y < d.cur
    # ---- trades ----
    def trade_fab():
        out = []
        for y in T:
            for t in trades(y):
                tot = sum(w[2] for w in t["fab"])
                if tot:
                    a, b = (who(y, r) for r in t["r"][:2]); moves = ", ".join(f"{who(y, s)} to {who(y, r)} ${m}" for s, r, m in t["fab"])
                    out.append({"value": tot, "holders": [a, b], "season": y, "week": W(y, t), "rid": None, "opp_rid": None, "detail": "", "when": wk(y, W(y, t)), "holder_text": f"{a} & {b}",
                                "card": card(f"Trade · Week {W(y, t)}, {y}", f"{a} & {b}", [["FAB moved", f"${tot}"], ["Who sent what", moves]])})
        return out
    def trades_24h():
        out = []
        for y in T:
            by = collections.defaultdict(list)
            for t in trades(y):
                for r in t["r"]: by[r].append(t)
            for r, ts in by.items():
                ts.sort(key=lambda t: t["c"])
                last = {}
                for i, t0 in enumerate(ts):
                    win = [t for t in ts[i:] if t["c"] - t0["c"] <= 86400000]
                    if len(win) >= 2 and not (len(win) in last and t0["c"] - last[len(win)] <= 86400000):
                        last[len(win)] = t0["c"]
                        out.append({"value": len(win), "holders": [who(y, r)], "season": y, "week": W(y, t0), "rid": None, "opp_rid": None, "detail": "", "when": wk(y, W(y, t0)), "holder_text": who(y, r),
                                    "card": card(f"{len(win)} trades in 24 hours · {y}", who(y, r), [[f"Week {W(y, t)}", " & ".join(who(y, x) for x in t["r"] if x != r) or "-"] for t in win])})
        return out
    def per_season_league():
        return [{"value": len(trades(y)), "holders": ["DTFClub"], "season": y, "week": None, "rid": None, "opp_rid": None, "detail": "", "when": str(y)} for y in T if done(y)]
    def per_season_team():
        out = []
        for y in T:
            if not done(y): continue
            c = collections.Counter(r for t in trades(y) for r in t["r"])
            out += [{"value": n, "holders": [who(y, r)], "season": y, "week": None, "rid": None, "opp_rid": None, "detail": "", "when": str(y)} for r, n in c.items()]
        return out
    # ---- FAB claims ----
    def contested():
        """(winning claim, [bids of the claims it beat]) for every player claimed by more than one team in a week; a claim that failed only because of the
        roster limit or the budget was no competing bid."""
        out = []
        for y in T:
            by = collections.defaultdict(list)
            for t in T[y]:
                if t["ty"] != "waiver" or t["bid"] is None or not t["adds"]: continue
                by[(t["leg"], t["adds"][0])].append(t)
            for (leg, pid), c in by.items():
                win = [t for t in c if t["st"] == "complete"]
                if not win: continue
                beat = [t["bid"] for t in c if t["st"] == "failed" and (t.get("n") or "").startswith("This player was claimed")]
                if beat: out.append((y, fweek(y, win[0]["c"] or win[0]["u"] or 0), pid, win[0], beat))
        return out
    pname = {}
    for a in ((d.raw.get("fab") or {}).get("adds") or []): pname[str(a["pid"])] = a["pl"]
    def pl(pid): return pname.get(str(pid), f"player {pid}")
    def claim_card(y, leg, pid, t, beat):
        return card(f"Claim · Week {leg}, {y}", who(y, t["r"][0]), [["Player", pl(pid)], ["Winning bid", f"${t['bid']}"], ["Next highest bid", f"${max(beat)}"], ["Teams beaten", str(len(beat))]])
    def overbid():
        return [{"value": t["bid"] - max(beat), "holders": [who(y, t["r"][0])], "season": y, "week": leg, "rid": None, "opp_rid": None, "detail": "", "when": wk(y, leg),
                 "holder_text": f"{who(y, t['r'][0])} - {pl(pid)}", "display": f"${t['bid'] - max(beat)} (${t['bid']} total bid)", "card": claim_card(y, leg, pid, t, beat)} for y, leg, pid, t, beat in contested() if max(beat) > 0 or t["bid"] > 0]
    def bestbid():
        out = []
        for y, leg, pid, t, beat in contested():
            nxt = max(beat)
            if t["bid"] < 10 or nxt <= 0: continue
            pct = 100 * (t["bid"] - nxt) / nxt
            out.append({"value": round(pct, 1) - t["bid"] * 1e-6, "holders": [who(y, t["r"][0])], "season": y, "week": leg, "rid": None, "opp_rid": None, "detail": "", "when": wk(y, leg),
                        "holder_text": f"{who(y, t['r'][0])} - {pl(pid)}", "display": f"{max(0, pct):.0f}%; ${t['bid']}", "card": claim_card(y, leg, pid, t, beat)})
        return out
    def fab_owned():
        out = []
        for y in T:
            ev = []
            for t in T[y]:
                if t["st"] != "complete": continue
                if t["ty"] == "waiver" and t["bid"]: ev.append((t["u"] or t["c"], t["r"][0], -t["bid"], 0))
                if t["ty"] == "trade":
                    for s, r, m in t["fab"]: ev += [(t["u"] or t["c"], s, -m, 0), (t["u"] or t["c"], r, m, 0)]
            ev.sort(); bal = collections.defaultdict(lambda: 200); best = {}
            for ts, r, dv, leg in ev:
                bal[r] += dv
                if bal[r] > best.get(r, (200,))[0]: best[r] = (bal[r], fweek(y, ts))
            for r, (v, leg) in best.items():
                out.append({"value": v, "holders": [who(y, r)], "season": y, "week": leg, "rid": None, "opp_rid": None, "detail": "", "when": wk(y, leg), "holder_text": who(y, r)})
        return out
    R.update(trade_fab=trade_fab, trades_24h=trades_24h, trades_league_all=per_season_league, trades_team_all=per_season_team,
             fab_overbid=overbid, fab_bestbid=bestbid, fab_owned=fab_owned)
    # ---- total wins incl. playoffs (every season) ----
    def total_wins():
        seen = set(); pw = collections.Counter()
        for p in d.raw["playoffs"]:
            k = (p["season"], p["week"], p["winner"])
            if k in seen: continue
            seen.add(k); pw[(p["season"], norm(p["winner"]))] += 1
        out = []
        for r in d.srows:
            if r["season"] not in d.done_all: continue
            n = r["w"] + pw[(r["season"], r["m"])]
            out.append({"value": n, "holders": [r["m"]], "season": r["season"], "week": None, "rid": None, "opp_rid": None, "detail": "", "when": str(r["season"]),
                        "card": card(f"Wins · {r['season']}", r["m"], [["Regular season", str(r["w"])], ["Playoffs", str(pw[(r["season"], r["m"])])], ["Total", str(n)]])})
        return out
    R["total_wins"] = total_wins
    return R

FORMAT = {"trade_fab": lambda v: f"${v:.0f}", "trades_24h": lambda v: f"{v:.0f}", "trades_league_all": lambda v: f"{v:.0f}", "trades_team_all": lambda v: f"{v:.0f}",
          "fab_owned": lambda v: f"${v:.0f}", "total_wins": lambda v: f"{v:.0f}"}
