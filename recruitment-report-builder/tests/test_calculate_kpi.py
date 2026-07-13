import pandas as pd
import pytest

from conftest import DEMO, run_script

# 浮動小数点の許容誤差（docs/open-questions.md A-9）
RATE_TOL = 0.05   # 率・比率（%ポイント）
YEN_TOL = 0.5     # 単価（円）

RATE_COLS = ["クリック率", "応募率", "面接設定率", "採用率",
             "応募数前月比", "応募単価前月比", "応募数目標比", "応募単価目標比"]
YEN_COLS = ["クリック単価", "応募単価", "採用単価"]
COUNT_COLS = ["表示数", "クリック数", "応募数", "面接数", "採用数", "広告費"]


@pytest.fixture
def kpi_result(pipeline):
    r = run_script("calculate_kpi.py",
                   "--current", pipeline["current"],
                   "--previous", pipeline["previous"],
                   "--targets", pipeline["targets"],
                   "--output", pipeline["kpi"])
    assert r.returncode == 0, r.stderr
    # "N/A" 等の特殊値を欠損値扱いさせず文字列のまま読む
    return pd.read_csv(pipeline["kpi"], dtype=str, keep_default_na=False)


def _index(df):
    return {(r["媒体"], r["職種"], r["拠点"]): r for _, r in df.iterrows()}


def test_kpi_matches_expected(kpi_result):
    expected = pd.read_csv(DEMO / "expected-kpi-results.csv", dtype=str, keep_default_na=False)
    actual = _index(kpi_result)
    assert len(kpi_result) == len(expected), "行数が正解データと一致しません"

    for _, exp in expected.iterrows():
        key = (exp["媒体"], exp["職種"], exp["拠点"])
        assert key in actual, f"行が見つかりません: {key}"
        act = actual[key]
        for col in COUNT_COLS + RATE_COLS + YEN_COLS:
            e, a = exp[col], act[col]
            if e in ("", "N/A", "NEW", "NOT_SET"):
                # 特殊値・空欄は完全一致
                assert a == e, f"{key} の {col}: 期待={e!r} 実際={a!r}"
            else:
                tol = RATE_TOL if col in RATE_COLS else YEN_TOL if col in YEN_COLS else 0.5
                assert abs(float(a) - float(e)) <= tol, \
                    f"{key} の {col}: 期待={e} 実際={a}"


def test_no_division_by_zero_artifacts(kpi_result):
    # 応募0件の行: 応募単価は0ではなくN/A
    row = _index(kpi_result)[("求人ボックス", "一般事務", "東京")]
    assert row["応募単価"] == "N/A"
    assert row["面接設定率"] == "N/A"
    # 採用0の行: 採用単価はN/A
    row2 = _index(kpi_result)[("求人ボックス", "法人営業", "大阪")]
    assert row2["採用単価"] == "N/A"


def test_new_and_not_set(kpi_result):
    idx = _index(kpi_result)
    new_row = idx[("エンゲージ", "コールセンタースタッフ", "東京")]
    assert new_row["応募数前月比"] == "NEW"
    assert new_row["応募数目標比"] == "NOT_SET"
    no_target = idx[("求人ボックス", "コールセンタースタッフ", "大阪")]
    assert no_target["応募数目標比"] == "NOT_SET"


def test_total_recalculated_from_sums(kpi_result):
    total = _index(kpi_result)[("全体", "合計", "-")]
    assert total["応募数"] == "98"       # 明細合計（合計行103は使わない）
    assert total["広告費"] == "635000"
    assert abs(float(total["応募単価"]) - 6480) <= YEN_TOL


def test_runs_without_previous_and_targets(pipeline):
    out = pipeline["tmp"] / "kpi_no_prev.csv"
    r = run_script("calculate_kpi.py", "--current", pipeline["current"], "--output", out)
    assert r.returncode == 0, r.stderr
    df = pd.read_csv(out, dtype=str, keep_default_na=False)
    detail = df[df["媒体"] != "全体"]
    assert set(detail["応募数前月比"]) == {"NEW"}
    assert set(detail["応募数目標比"]) == {"NOT_SET"}
