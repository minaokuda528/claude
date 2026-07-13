#!/usr/bin/env python3
"""デモの正解KPI（expected-kpi-results.csv）を計算するスクリプト。

生データの表記揺れ・欠損を人手で解釈した「真の値」を CLEAN_* に定義し、
KPI・前月比・目標比をスクリプトで計算する（文章推論で数値を作らない）。
計算過程は kpi-calculation-process.md へ出力する。

丸めルール（docs/system-design.md）:
  率 = %・小数1桁 / 単価 = 円・整数四捨五入 / 前月比・目標比 = %・小数1桁
特殊値: N/A（0除算・欠損）, NEW（前月なし）, NOT_SET（目標なし）
"""
import csv
from pathlib import Path

HERE = Path(__file__).parent

# (media, job, location): [impressions, clicks, applications, interviews, hires, cost]
# None = 元データが空欄（欠損）
CLEAN_CURRENT = {
    ("Indeed", "法人営業", "東京"): [22000, 900, 30, 12, 3, 120000],
    ("Indeed", "一般事務", "東京"): [18000, 900, 30, 10, 1, 150000],
    ("求人ボックス", "法人営業", "大阪"): [30000, 1500, 5, 2, 0, 90000],
    ("エンゲージ", "一般事務", "大阪"): [5000, 200, 4, 3, 2, 40000],
    ("エンゲージ", "コールセンタースタッフ", "東京"): [8000, 320, 12, 4, 1, 60000],
    ("求人ボックス", "一般事務", "東京"): [12000, 300, 0, 0, 0, 45000],
    ("Indeed", "コールセンタースタッフ", "大阪"): [None, 400, 10, None, 1, 50000],
    ("求人ボックス", "コールセンタースタッフ", "大阪"): [15000, 500, 1, 0, 0, 80000],
    ("エンゲージ", "法人営業", "東京"): [4000, 150, 6, 2, 1, 0],
}
CLEAN_PREVIOUS = {
    ("Indeed", "法人営業", "東京"): [20000, 800, 20, 8, 2, 100000],
    ("Indeed", "一般事務", "東京"): [15000, 600, 25, 8, 1, 75000],
    ("求人ボックス", "法人営業", "大阪"): [28000, 1400, 8, 3, 1, 85000],
    ("エンゲージ", "一般事務", "大阪"): [5200, 210, 5, 3, 2, 40000],
    ("求人ボックス", "一般事務", "東京"): [11000, 280, 3, 1, 0, 42000],
    ("Indeed", "コールセンタースタッフ", "大阪"): [9000, 380, 9, 3, 1, 48000],
    ("求人ボックス", "コールセンタースタッフ", "大阪"): [14000, 480, 4, 1, 0, 70000],
    ("エンゲージ", "法人営業", "東京"): [3900, 140, 5, 2, 1, 0],
}
# (media, job, location): [応募数目標, 応募単価目標, 採用数目標]  None = 未設定
TARGETS = {
    ("Indeed", "法人営業", "東京"): [30, 4500, 2],
    ("Indeed", "一般事務", "東京"): [28, 4000, 1],
    ("求人ボックス", "法人営業", "大阪"): [10, 8000, 1],
    ("エンゲージ", "一般事務", "大阪"): [5, 8000, 1],
    ("求人ボックス", "一般事務", "東京"): [5, 10000, 1],
    ("Indeed", "コールセンタースタッフ", "大阪"): [10, 5000, 1],
    ("エンゲージ", "法人営業", "東京"): [5, None, 1],
}

NA, NEW, NOT_SET = "N/A", "NEW", "NOT_SET"


def rate(num, den):
    """率(%): 分子・分母が欠損、または分母0なら N/A。"""
    if num is None or den is None or den == 0:
        return NA
    return round(num / den * 100, 1)


def unit_cost(cost, den):
    """単価(円): 欠損・分母0なら N/A。四捨五入で整数。"""
    if cost is None or den is None or den == 0:
        return NA
    return round(cost / den)


def mom(cur, prev):
    """前月比(%): 前月なし=NEW / 前月0や算出不可=N/A / 両方0=0.0。"""
    if prev is NEW:
        return NEW
    if cur is None or prev is None or cur == NA or prev == NA:
        return NA
    if prev == 0:
        return 0.0 if cur == 0 else NA
    return round((cur - prev) / prev * 100, 1)


def vs_target(cur, target):
    """目標比(%): 目標なし=NOT_SET / 目標0や算出不可=N/A。"""
    if target is None:
        return NOT_SET
    if cur is None or cur == NA or target == 0:
        return NA
    return round(cur / target * 100, 1)


def main():
    header = ["媒体", "職種", "拠点", "表示数", "クリック数", "応募数", "面接数", "採用数",
              "広告費", "クリック率", "応募率", "面接設定率", "採用率",
              "クリック単価", "応募単価", "採用単価",
              "応募数前月比", "応募単価前月比", "応募数目標比", "応募単価目標比"]
    rows, log = [], []
    for key, cur in CLEAN_CURRENT.items():
        imp, clk, app, itv, hire, cost = cur
        prev = CLEAN_PREVIOUS.get(key)
        tgt = TARGETS.get(key)

        cpa = unit_cost(cost, app)
        row = {
            "クリック率": rate(clk, imp), "応募率": rate(app, clk),
            "面接設定率": rate(itv, app), "採用率": rate(hire, app),
            "クリック単価": unit_cost(cost, clk), "応募単価": cpa,
            "採用単価": unit_cost(cost, hire),
        }
        if prev is None:
            app_mom, cpa_mom = NEW, NEW
        else:
            prev_cpa = unit_cost(prev[5], prev[2])
            app_mom = mom(app, prev[2])
            cpa_mom = mom(cpa, prev_cpa)
        app_tgt = vs_target(app, tgt[0] if tgt else None)
        cpa_tgt = vs_target(cpa, tgt[1] if tgt else None)

        blank = lambda v: "" if v is None else v
        rows.append([*key, blank(imp), blank(clk), app, blank(itv), blank(hire), cost,
                     *[row[k] for k in ["クリック率", "応募率", "面接設定率", "採用率",
                                        "クリック単価", "応募単価", "採用単価"]],
                     app_mom, cpa_mom, app_tgt, cpa_tgt])

        log.append(f"### {key[0]} / {key[1]} / {key[2]}\n"
                   f"- 当月実数: 表示={imp} クリック={clk} 応募={app} 面接={itv} 採用={hire} 広告費={cost}\n"
                   f"- クリック率 = {clk}/{imp} → {row['クリック率']}\n"
                   f"- 応募率 = {app}/{clk} → {row['応募率']}\n"
                   f"- 面接設定率 = {itv}/{app} → {row['面接設定率']}\n"
                   f"- 採用率 = {hire}/{app} → {row['採用率']}\n"
                   f"- CPC = {cost}/{clk} → {row['クリック単価']}\n"
                   f"- CPA = {cost}/{app} → {row['応募単価']}\n"
                   f"- CPH = {cost}/{hire} → {row['採用単価']}\n"
                   f"- 応募数前月比: 前月={prev[2] if prev else 'なし'} → {app_mom}\n"
                   f"- 応募単価前月比 → {cpa_mom}\n"
                   f"- 応募数目標比: 目標={tgt[0] if tgt else 'なし'} → {app_tgt}\n"
                   f"- 応募単価目標比: 目標={tgt[1] if tgt else 'なし'} → {cpa_tgt}\n")

    # 全体合計行（欠損は合計から除外し、率・単価は合計値から再計算）
    def total(idx):
        return sum(v[idx] for v in CLEAN_CURRENT.values() if v[idx] is not None)
    t_imp, t_clk, t_app, t_itv, t_hire, t_cost = (total(i) for i in range(6))
    p_app = sum(v[2] for v in CLEAN_PREVIOUS.values())
    p_cost = sum(v[5] for v in CLEAN_PREVIOUS.values())
    t_cpa, p_cpa = unit_cost(t_cost, t_app), unit_cost(p_cost, p_app)
    t_app_tgt = sum(t[0] for t in TARGETS.values())
    rows.append(["全体", "合計", "-", t_imp, t_clk, t_app, t_itv, t_hire, t_cost,
                 rate(t_clk, t_imp), rate(t_app, t_clk), rate(t_itv, t_app), rate(t_hire, t_app),
                 unit_cost(t_cost, t_clk), t_cpa, unit_cost(t_cost, t_hire),
                 mom(t_app, p_app), mom(t_cpa, p_cpa), vs_target(t_app, t_app_tgt), NOT_SET])
    log.append(f"### 全体合計\n"
               f"- 表示={t_imp}（欠損1行は合計から除外） クリック={t_clk} 応募={t_app} 面接={t_itv}"
               f"（欠損1行除外） 採用={t_hire} 広告費={t_cost}\n"
               f"- 前月合計: 応募={p_app} 広告費={p_cost} 前月CPA={p_cpa}\n"
               f"- 全体CPA = {t_cost}/{t_app} → {t_cpa} / 応募数前月比 → {mom(t_app, p_app)}\n"
               f"- 応募数目標合計 = {t_app_tgt}（目標未設定2求人は含まず）\n"
               f"- 全体の応募単価目標比は、目標未設定求人があるため NOT_SET 扱い\n")

    with open(HERE / "expected-kpi-results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)

    with open(HERE / "kpi-calculation-process.md", "w", encoding="utf-8") as f:
        f.write("# 正解KPIの計算過程（generate_expected_kpi.py が自動出力）\n\n"
                "丸め: 率=％小数1桁 / 単価=円整数四捨五入。特殊値: N/A, NEW, NOT_SET。\n\n"
                + "\n".join(log))
    print(f"OK: {len(rows)}行を expected-kpi-results.csv へ出力（明細{len(rows)-1} + 合計1）")


if __name__ == "__main__":
    main()
