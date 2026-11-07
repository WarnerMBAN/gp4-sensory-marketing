"""
mban_docx.py · Dale's MBAN 5640 Word (.docx) house style, as reusable code
==========================================================================

WHAT
    Building blocks for a house-style Word report: page set-up, header and
    footer, title block, AI ATTRIBUTION callout, BLUF box, navy ruled headings,
    body text with **bold**, bullets, navy-header tables, code blocks, and
    lecture / "beyond the lectures" callouts.
WHY
    The style was settled on the GP2 Code Walkthrough Report (Dale's layout of
    2026-10-13, decision D-027). Keeping it in one module means every new
    report or script looks the same without re-deriving fonts, colours, tab
    stops or Word quirks.
SOURCE
    Extracted from 02_Deliverables/P2_EndToEnd_Pipeline_30pct/working/P2_pipeline/
    reports/build_walkthrough.py (new_document and helpers), 2026-10-13.
NEEDS
    python-docx (pip install python-docx); tzdata on Windows for the Halifax clock.
USE
    import sys; sys.path.insert(0, r"<skill folder>/scripts")
    import mban_docx as M
    doc = M.new_document(title="P2 Code Walkthrough", doc_name="GP2 - Code Walkthrough", ...)
    M.bluf(doc, "One-paragraph bottom line.")
    M.heading(doc, "1. Architecture overview")
    M.para(doc, "Body text with **bold** parts.")
    path = M.save(doc, out_dir, "MBAN5640_P2_Group01_CodeWalkthrough_SONI-TONER-WARNER")
    Run this file directly for a sample:  python mban_docx.py <out_dir>
"""
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Twips

# ---------------------------------------------------------------------------
# Tokens (measured from the GP1 walkthrough; layout per D-027)
# ---------------------------------------------------------------------------
NAVY = "00205B"          # course house colour, RGB 0/32/91
INK = "1A1A1A"           # body text
GREY = "595959"          # header, footer, meta lines, captions
SUBTITLE = "333333"
CODE_FILL, CODE_EDGE = "F4F4F1", "B9B6AC"
TINT = "E8ECF5"          # BLUF box, lecture and AI callouts
BEYOND_FILL, BEYOND_EDGE, BEYOND_INK = "FDEEE4", "EB6834", "B23A00"
NOTE_INK = "7A3E00"
GRID = "D9D7CF"
FONT, CODE_FONT = "Arial", "Consolas"
TEAM = "Krishna Soni (A00495153) · Michael Toner (A00494090) · Dale Warner (A00056348)"
COURSE_HEADER = "MBAN 5640 · Visualization & Data Mining"

PAGE_W, PAGE_H = 12240, 15840          # US Letter, twips (1440 = 1 inch)
SIDE = 1000                            # left/right margin
CONTENT_WIDTH = PAGE_W - 2 * SIDE      # 10240
RIGHT_TAB = 10206                      # right-aligned tab at the right margin (header/footer)

AI_TEXT_DEFAULT = ("Prepared with AI assistance from **Claude (Anthropic)**. The pipeline code, the dashboard and "
                   "this report generator were developed with Claude under the team's direction, and reviewed by "
                   "the team.")


def halifax_now():
    """(file stamp YYYYMMDD_HHMM, display stamp YYYY-MM-DD HH:MM) from the America/Halifax clock."""
    now = datetime.now(ZoneInfo("America/Halifax"))
    return now.strftime("%Y%m%d_%H%M"), now.strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------
def run(paragraph, text, size=None, bold=False, italic=False, color=INK, font=FONT):
    r = paragraph.add_run(text)
    r.font.name = font
    r._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), font)
    if size:
        r.font.size = Pt(size)
    r.font.bold, r.font.italic = bold, italic
    r.font.color.rgb = RGBColor.from_string(color)
    return r


def rich(paragraph, text, size=None, color=INK):
    """Add text with **bold**, *italic* and `code` segments."""
    for tok in re.split(r"(\*\*.+?\*\*|`[^`]+`|\*[^*\s][^*]*\*)", text):
        if not tok:
            continue
        if tok.startswith("**"):
            run(paragraph, tok[2:-2], size=size, bold=True, color=color)
        elif tok.startswith("`"):
            run(paragraph, tok[1:-1], size=(size or 10.5) - 1, color=color, font=CODE_FONT)
        elif tok.startswith("*") and len(tok) > 2:
            run(paragraph, tok[1:-1], size=size, italic=True, color=color)
        else:
            run(paragraph, tok, size=size, color=color)


def spacing(paragraph, before=0, after=0, line=None):
    pf = paragraph.paragraph_format
    pf.space_before, pf.space_after = Pt(before), Pt(after)
    if line:
        pf.line_spacing = line


def bottom_rule(paragraph, color=NAVY, size=8):
    p_pr = paragraph._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    b = OxmlElement("w:bottom")
    for k, v in (("val", "single"), ("sz", str(size)), ("space", "2"), ("color", color)):
        b.set(qn(f"w:{k}"), v)
    bdr.append(b)
    p_pr.append(bdr)


def field(paragraph, code, size=8, color=GREY):
    """Word field (PAGE / NUMPAGES) so page numbers update by themselves."""
    r = run(paragraph, "", size=size, color=color)
    for kind, text in (("begin", None), (None, code), ("separate", None), (None, "1"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), kind)
        elif text == code:
            el = OxmlElement("w:instrText"); el.set(qn("xml:space"), "preserve"); el.text = f" {code} "
        else:
            el = OxmlElement("w:t"); el.text = text
        r._element.append(el)


def _shade(cell, fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")          # "clear" + fill = solid background ("solid" renders black)
    shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), fill)
    cell._tc.get_or_add_tcPr().append(shd)


def _cell_margins(cell, top, left, bottom, right):
    mar = OxmlElement("w:tcMar")
    for side, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        el = OxmlElement(f"w:{side}"); el.set(qn("w:w"), str(val)); el.set(qn("w:type"), "dxa"); mar.append(el)
    cell._tc.get_or_add_tcPr().append(mar)


def _borders(table, edges):
    """edges: {"top": (size, colour), ...}; sides not given are switched off."""
    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{side}")
        if side in edges:
            size, colour = edges[side]
            el.set(qn("w:val"), "single"); el.set(qn("w:sz"), str(size)); el.set(qn("w:color"), colour)
        else:
            el.set(qn("w:val"), "nil")
        el.set(qn("w:space"), "0")
        borders.append(el)
    table._tbl.tblPr.append(borders)


def _widths(table, widths):
    """Fixed column widths in twips, on the grid AND every cell (Word and Google Docs both need this)."""
    table.autofit = False
    layout = OxmlElement("w:tblLayout"); layout.set(qn("w:type"), "fixed")
    table._tbl.tblPr.append(layout)
    for row in table.rows:
        for cell, w in zip(row.cells, widths):
            cell.width = Twips(w)
    for col, w in zip(table._tbl.tblGrid.findall(qn("w:gridCol")), widths):
        col.set(qn("w:w"), str(w))


def _gap(doc):
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def boxed(doc, fill, edges, margins=(100, 180, 100, 180)):
    """One-cell table used as a coloured box; returns the cell to write into."""
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    _borders(t, edges)
    _widths(t, [CONTENT_WIDTH])
    cell = t.cell(0, 0)
    _shade(cell, fill)
    _cell_margins(cell, *margins)
    return cell


def _left_right(paragraph):
    """Header/footer line: text, two tabs, text. Clear Word's 9360 right stop; right stop at the margin."""
    stops = paragraph.paragraph_format.tab_stops
    stops.add_tab_stop(Twips(9360), WD_TAB_ALIGNMENT.CLEAR)
    stops.add_tab_stop(Twips(RIGHT_TAB), WD_TAB_ALIGNMENT.RIGHT)


def _arial_heading_style(style, size, before, after):
    style.font.name, style.font.size, style.font.bold = FONT, Pt(size), True
    style.font.color.rgb = RGBColor.from_string(NAVY)
    # Word's built-in headings name a THEME font (asciiTheme="majorHAnsi"...), which always
    # wins over a named font: without this the headings show in Word's default heading font.
    rf = style.element.rPr.rFonts
    for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        rf.attrib.pop(qn(a), None)
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rf.set(qn(a), FONT)
    style.paragraph_format.space_before, style.paragraph_format.space_after = Pt(before), Pt(after)
    style.paragraph_format.keep_with_next = True


# ---------------------------------------------------------------------------
# Document set-up: page, styles, header, footer, title block, AI callout
# ---------------------------------------------------------------------------
def new_document(title, doc_name, subtitle="", subsubtitle="", course_line="MBAN 5640 Visualization & Data Mining",
                 group="Group 1", team=TEAM, status="Draft for team review", status_tail="",
                 ai_text=AI_TEXT_DEFAULT, stamp_text=None):
    """
    Return a new Document in house style with header, footer, title block and AI ATTRIBUTION callout.

    title        big navy title, e.g. "P2 Code Walkthrough"
    doc_name     right side of the header, e.g. "GP2 - Code Walkthrough"
    subtitle     12 pt line, e.g. "Adult Income Data Mining Pipeline"
    subsubtitle  10 pt bracketed line, e.g. "component-by-component reference, mapped to Lecture Notes 02 and 03"
    course_line  9 pt grey, e.g. "MBAN 5640 Visualization & Data Mining · Group Project 2"
    group, team  9 pt "Group 1 · " followed by names with IDs at 8 pt
    status       italic status line ("Draft for team review" or "Final")
    status_tail  text after the timestamp, e.g. "from the current code and artifacts"
    ai_text      body of the AI ATTRIBUTION callout (**bold** allowed); keep it truthful to the work
    stamp_text   "YYYY-MM-DD HH:MM" (Halifax); defaults to now
    """
    stamp_text = stamp_text or halifax_now()[1]
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Twips(PAGE_W), Twips(PAGE_H)
    sec.left_margin = sec.right_margin = Twips(SIDE)
    sec.top_margin, sec.bottom_margin = Twips(1096), Twips(900)
    sec.header_distance = sec.footer_distance = Twips(720)

    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = FONT, Pt(10.5)
    normal.font.color.rgb = RGBColor.from_string(INK)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.1
    _arial_heading_style(doc.styles["Heading 1"], 15, 16, 6)
    _arial_heading_style(doc.styles["Heading 2"], 12, 10, 4)
    for name in ("List Bullet", "List Number"):
        doc.styles[name].font.name, doc.styles[name].font.size = FONT, Pt(10.5)

    hp = sec.header.paragraphs[0]
    _left_right(hp)
    run(hp, f"{COURSE_HEADER}\t\t{doc_name}", size=8, color=GREY)
    fp = sec.footer.paragraphs[0]
    _left_right(fp)
    run(fp, f"Generated {stamp_text} (ADT)", size=7.5, color=GREY)
    run(fp, "\t\tPage ", size=8, color=GREY)
    field(fp, "PAGE"); run(fp, " of ", size=8, color=GREY); field(fp, "NUMPAGES")

    p = doc.add_paragraph(); spacing(p, after=1); run(p, title, size=20, bold=True, color=NAVY)
    if subtitle:
        p = doc.add_paragraph(); spacing(p, after=4); run(p, subtitle, size=12, color=SUBTITLE)
    if subsubtitle:
        p = doc.add_paragraph(); spacing(p, after=4); run(p, f"({subsubtitle})", size=10, color=SUBTITLE)
    if course_line:
        p = doc.add_paragraph(); spacing(p, after=2); run(p, course_line, size=9, color=GREY)
    if team:
        p = doc.add_paragraph(); spacing(p, after=2)
        if group:
            run(p, f"{group} · ", size=9, color=GREY)
        run(p, team, size=8, color=GREY)
    p = doc.add_paragraph(); spacing(p, after=10)
    tail = f" {status_tail}" if status_tail else ""
    run(p, f"{status} · generated {stamp_text} (ADT){tail}", size=9, italic=True, color=GREY)

    if ai_text:
        cell = boxed(doc, TINT, {"top": (4, NAVY), "left": (20, NAVY), "bottom": (4, NAVY), "right": (4, NAVY)})
        first = cell.paragraphs[0]; spacing(first, after=2.5)
        run(first, "AI ATTRIBUTION", size=8.5, bold=True, color=NAVY)
        bp = cell.add_paragraph(); spacing(bp, after=0); rich(bp, ai_text, size=9.5)
        _gap(doc)
    return doc


# ---------------------------------------------------------------------------
# Body blocks
# ---------------------------------------------------------------------------
def bluf(doc, text_or_items):
    """BOTTOM LINE UP FRONT label + tinted box with a navy bar. A string = one paragraph; a list = bullets."""
    p = doc.add_paragraph(); spacing(p, after=3)
    run(p, "BOTTOM LINE UP FRONT", size=9, bold=True, color=NAVY)
    cell = boxed(doc, TINT, {"left": (20, NAVY)})
    if isinstance(text_or_items, str):
        rich(cell.paragraphs[0], text_or_items, size=10.5)
    else:
        cell.paragraphs[0]._p.getparent().remove(cell.paragraphs[0]._p)
        for item in text_or_items:
            bp = cell.add_paragraph(style="List Bullet"); spacing(bp, after=3); rich(bp, item, size=10)
    _gap(doc)


def heading(doc, text, level=1):
    """Level 1: 15 pt navy with a navy rule underneath. Level 2: 12 pt navy. Number them in the text ("1.2 ...")."""
    h = doc.add_heading(text, level=level)
    if level == 1:
        bottom_rule(h)
    return h


def para(doc, text, size=None, color=INK):
    p = doc.add_paragraph(); rich(p, text, size=size, color=color); return p


def bullets(doc, items, numbered=False, size=None):
    """Bullets use Word's List Bullet. Numbered lists are written as "1." + hanging indent so each list restarts at 1."""
    for i, item in enumerate(items, 1):
        if numbered:
            p = doc.add_paragraph()
            p.paragraph_format.left_indent, p.paragraph_format.first_line_indent = Twips(360), Twips(-360)
            run(p, f"{i}.\t", size=size)
        else:
            p = doc.add_paragraph(style="List Bullet")
        spacing(p, after=3); rich(p, item, size=size)


def note(doc, text):
    """Small dark-orange note line (caveats, "re-run after any change", etc.)."""
    p = doc.add_paragraph(); spacing(p, before=2, after=8); rich(p, text, size=9.5, color=NOTE_INK)


def callout(doc, label, body, kind="lecture"):
    """
    kind="lecture": tinted navy box, e.g. label "LN02 s.5 · The data mining pipeline".
    kind="beyond":  orange box, label prefixed "Beyond the lectures · ".
    kind="ai":      same look as the AI ATTRIBUTION box (for extra AI notes inside the body).
    """
    if kind == "beyond":
        fill, edge, ink, label = BEYOND_FILL, BEYOND_EDGE, BEYOND_INK, f"Beyond the lectures · {label}"
    else:
        fill, edge, ink = TINT, NAVY, NAVY
    cell = boxed(doc, fill, {"top": (4, edge), "left": (20, edge), "bottom": (4, edge), "right": (4, edge)})
    first = cell.paragraphs[0]; spacing(first, after=2.5)
    run(first, label, size=8.5, bold=True, color=ink)
    p = cell.add_paragraph(); spacing(p, after=0); rich(p, body, size=10)
    _gap(doc)


def code_block(doc, lines, caption=""):
    """Grey code box with a navy left bar, Consolas 8.5 pt; optional 8 pt grey caption above."""
    if caption:
        p = doc.add_paragraph(); spacing(p, before=6, after=2); run(p, caption, size=8, color=GREY)
    cell = boxed(doc, CODE_FILL, {"top": (4, CODE_EDGE), "left": (16, NAVY), "bottom": (4, CODE_EDGE),
                                  "right": (4, CODE_EDGE)}, margins=(90, 160, 90, 140))
    cell.paragraphs[0]._p.getparent().remove(cell.paragraphs[0]._p)
    for line in lines:
        cp = cell.add_paragraph(); spacing(cp, line=0.96)
        run(cp, line if line else " ", size=8.5, font=CODE_FONT)
    _gap(doc)


def table(doc, headers, rows, widths=None):
    """
    Data table: navy header row with white bold text, light grid, 8.5 pt body, header repeats on new pages.
    widths: twips per column summing to CONTENT_WIDTH (10240); default = sized to the longest text per column.
    """
    n = len(headers)
    if widths is None:
        lens = [max([len(str(headers[i]))] + [len(str(r[i])) for r in rows if i < len(r)]) for i in range(n)]
        lens = [min(max(L, len(str(h)) + 3, 9), 70) for L, h in zip(lens, headers)]
        widths = [int(CONTENT_WIDTH * L / sum(lens)) for L in lens]
        widths[-1] = CONTENT_WIDTH - sum(widths[:-1])
    t = doc.add_table(rows=1, cols=n)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    _borders(t, {"top": (4, CODE_EDGE), "left": (16, NAVY), "bottom": (4, CODE_EDGE), "right": (4, CODE_EDGE),
                 "insideH": (4, GRID), "insideV": (4, GRID)})
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        _shade(c, NAVY); _cell_margins(c, 60, 90, 60, 90)
        spacing(c.paragraphs[0], after=0, line=1.0)
        run(c.paragraphs[0], str(h), size=8.5, bold=True, color="FFFFFF")
    for r in rows:
        cells = t.add_row().cells
        for i, v in enumerate(r):
            _cell_margins(cells[i], 50, 90, 50, 90)
            spacing(cells[i].paragraphs[0], after=0, line=1.0)
            rich(cells[i].paragraphs[0], str(v), size=8.5)
    _widths(t, widths)
    hdr = OxmlElement("w:tblHeader"); hdr.set(qn("w:val"), "true")
    t.rows[0]._tr.get_or_add_trPr().append(hdr)
    _gap(doc)


def save(doc, out_dir, base_name, stamp_file=None):
    """Save as <base_name>_<YYYYMMDD_HHMM>.docx (Halifax clock) and return the path."""
    stamp_file = stamp_file or halifax_now()[0]
    out = Path(out_dir) / f"{base_name}_{stamp_file}.docx"
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out)
    return out


# ---------------------------------------------------------------------------
# Sample (python mban_docx.py <out_dir>)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    d = new_document("P2 Code Walkthrough", "GP2 - Code Walkthrough",
                     subtitle="Adult Income Data Mining Pipeline",
                     subsubtitle="component-by-component reference, mapped to Lecture Notes 02 and 03",
                     course_line="MBAN 5640 Visualization & Data Mining · Group Project 2",
                     status_tail="from the current code and artifacts")
    bluf(d, "Sample of every house-style block. **Bold** works inside any text.")
    heading(d, "1. Section heading")
    para(d, "Body text, 10.5 pt Arial. Inline `code` and *italic* are supported.")
    heading(d, "1.1 Sub-heading", level=2)
    bullets(d, ["First point", "Second point with **bold**"])
    bullets(d, ["Numbered one", "Numbered two"], numbered=True)
    callout(d, "LN02 s.5 · The data mining pipeline", "A lecture callout.")
    callout(d, "Leakage check", "A beyond-the-lectures callout.", kind="beyond")
    code_block(d, ["def hello():", "    return 'world'"], "example.py, a code excerpt")
    table(d, ["Model", "ROC-AUC", "Note"], [["XGBoost", "0.934", "best"], ["Decision Tree", "0.883", "readable"]])
    note(d, "A note line in dark orange.")
    print("Written:", save(d, out_dir, "MBAN5640_HouseStyle_Sample"))
