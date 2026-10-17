#!/usr/bin/env bash
# probe_mirror.sh -- find the fastest PyPI route reachable from this pod.
#
# Context: measured throughput is ~0.4-0.5 MB/s per connection against both
# mirrors.aliyun.com and github.com, which would put a ~3 GB environment install
# at ~2 hours. Before accepting that, test whether a mirror on the cloud's own
# network (the pod is a UCloud "compshare" instance; its mirror and pod-hosting
# domains are already in the pod's no_proxy list, i.e. expected to be reachable
# the proxy) is materially faster.
#
# Each candidate is timed on a real wheel file, not on an index page, because an
# index page is a few KB and measures latency, not throughput.
set -u
PIP=/usr/local/miniconda3/envs/cis/bin/pip

echo "=== what the image itself trusts (reveals the cloud-internal mirror host) ==="
grep -rhoE "https?://[a-zA-Z0-9._/-]+" /etc/apt/sources.list /etc/apt/sources.list.d/ 2>/dev/null | sort -u | head -12
echo
echo "=== conda channels ==="
grep -E "channels|default_channels|channel_alias" -A3 /root/.condarc /usr/local/miniconda3/.condarc 2>/dev/null | head -20

echo
echo "=== timing each candidate on one real wheel (~35 MB, --no-cache-dir) ==="
try () {
  local label="$1" url="$2"
  rm -rf /tmp/m_dl; mkdir -p /tmp/m_dl
  local t0 t1 sz
  t0=$(date +%s.%N)
  $PIP download --no-cache-dir --no-deps --disable-pip-version-check -q \
      -d /tmp/m_dl --index-url "$url" --trusted-host "$(echo "$url" | awk -F/ '{print $3}')" \
      scipy >/tmp/m.log 2>&1
  local rc=$?
  t1=$(date +%s.%N)
  sz=$(du -sb /tmp/m_dl 2>/dev/null | cut -f1)
  awk -v l="$label" -v a="$t0" -v b="$t1" -v s="${sz:-0}" -v r="$rc" \
    'BEGIN{d=b-a; printf "%-46s rc=%d bytes=%-10d %6.1fs %7.2f MB/s\n", l, r, s, d, (d>0? s/d/1048576 : 0)}'
  [ "$rc" -ne 0 ] && tail -2 /tmp/m.log | sed 's/^/      /'
}

try "aliyun (current default)"          "https://mirrors.aliyun.com/pypi/simple/"
try "ucloud (cloud-internal?)"          "https://mirrors.ucloud.cn/pypi/simple/"
try "aliyun clouds (internal?)"         "https://mirrors.cloud.aliyuncs.com/pypi/simple/"
try "tuna"                              "https://pypi.tuna.tsinghua.edu.cn/simple/"
try "pypi.org (proxy)"                  "https://pypi.org/simple/"

echo
echo "=== proxy-free route to ucloud ==="
export no_proxy="mirrors.ucloud.cn,localhost,127.0.0.1"; export NO_PROXY="$no_proxy"
try "ucloud with proxy excluded"        "https://mirrors.ucloud.cn/pypi/simple/"

rm -rf /tmp/m_dl /tmp/m.log
echo "PROBE_MIRROR_DONE"
