"""KPI計算ステージ.

検証済みの確定値（明細合計）を用いて採用KPIを算出し、
前月比(MoM)・目標比を付与する。
"""

from __future__ import annotations

from dataclasses import dataclass


def _rate(numer: float, denom: float) -> float:
    return (numer / denom) if denom else 0.0


@dataclass
class KpiSet:
    period_label: str
    funnel: dict          # stage -> 確定値
    metrics: dict         # KPI名 -> 値
    channel_rollup: list  # チャネル別 集計（率つき）


def compute_kpis(data: dict, validated_totals: dict) -> KpiSet:
    f = validated_totals
    apps = f["applications"]
    doc = f["document_pass"]
    first = f["first_interview"]
    final = f["final_interview"]
    offers = f["offers"]
    accepted = f["accepted"]
    cost = f["cost"]

    metrics = {
        "applications": apps,
        "hires": accepted,
        "offers": offers,
        "document_pass_rate": _rate(doc, apps),
        "first_interview_rate": _rate(first, doc),
        "final_interview_rate": _rate(final, first),
        "offer_rate": _rate(offers, final),
        "offer_acceptance_rate": _rate(accepted, offers),
        "overall_conversion": _rate(accepted, apps),
        "total_cost": cost,
        "cost_per_hire": int(round(cost / accepted)) if accepted else 0,
    }

    channel_rollup = []
    for ch in data["channels"]:
        channel_rollup.append(
            {
                "name": ch["name"],
                "applications": ch["applications"],
                "hires": ch["accepted"],
                "offers": ch["offers"],
                "cost": ch["cost"],
                "acceptance_rate": _rate(ch["accepted"], ch["offers"]),
                "conversion": _rate(ch["accepted"], ch["applications"]),
                "cost_per_hire": int(round(ch["cost"] / ch["accepted"])) if ch["accepted"] else None,
            }
        )

    return KpiSet(
        period_label=data.get("period_label", data.get("period", "")),
        funnel={k: f[k] for k in data["stages"]},
        metrics=metrics,
        channel_rollup=channel_rollup,
    )


@dataclass
class KpiComparison:
    current: KpiSet
    previous: KpiSet
    targets: dict
    rows: list  # 各KPIの current/prev/target/mom/attainment


def _delta_pct(cur: float, prev: float) -> float | None:
    if prev == 0:
        return None
    return (cur - prev) / prev


def compare(current: KpiSet, previous: KpiSet, targets: dict) -> KpiComparison:
    kt = targets.get("kpi_targets", {})
    cm = current.metrics
    pm = previous.metrics

    def row(key, label, fmt, target=None, higher_is_better=True):
        cur = cm.get(key)
        prev = pm.get(key)
        mom = _delta_pct(cur, prev) if isinstance(cur, (int, float)) else None
        attainment = None
        met = None
        if target is not None and target:
            attainment = cur / target
            if higher_is_better:
                met = cur >= target
            else:
                met = cur <= target
        return {
            "key": key,
            "label": label,
            "fmt": fmt,
            "current": cur,
            "previous": prev,
            "target": target,
            "mom": mom,
            "attainment": attainment,
            "met": met,
            "higher_is_better": higher_is_better,
        }

    rows = [
        row("applications", "応募数", "int", targets.get("stage_targets", {}).get("applications")),
        row("hires", "採用数（内定承諾）", "int", kt.get("hires")),
        row("document_pass_rate", "書類選考通過率", "pct", kt.get("document_pass_rate")),
        row("offer_acceptance_rate", "内定承諾率", "pct", kt.get("offer_acceptance_rate")),
        row("overall_conversion", "応募→採用 転換率", "pct"),
        row("cost_per_hire", "採用単価", "yen", kt.get("cost_per_hire"), higher_is_better=False),
    ]
    return KpiComparison(current=current, previous=previous, targets=targets, rows=rows)


# ---- フォーマットヘルパ ----
def fmt_value(value, fmt) -> str:
    if value is None:
        return "—"
    if fmt == "pct":
        return f"{value * 100:.1f}%"
    if fmt == "yen":
        return f"¥{value:,.0f}"
    if fmt == "int":
        return f"{value:,.0f}"
    return str(value)


def fmt_mom(mom) -> str:
    if mom is None:
        return "—"
    arrow = "▲" if mom > 0 else ("▼" if mom < 0 else "→")
    return f"{arrow}{abs(mom) * 100:.1f}%"


def format_report(comp: KpiComparison) -> str:
    lines = [f"■ KPI計算結果: {comp.current.period_label}（前月比・目標比）"]
    for r in comp.rows:
        cur = fmt_value(r["current"], r["fmt"])
        prev = fmt_value(r["previous"], r["fmt"])
        tgt = fmt_value(r["target"], r["fmt"]) if r["target"] is not None else "—"
        mom = fmt_mom(r["mom"])
        status = ""
        if r["met"] is True:
            status = "  ✅達成"
        elif r["met"] is False:
            status = "  ⚠️未達"
        lines.append(
            f"    - {r['label']}: {cur}（前月 {prev} / 目標 {tgt} / MoM {mom}）{status}"
        )
    return "\n".join(lines)
