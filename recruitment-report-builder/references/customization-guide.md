# カスタマイズ・設定変更ガイド

初期設定後に設定を変更するときの手順（設定変更モード）。

## 変更前の共通ルール

- 既存の `company-settings.yaml` を必ずバックアップする（`company-settings.yaml.bak-YYYYMMDD-HHMMSS`）。
- 変更したい箇所だけを対話で確認し、他の項目は聞き直さない。
- 変更後に `scripts/validate_settings.py` で矛盾チェックを行う。
- 変更内容を要約して承認を得てから保存する。

## よくある変更

### 媒体を追加する
1. `media.registered` に正式名称を追加。
2. 表記揺れがあれば `media.aliases` に「入力名: 正式名称」を追加、または `media-mapping.csv` に行を追加。
3. その媒体の目標を設定する場合は目標データにも行を追加。

### KPIを追加・変更する
- `kpi.required` / `kpi.optional` に内部キーを追加。
- 内部キーの対応: 表示数=impressions, クリック数=clicks, 応募数=applications,
  面接数=interviews, 採用数=hires, 広告費=cost, クリック率=ctr, 応募率=application_rate,
  面接設定率=interview_rate, 採用率=hire_rate, クリック単価=cpc, 応募単価=cpa, 採用単価=cph。
- 単価・率を必須にする場合、その計算に必要な実数（例: cpa には applications と cost）を
  取得している必要がある（矛盾チェックで確認）。

### スライドを増減する
- `report.slides` のリストから不要なキーを削除、または並べ替え。
- キー一覧は `report-settings-template.yaml` を参照。

### 見た目を変える
- `report.brand_color`: 会社の色を16進で（例: "#C8102E"）。表・グラフ・見出しに反映。
- `report.logo`: ロゴファイル名（初期版は差し替え枠のみ）。
- `report.tone`: 文体。`report.summary_length`: short / standard / long。

### 判定基準を変える
- `thresholds.*` を編集（好調・注意・改善優先・警告の各基準）。
- 変更は次回のサマリー生成（`generate_summary_input.py`）から反映される。

### 使ってほしくない表現を追加する
- `analysis.avoid_expressions` に語句を追加。

## 会社ごとにファイルを分ける

- 会社別に `settings/<会社名>/company-settings.yaml` を作成し、実行時に `--settings` で指定する。
- 1つの設定を別会社へ流用する場合は、`company.name`・`media`・目標・`brand_color` を必ず見直す。
- **特定企業専用の値を他社設定へ残さない**（会社名・目標・色）。

## 変更してはいけないこと

- 認証情報（媒体のID/パスワード）を設定へ書かない。
- 個人情報（応募者氏名など）を設定・デモ・ログへ残さない。
