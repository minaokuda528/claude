---
name: lovechara-form-send
description: ラブキャラのフォーム営業を支援する。キューから企業を取り出し、Claudeが問い合わせフォームを解析・入力（下書き）まで行い、送信ボタンは人間が1社ずつ自分で押す。「フォーム営業を進めて」「/lovechara-form-send」で起動。
---

# lovechara-form-send — フォーム営業支援（送信は人間が押す）

## 大原則（絶対に守る）

1. **Claudeは送信ボタンを押さない。** 各社の最終送信は必ず人間が `pw_form.py prepare` の実ブラウザ上で自分でクリックする。
2. **一括承認による自動一斉送信は行わない。** 「1回OKしたらあとはボットが全部submit」という運用は禁止。承認は送信ではなく、あくまで下書きの確認まで。
3. **CAPTCHA検出フォームは入力・送信を試みず**、即「手動で実施必要」に振り分けて次へ。
4. **営業お断りの明記を発見 → 入力せず**「対象外／営業NG明記」で記録して次へ。
5. 項目名が無ラベル(ext_XX等)で意味判断不能、送信ボタンがhidden/JS制御 → 憶測で埋めず「手動で実施必要」。
6. `sender_profile.json` に TODO が残っていれば開始前に停止して確認。
7. 二重送信防止: 開始前にステータスが「未対応」のままか確認する。

## 実行方式

- Playwright（Python）を使う。作業ディレクトリは `lovechara-form-pipeline/`。
- `pw_form.py inspect <url>` … 解析（CAPTCHA/営業NG/項目一覧）。送信しない。
- `pw_form.py fill <url> map.json` … headlessで入力プレビュー(filled.png)。送信しない。
- `pw_form.py prepare <url> map.json` … 画面付きで入力し待機。**人間が送信ボタンを押す。**
- Pythonは常に `PYTHONIOENCODING=utf-8` で実行。

## 実行フロー

### Step 0: 準備
1. `sender_profile.json` を読み、TODOが残っていれば停止して確認。
2. `python read_diag_sheet.py 10` で対象抽出（未対応＋URL有り、デフォルト10社）。
3. 抽出したキューをユーザーに一覧提示する。

### Step 1: フォーム解析（1社ずつ）
`pw_form.py inspect <url>` で解析。以下は入力せず手動行き/対象外に振り分け:
- 404・フォーム消滅 → `エラー／フォームURL無効`
- CAPTCHA検出 → `エラー／CAPTCHA検出のため手動で実施必要`
- 営業お断り明記 → `対象外／営業NG明記`
- 無ラベル項目・hidden送信ボタン → `エラー／(理由)。手動で実施必要`

### Step 2: 文面
- 件名・本文 = `messages.json[営業軸][業界カテゴリ]`、本文は常に `本文_奥田`。
- カテゴリが無ければ同じ営業軸内で最も近いものを選び、その旨を明示。

### Step 3: 入力マッピング（map_<row>.json 生成）
DOMの項目(label/name/type/required/選択肢)を読み、以下で埋める:

| 項目パターン | 値 |
|---|---|
| 会社名・貴社名 | profile.会社名 |
| 部署 | profile.部署 |
| 氏名（1欄） | 担当者.氏名 ／ 姓名別欄は 姓/名 |
| ふりがな/フリガナ | ひらがな・カタカナを指定に合わせる |
| メール・確認用メール | **必ず profile.「送信メールアドレス（固定・必須）」**（個人アドレス不可） |
| 電話 | 担当者.電話（ハイフン不可なら数字のみ、3分割は分割） |
| 郵便番号・住所 | profile.住所（分割欄は対応部分のみ） |
| 件名 | messages の件名 |
| 本文 | messages の本文（改行維持、字数制限は署名から削る） |
| 種別(select/radio) | 「業務提携」「協業」「取材・コラボ」優先、なければ「その他」 |
| 連絡方法 | メール |
| 予算・時期 | 「未定」「検討中」相当 |
| 個人情報同意 | チェックする |
| メルマガ購読 | チェックしない |
| 判断不能な必須項目 | そのフォームは手動行きにし理由を記録（憶測で埋めない） |

`submit_selector` / `confirm_selector` は書かない（送信は人間が行うため）。

### Step 4: 確認と送信
1. `pw_form.py fill <url> map_<row>.json` で filled.png を作り、入力内容をユーザーに提示。
2. ユーザーが内容を確認してよいと言ったら `pw_form.py prepare <url> map_<row>.json` を案内する。
   → **画面付きブラウザで、ユーザー自身が送信ボタンを押す。**
3. Claudeが代わりにsubmitすることはしない。CAPTCHAや2段階確認も人間が画面上で対応する。

### Step 5: 結果記録
1. 各社の結果（送信済み／手動行き／対象外）を `form_results.json` に蓄積。
   - status/approach=フォーム候補/taiobi=フォーム送信：YYYY/MM/DD HH:MM/error
2. `write_back.py`（dry-run）で確認 → `write_back.py --apply` でシートのL/M/N/O/Q列を更新。
3. サマリー: 送信N件／手動行きN件／対象外N件と特記事項を報告。

## 運用ルール
- 1バッチ=10社目安。無人の定期自動送信タスクは作らない。
- 同日再実行時は form_results.json とシートのステータスで処理済みを除外し二重送信を防ぐ。
