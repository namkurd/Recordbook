"""One-time: turn the hand-kept sheet (tools/sheet.psv) into data/records.json. Re-running overwrites; never run after go-live."""
import json, re, sys
if "--force" not in sys.argv: sys.exit("seed.py overwrites data/records.json (and your edits). Re-run with --force only for a fresh start.")

CATS = ["Seasons & Playoffs", "Team Seasons", "Games & Weeks", "Projections & NFL Clock", "Trades & FAB"]
# row order in the sheet is the category order (counts: 18, 21, 18, 6, 13)
SIZES = [18, 21, 18, 6, 13]

# sheet name -> (metric key engine computes, direction, unit)
METRIC = {
 "Most Championships": ("titles", "max"),
 "Most Championship Appearances": ("finals", "max"),
 "Most Championship Losses": ("final_losses", "max"),
 "Most Consecutive Championship Appearances": ("final_streak", "max"),
 "Most Playoff Appearances": ("playoff_apps", "max"),
 "Most Consecutive Playoff Appearances": ("playoff_streak", "max"),
 "Longest Playoff Drought": ("drought", "max"),
 "Most Sackos": ("sackos", "max"),
 "Most #1 Seeds": ("seed1", "max"),
 "Most Top Scoring Seasons": ("top_pf_seasons", "max"),
 "Most Bottom Scoring Seasons": ("bottom_pf_seasons", "max"),
 "Most Highest Points Against Seasons": ("high_pa_seasons", "max"),
 "Most Consecutive .500 or Better Seasons": ("winning_streak_seasons", "max"),
 "Most Consecutive Losing Seasons": ("losing_streak_seasons", "max"),
 "Most Points (Season)": ("season_pf", "max"), "Most Points Against (Season)": ("season_pa", "max"),
 "Fewest Points (Season)": ("season_pf", "min"),
 "Most Dominant Offensive Season": ("pf_plus", "max"), "Most Futile Offensive Season": ("pf_plus", "min"),
 "Most Cursed Defensive Season": ("pa_plus", "max"), "Most Dominant Defensive Season": ("pa_plus", "min"),
 "Best Record vs. Field": ("field_pct", "max"), "Worst Record vs. Field": ("field_pct", "min"),
 "Total Wins (Regular Season)": ("reg_wins", "max"),
 "Luckiest Season (H2H% - Field%)": ("luck", "max"), "Unluckiest Season (H2H% - Field%)": ("luck", "min"),
 "Most Composite Wins in a Season": ("composite", "max"), "Fewest Composite Wins in a Season": ("composite", "min"),
 "Best Rumble %": ("rumble_pct", "max"), "Worst Rumble %": ("rumble_pct", "min"),
 "Most Top Scoring Weeks (Season)": ("top_weeks", "max"), "Most Bottom Scoring Weeks (Season)": ("bottom_weeks", "max"),
 "Most Consecutive Top Scoring Weeks": ("top_streak", "max"), "Most Consecutive Bottom Scoring Weeks": ("bottom_streak", "max"),
 "Winning Streak": ("win_streak", "max"), "Losing Streak": ("loss_streak", "max"),
 "Most Points to Not Make Playoffs": ("pts_missed_playoffs", "max"), "Fewest Points to Make Playoffs": ("pts_made_playoffs", "min"),
 "Most Points (Game)": ("game_pts", "max"), "Fewest Points (Game)": ("game_pts", "min"),
 "Most Points (Game, Era Adjusted)": ("game_pts_adj", "max"), "Fewest Points (Game, Era Adjusted)": ("game_pts_adj", "min"),
 "Largest Margin of Victory": ("margin", "max"), "Smallest Margin of Victory": ("margin", "min"),
 "Largest Multiple of Opponents Score": ("multiple", "max"),
 "Fewest Points in a Win": ("win_pts", "min"), "Most Points in a Loss": ("loss_pts", "max"),
 "Highest Scoring Week (League)": ("league_week", "max"), "Lowest Scoring Week (League)": ("league_week", "min"),
 "Highest Scoring Week (League, Era Adjusted)": ("league_week_adj", "max"), "Lowest Scoring Week (League, Era Adjusted)": ("league_week_adj", "min"),
}
ERA_PAIRS = {"Most Points (Game)": "Most Points (Game, Era Adjusted)", "Fewest Points (Game)": "Fewest Points (Game, Era Adjusted)",
 "Highest Scoring Week (League)": "Highest Scoring Week (League, Era Adjusted)", "Lowest Scoring Week (League)": "Lowest Scoring Week (League, Era Adjusted)"}
# rows whose raw count/total depends on 10 vs 12 teams or the length of the season
SIZE_SENSITIVE = re.compile(r"Top Scoring Weeks|Bottom Scoring Weeks|Composite|Trades|Teams to Make|FAB owned|Top Scoring Seasons|Bottom Scoring Seasons|#1 Seeds|Playoff Appearances|Points \(Season\)|Points Against \(Season\)|Fewest Points \(Season\)|Winning Streak|Losing Streak|Total Wins")
NEEDS_DEFINITION = {}
DEFINITION = {
 "Most Composite Wins in a Season": "Each week a manager earns a win for winning their matchup and another for scoring in the top half of all scores that week (top 5 of 10 teams, top 6 of 12).",
 "Fewest Composite Wins in a Season": "Each week a manager earns a win for winning their matchup and another for scoring in the top half of all scores that week.",
 "Most Shotguns in a Season (League)": "A score of 0 or less from a non-defense starter who was not ruled out before the 2nd half, or ruled out but didn't play in the 2nd half.",
 "Most Dominant Offensive Season": "PF+: a team's points scored as a % of that season's league average (100 = average), like OPS+.",
 "Most Futile Offensive Season": "PF+: a team's points scored as a % of that season's league average (100 = average).",
 "Most Dominant Defensive Season": "PA+: points against as a % of that season's league average. Lower is better.",
 "Most Cursed Defensive Season": "PA+: points against as a % of that season's league average. Higher is worse.",
 "Most Points (Game, Era Adjusted)": "Score as a % of that season's average team score.", "Fewest Points (Game, Era Adjusted)": "Score as a % of that season's average team score.",
 "Highest Scoring Week (League, Era Adjusted)": "The week's average team score as a % of that season's average.", "Lowest Scoring Week (League, Era Adjusted)": "The week's average team score as a % of that season's average.",
 "Best Rumble %": "Rumbles earned out of the maximum possible in the regular season (9 per matchup win + 1 per team outscored each week).",
 "Luckiest Season (H2H% - Field%)": "Head-to-head win % minus record-vs-the-field %.",
}
SOURCE_HINT = {  # rows the engine can't compute yet and why
 "Most Points on Bench": "Needs per-player starter/bench points (Sleeper matchups).", "Most Points on a Saturday": "Needs NFL kickoff times.",
 "Highest Projected Point Total": "Needs stored projection snapshots.", "Highest Projected Point Total (Era Adjusted)": "Needs stored projection snapshots.",
 "Most 0.0's in a Win": "Needs per-player points.", "Highest % Points Scored by 1 Player": "Needs per-player points.",
 "Fewest Total League Points on Thursday Night": "Needs NFL kickoff times + per-player points.", "Largest Monday Night Deficit Overcome": "Candidate for Rumble Central wp_timeline.",
 "Fastest Trade Acceptance to Player Start": "Needs trade timestamps + kickoff times.",
 "Most Shotguns in a Season (League)": "Needs per-player points plus game-day inactive/ruled-out status for every starter.",
}

def slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
def num(s):
    m = re.search(r"(-?)\$?(\d[\d,]*\.?\d*)", s.replace("+", ""))
    return float(m.group(1) + m.group(2).replace(",", "")) if m else None

rows = [l.rstrip("\n").split("|") for l in open("tools/sheet.psv") if l.strip()]
assert len(rows) == sum(SIZES), len(rows)
recs, i = [], 0
for cat, n in zip(CATS, SIZES):
    for _ in range(n):
        name, val, when, holder, team, extra = (rows[i] + [""] * 6)[:6]; i += 1
        holders = [re.split(r"\s+(?:over|vs)\s+|\s+-\s+", h.strip())[0] for h in re.split(r"[;,&]", holder) if h.strip()]
        ev = [x.strip() for x in extra.split("¦") if x.strip()] if extra else []
        evidence = [x for x in ev if x.startswith("http")]
        notes = [x for x in ev if not x.startswith("http")]
        metric = METRIC.get(name)
        recs.append({
          "id": slug(name), "name": name, "category": cat,
          "source": "seeded", "metric": metric[0] if metric else None, "direction": metric[1] if metric else None,
          "value": val, "value_num": num(val), "when": when, "holder": holder.strip(), "holders": holders,
          "league_level": holder.strip() == "DTFClub", "team": team, "notes": notes, "evidence": evidence,
          "replay": None, "previous": None, "ties": [], "locked": False, "status": "active",
          "era_pair": slug(ERA_PAIRS[name]) if name in ERA_PAIRS else None,
          "size_sensitive": bool(SIZE_SENSITIVE.search(name)),
          "needs_definition": NEEDS_DEFINITION.get(name), "definition": DEFINITION.get(name), "engine_gap": SOURCE_HINT.get(name),
          "updated": "2026-11-02"})
json.dump({"version": 1, "league": "DTF Club", "records": recs}, open("data/records.json", "w"), indent=1, ensure_ascii=False)
open("data/changelog.jsonl", "w").write(json.dumps({"ts": "2026-11-02T00:00:00Z", "record": "*", "cause": "seed:sheet",
  "note": "Imported 76 records from the hand-kept Record Book sheet."}) + "\n")
print(len(recs), "records;", sum(1 for r in recs if r["metric"]), "have an engine metric")
