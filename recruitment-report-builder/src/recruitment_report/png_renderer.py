"""PPTX → PNG レンダラ（LibreOffice非依存）.

python-pptx で生成したスライドの図形を走査し、Pillow で PNG に描画する。
実際に生成された .pptx の内容をそのまま画像化するため、PowerPointと一致する。
"""

from __future__ import annotations

import os

from pptx import Presentation
from pptx.util import Emu
from pptx.enum.dml import MSO_FILL_TYPE
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

from PIL import Image, ImageDraw, ImageFont

EMU_PER_INCH = 914400

_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
_FONT_PATH = next((p for p in _FONT_CANDIDATES if os.path.exists(p)), None)
_font_cache: dict = {}


def _font(px: int):
    px = max(6, int(px))
    if px not in _font_cache:
        if _FONT_PATH:
            _font_cache[px] = ImageFont.truetype(_FONT_PATH, px)
        else:
            _font_cache[px] = ImageFont.load_default()
    return _font_cache[px]


def _rgb(color):
    return (color[0], color[1], color[2])


def _wrap(text: str, font, max_w: int) -> list[str]:
    """日本語対応の折り返し（スペースがあれば優先、無ければ文字単位）。"""
    if not text:
        return [""]
    lines = []
    for raw in text.split("\n"):
        if font.getlength(raw) <= max_w:
            lines.append(raw)
            continue
        cur = ""
        for ch in raw:
            if font.getlength(cur + ch) <= max_w or not cur:
                cur += ch
            else:
                lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
    return lines


def _shape_fill(shape):
    try:
        if shape.fill.type == MSO_FILL_TYPE.SOLID:
            return _rgb(shape.fill.fore_color.rgb)
    except Exception:
        pass
    return None


def _shape_line(shape):
    try:
        if shape.line.fill.type == MSO_FILL_TYPE.SOLID:
            w = shape.line.width
            wpx = max(1, int(Emu(w).inches * _DPI)) if w else 1
            return _rgb(shape.line.color.rgb), wpx
    except Exception:
        pass
    return None, 0


_DPI = 150


def _draw_shape(draw: ImageDraw.ImageDraw, shape, scale: float):
    x0 = int(shape.left * scale)
    y0 = int(shape.top * scale)
    w = int(shape.width * scale)
    h = int(shape.height * scale)
    x1, y1 = x0 + w, y0 + h

    fill = _shape_fill(shape)
    line_color, line_w = _shape_line(shape)

    is_rounded = False
    radius_px = 0
    if shape.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE:
        try:
            from pptx.enum.shapes import MSO_SHAPE
            if shape.auto_shape_type == MSO_SHAPE.ROUNDED_RECTANGLE:
                is_rounded = True
                adj = 0.1
                try:
                    adj = float(shape.adjustments[0])
                except Exception:
                    adj = 0.1
                radius_px = max(1, int(min(w, h) * adj))
        except Exception:
            pass

    if fill is not None or line_color is not None:
        if is_rounded:
            draw.rounded_rectangle([x0, y0, x1, y1], radius=radius_px,
                                   fill=fill, outline=line_color, width=line_w or 1)
        else:
            draw.rectangle([x0, y0, x1, y1], fill=fill,
                           outline=line_color, width=line_w or 1)


def _draw_text(draw: ImageDraw.ImageDraw, shape, scale: float):
    if not shape.has_text_frame:
        return
    tf = shape.text_frame
    x0 = int(shape.left * scale)
    y0 = int(shape.top * scale)
    w = int(shape.width * scale)
    h = int(shape.height * scale)

    anchor = tf.vertical_anchor

    # 各段落を行に展開
    para_blocks = []  # list of (list_of_line_dicts, space_after_px)
    total_h = 0
    for para in tf.paragraphs:
        runs = para.runs
        if not runs:
            para_blocks.append(([], int(6 * scale * EMU_PER_INCH / EMU_PER_INCH)))
            continue
        # 段落内は同一行に連結（wrap は段落テキスト全体で行うが、ランのスタイルを保持）
        # ここでは簡略化のため段落を「連結テキスト＋代表フォント」で扱いつつ、
        # ラン単位の色・太字はセグメントとして保持する。
        segments = []
        for r in runs:
            size_px = int((r.font.size.pt if r.font.size else 12) * _DPI / 72.0)
            try:
                color = _rgb(r.font.color.rgb) if r.font.color and r.font.color.type is not None else (0, 0, 0)
            except Exception:
                color = (0, 0, 0)
            segments.append({"text": r.text, "font": _font(size_px), "color": color,
                             "size": size_px})
        # 折り返し: セグメントを順に配置し幅超過で改行
        lines = _wrap_segments(segments, w)
        line_h = max((s["size"] for s in segments), default=12) * 1.28
        align = para.alignment or PP_ALIGN.LEFT
        sa = int((para.space_after.pt if para.space_after else 2) * _DPI / 72.0)
        para_blocks.append((lines, line_h, align, sa))
        total_h += line_h * len(lines) + sa

    # 垂直位置
    if anchor == MSO_ANCHOR.MIDDLE:
        cy = y0 + (h - total_h) / 2
    elif anchor == MSO_ANCHOR.BOTTOM:
        cy = y0 + (h - total_h)
    else:
        cy = y0

    for block in para_blocks:
        if len(block) == 2:  # empty paragraph
            cy += block[1]
            continue
        lines, line_h, align, sa = block
        for line in lines:
            line_w = sum(seg["font"].getlength(seg["text"]) for seg in line)
            if align == PP_ALIGN.CENTER:
                cx = x0 + (w - line_w) / 2
            elif align == PP_ALIGN.RIGHT:
                cx = x0 + (w - line_w)
            else:
                cx = x0
            for seg in line:
                draw.text((cx, cy), seg["text"], font=seg["font"], fill=seg["color"])
                cx += seg["font"].getlength(seg["text"])
            cy += line_h
        cy += sa


def _wrap_segments(segments, max_w):
    """複数スタイルのセグメント列を、幅 max_w で折り返して行(=セグメントの部分列)に分割。"""
    lines = [[]]
    cur_w = 0.0
    for seg in segments:
        for ch in seg["text"]:
            cw = seg["font"].getlength(ch)
            if cur_w + cw > max_w and lines[-1]:
                lines.append([])
                cur_w = 0.0
            if lines[-1] and lines[-1][-1]["font"] is seg["font"] and lines[-1][-1]["color"] == seg["color"]:
                lines[-1][-1]["text"] += ch
            else:
                lines[-1].append({"text": ch, "font": seg["font"], "color": seg["color"], "size": seg["size"]})
            cur_w += cw
    return lines


def render_pptx_to_png(pptx_path: str, out_dir: str, dpi: int = 150) -> list[str]:
    global _DPI
    _DPI = dpi
    prs = Presentation(pptx_path)
    scale = dpi / EMU_PER_INCH  # EMU -> px
    W = int(prs.slide_width * scale)
    H = int(prs.slide_height * scale)

    slides_dir = os.path.join(out_dir, "slides")
    os.makedirs(slides_dir, exist_ok=True)
    pngs = []
    for i, slide in enumerate(prs.slides, 1):
        img = Image.new("RGB", (W, H), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        for shape in slide.shapes:
            _draw_shape(draw, shape, scale)
        for shape in slide.shapes:
            _draw_text(draw, shape, scale)
        p = os.path.join(slides_dir, f"slide_{i:02d}.png")
        img.save(p)
        pngs.append(p)
    return pngs
