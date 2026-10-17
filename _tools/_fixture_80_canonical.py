# -*- coding: utf-8 -*-
"""Controls for 80_e5p_landing.place_canonical, in a scratch directory.

The branch that matters is the third one: the canonical name is exactly the name
an EARLIER run's output sits at. If that branch does not refuse, the landing
silently files this run's reader-facing artefact over the previous run's -- and
every sha check still passes, because they only compare copy against original.

Never touches D:\\CIS\\results: the target is a temp dir.
"""
import hashlib
import importlib.util
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "land", os.path.join(HERE, "80_e5p_landing.py"))
land = importlib.util.module_from_spec(spec)
spec.loader.exec_module(land)

D = tempfile.mkdtemp(prefix="_ctl_canon_")
CANON = os.path.join(D, "53_E5p_result.json")
NEW = b'{"run": "rerun", "seconds_total": 2900.0}\n'
OLD = b'{"run": "old", "seconds_total": 2667.1}\n'

bad = 0


def check(name, got, want):
    global bad
    flag = "OK  " if got == want else "BAD "
    if got != want:
        bad += 1
    print("  %s %-56s got=%-14s want=%s" % (flag, name, got, want))


print("scratch: %s\n" % D)

print("-- A: canonical ABSENT --")
rc, line = land.place_canonical(CANON, NEW)
check("A: rc", rc, 0)
check("A: file exists", os.path.exists(CANON), True)
check("A: bytes are the new ones", io.open(CANON, "rb").read() == NEW, True)
check("A: no .part residue left", os.path.exists(CANON + ".part"), False)

print("\n-- B: canonical IDENTICAL --")
rc, line = land.place_canonical(CANON, NEW)
check("B: rc", rc, 0)
check("B: says it already holds these bytes", "already holds" in line, True)
check("B: bytes unchanged", io.open(CANON, "rb").read() == NEW, True)

print("\n-- C: canonical DIFFERENT (the branch that must refuse) --")
io.open(CANON, "wb").write(OLD)
old_sha = hashlib.sha256(OPEN := io.open(CANON, "rb").read()).hexdigest()
rc, line = land.place_canonical(CANON, NEW)
check("C: rc is the refusal code", rc, 4)
check("C: says REFUSING", "REFUSING" in line, True)
check("C: OLD object still there, byte-identical",
      hashlib.sha256(io.open(CANON, "rb").read()).hexdigest(), old_sha)
check("C: the new bytes were NOT placed",
      io.open(CANON, "rb").read() != NEW, True)
check("C: no .part residue left", os.path.exists(CANON + ".part"), False)

shutil.rmtree(D, ignore_errors=True)
check("scratch removed", os.path.exists(D), False)

print("\n%d unexpected result(s)" % bad)
sys.exit(1 if bad else 0)
