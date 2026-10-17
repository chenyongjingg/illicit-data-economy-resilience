#!/usr/bin/env bash
# probe_c.sh -- third pass: work around the pod's missing tooling (no git, no
# unzip) and its direct-route blocks (archive.org resets TLS unless proxied).
set -uo pipefail

OUT=/root/cis/data/_recon
mkdir -p "$OUT" "$OUT/abusech"
echo "=========== env build progress ==========="
tail -4 /root/cis/logs/setup_env.log 2>/dev/null | sed 's/^/  /'
echo "  pip procs: $(pgrep -fc 'pip install' 2>/dev/null || echo 0)"

echo
echo "=========== url route tests (direct vs proxy) ==========="
for u in https://archive.org/metadata/gwern-dnm-archive https://web.archive.org/ ; do
  d=$(curl -s -o /dev/null -m 20 -w "%{http_code}" -L "$u" 2>/dev/null)
  p=$(curl -s -o /dev/null -m 20 -w "%{http_code}" -L -x http://mihomo.kube-system.svc.cluster.local:7890 "$u" 2>/dev/null)
  echo "  direct=$d proxy=$p  $u"
done
echo "  proxy env present: $(env | grep -ci proxy)"

echo
echo "=========== unzip abuse.ch feeds via python zipfile ==========="
python3 - <<'PYEOF'
import zipfile, os, io, collections
base = "/root/cis/data/_recon/abusech"
for name in ("urlhaus_full", "threatfox_full"):
    z = os.path.join(base, name + ".zip")
    if not os.path.exists(z):
        print("  %s: missing" % name); continue
    with open(z, "rb") as fh:
        head = fh.read(4)
    if head[:2] != b"PK":
        print("  %s: not a zip (head=%r)" % (name, head)); continue
    with zipfile.ZipFile(z) as zf:
        for info in zf.infolist():
            out = os.path.join(base, name + "__" + os.path.basename(info.filename))
            with zf.open(info) as src, open(out, "wb") as dst:
                dst.write(src.read())
            print("  extracted %s (%d bytes)" % (out, os.path.getsize(out)))
PYEOF

echo
echo "=========== abuse.ch schemas ==========="
python3 - <<'PYEOF'
import glob, os, collections, datetime
for f in sorted(glob.glob("/root/cis/data/_recon/abusech/*__*")):
    if f.endswith(".zip"):
        continue
    rows, hdr, comments = [], None, []
    with open(f, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("#"):
                comments.append(line.rstrip()); continue
            if not line.strip():
                continue
            if hdr is None:
                hdr = line.rstrip()
            rows.append(line.rstrip())
    print("\n  === %s ===" % os.path.basename(f))
    print("    rows: %d" % len(rows))
    for c in comments[:6]:
        print("      %s" % c)
    print("    header: %s" % (hdr[:220] if hdr else "-"))
    if rows:
        print("    row0  : %s" % rows[0][:220])
        print("    rowN  : %s" % rows[-1][:220])
PYEOF

echo
echo "=========== Elliptic++ via codeload tarball (no git needed) ==========="
cd /root/cis/data
if [ ! -d EllipticPlusPlus-master ]; then
  curl -sS -m 300 -L --retry 3 -o EllipticPlusPlus.tar.gz \
    "https://codeload.github.com/git-disl/EllipticPlusPlus/tar.gz/refs/heads/main" \
    || echo "  codeload failed"
  echo "  tarball: $(stat -c%s EllipticPlusPlus.tar.gz 2>/dev/null || echo 0) bytes"
  python3 -c "import tarfile;tarfile.open('/root/cis/data/EllipticPlusPlus.tar.gz').extractall('/root/cis/data')" \
    && echo "  extracted"
fi
echo "  --- contents ---"
find /root/cis/data -maxdepth 3 -name 'EllipticPlusPlus*' -not -path '*/.git/*' 2>/dev/null | head
find /root/cis/data -maxdepth 2 -type d -name 'EllipticPlusPlus*' -exec du -sh {} \; 2>/dev/null
find /root/cis/data -maxdepth 3 -type f -path '*Elliptic*' 2>/dev/null | head -30

echo
echo "=========== DONE $(date -Is) ==========="
