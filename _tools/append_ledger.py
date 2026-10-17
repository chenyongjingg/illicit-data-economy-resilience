# -*- coding: utf-8 -*-
"""Append a block of text to the ledger, preserving every existing byte.

Why a tool and not `cat >>`: the ledger is the project's only authoritative
record, it is append-only BY RULE, and "append-only" is a claim that has to be
checked rather than asserted. This asserts it -- it re-reads the file after
writing and requires the original prefix to be byte-identical. It also refuses
to write if the file is CRLF, because a tool that silently normalises line
endings would rewrite the whole history while looking like an append.

Usage
  python append_ledger.py <text-file> [--target <path>]
"""
import io
import os
import sys

DEFAULT = r"D:\CIS\pipeline_reports\progress.md"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    target = DEFAULT
    if "--target" in sys.argv:
        target = sys.argv[sys.argv.index("--target") + 1]
    src = args[0]

    block = io.open(src, encoding="utf-8").read()
    if not block.endswith("\n"):
        block += "\n"

    raw = io.open(target, "rb").read()
    if raw.count(b"\r\n"):
        print("REFUSING: %s is CRLF (%d). Normalising it would rewrite history."
              % (target, raw.count(b"\r\n")))
        return 2
    before = len(raw)

    with io.open(target, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(block)

    after = io.open(target, "rb").read()
    if after[:before] != raw:
        print("FAILED: existing bytes changed -- this was not an append.")
        return 3
    print("appended %d bytes to %s (%d -> %d); existing bytes byte-identical"
          % (len(block.encode("utf-8")), os.path.basename(target),
             before, len(after)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
