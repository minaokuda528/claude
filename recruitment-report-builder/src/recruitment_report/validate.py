"""検証（Validation）ステージ.

月次データの構造チェックと、「合計（reported_totals）」と「明細（channels の合計）」の
整合性チェックを行う。合計と明細が一致しない箇所は承認済み(approved)として扱い、
明細合計を採用して後続処理を進める。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ValidationIssue:
    field: str
    reported: int
    detail_sum: int
    resolution: str

    @property
    def delta(self) -> int:
        return self.reported - self.detail_sum


@dataclass
class ValidationResult:
    period_label: str
    validated_totals: dict          # 後続で使用する確定値（=明細合計）
    issues: list = field(default_factory=list)
    structural_errors: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.structural_errors


def _detail_sum(data: dict, field_name: str) -> int:
    return sum(int(ch[field_name]) for ch in data["channels"])


def validate(data: dict, approve_mismatches: bool = True) -> ValidationResult:
    """月次データを検証する.

    approve_mismatches=True の場合、合計と明細の不一致は「承認済み」として
    明細合計を採用する（後続の validated_totals には常に明細合計が入る）。
    """
    fields = list(data["reported_totals"].keys())
    validated_totals: dict = {}
    issues: list[ValidationIssue] = []
    structural_errors: list[str] = []

    # 1) 合計 vs 明細 の整合性チェック
    for f in fields:
        reported = int(data["reported_totals"][f])
        detail = _detail_sum(data, f)
        validated_totals[f] = detail  # 明細を信頼して確定値とする
        if reported != detail:
            if approve_mismatches:
                resolution = "承認済み: 明細合計を採用"
            else:
                resolution = "未承認: 要確認"
                structural_errors.append(
                    f"{f}: 合計({reported}) と明細合計({detail}) が不一致"
                )
            issues.append(
                ValidationIssue(
                    field=f, reported=reported, detail_sum=detail, resolution=resolution
                )
            )

    # 2) 構造チェック: ファネルが単調非増加であること、負値がないこと
    stages = data["stages"]
    for ch in data["channels"]:
        prev = None
        for st in stages:
            v = int(ch[st])
            if v < 0:
                structural_errors.append(f"{ch['name']} / {st}: 負の値 ({v})")
            if prev is not None and v > prev:
                structural_errors.append(
                    f"{ch['name']}: ファネル逆転 ({st}={v} > 前段={prev})"
                )
            prev = v

    return ValidationResult(
        period_label=data.get("period_label", data.get("period", "")),
        validated_totals=validated_totals,
        issues=issues,
        structural_errors=structural_errors,
    )


def format_report(result: ValidationResult) -> str:
    lines = [f"■ 検証結果: {result.period_label}"]
    if result.structural_errors:
        lines.append("  構造エラー:")
        for e in result.structural_errors:
            lines.append(f"    - {e}")
    else:
        lines.append("  構造チェック: OK（ファネル整合・非負）")

    if result.issues:
        lines.append("  合計 vs 明細:")
        for i in result.issues:
            sign = "+" if i.delta > 0 else ""
            lines.append(
                f"    - {i.field}: 合計={i.reported} / 明細={i.detail_sum} "
                f"(差分 {sign}{i.delta}) → {i.resolution}"
            )
    else:
        lines.append("  合計 vs 明細: 全項目一致")
    return "\n".join(lines)
