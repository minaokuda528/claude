#!/usr/bin/env python3
"""CSVから調査対象行を抽出する。

公式サイトURL列(または会社名列)を手がかりに問い合わせフォームURLを調べる対象を絞り込む。
行番号は「元CSVの行番号(ヘッダー=1行目, データ先頭=2)」で出力する。

使い方の例:
  # 「公式URL」があり「問い合わせフォームURL」が空欄、かつ「対応日」が空欄の行を抽出
  python extract_targets.py input.csv \
      --url-col 公式URL --name-col 会社名 \
      --nonempty 公式URL --empty 問い合わせフォームURL --empty 対応日 \
      --out targets.csv

  # 会社名だけで全行対象(条件なし)
  python extract_targets.py input.csv --name-col 会社名 --out targets.csv

列は名前(ヘッダー文字列)または 0 始まりの番号で指定できる。
"""
import argparse, csv, sys


def resolve_col(header, key):
    """列指定を 0 始まりのインデックスに解決。名前・番号どちらも可。"""
    if key is None:
        return None
    if key.isdigit():
        return int(key)
    for i, h in enumerate(header):
        if h.strip() == key.strip():
            return i
    raise SystemExit(f"列が見つかりません: {key!r} / ヘッダー: {header}")


def cell(row, idx):
    return row[idx].strip() if (idx is not None and idx < len(row)) else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("--encoding", default="utf-8-sig",
                    help="入力の文字コード(既定 utf-8-sig。Excel由来は cp932 も試す)")
    ap.add_argument("--url-col", help="公式サイトURL列(名前 or 番号)")
    ap.add_argument("--name-col", help="会社名/店舗名列(名前 or 番号)")
    ap.add_argument("--nonempty", action="append", default=[],
                    help="この列が非空の行のみ対象(複数可)")
    ap.add_argument("--empty", action="append", default=[],
                    help="この列が空欄の行のみ対象(複数可)")
    ap.add_argument("--out", default="targets.csv")
    args = ap.parse_args()

    rows = list(csv.reader(open(args.input, encoding=args.encoding)))
    if not rows:
        raise SystemExit("入力が空です")
    header = rows[0]

    url_i = resolve_col(header, args.url_col)
    name_i = resolve_col(header, args.name_col)
    nonempty_i = [resolve_col(header, k) for k in args.nonempty]
    empty_i = [resolve_col(header, k) for k in args.empty]

    out = []
    for n, row in enumerate(rows[1:], start=2):  # 元CSVの行番号
        if any(not cell(row, i) for i in nonempty_i):
            continue
        if any(cell(row, i) for i in empty_i):
            continue
        name = cell(row, name_i)
        url = cell(row, url_i)
        if url_i is not None and not url:
            # 公式URL列を条件にしていないが、URLも名前も無ければスキップ
            if not name:
                continue
        out.append((n, name, url))

    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["行番号", "会社名/店舗名", "公式URL"])
        w.writerows(out)

    print(f"抽出 {len(out)} 件 -> {args.out}")
    for r in out[:20]:
        print(*r, sep=" | ")
    if len(out) > 20:
        print(f"... 他 {len(out) - 20} 件")


if __name__ == "__main__":
    main()
