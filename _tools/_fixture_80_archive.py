# -*- coding: utf-8 -*-
"""Controls for 80_e5p_landing.archive_once -- all three branches, on the pod.

Run against a scratch directory, never the real artefact paths.

WHY INODE IS THE WITNESS FOR "NO COPY HAPPENED"
-----------------------------------------------
`cp -p` PRESERVES mtime, so a destination's mtime cannot distinguish "copied
over" from "left alone" -- mtime is not a witness, the same way it was not one in
G-62. ctime and inode are not preserved by `cp -p`, so the inode changes iff a
new file was created at that path. That is the property each branch is about:

  A  destination absent          -> copy happens    -> inode CHANGES
  B  destination identical       -> no copy         -> inode UNCHANGED
  C  destination different       -> refuse          -> inode AND sha UNCHANGED

C is the one that matters: it is the branch that protects an existing object
from being overwritten and the new run from being filed under the old object's
name. A guard whose failure branch has never been exercised proves nothing.
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "land", os.path.join(HERE, "80_e5p_landing.py"))
land = importlib.util.module_from_spec(spec)
spec.loader.exec_module(land)

D = "/root/cis/results/_ctl_80"
SRC = D + "/src.txt"
ARCH = D + "/arch.txt"


def pod(cmd):
    rc, out = land.rsc("exec", cmd)
    return rc, out.strip()


def sha(p):
    rc, out = pod("sha256sum %s 2>/dev/null || echo NONE" % p)
    return out.split()[0] if rc == 0 and out else "ERR"


def inode(p):
    rc, out = pod("stat -c '%%i' %s 2>/dev/null || echo NONE" % p)
    return out.split()[0] if rc == 0 and out else "ERR"


def check(name, got, want):
    flag = "OK  " if got == want else "BAD "
    print("  %s %-58s got=%-22s want=%s" % (flag, name, got, want))
    return 0 if got == want else 1


print("scratch: %s\n" % D)
bad = 0
pod("rm -rf %s && mkdir -p %s" % (D, D))
pod("printf 'payload A\\n' > %s" % SRC)

# ---- A: destination absent -> copy ----------------------------------------
print("-- A: destination ABSENT --")
rc, _ = pod("test -e %s && echo yes || echo no" % ARCH)
bad += check("A: archive starts absent", rc, 0)
rca, _ = land.archive_once(SRC, ARCH)
bad += check("A: archive_once rc", rca, 0)
bad += check("A: bytes arrived intact", sha(ARCH), sha(SRC))
inoA = inode(ARCH)
bad += check("A: destination now exists", inoA != "NONE", True)

# ---- B: identical -> no copy ----------------------------------------------
print("\n-- B: destination IDENTICAL --")
rcb, _ = land.archive_once(SRC, ARCH)
bad += check("B: archive_once rc", rcb, 0)
bad += check("B: inode UNCHANGED (no copy was attempted)", inode(ARCH), inoA)
bad += check("B: content still matches", sha(ARCH), sha(SRC))

# ---- C: different -> REFUSE -----------------------------------------------
print("\n-- C: destination DIFFERENT (the branch that must exist) --")
pod("printf 'payload B -- a different run\\n' > %s" % SRC)
sha_before, ino_before = sha(ARCH), inode(ARCH)
rcc, _ = land.archive_once(SRC, ARCH)
bad += check("C: archive_once rc is the refusal code", rcc, 4)
bad += check("C: destination sha UNCHANGED", sha(ARCH), sha_before)
bad += check("C: destination inode UNCHANGED", inode(ARCH), ino_before)

print("\ncleanup")
pod("rm -rf %s" % D)
rc, out = pod("test -e %s && echo STILL-THERE || echo gone" % D)
bad += check("scratch removed", out, "gone")

print("\n%d unexpected result(s)" % bad)
sys.exit(1 if bad else 0)
