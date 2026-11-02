import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from load import load
import metrics as M
d = M.Data(load()); d.done_all = {y for y in d.raw["seasons"] if int(y) < d.cur}; d.done_all = {int(y) for y in d.done_all}
recs = json.load(open("data/records.json"))["records"]
for r in recs:
    if not r["metric"]: continue
    c = M.REGISTRY[r["metric"]](d)
    if not c: print("NO DATA", r["name"]); continue
    f = max if r["direction"] == "max" else min
    best = f(c, key=lambda x: x["value"]); top = sorted(c, key=lambda x: x["value"], reverse=r["direction"] == "max")[:3]
    flag = "" if r["value_num"] is not None and abs(best["value"] - r["value_num"]) < (0.51 if r["value_num"] > 500 else 0.06) else "  <-- DIFF"
    print(f'{r["name"][:42]:42} sheet={r["value"][:14]:14} data={best["value"]} {best["holders"]} {best["season"]} w{best["week"]}{flag}')
    if flag: print("      top3:", [(x["value"], x["holders"][0], x["season"], x["week"]) for x in top])
