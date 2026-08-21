"""Render a document in `docs/` to PDF, through the same toolchain as the papers.

A PDF committed beside its source is a second copy of the same claims that nothing keeps in step.
This exists so the copy can be rebuilt rather than remembered: `docs/pdf/BASELINE.pdf` is a render
of `docs/BASELINE.md` and has no independent authority.

pandoc to standalone HTML, then weasyprint with the Research-Papers stylesheet, which is what
`Research-Papers/TimSim/build.py` does and is the reason the output matches the series rather than
a browser default. No title metadata is passed, because the document's own first heading is its
title and pandoc otherwise prints the file name above it.

The stylesheet lives in the papers repository. When it is not on this machine the render still
happens, unstyled, and says so, rather than failing and leaving no PDF at all.

    python examples/render_docs.py BASELINE.md
    python examples/render_docs.py            # every document listed in DEFAULT
"""

import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(REPO, "docs")
OUT = os.path.join(DOCS, "pdf")
CSS = "/Users/timstreet/StudioProjects/Research-Papers/TimSim/paper.css"

# Documents that carry figures somebody outside this repository is expected to read. Reference
# material that is only read here does not need a second copy.
DEFAULT = ["BASELINE.md"]


def render(name):
    src = os.path.join(DOCS, name)
    if not os.path.exists(src):
        raise SystemExit(f"{src} does not exist")
    os.makedirs(OUT, exist_ok=True)
    stem = os.path.splitext(name)[0]
    html = os.path.join(OUT, stem + ".html")
    pdf = os.path.join(OUT, stem + ".pdf")
    subprocess.run(["pandoc", src, "-o", html, "--standalone", "--metadata", "title="],
                   check=True)
    sheets = [CSS] if os.path.exists(CSS) else []
    if not sheets:
        print(f"note: {CSS} is not on this machine, so {stem} renders unstyled")
    # The `weasyprint` command rather than `sys.executable -c "import weasyprint"`. The
    # interpreter running this is the project virtual environment, which does not carry
    # weasyprint; the command is on the path and does. Assuming the running interpreter has it
    # produced a traceback and no PDF.
    cmd = ["weasyprint", html, pdf]
    for sheet in sheets:
        cmd += ["-s", sheet]
    subprocess.run(cmd, check=True)
    os.remove(html)
    print(f"wrote {pdf}")
    return pdf


if __name__ == "__main__":
    for arg in (sys.argv[1:] or DEFAULT):
        render(arg)
