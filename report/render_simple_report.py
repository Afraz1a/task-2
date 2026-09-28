"""
Render report/simple_report.md to a plain black-and-white PDF.

Same approach as Task 1's scripts/report_to_pdf.py: xhtml2pdf, pure Python,
no system libraries needed on Windows. The stylesheet uses only black, white
and grey - no colour anywhere, including link text - to match the plain,
easy-to-read version of the report.

Usage:
    python report/render_simple_report.py
"""

import sys
import types
from pathlib import Path

CSS = """
@page { size: a4 portrait; margin: 1.6cm 1.4cm; @frame footer {
        -pdf-frame-content: footer; bottom: 0.8cm; margin-left: 1.4cm;
        margin-right: 1.4cm; height: 1cm; } }
body { font-family: Helvetica, Arial, sans-serif; font-size: 9.5pt;
       line-height: 1.45; color: #1a1a1a; }
h1 { font-size: 18pt; color: #111; margin: 0 0 2pt 0; padding-bottom: 4pt;
     border-bottom: 2pt solid #333; }
h2 { font-size: 13pt; color: #111; margin: 16pt 0 5pt 0; padding-bottom: 2pt;
     border-bottom: 0.5pt solid #bbb; }
h3 { font-size: 10.5pt; color: #222; margin: 11pt 0 3pt 0; }
p  { margin: 5pt 0; }
img { max-width: 100%; border: 0.5pt solid #999; margin: 6pt 0 2pt 0; }
em  { color: #333; font-size: 8.5pt; }
ul, ol { margin: 4pt 0 4pt 14pt; }
li { margin: 2pt 0; }
hr { border-top: 0.5pt solid #ddd; margin: 12pt 0; }
a { color: #1a1a1a; text-decoration: none; }
.footer { font-size: 7.5pt; color: #888; text-align: center; }
"""

FOOTER = ('<div id="footer" class="footer">TrendPilot &mdash; AIRI Team PITB, '
          'AI Internship Task 2 &mdash; page <pdf:pagenumber> of <pdf:pagecount></div>')


def main() -> int:
    import markdown
    try:
        import bidi  # noqa: F401
    except Exception:
        stub = types.ModuleType("bidi")
        stub.get_display = lambda text, *a, **kw: text
        algo = types.ModuleType("bidi.algorithm")
        algo.get_display = stub.get_display
        stub.algorithm = algo
        sys.modules["bidi"] = stub
        sys.modules["bidi.algorithm"] = algo

    from xhtml2pdf import pisa

    src = Path("report/simple_report.md")
    out = Path("report/simple_report.pdf")
    if not src.exists():
        sys.exit(f"not found: {src}")

    text = src.read_text(encoding="utf-8")
    for bad, good in (("—", "&mdash;"), ("–", "&ndash;"), ("×", "x")):
        text = text.replace(bad, good)

    body = markdown.markdown(text, extensions=["fenced_code", "sane_lists"])
    html = (f'<html><head><meta charset="utf-8">'
            f'<style>{CSS}</style></head><body>{FOOTER}{body}</body></html>')

    with out.open("wb") as fh:
        result = pisa.CreatePDF(html, dest=fh, encoding="utf-8")
    if result.err:
        sys.exit(f"PDF generation reported {result.err} error(s)")

    size = out.stat().st_size
    print(f"wrote {out}  ({size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
