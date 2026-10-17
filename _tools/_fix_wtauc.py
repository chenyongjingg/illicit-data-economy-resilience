# -*- coding: utf-8 -*-
"""Fix the E5p writer defect that killed the rerun, and CONTROL the fix.

THE DEFECT (C-174, from the pod traceback, not from reading):
    :1321  wtauc -> within_t0_auc(t0v[m], Y[m, k], scores[m])   <- no column index
`wtauc` received the FULL (n, n_deltas) score matrix. `within_t0_auc` indexes
whatever it is handed by the BIN mask, so `s[m]` came out (n_in_bin, 3); with a
>2-column score `roc_auc_score` takes the MULTICLASS branch and, since
`multi_class` defaults to "raise", threw
    ValueError: multi_class must be in ('ovo', 'ovr')
-- a message that named neither the line nor the shape. The neighbouring
`test_auc_by_delta` at :1342 slices `[..., k]`; the line my fix added did not.
The arms never hit it because `eval_block` passes a 1-D score.

TWO FIXES, NOT ONE.
  1. The caller selects its column (`scores[m, k]`).
  2. `within_t0_auc` REFUSES non-1-D input at its boundary. Without this the
     next such mistake costs another 44-minute run to discover: the defect was
     detectable at second zero and was found at second 2,636.

WHY THE FIXTURE EXTRACTS SOURCE INSTEAD OF RETYPING IT.
The pre-fix and post-fix implementations are pulled out of the real files with
`ast` and exec'd, so the negative control is the ACTUAL object that crashed
rather than my recollection of it. A fixture written against a retyped copy
tests the copy. The four cases:

  A  PRE-fix, 2-D input   -> sklearn's multi_class error   (reproduces the crash)
  B  POST-fix, 2-D input  -> the new guard's error         (has a rejecting branch)
  C  POST-fix, column     -> a real weighted value          (the fix works)
  D  POST-fix, 1-D input  -> a real weighted value          (arms unaffected)

B is what proves the guard is not a literal: it is reached and it raises.
"""
import ast
import hashlib
import io
import re
import shutil
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = r"D:\CIS\_server\53_E5p_temporal_gnn.py"
REV = r"D:\CIS\_tools\_revisions\53_E5p_temporal_gnn.%s.py"

NEW_CALL = """        return within_t0_auc(t0v[m], Y[m, k], scores[m, k])"""
OLD_CALL = """        return within_t0_auc(t0v[m], Y[m, k], scores[m])"""

GUARD = '''    y = np.asarray(y)
    s = np.asarray(s, dtype="float64")
    # REFUSE NON-1-D AT THE BOUNDARY (C-174).
    # `mask` below indexes whatever it is given, so a SCORE MATRIX silently
    # becomes `s[m]` of shape (n_in_bin, n_columns). With >2 columns
    # `roc_auc_score` takes the MULTICLASS branch and raises
    # "multi_class must be in ('ovo', 'ovr')" -- naming neither this function
    # nor the shape -- and the first E5p rerun died there 2,636 s into a 2,667 s
    # run with no artefact written. The mistake is a missing column index and is
    # detectable at second zero, so it fails here instead. Select the column at
    # the call site (see `wtauc`).
    if y.ndim != 1 or s.ndim != 1:
        raise ValueError(
            "within_t0_auc takes 1-D labels and scores; got y.shape=%r "
            "s.shape=%r. A 2-D `s` is a SCORE MATRIX -- select its column "
            "first (`scores[m, k]`), or roc_auc_score will take the multiclass "
            "branch and fail 44 minutes into a run. (C-174)" % (y.shape, s.shape))
'''

text = io.open(SRC, encoding="utf-8").read()
pre_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

# ---- 1. extract the PRE-fix `within_t0_auc` source, for the negative control
tree = ast.parse(text)
def fn_src(name):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(text, node)
    raise AssertionError("no top-level def %r" % name)

PRE_WT = fn_src("within_t0_auc")
PRE_AUC = fn_src("auc")
assert "REFUSE NON-1-D" not in PRE_WT, "already patched?"

# ---- 2. apply the guard + the column index
anchor = '''    t0 = np.asarray(t0)
    y = np.asarray(y)
    s = np.asarray(s, dtype="float64")
'''
assert text.count(anchor) == 1, "guard anchor not unique: %d" % text.count(anchor)
assert GUARD not in text, "guard already present"
text = text.replace(anchor, "    t0 = np.asarray(t0)\n" + GUARD)

assert text.count(OLD_CALL) == 1, "call anchor not unique: %d" % text.count(OLD_CALL)
text = text.replace(OLD_CALL, NEW_CALL)

post_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
io.open(SRC, "w", encoding="utf-8", newline="").write(text)
print("patched %s  %s -> %s" % (SRC, pre_sha, post_sha))
print("  lines %d -> %d (unchanged: %s)\n"
      % (text.count("\n"), io.open(SRC, encoding="utf-8").read().count("\n"),
         "verify below"))

# ---- 3. CONTROL: run pre- and post-fix implementations on the same inputs
ns_common = {"np": np, "SEED_BOOT": 20240924}
from sklearn.metrics import roc_auc_score          # noqa: E402
ns_common["roc_auc_score"] = roc_auc_score

def build(f_src, wt_src, label):
    ns = dict(ns_common)
    exec(f_src, ns)
    exec(wt_src, ns)
    return ns["within_t0_auc"]

PRE = build(PRE_AUC, PRE_WT, "pre")
POST = build(fn_src("auc"), fn_src("within_t0_auc"), "post")

rng = np.random.default_rng(0)
r = make = None
n = 300
t0 = rng.integers(0, 5, n)
Y = (rng.random(n) < 0.3).astype(float)
SCORES = rng.random((n, 3))          # <- the 2-D matrix shape that crashed it
COL = SCORES[:, 1]

def run(fn, t0_, y_, s_):
    try:
        d = fn(t0_, y_, s_)
        return "value weighted=%s" % (
            "None" if d.get("weighted") is None else "%.5f" % d["weighted"])
    except Exception as e:
        return "%s: %s" % (type(e).__name__, str(e)[:70])

cases = [
    ("A  PRE-fix, 2-D input  (the crash)", PRE, t0, Y, SCORES, "reproduce"),
    ("B  POST-fix, 2-D input (the guard)", POST, t0, Y, SCORES, "raise"),
    ("C  POST-fix, one column", POST, t0, Y, COL, "value"),
    ("D  POST-fix, 1-D (arms)", POST, t0, Y, COL.copy(), "value"),
]
print("-- control: same inputs through the pre-fix and post-fix source --")
fails = 0
for label, fn, a, b, c, want in cases:
    got = run(fn, a, b, c)
    if want == "reproduce":
        ok = got.startswith("ValueError") and "multi_class" in got
        want_s = "sklearn multi_class error"
    elif want == "raise":
        ok = got.startswith("ValueError") and "within_t0_auc takes 1-D" in got
        want_s = "the new guard's error"
    else:
        ok = got.startswith("value weighted=") and "None" not in got
        want_s = "a real weighted value"
    fails += 0 if ok else 1
    print("  %-38s -> %-52s want %s  %s"
          % (label, got, want_s, "OK" if ok else "*** NOT OK ***"))

print("\n%d case(s) not as required" % fails)
if fails:
    sys.exit(1)

# ---- 4. store the revision under its own sha, so the object is recoverable
rev_path = REV % post_sha
shutil.copyfile(SRC, rev_path)
b = io.open(rev_path, "rb").read()
assert hashlib.sha256(b).hexdigest()[:16] == post_sha
print("\nrevision stored: %s  (%d B)" % (rev_path, len(b)))
print("push this exact sha to the pod and confirm it there before rerunning.")
