import sys

import pandas as pd
from pptx import Presentation

from conftest import DEMO, run_script


def _base_args(tmp_path):
    return ["--settings", DEMO / "demo-company-settings.yaml",
            "--current", DEMO / "demo-current-month.csv",
            "--previous", DEMO / "demo-previous-month.csv",
            "--targets", DEMO / "demo-targets.csv",
            "--period", "2026-06", "--prev-period", "2026-05",
            "--outdir", tmp_path]


def test_validate_mode_stops_on_total_mismatch(tmp_path):
    """検証モード相当: 合計不一致(E-020)で終了コード2、PPTXなし。"""
    r = run_script("run_report.py", *_base_args(tmp_path))
    assert r.returncode == 2
    assert (tmp_path / "validation_report.csv").exists()
    assert (tmp_path / "kpi_results.csv").exists()
    assert not (tmp_path / "report.pptx").exists()
    report = pd.read_csv(tmp_path / "validation_report.csv")
    assert "E-020" in set(report["code"])


def test_report_mode_completes_with_approval(tmp_path):
    """承認フラグ付きで最後まで完走し、PPTXが生成される。"""
    args = _base_args(tmp_path) + [
        "--summary", DEMO / "generated-summary.md",
        "--allow-total-mismatch", "--make-pptx"]
    r = run_script("run_report.py", *args)
    assert r.returncode == 0, r.stderr
    pptx = tmp_path / "report.pptx"
    assert pptx.exists()
    assert len(Presentation(pptx).slides) == 10
    # 承認により E-020 は警告(W-020C)へ降格
    report = pd.read_csv(tmp_path / "validation_report.csv")
    assert "E-020" not in set(report["code"])
    assert "W-020C" in set(report["code"])


def test_runs_without_previous_and_targets(tmp_path):
    """前月・目標なしでも標準化〜サマリー入力まで動く（新規/未設定扱い）。"""
    r = run_script("run_report.py",
                   "--settings", DEMO / "demo-company-settings.yaml",
                   "--current", DEMO / "demo-current-month.csv",
                   "--period", "2026-06", "--outdir", tmp_path,
                   "--allow-total-mismatch")
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "summary_input.json").exists()


def test_original_demo_files_untouched(tmp_path):
    import hashlib
    before = {f: hashlib.md5((DEMO / f).read_bytes()).hexdigest()
              for f in ("demo-current-month.csv", "demo-previous-month.csv", "demo-targets.csv")}
    run_script("run_report.py", *_base_args(tmp_path), "--allow-total-mismatch")
    after = {f: hashlib.md5((DEMO / f).read_bytes()).hexdigest() for f in before}
    assert before == after, "元のデモ入力ファイルが変更されました"
