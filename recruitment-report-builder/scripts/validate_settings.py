#!/usr/bin/env python3
"""validate_settings.py — 会社設定YAMLの形式・矛盾を検証する（保存前チェック）。

YAMLが壊れていないか、設定同士に矛盾がないかを日本語で報告する。
エラー（保存すべきでない）と警告（保存可能だが確認推奨）を区別する。

使用例:
  python3 scripts/validate_settings.py --settings settings/会社/company-settings.yaml
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import load_settings, setup_logger

# KPI → 計算に必要な実数項目
KPI_DEPS = {
    "ctr": ["clicks", "impressions"], "application_rate": ["applications", "clicks"],
    "interview_rate": ["interviews", "applications"], "hire_rate": ["hires", "applications"],
    "cpc": ["cost", "clicks"], "cpa": ["cost", "applications"], "cph": ["cost", "hires"],
}
JP = {"impressions": "表示数", "clicks": "クリック数", "applications": "応募数",
      "interviews": "面接数", "hires": "採用数", "cost": "広告費", "cpa": "応募単価",
      "cph": "採用単価", "cpc": "クリック単価"}


def check(settings: dict) -> list[tuple[str, str]]:
    """(level, message) のリストを返す。level は error / warning。"""
    issues: list[tuple[str, str]] = []
    company = settings.get("company", {}) or {}
    media = settings.get("media", {}) or {}
    kpi = settings.get("kpi", {}) or {}
    report = settings.get("report", {}) or {}

    required = set(kpi.get("required", []) or [])
    optional = set(kpi.get("optional", []) or [])
    all_kpi = required | optional

    # 媒体登録
    if not (media.get("registered") or []):
        issues.append(("error", "媒体が1つも登録されていません（media.registered が空）。"
                       "使用媒体を追加してください。"))

    # KPIの依存関係（必須KPIの計算に必要な実数を取得しているか）
    available = all_kpi | {"applications", "cost"}  # 必須の実数は常に取得前提
    for k in required:
        for dep in KPI_DEPS.get(k, []):
            if dep not in available:
                issues.append(("error", f"必須KPI「{JP.get(k, k)}」の計算には"
                               f"「{JP.get(dep, dep)}」が必要ですが、取得項目にありません。"
                               f"kpi.optional に {dep} を追加するか、必須から外してください。"))

    # 期間形式
    for key in ("current_period", "previous_period"):
        v = company.get(key)
        if v and not re.fullmatch(r"\d{4}-\d{2}", str(v)):
            issues.append(("error", f"{key} は YYYY-MM 形式にしてください（現在: {v}）。"))

    # ブランドカラー
    color = report.get("brand_color")
    if color and not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(color)):
        issues.append(("error", f"brand_color は #RRGGBB 形式にしてください（現在: {color}）。"))

    # サマリー長
    if report.get("summary_length") and report["summary_length"] not in ("short", "standard", "long"):
        issues.append(("warning", "summary_length は short / standard / long のいずれかにしてください。"))

    # スライドキー
    valid_slides = {"cover", "executive_summary", "main_kpi", "by_media", "by_job",
                    "by_location", "best_worst", "issues", "actions", "open_items"}
    for s in report.get("slides", []) or []:
        if s not in valid_slides:
            issues.append(("warning", f"未知のスライドキー「{s}」があります。無視されます。"))

    # 会社名の空
    if not company.get("name"):
        issues.append(("warning", "会社名（company.name）が未入力です。"))

    # 目標重視だが目標が全く無い場合の注意喚起はデータ側で判定（ここでは設定のみ）
    return issues


def main() -> int:
    ap = argparse.ArgumentParser(description="会社設定YAMLの検証")
    ap.add_argument("--settings", required=True, help="会社設定YAML")
    ap.add_argument("--log", help="ログファイルパス")
    args = ap.parse_args()

    logger = setup_logger("validate_settings", args.log)
    try:
        settings = load_settings(args.settings)  # 壊れていればここで例外
    except Exception as e:
        logger.error("設定ファイルを読み込めません: %s", e)
        return 1

    issues = check(settings)
    n_err = sum(1 for lv, _ in issues if lv == "error")
    for lv, msg in issues:
        (logger.error if lv == "error" else logger.warning)(msg)
    if not issues:
        logger.info("設定に矛盾は見つかりませんでした。")
    logger.info("設定検証: エラー%d件 / 警告%d件", n_err, len(issues) - n_err)
    return 2 if n_err else 0


if __name__ == "__main__":
    sys.exit(main())
