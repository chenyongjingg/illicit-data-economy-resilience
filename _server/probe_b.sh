#!/usr/bin/env bash
# probe_b.sh -- second reconnaissance pass:
#   (a) find the Internet Archive item that holds the DNM archive and learn its
#       file granularity (can we fetch a few markets instead of all 50GB?),
#   (b) unpack the abuse.ch feeds and report their real schemas + time coverage,
#   (c) stage the Elliptic++ datasets.
set -uo pipefail

OUT=/root/cis/data/_recon
mkdir -p "$OUT"

echo "=========== (a) Internet Archive: locate DNM archive item ==========="
curl -sS -m 60 -L --retry 4 --retry-delay 3 \
  "https://archive.org/advancedsearch.php?q=gwern+AND+darknet&fl%5B%5D=identifier&fl%5B%5D=title&fl%5B%5D=item_size&fl%5B%5D=downloads&rows=25&output=json" \
  -o "$OUT/ia_search.json"
python3 - "$OUT/ia_search.json" <<'PYEOF'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception as e:
    print("  parse failed:", e); sys.exit(0)
docs = d.get("response", {}).get("docs", [])
print("  hits:", len(docs))
for r in docs:
    print("   %-40s %14s  %s" % (r.get("identifier"), r.get("item_size", "?"), str(r.get("title"))[:70]))
PYEOF

echo
echo "  --- metadata for the most likely identifier(s) ---"
for id in gwern-dnm-archive dnm-archive darknet-market-archive; do
  echo "  [$id]"
  curl -sS -m 60 -L --retry 3 --retry-delay 2 "https://archive.org/metadata/$id" -o "$OUT/ia_$id.json" || true
  python3 - "$OUT/ia_$id.json" "$id" <<'PYEOF'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception as e:
    print("    no metadata:", e); raise SystemExit(0)
if not d or "metadata" not in d:
    print("    empty/absent"); raise SystemExit(0)
md = d["metadata"]
files = d.get("files", [])
tot = sum(int(f.get("size", 0) or 0) for f in files)
print("    title: %s" % str(md.get("title"))[:80])
print("    files: %d   total: %.2f GB" % (len(files), tot/1e9))
for f in sorted(files, key=lambda x: -int(x.get("size", 0) or 0))[:30]:
    print("      %14d  %s" % (int(f.get("size", 0) or 0), f.get("name")))
PYEOF
done

echo
echo "=========== (b) abuse.ch feeds: unzip + schema + time coverage ==========="
mkdir -p "$OUT/abusech"
for pair in "https://urlhaus.abuse.ch/downloads/csv/ urlhaus_full" \
            "https://threatfox.abuse.ch/export/csv/full/ threatfox_full"; do
  set -- $pair
  url="$1"; name="$2"
  z="$OUT/abusech/$name.zip"
  [ -s "$z" ] || curl -sS -m 180 -L --retry 3 -o "$z" "$url"
  echo "  $name: $(stat -c%s "$z" 2>/dev/null) bytes"
  ( cd "$OUT/abusech" && unzip -o -q "$z" 2>/dev/null || echo "    (not a zip)" )
  ls -la "$OUT/abusech" | head
done

echo
echo "  --- urlhaus csv.txt ---"
U="$OUT/abusech/csv.txt"; [ -s "$U" ] || U=$(find "$OUT/abusech" -name 'csv.txt' | head -1)
if [ -s "$U" ]; then
  echo "    size $(stat -c%s "$U"), data lines $(grep -vc '^#' "$U")"
  echo "    header/comment sample:"; grep '^#' "$U" | head -12 | sed 's/^/      /'
  echo "    first data rows:"; grep -v '^#' "$U" | head -3 | sed 's/^/      /'
  echo "    distinct url_status values:"
  grep -v '^#' "$U" | awk -F'","' '{print $2}' | sort | uniq -c | sort -rn | head -10 | sed 's/^/      /'
fi

echo
echo "  --- threatfox full.csv ---"
T="$OUT/abusech/full.csv"
if [ -s "$T" ]; then
  echo "    size $(stat -c%s "$T"), data lines $(grep -vc '^#' "$T")"
  grep '^#' "$T" | head -8 | sed 's/^/      /'
  echo "    first data rows:"; grep -v '^#' "$T" | head -3 | sed 's/^/      /'
fi

echo
echo "=========== (c) Elliptic++ staging ==========="
cd /root/cis/data
if [ ! -d EllipticPlusPlus ]; then
  git clone --depth 1 https://github.com/git-disl/EllipticPlusPlus.git 2>&1 | tail -3
fi
echo "  --- tree ---"
find EllipticPlusPlus -maxdepth 2 -not -path '*/.git/*' | head -40
echo "  --- sizes ---"
du -sh EllipticPlusPlus/* 2>/dev/null | head -20

echo
echo "=========== DONE $(date -Is) ==========="
