# データフロー定義｜recruitment-report-builder

- 版数: 1.0（フェーズ1）

## 1. 全体フロー

```text
┌─────────────┐
│ 利用者の入力            │ 当月CSV/xlsx（必須）、前月・目標（任意）、補足コメント（任意）
└──────┬──────┘
       ▼
[Step1] 設定読込
  company-settings.yaml / media-mapping.csv / report-settings.yaml
  → 設定なし: 初期設定モードへ分岐
       ▼
[Step2] 読み込み・形式判定
  文字コード判定 → CSV/xlsx読込 → 列構成の確認
  → 不足情報のみ利用者へ質問
       ▼
[Step3] 標準化 (normalize_data.py)
  入力: 生データ + media-mapping.csv
  処理: 列名統一 / 媒体名統一 / 空白除去 / カンマ・円・％除去 /
        空欄と0の区別 / 日付統一(YYYY-MM) / 不正値フラグ
  出力: normalized_*.csv（元データは保持・不変）
       ▼
[Step4] 検証 (validate_data.py)
  入力: normalized_*.csv（当月・前月・目標）
  出力: validation_report_*.csv（エラー/警告を区分）
  ├─ エラーあり → ★停止。エラー一覧と対処方法を提示（確定資料を作らない）
  └─ 警告のみ → 続行（警告はレポートへ引き継ぐ）
       ▼
[Step5] KPI計算 (calculate_kpi.py)
  入力: normalized当月・前月 + 目標
  処理: 明細・媒体別・職種別・拠点別・全体のKPI / 前月比 / 目標比
        0除算 → N/A、前月なし → NEW、目標なし → NOT_SET
  出力: kpi_results_*.csv
       ▼
[Step6] サマリー入力生成 (generate_summary_input.py)
  入力: kpi_results_*.csv + validation_report + 会社設定（判定閾値）+ 補足コメント
  出力: summary_input_*.json（好調/注意判定済み・根拠数値付き構造化データ）
       ▼
[Step7] サマリー作成（Claude）
  入力: summary_input_*.json + references/analysis-rules.md + writing-rules.md
  出力: summary_*.md（事実/示唆/要確認を区分）
       ▼
★[Step8] 人による確認（必須）
  サマリー・数値・警告を利用者が承認 → 修正があればStep7へ戻る
       ▼
[Step9] PowerPoint生成 (generate_pptx.py)
  入力: kpi_results_*.csv + summary_*.md + report-settings.yaml + blank-report-template.pptx
  ルール: 数値はCSVからのみ取得。N/A→「算出不可」等の表示変換
  出力: report_*.pptx
       ▼
[Step10] 最終検証
  数値一致チェック（PPTX内数値 vs CSV）/ レイアウト検証 / 開けるか確認
       ▼
┌─────────────┐
│ 納品: PPTX + KPI CSV +  │
│ サマリー + 警告一覧      │ ★最終確認は人が実施
└─────────────┘
```

## 2. モード別フロー

| モード | 実行範囲 |
|---|---|
| 初期設定モード | 対話質問 → 設定ファイル生成 → 承認 → 確定 |
| レポート作成モード | Step1〜10（全工程） |
| 検証モード | Step1〜5 + 検証レポート提示（PPTXなし） |
| 設定変更モード | 既存設定バックアップ → 差分変更 → 承認 → 確定 |

## 3. データ受け渡し契約（中間ファイル）

| ファイル | 生成者 | 消費者 | 形式の要点 |
|---|---|---|---|
| normalized_*.csv | normalize_data.py | validate/calculate | 標準列名（英字内部キー）。空欄は空セルのまま |
| validation_report_*.csv | validate_data.py | Claude/利用者 | level(error/warning), code, row, message, action |
| kpi_results_*.csv | calculate_kpi.py | summary_input/pptx/テスト | 特殊値 N/A / NEW / NOT_SET を文字列で保持 |
| summary_input_*.json | generate_summary_input.py | Claude | facts / flags / thresholds / comments を分離 |
| summary_*.md | Claude | generate_pptx.py | 見出し構造を固定（フェーズ4で定義） |

## 4. 停止ポイント（フェイルセーフ）

1. 会社設定なし → 初期設定へ案内（勝手にデフォルトで進めない）
2. 必須列不足・数値矛盾などのエラー → Step4で停止
3. サマリー未承認 → Step9へ進まない
4. PPTX数値不一致 → 納品せず再生成・報告

## 5. ファイル保護

- 入力ファイルは読み取り専用として扱い、上書き・移動しない
- 出力は `output/YYYY-MM/` へ新規作成（同名がある場合は連番付与）
- 設定変更時は `*.yaml.bak-<日時>` を先に作成
