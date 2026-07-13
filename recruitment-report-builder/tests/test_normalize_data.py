import hashlib

import pandas as pd

from conftest import DEMO


def _md5(path):
    return hashlib.md5(path.read_bytes()).hexdigest()


def test_normalize_demo_current(pipeline):
    df = pd.read_csv(pipeline["current"])

    # 媒体名の表記揺れ統一（indeed / 求人BOX）
    media = set(df[df["row_type"] == "detail"]["media"])
    assert media == {"Indeed", "求人ボックス", "エンゲージ"}

    # 職種名の前後空白削除（全角空白付き「 コールセンタースタッフ」）
    jobs = set(df[df["row_type"] == "detail"]["job_category"])
    assert jobs == {"法人営業", "一般事務", "コールセンタースタッフ"}

    # 数値のカンマ・円除去（"120,000円" → 120000）
    row = df[(df["media"] == "Indeed") & (df["job_category"] == "法人営業")].iloc[0]
    assert row["cost"] == 120000
    assert row["impressions"] == 22000

    # 空欄と0の区別: 応募0件は0、表示数の空欄は欠損のまま
    zero_row = df[(df["media"] == "求人ボックス") & (df["job_category"] == "一般事務")].iloc[0]
    assert zero_row["applications"] == 0
    blank_row = df[(df["media"] == "Indeed") & (df["job_category"] == "コールセンタースタッフ")].iloc[0]
    assert pd.isna(blank_row["impressions"])
    assert pd.isna(blank_row["interviews"])

    # 合計行の判定
    assert (df["row_type"] == "total").sum() == 1
    assert (df["row_type"] == "detail").sum() == 9

    # 対象期間の付与
    assert set(df["period"]) == {"2026-06"}


def test_original_file_not_modified(pipeline):
    before = _md5(DEMO / "demo-current-month.csv")
    assert _md5(DEMO / "demo-current-month.csv") == before


def test_normalize_report_contains_changes(pipeline):
    report = pd.read_csv(pipeline["norm_report"])
    codes = set(report["code"])
    assert "W-004" in codes  # 媒体名統一
    assert "W-005" in codes  # 数値表記統一
    messages = " / ".join(report["message"])
    assert "indeed" in messages
    assert "求人BOX" in messages


def test_refuses_overwriting_input(tmp_path):
    from conftest import run_script
    src = DEMO / "demo-current-month.csv"
    r = run_script("normalize_data.py", "--input", src, "--output", src)
    assert r.returncode == 1
    assert "上書き" in r.stderr


def test_previous_month_column_aliases(pipeline):
    # 前月CSVは列名が異なる（媒体/拠点/表示数/広告費）が同じ内部キーへ揃う
    df = pd.read_csv(pipeline["previous"])
    row = df[(df["media"] == "Indeed") & (df["job_category"] == "法人営業")].iloc[0]
    assert row["impressions"] == 20000
    assert row["cost"] == 100000
    assert row["location"] == "東京"
