"""サマリー作成ステージ.

KPI比較結果から、経営報告向けのエグゼクティブサマリー（要点箇条書き）と
次月アクションを生成する。
"""

from __future__ import annotations

from .kpi import KpiComparison, fmt_value, fmt_mom


def _row(comp: KpiComparison, key: str):
    for r in comp.rows:
        if r["key"] == key:
            return r
    return None


def build_summary(comp: KpiComparison) -> dict:
    highlights: list[str] = []
    concerns: list[str] = []
    actions: list[str] = []

    hires = _row(comp, "hires")
    apps = _row(comp, "applications")
    acc = _row(comp, "offer_acceptance_rate")
    cph = _row(comp, "cost_per_hire")
    doc = _row(comp, "document_pass_rate")

    # 採用数
    if hires:
        line = f"採用数は {fmt_value(hires['current'], 'int')}名（前月比 {fmt_mom(hires['mom'])}）"
        if hires["met"]:
            line += f"、目標 {fmt_value(hires['target'], 'int')}名を達成"
            highlights.append(line)
        else:
            line += f"、目標 {fmt_value(hires['target'], 'int')}名に対し未達"
            concerns.append(line)

    # 応募数
    if apps:
        line = f"応募数は {fmt_value(apps['current'], 'int')}件（前月比 {fmt_mom(apps['mom'])}）"
        if apps["met"]:
            highlights.append(line + "で目標超過")
        else:
            concerns.append(line)

    # 内定承諾率
    if acc:
        line = f"内定承諾率 {fmt_value(acc['current'], 'pct')}（前月 {fmt_value(acc['previous'], 'pct')}）"
        (highlights if acc["met"] else concerns).append(line)

    # 採用単価
    if cph:
        line = f"採用単価 {fmt_value(cph['current'], 'yen')}（前月 {fmt_value(cph['previous'], 'yen')}）"
        if cph["met"]:
            highlights.append(line + f"、目標 {fmt_value(cph['target'], 'yen')}以内")
        else:
            concerns.append(line + f"、目標 {fmt_value(cph['target'], 'yen')}を超過")

    # チャネル最良/コスト効率
    roll = comp.current.channel_rollup
    best_conv = max(roll, key=lambda c: c["conversion"])
    highlights.append(
        f"最も転換率が高いチャネルは {best_conv['name']}（応募→採用 {best_conv['conversion'] * 100:.1f}%）"
    )
    valid_cph = [c for c in roll if c["cost_per_hire"]]
    worst_cph = max(valid_cph, key=lambda c: c["cost_per_hire"])
    concerns.append(
        f"{worst_cph['name']} は採用単価が {worst_cph['cost_per_hire']:,.0f}円と突出"
    )

    # 次月アクション
    actions.append(f"{best_conv['name']}への配分を増やし、高効率チャネルを強化")
    actions.append(f"{worst_cph['name']}のコスト対効果を精査し、単価適正化を交渉")
    if doc and doc["current"] is not None:
        actions.append(f"書類選考通過率 {fmt_value(doc['current'], 'pct')} の質を維持しつつ母集団を拡大")
    actions.append("内定承諾率の維持に向け、内定者フォロー（面談・オファー面談）を継続")

    headline = (
        f"{comp.current.period_label}は採用目標を達成。"
        if hires and hires["met"]
        else f"{comp.current.period_label}は採用目標に対し未達。"
    )

    return {
        "period_label": comp.current.period_label,
        "headline": headline,
        "highlights": highlights,
        "concerns": concerns,
        "actions": actions,
    }


def format_report(summary: dict) -> str:
    lines = [f"■ サマリー: {summary['period_label']}", f"  {summary['headline']}"]
    lines.append("  ハイライト:")
    for h in summary["highlights"]:
        lines.append(f"    ✓ {h}")
    lines.append("  課題:")
    for c in summary["concerns"]:
        lines.append(f"    ! {c}")
    lines.append("  次月アクション:")
    for a in summary["actions"]:
        lines.append(f"    → {a}")
    return "\n".join(lines)
