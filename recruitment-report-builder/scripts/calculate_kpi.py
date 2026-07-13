#!/usr/bin/env python3
"""calculate_kpi.py — 標準化済みデータからKPI・前月比・目標比を計算する。

- 率・単価は明細行ごとに計算し、全体行は合計値から再計算する
- 0除算・欠損は「N/A」（0を返さない）
- 前月データなしは「NEW」、目標未設定は「NOT_SET」
- 丸め: 率=%小数1桁 / 単価=円整数四捨五入 / 前月比・目標比=%小数1桁

使用例:
  python3 scripts/calculate_kpi.py \
    --current output/normalized_current.csv \
    --previous output/normalized_previous.csv \
    --targets output/normalized_targets.csv \
    --output output/kpi_results.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from common import KEY_COLUMNS, NA, NEW, NOT_SET, setup_logger

HEADER = ["媒体", "職種", "拠点", "表示数", "クリック数", "応募数", "面接数", "採用数",
          "広告費", "クリック率", "応募率", "面接設定率", "採用率",
          "クリック単価", "応募単価", "採用単価",
          "応募数前月比", "応募単価前月比", "応募数目標比", "応募単価目標比"]

COUNT_COLS = ["impressions", "clicks", "applications", "interviews", "hires", "cost"]


def _num(value) -> float | None:
    """CSV読込後の値を数値またはNone（欠損）へ。数値以外はNone扱い（validateで検出済み前提）。"""
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def rate(num, den):
    if num is None or den is None or den == 0:
        return NA
    return round(num / den * 100, 1)


def unit_cost(cost, den):
    if cost is None or den is None or den == 0:
        return NA
    return round(cost / den)


def mom(cur, prev):
    if prev is NEW:
        return NEW
    if cur is None or prev is None or cur == NA or prev == NA:
        return NA
    if prev == 0:
        return 0.0 if cur == 0 else NA
    return round((cur - prev) / prev * 100, 1)


def vs_target(cur, target):
    if target is None:
        return NOT_SET
    if cur is None or cur == NA or target == 0:
        return NA
    return round(cur / target * 100, 1)


def _key(row) -> tuple:
    return tuple(None if pd.isna(row.get(c)) else row.get(c) for c in KEY_COLUMNS)


def _fmt_int(value):
    """実数列の表示: 欠損は空欄、それ以外は整数化。"""
    if value is None:
        return ""
    return int(value) if float(value) == int(value) else value


def calculate(current: pd.DataFrame, previous: pd.DataFrame | None,
              targets: pd.DataFrame | None, logger) -> pd.DataFrame:
    cur = current[current["row_type"] == "detail"].copy()
    if cur.empty:
        raise ValueError("当月データに明細行がありません。標準化結果を確認してください。")

    prev_map = {}
    if previous is not None:
        for _, r in previous[previous["row_type"] == "detail"].iterrows():
            prev_map[_key(r)] = {c: _num(r.get(c)) for c in COUNT_COLS}
    tgt_map = {}
    if targets is not None:
        for _, r in targets.iterrows():
            tgt_map[_key(r)] = {c: _num(r.get(c))
                                for c in ("target_applications", "target_cpa", "target_hires")}

    rows = []
    for _, r in cur.iterrows():
        v = {c: _num(r.get(c)) for c in COUNT_COLS}
        cpa = unit_cost(v["cost"], v["applications"])
        prev = prev_map.get(_key(r))
        if prev is None:
            app_mom = cpa_mom = NEW
        else:
            app_mom = mom(v["applications"], prev["applications"])
            cpa_mom = mom(cpa, unit_cost(prev["cost"], prev["applications"]))
        tgt = tgt_map.get(_key(r), {})
        rows.append([r.get("media"), r.get("job_category"),
                     r.get("location") if not pd.isna(r.get("location")) else "",
                     _fmt_int(v["impressions"]), _fmt_int(v["clicks"]), _fmt_int(v["applications"]),
                     _fmt_int(v["interviews"]), _fmt_int(v["hires"]), _fmt_int(v["cost"]),
                     rate(v["clicks"], v["impressions"]), rate(v["applications"], v["clicks"]),
                     rate(v["interviews"], v["applications"]), rate(v["hires"], v["applications"]),
                     unit_cost(v["cost"], v["clicks"]), cpa, unit_cost(v["cost"], v["hires"]),
                     app_mom, cpa_mom,
                     vs_target(v["applications"], tgt.get("target_applications")),
                     vs_target(cpa, tgt.get("target_cpa"))])

    # 全体合計（欠損は合計から除外。率・単価は合計値から再計算）
    def col_sum(df_rows, col, mapper=_num):
        vals = [mapper(x) for x in df_rows[col]]
        vals = [x for x in vals if x is not None]
        return sum(vals) if vals else None

    t = {c: col_sum(cur, c) for c in COUNT_COLS}
    t_cpa = unit_cost(t["cost"], t["applications"])
    if previous is not None and not previous[previous["row_type"] == "detail"].empty:
        pdet = previous[previous["row_type"] == "detail"]
        p_app, p_cost = col_sum(pdet, "applications"), col_sum(pdet, "cost")
        t_app_mom = mom(t["applications"], p_app)
        t_cpa_mom = mom(t_cpa, unit_cost(p_cost, p_app))
    else:
        t_app_mom = t_cpa_mom = NEW
    # 目標比: 全明細に目標がある場合のみ合算して算出。1つでも未設定なら NOT_SET
    keys = [_key(r) for _, r in cur.iterrows()]
    app_targets = [tgt_map.get(k, {}).get("target_applications") for k in keys]
    cpa_targets = [tgt_map.get(k, {}).get("target_cpa") for k in keys]
    t_app_tgt = vs_target(t["applications"], sum(x for x in app_targets if x is not None)
                          if any(x is not None for x in app_targets) else None) \
        if all(x is not None for x in app_targets) else \
        (vs_target(t["applications"], sum(x for x in app_targets if x is not None))
         if any(x is not None for x in app_targets) else NOT_SET)
    t_cpa_tgt = NOT_SET if any(x is None for x in cpa_targets) else NA

    rows.append(["全体", "合計", "-", *(_fmt_int(t[c]) for c in COUNT_COLS[:5]), _fmt_int(t["cost"]),
                 rate(t["clicks"], t["impressions"]), rate(t["applications"], t["clicks"]),
                 rate(t["interviews"], t["applications"]), rate(t["hires"], t["applications"]),
                 unit_cost(t["cost"], t["clicks"]), t_cpa, unit_cost(t["cost"], t["hires"]),
                 t_app_mom, t_cpa_mom, t_app_tgt, t_cpa_tgt])

    logger.info("KPI計算完了: 明細%d行 + 全体1行", len(rows) - 1)
    return pd.DataFrame(rows, columns=HEADER)


GROUP_HEADER = ["区分", "対象", "表示数", "クリック数", "応募数", "面接数", "採用数", "広告費",
                "クリック率", "応募率", "面接設定率", "採用率",
                "クリック単価", "応募単価", "採用単価",
                "応募数前月比", "応募単価前月比", "応募数目標比", "応募単価目標比"]

DIMENSIONS = [("media", "媒体"), ("job_category", "職種"), ("location", "拠点")]


def _col_sum(df_rows, col):
    if col not in df_rows.columns:
        return None
    vals = [_num(x) for x in df_rows[col]]
    vals = [x for x in vals if x is not None]
    return sum(vals) if vals else None


def build_groups(current: pd.DataFrame, previous: pd.DataFrame | None,
                 targets: pd.DataFrame | None, logger) -> pd.DataFrame:
    """媒体別・職種別・拠点別の集計行を作成する（率・単価は合計値から再計算）。

    集計単位の目標比: 応募数目標は加算可能なため、対象グループの全明細に目標が
    そろっている場合のみ算出する（1つでも欠ければ NOT_SET）。応募単価目標は
    グループ合算の定義が曖昧なため、集計行では常に NOT_SET とする。
    """
    cur = current[current["row_type"] == "detail"].copy()
    prev = previous[previous["row_type"] == "detail"].copy() if previous is not None else None
    tgt_map = {}
    if targets is not None:
        for _, r in targets.iterrows():
            tgt_map[_key(r)] = _num(r.get("target_applications"))

    out_rows = []
    for col, dim_name in DIMENSIONS:
        for value, g in cur.groupby(cur[col].fillna("（未設定）"), sort=False):
            counts = {c: _col_sum(g, c) for c in COUNT_COLS}
            cpa = unit_cost(counts["cost"], counts["applications"])
            # 前月比
            if prev is not None:
                pg = prev[prev[col].fillna("（未設定）") == value]
                if pg.empty:
                    app_mom = cpa_mom = NEW
                else:
                    p_app, p_cost = _col_sum(pg, "applications"), _col_sum(pg, "cost")
                    app_mom = mom(counts["applications"], p_app)
                    cpa_mom = mom(cpa, unit_cost(p_cost, p_app))
            else:
                app_mom = cpa_mom = NEW
            # 応募数目標比（全明細に目標があるときのみ）
            g_targets = [tgt_map.get(_key(r)) for _, r in g.iterrows()]
            if targets is None or any(x is None for x in g_targets):
                app_tgt = NOT_SET
            else:
                app_tgt = vs_target(counts["applications"], sum(g_targets))
            out_rows.append([dim_name, value,
                             *(_fmt_int(counts[c]) for c in COUNT_COLS[:5]), _fmt_int(counts["cost"]),
                             rate(counts["clicks"], counts["impressions"]),
                             rate(counts["applications"], counts["clicks"]),
                             rate(counts["interviews"], counts["applications"]),
                             rate(counts["hires"], counts["applications"]),
                             unit_cost(counts["cost"], counts["clicks"]), cpa,
                             unit_cost(counts["cost"], counts["hires"]),
                             app_mom, cpa_mom, app_tgt, NOT_SET])
    logger.info("集計完了: 媒体・職種・拠点別 計%d行", len(out_rows))
    return pd.DataFrame(out_rows, columns=GROUP_HEADER)


def main() -> int:
    ap = argparse.ArgumentParser(description="KPI・前月比・目標比の計算")
    ap.add_argument("--current", required=True, help="標準化済みの当月データCSV")
    ap.add_argument("--previous", help="標準化済みの前月データCSV（任意）")
    ap.add_argument("--targets", help="標準化済みの目標値CSV（任意）")
    ap.add_argument("--output", required=True, help="KPI結果の出力先CSV")
    ap.add_argument("--group-output", help="媒体別・職種別・拠点別の集計CSV出力先（任意）")
    ap.add_argument("--log", help="ログファイルパス")
    args = ap.parse_args()

    logger = setup_logger("calculate_kpi", args.log)
    try:
        current = pd.read_csv(args.current, dtype={"media": str})
        previous = pd.read_csv(args.previous) if args.previous else None
        targets = pd.read_csv(args.targets) if args.targets else None
        result = calculate(current, previous, targets, logger)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(args.output, index=False, encoding="utf-8")
        logger.info("KPI結果を出力しました: %s", args.output)
        if args.group_output:
            groups = build_groups(current, previous, targets, logger)
            Path(args.group_output).parent.mkdir(parents=True, exist_ok=True)
            groups.to_csv(args.group_output, index=False, encoding="utf-8")
            logger.info("集計結果を出力しました: %s", args.group_output)
        return 0
    except Exception as e:
        logger.error("KPI計算に失敗しました: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
