#!/usr/bin/env python3
"""リストル 収集予約 自動処理ボット

収集予約一覧（照会）の予約を「下から順番」に処理する:
  収集実行（閾値2000件）→ CSV出力 → ダウンロード確認 → 確認できた予約のみ削除

安全原則:
  - CSVダウンロードが確認できない限り、予約は絶対に削除しない
  - 失敗した予約は削除せずログに記録して次へ進む
  - 収集中はポーリング間隔を守り、同じボタンを連打しない

実行モード:
  python3 listoru_bot.py --inspect   ログインして各画面のHTML/スクリーンショットを保存（処理はしない）
  python3 listoru_bot.py --dry-run   一覧の読み取り・照合まで実行（収集開始/CSV出力/削除はしない）
  python3 listoru_bot.py --run       本番実行

認証情報は環境変数 LISTORU_ID / LISTORU_PASSWORD で渡す（ファイルに保存しない）。
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE_DIR = Path(__file__).resolve().parent
CHROME_CANDIDATES = [
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
]


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Logger:
    def __init__(self, log_dir: Path):
        log_dir.mkdir(parents=True, exist_ok=True)
        self.path = log_dir / f"run_{datetime.now():%Y%m%d_%H%M%S}.log"
        self.records = []  # 予約ごとの処理記録

    def line(self, msg: str):
        text = f"[{now()}] {msg}"
        print(text, flush=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(text + "\n")

    def record(self, rec: dict):
        self.records.append(rec)
        block = (
            f"処理番号：{rec.get('no')}\n"
            f"処理開始時刻：{rec.get('start')}\n"
            f"収集サイト名：{rec.get('site')}\n"
            f"収集条件：{rec.get('condition')}\n"
            f"最大収集閾値：2000件\n"
            f"検索開始結果：{rec.get('search', '-')}\n"
            f"収集開始結果：{rec.get('collect', '-')}\n"
            f"収集完了結果：{rec.get('done', '-')}\n"
            f"CSV出力結果：{rec.get('csv', '-')}\n"
            f"CSVファイル名：{rec.get('csv_file', '-')}\n"
            f"予約削除結果：{rec.get('delete', '-')}\n"
            f"エラー・補足：{rec.get('note', '-')}\n"
        )
        self.line("---- 予約処理記録 ----\n" + block)

    def final_report(self):
        ok_csv = [r for r in self.records if r.get("csv") == "成功"]
        ok_del = [r for r in self.records if r.get("delete") == "成功"]
        skipped = [r for r in self.records if r.get("csv") != "成功" or r.get("delete") != "成功"]
        lines = [
            "==== 最終報告 ====",
            f"処理件数：{len(self.records)}",
            f"CSV出力成功件数：{len(ok_csv)}",
            f"削除成功件数：{len(ok_del)}",
            f"スキップ件数：{len(skipped)}",
            "スキップした予約の詳細：",
        ]
        for r in skipped:
            lines.append(f"  - #{r.get('no')} {r.get('site')} / {r.get('condition')} : {r.get('note')}")
        lines.append("ダウンロードされたCSVファイル一覧：")
        for r in ok_csv:
            lines.append(f"  - {r.get('csv_file')}")
        report = "\n".join(lines)
        self.line(report)
        return report


class ListoruBot:
    def __init__(self, config: dict, logger: Logger, mode: str):
        self.cfg = config
        self.log = logger
        self.mode = mode  # inspect / dry-run / run
        self.sel = config["selectors"]
        self.download_dir = BASE_DIR / config["download_dir"]
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.inspect_dir = BASE_DIR / "inspect"
        self.user_id = os.environ.get("LISTORU_ID", "")
        self.password = os.environ.get("LISTORU_PASSWORD", "")
        if not self.user_id or not self.password:
            sys.exit("環境変数 LISTORU_ID / LISTORU_PASSWORD を設定してください")

    # ---------- 低レベルヘルパー ----------

    def find(self, page, key, timeout=5000):
        """config.json の selectors[key] の候補を上から順に試し、最初に見つかった locator を返す"""
        candidates = self.sel[key]
        if isinstance(candidates, str):
            candidates = [candidates]
        for css in candidates:
            loc = page.locator(css).first
            try:
                loc.wait_for(state="visible", timeout=timeout)
                return loc
            except PWTimeout:
                continue
        return None

    def snapshot(self, page, name):
        self.inspect_dir.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(self.inspect_dir / f"{name}.png"), full_page=True)
        (self.inspect_dir / f"{name}.html").write_text(page.content(), encoding="utf-8")
        self.log.line(f"画面保存: inspect/{name}.png / .html")

    # ---------- 画面操作 ----------

    def login(self, page):
        page.goto(self.cfg["base_url"], wait_until="domcontentloaded", timeout=60000)
        id_box = self.find(page, "login_id")
        if id_box is None:
            # 既にログイン済みセッションの可能性
            self.log.line("ログインフォームが見つからないため、ログイン済みとみなします")
            return
        id_box.fill(self.user_id)
        self.find(page, "login_password").fill(self.password)
        self.find(page, "login_submit").click()
        page.wait_for_load_state("domcontentloaded")
        self.log.line("ログイン完了")

    def ensure_logged_in(self, page):
        """セッション切れなら再ログイン"""
        if self.find(page, "login_password", timeout=1500) is not None:
            self.log.line("セッション切れを検出。再ログインします")
            self.login(page)

    def open_reservation_list(self, page):
        link = self.find(page, "menu_reservation_list", timeout=10000)
        if link is None:
            raise RuntimeError("メニュー『収集予約一覧（照会）』が見つかりません")
        link.click()
        page.wait_for_load_state("domcontentloaded")
        self.ensure_logged_in(page)

    def read_reservations(self, page):
        """一覧の行を上から順に [{index, site, condition, row}] で返す"""
        rows = page.locator(self.sel["reservation_rows"][0])
        items = []
        for i in range(rows.count()):
            row = rows.nth(i)
            cells = row.locator("td")
            texts = [cells.nth(j).inner_text().strip() for j in range(cells.count())]
            # 想定: どこかのセルにサイト名、どこかに条件。--inspect の結果で列番号を確定させる
            items.append({"index": i, "cells": texts, "row": row})
        return items

    @staticmethod
    def site_and_condition(item):
        """行セルからサイト名・条件を取り出す。--inspect の結果で列番号を調整すること"""
        cells = item["cells"]
        site = cells[0] if len(cells) > 0 else ""
        condition = cells[1] if len(cells) > 1 else ""
        return site, condition

    # ---------- 予約1件の処理 ----------

    def process_one(self, page, no, site, condition):
        rec = {"no": no, "start": now(), "site": site, "condition": condition}
        try:
            # 収集実行画面へ
            self.find(page, "menu_collect", timeout=10000).click()
            page.wait_for_load_state("domcontentloaded")

            # 収集サイト・条件・閾値を設定
            site_sel = self.find(page, "collect_site_select")
            if site_sel is None:
                raise RuntimeError("収集サイト選択が見つかりません")
            site_sel.select_option(label=site)
            cond = self.find(page, "collect_condition_input", timeout=3000)
            if cond is not None and condition:
                cond.fill(condition)
            th = self.find(page, "threshold_input")
            if th is None:
                raise RuntimeError("最大収集閾値の入力欄が見つかりません")
            th.fill(str(self.cfg["max_threshold"]))

            if self.mode != "run":
                rec["note"] = "dry-run: 設定確認まで実行（検索開始以降はスキップ）"
                self.log.record(rec)
                return rec

            # 検索開始（1回だけ）
            self.find(page, "search_start_button").click()
            rec["search"] = "成功"
            self.log.line(f"#{no} 検索開始をクリック。{self.cfg['wait_after_search_start_sec']}秒待機")
            time.sleep(self.cfg["wait_after_search_start_sec"])

            # 収集開始（最大3回リトライ）
            started = False
            for attempt in range(1, self.cfg["collect_start_retry_max"] + 1):
                btn = self.find(page, "collect_start_button", timeout=5000)
                if btn is not None and btn.is_enabled():
                    btn.click()
                    started = True
                    rec["collect"] = "成功"
                    break
                self.log.line(f"#{no} 収集開始ボタン不可 (試行{attempt}) — {self.cfg['collect_start_retry_interval_sec']}秒待機")
                time.sleep(self.cfg["collect_start_retry_interval_sec"])
            if not started:
                rec["collect"] = "収集開始不可"
                rec["note"] = "収集開始不可のためスキップ（削除しない）"
                self.log.record(rec)
                return rec

            # 収集完了待ち: 15分待機 → 5分間隔 → 最大60分
            self.log.line(f"#{no} 収集開始。まず{self.cfg['initial_wait_before_first_check_sec']//60}分待機します")
            time.sleep(self.cfg["initial_wait_before_first_check_sec"])
            waited = self.cfg["initial_wait_before_first_check_sec"]
            csv_btn = None
            while waited <= self.cfg["max_wait_total_sec"]:
                btn = self.find(page, "csv_export_button", timeout=5000)
                if btn is not None and btn.is_enabled():
                    csv_btn = btn
                    break
                collecting = self.find(page, "collecting_indicator", timeout=2000)
                self.log.line(f"#{no} まだ収集中（経過{waited//60}分, 収集中表示={'有' if collecting else '無'}）")
                time.sleep(self.cfg["check_interval_sec"])
                waited += self.cfg["check_interval_sec"]
            if csv_btn is None:
                rec["done"] = "収集完了タイムアウト"
                rec["note"] = "60分以内に完了せずスキップ（削除しない）"
                self.log.record(rec)
                return rec
            rec["done"] = "成功"

            # CSV出力
            csv_btn.click()
            page.wait_for_load_state("domcontentloaded")
            boxes = page.locator(self.sel["csv_checkboxes"][0])
            for i in range(boxes.count()):
                box = boxes.nth(i)
                if not box.is_checked():
                    box.check()
            # 未チェックが残っていないことを確認
            for i in range(boxes.count()):
                if not boxes.nth(i).is_checked():
                    raise RuntimeError("未チェックのCSV項目が残っています")

            with page.expect_download(timeout=120000) as dl_info:
                self.find(page, "csv_execute_button").click()
            download = dl_info.value
            fname = download.suggested_filename
            dest = self.download_dir / fname
            download.save_as(str(dest))
            if dest.stat().st_size == 0:
                raise RuntimeError(f"CSVファイルが0KBです: {fname}")
            rec["csv"] = "成功"
            rec["csv_file"] = fname
            self.log.line(f"#{no} CSVダウンロード完了: {fname} ({dest.stat().st_size} bytes)")

            # 削除: CSV確認済みの場合のみ
            self.delete_reservation(page, no, site, condition, rec)

        except Exception as e:
            rec.setdefault("note", "")
            rec["note"] = (rec["note"] + f" エラー: {e}").strip()
            if rec.get("csv") != "成功":
                rec["delete"] = "実施せず（CSV未確認のため削除禁止）"
        self.log.record(rec)
        return rec

    def delete_reservation(self, page, no, site, condition, rec):
        """CSVダウンロード確認済みの予約のみ削除。一致行のうち一番下を対象にする"""
        self.open_reservation_list(page)
        items = self.read_reservations(page)
        target = None
        for item in items:  # 上から走査し、最後に一致したもの＝一番下の一致行
            s, c = self.site_and_condition(item)
            if s == site and c == condition:
                target = item
        if target is None:
            rec["delete"] = "失敗"
            rec["note"] = "削除対象行が一覧に見つかりません（手動確認要）"
            return
        # 削除直前の再照合
        s, c = self.site_and_condition(target)
        if s != site or c != condition:
            rec["delete"] = "失敗"
            rec["note"] = "削除直前の照合に失敗（削除中止）"
            return
        page.once("dialog", lambda d: d.accept())
        target["row"].locator(self.sel["row_delete_button"][0]).first.click()
        page.wait_for_load_state("domcontentloaded")
        # 削除後の確認: 同一 site/condition の行数が1減っていること
        after = self.read_reservations(page)
        before_n = sum(1 for i in items if self.site_and_condition(i) == (site, condition))
        after_n = sum(1 for i in after if self.site_and_condition(i) == (site, condition))
        rec["delete"] = "成功" if after_n == before_n - 1 else "失敗"
        self.log.line(f"#{no} 削除{'成功' if rec['delete']=='成功' else '失敗'} ({before_n}→{after_n}件)")

    # ---------- メインループ ----------

    def run(self):
        with sync_playwright() as p:
            exe = next((c for c in CHROME_CANDIDATES if Path(c).exists()), None)
            browser = p.chromium.launch(headless=True, executable_path=exe)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            self.login(page)

            if self.mode == "inspect":
                self.snapshot(page, "01_after_login")
                try:
                    self.open_reservation_list(page)
                    self.snapshot(page, "02_reservation_list")
                except Exception as e:
                    self.log.line(f"一覧画面の取得に失敗: {e}")
                try:
                    link = self.find(page, "menu_collect", timeout=5000)
                    if link:
                        link.click()
                        page.wait_for_load_state("domcontentloaded")
                        self.snapshot(page, "03_collect_page")
                except Exception as e:
                    self.log.line(f"収集実行画面の取得に失敗: {e}")
                browser.close()
                return

            no = 0
            skipped = {}  # (site, condition) -> この実行内でスキップした件数
            while True:
                self.open_reservation_list(page)
                items = self.read_reservations(page)
                if not items:
                    self.log.line("収集予約一覧が空になりました。処理を終了します")
                    break
                # 下から順に、まだスキップ扱いになっていない行を選ぶ
                target = None
                seen = {}
                for item in reversed(items):
                    key = self.site_and_condition(item)
                    seen[key] = seen.get(key, 0) + 1
                    if seen[key] > skipped.get(key, 0):
                        target = item
                        break
                if target is None:
                    self.log.line("残っている予約はすべてスキップ済みです。処理を終了します")
                    break
                site, condition = self.site_and_condition(target)
                no += 1
                self.log.line(f"#{no} 処理対象（{len(items)}件中 下から{seen[(site, condition)]}番目の一致行）: {site} / {condition}")
                rec = self.process_one(page, no, site, condition)
                if self.mode != "run":
                    self.log.line("dry-run のため1件で終了します")
                    break
                if rec.get("delete") != "成功":
                    if rec.get("csv") == "成功":
                        # CSVは取れたが削除に失敗: 二重処理を避けるため停止して手動確認
                        self.log.line("削除に失敗しました。同一予約の再処理を避けるため停止します（要手動確認）")
                        break
                    key = (site, condition)
                    skipped[key] = skipped.get(key, 0) + 1
                    self.log.line("この予約は削除せずスキップし、次の予約へ進みます")
            browser.close()
            print("\n" + self.log.final_report())


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--inspect", action="store_true", help="画面構造の調査のみ")
    g.add_argument("--dry-run", action="store_true", help="読み取り・照合のみ（収集/削除しない）")
    g.add_argument("--run", action="store_true", help="本番実行")
    args = ap.parse_args()
    mode = "inspect" if args.inspect else ("dry-run" if args.dry_run else "run")

    config = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))
    logger = Logger(BASE_DIR / config["log_dir"])
    logger.line(f"=== listoru_bot 開始 (mode={mode}) ===")
    ListoruBot(config, logger, mode).run()


if __name__ == "__main__":
    main()
