#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""58_E9_provenance.py -- stamp WHO produced each field of 51_E9_series.json.

Additive only: no existing value is altered.

The problem this fixes: `read_text()` is one line --
    out["fitz_chars"] = sum(len(p.get_text()) for p in doc)
-- and that line returns 11,853 for 2025-01 on the pod (PyMuPDF 1.28.2) and
6,670 for the same bytes, same call, locally (PyMuPDF 1.27.2.3). A field that
silently means different things on different machines is not a measurement of
the document; it is a measurement of the document-and-the-library.

★ C-207 (2026-09-24). THE CAUSE ASSERTED IN THE PARAGRAPH ABOVE WAS WITHDRAWN.
The numbers are observations and they stand; the attribution "1.28.2 (pod) vs
1.27.2.3 (local)" does not -- this record's own `extractors.fitz` field says
1.28.2 for BOTH of its non-null entries, so "local 1.27.2.3" is a claim no field
here supports. The mechanism is UNIDENTIFIED. This file had also drifted from the
artefact it stamps: `results/51_E9_series.json` carries the corrected note (the
one in `NOTE` below) while this generator would have re-stamped the withdrawn one
-- i.e. re-running it would have replaced a corrected record with a false one.
The pre-correction note is preserved as a witness at
`results/_superseded_51_E9_series.json.podcopy` (11,518 B, git blob
`c08fc6130d621c57561c0cf6c74f93e75785d4b5`), NOT remediated in place, because
editing that file would destroy its value as a byte-faithful copy of what the pod
produced. Do not restore the causal clause without a field that supports it.

Two consequences, both recorded here rather than fixed by rewriting:
  * `fitz_chars` / `text_chars` must never be compared across machines, and any
    claim resting on them ("01-04 have richer text layers") is not supported.
    The claim that IS supported is narrower and measured: p.6 of 01-04 carries a
    ~105-char text block with both headline sentences, and no page of 06-11
    carries the keyword at all.
  * the VALUES are unaffected: 51_'s four numbers are reproduced by local fitz
    1.27.2.3 and by OCR on rendered pixels, two instruments with different
    blind spots.
"""
import json
import sys

P = "/root/cis/results/51_E9_series.json"

# ★ C-207. This is the text the shipped `results/51_E9_series.json` actually
# carries. It used to assert the library-version cause as fact; that cause was
# withdrawn (see the module docstring). Regenerating now reproduces the shipped
# record instead of overwriting it with the withdrawn one.
NOTE = (
    "fitz_chars/text_chars differ between the runs recorded here, but the MECHANISM IS UNIDENTIFIED. "
    "This file's own `extractors.fitz` field records 1.28.2 for BOTH of its non-null entries, so the "
    "earlier explanation 'PyMuPDF 1.27.2.3 (local)' is not supported by any field in this record. The "
    "observations stand (pod 11853/12932/11945/12296; local 6670/6534/4859/6698); the cause does not. "
    "Do NOT compare these across machines; the supported cross-machine field is `despaced`/`series`, "
    "which OCR independently reproduces 4/4."
)


def main():
    import fitz
    try:
        import pypdf
        pv = pypdf.__version__
    except Exception:                                             # noqa: BLE001
        pv = None
    d = json.load(open(P, encoding="utf-8"))
    d["_provenance"] = {
        "extractors": {"fitz": fitz.version, "pypdf": pv},
        "produced_on": "pod (cpod-1vn6o9mm47jc)",
        "note": NOTE,
        "fields_safe_to_compare_across_machines": ["series", "despaced"],
        "fields_NOT_safe_to_compare_across_machines": ["fitz_chars", "text_chars"],
    }
    with open(P, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=2)
    print("stamped %s" % P)
    print(json.dumps(d["_provenance"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
