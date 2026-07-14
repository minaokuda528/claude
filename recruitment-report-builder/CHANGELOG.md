# 更新履歴（CHANGELOG）

本プロジェクトのバージョンごとの変更点を記録します。

## [1.0.0] - 2026-07（初期版）

汎用・セルフ実装型の求人媒体結果報告Skillの初期リリース。架空デモデータで完成形を構築。

### 追加
- 要件定義・システム設計・データフロー（`docs/`）
- 架空デモデータと正解データ一式（`demo/`）— 14種の代表ケースを網羅
- データ処理スクリプト（`scripts/`）
  - `normalize_data.py`（標準化）、`calculate_kpi.py`（KPI・前月比・目標比・集計）
  - `validate_data.py`（エラー/警告の区分検証）、`generate_summary_input.py`（構造化JSON）
  - `generate_pptx.py`（PowerPoint生成・検証・画像書き出し）
  - `validate_settings.py`（設定の矛盾検出）、`run_report.py`（一括実行）
  - `common.py`（共通処理）
- 分析・文章・KPI・スライド・検証・入力・エラー・設定の参照ルール（`references/`）
- 会社別設定テンプレートと確認チェックリスト（`templates/`）
- Skill本体 `SKILL.md`（4モード: 初期設定/レポート作成/設定変更/検証）と `agents/openai.yaml`
- お客様向けマニュアル（`docs/customer-setup-manual.md` ほか）とデモ台本
- テスト46件（単体・PPTX・設定・統合10シナリオ・別企業）

### 設計上の原則
- 数値計算はすべてスクリプトで実施（生成AIの文章推論で数値を作らない）
- 空欄と0を区別。0除算は「算出不可(N/A)」、前月なし「NEW」、目標なし「NOT_SET」
- データエラー時は確定資料を作らず停止
- 最終判断は人が行う

### 既知の制限
`docs/limitations.md` を参照。
