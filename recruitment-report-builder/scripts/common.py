"""共通ユーティリティ（設定読込・数値正規化・ログ）。

対応Pythonバージョン: 3.10以上
"""
from __future__ import annotations

import logging
import sys
import unicodedata
from pathlib import Path

import pandas as pd
import yaml

# 特殊値（docs/system-design.md §5）
NA = "N/A"          # 0除算・欠損により算出不可
NEW = "NEW"         # 前月データなし
NOT_SET = "NOT_SET" # 目標未設定

# 列名の表記揺れ → 内部キー（デフォルト。会社設定 column_aliases で拡張可能）
DEFAULT_COLUMN_ALIASES: dict[str, str] = {
    "媒体": "media", "媒体名": "media", "メディア": "media",
    "職種": "job_category", "職種名": "job_category",
    "拠点": "location", "勤務地": "location", "エリア": "location",
    "対象期間": "period", "期間": "period", "年月": "period",
    "表示数": "impressions", "表示回数": "impressions", "インプレッション": "impressions",
    "クリック数": "clicks", "クリック": "clicks",
    "応募数": "applications", "応募件数": "applications",
    "面接数": "interviews", "面接設定数": "interviews",
    "採用数": "hires", "採用人数": "hires",
    "広告費": "cost", "広告費用": "cost", "費用": "cost", "掲載費": "cost",
    "備考": "note", "メモ": "note",
    "応募数目標": "target_applications", "応募単価目標": "target_cpa", "採用数目標": "target_hires",
}

NUMERIC_COLUMNS = ["impressions", "clicks", "applications", "interviews", "hires", "cost",
                   "target_applications", "target_cpa", "target_hires"]
REQUIRED_COLUMNS = ["media", "job_category", "applications", "cost"]
TOTAL_ROW_NAMES = {"合計", "総計", "計", "total", "TOTAL"}
# 個人情報の疑いがある列名（検出したら処理を止める）
PII_COLUMN_KEYWORDS = ["氏名", "名前", "電話", "メール", "mail", "住所", "生年月日"]

KEY_COLUMNS = ["media", "job_category", "location"]


def setup_logger(name: str, log_file: str | None = None) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


def load_settings(path: str | Path) -> dict:
    """会社設定YAMLを読み込む。存在しない・壊れている場合は日本語メッセージで停止。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"会社設定ファイルが見つかりません: {p}。初期設定を先に行ってください。")
    with open(p, encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    if not isinstance(settings, dict):
        raise ValueError(f"会社設定ファイルの形式が正しくありません（YAMLの辞書形式である必要があります）: {p}")
    return settings


def read_table(path: str | Path, sheet: str | int = 0) -> pd.DataFrame:
    """CSV（UTF-8/Shift_JIS自動判定）またはExcelを読み込む。全列を文字列として読む。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"入力ファイルが見つかりません: {p}")
    if p.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
        return pd.read_excel(p, sheet_name=sheet, dtype=str)
    for enc in ("utf-8-sig", "cp932"):
        try:
            return pd.read_csv(p, dtype=str, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"文字コードを判定できません（UTF-8またはShift_JISで保存してください）: {p}")


def clean_text(value) -> str | None:
    """前後の空白（全角含む）を除去。空欄はNone。"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().strip("　").strip()
    return text if text else None


def parse_number(value) -> float | None | str:
    """数値文字列を数値へ。カンマ・円・¥・%・全角数字に対応。

    空欄 → None（欠損。0にしない）
    解釈不能 → 元の文字列を返す（validate_data.py が「数値以外」として検出する）
    """
    text = clean_text(value)
    if text is None:
        return None
    text = unicodedata.normalize("NFKC", text)
    for token in (",", "円", "¥", "\\", "%", "％", " "):
        text = text.replace(token, "")
    if text == "":
        return None
    try:
        num = float(text)
        return int(num) if num == int(num) else num
    except ValueError:
        return str(value)  # 不正値: 元の値を保持して検出対象にする


def column_alias_map(settings: dict | None = None) -> dict[str, str]:
    aliases = dict(DEFAULT_COLUMN_ALIASES)
    if settings:
        aliases.update(settings.get("column_aliases", {}) or {})
    return aliases


def media_alias_map(settings: dict | None = None) -> dict[str, str]:
    if not settings:
        return {}
    return dict((settings.get("media", {}) or {}).get("aliases", {}) or {})


def registered_media(settings: dict | None = None) -> list[str]:
    if not settings:
        return []
    return list((settings.get("media", {}) or {}).get("registered", []) or [])
