#!/usr/bin/env python3
"""
Minna no Nihongo -- vocabulary worksheet generator (English edition)
======================================================================

Turns the MinnaNoDS vocabulary dataset
(https://github.com/vitto4/MinnaNoDS) into printable "new words"
worksheet PDFs, one per lesson, laid out like the original hand-made
worksheet template:

      #  |  kanji                       |  meaning
         |  ..........................  |
         |  kana                        |
      ---+-------------------------------+----------------------------
      1  |  切ります                      |  cut, slice
      2  |  送ります                      |  send
         |  おくります                    |

Two continuously-numbered 25-row columns per page (a word gets slot
1-25 on the left, 26-50 on the right; a new page starts at 51, 101,
...), a header with the lesson number and a blank "Name" line, thin
table borders, and a dotted rule separating the kanji line from the
kana line -- same idea as the original template, except:

  * the meaning column is English (MinnaNoDS's `meaning.en` field)
    instead of Mongolian, and
  * row heights auto-fit their content, since English definitions
    range from one word ("send") to a full sentence (some entries in
    the dataset run 100+ characters) -- a fixed row height that works
    for one lesson would clip text in another.

Usage
-----
    python generate_worksheets.py                     # all 50 lessons
    python generate_worksheets.py --lessons 7 26       # just these
    python generate_worksheets.py --out my_folder
    python generate_worksheets.py --refresh            # re-download the dataset

Requires: reportlab, pyyaml   ->   pip install reportlab pyyaml
A bundled copy of Noto Serif CJK JP (fonts/NotoSerifCJKjp-Regular.ttf)
is used for the Japanese text so the script works without relying on
whatever fonts happen to be installed on your machine.
"""

import argparse
import os
import re
import sys
import urllib.request
from xml.sax.saxutils import escape as xml_escape

import yaml
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

# --------------------------------------------------------------------------- #
#                                   Config                                    #
# --------------------------------------------------------------------------- #

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET_URL = "https://raw.githubusercontent.com/vitto4/MinnaNoDS/main/minna-no-ds.yaml"
DEFAULT_DATASET_PATH = os.path.join(HERE, "data", "minna-no-ds.yaml")
JP_FONT_PATH = os.path.join(HERE, "fonts", "NotoSerifCJKjp-Regular.ttf")
JP_FONT_NAME = "NotoSerifJP"

PAGE_W, PAGE_H = A4
MARGIN_L, MARGIN_R = 30, 30
MARGIN_TOP, MARGIN_BOTTOM = 30, 26
HEADER_H = 30

ROWS_PER_COLUMN = 25         # left column = 1..25, right column = 26..50
SLOTS_PER_PAGE = ROWS_PER_COLUMN * 2

NUM_COL_W = 20
COL_GAP = 8                  # gap between the left and right sub-tables
CELL_PAD_X = 4               # horizontal text padding inside a cell
CELL_PAD_Y = 3               # vertical padding above/below text in a row
MIN_ROW_H = 24                # floor row height, even for a blank/short row
DOTTED_GAP = 1.5             # gap left around the dotted kanji/kana divider

# Font sizes are tried largest-first; the first size whose content fits
# every page of a given lesson without overflowing is used for that
# lesson's PDF (see fit_font_scale()).
FONT_SCALES = [1.0, 0.92, 0.85, 0.8, 0.75, 0.7, 0.65]
BASE_JP_SIZE = 11.5
BASE_EN_SIZE = 9.3
BASE_NUM_SIZE = 9.3

TABLE_W = PAGE_W - MARGIN_L - MARGIN_R
SUBTABLE_W = (TABLE_W - COL_GAP) / 2
JP_COL_W = 98
EN_COL_W = SUBTABLE_W - NUM_COL_W - JP_COL_W


# --------------------------------------------------------------------------- #
#                                Dataset I/O                                  #
# --------------------------------------------------------------------------- #

def load_dataset(path=DEFAULT_DATASET_PATH, refresh=False):
    """Load minna-no-ds.yaml, downloading it if missing (or --refresh)."""
    if refresh or not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        print(f"Downloading dataset from {DATASET_URL} ...")
        urllib.request.urlretrieve(DATASET_URL, path)
    with open(path, encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def lesson_entries(dataset, lesson_num):
    """Return [{num, kanji, kana, en}, ...] for one lesson, in dataset order."""
    key = f"lesson-{lesson_num:02d}"
    words = dataset.get(key, [])
    entries = []
    for i, w in enumerate(words, start=1):
        entries.append({
            "num": i,
            "kanji": (w.get("kanji") or "").strip(),
            "kana": (w.get("kana") or "").strip(),
            "en": (w["meaning"].get("en") or "").strip(),
        })
    return entries


# --------------------------------------------------------------------------- #
#                             Mixed-script markup                            #
# --------------------------------------------------------------------------- #
# A handful of English `meaning` entries in the dataset embed a bit of raw
# Japanese for clarity (e.g. "put on [glasses]" vs. a literal reading, or
# "～を します : travel, make a trip"). Helvetica can't render those glyphs,
# so any CJK/fullwidth run inside English text gets wrapped in a <font>
# tag pointing at the embedded Japanese face; reportlab's Paragraph markup
# understands that inline.

_CJK_RE = re.compile(
    "[\u3000-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]"
)


def mark_mixed_script(text, jp_font):
    if not text:
        return text
    parts = []
    buf, buf_is_cjk = "", None
    for ch in text:
        is_cjk = bool(_CJK_RE.match(ch))
        if buf_is_cjk is None:
            buf_is_cjk = is_cjk
        if is_cjk != buf_is_cjk:
            parts.append((buf, buf_is_cjk))
            buf = ""
            buf_is_cjk = is_cjk
        buf += ch
    if buf:
        parts.append((buf, buf_is_cjk))

    out = []
    for chunk, is_cjk in parts:
        esc = xml_escape(chunk)
        out.append(f'<font name="{jp_font}">{esc}</font>' if is_cjk else esc)
    return "".join(out)


# --------------------------------------------------------------------------- #
#                                   Fonts                                     #
# --------------------------------------------------------------------------- #

def register_fonts():
    if JP_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        if not os.path.exists(JP_FONT_PATH):
            sys.exit(
                f"Japanese font not found at {JP_FONT_PATH}.\n"
                "Grab a Japanese-capable font (e.g. Noto Serif CJK JP) and place it there, "
                "or point JP_FONT_PATH at one you already have."
            )
        pdfmetrics.registerFont(TTFont(JP_FONT_NAME, JP_FONT_PATH))


def styles_for_scale(scale):
    jp_size = BASE_JP_SIZE * scale
    en_size = BASE_EN_SIZE * scale
    num_size = BASE_NUM_SIZE * scale
    return {
        "kanji": ParagraphStyle("kanji", fontName=JP_FONT_NAME, fontSize=jp_size,
                                 leading=jp_size * 1.15, spaceAfter=0),
        "kana": ParagraphStyle("kana", fontName=JP_FONT_NAME, fontSize=jp_size,
                                leading=jp_size * 1.15, spaceAfter=0),
        "en": ParagraphStyle("en", fontName="Helvetica", fontSize=en_size,
                              leading=en_size * 1.28, spaceAfter=0),
        "num": ParagraphStyle("num", fontName="Helvetica", fontSize=num_size,
                               leading=num_size * 1.15),
        "num_size": num_size,
        "jp_size": jp_size,
        "en_size": en_size,
    }


# --------------------------------------------------------------------------- #
#                             Layout measurement                             #
# --------------------------------------------------------------------------- #

def _wrap_h(text, style, width):
    if not text:
        return 0.0
    p = Paragraph(text.replace("\n", "<br/>"), style)
    _, h = p.wrap(width, 100000)
    return h


def entry_height(entry, sty):
    """Height needed to render one vocab entry's jp/en pair, content only."""
    if entry is None:
        return 0.0
    jp_w = JP_COL_W - 2 * CELL_PAD_X
    en_w = EN_COL_W - 2 * CELL_PAD_X
    kanji_h = _wrap_h(xml_escape(entry["kanji"]), sty["kanji"], jp_w)
    kana_h = _wrap_h(xml_escape(entry["kana"]), sty["kana"], jp_w)
    jp_h = kanji_h + kana_h + (DOTTED_GAP * 2 if kanji_h and kana_h else DOTTED_GAP)
    en_marked = mark_mixed_script(entry["en"], JP_FONT_NAME)
    en_h = _wrap_h(en_marked, sty["en"], en_w)
    return max(jp_h, en_h)


def paginate(entries):
    """Split entries into 25-row columns (numbered continuously, blanks keep
    their position number like the original template), then pack two
    columns per page. If the final column would leave its page-mate
    completely empty, that empty column is simply not created -- so a
    52-word lesson gets a full page-1 (cols 1-25 / 26-50) plus a second
    page holding only column 3 (51-75), instead of an almost-blank
    second page padded all the way out to slot 100."""
    n = len(entries)
    by_num = {e["num"]: e for e in entries}
    n_columns = max(2, -(-n // ROWS_PER_COLUMN))  # ceil(n/25), at least 2 for a normal single page
    columns = []
    for col_idx in range(n_columns):
        base = col_idx * ROWS_PER_COLUMN
        col = [by_num.get(base + i) for i in range(1, ROWS_PER_COLUMN + 1)]
        columns.append(col)
    pages = [columns[i:i + 2] for i in range(0, len(columns), 2)]

    # A solo trailing column (no page-mate) is the most wasteful case --
    # e.g. 2 leftover words padded out to 25 blank rows. Trim it down to
    # just past its last real entry, with a small buffer of blank rows
    # left for anyone who wants to jot down extra vocab.
    if len(pages) and len(pages[-1]) == 1:
        col = pages[-1][0]
        last_filled = max((i for i, e in enumerate(col) if e is not None), default=-1)
        trimmed_len = min(ROWS_PER_COLUMN, max(5, last_filled + 1 + 3))
        pages[-1] = [col[:trimmed_len]]

    return pages


def fit_font_scale(pages):
    """Pick the largest font scale for which every page's rows fit the
    printable height, so one lesson's PDF stays visually consistent."""
    avail_h = PAGE_H - MARGIN_TOP - MARGIN_BOTTOM - HEADER_H
    for scale in FONT_SCALES:
        sty = styles_for_scale(scale)
        ok = True
        for cols in pages:
            total = 0.0
            for row_idx in range(len(cols[0])):
                row_content_h = max(entry_height(col[row_idx], sty) for col in cols)
                total += max(row_content_h + 2 * CELL_PAD_Y, MIN_ROW_H)
            if total > avail_h:
                ok = False
                break
        if ok:
            return scale
    return FONT_SCALES[-1]


def row_heights_for_page(cols, sty):
    heights = []
    for row_idx in range(len(cols[0])):
        row_content_h = max(entry_height(col[row_idx], sty) for col in cols)
        heights.append(max(row_content_h + 2 * CELL_PAD_Y, MIN_ROW_H))
    return heights


# --------------------------------------------------------------------------- #
#                                  Drawing                                    #
# --------------------------------------------------------------------------- #

def draw_header(c, lesson_num, page_idx, page_count):
    top_y = PAGE_H - MARGIN_TOP
    c.setLineWidth(1.1)
    c.rect(MARGIN_L, top_y - HEADER_H, TABLE_W, HEADER_H, stroke=1, fill=0)

    title = f"Lesson {lesson_num} - New Words"
    if page_count > 1:
        title += f"  (page {page_idx + 1}/{page_count})"
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(MARGIN_L + TABLE_W * 0.38, top_y - HEADER_H / 2 - 4.5, title)

    c.setFont("Helvetica", 10.5)
    name_x = MARGIN_L + TABLE_W * 0.68
    c.drawString(name_x, top_y - HEADER_H / 2 - 3.5, "Name:")
    c.setDash([1, 1.6], 0)
    c.setLineWidth(0.7)
    c.line(name_x + 34, top_y - HEADER_H / 2 - 4, MARGIN_L + TABLE_W - 6, top_y - HEADER_H / 2 - 4)
    c.setDash([], 0)


def draw_footer(c):
    c.setFont("Helvetica", 6.5)
    c.setFillGray(0.45)
    note = ("Vocabulary from Minna no Nihongo Shokyu I & II, via the MinnaNoDS dataset "
            "(github.com/vitto4/MinnaNoDS). Words \u00a9 3A Corporation; for personal study use only.")
    c.drawCentredString(PAGE_W / 2, MARGIN_BOTTOM / 2, note)
    c.setFillGray(0)


def draw_row(c, entry, slot_num, num_x0, jp_x0, en_x0, right_edge, row_top, row_bot, sty):
    h = row_top - row_bot
    # -- number, vertically centred-ish near the top like the original --
    c.setFont("Helvetica", sty["num_size"])
    c.drawString(num_x0 + 3, row_top - sty["num_size"] - 2, str(slot_num))

    if entry is None:
        return

    jp_w = (en_x0 - jp_x0) - 2 * CELL_PAD_X
    en_w = (right_edge - en_x0) - 2 * CELL_PAD_X

    kanji_p = Paragraph(xml_escape(entry["kanji"]), sty["kanji"]) if entry["kanji"] else None
    kana_p = Paragraph(xml_escape(entry["kana"]), sty["kana"]) if entry["kana"] else None

    kanji_h = 0
    if kanji_p:
        _, kanji_h = kanji_p.wrap(jp_w, 10000)
    kana_h = 0
    if kana_p:
        _, kana_h = kana_p.wrap(jp_w, 10000)

    # dotted divider sits right after the kanji line (or right at the top
    # of the cell if there's no separate kanji line, so the reading always
    # lands in the same "lower" slot -- matching the source template)
    divider_y = row_top - (kanji_h if kanji_h else 0) - DOTTED_GAP

    if kanji_p:
        kanji_p.drawOn(c, jp_x0 + CELL_PAD_X, divider_y + DOTTED_GAP)
    if kana_p:
        kana_p.drawOn(c, jp_x0 + CELL_PAD_X, divider_y - DOTTED_GAP - kana_h)

    c.setDash([0.9, 1.3], 0)
    c.setLineWidth(0.6)
    c.line(jp_x0 + 1, divider_y, right_edge - (right_edge - en_x0) - 1, divider_y)
    c.setDash([], 0)

    if entry["en"]:
        en_marked = mark_mixed_script(entry["en"], JP_FONT_NAME)
        en_p = Paragraph(en_marked, sty["en"])
        _, en_h = en_p.wrap(en_w, 10000)
        en_p.drawOn(c, en_x0 + CELL_PAD_X, row_top - en_h - (h - en_h) / 2 if en_h < h else row_bot + 1)


# --------------------------------------------------------------------------- #
#                              Page rendering                                #
# --------------------------------------------------------------------------- #

def render_page(c, lesson_num, page_idx, page_count, cols, sty):
    draw_header(c, lesson_num, page_idx, page_count)
    heights = row_heights_for_page(cols, sty)

    top_y = PAGE_H - MARGIN_TOP - HEADER_H
    left_x0 = MARGIN_L
    right_x0 = MARGIN_L + NUM_COL_W + JP_COL_W + EN_COL_W + COL_GAP
    col_x0s = [left_x0, right_x0]

    for col_i, col_entries in enumerate(cols):
        x0 = col_x0s[col_i]
        start_num = (page_idx * 2 + col_i) * ROWS_PER_COLUMN + 1
        jp_x0 = x0 + NUM_COL_W
        en_x0 = jp_x0 + JP_COL_W
        right_edge = en_x0 + EN_COL_W
        total_h = sum(heights)

        c.setLineWidth(1.0)
        c.rect(x0, top_y - total_h, right_edge - x0, total_h, stroke=1, fill=0)

        y = top_y
        for i, (entry, h) in enumerate(zip(col_entries, heights)):
            row_top = y
            row_bot = y - h
            c.setLineWidth(0.5)
            c.line(jp_x0, row_top, jp_x0, row_bot)
            c.line(en_x0, row_top, en_x0, row_bot)
            if i > 0:
                c.line(x0, row_top, right_edge, row_top)
            draw_row(c, entry, start_num + i, x0, jp_x0, en_x0, right_edge, row_top, row_bot, sty)
            y = row_bot

    draw_footer(c)


def render_lesson(dataset, lesson_num, out_dir):
    entries = lesson_entries(dataset, lesson_num)
    if not entries:
        print(f"  (lesson {lesson_num}: no entries in dataset, skipping)")
        return None

    pages = paginate(entries)
    scale = fit_font_scale(pages)
    sty = styles_for_scale(scale)

    out_path = os.path.join(out_dir, f"lesson-{lesson_num:02d}-new-words.pdf")
    c = canvas.Canvas(out_path, pagesize=A4)
    c.setTitle(f"Lesson {lesson_num} - New Words")
    for page_idx, cols in enumerate(pages):
        render_page(c, lesson_num, page_idx, len(pages), cols, sty)
        c.showPage()
    c.save()
    print(f"  lesson {lesson_num:>2}: {len(entries):>2} words -> "
          f"{len(pages)} page(s), font scale {scale:.2f}  ({os.path.basename(out_path)})")
    return out_path


# --------------------------------------------------------------------------- #
#                                    Main                                     #
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lessons", type=int, nargs="+", default=None,
                         help="Lesson numbers to generate (default: all 1-50)")
    parser.add_argument("--out", default=os.path.join(HERE, "output"),
                         help="Output directory for the generated PDFs")
    parser.add_argument("--dataset", default=DEFAULT_DATASET_PATH,
                         help="Path to minna-no-ds.yaml (downloaded automatically if missing)")
    parser.add_argument("--refresh", action="store_true",
                         help="Re-download the dataset even if a local copy exists")
    args = parser.parse_args()

    register_fonts()
    dataset = load_dataset(args.dataset, refresh=args.refresh)
    os.makedirs(args.out, exist_ok=True)

    lesson_nums = args.lessons or [l["id"] for l in dataset["lessons"]]
    print(f"Generating {len(lesson_nums)} worksheet(s) into {args.out}/ ...")
    for n in lesson_nums:
        render_lesson(dataset, n, args.out)
    print("Done.")


if __name__ == "__main__":
    main()
