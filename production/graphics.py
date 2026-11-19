"""Brand graphics: reel overlays, end card and carousel slides."""

from PIL import Image, ImageDraw

import brand
from text_render import block_height, draw_block, font, text_width, visual

W, H = brand.REEL_SIZE


def _rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _logo_or_name(size_px: int):
    """Logo image if provided, else the brand name drawn as text."""
    if brand.LOGO.exists():
        logo = Image.open(brand.LOGO).convert("RGBA")
        logo.thumbnail((size_px, size_px))
        return logo
    return None


# --- reel overlays (full-frame transparent PNGs) ---------------------------------

def hook_overlay(text: str) -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font(brand.FONT_BOLD, 76)
    max_w = W - 2 * 110
    h = block_height(text, f, max_w, 1.3)
    top = int(H * 0.13)
    _rounded(d, (70, top - 40, W - 70, top + h + 30), 40, brand.SUGAR + (245,))
    draw_block(d, text, f, (110, top, W - 110, top + h), brand.DEEP_ROSE, align="center", line_gap=1.3)
    return img


def subtitle_overlay(text: str) -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font(brand.FONT_BOLD, 64)
    max_w = W - 2 * 120
    h = block_height(text, f, max_w, 1.3)
    bottom = int(H * 0.78)
    top = bottom - h
    _rounded(d, (90, top - 26, W - 90, bottom + 18), 28, brand.TEXT + (150,))
    draw_block(d, text, f, (120, top, W - 120, bottom), brand.WHITE, align="center", line_gap=1.3)
    return img


def watermark_overlay() -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    logo = _logo_or_name(110)
    if logo:
        img.alpha_composite(logo, (W - logo.width - 50, H - logo.height - 230))
    else:
        f = font(brand.FONT_BOLD, 38)
        label = brand.BRAND_NAME
        tw = text_width(label, f)
        _rounded(d, (W - tw - 100, H - 300, W - 50, H - 240), 30, brand.SUGAR + (230,))
        d.text((W - tw - 75, H - 296), visual(label, f), font=f, fill=brand.DEEP_ROSE)
    return img


def end_card(text: str) -> Image.Image:
    img = Image.new("RGB", (W, H), brand.DUSTY_PINK)
    d = ImageDraw.Draw(img)
    cx, cy, r = W // 2, int(H * 0.36), 190
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=brand.SUGAR)
    logo = _logo_or_name(300)
    if logo:
        img.paste(logo, (cx - logo.width // 2, cy - logo.height // 2), logo)
    else:
        draw_block(d, brand.BRAND_NAME, font(brand.FONT_BOLD, 64),
                   (cx - r + 20, cy - 50, cx + r - 20, cy + 50), brand.DEEP_ROSE, align="center", valign="middle")
    draw_block(d, text, font(brand.FONT_BOLD, 72), (110, int(H * 0.56), W - 110, int(H * 0.75)),
               brand.SUGAR, align="center", line_gap=1.3)
    draw_block(d, brand.BRAND_NAME, font(brand.FONT_REGULAR, 44), (110, int(H * 0.86), W - 110, int(H * 0.92)),
               brand.SUGAR, align="center")
    return img


def placeholder_scene(index: int, label: str) -> Image.Image:
    """Offline test image (no OpenAI call)."""
    tones = [(222, 205, 186), (214, 196, 176), (230, 214, 196), (205, 188, 170), (226, 208, 190), (218, 200, 182)]
    img = Image.new("RGB", (1024, 1536), tones[index % len(tones)])
    d = ImageDraw.Draw(img)
    d.ellipse((262, 518, 762, 1018), fill=(236, 226, 196), outline=brand.SUGAR, width=24)
    d.text((40, 40), f"scene {index + 1} (placeholder): {label[:60]}", fill=(120, 100, 90))
    return img


# --- carousel slides (1080x1350 JPEG) ----------------------------------------------

SW, SH = brand.SLIDE_SIZE
MARGIN = 100


def slide_cover(title: str, subtitle: str = "", tag: str = "") -> Image.Image:
    img = Image.new("RGB", (SW, SH), brand.SUGAR)
    d = ImageDraw.Draw(img)
    if tag:
        f = font(brand.FONT_BOLD, 40)
        tw = text_width(tag, f)
        _rounded(d, (SW - MARGIN - tw - 60, 120, SW - MARGIN, 190), 35, brand.DUSTY_PINK)
        d.text((SW - MARGIN - tw - 30, 128), visual(tag, f), font=f, fill=brand.WHITE)
    y = draw_block(d, title, font(brand.FONT_BOLD, 130), (MARGIN, 360, SW - MARGIN, 820), brand.DEEP_ROSE, line_gap=1.2)
    if subtitle:
        draw_block(d, subtitle, font(brand.FONT_REGULAR, 66), (MARGIN, y + 50, SW - MARGIN, 1100), brand.TEXT, line_gap=1.4)
    d.rectangle((0, SH - 230, SW, SH), fill=(236, 214, 211))
    f = font(brand.FONT_BOLD, 48)
    label = "اسحبي"
    lw = text_width(label, f)
    ax, ay = MARGIN, SH - 122
    d.polygon([(ax, ay), (ax + 30, ay - 20), (ax + 30, ay + 20)], fill=brand.DEEP_ROSE)
    d.line((ax + 28, ay, ax + 70, ay), fill=brand.DEEP_ROSE, width=8)
    d.text((ax + 90, SH - 154), visual(label, f), font=f, fill=brand.DEEP_ROSE)
    return img


def slide_point(number, title: str, body: str = "", source: str = "") -> Image.Image:
    img = Image.new("RGB", (SW, SH), brand.SUGAR)
    d = ImageDraw.Draw(img)
    if number is not None:
        num = str(number)
        f = font(brand.FONT_BOLD, 150)
        d.text((SW - MARGIN - text_width(num, f), 90), num, font=f, fill=brand.DUSTY_PINK)
    y = draw_block(d, title, font(brand.FONT_BOLD, 100), (MARGIN, 400, SW - MARGIN, 760), brand.DEEP_ROSE, line_gap=1.25)
    if body:
        draw_block(d, body, font(brand.FONT_REGULAR, 70), (MARGIN, y + 50, SW - MARGIN, SH - 220), brand.TEXT, line_gap=1.45)
    d.line((MARGIN, SH - 170, SW - MARGIN, SH - 170), fill=brand.DUSTY_PINK, width=3)
    if source:
        draw_block(d, f"المصدر: {source}", font(brand.FONT_REGULAR, 36), (MARGIN, SH - 140, SW - MARGIN, SH - 60), brand.DEEP_ROSE)
    return img


def slide_final(title: str) -> Image.Image:
    img = Image.new("RGB", (SW, SH), brand.DUSTY_PINK)
    d = ImageDraw.Draw(img)
    cx, cy, r = SW // 2, 430, 170
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=brand.SUGAR)
    logo = _logo_or_name(260)
    if logo:
        img.paste(logo, (cx - logo.width // 2, cy - logo.height // 2), logo)
    else:
        draw_block(d, brand.BRAND_NAME, font(brand.FONT_BOLD, 58),
                   (cx - r + 20, cy - 45, cx + r - 20, cy + 45), brand.DEEP_ROSE, align="center", valign="middle")
    draw_block(d, title, font(brand.FONT_BOLD, 76), (MARGIN, 720, SW - MARGIN, 1050), brand.SUGAR, align="center", line_gap=1.3)
    draw_block(d, "محتوى تثقيفي لا يغني عن استشارة الطبيب", font(brand.FONT_REGULAR, 36),
               (MARGIN, SH - 150, SW - MARGIN, SH - 80), brand.SUGAR, align="center")
    return img
