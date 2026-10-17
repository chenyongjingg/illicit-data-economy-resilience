#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract plain text from a .docx (a zip whose word/document.xml holds the body).

    python _docx_text.py <file.docx> [outfile.txt]

No third-party dependency: python-docx may not be installed, and this is a
one-purpose tool. Paragraph breaks come from </w:p>.
"""
import re
import sys
import zipfile


def docx_text(path):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    # </w:p> and <w:br/> are the paragraph/line boundaries that matter here.
    xml = xml.replace("</w:p>", "\n").replace("<w:br/>", "\n")
    # Keep tab cells readable rather than running them together.
    xml = xml.replace("</w:tc>", "\t")
    txt = re.sub(r"<[^>]+>", "", xml)
    txt = (txt.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
              .replace("&quot;", '"').replace("&apos;", "'"))
    txt = re.sub(r"[ \t]+\n", "\n", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt


if __name__ == "__main__":
    src = sys.argv[1]
    out = docx_text(src)
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8", newline="\n") as fh:
            fh.write(out)
        print("wrote %s (%d chars)" % (sys.argv[2], len(out)))
    else:
        print(out)
