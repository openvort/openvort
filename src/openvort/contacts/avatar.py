"""
Default avatar generator — creates a 200x200 PNG with gradient background and 2-char name label.
"""

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from openvort.utils.logging import get_logger

log = get_logger("contacts.avatar")

_SIZE = 200

_GRADIENT_PALETTE = [
    ((255, 107, 107), (255, 142, 83)),
    ((252, 92, 125), (106, 130, 251)),
    ((245, 175, 25), (241, 39, 17)),
    ((17, 153, 142), (56, 239, 125)),
    ((33, 147, 176), (109, 213, 237)),
    ((142, 45, 226), (74, 0, 224)),
    ((238, 9, 121), (255, 106, 0)),
    ((86, 171, 47), (168, 224, 99)),
    ((97, 67, 133), (81, 99, 149)),
    ((0, 176, 155), (150, 201, 61)),
    ((69, 104, 220), (176, 106, 179)),
    ((36, 198, 220), (81, 74, 157)),
    ((5, 117, 230), (2, 27, 121)),
    ((230, 92, 0), (249, 212, 35)),
]

_FONT_SEARCH_PATHS = [
    # macOS
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/Library/Fonts/Arial Unicode MS.ttf",
    # Linux (Debian/Ubuntu/CentOS)
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/google-noto-cjk-fonts/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/wenquanyi/wqy-zenhei/wqy-zenhei.ttc",
    "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
]

_cached_font: ImageFont.FreeTypeFont | None = None
_font_resolved = False


def _resolve_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    global _cached_font, _font_resolved
    if _font_resolved:
        return _cached_font if _cached_font else ImageFont.load_default()

    _font_resolved = True
    for path in _FONT_SEARCH_PATHS:
        if not Path(path).exists():
            continue
        try:
            _cached_font = ImageFont.truetype(path, size)
            log.info("头像字体: %s", path)
            return _cached_font
        except Exception:
            continue

    log.warning("未找到中文字体，头像文字可能显示异常")
    return ImageFont.load_default()


def _name_hash(name: str) -> int:
    h = 0
    for c in name:
        h = ord(c) + ((h << 5) - h)
    return abs(h)


def name_label(name: str) -> str:
    s = name.strip()
    if not s:
        return "?"
    if len(s) <= 2:
        return s
    return s[-2:]


def _lerp_color(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def generate_avatar_png(name: str) -> bytes:
    """Generate a 200x200 circular PNG avatar with gradient background and name label."""
    label = name_label(name)
    colors = _GRADIENT_PALETTE[_name_hash(name) % len(_GRADIENT_PALETTE)]

    img = Image.new("RGBA", (_SIZE, _SIZE), (0, 0, 0, 0))
    gradient = Image.new("RGB", (_SIZE, _SIZE))

    max_dist = _SIZE * 2 - 2
    pixels = []
    for y in range(_SIZE):
        for x in range(_SIZE):
            t = (x + y) / max_dist if max_dist else 0
            pixels.append(_lerp_color(colors[0], colors[1], t))
    gradient.putdata(pixels)

    mask = Image.new("L", (_SIZE, _SIZE), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse([0, 0, _SIZE - 1, _SIZE - 1], fill=255)

    img.paste(gradient, (0, 0), mask)

    font_size = 72 if len(label) >= 2 else 90
    font = _resolve_font(font_size)
    if isinstance(font, ImageFont.FreeTypeFont) and font.size != font_size:
        try:
            font = ImageFont.truetype(font.path, font_size)
        except Exception:
            pass

    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (_SIZE - tw) / 2 - bbox[0]
    ty = (_SIZE - th) / 2 - bbox[1]
    draw.text((tx, ty), label, fill=(255, 255, 255), font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def generate_and_save_avatar(name: str) -> str:
    """Generate avatar PNG, save to uploads/avatars/, return the URL path."""
    from openvort.web.upload_utils import save_upload

    png_data = generate_avatar_png(name)
    return save_upload("avatars", png_data, "png")
