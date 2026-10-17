# -*- coding: utf-8 -*-
"""Control the E5p writer fix against the two REAL files.

WHY THIS REPLACES `_fix_wtauc.py`'s BUILT-IN FIXTURE.
That fixture extracted both implementations from ONE parse tree and one `text`
variable. `ast.get_source_segment(text, node)` resolves offsets against the
CURRENT value of `text`, so after the patch the pre-patch node offsets were
applied to the post-patch text: every function below the insertion point came
back silently TRUNCATED (missing its `return` statements) and returned None.
Cases A and B survived only because both raise before the truncation. A fixture
whose instrument drifts with the object it measures reports on neither.

So: no offsets shared across files. The PRE-fix object is the stored revision
`...1ebf15e85fe73026.py` and the POST-fix object is `_server/...py`; each is
parsed in its own pass, and both shas are asserted before anything is run.

  A  PRE-fix, 2-D input   -> sklearn's multi_class error   (reproduces the crash)
  B  POST-fix, 2-D input  -> the new guard's error         (the guard rejects)
  C  POST-fix, one column -> a real weighted value          (the fix works)
  D  POST-fix, 1-D input  -> a real weighted value          (arms unaffected)
  E  PRE-fix, one column  -> a real weighted value          (A is about the
                                                             SHAPE, not the fix)
"""
import ast
import hashlib
import io
import shutil
import sys

import numpy as np
from sklearn.metrics import roc_auc_score

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PRE_FILE = r"D:\CIS\_tools\_revisions\53_E5p_temporal_gnn.1ebf15e85fe73026.py"
POST_FILE = r"D:\CIS\_server\53_E5p_temporal_gnn.py"
REV_FMT = r"D:\CIS\_tools\_revisions\53_E5p_temporal_gnn.%s.py"

WANT_PRE = "1ebf15e85fe73026"


def load(path):
    text = io.open(path, encoding="utf-8").read()
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    tree = ast.parse(text)
    out = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in ("auc", "within_t0_auc"):
            out[node.name] = ast.get_source_segment(text, node)
    missing = {"auc", "within_t0_auc"} - set(out)
    assert not missing, "%s missing %s" % (path, missing)
    # A truncated extraction is the failure this whole rewrite exists to avoid,
    # so require the terminal statements to be present in the extracted text.
    assert "return float(roc_auc_score(y, s))" in out["auc"], "auc truncated"
    assert "per_bin=per)" in out["within_t0_auc"], "within_t0_auc truncated"
    return sha, out, text


pre_sha, pre_fn, pre_text = load(PRE_FILE)
post_sha, post_fn, post_text = load(POST_FILE)
assert pre_sha == WANT_PRE, "pre-fix revision is not the one that ran: %s" % pre_sha

print("pre-fix  %s  sha=%s  lines=%d" % (PRE_FILE.split("\\")[-1], pre_sha,
                                         pre_text.count("\n")))
print("post-fix %s  sha=%s  lines=%d" % (POST_FILE.split("\\")[-1], post_sha,
                                         post_text.count("\n")))

# The guard must be present in the post-fix text and absent from the pre-fix.
assert "REFUSE NON-1-D" in post_text and "REFUSE NON-1-D" not in pre_text
assert "scores[m, k]" in post_text and "scores[m, k]" not in pre_text
print("  guard present in post-fix, absent in pre-fix: OK")
print("  column index present in post-fix, absent in pre-fix: OK\n")

NS = {"np": np, "roc_auc_score": roc_auc_score, "SEED_BOOT": 20240924}


def build(fx):
    ns = dict(NS)
    exec(fx["auc"], ns)
    exec(fx["within_t0_auc"], ns)
    return ns["within_t0_auc"]


PRE, POST = build(pre_fn), build(post_fn)

rng = np.random.default_rng(0)
n = 300
t0 = rng.integers(0, 5, n)
Y = (rng.random(n) < 0.3).astype(float)
SCORES = rng.random((n, 3))
COL = SCORES[:, 1]


def run(fn, s):
    try:
        d = fn(t0, Y, s)
        if not isinstance(d, dict):
            return "returned %r (NOT A DICT -- truncated body)" % (d,)
        w = d.get("weighted")
        return "value weighted=%s" % ("None" if w is None else "%.5f" % w)
    except Exception as e:
        return "%s: %s" % (type(e).__name__, str(e)[:80])


CASES = [
    ("A  PRE-fix,  2-D input  (the crash)", PRE, SCORES,
     lambda g: g.startswith("ValueError") and "multi_class" in g),
    ("B  POST-fix, 2-D input  (the guard)", POST, SCORES,
     lambda g: g.startswith("ValueError") and "within_t0_auc takes 1-D" in g),
    ("C  POST-fix, one column", POST, COL,
     lambda g: g.startswith("value weighted=") and "None" not in g),
    ("D  POST-fix, 1-D input  (arms)", POST, COL.copy(),
     lambda g: g.startswith("value weighted=") and "None" not in g),
    ("E  PRE-fix,  one column (control for A)", PRE, COL,
     lambda g: g.startswith("value weighted=") and "None" not in g),
]
fails = 0
print("-- control table --")
for label, fn, s, pred in CASES:
    got = run(fn, s)
    ok = pred(got)
    fails += 0 if ok else 1
    print("  %-42s -> %-58s %s" % (label, got, "OK" if ok else "*** NOT OK ***"))
print("\n%d case(s) not as required" % fails)
if fails:
    sys.exit(1)

rev = REV_FMT % post_sha
shutil.copyfile(POST_FILE, rev)
b = io.open(rev, "rb").read()
assert hashlib.sha256(b).hexdigest()[:16] == post_sha
print("\nrevision stored: %s (%d B)" % (rev.split("\\")[-1], len(b)))
print("pod must be updated to sha %s and re-verified there before the rerun." % post_sha)
