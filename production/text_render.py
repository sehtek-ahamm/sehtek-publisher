"""Draw right-to-left Arabic text with Pillow on any computer.

Arabic letters are shaped with arabic_reshaper and ordered with python-bidi,
then drawn with Pillow's BASIC layout so Windows and Linux give the same result.
"""

import unicodedata

import arabic_reshaper
from bidi.algorithm import get_display
from fontTools.ttLib import TTFont
from PIL import ImageFont

_font_cache = {}
_cmap_cache = {}


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    key = (path, size)
    if key not in _font_cache:
        fnt = ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.BASIC)
        fnt.cmap = _cmap(path)
        _font_cache[key] = fnt
    return _font_cache[key]


def _cmap(path: str) -> set:
    if path not in _cmap_cache:
        _cmap_cache[path] = set(TTFont(path).getBestCmap())
    return _cmap_cache[path]


def _fit_to_font(text: str, cmap: set) -> str:
    """Modern fonts often lack the 'isolated' Arabic presentation forms because they
    draw them with the plain letter. Swap any missing form for its plain letter."""
    out = []
    for ch in text:
        if ord(ch) in cmap:
            out.append(ch)
            continue
        base = unicodedata.normalize("NFKC", ch)
        out.append(base if all(ord(b) in cmap for b in base) else ch)
    return "".join(out)


def visual(text: str, fnt=None) -> str:
    """Logical Arabic text -> shaped, visually ordered string for drawing."""
    shaped = get_display(arabic_reshaper.reshape(text))
    cmap = getattr(fnt, "cmap", None)
    return _fit_to_font(shaped, cmap) if cmap else shaped


def text_width(text: str, fnt) -> int:
    left, _, right, _ = fnt.getbbox(visual(text, fnt))
    return right - left


def wrap(text: str, fnt, max_width: int) -> list:
    """Split text into lines (logical order) that fit max_width."""
    lines = []
    for paragraph in text.split("\n"):
        words, line = paragraph.split(), ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if line and text_width(candidate, fnt) > max_width:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
    return lines


def draw_block(draw, text, fnt, box, fill, align="right", line_gap=1.35, valign="top"):
    """Draw wrapped RTL text inside box=(x0, y0, x1, y1). Returns the bottom y."""
    x0, y0, x1, y1 = box
    lines = wrap(text, fnt, x1 - x0)
    line_h = int(fnt.size * line_gap)
    total_h = line_h * len(lines)
    y = y0 if valign == "top" else y0 + ((y1 - y0) - total_h) // 2
    for line in lines:
        vis = visual(line, fnt)
        left, top, right, _ = fnt.getbbox(vis)
        w = right - left
        if align == "right":
            x = x1 - w
        elif align == "center":
            x = x0 + ((x1 - x0) - w) // 2
        else:
            x = x0
        draw.text((x - left, y), vis, font=fnt, fill=fill)
        y += line_h
    return y


def block_height(text, fnt, max_width, line_gap=1.35) -> int:
    return int(fnt.size * line_gap) * len(wrap(text, fnt, max_width))
