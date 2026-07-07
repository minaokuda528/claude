# -*- coding: utf-8 -*-
"""form_results.json を読み、整形済み_診断サイト受託 シートの各row行の
L(アプローチ方法)/M(ステータス)/N(対応日)/O(エラー内容)/Q(担当者) 列を更新する。

- 記録するのは「人間が手動で送信した／手動行きにした」結果。自動送信はしない。
- 更新のみ（values.batchUpdate）。他列・他行・他シートには触れない。
- デフォルト dry-run。--apply で実書き込み。

環境変数で上書き可:
  LC_SHEET_ID / LC_SHEET_NAME / LC_SA_KEY / LC_RESULTS

使い方: python write_back.py [--apply]
"""
from __future__ import annotations
import argparse, json, os
from pathlib import Path
import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

SHEET_ID = os.environ.get("LC_SHEET_ID", "1J748-Kt8OOxlOh6iEfLv6Viya9nuzBB1xVsZ38jZdS0")
SHEET_NAME = os.environ.get("LC_SHEET_NAME", "整形済み_診断サイト受託")
KEY = Path(os.environ.get("LC_SA_KEY", "C:/Users/OkudaMina/.secrets/lovechara-sa.json"))
RESULTS = Path(os.environ.get("LC_RESULTS", "form_results.json"))
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    creds = service_account.Credentials.from_service_account_file(str(KEY), scopes=SCOPES)
    creds.refresh(Request())
    tok = creds.token
    base = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}"
    q = f"'{SHEET_NAME}'"

    data = []
    for r in results:
        row = r["row"]
        tanto = r.get("担当者") or r.get("tantosha") or "奥田さん"
        data.append({"range": f"{q}!L{row}:M{row}",
                     "values": [[r.get("approach", ""), r.get("status", "")]]})
        data.append({"range": f"{q}!N{row}:O{row}",
                     "values": [[r.get("taiobi", ""), r.get("error", "")]]})
        data.append({"range": f"{q}!Q{row}", "values": [[tanto]]})

    print(f"対象 {len(results)} 行 / 更新レンジ {len(data)}")
    for r in results:
        err = (r.get("error") or "")[:40]
        print(f"  row {r['row']}: L={r.get('approach')} M={r.get('status')} "
              f"N={r.get('taiobi')} O={err} Q={r.get('担当者') or '奥田さん'}")
    if not args.apply:
        print("\n[DRY-RUN] --apply を付けると書き込みます。")
        return

    body = {"valueInputOption": "USER_ENTERED", "data": data}
    resp = requests.post(f"{base}/values:batchUpdate",
                         headers={"Authorization": f"Bearer {tok}",
                                  "Content-Type": "application/json"},
                         json=body)
    resp.raise_for_status()
    j = resp.json()
    print(f"\n[APPLIED] updatedCells={j.get('totalUpdatedCells')} "
          f"updatedRanges={len(j.get('responses', []))}")


if __name__ == "__main__":
    main()
