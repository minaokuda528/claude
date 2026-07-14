# recruitment-report-builder

採用月次レポートを **検証 → KPI計算 → サマリー作成 → PowerPoint作成** の
パイプラインで自動生成するツール。当月・前月・目標データ（JSON）を入力すると、
経営報告向けの 16:9 スライド（.pptx）と、確認用のスライド画像・コンタクトシートを出力する。

## パイプライン

| ステージ | 内容 |
|---|---|
| 1. 検証 (Validation) | 構造チェック（ファネル整合・非負）と **合計 vs 明細** の整合性チェック。合計と明細が一致しない箇所は **承認済み(approved)** として **明細合計** を採用して進める。 |
| 2. KPI計算 (KPI) | 検証済みの確定値から採用KPI（応募数・各通過率・内定承諾率・採用単価など）を算出し、前月比(MoM)・目標比を付与。 |
| 3. サマリー作成 (Summary) | KPI比較からハイライト・課題・次月アクションを生成。 |
| 4. PowerPoint作成 (Slides) | 6枚のスライド（表紙／サマリー／採用ファネル／KPI達成状況／媒体別／次月アクション）を生成し、画像化してコンタクトシートを作成。 |

## デモの実行

```bash
pip install python-pptx Pillow          # 必須
python run_demo.py
```

`demo/data/` の当月(`current_month.json`)・前月(`previous_month.json`)・
目標(`targets.json`)を使い、パイプラインを通しで実行する。成果物は `demo/output/` に出力される。

- `recruitment_report.pptx` — 生成された PowerPoint（6枚）
- `slides/slide_0X.png` — 各スライドの画像
- `contact_sheet.png` — スライド一覧（コンタクトシート）

## 構成

```
recruitment-report-builder/
├── run_demo.py                     # デモ実行スクリプト
├── demo/
│   ├── data/                       # 当月・前月・目標データ
│   └── output/                     # 生成物
└── src/recruitment_report/
    ├── validate.py                 # 検証
    ├── kpi.py                      # KPI計算
    ├── summary.py                  # サマリー作成
    ├── pptx_builder.py             # PowerPoint作成
    ├── png_renderer.py             # PPTX→PNG レンダラ（内蔵・外部依存なし）
    └── pipeline.py                 # パイプライン統括
```

## スライド画像化について

スライドの画像化は、まず LibreOffice（PDF経由）を試み、利用できない環境では
python-pptx + Pillow の **内蔵レンダラ**（`png_renderer.py`）にフォールバックする。
内蔵レンダラは生成済み `.pptx` の図形を走査して描画するため、外部プロセスに依存せず
どの環境でも同一の画像を生成できる。

## データ仕様（入力 JSON）

- `channels[]`: 媒体別のファネル各段（`applications` → `document_pass` →
  `first_interview` → `final_interview` → `offers` → `accepted`）と `cost`。
- `reported_totals`: 各段の「報告合計」。明細（channels の合計）と一致しない場合は
  検証ステージで検知され、承認済みとして明細合計が採用される。
- `targets.json`: 各段の目標(`stage_targets`)と KPI 目標(`kpi_targets`)。

> デモデータでは、当月の `applications`（合計425 / 明細430）と
> `accepted`（合計46 / 明細48）が意図的に不一致になっており、検証ステージで
> 「承認済み: 明細合計を採用」として処理される様子を確認できる。
