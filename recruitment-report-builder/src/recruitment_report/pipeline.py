"""パイプライン統括.

検証 → KPI計算 → サマリー作成 → PowerPoint作成 を順に実行し、
生成した .pptx を画像化してコンタクトシート(contact-sheet)を作る。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

from . import validate as V
from . import kpi as K
from . import summary as S
from . import pptx_builder as P


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run(current_path: str, previous_path: str, targets_path: str, out_dir: str,
        approve_mismatches: bool = True, verbose: bool = True) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    cur = _load(current_path)
    prev = _load(previous_path)
    targets = _load(targets_path)

    log = []

    def say(msg=""):
        log.append(msg)
        if verbose:
            print(msg)

    say("=" * 68)
    say("recruitment-report-builder — 採用月次レポート生成パイプライン")
    say("=" * 68)

    # 1) 検証
    say("\n[1/4] 検証（Validation）")
    v_cur = V.validate(cur, approve_mismatches=approve_mismatches)
    v_prev = V.validate(prev, approve_mismatches=approve_mismatches)
    say(V.format_report(v_cur))
    say(V.format_report(v_prev))
    if not v_cur.ok or not v_prev.ok:
        raise ValueError("構造エラーにより中断（承認では解消できない不整合）")

    # 2) KPI計算
    say("\n[2/4] KPI計算（KPI）")
    kpi_cur = K.compute_kpis(cur, v_cur.validated_totals)
    kpi_prev = K.compute_kpis(prev, v_prev.validated_totals)
    comp = K.compare(kpi_cur, kpi_prev, targets)
    say(K.format_report(comp))

    # 3) サマリー
    say("\n[3/4] サマリー作成（Summary）")
    summ = S.build_summary(comp)
    say(S.format_report(summ))

    # 4) PowerPoint
    say("\n[4/4] PowerPoint作成（Slides）")
    meta = {
        "department": cur.get("department", ""),
        "period_label": cur.get("period_label", cur.get("period", "")),
    }
    pptx_path = os.path.join(out_dir, "recruitment_report.pptx")
    P.build_presentation(meta, comp, summ, pptx_path)
    say(f"  生成: {pptx_path}（{6}枚）")

    # 画像化 + コンタクトシート
    pngs = render_slides_to_png(pptx_path, out_dir)
    say(f"  スライド画像: {len(pngs)}枚")
    contact = build_contact_sheet(pngs, os.path.join(out_dir, "contact_sheet.png"))
    say(f"  コンタクトシート: {contact}")

    return {
        "validation_current": v_cur,
        "validation_previous": v_prev,
        "comparison": comp,
        "summary": summ,
        "pptx": pptx_path,
        "slide_pngs": pngs,
        "contact_sheet": contact,
        "log": "\n".join(log),
    }


def render_slides_to_png(pptx_path: str, out_dir: str, dpi: int = 150) -> list[str]:
    """スライドを PNG 化する。

    まず LibreOffice(PDF経由) を試み、失敗した環境では python-pptx+Pillow の
    内蔵レンダラにフォールバックする（外部プロセス非依存で常に描画可能）。
    """
    try:
        return _render_via_libreoffice(pptx_path, out_dir, dpi)
    except Exception:
        from . import png_renderer
        return png_renderer.render_pptx_to_png(pptx_path, out_dir, dpi=dpi)


def _render_via_libreoffice(pptx_path: str, out_dir: str, dpi: int) -> list[str]:
    import fitz  # PyMuPDF

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError("LibreOffice(soffice) が見つかりません")

    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", out_dir, pptx_path],
        check=True, capture_output=True, timeout=180,
    )
    pdf_path = os.path.join(out_dir, os.path.splitext(os.path.basename(pptx_path))[0] + ".pdf")
    if not os.path.exists(pdf_path):
        raise RuntimeError("PDF 変換に失敗しました")

    slides_dir = os.path.join(out_dir, "slides")
    os.makedirs(slides_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pngs = []
    for i, page in enumerate(doc, 1):
        pix = page.get_pixmap(matrix=mat)
        p = os.path.join(slides_dir, f"slide_{i:02d}.png")
        pix.save(p)
        pngs.append(p)
    doc.close()
    return pngs


def build_contact_sheet(pngs: list[str], out_path: str, cols: int = 2,
                        margin: int = 40, gap: int = 28, pad: int = 10) -> str:
    """スライド PNG をグリッドに並べてコンタクトシートを作る。"""
    from PIL import Image, ImageDraw, ImageFont

    if not pngs:
        raise ValueError("画像がありません")

    thumbs = [Image.open(p).convert("RGB") for p in pngs]
    tw = max(t.width for t in thumbs)
    th = max(t.height for t in thumbs)
    rows = (len(thumbs) + cols - 1) // cols

    label_h = 46
    title_h = 84
    cell_w = tw + pad * 2
    cell_h = th + pad * 2 + label_h
    sheet_w = margin * 2 + cols * cell_w + (cols - 1) * gap
    sheet_h = margin * 2 + title_h + rows * cell_h + (rows - 1) * gap

    bg = (17, 34, 58)
    sheet = Image.new("RGB", (sheet_w, sheet_h), bg)
    draw = ImageDraw.Draw(sheet)

    def font(size, bold=False):
        candidates = [
            "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
            "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for c in candidates:
            if os.path.exists(c):
                try:
                    return ImageFont.truetype(c, size)
                except Exception:
                    continue
        return ImageFont.load_default()

    draw.text((margin, margin), "採用月次レポート — スライド一覧 (contact sheet)",
              fill=(255, 255, 255), font=font(34, bold=True))
    draw.text((margin, margin + 46), f"{len(thumbs)} slides ｜ recruitment-report-builder",
              fill=(155, 170, 190), font=font(20))

    titles = ["表紙", "サマリー", "採用ファネル", "KPI達成状況", "媒体別パフォーマンス", "次月アクション"]
    for idx, thumb in enumerate(thumbs):
        r, c = divmod(idx, cols)
        x = margin + c * (cell_w + gap)
        y = margin + title_h + r * (cell_h + gap)
        # カード
        draw.rectangle([x, y, x + cell_w, y + cell_h], fill=(255, 255, 255))
        sheet.paste(thumb, (x + pad, y + pad))
        # ラベル
        label = f"{idx + 1:02d}  {titles[idx] if idx < len(titles) else ''}"
        draw.text((x + pad, y + pad + th + 8), label, fill=(30, 40, 60), font=font(24, bold=True))

    sheet.save(out_path)
    return out_path
