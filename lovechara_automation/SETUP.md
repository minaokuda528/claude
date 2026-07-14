# LoveChara 問い合わせフォームURL自動追記バッチ — セットアップ指示書

このドキュメントは Claude Code に**そのまま渡して**実行してもらうための手順書です。目的は、Googleスプレッドシート上の「問い合わせフォームURL(H列)」を、公式URL(G列)を元に自動で埋めるバッチを、この指示書と同じフォルダにある付属ファイルを使って新しい環境に再現することです。

Claude Codeへ: 以下を順番に実行してください。各ステップの前提が満たせない場合は、そこで止めてユーザーに確認してください。

---

## 0. 付属ファイル(このSETUP.mdと同じフォルダにあります)

```
portable_setup/
├── SETUP.md                              ← このファイル
├── run_contact_form_gsheet_gh_only.py     ← 実行エントリポイント(そのままコピー)
├── scheduled-task-SKILL.md                ← スケジュールタスク定義のテンプレート
└── skill/
    └── scripts/
        ├── contact_form_runner.py         ← 本体ロジック(そのままコピー)
        ├── requirements.txt               ← Python依存パッケージ
        └── data/
            └── baseline_results.csv       ← 過去の調査結果キャッシュ(任意・下記参照)
```

## 1. 前提条件の確認

- Python 3.12以降がインストール済みであること(`python --version`)。
- インターネットアクセス可能であること(対象企業サイトをクロールするため)。
- 対象のGoogleスプレッドシートが存在し、列構成が以下と一致していること:
  - D列: 会社名
  - E列: 店舗名
  - G列: 公式URL
  - H列: 問い合わせフォームURL(書き込み対象)
  - 1行目はヘッダー、2行目以降がデータ

一致しない場合は `skill/scripts/contact_form_runner.py` 内の列定義(`row_cell(row, 4/5/6/7)` 等)を調整する必要があるので、その旨をユーザーに報告してください。

## 2. ファイル配置

以下のパスにコピーしてください(`$HOME` はこの環境のユーザーホーム):

| コピー元 | コピー先 |
|---|---|
| `run_contact_form_gsheet_gh_only.py` | `$HOME/Documents/Codex/lovechara_automation/run_contact_form_gsheet_gh_only.py` |
| `skill/scripts/contact_form_runner.py` | `$HOME/.codex/skills/lovechara-contact-url-csv-fill/scripts/contact_form_runner.py` |
| `skill/scripts/requirements.txt` | `$HOME/.codex/skills/lovechara-contact-url-csv-fill/scripts/requirements.txt` |
| `skill/scripts/data/baseline_results.csv` | `$HOME/.codex/skills/lovechara-contact-url-csv-fill/scripts/data/baseline_results.csv` |

ログ出力先ディレクトリも作成してください: `$HOME/Documents/Codex/lovechara_automation/logs`

**baseline_results.csv について:** これは元環境で過去に人手/AIが調査した「会社名→問い合わせフォームURL」の実績データです。同じ会社群を対象にするなら再利用価値がありますが、対象企業が全く異なるスプレッドシートの場合は空ファイル(ヘッダーのみ)から始めても構いません。ユーザーに確認してください。

## 3. Python依存パッケージのインストール

```bash
pip install -r skill/scripts/requirements.txt
```

内容: `beautifulsoup4==4.12.3` `gspread==6.1.2` `google-auth==2.32.0` `requests==2.32.3`

元環境では `$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe` という特定ランタイムのPythonを使っていましたが、これは元マシン固有のパスです。**新環境では、この環境で通常使うPython(システムPythonや専用venv)を使ってください。** 実行コマンド中の `python.exe` パスはその環境に合わせて読み替えます。

## 4. Google認証情報の準備(ユーザー対応が必要)

1. Google Cloud ConsoleでサービスアカウントJSONキーを発行し(Sheets APIを有効化)、
   `$HOME/.secrets/lovechara-sa.json` に配置する。
2. 対象スプレッドシートを開き、共有設定でそのサービスアカウントのメールアドレス(JSON内の `client_email`)を**編集者**として招待する。
3. サービスアカウントJSONは秘密情報のため、この指示書には含まれていません。**Claude自身がこのファイルの中身を生成・入力・送信することはありません。ユーザー本人に配置してもらってください。**

`run_contact_form_gsheet_gh_only.py` は `$HOME/.secrets/lovechara-sa.json` があれば自動でフォールバック使用するため、環境変数 `GOOGLE_APPLICATION_CREDENTIALS` の設定は不要です。

## 5. スプレッドシートIDの確認

`scheduled-task-SKILL.md` 内の以下2箇所は元環境の値です。**新環境の対象スプレッドシートに置き換えてください**:

```
--spreadsheet-id "1J748-Kt8OOxlOh6iEfLv6Viya9nuzBB1xVsZ38jZdS0"
--sheet-name "整形済み_診断サイト受託"
```

同じスプレッドシートを共有して使う場合はそのままで構いません。

## 6. 動作確認(dry-run)

書き込み前に必ず1回、`--dry-run` を付けて実行し、対象行の検出とURL特定ロジックが正しく動くか確認してください:

```bash
python run_contact_form_gsheet_gh_only.py \
  --spreadsheet-id "<対象スプレッドシートID>" \
  --sheet-name "<対象シート名>" \
  --baseline "$HOME/.codex/skills/lovechara-contact-url-csv-fill/scripts/data/baseline_results.csv" \
  --logs-dir "$HOME/Documents/Codex/lovechara_automation/logs" \
  --max-rows 5 \
  --dry-run
```

問題なければ `--dry-run` を外して少数件(`--max-rows 5`程度)で本番書き込みを試し、H列に正しく反映されるかスプレッドシート上で確認してください。

## 7. スケジュールタスクの登録

`scheduled-task-SKILL.md` の内容(スプレッドシートID/シート名を書き換えたもの)を使って、`mcp__scheduled-tasks__create_scheduled_task` でタスクを登録してください。元環境の設定は以下の通りです:

- タスク名: `lovechara-contact-url-batch`
- cron式: `0 12,15,18,21 * * *` (毎日12/15/18/21時、100件ずつ)
- 説明: 毎日12/15/18/21時にLoveChara問い合わせフォームURLを100件ずつ自動追記する

登録後、`mcp__scheduled-tasks__list_scheduled_tasks` で登録内容を確認してください。

## 8. 運用ルール(元環境と同一・変更禁止)

- 1回の実行は必ず `--max-rows 100`。増やさない。
- 対象: G列が非空かつH列が完全空欄の行を上から順に処理。
- フォームURLを特定できない行はH列に「ー」を書く(書き込み扱い)。
- 書き込み直前にH列を再確認し、値があればスキップ(runner組み込み済み)。
- 書き込み後の読み戻し検証もrunner組み込み済み。検証失敗でエラー停止した場合はエラー内容を報告するのみで、コードは修正しない。
- Google Sheets APIの読み取りクォータ(429エラー)に達した場合は、90秒程度待って同じコマンドを再実行する。書き込み済み行は自動スキップされるため二重書き込みは起きない。

## 9. 実行後の報告フォーマット(元環境と同一)

- 対象件数
- H列書き込み件数(URL件数 / ー件数の内訳)
- 処理範囲(runner出力の「Processed row range: X - Y」)
- ログファイルパス
- 処理範囲外の行は未処理であることを明記
