#!/usr/bin/env python3
"""generate_pptx.py — 求人媒体結果報告のPowerPointを生成する。

- スライド内の数値は計算済みCSV（kpi_results.csv / kpi_by_group.csv）と
  そこから作った summary_input.json からのみ取得する（手入力・再計算をしない）。
- 算出不可(N/A)→「算出不可」, 前月なし(NEW)→「新規」, 目標なし(NOT_SET)→「未設定」と表示。0にしない。
- テーマ色は会社設定 report.brand_color を1箇所で参照し、企業別に差し替え可能。
- 生成後に validate_pptx で検証し、--export-images でLibreOfficeによる画像書き出しも行う。

使用例:
  python3 scripts/generate_pptx.py \
    --kpi output/2026-06/kpi_results.csv \
    --group output/2026-06/kpi_by_group.csv \
    --summary-input demo/generated-summary-input.json \
    --summary demo/generated-summary.md \
    --settings demo/demo-company-settings.yaml \
    --template assets/blank-report-template.pptx \
    --output demo/demo-report.pptx \
    --validate-report output/2026-06/pptx_validation.csv \
    --export-images

  # 空テンプレートの生成のみ
  python3 scripts/generate_pptx.py --make-template assets/blank-report-template.pptx
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Emu, Inches, Pt

sys.path.insert(0, str(Path(__file__).parent))
from common import NA, NEW, NOT_SET, load_settings, setup_logger

SLIDE_W, SLIDE_H = Inches(13.333), Inches(7.5)
DEFAULT_BRAND = "#2E5E8C"
GRAY = RGBColor(0x59, 0x59, 0x59)
LIGHT = RGBColor(0xF2, 0xF4, 0xF7)
DARK = RGBColor(0x22, 0x22, 0x22)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

SLIDE_KEYS = ["cover", "executive_summary", "main_kpi", "by_media", "by_job",
              "by_location", "best_worst", "issues", "actions", "open_items"]


# ---------- 表示変換（特殊値を0にしない） ----------
def _is_special(v) -> bool:
    return isinstance(v, str) and v in (NA, NEW, NOT_SET)


def disp_special(v) -> str:
    return {NA: "算出不可", NEW: "新規", NOT_SET: "未設定"}.get(v, str(v))


def disp_int(v) -> str:
    if v is None or v == "" or (isinstance(v, float) and pd.isna(v)):
        return "―"
    if _is_special(v):
        return disp_special(v)
    return f"{int(float(v)):,}"


def disp_yen(v) -> str:
    if _is_special(v):
        return disp_special(v)
    if v is None or v == "" or (isinstance(v, float) and pd.isna(v)):
        return "―"
    return f"{int(round(float(v))):,}円"


def disp_pct(v) -> str:
    if _is_special(v):
        return disp_special(v)
    if v is None or v == "" or (isinstance(v, float) and pd.isna(v)):
        return "―"
    return f"{float(v):.1f}%"


def disp_signed_pct(v) -> str:
    if _is_special(v):
        return disp_special(v)
    if v is None or v == "" or (isinstance(v, float) and pd.isna(v)):
        return "―"
    return f"{float(v):+.1f}%"


def hex_to_rgb(color: str) -> RGBColor:
    c = (color or DEFAULT_BRAND).lstrip("#")
    return RGBColor(int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


# ---------- 描画ヘルパー ----------
def _set_text(tf, text, size, color=DARK, bold=False, align=PP_ALIGN.LEFT):
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = "Meiryo"
    return p


def add_textbox(slide, x, y, w, h, text, size, **kw):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tb.text_frame.word_wrap = True
    _set_text(tb.text_frame, text, size, **kw)
    return tb


def add_title(slide, text, brand):
    bar = slide.shapes.add_shape(1, Inches(0), Inches(0), SLIDE_W, Inches(0.12))
    bar.fill.solid(); bar.fill.fore_color.rgb = brand; bar.line.fill.background()
    tb = slide.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(12.1), Inches(0.9))
    tf = tb.text_frame; tf.word_wrap = True
    _set_text(tf, text, 26, color=DARK, bold=True)
    return tb


def add_page_number(slide, n, brand):
    tb = slide.shapes.add_textbox(Inches(12.4), Inches(7.05), Inches(0.8), Inches(0.35))
    _set_text(tb.text_frame, str(n), 11, color=GRAY, align=PP_ALIGN.RIGHT)


def add_logo_placeholder(slide, brand):
    """差し替え用のロゴ枠（右上）。実在ロゴは入れない。"""
    box = slide.shapes.add_textbox(Inches(11.5), Inches(0.32), Inches(1.6), Inches(0.5))
    _set_text(box.text_frame, "［ロゴ］", 10, color=GRAY, align=PP_ALIGN.RIGHT)


def add_card(slide, x, y, w, h, label, value, sub, brand):
    card = slide.shapes.add_shape(1, x, y, w, h)
    card.fill.solid(); card.fill.fore_color.rgb = LIGHT
    card.line.color.rgb = brand; card.line.width = Pt(1)
    card.shadow.inherit = False
    tf = card.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.15); tf.margin_right = Inches(0.15)
    p0 = tf.paragraphs[0]; p0.alignment = PP_ALIGN.CENTER
    r0 = p0.add_run(); r0.text = label
    r0.font.size = Pt(13); r0.font.color.rgb = GRAY; r0.font.name = "Meiryo"
    p1 = tf.add_paragraph(); p1.alignment = PP_ALIGN.CENTER
    r1 = p1.add_run(); r1.text = value
    r1.font.size = Pt(34); r1.font.bold = True; r1.font.color.rgb = brand; r1.font.name = "Meiryo"
    if sub:
        p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
        r2 = p2.add_run(); r2.text = sub
        r2.font.size = Pt(12); r2.font.color.rgb = DARK; r2.font.name = "Meiryo"
    return card


def add_table(slide, x, y, w, h, headers, rows, brand):
    shape = slide.shapes.add_table(len(rows) + 1, len(headers), x, y, w, h)
    table = shape.table
    for j, htext in enumerate(headers):
        cell = table.cell(0, j)
        cell.fill.solid(); cell.fill.fore_color.rgb = brand
        tf = cell.text_frame; tf.word_wrap = True
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = htext
        r.font.size = Pt(11); r.font.bold = True; r.font.color.rgb = WHITE; r.font.name = "Meiryo"
    for i, row in enumerate(rows, start=1):
        for j, val in enumerate(row):
            cell = table.cell(i, j)
            cell.fill.solid()
            cell.fill.fore_color.rgb = WHITE if i % 2 else LIGHT
            tf = cell.text_frame; tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.RIGHT
            r = p.add_run(); r.text = str(val)
            r.font.size = Pt(11); r.font.color.rgb = DARK; r.font.name = "Meiryo"
    return table


def add_bar_chart(slide, x, y, w, h, categories, series, brand, title=None):
    data = CategoryChartData()
    data.categories = categories
    for name, values in series.items():
        data.add_series(name, values)
    gframe = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, x, y, w, h, data)
    chart = gframe.chart
    chart.has_legend = len(series) > 1
    if chart.has_legend:
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(11)
    plot = chart.plots[0]
    plot.has_data_labels = True
    plot.data_labels.font.size = Pt(11)
    plot.data_labels.number_format = "#,##0"
    plot.data_labels.number_format_is_linked = False
    if title:
        chart.has_title = True
        chart.chart_title.text_frame.text = title
        chart.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(12)
    else:
        chart.has_title = False
    for s in chart.series:
        s.format.fill.solid(); s.format.fill.fore_color.rgb = brand
    return chart


def add_bullets(slide, x, y, w, h, lines, size=14):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame; tf.word_wrap = True
    first = True
    for line in lines:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        run = p.add_run(); run.text = ("・" + line) if not line.startswith(("1", "2", "3", "4", "5")) else line
        run.font.size = Pt(size); run.font.color.rgb = DARK; run.font.name = "Meiryo"
        p.space_after = Pt(6)
    return tb


# ---------- サマリーMarkdownの節分割 ----------
def parse_summary_sections(md_path: str | None) -> dict[int, dict]:
    sections: dict[int, dict] = {}
    if not md_path or not Path(md_path).exists():
        return sections
    text = Path(md_path).read_text(encoding="utf-8")
    cur = None
    for line in text.splitlines():
        m = re.match(r"^##\s+(\d+)\.\s+(.*)$", line)
        if m:
            cur = int(m.group(1))
            sections[cur] = {"title": m.group(2).strip(), "lines": []}
        elif cur is not None:
            s = line.strip()
            if s.startswith(("-", "・", "1.", "2.", "3.", "4.", "5.", "6.", "7.")):
                sections[cur]["lines"].append(re.sub(r"^[-・]\s*", "", s))
    return sections


# ---------- スライド生成 ----------
def build_presentation(kpi, group, sinput, sections, settings, template) -> Presentation:
    report = settings.get("report", {}) or {}
    company = settings.get("company", {}) or {}
    brand = hex_to_rgb(report.get("brand_color", DEFAULT_BRAND))
    enabled = report.get("slides", SLIDE_KEYS)

    prs = Presentation(template) if template and Path(template).exists() else Presentation()
    prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H
    blank = prs.slide_layouts[6]

    overall = sinput.get("overall", {})
    om = overall.get("metrics", {})
    oc = overall.get("comparison", {})
    page = [0]

    def new_slide(title=None):
        slide = prs.slides.add_slide(blank)
        page[0] += 1
        if title:
            add_title(slide, title, brand)
        add_page_number(slide, page[0], brand)
        return slide

    def group_rows(dim):
        return group[group["区分"] == dim]

    # 1. 表紙
    if "cover" in enabled:
        slide = prs.slides.add_slide(blank); page[0] += 1
        band = slide.shapes.add_shape(1, Inches(0), Inches(2.4), SLIDE_W, Inches(1.9))
        band.fill.solid(); band.fill.fore_color.rgb = brand; band.line.fill.background()
        band.shadow.inherit = False
        _set_text(band.text_frame, report.get("report_title", "求人媒体 月次結果報告書"),
                  34, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
        band.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        sub = f"対象期間: {company.get('current_period', '')}"
        add_textbox(slide, Inches(0.6), Inches(4.5), Inches(12), Inches(0.5),
                    sub, 18, color=DARK, align=PP_ALIGN.CENTER)
        info = f"{company.get('name', '')}　{company.get('department', '')}"
        add_textbox(slide, Inches(0.6), Inches(5.1), Inches(12), Inches(0.5),
                    info, 16, color=GRAY, align=PP_ALIGN.CENTER)
        add_textbox(slide, Inches(0.6), Inches(6.7), Inches(12), Inches(0.4),
                    f"作成日: {date.today().isoformat()}", 12, color=GRAY, align=PP_ALIGN.CENTER)
        add_logo_placeholder(slide, brand)
        add_page_number(slide, page[0], brand)

    # 2. エグゼクティブサマリー
    if "executive_summary" in enabled:
        slide = new_slide("エグゼクティブサマリー")
        cards = [("応募数", disp_int(om.get("applications")), disp_signed_pct(oc.get("applications_mom_pct")) + "（前月比）"),
                 ("採用数", (disp_int(om.get("hires")) + "名") if om.get("hires") is not None else "―", ""),
                 ("応募単価", disp_yen(om.get("cpa_yen")), disp_signed_pct(oc.get("cpa_mom_pct")) + "（前月比）")]
        cw = Inches(3.7)
        for i, (lb, vv, sb) in enumerate(cards):
            add_card(slide, Inches(0.7 + i * 4.0), Inches(1.5), cw, Inches(1.9), lb, vv, sb, brand)
        bullets = sections.get(1, {}).get("lines", [])[:2] + sections.get(2, {}).get("lines", [])[:2]
        check = sections.get(7, {}).get("lines", [])[:1]
        add_textbox(slide, Inches(0.7), Inches(3.7), Inches(12), Inches(0.4), "要点", 15, color=brand, bold=True)
        add_bullets(slide, Inches(0.7), Inches(4.1), Inches(12), Inches(2.0), bullets, size=13)
        if check:
            add_textbox(slide, Inches(0.7), Inches(6.1), Inches(12), Inches(0.4), "要確認", 14, color=brand, bold=True)
            add_bullets(slide, Inches(0.7), Inches(6.45), Inches(12), Inches(0.6), check, size=12)

    # 3. 主要KPI
    if "main_kpi" in enabled:
        title = f"当月の応募は{disp_int(om.get('applications'))}件（前月比{disp_signed_pct(oc.get('applications_mom_pct'))}）"
        slide = new_slide(title)
        c1 = [("表示数", disp_int(om.get("impressions"))), ("クリック数", disp_int(om.get("clicks"))),
              ("応募数", disp_int(om.get("applications"))), ("採用数", disp_int(om.get("hires")))]
        c2 = [("クリック率", disp_pct(om.get("ctr_pct"))), ("応募率", disp_pct(om.get("application_rate_pct"))),
              ("応募単価", disp_yen(om.get("cpa_yen"))), ("採用単価", disp_yen(om.get("cph_yen")))]
        for i, (lb, vv) in enumerate(c1):
            add_card(slide, Inches(0.7 + i * 3.05), Inches(1.6), Inches(2.8), Inches(1.6), lb, vv, "", brand)
        for i, (lb, vv) in enumerate(c2):
            add_card(slide, Inches(0.7 + i * 3.05), Inches(3.5), Inches(2.8), Inches(1.6), lb, vv, "", brand)
        add_textbox(slide, Inches(0.7), Inches(5.4), Inches(12), Inches(1.2),
                    f"広告費: {disp_yen(om.get('cost_yen'))}　／　応募数 目標比: {disp_pct(oc.get('applications_vs_target_pct'))}"
                    f"　／　応募単価 目標比: {disp_pct(oc.get('cpa_vs_target_pct'))}", 15, color=DARK)

    # 4-6. 媒体別・職種別・拠点別
    dim_map = [("by_media", "媒体", "応募数はどの媒体が牽引したか"),
               ("by_job", "職種", "職種別の応募数と応募単価"),
               ("by_location", "拠点", "拠点別の応募数と応募単価")]
    for key, dim, subtitle in dim_map:
        if key not in enabled:
            continue
        gr = group_rows(dim)
        if gr.empty:
            continue
        cats = list(gr["対象"])
        apps = [int(float(x)) if str(x) not in ("", "nan") else 0 for x in gr["応募数"]]
        top = cats[apps.index(max(apps))] if apps else "―"
        slide = new_slide(f"応募数は{top}が最多（{dim}別）")
        add_bar_chart(slide, Inches(0.6), Inches(1.5), Inches(6.2), Inches(4.6),
                      cats, {"応募数": apps}, brand)
        headers = [dim, "応募数", "応募単価", "採用数", "応募数前月比"]
        rows = [[r["対象"], disp_int(r["応募数"]), disp_yen(_v(r["応募単価"])),
                 disp_int(r["採用数"]), disp_signed_pct(_v(r["応募数前月比"]))]
                for _, r in gr.iterrows()]
        add_table(slide, Inches(7.0), Inches(1.6), Inches(5.7), Inches(0.4 + 0.45 * len(rows)),
                  headers, rows, brand)
        add_textbox(slide, Inches(7.0), Inches(6.2), Inches(5.7), Inches(0.7),
                    "※棒グラフは応募数。応募単価は右表に併記（算出不可・未設定はその旨を表示）。",
                    10, color=GRAY)

    # 7. 好調求人・要改善求人
    if "best_worst" in enabled:
        slide = new_slide("好調な求人と要改善の求人")
        good = sinput.get("judgements", {}).get("good", [])
        priority = sinput.get("judgements", {}).get("priority", [])
        add_textbox(slide, Inches(0.7), Inches(1.4), Inches(5.9), Inches(0.4), "好調な求人", 16, color=brand, bold=True)
        glines = [f"{g['label']}（{ '・'.join(g['reasons']) }）" for g in good] or ["該当なし"]
        add_bullets(slide, Inches(0.7), Inches(1.85), Inches(5.9), Inches(4.8), glines, size=12)
        add_textbox(slide, Inches(6.9), Inches(1.4), Inches(5.9), Inches(0.4), "要改善の求人（優先度順）", 16, color=brand, bold=True)
        plines = [f"{p['rank']}. [{p['level']}] {p['label']}（{p['reason']}）" for p in priority] or ["該当なし"]
        add_bullets(slide, Inches(6.9), Inches(1.85), Inches(5.9), Inches(4.8), plines, size=12)

    # 8. 課題分析
    if "issues" in enabled:
        slide = new_slide("課題分析")
        lines = sections.get(4, {}).get("lines", []) or ["（サマリーの課題セクションが見つかりません）"]
        add_bullets(slide, Inches(0.7), Inches(1.5), Inches(12), Inches(5.4), lines, size=13)

    # 9. 次月の改善案
    if "actions" in enabled:
        slide = new_slide("次月の改善案")
        lines = (sections.get(5, {}).get("lines", []) + sections.get(6, {}).get("lines", [])) \
            or ["（サマリーの改善案セクションが見つかりません）"]
        add_bullets(slide, Inches(0.7), Inches(1.5), Inches(12), Inches(5.4), lines, size=13)

    # 10. 要確認事項
    if "open_items" in enabled:
        slide = new_slide("要確認事項（人による確認が必要）")
        lines = sections.get(7, {}).get("lines", []) or ["（要確認セクションが見つかりません）"]
        add_bullets(slide, Inches(0.7), Inches(1.5), Inches(12), Inches(5.4), lines, size=13)

    return prs


def _v(x):
    """CSVセル値を数値/特殊値へ。"""
    if x in (NA, NEW, NOT_SET):
        return x
    try:
        f = float(x)
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        return x


# ---------- 生成後の自動検証 ----------
def validate_pptx(path: str, expected_slides: int, kpi_overall: dict) -> list[dict]:
    findings = []

    def add(level, item, message):
        findings.append({"level": level, "item": item, "message": message})

    try:
        prs = Presentation(path)
    except Exception as e:
        return [{"level": "error", "item": "open", "message": f"ファイルを開けません: {e}"}]

    slides = list(prs.slides)
    if len(slides) != expected_slides:
        add("error", "slide_count", f"スライド数が想定({expected_slides})と異なります: {len(slides)}")

    titles = []
    for i, slide in enumerate(slides, start=1):
        texts = _slide_texts(slide)
        joined = " ".join(texts)
        if not joined.strip():
            add("error", "blank_slide", f"{i}枚目が空白です")
        # タイトル = 最初の非数字テキスト
        title = next((t for t in texts if t and not t.isdigit()), "")
        titles.append(title)
        if "N/A" in joined or "NOT_SET" in joined or "NEW" in joined or "nan" in joined:
            add("error", "special_value", f"{i}枚目に未変換の特殊値が残っています")
        if not any(t.isdigit() for t in texts):
            add("warning", "slide_number", f"{i}枚目にスライド番号が見当たりません")
        # 文字サイズ
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    for run in para.runs:
                        if run.text.strip() and run.font.size and run.font.size < Pt(10):
                            add("warning", "font_size", f"{i}枚目に10pt未満の文字があります: {run.text[:12]}")
                            break
    dup = {t for t in titles if titles.count(t) > 1 and t}
    if dup:
        add("warning", "title_dup", f"タイトルが重複しています: {dup}")

    # オブジェクトの重なり
    for i, slide in enumerate(slides, start=1):
        boxes = [(s.left, s.top, s.width, s.height) for s in slide.shapes
                 if s.left is not None and s.width and s.height]
        for a in range(len(boxes)):
            for b in range(a + 1, len(boxes)):
                if _overlap_ratio(boxes[a], boxes[b]) > 0.6:
                    add("warning", "overlap", f"{i}枚目で図形が大きく重なっています")
                    break
            else:
                continue
            break

    # 数値の一致（全体応募数・広告費・応募単価がどこかに表示されているか）
    all_text = " ".join(" ".join(_slide_texts(s)) for s in slides)
    for label, val in (("応募数", kpi_overall.get("applications")),
                       ("広告費", kpi_overall.get("cost_yen"))):
        if val is not None and f"{int(float(val)):,}" not in all_text:
            add("error", "number_match", f"全体{label}({int(float(val)):,})がスライドに見つかりません")
    return findings


def _slide_texts(slide) -> list[str]:
    texts = []
    for shape in slide.shapes:
        if shape.has_text_frame:
            texts.append(shape.text_frame.text)
        if shape.has_table:
            for row in shape.table.rows:
                for cell in row.cells:
                    texts.append(cell.text)
    return [t for t in texts if t is not None]


def _overlap_ratio(a, b) -> float:
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    smaller = min(aw * ah, bw * bh)
    return inter / smaller if smaller else 0.0


def export_images(pptx_path: str, out_dir: str, logger) -> bool:
    """各スライドを画像化する。まずLibreOffice→PDF→PNGを試み、
    使えない環境ではPillowによる簡易レンダリングへフォールバックする（処理は失敗させない）。"""
    import shutil
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    soffice = shutil.which("libreoffice") or shutil.which("soffice")
    if soffice:
        try:
            subprocess.run([soffice, "--headless", "--convert-to", "pdf",
                            "--outdir", str(out), str(Path(pptx_path).resolve())],
                           check=True, capture_output=True, timeout=120)
            pdf = out / (Path(pptx_path).stem + ".pdf")
            if pdf.exists() and pdf.stat().st_size > 0:
                if _pdf_to_png(pdf, out, logger):
                    logger.info("LibreOfficeでスライド画像を書き出しました: %s", out)
                    return True
            else:
                logger.warning("LibreOfficeがPDFを生成できませんでした（この環境ではpptx変換に非対応）")
        except Exception as e:
            logger.warning("LibreOfficeでの変換に失敗しました: %s", e)
    # フォールバック: Pillowで簡易レンダリング
    if _render_slides_pillow(pptx_path, out, logger):
        logger.info("Pillowでスライド画像を書き出しました（簡易レンダリング）: %s", out)
        return True
    logger.warning("スライド画像の書き出しをスキップしました（レンダリング手段なし）")
    return False


def _pdf_to_png(pdf: Path, out: Path, logger) -> bool:
    import shutil
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(pdf))
        for i, pageobj in enumerate(doc, start=1):
            pageobj.get_pixmap(dpi=110).save(str(out / f"slide-{i:02d}.png"))
        return doc.page_count > 0
    except Exception:
        pass
    if shutil.which("pdftoppm"):
        try:
            subprocess.run(["pdftoppm", "-png", "-r", "110", str(pdf), str(out / "slide")],
                           check=True, capture_output=True, timeout=120)
            return True
        except Exception:
            return False
    return False


def _find_jp_font():
    from pathlib import Path as _P
    for p in ("/etc/alternatives/fonts-japanese-gothic.ttf",
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
              "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf"):
        if _P(p).exists():
            return p
    return None


def _render_slides_pillow(pptx_path: str, out: Path, logger) -> bool:
    """python-pptxの図形を読み、Pillowで各スライドを近似描画する（環境非依存の目視確認用）。"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return False
    font_path = _find_jp_font()
    if not font_path:
        logger.warning("日本語フォントが見つからないためPillowレンダリングをスキップします")
        return False

    prs = Presentation(pptx_path)
    SCALE = 96 / 914400  # EMU→px (96dpi)
    W = int(prs.slide_width * SCALE); H = int(prs.slide_height * SCALE)

    def font(sz):
        return ImageFont.truetype(font_path, max(9, int(sz * SCALE * 12700 / 12700 * 1.0)))

    def px(v):
        return int(v * SCALE)

    def rgb(color, default=(34, 34, 34)):
        try:
            return (color[0], color[1], color[2])
        except Exception:
            return default

    for idx, slide in enumerate(prs.slides, start=1):
        img = Image.new("RGB", (W, H), (255, 255, 255))
        d = ImageDraw.Draw(img)
        for shape in slide.shapes:
            if shape.left is None:
                continue
            x, y, w, h = px(shape.left), px(shape.top), px(shape.width or 0), px(shape.height or 0)
            # 塗り（オートシェイプ）
            if shape.shape_type == 1 or (shape.has_text_frame and shape.fill.type is not None):
                try:
                    if shape.fill.type == 1:  # solid
                        d.rectangle([x, y, x + w, y + h], fill=rgb(shape.fill.fore_color.rgb, (242, 244, 247)))
                except Exception:
                    pass
            # 表
            if shape.has_table:
                _draw_table(d, shape.table, x, y, w, h, font)
                continue
            # グラフ（棒）
            if shape.has_chart:
                _draw_chart(d, shape.chart, x, y, w, h, font)
                continue
            # テキスト
            if shape.has_text_frame:
                ty = y + 4
                for para in shape.text_frame.paragraphs:
                    text = "".join(r.text for r in para.runs) or para.text
                    if not text:
                        continue
                    sz = 18
                    col = (34, 34, 34)
                    if para.runs:
                        rf = para.runs[0].font
                        if rf.size:
                            sz = rf.size.pt
                        try:
                            if rf.color and rf.color.type is not None:
                                col = rgb(rf.color.rgb, col)
                        except Exception:
                            pass
                    f = ImageFont.truetype(font_path, max(9, int(sz * 96 / 72)))
                    lines = _wrap_draw(d, text, x + 6, ty, w - 12, f, col)
                    ty += lines * (int(sz * 96 / 72) + 3) + 4
        img.save(str(out / f"slide-{idx:02d}.png"))
    _make_contact_sheet(out, len(list(prs.slides)))
    return True


def _wrap_draw(d, text, x, y, maxw, font, color) -> int:
    """テキストを折り返して描画し、使用した行数を返す。"""
    line = ""
    cy = y
    count = 0
    for ch in text:
        if d.textlength(line + ch, font=font) > maxw and line:
            d.text((x, cy), line, font=font, fill=color)
            cy += font.size + 3
            count += 1
            line = ch
        else:
            line += ch
    if line:
        d.text((x, cy), line, font=font, fill=color)
        count += 1
    return max(count, 1)


def _draw_table(d, table, x, y, w, h, font):
    rows = len(table.rows); cols = len(table.columns)
    cw = w // max(cols, 1); rh = h // max(rows, 1)
    from PIL import ImageFont
    f = _find_jp_font()
    ft = ImageFont.truetype(f, 13)
    for i in range(rows):
        for j in range(cols):
            cx, cy = x + j * cw, y + i * rh
            fill = (46, 94, 140) if i == 0 else (255, 255, 255) if i % 2 else (242, 244, 247)
            d.rectangle([cx, cy, cx + cw, cy + rh], fill=fill, outline=(200, 200, 200))
            txt = table.cell(i, j).text
            d.text((cx + 4, cy + rh // 2 - 7), txt[:14], font=ft,
                   fill=(255, 255, 255) if i == 0 else (34, 34, 34))


def _draw_chart(d, chart, x, y, w, h, font):
    from PIL import ImageFont
    f = _find_jp_font()
    ft = ImageFont.truetype(f, 12)
    try:
        cats = [str(c) for c in chart.plots[0].categories]
        vals = list(chart.series[0].values)
    except Exception:
        d.rectangle([x, y, x + w, y + h], outline=(180, 180, 180))
        return
    d.rectangle([x, y, x + w, y + h], outline=(210, 210, 210))
    if not vals:
        return
    mx = max(v for v in vals if v is not None) or 1
    n = len(vals)
    bw = int(w / (n * 1.6))
    base = y + h - 24
    for i, (c, v) in enumerate(zip(cats, vals)):
        bx = x + 12 + int(i * (w - 24) / n)
        bh = int((v or 0) / mx * (h - 60))
        d.rectangle([bx, base - bh, bx + bw, base], fill=(46, 94, 140))
        d.text((bx, base - bh - 14), str(int(v or 0)), font=ft, fill=(34, 34, 34))
        d.text((bx, base + 4), c[:8], font=ft, fill=(89, 89, 89))


def _make_contact_sheet(out: Path, n: int):
    from PIL import Image
    imgs = [Image.open(out / f"slide-{i:02d}.png") for i in range(1, n + 1)
            if (out / f"slide-{i:02d}.png").exists()]
    if not imgs:
        return
    cols = 2
    tw = max(i.width for i in imgs) // 2
    th = max(i.height for i in imgs) // 2
    rows = (len(imgs) + cols - 1) // cols
    sheet = Image.new("RGB", (tw * cols + 30, th * rows + 30), (255, 255, 255))
    for i, im in enumerate(imgs):
        thumb = im.resize((tw - 10, th - 10))
        r, c = divmod(i, cols)
        sheet.paste(thumb, (10 + c * tw, 10 + r * th))
    sheet.save(str(out / "contact-sheet.png"))


def create_blank_template(path: str) -> None:
    prs = Presentation()
    prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    prs.save(path)


def main() -> int:
    ap = argparse.ArgumentParser(description="求人媒体結果報告PowerPointの生成")
    ap.add_argument("--make-template", help="空テンプレートを生成して終了")
    ap.add_argument("--kpi", help="kpi_results.csv")
    ap.add_argument("--group", help="kpi_by_group.csv")
    ap.add_argument("--summary-input", help="summary_input.json")
    ap.add_argument("--summary", help="summary.md")
    ap.add_argument("--settings", help="会社設定YAML")
    ap.add_argument("--template", help="ベースにする空テンプレートpptx（任意）")
    ap.add_argument("--output", help="出力pptx")
    ap.add_argument("--validate-report", help="検証結果CSVの出力先（任意）")
    ap.add_argument("--export-images", action="store_true", help="スライドを画像へ書き出す")
    ap.add_argument("--log", help="ログファイルパス")
    args = ap.parse_args()

    logger = setup_logger("generate_pptx", args.log)
    try:
        if args.make_template:
            create_blank_template(args.make_template)
            logger.info("空テンプレートを生成しました: %s", args.make_template)
            return 0

        for req in ("kpi", "group", "summary_input", "settings", "output"):
            if not getattr(args, req):
                raise ValueError(f"--{req.replace('_', '-')} は必須です")

        kpi = pd.read_csv(args.kpi, dtype=str, keep_default_na=False)
        group = pd.read_csv(args.group, dtype=str, keep_default_na=False)
        sinput = json.loads(Path(args.summary_input).read_text(encoding="utf-8"))
        sections = parse_summary_sections(args.summary)
        settings = load_settings(args.settings)

        prs = build_presentation(kpi, group, sinput, sections, settings, args.template)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        prs.save(args.output)
        n_slides = len(list(prs.slides))
        logger.info("PowerPointを生成しました: %s（%d枚）", args.output, n_slides)

        findings = validate_pptx(args.output, n_slides, sinput.get("overall", {}).get("metrics", {}))
        n_err = sum(1 for f in findings if f["level"] == "error")
        if args.validate_report:
            pd.DataFrame(findings, columns=["level", "item", "message"]).to_csv(
                args.validate_report, index=False, encoding="utf-8")
        for f in findings:
            (logger.error if f["level"] == "error" else logger.warning)("[%s] %s", f["item"], f["message"])
        logger.info("PowerPoint検証: エラー%d件 / 警告%d件", n_err, len(findings) - n_err)

        if args.export_images:
            export_images(args.output, str(Path(args.output).parent / "slides"), logger)

        return 0 if n_err == 0 else 2
    except Exception as e:
        logger.error("PowerPoint生成に失敗しました: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
