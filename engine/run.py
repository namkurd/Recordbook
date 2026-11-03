"""Recompute every computed record, compare with data/records.json, and apply changes + changelog.
   python engine/run.py [--baseline] [--dry]
   Rules: a locked record is never touched (a 'would have changed' entry is logged instead); a better value takes over and the old
   one becomes `previous`; an equal value from a different game becomes a tie; Sleeper data wins over the hand-kept sheet."""
import json, os, re, sys, datetime
sys.path.insert(0, os.path.dirname(__file__))
from load import load
import metrics as M
import cards as CARDS
import seasons as SE
import market as MK
import facts as F
import moments as MO
import extras as EX

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RC_BASE = os.environ.get("RC_BASE", "https://namkurd.github.io/SleeperLiveRumbles/rumbles.html")
args = set(sys.argv[1:]); BASELINE = "--baseline" in args; DRY = "--dry" in args
TOL = {"game_pts_adj": 0.15, "league_week_adj": 0.15, "league_week": 0.05, "pf_plus": 0.05, "pa_plus": 0.05}

FORMATS = {**MK.FORMAT, **MO.FORMAT, **EX.FORMAT}
VERIFY = {"bench", "shot_league", "thu_league", "sat_pts", "mnf_overcome"}     # seeded records whose game is in the 2021+ data: Sleeper wins on a mismatch
NEW_MOMENTS = {"comeback", "blown_lead", "lead_changes", "upset_proj", "over_proj", "under_proj", "thu_pts", "mon_pts", "bench_season", "shot_week", "shot_season"}

def stored_num(r):
    v = r["value"]
    if r["metric"] in ("game_pts_adj", "league_week_adj") or (r["metric"] in ("game_pts", "league_week") and False):
        m = re.search(r"\(([\d.]+)%", v); return float(m.group(1)) if m else None
    if r["metric"] == "field_pct":
        m = re.search(r"\(([\d.]+)%", v); return float(m.group(1)) if m else None
    return r["value_num"]

def fmt(metric, c, d):
    v = c["value"]
    if c.get("display"): return c["display"]
    if metric in FORMATS: return FORMATS[metric](v)
    if metric in ("season_pf", "season_pa", "pts_missed_playoffs", "pts_made_playoffs"): return f"{v:.0f}"
    if metric in ("pf_plus", "pa_plus"): return f"{v:.1f}"
    if metric == "field_pct": return f'{c["detail"]} ({v}%)'
    if metric == "luck": return f"{v:+.1f}%"
    if metric == "rumble_pct": return f"{v:.0f}%"
    if metric == "multiple": return f"{v:.2f}x"
    if metric == "game_pts": return f'{v:.2f} ({100 * v / d.season_avg[c["season"]]:.0f}% of League Average)'
    if metric == "game_pts_adj": return f'{c["detail"].split()[0]} ({v:.2f}% of League Average)'
    if metric == "league_week": return f'{v:.1f} ({100 * v / d.season_avg[c["season"]]:.1f}% of League Average)'
    if metric == "league_week_adj": return f'{v:.1f}% of League Average'
    if metric in ("margin", "win_pts", "loss_pts"): return f"{v:.2f}"
    return str(int(v)) if float(v).is_integer() else str(v)

def when(metric, c):
    if c.get("when"): return c["when"]
    if metric in ("win_streak", "loss_streak", "top_streak", "bottom_streak"): return c["detail"]
    if c["week"] is not None: return f'Week {c["week"]} - {c["season"]}'
    return str(c["season"])

def holder_text(metric, c):
    if c.get("holder_text"): return c["holder_text"]
    m = re.search(r"over (\S+)", c["detail"])
    if metric in ("margin", "multiple", "win_pts") and m: return f'{c["holders"][0]} over {m.group(1)}'
    return " & ".join(c["holders"]) if c["holders"] != ["DTFClub"] else "DTFClub"

def replay(metric, c, cur):
    if not c.get("rid") or not c.get("opp_rid") or c["week"] is None: return None
    q = f'?wp={c["week"]}.{c["rid"]}.{c["opp_rid"]}' + (f'&season={c["season"]}' if c["season"] != cur else "")
    return {"season": c["season"], "week": c["week"], "rid": c["rid"], "opp_rid": c["opp_rid"], "url": RC_BASE + q}

def snapshot(r): return {k: r[k] for k in ("value", "holder", "when", "team", "evidence") if k in r}
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def main():
    d = M.Data(load()); d.done_all = {int(y) for y in d.raw["seasons"] if int(y) < d.cur}
    LEDGER = SE.make(d)
    for k, fn in LEDGER.items(): M.REGISTRY[k] = (lambda f: (lambda _d: f()))(fn)
    for k, fn in MK.REG.items(): M.REGISTRY[k] = fn
    FACTS, NAMES = (F.load_cache(), F.load_names()) if "--no-ingest" in args else F.ingest(d)
    for k, fn in MO.make(d, FACTS, NAMES).items(): M.REGISTRY[k] = (lambda f: (lambda _d: f()))(fn)
    EXR = EX.make(d)
    for k, fn in EXR.items(): M.REGISTRY[k] = (lambda f: (lambda _d: f()))(fn)
    OWNED = set(MK.REG) - {"trades_league_season", "trades_team_season"} | {"trader_best", "trader_worst"} | set(EXR) | NEW_MOMENTS
    doc = json.load(open(f"{ROOT}/data/records.json")); log = []
    for r in doc["records"]:
        if not r["metric"]: continue
        m = r["metric"]; cands = M.REGISTRY[m](d)
        if not cands: continue
        rev = r["direction"] == "max"
        cands.sort(key=lambda c: (c["value"], -c["season"], -(c["week"] or 0)), reverse=rev)
        best = cands[0]; sn = stored_num(r); tol = TOL.get(m, 0.006 if r["value_num"] and r["value_num"] > 500 else 0.0051)
        r["leaderboard"] = [{"value": fmt(m, c, d), "holder": holder_text(m, c), "when": when(m, c), "replay": replay(m, c, d.cur)} for c in cands[:5]]
        if m in OWNED:
            best = cands[0]; top_c = sorted([c for c in cands if abs(c["value"] - best["value"]) < 1e-9], key=lambda c: (c["season"], c["week"] or 0))
            new = {"value": fmt(m, best, d), "holder": "; ".join(holder_text(m, c) for c in top_c), "when": "; ".join(when(m, c) for c in top_c), "team": ""}
            hs = []
            for c in top_c: hs += [h for h in c["holders"] if h not in hs]
            r["detail"] = top_c[0].get("card"); r["replay"] = replay(m, top_c[0], d.cur)
            if r["locked"]: continue
            old = snapshot(r)
            if not r["value"]: kind, note = "auto:new", "Added to the book."
            elif abs((r["value_num"] or 0) - best["value"]) > 1e-9:
                worse = (best["value"] < r["value_num"]) if rev else (best["value"] > r["value_num"])
                kind, note = ("auto:reconcile", "Data changed; value recomputed.") if worse else ("auto:break", "Record broken.")
            elif hs != r["holders"] or new["when"] != r["when"]:
                kind, note = "auto:tie" if set(hs) > set(r["holders"]) else "auto:reconcile", "Holders updated."
            else:
                kind = None
                if new["holder"] != r["holder"]: r["holder"] = new["holder"]      # wording only: no change-log entry
            if kind:
                if kind == "auto:break": r["previous"] = dict(old, replaced_on=now[:10], replaced_by=new["holder"])
                r.update(new, value_num=best["value"], holders=hs, ties=[], source="computed", verified=True, updated=now[:10], league_level=hs == ["DTFClub"])
                log.append({"ts": now, "record": r["id"], "name": r["name"], "cause": kind, "old": old if r["value"] and old.get("value") else None, "new": new, "note": note})
            continue
        if sn is None: continue
        if m in SE.COMPLETE and not r["locked"] and abs(best["value"] - r["value_num"]) < 1e-9:
            top_c = sorted([c for c in cands if c["value"] == best["value"]], key=lambda c: (c["season"], c["holders"][0]))
            want = {h for c in top_c for h in c["holders"]}; have = set(r["holders"]) | {t["holder"] for t in r["ties"]}
            if want != have:
                old = snapshot(r); new = {"value": r["value"], "holder": ";".join(h for c in top_c for h in c["holders"]), "when": "; ".join(when(m, c) for c in top_c), "team": ""}
                r["previous"] = dict(old, replaced_on=now[:10], replaced_by=new["holder"], reconciled=True)
                r.update(new, holders=[h for c in top_c for h in c["holders"]], ties=[], source="computed", verified=True, updated=now[:10])
                log.append({"ts": now, "record": r["id"], "name": r["name"], "cause": "auto:reconcile", "old": old, "new": new,
                            "note": "Season ledger from Sleeper data lists different holders than the sheet; data wins."})
                continue
        better = best["value"] > sn + tol + (0.5 if m in ("season_pf", "season_pa", "pts_missed_playoffs", "pts_made_playoffs") else 0) if rev else best["value"] < sn - tol - (0.5 if m in ("season_pf", "season_pa", "pts_missed_playoffs", "pts_made_playoffs") else 0)
        slack = tol + (0.5 if m in ("season_pf", "season_pa", "pts_missed_playoffs", "pts_made_playoffs") else 0)
        same = abs(best["value"] - sn) <= slack
        if better:
            new = {"value": fmt(m, best, d), "holder": holder_text(m, best), "when": when(m, best), "team": ""}
            if r["locked"]:
                log.append({"ts": now, "record": r["id"], "name": r["name"], "cause": "auto:blocked", "new": new, "note": "Record is locked; engine found a better mark and did not apply it."}); continue
            old = snapshot(r)
            r["previous"] = dict(old, replaced_on=now[:10], replaced_by=new["holder"], reconciled=BASELINE)
            r.update(new, value_num=best["value"], holders=best["holders"], source="computed", evidence=[], ties=[], replay=replay(m, best, d.cur), detail=best.get("card"),
                     league_level=best["holders"] == ["DTFClub"], status="active", updated=now[:10])
            log.append({"ts": now, "record": r["id"], "name": r["name"], "cause": "auto:reconcile" if BASELINE else "auto:break", "old": old, "new": new,
                        "note": "Sleeper data differs from the hand-kept sheet; data wins." if BASELINE else "Record broken."})
        elif m in VERIFY and not r["locked"] and not same and (lambda ys: ys and min(ys) >= 2021)([int(x) for x in re.findall(r"\b(20\d\d)\b", r["when"])]):
            new = {"value": fmt(m, best, d), "holder": holder_text(m, best), "when": when(m, best), "team": ""}; old = snapshot(r)
            r["previous"] = dict(old, replaced_on=now[:10], replaced_by=new["holder"], reconciled=True)
            r.update(new, value_num=best["value"], holders=best["holders"], ties=[], source="computed", verified=True, evidence=[], replay=replay(m, best, d.cur), detail=best.get("card"), updated=now[:10])
            log.append({"ts": now, "record": r["id"], "name": r["name"], "cause": "auto:reconcile", "old": old, "new": new, "note": "Sleeper data for this same game differs from the sheet; data wins."})
        elif same:
            hit = [c for c in cands if abs(c["value"] - sn) <= slack]
            if r["source"] == "seeded": r["source"] = "computed"; r["verified"] = True
            mine = [c for c in hit if set(c["holders"]) & set(r["holders"])] or hit[:1]
            if not r.get("replay"): r["replay"] = replay(m, mine[0], d.cur)
            if mine[0].get("card"): r["detail"] = mine[0]["card"]
            known = {r["holder"]} | set(r["holders"]) | {t["holder"] for t in r["ties"]}
            for c in hit:
                h = holder_text(m, c)
                if len(r["ties"]) >= 4: break
                if all(x not in known for x in c["holders"]) and h not in known:
                    t = {"holder": h, "when": when(m, c), "replay": replay(m, c, d.cur)}
                    r["ties"].append(t); known.add(h); known.update(c["holders"])
                    log.append({"ts": now, "record": r["id"], "name": r["name"], "cause": "auto:tie", "new": t, "note": "Tied the record."})
    n_cards = sum(1 for r in doc["records"] if CARDS.attach(d, r))
    print(n_cards, "record(s) with a Rumble Card")
    if not DRY:
        json.dump(doc, open(f"{ROOT}/data/records.json", "w"), indent=1, ensure_ascii=False)
        with open(f"{ROOT}/data/changelog.jsonl", "a") as f:
            for e in log: f.write(json.dumps(e, ensure_ascii=False) + "\n")
    for e in log: print(e["cause"], "|", e["name"], "|", (e.get("old") or {}).get("value"), (e.get("old") or {}).get("holder"), "->", e["new"].get("value"), e["new"].get("holder"), e["new"].get("when"))
    print(len(log), "change(s)", "(dry run)" if DRY else "")
main()
