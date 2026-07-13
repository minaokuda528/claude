---
name: recruitment-report-builder
description: >-
  求人媒体（Indeed・求人ボックス・エンゲージ等）の結果データから、KPI集計・前月/目標比較・
  分析サマリー・PowerPoint報告資料を作成する。複数企業で使える汎用・セルフ実装型。
  「求人媒体の結果報告書を作りたい」「採用媒体の月次レポート」「応募数や採用単価を集計」
  「求人広告の実績を分析」「求人媒体の結果からPowerPointを作りたい」
  「自社用の求人媒体レポートを設定したい」といった依頼で使う。数値計算は必ず同梱スクリプトで行う。
---

# recruitment-report-builder

求人媒体の月次結果を、KPI集計→検証→サマリー→PowerPointまで半自動で作成するSkill。
**数値はすべてスクリプトで計算し、生成AIの文章推論で数値を作らない。最終判断は人が行う。**

## 最初に判定すること（動作モード）

1. 会社設定（`company-settings.yaml`）が無い、または利用者が初期設定を望む → **初期設定モード**
2. 会社設定があり、媒体データからレポートを作る → **レポート作成モード**
3. 既存設定（KPI・媒体・スライド等）を変えたい → **設定変更モード**
4. 数値だけ確認したい（PowerPoint不要）→ **検証モード**

判断に迷う情報が足りなければ、利用者に1つだけ確認する。

## 前提

- Python 3.10以上。初回に `pip install -r requirements.txt`。
- スクリプト実行はClaudeが代行する（利用者にコマンドライン操作を求めない）。
- 元ファイルは上書きしない。出力は `output/<期間>/` へ。設定変更前はバックアップを取る。

---

## モード1: 初期設定モード

`references/setup-guide.md` に従う。

1. 質問を5〜8問ずつ、5グループ（基本情報→媒体→目標→資料→分析）で進める。専門用語は言い換える。
2. 「不明」「未設定」を許容し、後から変更できると伝える。回答済みは聞き直さない。
3. `templates/company-settings-template.yaml` を雛形に設定を組み立てる。
   媒体の表記揺れは `templates/media-mapping-template.csv` を参考に整理。
4. `python3 scripts/validate_settings.py --settings <path>` で矛盾チェック。
5. 確認画面（setup-guide.md の様式）を提示し、**承認後に保存**（`settings/<会社名>/company-settings.yaml`）。

## モード2: レポート作成モード

`references/error-handling.md` を随時参照。工程ごとに停止条件を守る。

1. 会社設定を読む。無ければモード1へ案内。
2. 入力ファイル（当月／任意で前月・目標）と形式を確認。`references/input-schema.md` 参照。
3. 必須項目を確認し、**不足情報だけ**を質問する。
4. 一括実行（標準化→KPI→検証→サマリー入力）:
   ```
   python3 scripts/run_report.py \
     --settings <settings.yaml> --current <当月> [--previous <前月>] [--targets <目標>] \
     --period <YYYY-MM> [--prev-period <YYYY-MM>] --outdir output/<期間> [--comments "<補足>"]
   ```
   - 終了コード2（検証エラー）なら**停止**。`validation_report.csv` の内容と対処を提示。
     合計不一致などは、承認後に `--allow-total-mismatch` を付けて再実行。
5. `output/<期間>/summary_input.json` を根拠に、`references/analysis-rules.md` と
   `references/writing-rules.md` に従ってサマリー（`summary_<期間>.md`）を作成。
   事実／示唆／要確認を必ず分け、全記述に根拠数値を付ける。JSONにない数値を書かない。
6. **PowerPoint作成前に、サマリーと主要数値・警告を利用者に確認してもらう。**
7. 承認後、PowerPointを生成:
   ```
   python3 scripts/run_report.py ... --summary <summary.md> \
     --template assets/blank-report-template.pptx --make-pptx [--allow-total-mismatch]
   ```
   （数値は `references/slide-structure.md` の通りCSV/JSONからのみ取得。手入力しない。）
8. `pptx_validation.csv` を確認（`references/validation-rules.md`）。エラーがあれば納品せず再生成。
9. 完成ファイル・要確認事項・警告一覧を提示。初回は媒体管理画面との数値照合を促す。
   `templates/review-checklist.md` を人による最終確認に使う。

## モード3: 設定変更モード

`references/customization-guide.md` に従う。

1. 対象の `company-settings.yaml` をバックアップ（`*.bak-<日時>`）。
2. 変えたい箇所だけ対話で確認（他は聞き直さない）。
3. `validate_settings.py` で矛盾チェック → 承認後に保存。

## モード4: 検証モード

レポート作成モードの手順1〜4のみ実行し、`kpi_results.csv` と `validation_report.csv` を提示する。
PowerPointは作らない（`--make-pptx` を付けない）。

---

## 重要ルール（全モード共通）

- データエラーがある状態で確定資料を作らない。
- 不明な数値を補完しない。空欄と0を区別する。0除算は「算出不可」。
- 数値計算はスクリプトで行う。サマリーの数値は `summary_input.json` の値のみ使う。
- 推測と事実を分ける（事実／示唆／要確認）。
- PowerPoint作成前に分析内容を人に確認してもらう。
- 会社設定が無ければ初期設定へ案内する。初回は人による数値確認を促す。
- 既存PowerPointは構成の参考にとどめ、その数値を新実績として流用しない。
- 個人情報・実在企業情報をデモやログに残さない。認証情報を設定に保存しない。

## ファイルの読み分け

| 場面 | 読むファイル |
|---|---|
| 初期設定の質問・確認 | `references/setup-guide.md` |
| 設定変更 | `references/customization-guide.md` |
| 入力形式の確認 | `references/input-schema.md` |
| KPIの定義 | `references/standard-kpi.md` |
| サマリーの分析 | `references/analysis-rules.md` |
| サマリーの文章 | `references/writing-rules.md` |
| スライド構成 | `references/slide-structure.md` |
| 検証項目 | `references/validation-rules.md` |
| エラー時の判断 | `references/error-handling.md` |

## スクリプトの実行順

1. `run_report.py`（内部で normalize → calculate_kpi → validate → generate_summary_input を順に実行）
2. Claudeがサマリー作成（人が確認）
3. `run_report.py ... --make-pptx`（内部で generate_pptx）
4. 設定検証は `validate_settings.py`

個別に動かす場合は各スクリプトを `--help` で確認（すべてCLI・引数でパス指定・日本語ログ）。
