#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check the E5p ev_require predicate against the REAL artefact and the REAL schema.

Two independent things are tested:

1) MUTATION TEST ON THE REAL SCHEMA. The first version of this predicate read
   d["deltas"], but the real artefact keeps them at meta.deltas, so it would have
   returned False forever on a perfect file. The earlier mutation test could not
   catch that: its fixture was written from the same wrong mental model as the
   predicate. Here the fixture is the REAL file, and the acceptance case is
   produced by flipping exactly the one clause that this run legitimately fails.

2) A NAMED REPORT of which clause fails on the unmodified artefact, so "not DONE"
   comes with a reason rather than a bare False.
"""
import copy
import importlib.util
import io
import json
import os
import sys

CIS = r"D:\CIS"
P = os.path.join(CIS, "results", "53_E5p_result.oldwriter_55d7d8f8.json")
d = json.load(io.open(P, encoding="utf-8"))

spec = importlib.util.spec_from_file_location(
    "rp", os.path.join(CIS, "_tools", "run_pipeline.py"))
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)
req = [s for s in rp.STAGES if s["id"] == "E5p"][0]["ev_require"]


def clauses(x):
    m = x.get("meta") or {}
    return {
        "meta.deltas is list": isinstance(m.get("deltas"), list),
        "len(meta.deltas) >= 2": isinstance(m.get("deltas"), list) and len(m["deltas"]) >= 2,
        "3 arms numeric auc_test at every delta": all(
            isinstance(((((x.get("arms") or {}).get(a) or {}).get("by_delta") or {})
                        .get(str(D), {})).get("auc_test"), (int, float))
            for a in ("mlp_feature_only", "graphsage", "tgn")
            for D in (m.get("deltas") or [])),
        "split.test int > 0": isinstance((x.get("split") or {}).get("test"), int)
            and (x["split"]["test"] or 0) > 0,
        "summary.feature_filter_verification_exact": bool(
            ((x.get("leakage_check") or {}).get("summary") or {})
            .get("feature_filter_verification_exact")),
        "summary.no_lifetime_column_in_model_matrices": bool(
            ((x.get("leakage_check") or {}).get("summary") or {})
            .get("no_lifetime_column_in_model_matrices")),
        "naive_leaking_baseline.admissible is False": (
            (x.get("naive_leaking_baseline") or {}).get("admissible") is False),
    }


print("=" * 78)
print("A) THE REAL PULLED ARTEFACT, UNMODIFIED")
print("=" * 78)
print("file:", os.path.basename(P))
real = bool(req(d))
for k, v in clauses(d).items():
    print("   [%s] %s" % ("PASS" if v else "FAIL", k))
print("   => ev_require =", real, " (driver verdict: %s)"
      % ("DONE" if real else "NOT DONE"))

print()
print("=" * 78)
print("B) MUTATION TEST ON THE REAL SCHEMA (fixture = the real file)")
print("=" * 78)

# acceptance case: flip ONLY the one clause this run legitimately fails
acc = copy.deepcopy(d)
acc["leakage_check"]["summary"]["feature_filter_verification_exact"] = True
print("   flip summary.feature_filter_verification_exact -> True :",
      "ACCEPTED" if req(acc) else "*** STILL REJECTED -- predicate is broken ***")
assert req(acc), "predicate does not accept a valid artefact: the schema path is wrong"

# and it must reject each mutation
muts = {
    "deltas moved to top level, removed from meta": lambda x: (
        x["meta"].pop("deltas"), x.__setitem__("deltas", [1, 3, 5])),
    "deltas emptied": lambda x: x["meta"].__setitem__("deltas", []),
    "one arm's auc_test stringified": lambda x: x["arms"]["tgn"]["by_delta"]["5"]
        .__setitem__("auc_test", "0.83"),
    "one arm's auc_test removed": lambda x: x["arms"]["graphsage"]["by_delta"]["3"]
        .pop("auc_test"),
    "split.test = 0": lambda x: x["split"].__setitem__("test", 0),
    "split.test removed": lambda x: x["split"].pop("test"),
    "lifetime-column denial flag off": lambda x: x["leakage_check"]["summary"]
        .__setitem__("no_lifetime_column_in_model_matrices", False),
    "naive baseline marked admissible": lambda x: x["naive_leaking_baseline"]
        .__setitem__("admissible", True),
}
allgood = True
for name, fn in muts.items():
    x = copy.deepcopy(acc)
    fn(x)
    got = bool(req(x))
    allgood &= (got is False)
    print("   [%s] %s" % ("REJECTED" if got is False else "*** ACCEPTED ***", name))
print("   => mutation test:", "all 8 rejected OK" if allgood else "SOME MUTATION PASSED")

# and the null-mutation control must remain accepted
x = copy.deepcopy(acc)
print("   [%s] null mutation (must stay ACCEPTED)"
      % ("ACCEPTED" if req(x) else "*** REJECTED ***"))
score = real is False and req(acc) and allgood and req(x)
print()
print("VERDICT OF THIS SUITE:", "OK" if score else "PROBLEM")
sys.exit(0 if score else 1)
