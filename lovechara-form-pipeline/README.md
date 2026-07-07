# lovechara-form-pipeline（送信は人間が押す版）

問い合わせフォーム営業の**下書き生成・フォーム解析・フォーム自動入力**までをClaude/スクリプトが行い、
**最後の送信ボタンは必ず人間が1社ずつ自分で押す**ワークフロー。

> このパイプラインには「一括承認したらボットが自動一斉送信する」経路は含まれていません。
> 無人・承認なしの自動送信、および `--submit` によるボット送信は意図的に実装していません。

## セットアップ

```bash
pip install playwright==1.61.0 google-auth==2.55.1 requests==2.34.2
python -m playwright install chromium
cp sender_profile.example.json sender_profile.json   # 中身を実データに書き換え（TODOを消す）
```

環境変数（任意・パスを変える場合）:

| 変数 | 意味 | 既定値 |
|---|---|---|
| `LC_SHEET_ID` | スプレッドシートID | 手順書のID |
| `LC_SHEET_NAME` | シート名 | 整形済み_診断サイト受託 |
| `LC_SA_KEY` | サービスアカウント鍵パス | `C:/Users/OkudaMina/.secrets/lovechara-sa.json` |
| `LC_RESULTS` | 結果JSONパス | `form_results.json` |

Windowsコンソールは文字化け対策で常に `PYTHONIOENCODING=utf-8` を付けて実行。

## 使い方（1バッチの流れ）

1. **対象抽出**（送信しない）
   `PYTHONIOENCODING=utf-8 python read_diag_sheet.py 10`
   → `diag_candidates.json` に未対応＋URL有りの企業が出る。

2. **フォーム解析**（送信しない）
   `PYTHONIOENCODING=utf-8 python pw_form.py inspect <url>`
   → CAPTCHA・営業NG文言・項目一覧を確認。CAPTCHA/営業NG/判断不能は「手動行き」に振り分け。

3. **文面と入力マッピングの用意**
   `messages.json` の本文_奥田を使い、各社の `map_<row>.json` を作る。
   `PYTHONIOENCODING=utf-8 python pw_form.py fill <url> map_<row>.json`（headlessで入力プレビュー、送信なし）で内容確認。

4. **人間が送信**
   `PYTHONIOENCODING=utf-8 python pw_form.py prepare <url> map_<row>.json`
   → 画面付きブラウザが開き、入力済みの状態で待機する。
     内容を目視確認し、**あなた自身がサイトの送信ボタンを押す**。
     送信後、コンソールで Enter を押すとブラウザが閉じる。

5. **結果記録**
   人間が送信した／手動行きにした結果を `form_results.json` に書き、
   `PYTHONIOENCODING=utf-8 python write_back.py`（dry-run）→ 確認後 `--apply` でシートに反映。

## ファイル

| ファイル | 役割 |
|---|---|
| `read_diag_sheet.py` | シート→対象リスト抽出（送信なし） |
| `pw_form.py` | inspect(解析)/fill(入力プレビュー)/prepare(入力して人間が送信) |
| `write_back.py` | 結果をシートL/M/N/O/Q列へ反映（dry-run既定） |
| `sender_profile.example.json` | 送信者情報テンプレート（実データは sender_profile.json、コミット禁止） |
| `messages.json` | 営業軸×業界カテゴリ→件名・本文（別途配置） |
