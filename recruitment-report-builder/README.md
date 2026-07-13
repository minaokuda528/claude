# recruitment-report-builder

求人媒体（Indeed・求人ボックス・エンゲージ等）の結果データから、
**KPI集計・前月/目標比較・分析サマリー・PowerPoint報告資料**を作成する、
複数企業で使える汎用・セルフ実装型のClaude Skillです。

- 数値計算はすべてPythonスクリプトで行い、生成AIの文章推論で数値を作りません。
- 初回に対話で会社別設定を作成します（セルフ実装型）。
- 空欄と0を区別し、0除算は「算出不可」と表示。エラー時は確定資料を作りません。
- 最終判断は人が行う設計です。

## できること / できないこと

**対応**: CSV / Excel の月次媒体データ、複数媒体・職種・拠点の集計、前月・目標比較、
表記揺れ・数値形式の正規化、データエラー検出、会社別カスタマイズ（KPI・スライド・色・文体）。

**非対応（初期版）**: PDFの自動数値抽出（転記のみ補助対応）、媒体管理画面への自動ログイン、
Google Drive監視・Slack/Gmail通知・定期実行、複数企業一括処理、Webダッシュボード、ATS連携。

## セットアップ

```bash
pip install -r requirements.txt   # Python 3.10 以上
```

主要ライブラリ: pandas, openpyxl, python-pptx, PyYAML, pytest
（画像書き出し用に Pillow / PyMuPDF は任意）。

## 使い方（Skillとして）

Claudeに「求人媒体の結果報告書を作りたい」等と依頼すると、`SKILL.md` に従って動作します。
初回は初期設定（会社情報・媒体・目標・資料・分析の質問）を対話で行います。

### コマンドで試す（デモデータ）

```bash
# 検証・KPI・サマリー入力まで（検証モード相当）
python3 scripts/run_report.py \
  --settings demo/demo-company-settings.yaml \
  --current demo/demo-current-month.csv \
  --previous demo/demo-previous-month.csv \
  --targets demo/demo-targets.csv \
  --period 2026-06 --prev-period 2026-05 \
  --outdir output/2026-06

# サマリーを人が確認したうえで PowerPoint まで生成
#（デモは合計行と明細の意図的な不一致を含むため、承認を示す --allow-total-mismatch を付与）
python3 scripts/run_report.py \
  --settings demo/demo-company-settings.yaml \
  --current demo/demo-current-month.csv \
  --previous demo/demo-previous-month.csv \
  --targets demo/demo-targets.csv \
  --period 2026-06 --prev-period 2026-05 \
  --outdir output/2026-06 \
  --summary demo/generated-summary.md \
  --template assets/blank-report-template.pptx \
  --allow-total-mismatch --make-pptx
```

出力は `output/2026-06/`（標準化データ・KPI・検証レポート・サマリー入力JSON・report.pptx）。

## テスト

```bash
python -m pytest tests/ -v
```

## ディレクトリ構成

```text
recruitment-report-builder/
├── SKILL.md            # Skill本体（動作指示）
├── CLAUDE.md           # 開発ルール
├── agents/openai.yaml  # 外部エージェント基盤向け定義
├── references/         # 詳細ルール（分析・文章・KPI・検証・設定・入力・エラー）
├── templates/          # 会社別設定テンプレート
├── demo/               # 架空デモデータ・正解データ・デモ資料
├── assets/             # 空PPTXテンプレート
├── scripts/            # Pythonスクリプト（数値処理）
├── tests/              # pytest
├── output/             # 生成物（コミット対象外）
└── docs/               # 設計書・マニュアル
```

## 主なスクリプト

| スクリプト | 役割 |
|---|---|
| `run_report.py` | パイプライン一括実行（標準化→KPI→検証→サマリー入力→任意でPPTX） |
| `normalize_data.py` | 列名・媒体名・数値形式の標準化 |
| `calculate_kpi.py` | KPI・前月比・目標比の計算（明細＋媒体/職種/拠点別集計） |
| `validate_data.py` | データ検証（エラー／警告の区分） |
| `generate_summary_input.py` | サマリー用の構造化JSON生成 |
| `generate_pptx.py` | PowerPoint生成・検証・画像書き出し |
| `validate_settings.py` | 会社設定の形式・矛盾チェック |

## 注意事項

- 実在企業のロゴ・商標・機密数値、応募者個人情報を入力・出力・ログに残さないでください。
- デモデータはすべて架空です。
- 初回利用時は、主要KPIを媒体管理画面の値と必ず照合してください（`templates/review-checklist.md`）。

制限事項の詳細は `docs/open-questions.md` を参照してください。
