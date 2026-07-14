from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path


SKILL_RUNNER = (
    Path.home()
    / ".codex"
    / "skills"
    / "lovechara-contact-url-csv-fill"
    / "scripts"
    / "contact_form_runner.py"
)

# --credentials も GOOGLE_APPLICATION_CREDENTIALS も無い場合のフォールバック用キー。
# これにより環境変数の反映タイミングや Codex 再起動に依存せず認証できる。
DEFAULT_CREDENTIALS_PATH = Path.home() / ".secrets" / "lovechara-sa.json"


def load_runner():
    spec = importlib.util.spec_from_file_location("contact_form_runner", SKILL_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load runner: {SKILL_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_parser(runner) -> argparse.ArgumentParser:
    parser = runner.build_parser()
    parser.description = "Fill Google Sheets contact form URLs using G/H-only target rules."
    return parser


def main() -> int:
    # Automation defaults: keep slow/free-search rows from consuming the whole run.
    os.environ.setdefault("REQUEST_TIMEOUT_SECONDS", "6")
    os.environ.setdefault("CRAWL_DELAY_SECONDS", "0.2")

    runner = load_runner()
    parser = build_parser(runner)
    args = parser.parse_args()

    # --credentials も GOOGLE_APPLICATION_CREDENTIALS も無い場合は既定キーにフォールバック。
    if not getattr(args, "credentials", None) and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        if DEFAULT_CREDENTIALS_PATH.exists():
            args.credentials = str(DEFAULT_CREDENTIALS_PATH)

    try:
        settings = runner.Settings.from_args(args)
        settings.validate()
    except ValueError as exc:
        print(f"[config error] {exc}", file=sys.stderr)
        return 2

    class GHOnlySheetClient(runner.SheetClient):
        def fetch_target_rows(self, max_rows: int):
            values = self._with_retry(self.worksheet.get_all_values)
            targets = []
            for row_number, row in enumerate(values[1:], start=2):
                official_url = runner.row_cell(row, 6)
                contact_url = runner.row_cell(row, 7)
                if not official_url or not runner.is_missing_contact_value(contact_url):
                    continue
                targets.append(
                    runner.CompanyRow(
                        row_number=row_number,
                        company_name=runner.row_cell(row, 4),
                        store_name=runner.row_cell(row, 5),
                        official_url=official_url,
                    )
                )
                if len(targets) >= max_rows:
                    break
            return targets

        def can_write_row(self, row_number: int) -> bool:
            ranges = self._with_retry(lambda: self.worksheet.batch_get([f"H{row_number}"]))
            current_h = runner.single_value(ranges[0]) if ranges else ""
            return runner.is_missing_contact_value(current_h)

    baseline = runner.BaselineStore(settings.baseline_path)
    logger = runner.RunLogger(settings.logs_dir)
    session = runner.RateLimitedSession(
        timeout_seconds=settings.request_timeout_seconds,
        delay_seconds=settings.crawl_delay_seconds,
        user_agent=settings.user_agent,
    )
    search_client = runner.GoogleSearchClient(
        session=session,
        api_key=settings.google_api_key,
        cse_id=settings.google_cse_id,
    )
    contact_finder = runner.ContactFinder(session=session, search_client=search_client)
    sheet = GHOnlySheetClient(settings)

    targets = sheet.fetch_target_rows(settings.max_rows_per_run)
    print(f"Target rows: {len(targets)}")

    written_count = 0
    for row in targets:
        decision = baseline.match(row.row_number, row.official_url)
        if decision is None:
            decision = contact_finder.find(row)

        should_write = False
        if settings.dry_run:
            decision = runner.Decision(
                url=decision.url,
                reason=f"{decision.reason} / dry-run",
                source=decision.source,
            )
        else:
            if sheet.can_write_row(row.row_number):
                sheet.update_contact_url(row.row_number, decision.sheet_value)
                should_write = True
                written_count += 1
            else:
                decision = runner.Decision(
                    url=decision.url,
                    reason=f"{decision.reason} / skipped because H changed",
                    source=decision.source,
                )

        logger.append(
            runner.ResultRecord(
                row_number=row.row_number,
                company_name=row.company_name,
                store_name=row.store_name,
                official_url=row.official_url,
                result_value=decision.sheet_value,
                reason=decision.reason,
                source=decision.source,
                written=should_write,
            )
        )
        if settings.verbose:
            print(f"[row {row.row_number}] {row.display_name} -> {decision.sheet_value} ({decision.reason})")

    if targets:
        print(
            f"Processed row range: {targets[0].row_number} - {targets[-1].row_number} "
            "(rows outside this range were NOT processed in this run)"
        )
    print(f"Done: wrote {written_count} rows. Log: {logger.path}")
    if settings.dry_run:
        print("dry-run: no spreadsheet updates were written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

