#!/usr/bin/env bash
# probe_d.sh -- pin down (a) which Gwern-hosted DNM archives are actually
# fetchable and how big they are, (b) whether the Internet Archive's *file*
# hosts are reachable even though archive.org itself is blocked, (c) the real
# schema and scale of the Elliptic++ tables we will model on.
set -uo pipefail

OUT=/root/cis/data/_recon
mkdir -p "$OUT"

echo "=========== (a) candidate Gwern DNM artefacts: size probe ==========="
CAND="
https://gwern.net/doc/darknet-market/alphabay/2017-01-28-alphabay.tar.xz
https://gwern.net/doc/darknet-market/2017-01-28-alphabay.tar.xz
https://gwern.net/doc/darknet-market/agora/2017-12-05-philipjames11-darknetmarketplacedataagora20142015.csv.xz
https://gwern.net/doc/darknet-market/2020-01-13-kilos-6dnms-reviews.csv.xz
https://gwern.net/doc/darknet-market/dnm-archive/2021-09-30-munhouwong-kaggle-druglistingdataset.csv.xz
https://gwern.net/doc/darknet-market/silk-road/1/2015-02-02-rossulbrichttrial-303exhibits.tar.xz
https://gwern.net/doc/darknet-market/2016-sarahjamielewis-darkwebdatadumps-hansavalhalla.zip
"
for u in $CAND; do
  printf "  %-95s " "$(basename "$u")"
  curl -sSI -m 30 -L "$u" 2>/dev/null | awk 'BEGIN{IGNORECASE=1} /^HTTP\//{s=$2} /^content-length:/{gsub(/\r/,"");c=$2} /^content-type:/{gsub(/\r/,"");t=$2} END{printf "HTTP %s  %s bytes  %s\n", (s?s:"?"), (c?c:"?"), (t?t:"?")}'
done

echo
echo "=========== (a2) is there a directory index under /doc/darknet-market/ ? ==========="
for u in https://gwern.net/doc/darknet-market/ https://gwern.net/doc/darknet-market/dnm-archive/ https://gwern.net/doc/darknet-market/alphabay/ ; do
  printf "  %-70s " "$u"
  curl -sS -m 30 -L -o /tmp/d.html -w "HTTP %{http_code} %{size_download}B " "$u" 2>/dev/null
  # an autoindex would list many sibling files
  n=$(grep -oE 'href="[^"]+"' /tmp/d.html 2>/dev/null | grep -cE '\.(xz|zip|tar|gz|csv|7z)$')
  echo "archive-links=$n"
done

echo
echo "=========== (b) Internet Archive file hosts reachable? ==========="
for h in https://ia801504.us.archive.org/ https://ia601504.us.archive.org/ https://archive.org/download/ ; do
  printf "  %-45s " "$h"
  curl -s -o /dev/null -m 20 -w "direct=%{http_code} " -L "$h" 2>/dev/null
  curl -s -o /dev/null -m 20 -w "proxy=%{http_code}\n" -L -x http://mihomo.kube-system.svc.cluster.local:7890 "$h" 2>/dev/null
done
echo "  (IA is blocked from this pod; the DNM panel must come from Gwern's own HTTP tree.)"

echo
echo "=========== (c) Elliptic++ schema and scale ==========="
python3 - <<'PYEOF'
import csv, os, glob, collections
root = None
for cand in glob.glob("/root/cis/data/EllipticPlusPlus*"):
    if os.path.isdir(cand):
        root = cand; break
print("  root:", root)
if not root:
    raise SystemExit("  Elliptic++ not staged")
for path in sorted(glob.glob(os.path.join(root, "**", "*.csv"), recursive=True)):
    n = 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        rd = csv.reader(fh)
        try:
            hdr = next(rd)
        except StopIteration:
            print("  %-40s EMPTY" % os.path.basename(path)); continue
        col0 = collections.Counter()
        for r in rd:
            n += 1
            if r: col0[r[0]] += 0
    rel = os.path.relpath(path, root)
    print("  %-62s rows=%-8d cols=%-4d" % (rel, n, len(hdr)))
    print("       header: %s" % (", ".join(hdr[:12]) + ("..." if len(hdr) > 12 else "")))
PYEOF

echo
echo "=========== (d) env build progress ==========="
tail -3 /root/cis/logs/setup_env.log 2>/dev/null | sed 's/^/  /'
echo "  disk: $(df -h /root | tail -1 | awk '{print $4" free"}')"

echo
echo "=========== DONE $(date -Is) ==========="
