# -*- coding: utf-8 -*-
"""整形済み_診断サイト受託 シートを読み、未対応かつフォームURL有りの企業を抽出する。

送信は一切行わない。対象リスト(diag_candidates.json)を作るだけのスクリプト。

環境変数で上書き可（Windows/別環境でパスを変えられるように）:
  LC_SHEET_ID   : 対象スプレッドシートID
  LC_SHEET_NAME : シート名
  LC_SA_KEY     : サービスアカウント鍵(JSON)のパス

使い方:
  PYTHONIOENCODING=utf-8 python read_diag_sheet.py [件数]   (省略時10件)
"""
import json, os, sys
from pathlib import Path
import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

SHEET_ID = os.environ.get("LC_SHEET_ID", "1J748-Kt8OOxlOh6iEfLv6Viya9nuzBB1xVsZ38jZdS0")
SHEET_NAME = os.environ.get("LC_SHEET_NAME", "整形済み_診断サイト受託")
KEY = Path(os.environ.get("LC_SA_KEY", "C:/Users/OkudaMina/.secrets/lovechara-sa.json"))
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

creds = service_account.Credentials.from_service_account_file(str(KEY), scopes=SCOPES)
creds.refresh(Request())
tok = creds.token

base = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}"
r = requests.get(f"{base}/values/{requests.utils.quote(SHEET_NAME)}",
                 headers={"Authorization": f"Bearer {tok}"},
                 params={"valueRenderOption": "FORMATTED_VALUE"})
r.raise_for_status()
values = r.json().get("values", [])
print("TOTAL ROWS (incl header):", len(values))
if not values:
    sys.exit("no data")
header = values[0]


def col_letter(i):
    s = ""
    i += 1
    while i:
        i, rem = divmod(i - 1, 26)
        s = chr(65 + rem) + s
    return s


print("HEADER (col index -> letter -> name):")
for i, h in enumerate(header):
    print(f"  [{i}] {col_letter(i)} : {h}")


def find(names):
    for i, h in enumerate(header):
        hn = (h or "").strip()
        for n in names:
            if n in hn:
                return i
    return None


url_c = find(["問い合わせフォームURL", "フォームURL", "問い合わせフォーム"])
l_c = find(["アプローチ方法"])
m_c = find(["ステータス"])
n_c = find(["対応日"])
o_c = find(["エラー内容"])
q_c = find(["担当者"])
comp_c = find(["企業名", "会社名", "運営会社"])
print("\nRESOLVED COLUMNS:")
for label, idx in [("フォームURL", url_c), ("L/アプローチ方法", l_c), ("M/ステータス", m_c),
                    ("N/対応日", n_c), ("O/エラー内容", o_c), ("Q/担当者", q_c), ("企業名", comp_c)]:
    print(f"  {label}: idx={idx} letter={col_letter(idx) if idx is not None else '?'}")


def cell(row, idx):
    return (row[idx].strip() if (idx is not None and idx < len(row) and row[idx] is not None) else "")


mitaio_total = 0
mitaio_with_url = 0
candidates = []  # 未対応 かつ URL有り
for ridx, row in enumerate(values[1:], start=2):
    status = cell(row, m_c)
    if status != "未対応":
        continue
    mitaio_total += 1
    url = cell(row, url_c)
    if url:
        mitaio_with_url += 1
        candidates.append({
            "row": ridx,
            "company": cell(row, comp_c),
            "url": url,
            "target": cell(row, 1),       # B ターゲット業界
            "category": cell(row, 2),     # C 業界カテゴリ
            "email": cell(row, 8),        # I メールアドレス
        })

batch_size = int(sys.argv[1]) if len(sys.argv) > 1 else 10
summary = {
    "mitaio_total": mitaio_total,
    "mitaio_with_url": mitaio_with_url,
    "first10": candidates[:batch_size],
}
out = Path("diag_candidates.json")
out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n未対応 total: {mitaio_total}")
print(f"未対応 かつ URL有り: {mitaio_with_url}")
print(f"wrote -> {out.resolve()}")
