import sys

import yaml

from conftest import DEMO, ROOT, run_script

sys.path.insert(0, str(ROOT / "scripts"))
from validate_settings import check  # noqa: E402


def test_demo_settings_pass():
    r = run_script("validate_settings.py", "--settings", DEMO / "demo-company-settings.yaml")
    assert r.returncode == 0, r.stderr


def test_template_settings_have_no_errors():
    """テンプレートは空値を含むが、致命的な矛盾（error）はないこと。"""
    settings = yaml.safe_load((ROOT / "templates" / "company-settings-template.yaml").read_text(encoding="utf-8"))
    # テンプレは media.registered が空なのでエラー1件は想定内
    errors = [m for lv, m in check(settings) if lv == "error"]
    assert all("媒体" in m for m in errors), errors


def test_detects_kpi_dependency_conflict():
    settings = {
        "company": {"name": "テスト"},
        "media": {"registered": ["Indeed"]},
        "kpi": {"required": ["cph"], "optional": []},  # 採用単価 必須だが hires を取得しない
        "report": {},
    }
    errors = [m for lv, m in check(settings) if lv == "error"]
    assert any("採用単価" in m and "採用数" in m for m in errors)


def test_detects_bad_color_and_period():
    settings = {
        "company": {"name": "テスト", "current_period": "2026/6"},
        "media": {"registered": ["Indeed"]},
        "kpi": {"required": ["applications", "cost"]},
        "report": {"brand_color": "blue"},
    }
    errors = [m for lv, m in check(settings) if lv == "error"]
    assert any("YYYY-MM" in m for m in errors)
    assert any("brand_color" in m for m in errors)


def test_detects_empty_media():
    settings = {"company": {"name": "テスト"}, "media": {"registered": []},
                "kpi": {"required": ["applications", "cost"]}, "report": {}}
    errors = [m for lv, m in check(settings) if lv == "error"]
    assert any("媒体" in m for m in errors)
