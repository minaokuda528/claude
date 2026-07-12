# contact-form-finder

企業・店舗リスト(CSV)の各行について、公式サイトURLまたは会社名から
問い合わせフォーム(お問い合わせ/contact)ページのURLを調査して補完する Claude Code スキル。

- `SKILL.md` … スキル本体(手順・判定ルール・制約)
- `scripts/extract_targets.py` … CSVから条件抽出(公式URLあり・フォームURL空欄 等)
- `scripts/append_results.py` … 調査結果を results.csv へ逐次追記(中断-再開用)
- `scripts/build_output.py` … 調査結果CSV / 記入用CSV(未特定は指定値。例 `ー`)を生成

呼び出し例(チャット): 「この会社リストCSVを渡すので、公式URLから問い合わせフォームURLを探して」

調査は Web 検索ベースで、Google スプレッドシートへの直接書き込みには
書き込み対応コネクタか Claude in Chrome が必要(詳細は SKILL.md)。
