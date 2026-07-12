#!/usr/bin/env python3
"""results.csv と 元CSV(targets) から最終成果物を生成する。

生成物:
  1) 調査結果CSV : 行番号 / 会社名 / 公式URL / 問い合わせフォームURL / 備考
  2) 記入用CSV   : 行番号 / 会社名 / H列に入れる値
     (見つからなかった行は --not-found の値。既定は空欄。例: --not-found ー)

使い方:
  python build_output.py --targets targets.csv --results results.csv \
      --out-detail 調査結果.csv --out-fill 記入用.csv --not-found ー
"""
import argparse, csv, os


def load_map(path, key=0):
    m = {}
    if path and os.path.exists(path):
        for r in csv.reader(open(path, encoding="utf-8-sig")):
            if r and r[0].isdigit():
                m[int(r[0])] = r
    return m


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--targets", help="extract_targets.py の出力(公式URL付き)")
    ap.add_argument("--results", default="results.csv")
    ap.add_argument("--out-detail", default="調査結果.csv")
    ap.add_argument("--out-fill", default="記入用.csv")
    ap.add_argument("--not-found", default="",
                    help="フォームURLが無い行のH列値(既定 空欄。例: ー)")
    args = ap.parse_args()

    tgt = load_map(args.targets)      # 行番号 -> [行番号, 会社名, 公式URL]
    res = load_map(args.results)      # 行番号 -> [行番号, 会社名, フォーム, 備考]

    rownums = sorted(set(tgt) | set(res))

    with open(args.out_detail, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["行番号", "会社名/店舗名", "公式URL", "問い合わせフォームURL", "備考"])
        for n in rownums:
            name = (res.get(n) or tgt.get(n) or [None, ""])[1]
            official = tgt.get(n, ["", "", ""])[2]
            form = res.get(n, ["", "", "", ""])[2] if n in res else ""
            note = res.get(n, ["", "", "", ""])[3] if n in res else ""
            w.writerow([n, name, official, form, note])

    filled = 0
    with open(args.out_fill, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["行番号", "会社名/店舗名", "H列(問い合わせフォームURL)に記入する値"])
        for n in rownums:
            name = (res.get(n) or tgt.get(n) or [None, ""])[1]
            form = res.get(n, ["", "", "", ""])[2] if n in res else ""
            val = form.strip() if form.strip() else args.not_found
            if form.strip():
                filled += 1
            w.writerow([n, name, val])

    print(f"対象 {len(rownums)} 件 / フォームURL {filled} 件 / 無し {len(rownums) - filled} 件")
    print(f"  調査結果 -> {args.out_detail}")
    print(f"  記入用   -> {args.out_fill}  (未特定は {args.not_found!r})")


if __name__ == "__main__":
    main()
