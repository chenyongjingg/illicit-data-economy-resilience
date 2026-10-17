#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rsc.py -- remote shell client for the CIS 4090 pod (paramiko).

Minimal, auditable remote executor used to drive the experiment pipeline on the
4090 server while keeping local (hotspot) bandwidth usage near zero.

Usage
  python rsc.py exec "<shell command>"          # run, stream stdout+stderr
  python rsc.py bg   "<shell command>" <log>    # nohup in background, print pid
  python rsc.py put  <local path> <remote path>
  python rsc.py get  <remote path> <local path>
  python rsc.py stat                          # one-shot probe of the pod
"""
import base64
import hashlib
import json
import os
import posixpath
import re
import socket
import sys
import time

import paramiko

# Required from the environment. Deliberately NO default: a host
# baked into a source file is a host that ships with the code.
HOST = os.environ["CIS_HOST"]

# The local console is GBK (zh-CN Windows). Remote output is UTF-8 and routinely
# contains CJK and accented text, so decode/print must not be left to the default
# codec -- otherwise a successful remote run looks like a local crash.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - only fails on exotic streams
        pass
# Required from the environment, for the same reason as HOST: a port
# left as a default is half of a retired endpoint. A run that sets
# HOST but not PORT must fail loudly, not connect nowhere quietly.
PORT = int(os.environ["CIS_PORT"])
USER = os.environ.get("CIS_USER", "root")
# Required from the environment. The previous revision carried the
# pod password as this default, which put a live credential into
# every copy of the delivery package (see C-181 in the ledger).
PASS = os.environ["CIS_PASS"]

# Keepalive + retries matter here: the local link is a phone hotspot and its
# resolver (10.36.38.46) drops requests under load, which surfaces as a
# confusing "[Errno 11001] getaddrinfo failed" deep inside paramiko even though
# the name resolves fine when queried on its own. So we resolve once ourselves,
# with retries, and cache the answer to disk; SSH then dials the IP directly.
CONNECT_TRIES = 5
CONNECT_TIMEOUT = 25
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".rsc_cache.json")


def resolve(host):
    if os.environ.get("CIS_NO_DNS_CACHE") == "1":
        pass
    else:
        try:
            with open(CACHE, "r", encoding="utf-8") as fh:
                cached = json.load(fh)
            if cached.get("host") == host and cached.get("ip"):
                return cached["ip"]
        except Exception:  # noqa: BLE001 - cache is an optimisation only
            pass
    last = None
    for attempt in range(6):
        try:
            infos = socket.getaddrinfo(host, PORT, socket.AF_UNSPEC, socket.SOCK_STREAM)
            ip = infos[0][4][0]
            try:
                with open(CACHE, "w", encoding="utf-8") as fh:
                    json.dump({"host": host, "ip": ip, "at": time.time()}, fh)
            except Exception:  # noqa: BLE001
                pass
            return ip
        except Exception as e:  # noqa: BLE001
            last = e
            sys.stderr.write("[rsc] dns attempt %d failed: %s\n" % (attempt + 1, e))
            time.sleep(1.5 * (attempt + 1))
    raise SystemExit("[rsc] cannot resolve %s -- %s" % (host, last))


def connect():
    ip = resolve(HOST)
    last = None
    for attempt in range(CONNECT_TRIES):
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(
                ip,
                port=PORT,
                username=USER,
                password=PASS,
                timeout=CONNECT_TIMEOUT,
                banner_timeout=CONNECT_TIMEOUT,
                auth_timeout=CONNECT_TIMEOUT,
                look_for_keys=False,
                allow_agent=False,
            )
            tr = c.get_transport()
            tr.set_keepalive(30)
            return c
        except Exception as e:  # noqa: BLE001 - report and retry
            last = e
            sys.stderr.write("[rsc] connect attempt %d failed: %s\n" % (attempt + 1, e))
            time.sleep(2 * (attempt + 1))
    raise SystemExit("[rsc] cannot connect to %s (%s):%d -- %s" % (HOST, ip, PORT, last))


def run(cmd, timeout=None, quiet=False):
    """Run cmd in a login shell; return (rc, stdout, stderr) as str."""
    c = connect()
    try:
        full = "bash -lc " + shq(cmd)
        stdin, stdout, stderr = c.exec_command(full, timeout=timeout, get_pty=False)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        rc = stdout.channel.recv_exit_status()
        if not quiet:
            sys.stdout.write(out)
            if err:
                sys.stdout.write(err)
        return rc, out, err
    finally:
        c.close()


def shq(s):
    return "'" + s.replace("'", "'\"'\"'") + "'"


_MSYS_RE = re.compile(r"^/([a-zA-Z])(/.*)?$")
# Git-Bash rewrites any argument that looks like a POSIX path into a Windows one
# before a native binary ever sees it: "/root/cis/x" arrives as
# "C:/Program Files/Git/root/cis/x". Set MSYS_NO_PATHCONV=1 at the call site, and
# keep this sanitiser as the belt-and-braces fallback.
_MSYS_ROOT_RE = re.compile(
    r"^[A-Za-z]:[/\\](?:Program Files(?: \(x86\))?[/\\]Git|msys64)[/\\]", re.IGNORECASE
)


def remote_path(p):
    """Undo Git-Bash POSIX->Windows argument mangling for a remote path."""
    m = _MSYS_ROOT_RE.match(p)
    if m:
        stripped = "/" + p[m.end():].replace("\\", "/")
        sys.stderr.write("[rsc] WARNING: remote path was MSYS-mangled (%s) -> %s\n" % (p, stripped))
        return stripped
    if not p.startswith("/"):
        raise SystemExit(
            "[rsc] refusing remote path %r: must be absolute POSIX. "
            "If Git Bash rewrote it, prefix the command with MSYS_NO_PATHCONV=1." % p
        )
    return p


def local_path(p):
    """Translate a Git-Bash style path (/d/CIS/x) into a Windows path (D:\\CIS\\x).

    Windows Python resolves "/d/CIS/x" against the *current drive*, giving
    "D:\\d\\CIS\\x" -- a silently different file. Always run local paths through
    this before handing them to open()/os.stat()/sftp.
    """
    m = _MSYS_RE.match(p)
    if m:
        drive = m.group(1).upper()
        rest = (m.group(2) or "").lstrip("/")
        return drive + ":\\" + rest.replace("/", "\\")
    return p


def bg(cmd, log):
    """Launch cmd fully detached from the SSH channel; print its pid.

    setsid + </dev/null + closing every inherited descriptor is what makes the
    exec channel return immediately. Without them the channel stays open for as
    long as the remote job lives, and a caller that just wants to start a
    long experiment blocks until the experiment ends.

    Two failure modes were observed here, both silent, and both are guarded now:

    1. The log file did not exist afterwards and no process was running -- yet a
       pid had been printed. The channel is torn down microseconds after `echo
       $!`, and the backgrounded job is still in the session's process group at
       that instant (`setsid` only takes effect once the fork+exec completes), so
       sshd's teardown killed it before it ever opened its own log. The symptom
       is the worst kind: a launcher that reports success and starts nothing.
       Fix: create the log synchronously in the *outer* shell first, and hold the
       channel open briefly so the detach wins the race.
    2. A caller could not tell "started" from "started and immediately died".
       The pid alone never proved anything; `bg` now reports whether the process
       is still alive a few seconds in.
    """
    # The log path is a bare `/root/...` argument, which is precisely the shape
    # Git Bash rewrites into `C:/Program Files/Git/root/...`. That path does not
    # exist on Linux, so the redirect fails and the job dies before it starts --
    # while still printing a plausible pid. push/pull already sanitise; bg did
    # not, and that was the whole bug.
    log = remote_path(log)
    # Append an exit marker, so completion is a fact recorded in the log rather
    # than an inference from process liveness. `kill -0 $!` is not a valid check
    # here: `setsid` forks, so the backgrounded shell can exit while the real
    # work continues under a different pid -- and a *successful* short job is
    # then indistinguishable from a job that was killed at launch. That is
    # exactly how this reported "DIED" for an E1 run that had in fact finished
    # cleanly and written both of its output files.
    mark = "echo RSC_EXIT=$? >> %s" % shq(log)
    inner = (
        ": > {log}; cd /root && setsid nohup bash -c {cmdq} </dev/null >>{log} 2>&1"
        " & echo RSC_BG_PID=$!"
    ).format(log=shq(log), cmdq=shq("( %s ); %s" % (cmd, mark)))

    # 3. The channel was never actually non-blocking. `run()` reads stdout to
    #    EOF, and the detached job inherits a dup of that pipe, so sshd keeps the
    #    channel open until the *job* finishes -- meaning `bg` blocked for the
    #    whole experiment, exactly what it exists to avoid. A timing test that
    #    measures elapsed time *inside* the remote shell reports "took 1s" and
    #    hides this, because the remote shell really did exit in 1s; it is the
    #    local round trip that hangs. So: read only until the pid line arrives,
    #    then abandon the channel and close the transport.
    c = connect()
    pid = None
    try:
        full = "bash -lc " + shq(inner)
        _in, stdout, _err = c.exec_command(full, timeout=30, get_pty=False)
        ch = stdout.channel
        buf = b""
        t0 = time.time()
        while time.time() - t0 < 20:
            if ch.recv_ready():
                buf += ch.recv(65536)
                if b"RSC_BG_PID=" in buf:
                    break
            elif ch.exit_status_ready() and not ch.recv_ready():
                break
            else:
                time.sleep(0.2)
        for line in buf.decode("utf-8", "replace").splitlines():
            if "RSC_BG_PID=" in line:
                pid = line.split("RSC_BG_PID=")[-1].strip()
    finally:
        c.close()

    if pid is None:
        raise SystemExit("[rsc] bg: launcher produced no pid; nothing was started")

    # 4. Verify on a *fresh* connection, which also proves the job outlived the
    #    launching channel. The log's exit marker is the authoritative signal:
    #    it distinguishes "finished" from "killed before it could finish", and
    #    neither of those is "started successfully".
    time.sleep(3)
    token = os.path.basename(log)
    state, detail = "unknown", ""
    for _ in range(3):
        rc, out, _ = run("tail -c 4000 %s 2>/dev/null | grep -o 'RSC_EXIT=[0-9]*' "
                         "| tail -1" % shq(log), quiet=True)
        if "RSC_EXIT=" in out:
            state, detail = "finished", out.strip()
            break
        rc, out, _ = run("pgrep -f %s | head -1" % shq(token), quiet=True)
        if out.strip():
            state, detail = "running", "live pid %s" % out.strip()
            break
        time.sleep(3)

    if state == "finished":
        print("[rsc] bg %s log=%s" % (detail, log))
    elif state == "running":
        print("[rsc] bg launched (%s, verified on a new connection) log=%s"
              % (detail, log))
    else:
        rc, out, _ = run("tail -20 %s 2>/dev/null" % shq(log), quiet=True)
        sys.stderr.write("[rsc] bg: no exit marker and no live process -- the job "
                         "was killed before completing. Log tail:\n%s\n" % out)
    return pid
    return pid


def runscript(local_script, args=None, timeout=None):
    """Push a local script to the pod and execute it there.

    Everything non-trivial lives in a file rather than an inline command: shell
    quoting survives one hop through Git Bash and one through paramiko, but not
    two, and a silently mangled one-liner is indistinguishable from a real
    negative result. A file is auditable afterwards, too.
    """
    args = args or []
    base = os.path.basename(local_path(local_script))
    remote = "/root/cis/_server/" + base
    push(local_script, remote)
    # Pick the interpreter from the extension. Assuming bash feeds a .py file to
    # the shell, which fails with "syntax error near unexpected token" on the
    # first docstring apostrophe -- a message that names a line of prose rather
    # than the real mistake.
    # Experiment code must run in the `cis` conda env. The image's bare
    # `python3` is a different interpreter with no scientific stack, and the
    # resulting ModuleNotFoundError looks like a missing dependency rather than
    # the wrong interpreter.
    interp = {"py": os.environ.get("CIS_PY",
                                   "/usr/local/miniconda3/envs/cis/bin/python")
              }.get(base.rsplit(".", 1)[-1].lower(), "bash")
    cmd = "cd /root/cis && %s %s %s" % (interp, shq(remote), " ".join(shq(a) for a in args))
    return run(cmd, timeout=timeout)


def _sha256_remote(path):
    rc, out, _ = run("sha256sum %s | cut -d' ' -f1" % shq(path), quiet=True)
    return out.strip() if rc == 0 else None


def push(local, remote):
    """Upload a file with base64-over-exec and verify by SHA-256 on both ends.

    Transport is an exec-channel base64 pipe rather than SFTP. Note what the
    SHA-256 check does and does not prove: it proves the bytes that landed at
    `remote` are the bytes we sent. It says nothing about whether `remote` was
    the path we *meant* -- so the path is asserted absolute-POSIX above, and a
    mis-mangled upload would still have round-tripped cleanly against its own
    wrong destination.
    """
    remote = remote_path(remote)
    lp = local_path(local)
    with open(lp, "rb") as fh:
        data = fh.read()
    local_sha = hashlib.sha256(data).hexdigest()
    b64 = base64.b64encode(data).decode("ascii")

    parent = posixpath.dirname(remote)
    if parent:
        run("mkdir -p %s" % shq(parent), quiet=True)
    tmp = remote + ".b64tmp"
    delim = "RSCB64_%s" % os.urandom(8).hex()
    script = "cat > %s <<'%s'\n%s\n%s\nbase64 -d %s > %s && rm -f %s && sha256sum %s" % (
        shq(tmp), delim, b64, delim, shq(tmp), shq(remote), shq(tmp), shq(remote),
    )
    rc, out, err = run(script, quiet=True)
    remote_sha = out.strip().split(" ")[0] if out.strip() else None
    if rc != 0 or remote_sha != local_sha:
        raise SystemExit(
            "[rsc] push FAILED %s -> %s (rc=%s local=%s remote=%s)\n%s"
            % (lp, remote, rc, local_sha, remote_sha, err)
        )
    print("[rsc] push ok %s -> %s sha256=%s" % (lp, remote, local_sha[:16]))


def pull(remote, local):
    """Download a file with base64-over-exec and verify by SHA-256 on both ends."""
    remote = remote_path(remote)
    lp = local_path(local)
    rc, out, err = run("base64 -w0 %s" % shq(remote), quiet=True)
    if rc != 0:
        raise SystemExit("[rsc] pull FAILED reading %s: %s" % (remote, err))
    try:
        data = base64.b64decode(out.strip())
    except Exception as e:  # noqa: BLE001
        raise SystemExit("[rsc] pull FAILED decoding %s: %s" % (remote, e))
    rc2, out2, _ = run("sha256sum %s | cut -d' ' -f1" % shq(remote), quiet=True)
    remote_sha = out2.strip()
    local_sha = hashlib.sha256(data).hexdigest()
    if remote_sha and remote_sha != local_sha:
        raise SystemExit(
            "[rsc] pull FAILED checksum %s (remote=%s local=%s)"
            % (remote, remote_sha, local_sha)
        )
    d = os.path.dirname(lp)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(lp, "wb") as fh:
        fh.write(data)
    print("[rsc] pull ok %s -> %s (%d bytes) sha256=%s"
          % (remote, lp, len(data), local_sha[:16]))


def pull_tree(remote_dir, local_dir, pattern="*"):
    """Download every file under remote_dir matching pattern (non-recursive).

    Returns the list of remote paths transferred. Uses `find -type f` so the
    manifest comes from the remote filesystem, not from a name we guessed.
    """
    remote_dir = remote_path(remote_dir)
    rc, out, _ = run("find %s -maxdepth 1 -type f -name %s | sort"
                     % (shq(remote_dir), shq(pattern)), quiet=True)
    files = [f for f in out.splitlines() if f.strip()]
    for i, rf in enumerate(files, 1):
        base = posixpath.basename(rf)
        sys.stderr.write("[rsc] pull_tree %d/%d %s\n" % (i, len(files), base))
        pull(rf, posixpath.join(local_path(local_dir), base))
    return files


def cmd_stat():
    probe = r"""
set +e
echo "== hostname =="; hostname
echo "== os =="; cat /etc/os-release 2>/dev/null | head -3
echo "== cpu =="; nproc; grep -m1 'model name' /proc/cpuinfo
echo "== mem =="; free -g
echo "== gpu =="; nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv 2>&1 | head -5
echo "== disk =="; df -h / /root /data 2>/dev/null
echo "== python =="; which python3; python3 -V
echo "== pip pkgs =="; python3 -m pip list 2>/dev/null | head -40
echo "== root ls =="; ls -la /root | head -30
echo "== net test =="
for u in https://pypi.org/simple/ https://huggingface.co https://github.com https://zenodo.org https://gwern.net; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -m 12 "$u"); echo "$u -> $code"
done
echo "== proxy env =="; env | grep -i proxy
"""
    return run(probe)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    op = sys.argv[1]
    if op == "exec":
        return run(sys.argv[2])[0]
    if op == "bg":
        bg(sys.argv[2], sys.argv[3])
        return 0
    if op in ("put", "push"):
        push(sys.argv[2], sys.argv[3])
        return 0
    if op in ("get", "pull"):
        pull(sys.argv[2], sys.argv[3])
        return 0
    if op == "pulltree":
        pull_tree(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "*")
        return 0
    if op in ("script", "runscript"):
        return runscript(sys.argv[2], sys.argv[3:])[0]
    if op == "stat":
        return cmd_stat()[0]
    print("unknown op", op)
    return 2


if __name__ == "__main__":
    sys.exit(main())
