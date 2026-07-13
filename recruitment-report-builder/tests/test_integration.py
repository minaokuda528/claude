"""フェーズ8 統合テスト: 指示書の10シナリオを網羅する。"""
import sys
from pathlib import Path

import pandas as pd
from pptx import Presentation

from conftest import DEMO, ROOT, run_script

CB = ROOT / "tests" / "fixtures" / "company_b"


def _kpi_index(path):
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    return {(r["媒体"], r["職種"], r["拠点"]): r for _, r in df.iterrows()}


def _norm(tmp, src, out, settings, period=None):
    args = ["--input", src, "--settings", settings, "--output", out]
    if period:
        args += ["--period", period]
    r = run_script("normalize_data.py", *args)
    assert r.returncode == 0, r.stderr
    return out


# --- シナリオ1: 正常データ（当月・前月・目標すべてあり） ---
def test_s1_normal_data_company_b(tmp_path):
    r = run_script("run_report.py",
                   "--settings", CB / "settings.yaml", "--current", CB / "current.csv",
                   "--previous", CB / "previous.csv", "--targets", CB / "targets.csv",
                   "--period", "2026-06", "--prev-period", "2026-05", "--outdir", tmp_path)
    assert r.returncode == 0, r.stderr
    idx = _kpi_index(tmp_path / "kpi_results.csv")
    row = idx[("マイナビバイト", "倉庫スタッフ", "横浜")]
    assert row["応募単価"] == "5000"          # 90000/18
    assert row["応募数前月比"] == "28.6"       # (18-14)/14
    assert row["応募数目標比"] == "120.0"      # 18/15


# --- シナリオ2: 前月データなし → 新規(NEW) ---
def test_s2_no_previous(tmp_path):
    out = tmp_path / "kpi.csv"
    cur = _norm(tmp_path, DEMO / "demo-current-month.csv", tmp_path / "c.csv",
                DEMO / "demo-company-settings.yaml", "2026-06")
    r = run_script("calculate_kpi.py", "--current", cur, "--output", out)
    assert r.returncode == 0
    idx = _kpi_index(out)
    assert all(v["応募数前月比"] == "NEW" for k, v in idx.items() if v["媒体"] != "全体")


# --- シナリオ3: 目標値なし → 未設定(NOT_SET) ---
def test_s3_no_targets(tmp_path):
    cur = _norm(tmp_path, DEMO / "demo-current-month.csv", tmp_path / "c.csv",
                DEMO / "demo-company-settings.yaml", "2026-06")
    out = tmp_path / "kpi.csv"
    run_script("calculate_kpi.py", "--current", cur, "--output", out)
    idx = _kpi_index(out)
    assert all(v["応募数目標比"] == "NOT_SET" for k, v in idx.items() if v["媒体"] != "全体")


# --- シナリオ4: 応募0件 → 応募単価は算出不可 ---
def test_s4_zero_applications(tmp_path):
    cur = _norm(tmp_path, DEMO / "demo-current-month.csv", tmp_path / "c.csv",
                DEMO / "demo-company-settings.yaml", "2026-06")
    out = tmp_path / "kpi.csv"
    run_script("calculate_kpi.py", "--current", cur, "--output", out)
    row = _kpi_index(out)[("求人ボックス", "一般事務", "東京")]
    assert row["応募数"] == "0"
    assert row["応募単価"] == "N/A"


# --- シナリオ5: 採用0件 → 採用単価は算出不可 ---
def test_s5_zero_hires(tmp_path):
    r = run_script("run_report.py",
                   "--settings", CB / "settings.yaml", "--current", CB / "current.csv",
                   "--targets", CB / "targets.csv", "--period", "2026-06", "--outdir", tmp_path)
    assert r.returncode == 0, r.stderr
    row = _kpi_index(tmp_path / "kpi_results.csv")[("タウンワーク", "ドライバー", "川崎")]
    assert row["採用数"] == "0"
    assert row["採用単価"] == "N/A"


# --- シナリオ6: 必須列不足 → 停止 ---
def test_s6_missing_required_column_stops(tmp_path):
    bad = tmp_path / "bad.csv"
    pd.DataFrame([{"媒体": "Indeed", "職種": "営業", "広告費": 1000}]).to_csv(bad, index=False)
    norm = tmp_path / "n.csv"
    run_script("normalize_data.py", "--input", bad, "--output", norm, "--period", "2026-06")
    out = tmp_path / "v.csv"
    r = run_script("validate_data.py", "--current", norm, "--output", out)
    assert r.returncode == 2
    assert "E-001" in set(pd.read_csv(out)["code"])


# --- シナリオ7: 表記揺れ → 媒体名・列名を統一 ---
def test_s7_normalization(tmp_path):
    # デモ: indeed→Indeed, 求人BOX→求人ボックス, 列名/数値形式
    cur = _norm(tmp_path, DEMO / "demo-current-month.csv", tmp_path / "c.csv",
                DEMO / "demo-company-settings.yaml", "2026-06")
    df = pd.read_csv(cur)
    detail = df[df["row_type"] == "detail"]
    assert set(detail["media"]) == {"Indeed", "求人ボックス", "エンゲージ"}
    # 別企業: マイナビ→マイナビバイト, townwork→タウンワーク, 独自列名
    cb = _norm(tmp_path, CB / "current.csv", tmp_path / "cb.csv", CB / "settings.yaml", "2026-06")
    dfb = pd.read_csv(cb)
    assert set(dfb["media"]) == {"マイナビバイト", "タウンワーク"}
    assert dfb["applications"].notna().all()  # 応募件数→applications 対応付け成功
    assert dfb["cost"].iloc[0] == 90000       # 「90,000円」→数値


# --- シナリオ8: 数値矛盾（面接>応募）→ 検出 ---
def test_s8_numeric_contradiction(tmp_path):
    bad = tmp_path / "bad.csv"
    pd.DataFrame([{"媒体": "Indeed", "職種": "営業", "拠点": "東京",
                   "応募数": 5, "面接数": 8, "採用数": 1, "広告費": 1000}]).to_csv(bad, index=False)
    norm = tmp_path / "n.csv"
    run_script("normalize_data.py", "--input", bad, "--output", norm, "--period", "2026-06")
    out = tmp_path / "v.csv"
    r = run_script("validate_data.py", "--current", norm, "--output", out)
    assert r.returncode == 2
    assert "E-010" in set(pd.read_csv(out)["code"])


# --- シナリオ9: 別企業設定でも動作（PPTX含む） ---
def test_s9_different_company(tmp_path):
    r = run_script("run_report.py",
                   "--settings", CB / "settings.yaml", "--current", CB / "current.csv",
                   "--previous", CB / "previous.csv", "--targets", CB / "targets.csv",
                   "--period", "2026-06", "--prev-period", "2026-05", "--outdir", tmp_path,
                   "--summary", DEMO / "generated-summary.md", "--make-pptx")
    assert r.returncode == 0, r.stderr
    prs = Presentation(tmp_path / "report.pptx")
    assert len(prs.slides) == 8   # 別企業はスライドを8種に絞っている


# --- シナリオ10: 非技術者の初期設定（設定が矛盾なく成立） ---
def test_s10_settings_valid_for_both_companies():
    for s in (DEMO / "demo-company-settings.yaml", CB / "settings.yaml"):
        r = run_script("validate_settings.py", "--settings", s)
        assert r.returncode == 0, f"{s}: {r.stderr}"


# --- 確認項目: 再実行の再現性 ---
def test_reproducibility(tmp_path):
    def once(d):
        d.mkdir()
        run_script("run_report.py", "--settings", CB / "settings.yaml",
                   "--current", CB / "current.csv", "--previous", CB / "previous.csv",
                   "--targets", CB / "targets.csv", "--period", "2026-06",
                   "--prev-period", "2026-05", "--outdir", d)
        return (d / "kpi_results.csv").read_text(encoding="utf-8")
    assert once(tmp_path / "a") == once(tmp_path / "b")


# --- 確認項目: 元データ保護・出力ファイル名・ログ ---
def test_output_files_and_log(tmp_path):
    r = run_script("run_report.py", "--settings", CB / "settings.yaml",
                   "--current", CB / "current.csv", "--period", "2026-06", "--outdir", tmp_path)
    assert r.returncode == 0, r.stderr
    for name in ("normalized_current.csv", "kpi_results.csv", "kpi_by_group.csv",
                 "validation_report.csv", "summary_input.json", "run.log"):
        assert (tmp_path / name).exists(), f"{name} が出力されていません"
    log = (tmp_path / "run.log").read_text(encoding="utf-8")
    assert "KPI計算完了" in log and "検証完了" in log
