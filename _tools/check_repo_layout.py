"""Give the numbers in README.md and NOT_REDISTRIBUTED.md a reader.

Both files state counts.  A count in a file is a claim, and a claim nothing
reads is a claim that drifts -- the previous README's layout table named five
directories that did not exist in the repository it was describing.  This
recomputes every count from disk and fails if either document disagrees.

    python _tools/check_repo_layout.py
    echo $?        # 0 = every stated number matches the tree

Three independent things are checked:

  1. the layout table in README.md (files per path)
  2. the census arithmetic in NOT_REDISTRIBUTED.md, which is recovered from the
     sha256 census itself -- every census entry is either present here with the
     same digest, or withheld and named as withheld.  A census entry that is
     neither is an entry the repository dropped without saying so.  A withheld
     entry whose bytes ship under another name is counted and named separately:
     the path is absent, but "not redistributed" would be false of the content.
  3. the upload bundle in manuscript/ against the source tree on disk.  The
     manuscript ships in two forms produced by different steps, so nothing binds
     them unless something does -- a zip built from a stale source compiles
     cleanly and looks right.
"""
import hashlib, os, re, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fail = []


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def walk_files():
    """Every shipped file, as a repo-relative posix path."""
    for dirpath, dirnames, filenames in os.walk(REPO):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for f in filenames:
            yield os.path.relpath(os.path.join(dirpath, f), REPO).replace("\\", "/")


# ------------------------------------------------------------------ 1. layout
print("=" * 68)
print("1. README.md layout table")
print("=" * 68)
readme = open(os.path.join(REPO, "README.md"), encoding="utf-8").read()
row = re.compile(r"^\| `([^`]+)` \| [^|]*\| (\d+) \|$", re.M)
rows = row.findall(readme)
if not rows:
    fail.append("README.md: layout table not found (nothing was checked)")
checked = 0
for path, stated in rows:
    stated = int(stated)
    target = os.path.join(REPO, path.replace("/", os.sep))
    if not os.path.exists(target):
        fail.append("README.md lists %-34s which does not exist" % path)
        continue
    actual = sum(1 for _ in walk_files() if _.startswith(path.rstrip("/") + "/")
                 or _ == path)
    ok = "ok " if actual == stated else "** FAIL **"
    if actual != stated:
        fail.append("README.md says %s has %d files; disk has %d"
                    % (path, stated, actual))
    print("  %-36s stated %4d  disk %4d  %s" % (path, stated, actual, ok))
    checked += 1
print("  rows checked: %d" % checked)

# --------------------------------------------------------------- 2. census
print()
print("=" * 68)
print("2. NOT_REDISTRIBUTED.md census arithmetic")
print("=" * 68)
mani = {}
mani_path = os.path.join(REPO, "manuscript", "supplementary",
                         "Additional file 2.txt")
for line in open(mani_path, encoding="utf-8"):
    if line.strip():
        d, _, p = line.rstrip("\n").partition("  ")
        mani[p.replace("\\", "/")] = d

shipped, mismatch, withheld = [], [], []
for p, digest in sorted(mani.items()):
    f = os.path.join(REPO, p.replace("/", os.sep))
    if not os.path.isfile(f):
        withheld.append(p)
    elif sha256(f) == digest:
        shipped.append(p)
    else:
        mismatch.append(p)

note = open(os.path.join(REPO, "NOT_REDISTRIBUTED.md"), encoding="utf-8").read()


def doc_number(pattern, label):
    """Pull a stated count out of NOT_REDISTRIBUTED.md.  A pattern that stops
    matching must fail loudly -- silently returning None would turn a document
    that no longer says anything into a document that passes."""
    m = re.search(pattern, note)
    if not m:
        fail.append("NOT_REDISTRIBUTED.md: could not read the '%s' count "
                    "(pattern %r no longer matches)" % (label, pattern))
        return -1
    return int(m.group(1))


table = {
    "manifest entries": (len(mani),
                         doc_number(r"study tree\*\* -- the (\d+) result artifacts",
                                    "manifest entries")),
    "present and byte-identical": (len(shipped),
                                   doc_number(r"present here and byte-identical\*\* \| \*\*(\d+)\*\*",
                                              "present and byte-identical")),
    "hash disagreements": (len(mismatch),
                           doc_number(r"\| hash disagreements \| \*\*(\d+)\*\*",
                                      "hash disagreements")),
}
for name, (actual, doc) in table.items():
    ok = "ok " if actual == doc else "** FAIL **"
    if actual != doc:
        fail.append("NOT_REDISTRIBUTED.md says %s = %d; recomputed %d"
                    % (name, doc, actual))
    print("  %-30s recomputed %4d  document %4d  %s" % (name, actual, doc, ok))

# every census entry must be accounted for: present, or named as withheld
named_as_withheld = all(("    " + p) in note for p in withheld)
print("  %-30s %s" % ("withheld entries all named",
                      "ok " if named_as_withheld else "** FAIL **"))
if not named_as_withheld:
    missing = [p for p in withheld if ("    " + p) not in note][:5]
    fail.append("withheld but not listed in NOT_REDISTRIBUTED.md: %s" % missing)

conserved = len(shipped) + len(withheld) == len(mani)
print("  %-30s %s  (%d = %d + %d)"
      % ("census conserved", "ok " if conserved else "** FAIL **",
         len(mani), len(shipped), len(withheld)))
if not conserved:
    fail.append("census not conserved")

# A withheld path whose content is here under another name.  The path really is
# absent, so it is withheld by the census's own criterion -- but calling its
# bytes withheld is a claim one sha256sum refutes, so the document names the
# exceptions and this recomputes them.  A count stated and never recomputed is
# how the previous README's layout table came to name five directories that did
# not exist.
shipped_by_digest = {}
for p in shipped:
    shipped_by_digest.setdefault(mani[p], []).append(p)
dupes = sorted(p for p in withheld if mani[p] in shipped_by_digest)
stated = doc_number(r"### 2\.1 Of those, (\d+) whose bytes are here after all",
                    "duplicate-with-shipped")
ok = "ok " if stated == len(dupes) else "** FAIL **"
if stated != len(dupes):
    fail.append("NOT_REDISTRIBUTED.md says %d withheld entries ship under another "
                "name; recomputed %d (%s)" % (stated, len(dupes), dupes or "-"))
print("  %-30s recomputed %4d  document %4d  %s"
      % ("bytes shipped elsewhere", len(dupes), stated, ok))
# and each one must be named with the file that carries it
for p in dupes:
    twin = shipped_by_digest[mani[p]][0]
    bound = ("    " + p) in note and ("        same bytes as  " + twin) in note
    if not bound:
        fail.append("duplicate %s is not listed with its twin %s" % (p, twin))
print("  %-30s %s" % ("each named with its twin",
                      "ok " if all(("    " + p) in note
                                   and ("        same bytes as  "
                                        + shipped_by_digest[mani[p]][0]) in note
                                   for p in dupes) else "** FAIL **"))

# ------------------------------------------------- 3. upload bundle vs source
# The manuscript ships in two forms: the LaTeX source here, and the zip that was
# handed to the journal.  They are produced separately, so nothing binds them
# unless something does -- a zip built from a stale source tree compiles fine and
# looks right.  This asserts every member of the zip is byte-identical to the
# same-named file on disk.
print()
print("=" * 68)
print("3. manuscript/manuscript_latex.zip vs manuscript/ on disk")
print("=" * 68)
import zipfile

zpath = os.path.join(REPO, "manuscript", "manuscript_latex.zip")
if not os.path.isfile(zpath):
    fail.append("manuscript/manuscript_latex.zip is missing")
    print("  ** FAIL **  the upload bundle is not here at all")
else:
    with zipfile.ZipFile(zpath) as z:
        names = [i.filename for i in z.infolist()]
        bad = []
        for n in names:
            p = os.path.join(REPO, "manuscript", n.replace("/", os.sep))
            if not os.path.isfile(p):
                bad.append((n, "absent from manuscript/"))
            elif hashlib.sha256(z.read(n)).hexdigest() != sha256(p):
                bad.append((n, "differs from manuscript/" + n))
        print("  members in bundle : %d" % len(names))
        print("  byte-identical    : %d" % (len(names) - len(bad)))
        for n, why in bad:
            print("  ** FAIL **  %s %s" % (n, why))
            fail.append("upload bundle %s" % why)
        # and the reverse: a source file the bundle forgot to carry
        covered = {n for n in names}
        expected = {"main.tex", "refs.bib", "main.bbl"}
        expected |= {"sections/" + f for f in
                     sorted(os.listdir(os.path.join(REPO, "manuscript", "sections")))}
        missing = sorted(expected - covered)
        print("  source files not in bundle: %d %s" % (len(missing), missing or ""))
        if missing:
            fail.append("upload bundle omits %s" % missing)

# ------------------------------------------------------------------ verdict
print()
print("=" * 68)
if fail:
    print("FAILURES (%d)" % len(fail))
    for f in fail:
        print("  - %s" % f)
    sys.exit(1)
print("ALL CHECKS PASS")
