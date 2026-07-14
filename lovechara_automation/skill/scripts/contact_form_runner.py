from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import parse_qs, unquote, urljoin, urlparse, urlunparse

import gspread
import requests
from bs4 import BeautifulSoup
from google.auth.exceptions import TransportError
from google.oauth2.service_account import Credentials
from requests import Response, Session
from requests.adapters import HTTPAdapter
from urllib3.exceptions import LocationParseError
from urllib3.util.retry import Retry


JP_SHEET_NAME = "\u6574\u5f62\u6e08\u307f_\u8a3a\u65ad\u30b5\u30a4\u30c8\u53d7\u8a17"
JP_DASH = "\u30fc"
JP_CONTACT = "\u304a\u554f\u3044\u5408\u308f\u305b"
JP_CONTACT_ALT_1 = "\u304a\u554f\u5408\u305b"
JP_CONTACT_ALT_2 = "\u554f\u3044\u5408\u308f\u305b"
JP_CONTACT_ALT_3 = "\u554f\u5408\u305b"
JP_CUSTOMER = "\u304a\u5ba2\u69d8"
JP_CONSULT = "\u3054\u76f8\u8ac7"
JP_RECRUIT = "\u63a1\u7528"
JP_ROW_NUMBER = "\u884c\u756a\u53f7"
JP_OFFICIAL_URL_HEADER = "\u516c\u5f0fURL(G\u5217)"
JP_CONTACT_URL_HEADER = "\u554f\u3044\u5408\u308f\u305b\u30d5\u30a9\u30fc\u30e0URL(H\u5217\u8cbc\u4ed8\u7528)"
JP_NOTE_HEADER = "\u5099\u8003"

HIGH_PRIORITY_KEYWORDS = (
    JP_CONTACT,
    JP_CONTACT_ALT_1,
    JP_CONTACT_ALT_2,
    JP_CONTACT_ALT_3,
    "contact",
    "inquiry",
    "otoiawase",
    "toiawase",
)
MEDIUM_PRIORITY_KEYWORDS = (
    JP_CUSTOMER,
    JP_CONSULT,
    "support",
    "form",
    "mail",
)
EXCLUDED_KEYWORDS = (
    "recruit",
    JP_RECRUIT,
    "ir",
    "privacy",
    "login",
)
COMMON_CONTACT_PATHS = (
    "/contact",
    "/contact/",
    "/contact/index",
    "/contact/index/",
    "/contact/form",
    "/contact/form/",
    "/contact-us",
    "/contact-us/",
    "/inquiry",
    "/inquiry/",
    "/otoiawase",
    "/otoiawase/",
    "/toiawase",
    "/toiawase/",
    "/support",
    "/support/",
    "/customer",
    "/customer/",
    "/form",
    "/form/",
    "/mail",
    "/mail/",
    "/faq/contact",
    "/faq/contact/",
    "/company/contact",
    "/company/contact/",
    "/shop/contact",
    "/shop/contact/",
)
SITEMAP_PATHS = (
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/wp-sitemap.xml",
)
MALL_HOST_HINTS = (
    "rakuten.co.jp",
    "rakuten.ne.jp",
    "store.shopping.yahoo.co.jp",
    "shopping.geocities.jp",
    "amazon.co.jp",
    "qoo10.jp",
    "mercari",
    "paypaymall",
    "wowma",
)
DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; ContactFinder/1.0; +https://example.com/bot)"
GOOGLE_CSE_ENDPOINT = "https://customsearch.googleapis.com/customsearch/v1"
SHEETS_SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
)


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def normalize_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value or "").strip().lower()


def ensure_url(url: str) -> str:
    candidate = (url or "").strip()
    if not candidate:
        return ""
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    return candidate


def site_key(host: str) -> str:
    parts = [part for part in (host or "").lower().split(".") if part]
    if len(parts) <= 2:
        return ".".join(parts)
    if parts[-2:] in (["co", "jp"], ["ne", "jp"], ["or", "jp"]):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def canonicalize_url(url: str) -> str:
    prepared = ensure_url(url)
    if not prepared:
        return ""
    parsed = urlparse(prepared)
    if parsed.scheme not in {"http", "https"}:
        return ""
    normalized_path = parsed.path or "/"
    if normalized_path != "/" and normalized_path.endswith("/"):
        normalized_path = normalized_path[:-1]
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            normalized_path,
            "",
            parsed.query,
            "",
        )
    )


def is_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def first_non_empty(*values: str) -> str:
    for value in values:
        if (value or "").strip():
            return value.strip()
    return ""


def row_cell(row: list[str], index: int) -> str:
    if index < len(row):
        return row[index].strip()
    return ""


def single_value(range_values: list[list[str]]) -> str:
    if range_values and range_values[0]:
        return range_values[0][0].strip()
    return ""


def is_missing_contact_value(value: str) -> bool:
    return normalize_text(value) in {"", "?", "?"}


@dataclass
class Settings:
    spreadsheet_id: str
    sheet_name: str
    credentials_path: Path
    baseline_path: Path
    logs_dir: Path
    max_rows_per_run: int
    request_timeout_seconds: int
    crawl_delay_seconds: float
    user_agent: str
    dry_run: bool
    verbose: bool
    google_api_key: str
    google_cse_id: str

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "Settings":
        credentials = args.credentials or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        spreadsheet_id = args.spreadsheet_id or os.getenv(
            "SPREADSHEET_ID",
            "1J748-Kt8OOxlOh6iEfLv6Viya9nuzBB1xVsZ38jZdS0",
        )
        sheet_name = args.sheet_name or os.getenv("SHEET_NAME", JP_SHEET_NAME)
        baseline_path = Path(args.baseline or os.getenv("BASELINE_PATH", "data/baseline_results.csv")).expanduser()
        logs_dir = Path(args.logs_dir or os.getenv("LOGS_DIR", "logs")).expanduser()
        return cls(
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            credentials_path=Path(credentials).expanduser(),
            baseline_path=baseline_path,
            logs_dir=logs_dir,
            max_rows_per_run=int(args.max_rows or os.getenv("MAX_ROWS_PER_RUN", "200")),
            request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "15")),
            crawl_delay_seconds=float(os.getenv("CRAWL_DELAY_SECONDS", "1.2")),
            user_agent=os.getenv("CONTACT_FINDER_USER_AGENT", DEFAULT_USER_AGENT),
            dry_run=args.dry_run or env_flag("DRY_RUN", False),
            verbose=args.verbose or env_flag("VERBOSE", False),
            google_api_key=os.getenv("GOOGLE_API_KEY", "").strip(),
            google_cse_id=os.getenv("GOOGLE_CSE_ID", "").strip(),
        )

    def validate(self) -> None:
        if str(self.credentials_path) in {"", "."} or self.credentials_path.is_dir():
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS must point to a service account JSON file.")
        if not self.credentials_path.exists():
            raise ValueError(f"Credentials file not found: {self.credentials_path}")
        if not self.baseline_path.exists():
            raise ValueError(f"Baseline CSV not found: {self.baseline_path}")
        if self.max_rows_per_run <= 0:
            raise ValueError("MAX_ROWS_PER_RUN must be greater than 0.")
        self.logs_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class CompanyRow:
    row_number: int
    company_name: str
    store_name: str
    official_url: str

    @property
    def display_name(self) -> str:
        return first_non_empty(self.company_name, self.store_name, f"row-{self.row_number}")


@dataclass
class ResultRecord:
    row_number: int
    company_name: str
    store_name: str
    official_url: str
    result_value: str
    reason: str
    source: str
    written: bool

    def to_csv_row(self) -> dict[str, str]:
        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "row_number": str(self.row_number),
            "company_name": self.company_name,
            "store_name": self.store_name,
            "official_url": self.official_url,
            "result_value": self.result_value,
            "reason": self.reason,
            "source": self.source,
            "written": "yes" if self.written else "no",
        }


@dataclass
class Decision:
    url: Optional[str]
    reason: str
    source: str

    @property
    def sheet_value(self) -> str:
        return self.url or JP_DASH


class RunLogger:
    HEADERS = (
        "timestamp",
        "row_number",
        "company_name",
        "store_name",
        "official_url",
        "result_value",
        "reason",
        "source",
        "written",
    )

    def __init__(self, logs_dir: Path) -> None:
        filename = f"run_log_{datetime.now().strftime('%Y%m%d')}.csv"
        self.path = logs_dir / filename
        self._initialized = self.path.exists()

    def append(self, record: ResultRecord) -> None:
        with self.path.open("a", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.HEADERS)
            if not self._initialized:
                writer.writeheader()
                self._initialized = True
            writer.writerow(record.to_csv_row())


class BaselineStore:
    def __init__(self, path: Path) -> None:
        self._row_map: dict[int, Decision] = {}
        self._url_map: dict[str, Decision] = {}
        self._load(path)

    def _load(self, path: Path) -> None:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                raw_row_number = (row.get(JP_ROW_NUMBER) or "").strip()
                official_url = (row.get(JP_OFFICIAL_URL_HEADER) or "").strip()
                result_url = (row.get(JP_CONTACT_URL_HEADER) or "").strip()
                note = (row.get(JP_NOTE_HEADER) or "").strip()
                if not raw_row_number and not official_url:
                    continue
                decision = Decision(
                    url=result_url or None,
                    reason=f"baseline\u6d41\u7528: {note}" if note else "baseline\u6d41\u7528",
                    source="baseline",
                )
                if raw_row_number.isdigit():
                    self._row_map[int(raw_row_number)] = decision
                canonical = canonicalize_url(official_url)
                if canonical:
                    self._url_map[canonical] = decision

    def match(self, row_number: int, official_url: str) -> Optional[Decision]:
        if row_number in self._row_map:
            return self._row_map[row_number]
        canonical = canonicalize_url(official_url)
        if canonical:
            return self._url_map.get(canonical)
        return None


class RateLimitedSession:
    def __init__(self, timeout_seconds: int, delay_seconds: float, user_agent: str) -> None:
        self.timeout_seconds = timeout_seconds
        self.delay_seconds = delay_seconds
        self.session = self._build_session(user_agent)
        self._last_request_at: dict[str, float] = {}

    def _build_session(self, user_agent: str) -> Session:
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "HEAD"),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({"User-Agent": user_agent})
        return session

    def _throttle(self, host: str) -> None:
        last_request = self._last_request_at.get(host)
        if last_request is None:
            return
        elapsed = time.monotonic() - last_request
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)

    def request(self, method: str, url: str, **kwargs: object) -> Optional[Response]:
        if not is_http_url(url):
            return None
        host = urlparse(url).netloc.lower()
        self._throttle(host)
        try:
            response = self.session.request(method, url, timeout=self.timeout_seconds, allow_redirects=True, **kwargs)
        except (requests.RequestException, LocationParseError, ValueError):
            return None
        finally:
            self._last_request_at[host] = time.monotonic()
        if response.status_code >= 400:
            return None
        return response

    def get(self, url: str) -> Optional[Response]:
        return self.request("GET", url)


class GoogleSearchClient:
    def __init__(self, session: RateLimitedSession, api_key: str, cse_id: str) -> None:
        self.session = session
        self.api_key = api_key
        self.cse_id = cse_id

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.cse_id)

    def search(self, query: str, num: int = 5) -> list[str]:
        if not self.enabled:
            return []
        response = self.session.request(
            "GET",
            GOOGLE_CSE_ENDPOINT,
            params={
                "key": self.api_key,
                "cx": self.cse_id,
                "q": query,
                "num": min(num, 10),
                "hl": "ja",
                "safe": "off",
            },
        )
        if response is None:
            return []
        try:
            payload = response.json()
        except ValueError:
            return []
        items = payload.get("items") or []
        urls: list[str] = []
        for item in items:
            link = (item or {}).get("link")
            if isinstance(link, str) and is_http_url(link):
                urls.append(link)
        return urls


class SheetClient:
    def __init__(self, settings: Settings) -> None:
        credentials = Credentials.from_service_account_file(
            str(settings.credentials_path),
            scopes=SHEETS_SCOPES,
        )
        client = gspread.authorize(credentials)
        self.worksheet = client.open_by_key(settings.spreadsheet_id).worksheet(settings.sheet_name)
        self.max_attempts = 4

    def _with_retry(self, func: Callable[[], object]):
        delay_seconds = 1.0
        for attempt in range(1, self.max_attempts + 1):
            try:
                return func()
            except gspread.exceptions.APIError:
                if attempt == self.max_attempts:
                    raise
                time.sleep(delay_seconds)
                delay_seconds *= 2
            except (requests.RequestException, TransportError):
                if attempt == self.max_attempts:
                    raise
                time.sleep(delay_seconds)
                delay_seconds *= 2
        raise RuntimeError("unreachable")

    def fetch_target_rows(self, max_rows: int) -> list[CompanyRow]:
        values = self._with_retry(self.worksheet.get_all_values)
        targets: list[CompanyRow] = []
        for row_number, row in enumerate(values[1:], start=2):
            official_url = row_cell(row, 6)
            contact_url = row_cell(row, 7)
            handled_at = row_cell(row, 13)
            if not official_url or not is_missing_contact_value(contact_url) or handled_at:
                continue
            targets.append(
                CompanyRow(
                    row_number=row_number,
                    company_name=row_cell(row, 4),
                    store_name=row_cell(row, 5),
                    official_url=official_url,
                )
            )
            if len(targets) >= max_rows:
                break
        return targets

    def can_write_row(self, row_number: int) -> bool:
        ranges = self._with_retry(lambda: self.worksheet.batch_get([f"H{row_number}", f"N{row_number}"]))
        current_h = single_value(ranges[0]) if len(ranges) > 0 else ""
        current_n = single_value(ranges[1]) if len(ranges) > 1 else ""
        return is_missing_contact_value(current_h) and not current_n

    def update_contact_url(self, row_number: int, value: str) -> None:
        self._with_retry(lambda: self.worksheet.update(f"H{row_number}", [[value]], value_input_option="RAW"))
        # 書き込み後に実セルを読み戻して検証する。API成功応答だけを信用して
        # 「記載済み」と報告しないための必須チェック。
        actual = self._with_retry(lambda: self.worksheet.acell(f"H{row_number}").value) or ""
        if actual.strip() != value.strip():
            raise RuntimeError(
                f"write verification failed at H{row_number}: expected {value!r}, sheet has {actual!r}"
            )


class ContactFinder:
    def __init__(self, session: RateLimitedSession, search_client: GoogleSearchClient) -> None:
        self.session = session
        self.search_client = search_client

    def find(self, row: CompanyRow) -> Decision:
        official_url = ensure_url(row.official_url)
        if not official_url:
            return Decision(url=None, reason="\u516c\u5f0fURL\u304c\u4e0d\u6b63\u306e\u305f\u3081\u8abf\u67fb\u4e0d\u53ef", source="crawler")

        if self._is_mall_url(official_url):
            searched = self._search_by_name(row, mall_mode=True)
            if searched is not None:
                return searched
            return Decision(
                url=None,
                reason="\u30e2\u30fc\u30eb\u5e97\u3002\u904b\u55b6\u4f1a\u793e\u306e\u81ea\u793e\u30b5\u30a4\u30c8/\u30d5\u30a9\u30fc\u30e0\u3092\u7279\u5b9a\u3067\u304d\u305a",
                source="crawler",
            )

        direct = self._inspect_url(official_url, row=row)
        if direct is not None:
            return Decision(url=direct, reason="\u516c\u5f0fURL\u914d\u4e0b\u304b\u3089\u554f\u3044\u5408\u308f\u305b\u30da\u30fc\u30b8\u3092\u7279\u5b9a", source="crawler")

        searched = self._search_by_name(row, mall_mode=False)
        if searched is not None:
            return searched

        return Decision(url=None, reason="\u554f\u3044\u5408\u308f\u305b\u30d5\u30a9\u30fc\u30e0\u3092\u7279\u5b9a\u3067\u304d\u305a", source="crawler")

    def _is_mall_url(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return any(hint in host for hint in MALL_HOST_HINTS)

    def _company_name_tokens(self, row: CompanyRow) -> list[str]:
        tokens: list[str] = []
        for raw in (row.company_name, row.store_name):
            name = normalize_text(raw)
            if not name:
                continue
            for junk in ("株式会社", "有限会社", "合同会社", "合資会社", "一般社団法人", "(株)", "（株）", "(有)", "（有）"):
                name = name.replace(normalize_text(junk), "")
            name = name.strip()
            if len(name) >= 2:
                tokens.append(name)
        return tokens

    def _mentions_company(self, html: str, row: CompanyRow) -> bool:
        tokens = self._company_name_tokens(row)
        if not tokens:
            return False
        soup = BeautifulSoup(html, "html.parser")
        text = normalize_text(soup.get_text(" ", strip=True))
        title = soup.title.get_text(strip=True) if soup.title else ""
        text = f"{normalize_text(title)} {text}"
        return any(token in text for token in tokens)

    def _inspect_url(self, url: str, row: Optional[CompanyRow] = None) -> Optional[str]:
        homepage = self.session.get(url)
        if homepage is None:
            return None
        # リダイレクトで別ドメインへ飛んだ場合（廃止ドメイン・パーキングページ等）は、
        # 企業名がページに含まれない限り無関係サイトとみなして打ち切る。
        requested_key = site_key(urlparse(url).netloc)
        landed_key = site_key(urlparse(homepage.url).netloc)
        if requested_key and landed_key != requested_key:
            if row is None or not self._mentions_company(homepage.text, row):
                return None
        if self._is_contact_page(homepage.url, homepage.text):
            return homepage.url

        candidates = self._find_candidate_links(homepage.url, homepage.text)
        for candidate in candidates[:8]:
            page = self.session.get(candidate)
            if page is None:
                continue
            if self._is_contact_page(page.url, page.text):
                return page.url

        root = self._root_url(homepage.url)
        for candidate in self._find_sitemap_candidates(root):
            page = self.session.get(candidate)
            if page is None:
                continue
            if self._is_contact_page(page.url, page.text):
                return page.url

        for path in COMMON_CONTACT_PATHS:
            guessed_url = urljoin(root, path)
            page = self.session.get(guessed_url)
            if page is None:
                continue
            if self._is_contact_page(page.url, page.text):
                return page.url
        return None

    def _search_by_name(self, row: CompanyRow, mall_mode: bool) -> Optional[Decision]:
        queries: list[str] = []
        display_name = row.display_name
        if row.company_name:
            queries.append(f'"{row.company_name}" {JP_CONTACT}')
            queries.append(f'"{row.company_name}" 公式サイト {JP_CONTACT}')
        if row.store_name:
            queries.append(f'"{row.store_name}" 運営会社 {JP_CONTACT}')
            queries.append(f'"{row.store_name}" contact')
        queries.append(f'"{display_name}" contact')

        official_key = ""
        if not mall_mode:
            official_key = site_key(urlparse(ensure_url(row.official_url)).netloc)

        used_free_search = False
        seen_urls: set[str] = set()
        for query in queries:
            result_urls, from_free_search = self._search_result_urls(query, num=5)
            used_free_search = used_free_search or from_free_search
            for result_url in result_urls:
                canonical = canonicalize_url(result_url)
                if not canonical or canonical in seen_urls or self._is_mall_url(result_url):
                    continue
                seen_urls.add(canonical)
                # 検索結果は公式URLと同一ドメインか、ページ本文に企業名/店舗名が
                # 含まれる場合のみ採用する。無関係な企業のフォームURL混入を防ぐ。
                result_key = site_key(urlparse(result_url).netloc)
                if not official_key or result_key != official_key:
                    page = self.session.get(result_url)
                    if page is None or not self._mentions_company(page.text, row):
                        continue
                found_url = self._inspect_url(result_url, row=row)
                if found_url:
                    source = "free-search" if from_free_search else "search"
                    reason_prefix = "無料Web検索で候補を発見" if from_free_search else "検索APIで候補を発見"
                    return Decision(
                        url=found_url,
                        reason=f"{reason_prefix}: {query}",
                        source=source,
                    )
        if mall_mode:
            if used_free_search:
                return Decision(url=None, reason="無料Web検索でも運営会社サイト/フォームを特定できず", source="free-search")
            if not self.search_client.enabled:
                return Decision(url=None, reason="無料運用: 検索API未設定のためモール店は再検索せず未特定", source="free-mode")
            return Decision(url=None, reason="検索APIで運営会社サイト/フォームを特定できず", source="search")
        return None

    def _search_result_urls(self, query: str, num: int = 5) -> tuple[list[str], bool]:
        if self.search_client.enabled:
            return self.search_client.search(query, num=num), False
        return self._search_web_fallback(query, num=num), True

    def _search_web_fallback(self, query: str, num: int = 5) -> list[str]:
        endpoints = (
            ("https://html.duckduckgo.com/html/", {"q": query, "kl": "jp-jp"}),
            ("https://www.bing.com/search", {"q": query, "setlang": "ja-JP"}),
        )
        seen: set[str] = set()
        urls: list[str] = []
        for endpoint, params in endpoints:
            response = self.session.request("GET", endpoint, params=params)
            if response is None:
                continue
            for candidate in self._extract_search_result_links(response.text, response.url):
                canonical = canonicalize_url(candidate)
                if not canonical or canonical in seen:
                    continue
                seen.add(canonical)
                urls.append(candidate)
                if len(urls) >= num:
                    return urls
        return urls

    def _extract_search_result_links(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        extracted: list[str] = []
        seen: set[str] = set()
        engine_host = urlparse(base_url).netloc.lower()
        for anchor in soup.select("a[href]"):
            href = (anchor.get("href") or "").strip()
            if not href:
                continue
            candidate = ""
            if "duckduckgo.com" in engine_host and "uddg=" in href:
                parsed = urlparse(urljoin(base_url, href))
                uddg = parse_qs(parsed.query).get("uddg", [])
                if uddg:
                    candidate = uddg[0]
            else:
                absolute = urljoin(base_url, href)
                parsed = urlparse(absolute)
                host = parsed.netloc.lower()
                if "bing.com" in host and parsed.path == "/ck/a":
                    target = parse_qs(parsed.query).get("u", [])
                    if target:
                        candidate = unquote(target[0])
                        if candidate.startswith("a1"):
                            candidate = candidate[2:]
                elif "bing.com" not in host and "duckduckgo.com" not in host:
                    candidate = absolute
            if not is_http_url(candidate):
                continue
            host = urlparse(candidate).netloc.lower()
            if any(blocked in host for blocked in ("bing.com", "duckduckgo.com", "microsoft.com")):
                continue
            canonical = canonicalize_url(candidate)
            if not canonical or canonical in seen:
                continue
            seen.add(canonical)
            extracted.append(candidate)
        return extracted

    def _find_sitemap_candidates(self, root_url: str) -> list[str]:
        root_host_key = site_key(urlparse(root_url).netloc)
        scored_urls: list[tuple[int, str]] = []
        seen: set[str] = set()
        for path in SITEMAP_PATHS:
            sitemap_url = urljoin(root_url, path)
            sitemap = self.session.get(sitemap_url)
            if sitemap is None:
                continue
            soup = BeautifulSoup(sitemap.text, "html.parser")
            for loc in soup.find_all("loc"):
                candidate = (loc.get_text(strip=True) or "").strip()
                if not is_http_url(candidate):
                    continue
                if site_key(urlparse(candidate).netloc) != root_host_key:
                    continue
                score = self._score_candidate(candidate)
                if score <= 0:
                    continue
                canonical = canonicalize_url(candidate)
                if not canonical or canonical in seen:
                    continue
                seen.add(canonical)
                scored_urls.append((score, candidate))
        scored_urls.sort(key=lambda item: item[0], reverse=True)
        return [url for _, url in scored_urls[:8]]
    def _find_candidate_links(self, base_url: str, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        current_host_key = site_key(urlparse(base_url).netloc)
        scored_links: list[tuple[int, str]] = []
        seen: set[str] = set()

        def add_candidate(raw_value: str, score_text: str) -> None:
            absolute = urljoin(base_url, (raw_value or "").strip())
            if not is_http_url(absolute):
                return
            if site_key(urlparse(absolute).netloc) != current_host_key:
                return
            score = self._score_candidate(score_text)
            if score <= 0:
                return
            canonical = canonicalize_url(absolute)
            if not canonical or canonical in seen:
                return
            seen.add(canonical)
            scored_links.append((score, absolute))

        for anchor in soup.select("a[href]"):
            href = (anchor.get("href") or "").strip()
            if not href or href.startswith("#") or href.lower().startswith("javascript:"):
                continue
            add_candidate(href, f"{anchor.get_text(' ', strip=True)} {href}")

        for form in soup.select("form[action]"):
            action = (form.get("action") or "").strip()
            if action:
                add_candidate(action, f"form action {action}")

        for frame in soup.select("iframe[src]"):
            src = (frame.get("src") or "").strip()
            if src:
                add_candidate(src, f"iframe src {src}")

        for selector, attr in (("[data-href]", "data-href"), ("[data-url]", "data-url")):
            for element in soup.select(selector):
                value = (element.get(attr) or "").strip()
                if value:
                    add_candidate(value, f"{attr} {value}")

        for element in soup.select("[onclick]"):
            onclick = (element.get("onclick") or "").strip()
            if not onclick:
                continue
            for raw_value in re.findall(r'''[\"\']([^\"\']+)[\"\']''', onclick):
                add_candidate(raw_value, f"onclick {onclick}")

        scored_links.sort(key=lambda item: item[0], reverse=True)
        return [url for _, url in scored_links]

    def _score_candidate(self, text: str) -> int:
        normalized = normalize_text(text)
        score = 0
        for keyword in HIGH_PRIORITY_KEYWORDS:
            if normalize_text(keyword) in normalized:
                score += 100
        for keyword in MEDIUM_PRIORITY_KEYWORDS:
            if normalize_text(keyword) in normalized:
                score += 40
        for keyword in EXCLUDED_KEYWORDS:
            if normalize_text(keyword) in normalized:
                score -= 60
        if "/contact" in normalized or "/inquiry" in normalized or "otoiawase" in normalized or "toiawase" in normalized:
            score += 20
        return score

    def _is_contact_page(self, page_url: str, html: str) -> bool:
        if not html:
            return False
        soup = BeautifulSoup(html, "html.parser")
        normalized_url = normalize_text(page_url)
        visible_text = normalize_text(soup.get_text(" ", strip=True))
        has_contact_marker = any(
            token in normalized_url for token in ("contact", "inquiry", "otoiawase", "toiawase", "form", "mail")
        )
        has_contact_copy = any(
            normalize_text(keyword) in visible_text for keyword in HIGH_PRIORITY_KEYWORDS
        )
        # フォーム要素の存在だけでは問い合わせページと判定しない。
        # サイト内検索ボックス等の誤検知を防ぐため、URLか本文に問い合わせの
        # 手がかりがあることを必須とする。
        has_form_signal = (
            soup.find("textarea") is not None
            or soup.select_one("input[type='email']") is not None
            or soup.find("form") is not None
        )
        if has_form_signal and (has_contact_marker or has_contact_copy):
            return True
        if has_contact_copy:
            for anchor in soup.select("a[href]"):
                href = (anchor.get("href") or "").strip().lower()
                if href.startswith("mailto:"):
                    return True
        return has_contact_marker and has_contact_copy

    def _root_url(self, url: str) -> str:
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, "/", "", "", ""))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fill Google Sheets contact form URLs.")
    parser.add_argument("--credentials", help="Path to the Google service account JSON file.")
    parser.add_argument("--spreadsheet-id", help="Google Spreadsheet ID.")
    parser.add_argument("--sheet-name", help="Worksheet name.")
    parser.add_argument("--baseline", help="Path to baseline_results.csv.")
    parser.add_argument("--logs-dir", help="Directory to store run logs.")
    parser.add_argument("--max-rows", type=int, help="Max rows to process in a single run.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write back to Sheets.")
    parser.add_argument("--verbose", action="store_true", help="Print per-row progress.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        settings = Settings.from_args(args)
        settings.validate()
    except ValueError as exc:
        print(f"[config error] {exc}", file=sys.stderr)
        return 2

    baseline = BaselineStore(settings.baseline_path)
    logger = RunLogger(settings.logs_dir)
    session = RateLimitedSession(
        timeout_seconds=settings.request_timeout_seconds,
        delay_seconds=settings.crawl_delay_seconds,
        user_agent=settings.user_agent,
    )
    search_client = GoogleSearchClient(
        session=session,
        api_key=settings.google_api_key,
        cse_id=settings.google_cse_id,
    )
    contact_finder = ContactFinder(session=session, search_client=search_client)
    sheet = SheetClient(settings)

    targets = sheet.fetch_target_rows(settings.max_rows_per_run)
    print(f"\u5bfe\u8c61\u884c\u6570: {len(targets)}")

    written_count = 0
    for row in targets:
        decision = baseline.match(row.row_number, row.official_url)
        if decision is None:
            decision = contact_finder.find(row)

        should_write = False
        if settings.dry_run:
            decision = Decision(
                url=decision.url,
                reason=f"{decision.reason} / dry-run\u306e\u305f\u3081\u672a\u66f4\u65b0",
                source=decision.source,
            )
        else:
            if sheet.can_write_row(row.row_number):
                sheet.update_contact_url(row.row_number, decision.sheet_value)
                should_write = True
                written_count += 1
            else:
                decision = Decision(
                    url=decision.url,
                    reason=f"{decision.reason} / \u7af6\u5408\u56de\u907f\u306e\u305f\u3081\u672a\u66f4\u65b0(H\u307e\u305f\u306fN\u306b\u5024\u3042\u308a)",
                    source=decision.source,
                )

        record = ResultRecord(
            row_number=row.row_number,
            company_name=row.company_name,
            store_name=row.store_name,
            official_url=row.official_url,
            result_value=decision.sheet_value,
            reason=decision.reason,
            source=decision.source,
            written=should_write,
        )
        logger.append(record)
        if settings.verbose:
            print(f"[row {row.row_number}] {row.display_name} -> {decision.sheet_value} ({decision.reason})")

    if targets:
        print(f"\u51e6\u7406\u7bc4\u56f2: \u884c {targets[0].row_number} \u301c {targets[-1].row_number}\uff08\u3053\u306e\u7bc4\u56f2\u5916\u306e\u884c\u306f\u4eca\u56de\u672a\u51e6\u7406\uff09")
    print(f"\u5b8c\u4e86: {written_count} \u4ef6\u3092\u66f8\u304d\u8fbc\u307f\u307e\u3057\u305f\u3002\u30ed\u30b0: {logger.path}")
    if settings.dry_run:
        print("dry-run \u306e\u305f\u3081\u30b9\u30d7\u30ec\u30c3\u30c9\u30b7\u30fc\u30c8\u306b\u306f\u66f8\u304d\u8fbc\u3093\u3067\u3044\u307e\u305b\u3093\u3002")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


