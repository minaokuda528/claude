---
name: lovechara-contact-url-batch
description: 毎日12/15/18/21時にLoveChara問い合わせフォームURLを100件ずつ自動追記する
---

# LoveChara 問い合わせフォームURL自動追記バッチ（100件）

このタスクは、Googleスプレッドシート「整形済み_診断サイト受託」のH列（問い合わせフォームURL）を100件ずつ自動で埋める。手動実行（今すぐ実行）の場合も同じく100件。承認待ちは不要、完全自動で実行すること。

## 実行コマンド

Bashで以下を実行する（タイムアウトは600000msに設定）:

```bash
PY="$USERPROFILE/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"
SCRIPT="$USERPROFILE/Documents/Codex/lovechara_automation/run_contact_form_gsheet_gh_only.py"
SKILL="$USERPROFILE/.codex/skills/lovechara-contact-url-csv-fill"
LOGS="$USERPROFILE/Documents/Codex/lovechara_automation/logs"
PYTHONIOENCODING=utf-8 "$PY" "$SCRIPT" \
  --spreadsheet-id "1J748-Kt8OOxlOh6iEfLv6Viya9nuzBB1xVsZ38jZdS0" \
  --sheet-name "整形済み_診断サイト受託" \
  --baseline "$SKILL/scripts/data/baseline_results.csv" \
  --logs-dir "$LOGS" \
  --max-rows 100
```

10分でタイムアウトした場合は、そのまま同じコマンドをバックグラウンド（run_in_background）で再実行して完了を待つ。書き込み済み行は自動スキップされるので二重書き込みは起きない。

## 仕様（変更禁止）

- 1回の実行は必ず --max-rows 100。増やさない。リトライで100件を超えて処理しない。
- 対象: G列（公式URL）が非空かつH列が完全空欄の行を上から順に処理。N列は条件にしない。
- フォームURLを特定できない行はH列に「ー」が書かれる（これも書き込み扱い）。
- 書き込み直前にH列を再確認し、値がある行はスキップされる（runner組み込み済み）。
- 書き込み後の読み戻し検証はrunnerに組み込み済み。検証失敗でエラー停止した場合は、エラー内容を報告して手を加えずに終了する。
- runnerのコードを修正しない。エラーが出たら内容を報告するのみ。

## 認証

サービスアカウントJSON: `~/.secrets/lovechara-sa.json`（runner側でフォールバック設定済み。GOOGLE_APPLICATION_CREDENTIALSの設定は不要）

## 報告（簡潔に）

実行後、以下だけを報告する:
- 対象件数
- H列書き込み件数（URL件数 / ー件数の内訳）
- 処理範囲（runnerが出力する「Processed row range: X - Y」）
- ログファイルパス

処理範囲外の行は未処理であることを必ず明記する。対象行が0件（全行処理済み）の場合はその旨だけ報告する。
