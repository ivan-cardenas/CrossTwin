"""Export docs/architecture/latest/*.svg to PNG and PDF with headless Chrome/Edge.

    python tools/arch_diagrams.py && python tools/arch_export.py

Writes <name>.png and <name>.pdf per diagram, plus CrossTwin-architecture.pdf
(all diagrams, one per page) and embed.html.
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "architecture" / "latest"
CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "google-chrome", "chromium", "chrome", "msedge",
]


def browser():
    for c in CANDIDATES:
        if Path(c).exists() or shutil.which(c):
            return c
    raise SystemExit("No Chrome/Edge found for export")


def size(svg_text):
    w, h = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg_text).groups()
    return int(w), int(h)


def page(svgs):
    """One page per SVG, each page sized to its diagram (named @page rules)."""
    rules, bodies = [], []
    for i, text in enumerate(svgs):
        w, h = size(text)
        rules.append(f"@page p{i} {{ size: {w}px {h}px; margin: 0; }} .p{i} {{ page: p{i}; width:{w}px; height:{h}px; }}")
        bodies.append(f'<div class="pg p{i}">{text}</div>')
    css = ("html,body{margin:0;padding:0;background:#fff} .pg{overflow:hidden;break-after:page}"
           " .pg:last-child{break-after:auto} .pg svg{display:block}" + "".join(rules))
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{''.join(bodies)}</body></html>"


def run(exe, args):
    subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-pdf-header-footer",
                    "--run-all-compositor-stages-before-draw", "--virtual-time-budget=2000", *args],
                   check=True, capture_output=True)


def main():
    exe = browser()
    svgs = sorted(OUT.glob("[0-9][0-9]-*.svg"))
    tmp = Path(tempfile.mkdtemp())
    texts = []
    for svg in svgs:
        text = svg.read_text(encoding="utf-8")
        texts.append(text)
        w, h = size(text)
        html = tmp / f"{svg.stem}.html"
        html.write_text(page([text]), encoding="utf-8")
        run(exe, [f"--window-size={w},{h}", "--force-device-scale-factor=2",
                  f"--screenshot={OUT / (svg.stem + '.png')}", html.as_uri()])
        run(exe, [f"--print-to-pdf={OUT / (svg.stem + '.pdf')}", html.as_uri()])
        print("exported", svg.stem)
    suite = tmp / "suite.html"
    suite.write_text(page(texts), encoding="utf-8")
    run(exe, [f"--print-to-pdf={OUT / 'CrossTwin-architecture.pdf'}", suite.as_uri()])
    print("exported CrossTwin-architecture.pdf")

    embed = "\n".join(
        f'<!-- {s.stem} -->\n<img src="docs/architecture/latest/{s.name}" alt="{s.stem}" width="100%">' for s in svgs)
    (OUT / "embed.html").write_text(embed + "\n", encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
