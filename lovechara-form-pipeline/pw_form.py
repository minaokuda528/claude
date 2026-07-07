# -*- coding: utf-8 -*-
"""Playwrightでお問い合わせフォームを解析・入力する（人間が送信ボタンを押す版）。

★このスクリプトは自動で送信(submit)しない。
  最後の送信操作は必ず人間が prepare モードの実ブラウザ上で自分で行う。
  一括承認による自動一斉送信の経路は意図的に持たせていない。

使い方:
  python pw_form.py inspect <url>
      → フォーム項目(label/name/type/required/options)・CAPTCHA有無・営業NG文言を
        JSONで出力し、スクリーンショットを pw_shots/inspect.png に保存（解析のみ）

  python pw_form.py fill <url> <mapping.json>
      → headlessで mapping 通りに入力し pw_shots/filled.png を保存（送信しない・確認用プレビュー）

  python pw_form.py prepare <url> <mapping.json>
      → 画面付き(headed)ブラウザを起動して mapping 通りに入力し、そのまま開いて待機する。
        入力内容を人間が目視で確認し、サイト上の送信ボタンを「自分で」クリックして送信する。
        送信し終えてコンソールで Enter を押すとブラウザを閉じる。
        ※Claudeやスクリプトが submit をクリックすることはない。

mapping.json 形式:
  {
    "fields": [{"selector": "...", "value": "...", "type": "fill|select|check"}]
  }
  （submit_selector / confirm_selector は使わない。送信は人間が行うため）
"""
from __future__ import annotations
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTDIR = Path(__file__).parent / "pw_shots"
OUTDIR.mkdir(exist_ok=True)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def open_page(p, url, headless=True):
    browser = p.chromium.launch(headless=headless)
    ctx = browser.new_context(user_agent=UA, locale="ja-JP",
                              viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.goto(url, timeout=45000, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    return browser, page


def inspect(url: str) -> None:
    with sync_playwright() as p:
        browser, page = open_page(p, url)
        fields = page.evaluate(r"""() => {
          const out = [];
          const els = document.querySelectorAll(
            'form input:not([type=hidden]), form textarea, form select');
          els.forEach(el => {
            let label = '';
            if (el.id) {
              const l = document.querySelector(`label[for="${el.id}"]`);
              if (l) label = l.textContent.trim();
            }
            if (!label) {
              const l = el.closest('label');
              if (l) label = l.textContent.trim().slice(0, 80);
            }
            if (!label) {
              const row = el.closest('tr, .form-group, p, dl, li, div');
              if (row) {
                const th = row.querySelector('th, dt, label, .label');
                if (th) label = th.textContent.trim().slice(0, 80);
              }
            }
            const o = {
              tag: el.tagName.toLowerCase(),
              type: el.type || '',
              name: el.name || '',
              id: el.id || '',
              placeholder: el.placeholder || '',
              required: el.required || false,
              label: label,
              maxlength: el.maxLength > 0 ? el.maxLength : null,
            };
            if (el.tagName === 'SELECT') {
              o.options = Array.from(el.options).map(x => x.text.trim()).slice(0, 30);
            }
            if (el.type === 'radio' || el.type === 'checkbox') {
              o.value = el.value;
            }
            out.push(o);
          });
          const btns = [];
          document.querySelectorAll(
            'form button, form input[type=submit], form input[type=button]')
            .forEach(b => btns.push({tag: b.tagName.toLowerCase(),
                                     type: b.type || '', name: b.name || '',
                                     text: (b.value || b.textContent || '').trim().slice(0, 40)}));
          const bodyText = document.body.innerText;
          const ngWords = ['営業目的', '営業のお問い合わせ', '営業・勧誘', 'セールスお断り', '営業お断り'];
          const ng = ngWords.filter(w => bodyText.includes(w));
          const captcha = !!document.querySelector(
            '.g-recaptcha, [class*=recaptcha], iframe[src*=recaptcha], iframe[src*=hcaptcha], [class*=captcha]');
          return {fields: out, buttons: btns, ngHits: ng, hasCaptcha: captcha,
                  title: document.title};
        }""")
        shot = OUTDIR / "inspect.png"
        page.screenshot(path=str(shot), full_page=True)
        fields["screenshot"] = str(shot)
        fields["finalUrl"] = page.url
        print(json.dumps(fields, ensure_ascii=False, indent=1))
        browser.close()


def _apply_fields(page, m):
    for f in m["fields"]:
        sel, val = f["selector"], f.get("value", "")
        kind = f.get("type", "fill")
        try:
            if kind == "fill":
                page.fill(sel, val, timeout=8000)
            elif kind == "select":
                page.select_option(sel, label=val, timeout=8000)
            elif kind == "check":
                page.check(sel, timeout=8000)
        except Exception as e:
            print(json.dumps({"fieldError": sel, "err": str(e)[:200]},
                             ensure_ascii=False))


def fill(url: str, mapping_path: str) -> None:
    """headlessで入力し、送信せずにスクリーンショットだけ保存（マッピング確認用）。"""
    m = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
    with sync_playwright() as p:
        browser, page = open_page(p, url, headless=True)
        _apply_fields(page, m)
        page.wait_for_timeout(800)
        shot = OUTDIR / "filled.png"
        page.screenshot(path=str(shot), full_page=True)
        print(json.dumps({"filledShot": str(shot),
                          "note": "送信していません。内容確認のみ。"},
                         ensure_ascii=False, indent=1))
        browser.close()


def prepare(url: str, mapping_path: str) -> None:
    """画面付きブラウザで入力し、開いたまま待機。送信は人間が手動で行う。"""
    m = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
    with sync_playwright() as p:
        browser, page = open_page(p, url, headless=False)
        _apply_fields(page, m)
        page.wait_for_timeout(500)
        print("―" * 50)
        print("フォームに入力しました。ブラウザ画面で内容を確認し、")
        print("問題なければ【あなた自身で】サイトの送信ボタンを押してください。")
        print("（このスクリプトは送信ボタンを押しません）")
        print("送信が完了したら、このコンソールで Enter を押すと閉じます。")
        print("―" * 50)
        try:
            input()
        except EOFError:
            page.wait_for_timeout(120000)
        browser.close()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "inspect":
        inspect(sys.argv[2])
    elif cmd == "fill":
        fill(sys.argv[2], sys.argv[3])
    elif cmd == "prepare":
        prepare(sys.argv[2], sys.argv[3])
    else:
        sys.exit("unknown command (use: inspect | fill | prepare)")
