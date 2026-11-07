# DTF Club Record Book

A living version of the hand-kept record book. Static page (GitHub Pages) + a weekly Python job.

- **`index.html`** – the page. Filters by type, manager, source and "recently changed"; hover a mark to see the previous record; click a row for the top marks, ties, proof links and that record's history; **Change log** tab for everything that has moved. Filters are saved in the URL, so any view is shareable.
- **`data/records.json`** – every record (76 at launch). **`data/changelog.jsonl`** – append-only history.
- **`engine/`** – recomputes records from the other league repos (`sleepersheet` season totals back to 2013; `SleeperLiveRumbles` weekly games from 2021 and the 2026 season so far) and updates the data files.
- **`tools/seed.py`** + `tools/sheet.psv` – the one-time import of the old sheet. Don't re-run after go-live; it overwrites the data.
- **`.github/workflows/update.yml`** – runs the engine Tuesday mornings (and on demand from the Actions tab).

## How a record changes
| Source | Meaning |
|---|---|
| **Computed** | The engine recomputed it from Sleeper-derived data and it matches (✓) or the engine set it. |
| **Seeded** | From the old sheet; predates the data we can recompute (weekly scores before 2021). New games are still tested against it. |
| **Manual** | Entered or edited by you in the browser. |

Rules: a better mark takes over and the old one becomes the **previous record** (tooltip). An equal mark from a different holder is added as a **tie**. A **locked** record is never touched by the engine; if the engine finds a better mark it logs `auto:blocked` instead. Where Sleeper data disagrees with the sheet, the data wins and the change log says so (`auto:reconcile`).

## Rumble Cards
For single-game records since 2021 the details view shows the full Rumble Card (both teams' starters, points, Rumbles) rebuilt from Rumble Central's `epa_weekly.json` and `rumbles_history.json`, instead of cached screenshots. The engine rebuilds them on every run (`engine/cards.py`). Older screenshots are kept in `legacy_evidence` and still shown for records the archive can't reproduce (pre-2021 games, bench points, transactions).

## Replay links
`https://namkurd.github.io/SleeperLiveRumbles/rumbles.html?wp=<week>.<roster>.<opponent roster>[&season=YYYY]` – set `RC_BASE` in the workflow if that URL ever changes. Only single-matchup records from 2021 on get one.

## Editing in the browser
Click **✎ Edit mode**, paste a GitHub **fine-grained token** limited to this repo with **Contents: Read and write**. It is stored in your browser only. Saving makes one commit that updates both data files and is rebuilt on top of the latest `main`, so it can't overwrite an engine run. Manual edits are locked by default.

## Run locally
```
RB_SRC=/path/with/sleeperliverumbles-and-sleepersheet-checkouts python3 engine/run.py --dry
python3 -m http.server   # then open http://localhost:8000
```
`--baseline` marks changes as reconciliations against the old sheet (used once at launch).

## What the engine computes
- **Season-end counts** (`engine/seasons.py`): a manager-by-season ledger from 2013 on (final standings, playoff results, the podium, Sackos, #1 seeds from FAB-Management) plus a small hand-seeded set for 2011-12 and the 2013-20 #1 seeds, which exist only in the old sheet. Where the ledger and the sheet disagree, the ledger wins and the change log says so.
- **Games and weeks, team seasons** (`engine/metrics.py`): from Rumble Central's weekly archive and the lifetime-record repo.
- **Trades, FAB and sit/start** (`engine/market.py`): from SleeperTradeNodes (`data.json`: every trade with its PAR swing) and FAB-Management (`data.json`: pickups, drops and lineup decisions). These records start in 2021.

`tools/add_records.py` is the one place new records are defined (idempotent). Adding a record = a row there + a function in `engine/`.

- **Bench, Shotguns, comebacks, projections, Thursday/Saturday/Monday** (`engine/facts.py` + `engine/moments.py`): each finished week is ingested once from Sleeper (every rostered player's points, who took the field) and Rumble Central's play-by-play timeline, then cached in `data/cache/`. Where the sheet's game is in this data and the numbers differ, Sleeper wins and the change log says so.
- **Rivalries, playoffs and titles, draft and auction, champion/Sacko trades** (`engine/extras.py`): from the games archive, the playoff results, the SleeperAuction `picks.csv`, and the ledger.

## Eras
The **Era** chips under the search bar filter the book by league format and, for records that can be split by season, show each record's best mark inside the era. The eras (No PPR, PPR, Superflex no PPFD, Superflex + 0.5 PPFD) come from `data/eras.json`, which `tools/build_eras.py` rebuilds every week from each season's Sleeper league settings (reception tiers, SUPER_FLEX slot, first-down bonuses); 2011-2020 were not on Sleeper and are hand-set.

## Not auto-updated yet
Projections (the sheet's Highest Projected rows come from a different Sleeper snapshot than the one in the archive), trade timing (24-hour trades, fastest acceptance), FAB balances (most FAB owned, overbid, bankruptcy, FAB in a trade) and the trade/lineup counts that include FAB-only trades. Their rows keep the sheet's value.
