import os
RC_BASE = os.environ.get("RC_BASE", "https://namkurd.github.io/SleeperLiveRumbles/rumbles.html")
def replay_url(season, week, rid, opp_rid, cur):
    q = f"?wp={week}.{rid}.{opp_rid}" + (f"&season={season}" if season != cur else "")
    return {"season": season, "week": week, "rid": rid, "opp_rid": opp_rid, "url": RC_BASE + q}
