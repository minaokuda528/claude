#!/usr/bin/env python3
"""generate_summary_input.py — KPI結果を、生成AIが誤解しにくい構造化JSONへ変換する。

- 数値はすべて calculate_kpi.py の出力CSVから転記（再計算しない。単位を明示）
- 好調/注意/改善優先の判定はここで行い、Claudeは判定をやり直さない
- 検証レポートの警告・エラーを添付し、判断材料の欠落を防ぐ

使用例:
  python3 scripts/generate_summary_input.py \
    --kpi output/2026-06/kpi_results.csv \
    --validation output/2026-06/validation_report.csv \
    --settings demo/demo-company-settings.yaml \
    --output output/2026-06/summary_input.json \
    --comments "6月はIndeedでクリック強化キャンペーンを実施"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from common import NA, NEW, NOT_SET, load_settings, setup_logger

SPECIAL = {NA, NEW, NOT_SET, ""}


def _val(x):
    """CSVの値をJSON用に変換。特殊値は文字列のまま、数値は数値型で。"""
    if x in SPECIAL:
        return x if x else None
    try:
        f = float(x)
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        return x


def _num(x):
    v = _val(x)
    return v if isinstance(v, (int, float)) else None


def build(kpi: pd.DataFrame, validation: pd.DataFrame | None,
          settings: dict, comments: str | None) -> dict:
    th = settings.get("thresholds", {}) or {}
    good_tgt = th.get("good_target_ratio_pct", 100)
    good_mom = th.get("good_mom_increase_pct", 20)
    caution_cpa = th.get("caution_cpa_target_ratio_pct", 120)
    caution_mom = th.get("caution_mom_decrease_pct", -20)
    cpa_warn = th.get("cpa_warning_yen", 50000)

    rows, judgements = [], {"good": [], "caution": [], "priority": []}
    overall = None
    for _, r in kpi.iterrows():
        label = f"{r['媒体']} {r['職種']} {r['拠点']}".replace(" -", "").strip()
        entry = {
            "media": r["媒体"], "job": r["職種"], "location": r["拠点"], "label": label,
            "metrics": {
                "impressions": _val(r["表示数"]), "clicks": _val(r["クリック数"]),
                "applications": _val(r["応募数"]), "interviews": _val(r["面接数"]),
                "hires": _val(r["採用数"]), "cost_yen": _val(r["広告費"]),
                "ctr_pct": _val(r["クリック率"]), "application_rate_pct": _val(r["応募率"]),
                "interview_rate_pct": _val(r["面接設定率"]), "hire_rate_pct": _val(r["採用率"]),
                "cpc_yen": _val(r["クリック単価"]), "cpa_yen": _val(r["応募単価"]),
                "cph_yen": _val(r["採用単価"]),
            },
            "comparison": {
                "applications_mom_pct": _val(r["応募数前月比"]),
                "cpa_mom_pct": _val(r["応募単価前月比"]),
                "applications_vs_target_pct": _val(r["応募数目標比"]),
                "cpa_vs_target_pct": _val(r["応募単価目標比"]),
            },
            "flags": [],
        }
        m, c = entry["metrics"], entry["comparison"]
        if r["媒体"] == "全体":
            overall = entry
            continue

        apps, cost = _num(r["応募数"]), _num(r["広告費"])
        cpa, app_mom = _num(r["応募単価"]), _num(r["応募数前月比"])
        app_tgt, cpa_tgt = _num(r["応募数目標比"]), _num(r["応募単価目標比"])

        if c["applications_mom_pct"] == NEW:
            entry["flags"].append("new_listing")
        if NOT_SET in (c["applications_vs_target_pct"], c["cpa_vs_target_pct"]):
            entry["flags"].append("target_not_set")
        if apps == 0 and (cost or 0) > 0:
            entry["flags"].append("zero_applications_with_cost")
        if cost == 0 and (apps or 0) > 0:
            entry["flags"].append("cost_zero_with_applications")
        if apps is not None and 0 < apps < 5:
            entry["flags"].append("small_sample")
        if cpa is not None and cpa > cpa_warn and "cost_zero_with_applications" not in entry["flags"]:
            entry["flags"].append("cpa_over_warning_threshold")

        good_reasons, caution_reasons = [], []
        if app_tgt is not None and app_tgt >= good_tgt:
            good_reasons.append(f"応募数目標比{app_tgt}%")
        if app_mom is not None and app_mom >= good_mom:
            good_reasons.append(f"応募数前月比+{app_mom}%")
        if cpa_tgt is not None and cpa_tgt >= caution_cpa and \
                "cost_zero_with_applications" not in entry["flags"]:
            caution_reasons.append(f"応募単価目標比{cpa_tgt}%（目標超過）")
        if app_mom is not None and app_mom <= caution_mom:
            caution_reasons.append(f"応募数前月比{app_mom}%")

        if good_reasons:
            entry["flags"].append("good")
            judgements["good"].append({"label": label, "reasons": good_reasons})
        if caution_reasons or "zero_applications_with_cost" in entry["flags"] \
                or "cpa_over_warning_threshold" in entry["flags"]:
            entry["flags"].append("caution")
            judgements["caution"].append({"label": label, "reasons": caution_reasons or
                                          [f for f in entry["flags"] if f != "caution"]})
        rows.append(entry)

    # 改善優先度（analysis-rules.md §3 の順）
    rank = 1
    def add_priority(label, reason, level):
        nonlocal rank
        judgements["priority"].append({"rank": rank, "level": level, "label": label, "reason": reason})
        rank += 1
    for e in rows:
        if "zero_applications_with_cost" in e["flags"]:
            add_priority(e["label"],
                         f"応募0件で広告費{e['metrics']['cost_yen']:,}円が発生", "高")
    for e in rows:
        if "cpa_over_warning_threshold" in e["flags"]:
            add_priority(e["label"],
                         f"応募単価{e['metrics']['cpa_yen']:,}円が警告閾値{cpa_warn:,}円を超過", "高")
    for e in rows:
        if "caution" in e["flags"] and "zero_applications_with_cost" not in e["flags"] \
                and "cpa_over_warning_threshold" not in e["flags"]:
            reasons = next((j["reasons"] for j in judgements["caution"]
                            if j["label"] == e["label"]), [])
            add_priority(e["label"], " / ".join(map(str, reasons)), "中")

    issues = []
    if validation is not None:
        for _, v in validation.iterrows():
            issues.append({"level": v["level"], "code": v["code"],
                           "target": str(v.get("target", "")), "message": v["message"]})

    return {
        "meta": {
            "description": "求人媒体月次サマリー作成用の構造化データ。数値の単位はキー名に明示。"
                           "特殊値: N/A=算出不可, NEW=前月データなし, NOT_SET=目標未設定。",
            "company": (settings.get("company", {}) or {}).get("name"),
            "period": (settings.get("company", {}) or {}).get("current_period"),
            "previous_period": (settings.get("company", {}) or {}).get("previous_period"),
            "source": "calculate_kpi.py の出力CSV（数値の再計算をしないこと）",
        },
        "thresholds": {"good_target_ratio_pct": good_tgt, "good_mom_increase_pct": good_mom,
                       "caution_cpa_target_ratio_pct": caution_cpa,
                       "caution_mom_decrease_pct": caution_mom, "cpa_warning_yen": cpa_warn},
        "overall": overall,
        "rows": rows,
        "judgements": judgements,
        "data_issues": issues,
        "user_comments": comments or None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="サマリー作成用の構造化JSONを生成")
    ap.add_argument("--kpi", required=True, help="calculate_kpi.py の出力CSV")
    ap.add_argument("--validation", help="validate_data.py の検証レポートCSV（任意）")
    ap.add_argument("--settings", required=True, help="会社設定YAML")
    ap.add_argument("--output", required=True, help="出力JSONパス")
    ap.add_argument("--comments", help="利用者の補足コメント（任意）")
    ap.add_argument("--log", help="ログファイルパス")
    args = ap.parse_args()

    logger = setup_logger("summary_input", args.log)
    try:
        kpi = pd.read_csv(args.kpi, dtype=str, keep_default_na=False)
        validation = pd.read_csv(args.validation) if args.validation else None
        settings = load_settings(args.settings)
        data = build(kpi, validation, settings, args.comments)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("サマリー入力JSONを出力しました: %s（明細%d行・優先項目%d件・警告等%d件）",
                    args.output, len(data["rows"]), len(data["judgements"]["priority"]),
                    len(data["data_issues"]))
        return 0
    except Exception as e:
        logger.error("サマリー入力の生成に失敗しました: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
