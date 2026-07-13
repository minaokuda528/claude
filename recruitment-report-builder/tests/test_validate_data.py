import pandas as pd

from conftest import DEMO, run_script


def _run_validation(pipeline, with_kpi=True):
    args = ["--current", pipeline["current"],
            "--previous", pipeline["previous"],
            "--targets", pipeline["targets"],
            "--settings", DEMO / "demo-company-settings.yaml",
            "--normalize-report", pipeline["norm_report"],
            "--output", pipeline["validation"]]
    if with_kpi:
        r = run_script("calculate_kpi.py", "--current", pipeline["current"],
                       "--previous", pipeline["previous"], "--targets", pipeline["targets"],
                       "--output", pipeline["kpi"])
        assert r.returncode == 0, r.stderr
        args += ["--kpi", pipeline["kpi"]]
    return run_script("validate_data.py", *args)


def test_demo_detects_expected_findings(pipeline):
    r = _run_validation(pipeline)
    assert r.returncode == 2, "合計不一致エラーがあるため終了コード2で停止すべき"
    report = pd.read_csv(pipeline["validation"])
    errors = report[report["level"] == "error"]
    warnings = report[report["level"] == "warning"]

    # E-020 合計不一致は応募数のみ（103 vs 98）
    assert set(errors["code"]) == {"E-020"}
    assert len(errors) == 1
    assert "applications" in errors.iloc[0]["target"]

    codes = set(warnings["code"])
    for expected_code in ("W-001", "W-002", "W-003", "W-004", "W-005",
                          "W-010", "W-011", "W-012", "W-013"):
        assert expected_code in codes, f"{expected_code} が検出されていません"

    # 過検出の防止: 数値矛盾・マイナス・必須列不足は存在しない
    for absent in ("E-001", "E-002", "E-003", "E-010", "E-011"):
        assert absent not in set(report["code"]), f"{absent} は誤検出"

    # W-002 目標未設定は2求人
    assert len(warnings[warnings["code"] == "W-002"]) == 2
    # W-010 異常単価は求人ボックス コールセンタースタッフ 大阪
    w010 = warnings[warnings["code"] == "W-010"]
    assert len(w010) == 1 and "コールセンタースタッフ" in w010.iloc[0]["target"]


def test_zero_applications_is_not_missing(pipeline):
    """応募0件を欠損(W-003)と誤判定しないこと。"""
    _run_validation(pipeline)
    report = pd.read_csv(pipeline["validation"])
    w003 = report[report["code"] == "W-003"]
    assert not any(("一般事務" in t) and ("求人ボックス" in t) for t in w003["target"])


def _write_normalized(tmp_path, rows, name="synthetic.csv"):
    cols = ["row_type", "media", "job_category", "location", "period",
            "impressions", "clicks", "applications", "interviews", "hires", "cost",
            "target_applications", "target_cpa", "target_hires", "note"]
    df = pd.DataFrame(rows, columns=cols)
    path = tmp_path / name
    df.to_csv(path, index=False)
    return path


def test_detects_interviews_exceeding_applications(tmp_path):
    path = _write_normalized(tmp_path, [
        ["detail", "Indeed", "営業", "東京", "2026-06", 100, 10, 3, 5, 1, 1000, None, None, None, None]])
    out = tmp_path / "v.csv"
    r = run_script("validate_data.py", "--current", path, "--output", out)
    assert r.returncode == 2
    assert "E-010" in set(pd.read_csv(out)["code"])


def test_detects_hires_exceeding_interviews(tmp_path):
    path = _write_normalized(tmp_path, [
        ["detail", "Indeed", "営業", "東京", "2026-06", 100, 10, 5, 2, 3, 1000, None, None, None, None]])
    out = tmp_path / "v.csv"
    r = run_script("validate_data.py", "--current", path, "--output", out)
    assert r.returncode == 2
    assert "E-011" in set(pd.read_csv(out)["code"])


def test_detects_negative_and_non_numeric(tmp_path):
    path = _write_normalized(tmp_path, [
        ["detail", "Indeed", "営業", "東京", "2026-06", 100, -10, 5, 2, 1, "十万円", None, None, None, None]])
    out = tmp_path / "v.csv"
    r = run_script("validate_data.py", "--current", path, "--output", out)
    assert r.returncode == 2
    codes = set(pd.read_csv(out)["code"])
    assert "E-003" in codes  # マイナス値
    assert "E-002" in codes  # 数値以外


def test_detects_missing_required_column(tmp_path):
    df = pd.DataFrame([{"row_type": "detail", "media": "Indeed", "job_category": "営業",
                        "cost": 1000}])  # applications列なし
    path = tmp_path / "missing.csv"
    df.to_csv(path, index=False)
    out = tmp_path / "v.csv"
    r = run_script("validate_data.py", "--current", path, "--output", out)
    assert r.returncode == 2
    assert "E-001" in set(pd.read_csv(out)["code"])


def test_detects_duplicate_rows(tmp_path):
    row = ["detail", "Indeed", "営業", "東京", "2026-06", 100, 10, 5, 2, 1, 1000, None, None, None, None]
    path = _write_normalized(tmp_path, [row, list(row)])
    out = tmp_path / "v.csv"
    r = run_script("validate_data.py", "--current", path, "--output", out)
    assert r.returncode == 0  # 重複は警告（続行可）
    assert "W-006" in set(pd.read_csv(out)["code"])
