#!/usr/bin/env python3
"""validate_data.py — 標準化済みデータの検証。エラーと警告を区分して出力する。

エラー（E-xxx）: 検出時はレポート作成を停止すべき問題（終了コード2）
警告（W-xxx）: 続行可能だがレポートへ明記すべき問題

検出項目:
  E-001 必須列不足 / E-002 数値以外の値 / E-003 マイナス値
  E-010 応募数より面接数が多い / E-011 面接数より採用数が多い / E-020 合計値の不一致
  W-001 前月データ不足 / W-002 目標値不足 / W-003 空欄セル / W-006 重複行
  W-007 未登録媒体 / W-010 応募単価の閾値超過 / W-011 前月比の大幅変動
  W-012 応募0件 / W-013 広告費0円で応募あり

使用例:
  python3 scripts/validate_data.py \
    --current output/normalized_current.csv \
    --previous output/normalized_previous.csv \
    --targets output/normalized_targets.csv \
    --settings demo/demo-company-settings.yaml \
    --kpi output/kpi_results.csv \
    --normalize-report output/normalize_report_current.csv \
    --output output/validation_report.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from common import (KEY_COLUMNS, NA, NEW, NOT_SET, REQUIRED_COLUMNS,
                    load_settings, registered_media, setup_logger)

COUNT_COLS = ["impressions", "clicks", "applications", "interviews", "hires", "cost"]
OPTIONAL_BLANK_OK = {"note", "location", "period", "target_applications", "target_cpa",
                     "target_hires", "row_type"}


def _num(value):
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return value  # 数値以外（文字列のまま）


def _label(row) -> str:
    parts = [str(row.get(c)) for c in KEY_COLUMNS if not pd.isna(row.get(c))]
    return " / ".join(parts)


class Findings:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, level: str, code: str, row, target: str, message: str, action: str):
        self.items.append({"level": level, "code": code, "row": row,
                           "target": target, "message": message, "action": action})

    def error(self, *args):
        self.add("error", *args)

    def warning(self, *args):
        self.add("warning", *args)


def validate(current: pd.DataFrame, previous: pd.DataFrame | None,
             targets: pd.DataFrame | None, settings: dict | None,
             kpi: pd.DataFrame | None, findings: Findings) -> None:
    th = (settings or {}).get("thresholds", {}) or {}
    cpa_warn = th.get("cpa_warning_yen", 50000)
    mom_warn = th.get("mom_change_warning_pct", 50)

    # E-001 必須列不足
    missing = [c for c in REQUIRED_COLUMNS if c not in current.columns]
    if missing:
        findings.error("E-001", "", ",".join(missing),
                       f"必須列が不足しています: {missing}",
                       "入力ファイルの列名を確認し、媒体・職種・応募数・広告費の列を含めてください")
        return  # 以降の行検証は不可能

    detail = current[current["row_type"] == "detail"]
    seen_keys: dict[tuple, int] = {}
    for i, row in detail.iterrows():
        rowno, label = i + 2, _label(row)
        vals = {c: _num(row.get(c)) for c in COUNT_COLS if c in current.columns}

        for col, v in vals.items():
            if isinstance(v, str):
                findings.error("E-002", rowno, f"{label}: {col}",
                               f"「{col}」に数値以外の値があります: {v}",
                               "元データの該当セルを数値に修正してください")
            elif v is not None and v < 0:
                findings.error("E-003", rowno, f"{label}: {col}",
                               f"「{col}」がマイナス値です: {v}",
                               "元データの該当セルを確認してください")
            elif v is None and col in ("applications", "cost"):
                findings.error("E-002", rowno, f"{label}: {col}",
                               f"必須項目「{col}」が空欄です",
                               "応募数・広告費は必須です。値を入力してください")
            elif v is None:
                findings.warning("W-003", rowno, f"{label}: {col}",
                                 f"「{col}」が空欄です（0ではなく欠損として扱います）",
                                 "取得可能であれば値を補ってください。関連KPIは算出不可となります")

        nums = {k: (v if isinstance(v, (int, float)) else None) for k, v in vals.items()}
        if nums.get("applications") is not None and nums.get("interviews") is not None \
                and nums["interviews"] > nums["applications"]:
            findings.error("E-010", rowno, label,
                           f"応募数({nums['applications']:.0f})より面接数({nums['interviews']:.0f})が多くなっています",
                           "元データの値を確認してください")
        if nums.get("interviews") is not None and nums.get("hires") is not None \
                and nums["hires"] > nums["interviews"]:
            findings.error("E-011", rowno, label,
                           f"面接数({nums['interviews']:.0f})より採用数({nums['hires']:.0f})が多くなっています",
                           "元データの値を確認してください")

        # W-006 重複行
        key = tuple(row.get(c) for c in KEY_COLUMNS)
        if key in seen_keys:
            findings.warning("W-006", rowno, label,
                             f"{seen_keys[key]}行目と同じ媒体・職種・拠点の行が重複しています",
                             "同一求人の行が複数ないか確認してください")
        seen_keys[key] = rowno

        # W-007 未登録媒体
        reg = registered_media(settings)
        if reg and row.get("media") not in reg and not pd.isna(row.get("media")):
            findings.warning("W-007", rowno, str(row.get("media")),
                             f"媒体「{row.get('media')}」は登録媒体一覧にありません",
                             "会社設定の媒体一覧またはエイリアスへ追加してください")

        # W-012 応募0件 / W-013 広告費0円で応募あり
        if nums.get("applications") == 0:
            findings.warning("W-012", rowno, label,
                             "応募が0件です。応募単価などは算出不可となります",
                             "掲載内容・予算配分の見直しを検討してください")
        if nums.get("cost") == 0 and (nums.get("applications") or 0) > 0:
            findings.warning("W-013", rowno, label,
                             f"広告費0円で応募{nums['applications']:.0f}件があります（費用0円・要確認）",
                             "無料掲載・オーガニック応募かを確認してください。費用対効果の評価から除外します")

        # W-001 前月データ不足 / W-002 目標値不足
        if previous is not None:
            prev_keys = {tuple(r.get(c) for c in KEY_COLUMNS)
                         for _, r in previous[previous["row_type"] == "detail"].iterrows()}
            if key not in prev_keys:
                findings.warning("W-001", rowno, label,
                                 "前月データがありません（新規掲載）。前月比は「新規」と表示します",
                                 "新規掲載でない場合は前月データの提供をご確認ください")
        if targets is not None:
            tgt_keys = {tuple(r.get(c) for c in KEY_COLUMNS) for _, r in targets.iterrows()}
            if key not in tgt_keys:
                findings.warning("W-002", rowno, label,
                                 "目標値が設定されていません。目標比は「未設定」と表示します",
                                 "必要であれば目標値ファイルへ追加してください")

    # E-020 合計値の不一致
    totals = current[current["row_type"] == "total"]
    for _, trow in totals.iterrows():
        for col in COUNT_COLS:
            if col not in current.columns:
                continue
            tv = _num(trow.get(col))
            if tv is None or isinstance(tv, str):
                continue
            dv = pd.to_numeric(detail[col], errors="coerce").dropna().sum()
            if abs(tv - dv) > 0.5:
                findings.error("E-020", "", col,
                               f"合計行の「{col}」({tv:.0f})が明細の合計({dv:.0f})と一致しません（差{tv - dv:+.0f}）",
                               "媒体管理画面の値と明細を照合してください。合計行を除外して続行する場合は承認が必要です")

    # W-010 / W-011（KPI結果がある場合）
    if kpi is not None:
        for _, r in kpi.iterrows():
            if r["媒体"] == "全体":
                continue
            label = f"{r['媒体']} / {r['職種']} / {r['拠点']}"
            cpa = pd.to_numeric(pd.Series([r["応募単価"]]), errors="coerce").iloc[0]
            if pd.notna(cpa) and cpa > cpa_warn:
                findings.warning("W-010", "", label,
                                 f"応募単価{cpa:.0f}円が警告閾値（{cpa_warn:,}円）を超えています",
                                 "掲載内容・予算配分を確認してください")
            for col, name in (("応募数前月比", "応募数"), ("応募単価前月比", "応募単価")):
                v = pd.to_numeric(pd.Series([r[col]]), errors="coerce").iloc[0]
                if pd.notna(v) and abs(v) > mom_warn:
                    findings.warning("W-011", "", label,
                                     f"{name}の前月比が{v:+.1f}%と大きく変動しています（閾値±{mom_warn}%）",
                                     "実績値が正しいか、掲載状況に変化がなかったかを確認してください")


def main() -> int:
    ap = argparse.ArgumentParser(description="標準化済みデータの検証")
    ap.add_argument("--current", required=True, help="標準化済みの当月データCSV")
    ap.add_argument("--previous", help="標準化済みの前月データCSV（任意）")
    ap.add_argument("--targets", help="標準化済みの目標値CSV（任意）")
    ap.add_argument("--settings", help="会社設定YAML（閾値・登録媒体）")
    ap.add_argument("--kpi", help="KPI結果CSV（異常値検証に使用・任意）")
    ap.add_argument("--normalize-report", help="normalize_data.pyの正規化レポート（統合する・任意）")
    ap.add_argument("--output", required=True, help="検証レポートの出力先CSV")
    ap.add_argument("--log", help="ログファイルパス")
    args = ap.parse_args()

    logger = setup_logger("validate", args.log)
    try:
        current = pd.read_csv(args.current)
        previous = pd.read_csv(args.previous) if args.previous else None
        targets = pd.read_csv(args.targets) if args.targets else None
        settings = load_settings(args.settings) if args.settings else None
        kpi = pd.read_csv(args.kpi, dtype=str, keep_default_na=False) if args.kpi else None

        findings = Findings()
        if args.normalize_report and Path(args.normalize_report).exists():
            for _, r in pd.read_csv(args.normalize_report).iterrows():
                findings.warning(str(r["code"]), r.get("row", ""), str(r.get("target", "")),
                                 str(r["message"]), "内容を確認してください（自動正規化済み）")
        validate(current, previous, targets, settings, kpi, findings)

        report = pd.DataFrame(findings.items,
                              columns=["level", "code", "row", "target", "message", "action"])
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        report.to_csv(args.output, index=False, encoding="utf-8")

        n_err = (report["level"] == "error").sum()
        n_warn = (report["level"] == "warning").sum()
        logger.info("検証完了: エラー%d件 / 警告%d件 → %s", n_err, n_warn, args.output)
        if n_err:
            logger.error("エラーが%d件あります。エラーを解消するまで確定資料は作成できません。", n_err)
            return 2
        return 0
    except Exception as e:
        logger.error("検証に失敗しました: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
