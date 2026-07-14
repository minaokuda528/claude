#!/usr/bin/env python3
"""recruitment-report-builder デモ実行スクリプト.

demo/data の当月・前月・目標データを使い、
検証 → KPI計算 → サマリー作成 → PowerPoint作成 を通しで実行する。
合計と明細の不一致は「承認済み」として明細合計で進める。

    python run_demo.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))

from recruitment_report import pipeline  # noqa: E402


def main():
    data = os.path.join(HERE, "demo", "data")
    out = os.path.join(HERE, "demo", "output")
    result = pipeline.run(
        current_path=os.path.join(data, "current_month.json"),
        previous_path=os.path.join(data, "previous_month.json"),
        targets_path=os.path.join(data, "targets.json"),
        out_dir=out,
        approve_mismatches=True,
        verbose=True,
    )
    print("\n" + "=" * 68)
    print("完了。成果物:")
    print(f"  - PowerPoint : {result['pptx']}")
    print(f"  - スライド画像: {len(result['slide_pngs'])} 枚 ({os.path.dirname(result['slide_pngs'][0])})")
    print(f"  - コンタクトシート: {result['contact_sheet']}")
    print("=" * 68)


if __name__ == "__main__":
    main()
