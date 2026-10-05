# Minna no Nihongo — English vocabulary worksheets

| <b>Русский</b> | <b>Монгол</b> | <b>日本語</b> |　<b dir="rtl" lang="he">עברית</b> |
|-----------------------|-----------------------|-----------------------|-----------------------------------|
| <h3>[🇷🇺 RU](README.ru.md)</h3> | <h3>[🇲🇳 MN](README.mn.md)</h3> | <h3>[🇯🇵 JP](README.ja.md)</h3> | <h3 dir="rtl" lang="he">[HE 🇮🇱](README.he.md)</h3> | 

| <b>Русский</b> | <b>Монгол</b> | <b>日本語</b> |　<b dir="rtl" lang="he">עברית</b> |
|-----------------------|-----------------------|-----------------------|-----------------------------------|
| <h3>[🇷🇺 RU](README.ru.md)</h3> | <h3>[🇲🇳 MN](README.mn.md)</h3> | <h3>[🇯🇵 JP](README.ja.md)</h3> | <h3 dir="rtl" lang="he">[HE 🇮🇱](README.he.md)</h3> | 

Generates one fill-in-the-blank "new words" worksheet PDF per lesson (50
total: Shokyu I lessons 1-25, Shokyu II lessons 26-50), styled after the
Mongolian-language worksheet used in the class, but with English
meanings pulled from the [MinnaNoDS](https://github.com/vitto4/MinnaNoDS)
dataset instead of Mongolian ones.

`output/` already has all 50 PDFs generated and ready to use.

## Layout

Same idea as your reference sheet: a bordered grid, two continuously
numbered columns per page (1-25 left, 26-50 right), each row showing

```
-----------------------------------------------------------------
 #  |  kanji                    |  meaning                      |
    |  ························ |                               |
    |  kana                     |                               |
-----------------------------------------------------------------
```

with a dotted rule between the kanji and kana line, plus a header with
the lesson number and a blank "Name" line.

## What's different from the original template, and why

- **English, not Mongolian.** MinnaNoDS already ships an `en` field per
  word, so no separate translation pass was needed for the words
  themselves. A few `en` entries embed a little raw Japanese for clarity
  (e.g. `however ~, even if ~`) — those runs are auto-detected and set in
  the Japanese font so they render instead of showing as missing-glyph
  boxes.
- **Row heights auto-fit their content, and font size auto-shrinks per
  lesson.** Your sample's rows are a fixed height, hand-tuned in Excel
  for that one lesson's word lengths. Across all 50 lessons, English
  definitions run anywhere from one word to 100+ characters (parenthetical
  explanations, example phrases, etc.), so a fixed row height would clip
  text somewhere. The script measures each entry's wrapped text and
  sizes rows to fit, and picks the largest font size (from a small
  preset list) that keeps every page of a given lesson within one A4
  page's height.
- **Pagination for lessons over 50 words.** Word counts range from 22 to
  79 per lesson, so lessons with >50 words spill onto a second page,
  continuing the numbering (51, 52, ...). To avoid mostly-blank pages,
  a lone leftover column (e.g. just 2 words left over) is trimmed to a
  few rows past its last entry instead of padded out to a full 25.

## Usage

```bash
pip install reportlab pyyaml
python generate_worksheets.py                  # regenerate all 50 lessons
python generate_worksheets.py --lessons 7 26    # just specific lessons
python generate_worksheets.py --out my_folder   # different output dir
python generate_worksheets.py --refresh         # re-download the dataset
```

The dataset (`data/minna-no-ds.yaml`) is bundled, and the script will
re-download it from MinnaNoDS's GitHub repo automatically if it's ever
missing or you pass `--refresh`.

## Files

- `../generate_worksheets.py` — the generator
- `data/minna-no-ds.yaml` — cached copy of the MinnaNoDS dataset
- `../fonts/NotoSerifCJKjp-Regular.ttf` — Noto Serif CJK, subset down to just
  the glyphs the dataset actually uses (~370 KB instead of ~24 MB), so
  Japanese text renders correctly regardless of what's installed on your
  machine. (SIL Open Font License; see the Noto CJK repo for full terms.)
- `output/` — all 50 generated worksheet PDFs

## Tweaking the look

Most layout knobs are constants near the top of `../generate_worksheets.py`
(`JP_COL_W`, `MIN_ROW_H`, `BASE_JP_SIZE`, margins, etc.) — worth a look
before touching the drawing code itself.

## Credit / license note

Vocabulary content (words, readings, meanings) comes from *Minna no
Nihongo Shokyu I & II*, © 3A Corporation, via the [MinnaNoDS](https://github.com/vitto4/MinnaNoDS) dataset.
This is for personal study use — not meant for redistribution or commercial use.
