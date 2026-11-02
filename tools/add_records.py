"""Add the trade / FAB / sit-start records (idempotent) and move the old 'Trades & FAB' rows into the three new categories."""
import json, re
P = "data/records.json"
doc = json.load(open(P)); have = {r["id"] for r in doc["records"]}
def slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
MOVE = {"Trades": ["Most Trades in 24hrs", "Most non-FAB Trades in a Season (League)", "Most Trades in a Season (League)", "Most non-FAB Trades in a Season (Team)",
                   "Most Trades in a Season (Team)", "Most Teams to Make a Trade", "Most FAB in a trade", "Fastest Trade Acceptance to Player Start"],
        "FAB & Waivers": ["Most FAB owned at one time", "Largest FAB Overbid", "Best FAB Bid (Lowest % over next bid)", "Earliest FAB Bankruptcy"],
        "Sit / Start": ["Most Shotguns in a Season (League)"]}
for r in doc["records"]:
    for cat, names in MOVE.items():
        if r["name"] in names: r["category"] = cat
for r in doc["records"]:   # the two non-FAB trade counts the data can verify
    if r["name"] == "Most non-FAB Trades in a Season (League)": r["metric"], r["direction"] = "trades_league_season", "max"
    if r["name"] == "Most non-FAB Trades in a Season (Team)": r["metric"], r["direction"] = "trades_team_season", "max"
S21 = " Counts trades since 2021 (the first Sleeper season)."
PAR = "PAR = points above replacement: how many more points the player's lineup got than a replacement-level player at the position would have."
NEW = [
 ("Trades", "Best Trade (PAR Swing)", "trade_net", "max", "The biggest gap between the two sides' PAR gained from a trade, measured from the trade to today." + S21 + " " + PAR),
 ("Trades", "Most PAR Gained in One Trade", "trade_best_side", "max", "The most PAR one team has gained from a single trade." + S21),
 ("Trades", "Most PAR Lost in One Trade", "trade_worst_side", "min", "The most PAR one team has lost in a single trade (the worst trade ever made)." + S21),
 ("Trades", "Biggest Trade-Day Heist (Value)", "trade_value_gap", "max", "The largest gap in trade-chart value between what a team got and what it gave, on the day of the trade." + S21),
 ("Trades", "Biggest Blockbuster (Total Value)", "trade_blockbuster", "max", "The highest combined trade-chart value of all assets in one trade." + S21),
 ("Trades", "Most Players in One Trade", "trade_assets", "max", "The most players changing hands in one trade." + S21),
 ("Trades", "Most Trades (Career)", "trades_career", "max", "Most trades made by one manager." + S21),
 ("Trades", "Most Trades with One Partner", "trades_partner", "max", "Most trades between the same two managers." + S21),
 ("Trades", "Best Trader (Career PAR)", "trader_best", "max", "Total PAR gained across every trade a manager has made (at least 3 trades)." + S21),
 ("Trades", "Worst Trader (Career PAR)", "trader_worst", "min", "Total PAR lost across every trade a manager has made (at least 3 trades)." + S21),
 ("FAB & Waivers", "Best FAB Pickup (PAR)", "fab_best_par", "max", "The waiver claim that produced the most PAR in the claiming team's starting lineups." + S21 + " " + PAR),
 ("FAB & Waivers", "Best Free-Agent Pickup (PAR)", "fab_best_fa", "max", "The best $0 free-agent add by PAR in the starting lineups."),
 ("FAB & Waivers", "Most Expensive FAB Claim", "fab_bid", "max", "The largest winning FAB bid."),
 ("FAB & Waivers", "Worst FAB Pickup ($40+ Bids)", "fab_worst", "min", "The lowest PAR from a claim that cost $40 or more."),
 ("FAB & Waivers", "Best FAB Value (PAR per $)", "fab_value", "max", "Most PAR per FAB dollar on a claim costing $10 or more."),
 ("FAB & Waivers", "Most FAB Spent in a Season", "fab_spent", "max", "The most FAB dollars spent on winning bids in one season."),
 ("FAB & Waivers", "Most Waiver PAR in a Season", "fab_season_par", "max", "The most PAR from a manager's waiver and free-agent pickups in one season."),
 ("FAB & Waivers", "Best Waiver Season (Net of Regret)", "fab_season_net", "max", "Waiver PAR minus the PAR that dropped players later gave other managers."),
 ("FAB & Waivers", "Most Difference-Makers in a Season", "fab_season_hits", "max", "Pickups worth 25+ PAR in one season."),
 ("FAB & Waivers", "Most Pickups in a Season", "fab_season_adds", "max", "The most claims and free-agent adds by one manager in a season."),
 ("FAB & Waivers", "Biggest Drop Regret (One Player)", "fab_regret_drop", "max", "A dropped player who went on to produce the most PAR in another manager's lineup."),
 ("FAB & Waivers", "Most Regret in a Season", "fab_season_regret", "max", "The most PAR that a manager's dropped players produced for other managers in one season."),
 ("Sit / Start", "Costliest Sit/Start Miss", "sit_start_miss", "max", "Started a player who scored below replacement while a bench player eligible for the same slot scored above replacement, and the call was a clear miss by pre-game projections. Points lost = the bench player's points minus the starter's."),
 ("Sit / Start", "Best Sit/Start Call", "sit_start_call", "max", "A 'big-brain start': started the lower-projected player by 2+ points and won the swap. Points gained = the starter's points minus the benched player's."),
 ("Sit / Start", "Worst Lineup Week (Points Lost)", "worst_week", "max", "The most points left on the bench in one week from clear lineup misses."),
 ("Sit / Start", "Most Points Lost to Lineup Misses in a Season", "season_bench", "max", "Season total of points lost to clear lineup misses."),
 ("Sit / Start", "Most Wins Lost to Lineup Misses in a Season", "season_wins_lost", "max", "Losses that the week's clear misses were bigger than the margin of."),
 ("Sit / Start", "Most Rumbles Lost to Lineup Misses in a Season", "season_rumbles_lost", "max", "Rumbles that would have been earned with the right calls."),
 ("Sit / Start", "Most Big-Brain Calls in a Season", "season_brain", "max", "Most winning sit/start calls (started the lower projection and won the swap) in one season."),
]
add = []
for cat, name, metric, direction, definition in NEW:
    if slug(name) in have: continue
    add.append({"id": slug(name), "name": name, "category": cat, "source": "computed", "metric": metric, "direction": direction, "value": "", "value_num": None,
                "when": "", "holder": "", "holders": [], "league_level": False, "team": "", "notes": [], "evidence": [], "replay": None, "previous": None, "ties": [],
                "locked": False, "status": "active", "era_pair": None, "size_sensitive": False, "needs_definition": None, "engine_gap": None, "definition": definition, "updated": ""})
order = ["Seasons & Playoffs", "Team Seasons", "Games & Weeks", "Projections & NFL Clock", "Trades", "FAB & Waivers", "Sit / Start"]
doc["records"] += add
doc["records"].sort(key=lambda r: order.index(r["category"]))     # stable: keeps the sheet's order inside a category
json.dump(doc, open(P, "w"), indent=1, ensure_ascii=False)
print("added", len(add), "total", len(doc["records"]))
