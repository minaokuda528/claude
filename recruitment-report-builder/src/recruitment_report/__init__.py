"""recruitment-report-builder.

採用月次レポートを、検証 → KPI計算 → サマリー作成 → PowerPoint作成 の
パイプラインで自動生成するツール。
"""

from . import validate, kpi, summary, pptx_builder, pipeline  # noqa: F401

__all__ = ["validate", "kpi", "summary", "pptx_builder", "pipeline"]
__version__ = "0.1.0"
