"""Add the trade / FAB / sit-start records (idempotent) and move the old 'Trades & FAB' rows into the three new categories."""
import json, re
P = "data/records.json"
doc = json.load(open(P)); have = {r["id"] for r in doc["records"]}
try:        # a record deleted in edit mode stays deleted
    for line in open("data/changelog.jsonl"):
        e = json.loads(line)
        if e.get("cause") == "manual:delete": have.add(e["record"])
except FileNotFoundError: pass
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
VERIFY_MAP = {"Smallest Margin of Rumble Win Victory": ("rumble_margin", "min"), "Most Points on Bench": ("bench", "max"), "Most Shotguns in a Season (League)": ("shot_league", "max"), "Most 0.0's in a Win": ("zeros_win", "max"),
              "Highest % Points Scored by 1 Player": ("top_share", "max"), "Fewest Total League Points on Thursday Night": ("thu_league", "min"),
              "Most Points on a Saturday": ("sat_pts", "max"), "Highest Projected Point Total": ("high_proj", "max"), "Highest Projected Point Total (Era Adjusted)": ("high_proj_adj", "max"), "Largest Monday Night Deficit Overcome": ("mnf_overcome", "max")}
for r in doc["records"]:
    k = VERIFY_MAP.get(r["name"].strip())
    if k:
        r["metric"], r["direction"] = k; r["engine_gap"] = None
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

S21b = " Counts games since 2021, when Rumble Central's records begin."
NEW += [
 ("Games & Weeks", "Biggest Comeback (Points Deficit Overcome)", "comeback", "max", "The biggest points deficit a team trailed by at any moment and still won, from Rumble Central's play-by-play timeline." + S21b),
 ("Games & Weeks", "Biggest Blown Lead", "blown_lead", "max", "The biggest points lead a team held at any moment and still lost." + S21b),
 ("Games & Weeks", "Most Lead Changes in a Game", "lead_changes", "max", "The most times the lead flipped in one matchup." + S21b),
 ("Games & Weeks", "Biggest Upset by Projection", "upset_proj", "max", "The winner who was projected furthest behind going in (sum of Sleeper's pre-game projections for the starters)." + S21b),
 ("Games & Weeks", "Most Points Over Projection", "over_proj", "max", "Most points a team scored above the sum of its starters' pre-game projections." + S21b),
 ("Games & Weeks", "Most Points Under Projection", "under_proj", "max", "Most points a team scored below the sum of its starters' pre-game projections." + S21b),
 ("Games & Weeks", "Most Points on Thursday Night (Team)", "thu_pts", "max", "Most points from the Thursday-night game in one week by one team's starters." + S21b),
 ("Games & Weeks", "Most Points on Monday Night (Team)", "mon_pts", "max", "Most points from Monday-night games in one week by one team's starters." + S21b),
 ("Sit / Start", "Most Points on Bench in a Season", "bench_season", "max", "Total points left on the bench across a regular season (every rostered player not in the starting lineup)." + S21b),
 ("Sit / Start", "Most Shotguns in a Week (Team)", "shot_week", "max", "A Shotgun is a score of 0 or less from a non-defense starter who took the field. The most for one team in one week." + S21b),
 ("Sit / Start", "Most Shotguns in a Season (Team)", "shot_season", "max", "The most Shotguns by one team in a season." + S21b),
 ("Rivalries", "Longest Head-to-Head Win Streak vs One Opponent", "rivalry_streak", "max", "Most consecutive wins by one manager over the same opponent (regular season and playoffs)." + S21b),
 ("Rivalries", "Most Meetings Between Two Managers", "rivalry_meetings", "max", "The most games between the same two managers." + S21b),
 ("Rivalries", "Most One-Sided Rivalry", "rivalry_onesided", "max", "Best head-to-head record against one opponent, with at least 6 meetings." + S21b),
 ("Rivalries", "Most Playoff Meetings Between Two Managers", "playoff_meetings", "max", "The most playoff games between the same two managers, 2013 on."),
 ("Seasons & Playoffs", "Lowest Seed to Win the Title", "lowest_seed_champ", "max", "The lowest playoff seed to win the championship (seeds are known from 2021)."),
 ("Seasons & Playoffs", "Highest Playoff Score", "highest_playoff_score", "max", "The most points by one team in a playoff game."),
 ("Seasons & Playoffs", "Closest Championship Game", "closest_final", "min", "The smallest winning margin in a championship game."),
 ("Seasons & Playoffs", "Biggest Championship Blowout", "biggest_final", "max", "The largest winning margin in a championship game."),
 ("Seasons & Playoffs", "Most Playoff Wins (Career)", "playoff_wins", "max", "Most playoff games won, 2013 on."),
 ("Seasons & Playoffs", "Most Playoff Trips Without a Title", "playoffs_no_title", "max", "Most playoff appearances by a manager who has never won the championship."),
 ("Seasons & Playoffs", "Fewest Wins to Make the Playoffs", "fewest_wins_playoffs", "min", "The fewest regular-season wins by a team that made the playoffs."),
 ("Seasons & Playoffs", "Most Wins to Miss the Playoffs", "most_wins_miss", "max", "The most regular-season wins by a team that missed the playoffs."),
 ("Seasons & Playoffs", "Biggest Standings Jump", "standings_jump", "max", "The most places a manager climbed in the final standings from one season to the next."),
 ("Seasons & Playoffs", "Biggest Standings Drop", "standings_drop", "max", "The most places a manager fell in the final standings from one season to the next."),
 ("Draft & Auction", "Most Expensive Auction Pick", "auction_price", "max", "The highest price ever paid for a player in the auction draft (budget is $200 per team every year)."),
 ("Draft & Auction", "Most Expensive QB", "auction_qb", "max", "The highest price paid for a quarterback."),
 ("Draft & Auction", "Most Expensive RB", "auction_rb", "max", "The highest price paid for a running back."),
 ("Draft & Auction", "Most Expensive WR", "auction_wr", "max", "The highest price paid for a wide receiver."),
 ("Draft & Auction", "Most Expensive TE", "auction_te", "max", "The highest price paid for a tight end."),
 ("Draft & Auction", "Costliest Bust", "auction_bust", "max", "The highest price paid for a player who played at least 8 games and finished in the bottom half at his position."),
 ("Draft & Auction", "Costliest Injury Casualty", "auction_injury", "max", "The highest price paid ($10+) for a player who played 7 games or fewer."),
 ("Draft & Auction", "Best Steal", "auction_steal", "min", "The cheapest top-3 positional finisher; ties go to the most points."),
 ("Draft & Auction", "Most Spent on One Position", "auction_pos_spend", "max", "The most one manager spent on a single position in one auction."),
 ("Trades", "Best Trade by a Champion (PAR)", "trade_champ_best", "max", "The best trade (by PAR) made by the eventual champion in their title season." + S21),
 ("Trades", "Worst Trade by a Champion (PAR)", "trade_champ_worst", "min", "The worst trade (by PAR) made by an eventual champion in their title season, and they still won." + S21),
 ("Trades", "Worst Trade by an Eventual Sacko (PAR)", "trade_sacko_worst", "min", "The worst trade (by PAR) made by the team that finished last that season." + S21),
 ("Games & Weeks", "Most Points by a Quarterback (Game)", "player_qb", "max", "The most fantasy points scored by one starting quarterback in a game." + S21),
 ("Games & Weeks", "Most Points by a Running Back (Game)", "player_rb", "max", "The most fantasy points scored by one starting running back in a game." + S21),
 ("Games & Weeks", "Most Points by a Wide Receiver (Game)", "player_wr", "max", "The most fantasy points scored by one starting wide receiver in a game." + S21),
 ("Games & Weeks", "Most Points by a Tight End (Game)", "player_te", "max", "The most fantasy points scored by one starting tight end in a game." + S21),
 ("Games & Weeks", "Most Points by a Kicker (Game)", "player_k", "max", "The most fantasy points scored by one starting kicker in a game." + S21),
 ("Games & Weeks", "Most Points by a Defense (Game)", "player_def", "max", "The most fantasy points scored by one starting defense/special teams in a game." + S21),
 ("Sit / Start", "Best Sit/Start % (Career)", "sitstart_career", "max", "The best Toss-up % across a career: of the sit/start calls that were projected within 2 points of each other, the share where the starter finished above replacement and the bench option did not (the Sit/Start tool's Toss-up %). At least 10 toss-ups." + S21),
 ("Sit / Start", "Best Sit/Start % (Season)", "sitstart_season", "max", "The best Toss-up % in one season (the Sit/Start tool's Toss-up %), with at least 10 toss-ups." + S21),
 ("Draft & Auction", "Best Draft", "draft_best", "max", "The highest Overall grade for one auction draft (10+ graded picks), as scored in the Auction tool's Draft Quality tab: each pick is a Banger (+2), Hit (+1), Meh (0), Bust (-1) or Fail (-2) from its price against where the player finished; kickers, defenses and injuries are left out."),
 ("Draft & Auction", "Best Drafter (Career)", "drafter_best", "max", "The highest career Overall grade across every graded auction pick, as scored in the Auction tool's Draft Quality tab (at least 3 drafts)."),
 ("FAB & Waivers", "Most FAB Spent by a Champion", "fab_champ_spent", "max", "The most FAB dollars spent on winning bids by a team that won the title that season."),
 ("FAB & Waivers", "Fewest FAB Spent by a Champion", "fab_champ_least", "min", "The fewest FAB dollars spent on winning bids by a team that won the title that season."),
]
add = []
for cat, name, metric, direction, definition in NEW:
    if slug(name) in have: continue
    add.append({"id": slug(name), "name": name, "category": cat, "source": "computed", "metric": metric, "direction": direction, "value": "", "value_num": None,
                "when": "", "holder": "", "holders": [], "league_level": False, "team": "", "notes": [], "evidence": [], "replay": None, "previous": None, "ties": [],
                "locked": False, "status": "active", "era_pair": None, "size_sensitive": False, "needs_definition": None, "engine_gap": None, "definition": definition, "updated": ""})
SHORT = {"Longest Head-to-Head Win Streak vs One Opponent": "Longest Win Streak vs One Opponent", "Most Meetings Between Two Managers": "Most Games vs One Opponent",
         "Most Playoff Meetings Between Two Managers": "Most Playoff Games vs One Opponent", "Biggest Comeback (Points Deficit Overcome)": "Biggest Comeback (Pts Overcome)",
         "Worst Trade by an Eventual Sacko (PAR)": "Worst Trade by a Sacko (PAR)"}     # row label only; the full name shows in the details view
for r in doc["records"]:
    if r["name"] in SHORT: r["short"] = SHORT[r["name"]]
order = ["Seasons & Playoffs", "Team Seasons", "Games & Weeks", "Projections & NFL Clock", "Trades", "FAB & Waivers", "Sit / Start", "Rivalries", "Draft & Auction"]
doc["records"] += add
doc["records"].sort(key=lambda r: order.index(r["category"]))     # stable: keeps the sheet's order inside a category
json.dump(doc, open(P, "w"), indent=1, ensure_ascii=False)
print("added", len(add), "total", len(doc["records"]))
