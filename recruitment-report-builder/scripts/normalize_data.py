#!/usr/bin/env python3
"""normalize_data.py — 求人媒体データの標準化。

- 列名・媒体名の表記揺れ統一 / 職種等の前後空白削除
- 数値のカンマ・円・％除去 / 空欄と0の区別（空欄は空欄のまま）
- 日付形式の統一（YYYY-MM）/ 不正値の検出（値は保持しフラグ）
- 合計行の判定（row_type列: detail / total）
- 元ファイルは読み取りのみ。標準化結果と正規化レポートを別ファイルへ出力。

使用例:
  python3 scripts/normalize_data.py \
    --input demo/demo-current-month.csv \
    --settings demo/demo-company-settings.yaml \
    --output output/normalized_current.csv \
    --report output/normalize_report_current.csv \
    --period 2026-06
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from common import (KEY_COLUMNS, NUMERIC_COLUMNS, PII_COLUMN_KEYWORDS, TOTAL_ROW_NAMES,
                    clean_text, column_alias_map, load_settings, media_alias_map,
                    parse_number, read_table, setup_logger)

OUTPUT_COLUMNS = ["row_type", "media", "job_category", "location", "period",
                  "impressions", "clicks", "applications", "interviews", "hires", "cost",
                  "target_applications", "target_cpa", "target_hires", "note"]


def normalize_period(value) -> str | None:
    """日付・年月表記を YYYY-MM へ統一。"""
    text = clean_text(value)
    if text is None:
        return None
    m = re.search(r"(\d{4})[年/\-\.](\d{1,2})", text)
    return f"{m.group(1)}-{int(m.group(2)):02d}" if m else text


def normalize(df: pd.DataFrame, settings: dict | None, period: str | None,
              logger) -> tuple[pd.DataFrame, list[dict]]:
    report: list[dict] = []

    # 個人情報らしき列の検出（検出時は停止）
    pii = [c for c in df.columns for kw in PII_COLUMN_KEYWORDS if kw.lower() in str(c).lower()]
    if pii:
        raise ValueError(f"個人情報の可能性がある列が含まれています: {pii}。"
                         "該当列を削除したファイルで再実行してください。")

    # 列名の統一
    aliases = column_alias_map(settings)
    rename = {}
    for col in df.columns:
        key = clean_text(col)
        if key in aliases:
            rename[col] = aliases[key]
            if key != aliases[key]:
                report.append({"code": "W-020", "row": "", "target": col,
                               "message": f"列名「{col}」を内部項目「{aliases[key]}」へ統一しました"})
        else:
            report.append({"code": "W-021", "row": "", "target": col,
                           "message": f"列名「{col}」は標準項目に対応付けできません（そのまま保持します）"})
    df = df.rename(columns=rename)

    media_aliases = media_alias_map(settings)
    rows = []
    for i, src in df.iterrows():
        row = {c: None for c in OUTPUT_COLUMNS}
        rowno = i + 2  # ヘッダー行を1行目とした実ファイル上の行番号

        raw_media = clean_text(src.get("media"))
        media = media_aliases.get(raw_media, raw_media) if raw_media else None
        if raw_media and media != raw_media:
            report.append({"code": "W-004", "row": rowno, "target": raw_media,
                           "message": f"媒体名「{raw_media}」を「{media}」へ統一しました"})
        row["media"] = media

        for col in ("job_category", "location", "note"):
            cleaned = clean_text(src.get(col))
            if col != "note" and src.get(col) is not None and cleaned != (None if pd.isna(src.get(col)) else str(src.get(col))):
                if cleaned is not None and str(src.get(col)) != cleaned:
                    report.append({"code": "W-014", "row": rowno, "target": str(src.get(col)),
                                   "message": f"「{src.get(col)}」の前後空白を除去しました"})
            row[col] = cleaned

        row["period"] = normalize_period(src.get("period")) or period

        for col in NUMERIC_COLUMNS:
            if col not in df.columns:
                continue
            raw = src.get(col)
            value = parse_number(raw)
            if isinstance(value, str):
                report.append({"code": "W-022", "row": rowno, "target": f"{col}={raw}",
                               "message": f"{rowno}行目の「{col}」に数値として解釈できない値があります: {raw}"})
            elif raw is not None and not pd.isna(raw) and value is not None \
                    and re.search(r"[,円¥％%　 ]", str(raw)):
                report.append({"code": "W-005", "row": rowno, "target": str(raw),
                               "message": f"数値表記「{raw}」を {value} へ統一しました"})
            row[col] = value

        row["row_type"] = "total" if (media in TOTAL_ROW_NAMES or
                                      (media is None and row["applications"] is not None)) else "detail"
        rows.append(row)

    out = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    logger.info("標準化完了: %d行（明細%d行・合計行%d行）", len(out),
                (out["row_type"] == "detail").sum(), (out["row_type"] == "total").sum())
    return out, report


def main() -> int:
    ap = argparse.ArgumentParser(description="求人媒体データの標準化")
    ap.add_argument("--input", required=True, help="入力ファイル（CSVまたはExcel）")
    ap.add_argument("--settings", help="会社設定YAML（媒体・列名エイリアス）")
    ap.add_argument("--output", required=True, help="標準化データの出力先CSV")
    ap.add_argument("--report", help="正規化レポートの出力先CSV")
    ap.add_argument("--period", help="対象期間（YYYY-MM）。データに期間列がない場合に使用")
    ap.add_argument("--sheet", default=0, help="Excelのシート名または番号（既定: 先頭）")
    ap.add_argument("--log", help="ログファイルパス")
    args = ap.parse_args()

    logger = setup_logger("normalize", args.log)
    try:
        if Path(args.input).resolve() == Path(args.output).resolve():
            raise ValueError("出力先が入力ファイルと同じです。元ファイルは上書きできません。")
        settings = load_settings(args.settings) if args.settings else None
        df = read_table(args.input, args.sheet)
        out, report = normalize(df, settings, args.period, logger)

        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(args.output, index=False, encoding="utf-8")
        logger.info("標準化データを出力しました: %s", args.output)
        if args.report:
            pd.DataFrame(report, columns=["code", "row", "target", "message"]) \
                .to_csv(args.report, index=False, encoding="utf-8")
            logger.info("正規化レポートを出力しました: %s（%d件）", args.report, len(report))
        return 0
    except Exception as e:
        logger.error("標準化に失敗しました: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
