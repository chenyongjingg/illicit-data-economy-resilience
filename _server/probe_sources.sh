#!/usr/bin/env bash
# probe_sources.sh -- enumerate what the DNM/illicit-trade data sources actually
# contain, so the experimental design is built on verified coverage rather than
# on the assumed coverage in the sprint plan.
set -uo pipefail

OUT=/root/cis/data/_recon
mkdir -p "$OUT"

fetch() {  # fetch <url> <outfile>
  local url="$1" out="$2"
  if [ -s "$out" ]; then echo "  cached $out"; return 0; fi
  curl -sS -m 120 -L --retry 3 -o "$out" "$url" 2>&1 | sed 's/^/  curl: /'
  local sz; sz=$(stat -c%s "$out" 2>/dev/null || echo 0)
  echo "  -> $(basename "$out") ${sz} bytes"
}

echo "=========== 1. Gwern dnm-archive directory index ==========="
fetch "https://gwern.net/doc/darknet-market/dnm-archive/index" "$OUT/gwern_dnm_index.html"
# Extract hrefs without python-quoting hazards.
grep -oE 'href="[^"]+"' "$OUT/gwern_dnm_index.html" \
  | sed -e 's/^href="//' -e 's/"$//' \
  | grep -viE '\.(css|js|png|jpg|jpeg|svg|woff2?|ico)$' \
  | sort -u > "$OUT/gwern_dnm_index.links"
echo "  links: $(wc -l < "$OUT/gwern_dnm_index.links")"
head -60 "$OUT/gwern_dnm_index.links"

echo
echo "=========== 2. Gwern archive size hints ==========="
# HEAD the biggest-looking artefacts to learn real sizes before downloading.
for l in $(grep -iE '\.(tar\.xz|tar\.gz|zip|xz|zst)$' "$OUT/gwern_dnm_index.links" | head -40); do
  case "$l" in
    http*) u="$l" ;;
    /*)    u="https://gwern.net$l" ;;
    *)     u="https://gwern.net/doc/darknet-market/dnm-archive/$l" ;;
  esac
  printf "  %-90s " "$u"
  curl -sSI -m 25 -L "$u" | awk 'BEGIN{IGNORECASE=1} /^content-length:/{gsub(/\r/,"");c=$2} /^HTTP\//{s=$2} END{printf "%s bytes (HTTP %s)\n", (c?c:"?"), (s?s:"?")}'
done | head -40

echo
echo "=========== 3. Internet Archive item listing ==========="
fetch "https://archive.org/metadata/gwern-dnm-archive" "$OUT/ia_metadata.json"
python3 - "$OUT/ia_metadata.json" <<'PYEOF'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception as e:
    print("  metadata parse failed:", e); sys.exit(0)
print("  identifier :", d.get("metadata", {}).get("identifier"))
print("  title      :", d.get("metadata", {}).get("title"))
files = d.get("files", [])
print("  n files    :", len(files))
tot = sum(int(f.get("size", 0) or 0) for f in files)
print("  total size : %.2f GB" % (tot / 1e9))
for f in sorted(files, key=lambda f: -int(f.get("size", 0) or 0))[:25]:
    print("   %12d  %s" % (int(f.get("size", 0) or 0), f.get("name")))
PYEOF

echo
echo "=========== 4. abuse.ch feed shapes ==========="
for u in \
  "https://urlhaus.abuse.ch/downloads/csv/" \
  "https://threatfox.abuse.ch/export/csv/full/" \
  "https://feodotracker.abuse.ch/downloads/ipblocklist.csv" ; do
  n=$(basename "$u")
  fetch "$u" "$OUT/abusech_$n"
  echo "  --- $n head ---"
  head -5 "$OUT/abusech_$n" | sed 's/^/    /'
  echo "  --- $n lines: $(wc -l < "$OUT/abusech_$n") ---"
done

echo
echo "=========== 5. Elliptic++ repo ==========="
fetch "https://api.github.com/repos/git-disl/EllipticPlusPlus/contents/" "$OUT/ellipticpp_root.json"
python3 - "$OUT/ellipticpp_root.json" <<'PYEOF'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception as e:
    print("  parse failed:", e); sys.exit(0)
if isinstance(d, dict):
    print("  ", d.get("message", d)); sys.exit(0)
for it in d:
    print("   %-8s %10s  %s" % (it["type"], it.get("size", "-"), it["name"]))
PYEOF

echo
echo "=========== DONE $(date -Is) ==========="
