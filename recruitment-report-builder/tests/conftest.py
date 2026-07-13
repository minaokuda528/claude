import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "scripts"
DEMO = ROOT / "demo"
sys.path.insert(0, str(SCRIPTS))


def run_script(name: str, *args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)],
                          capture_output=True, text=True)


@pytest.fixture
def pipeline(tmp_path):
    """デモデータで normalize（当月・前月・目標)まで実行し、パス一式を返す。"""
    paths = {
        "current": tmp_path / "normalized_current.csv",
        "previous": tmp_path / "normalized_previous.csv",
        "targets": tmp_path / "normalized_targets.csv",
        "norm_report": tmp_path / "normalize_report.csv",
        "kpi": tmp_path / "kpi_results.csv",
        "validation": tmp_path / "validation_report.csv",
        "tmp": tmp_path,
    }
    for src, dst, period in (
        (DEMO / "demo-current-month.csv", paths["current"], "2026-06"),
        (DEMO / "demo-previous-month.csv", paths["previous"], "2026-05"),
        (DEMO / "demo-targets.csv", paths["targets"], None),
    ):
        args = ["--input", src, "--settings", DEMO / "demo-company-settings.yaml",
                "--output", dst]
        if period:
            args += ["--period", period]
        if dst == paths["current"]:
            args += ["--report", paths["norm_report"]]
        r = run_script("normalize_data.py", *args)
        assert r.returncode == 0, f"normalize失敗: {src}\n{r.stderr}"
    return paths
