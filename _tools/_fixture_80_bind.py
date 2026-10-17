# -*- coding: utf-8 -*-
"""Controls for 80_e5p_landing.bind_text_report.

The old pair (the text report and the JSON written by the SAME process) is the
only pair whose answer is known independently of the function under test. So it
is the positive control; every negative is a one-field mutation of it.
"""
import copy
import importlib.util
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location(
    "land", os.path.join(HERE, "80_e5p_landing.py"))
land = importlib.util.module_from_spec(spec)
spec.loader.exec_module(land)

TXT = os.path.join(ROOT, "results", "53_E5p_result.txt")
JSN = os.path.join(ROOT, "results", "53_E5p_result.oldwriter_55d7d8f8.json")
txt = io.open(TXT, encoding="utf-8").read()
obj = json.loads(io.open(JSN, encoding="utf-8").read())

cases = []

ok, lines = land.bind_text_report(txt, obj)
cases.append(("genuine pair (same process wrote both)", ok, True))

o = copy.deepcopy(obj)
o["seconds_total"] = obj["seconds_total"] + 1.0
ok2, _ = land.bind_text_report(txt, o)
cases.append(("runtime disagrees (stale txt from an earlier run)", ok2, False))

o = copy.deepcopy(obj)
o["leakage_check"]["summary"] = dict(obj["leakage_check"]["summary"])
o["leakage_check"]["summary"]["__mutated__"] = True
ok3, _ = land.bind_text_report(txt, o)
cases.append(("summary block differs (a DIFFERENT run's summary)", ok3, False))

ok4, _ = land.bind_text_report("no runtime or summary here at all", obj)
cases.append(("txt lacks the two anchors", ok4, False))

ok5, _ = land.bind_text_report(txt.replace("summary: {", "summary: {BROKEN"),
                               obj)
cases.append(("txt summary block does not parse", ok5, False))

ok6, _ = land.bind_text_report(txt, {"seconds_total": 1.0})
cases.append(("artefact lacks leakage_check.summary", ok6, False))

print("POSITIVE CONTROL IS THE REAL PAIR: %s\n" % TXT)
bad = 0
for name, got, want in cases:
    flag = "OK  " if got is want else "BAD "
    if got is not want:
        bad += 1
    print("  %s %-52s got=%-5s want=%s" % (flag, name, got, want))
print("\n%d case(s), %d unexpected" % (len(cases), bad))
print("\n--- the positive control's own lines ---")
for l in lines:
    print("   %s" % l)
sys.exit(1 if bad else 0)
