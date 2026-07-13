#!/usr/bin/env python3
"""run_report.py — レポート作成パイプラインを順に実行するオーケストレーター。

標準化 → 検証 →（エラーなら停止）→ KPI計算（明細+集計）→ サマリー入力JSON。
--make-pptx を付けるとPowerPointも生成する（サマリーMDが必要）。

数値処理はすべて各スクリプトが行い、このスクリプトは順序制御と停止判定のみを担う。
検証でエラーがある場合は KPI計算以降へ進まず、終了コード2で停止する。

使用例（検証まで＝検証モード相当）:
  python3 scripts/run_report.py \
    --settings demo/demo-company-settings.yaml \
    --current demo/demo-current-month.csv \
    --previous demo/demo-previous-month.csv \
    --targets demo/demo-targets.csv \
    --period 2026-06 --prev-period 2026-05 \
    --outdir output/2026-06

  # PowerPointまで（サマリーMDを用意してから）:
  python3 scripts/run_report.py ... --summary demo/generated-summary.md --make-pptx
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from common import setup_logger


def run(logger, name, *args) -> int:
    cmd = [sys.executable, str(HERE / name), *map(str, args)]
    logger.info("実行: %s", name)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.stderr.strip():
        for line in proc.stderr.strip().splitlines():
            print(line, file=sys.stderr)
    return proc.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description="レポート作成パイプラインの一括実行")
    ap.add_argument("--settings", required=True)
    ap.add_argument("--current", required=True)
    ap.add_argument("--previous")
    ap.add_argument("--targets")
    ap.add_argument("--period", help="当月 YYYY-MM")
    ap.add_argument("--prev-period", help="前月 YYYY-MM")
    ap.add_argument("--outdir", required=True, help="出力ディレクトリ")
    ap.add_argument("--comments", help="サマリー用の補足コメント")
    ap.add_argument("--summary", help="サマリーMD（--make-pptx時に必要）")
    ap.add_argument("--make-pptx", action="store_true", help="PowerPointも生成する")
    ap.add_argument("--template", help="空PPTXテンプレート（任意）")
    ap.add_argument("--allow-total-mismatch", action="store_true",
                    help="合計不一致を承認済みとして明細合計で続行する（人の承認が前提）")
    args = ap.parse_args()

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    log = str(out / "run.log")
    logger = setup_logger("run_report", log)

    P = {k: str(out / v) for k, v in {
        "cur": "normalized_current.csv", "prev": "normalized_previous.csv",
        "tgt": "normalized_targets.csv", "norm_report": "normalize_report.csv",
        "kpi": "kpi_results.csv", "group": "kpi_by_group.csv",
        "validation": "validation_report.csv", "sinput": "summary_input.json",
        "pptx_validation": "pptx_validation.csv",
    }.items()}

    # 1. 標準化
    rc = run(logger, "normalize_data.py", "--input", args.current, "--settings", args.settings,
             "--output", P["cur"], "--report", P["norm_report"],
             *(["--period", args.period] if args.period else []), "--log", log)
    if rc:
        logger.error("当月データの標準化に失敗しました。処理を停止します。")
        return 1
    if args.previous:
        run(logger, "normalize_data.py", "--input", args.previous, "--settings", args.settings,
            "--output", P["prev"], *(["--period", args.prev_period] if args.prev_period else []),
            "--log", log)
    if args.targets:
        run(logger, "normalize_data.py", "--input", args.targets, "--settings", args.settings,
            "--output", P["tgt"], "--log", log)

    # 2. KPI計算（検証で異常値を見るため先に計算）
    rc = run(logger, "calculate_kpi.py", "--current", P["cur"],
             *(["--previous", P["prev"]] if args.previous else []),
             *(["--targets", P["tgt"]] if args.targets else []),
             "--output", P["kpi"], "--group-output", P["group"], "--log", log)
    if rc:
        logger.error("KPI計算に失敗しました。処理を停止します。")
        return 1

    # 3. 検証（エラーがあれば停止）
    rc = run(logger, "validate_data.py", "--current", P["cur"],
             *(["--previous", P["prev"]] if args.previous else []),
             *(["--targets", P["tgt"]] if args.targets else []),
             "--settings", args.settings, "--kpi", P["kpi"],
             "--normalize-report", P["norm_report"], "--output", P["validation"],
             *(["--allow-total-mismatch"] if args.allow_total_mismatch else []), "--log", log)
    if rc == 2:
        logger.error("データ検証でエラーが検出されました。%s を確認し、"
                     "修正または合計行除外などの対応後に再実行してください。"
                     "（確定資料は作成しません）", P["validation"])
        return 2
    if rc == 1:
        logger.error("検証処理に失敗しました。")
        return 1

    # 4. サマリー入力JSON
    rc = run(logger, "generate_summary_input.py", "--kpi", P["kpi"],
             "--validation", P["validation"], "--settings", args.settings,
             "--output", P["sinput"], *(["--comments", args.comments] if args.comments else []),
             "--log", log)
    if rc:
        logger.error("サマリー入力の生成に失敗しました。")
        return 1

    logger.info("検証・KPI・サマリー入力まで完了しました。")
    logger.info("→ サマリー(%s)はClaudeが analysis-rules.md / writing-rules.md に従って作成します。", P["sinput"])

    # 5. PowerPoint（任意。サマリーMD確認後）
    if args.make_pptx:
        if not args.summary:
            logger.error("--make-pptx には --summary（サマリーMD）が必要です。"
                         "サマリーを人が確認・承認してから指定してください。")
            return 1
        rc = run(logger, "generate_pptx.py", "--kpi", P["kpi"], "--group", P["group"],
                 "--summary-input", P["sinput"], "--summary", args.summary,
                 "--settings", args.settings, "--output", str(out / "report.pptx"),
                 "--validate-report", P["pptx_validation"],
                 *(["--template", args.template] if args.template else []), "--log", log)
        if rc == 2:
            logger.error("PowerPoint検証でエラーがあります。%s を確認してください。", P["pptx_validation"])
            return 2
        if rc:
            logger.error("PowerPoint生成に失敗しました。")
            return 1
        logger.info("PowerPointを生成しました: %s", out / "report.pptx")

    return 0


if __name__ == "__main__":
    sys.exit(main())
