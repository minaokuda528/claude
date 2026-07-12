#!/usr/bin/env python3
"""調査結果を results.csv に1件追記する(バッチごとに逐次保存して中断-再開可能にする)。

列: 行番号, 会社名, 問い合わせフォームURL, 備考

使い方:
  python append_results.py --row 92 --name "MTK SHOP" \
      --form "https://mitsukin.info/inquiry/" --note "運営:三金商事。個人向けは /inquiry/individual/"

  # フォームが見つからない場合は --form を空(または省略)にし、備考に代替連絡先を書く
  python append_results.py --row 94 --name "mucstore" --note "運営:MUC株式会社。独立フォームなし(楽天メッセージ経由)"

同じ行番号が既にあれば上書き更新する。
"""
import argparse, csv, os

FILE = "results.csv"
HEADER = ["行番号", "会社名", "問い合わせフォームURL", "備考"]


def load(path):
    rows = {}
    if os.path.exists(path):
        for r in csv.reader(open(path, encoding="utf-8-sig")):
            if r and r[0].isdigit():
                rows[int(r[0])] = r
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", default=FILE)
    ap.add_argument("--row", type=int, required=True, help="元CSVの行番号")
    ap.add_argument("--name", default="")
    ap.add_argument("--form", default="", help="問い合わせフォームURL(無ければ空)")
    ap.add_argument("--note", default="", help="備考(メール・電話・注意点など)")
    args = ap.parse_args()

    rows = load(args.file)
    rows[args.row] = [str(args.row), args.name, args.form, args.note]

    with open(args.file, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for k in sorted(rows):
            w.writerow(rows[k])

    got = sum(1 for r in rows.values() if r[2].strip())
    print(f"記録 {len(rows)} 件(URLあり {got} / なし {len(rows) - got}) -> {args.file}")


if __name__ == "__main__":
    main()
