import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from qa_python_lab.pytest_reporter import QaReporter
from qa_python_lab.qa_report import QaTestResult, build_summary, render_markdown


def _run_reporter(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "qa_python_lab.pytest_reporter", *args],
        cwd=root,
        env=os.environ | {
            "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        },
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.mark.parametrize("context", ["", "Traceback context\n" * 100], ids=["short", "long"])
def test_failure_excerpt_preserves_final_error(tmp_path: Path, context: str) -> None:
    reporter = QaReporter(tmp_path)
    message = "AssertionError: expected status 200, got 500"
    report = pytest.TestReport(
        nodeid="test_response",
        location=("test_response.py", 0, "test_response"),
        keywords={},
        outcome="failed",
        longrepr=context + message,
        when="call",
    )

    reporter.pytest_runtest_logreport(report)

    excerpt = reporter.errors[report.nodeid]
    assert len(excerpt) <= 1000
    assert excerpt.endswith(message)
    if not context:
        assert excerpt == message
    summary = build_summary([
        QaTestResult(report.nodeid, "failed", 0, error=excerpt),
    ], exit_code=1)
    assert f"Failure: {message}" in render_markdown(summary)


@pytest.mark.parametrize("phase", ["setup", "call", "teardown"])
def test_real_pytest_failure_blocks_saved_reports(tmp_path: Path, phase: str) -> None:
    (tmp_path / "test_scenario.py").write_text(
        f"""import pytest

phase = {phase!r}

@pytest.fixture
def resource():
    if phase == "setup":
        raise RuntimeError("setup failure")
    yield
    if phase == "teardown":
        raise RuntimeError("teardown failure")

def test_case(resource):
    if phase == "call":
        raise AssertionError("call failure")
""",
        encoding="utf-8",
    )
    completed = _run_reporter(tmp_path)

    assert completed.returncode == 1, completed.stdout + completed.stderr
    output = tmp_path / "qa-report"
    summary = json.loads((output / "qa-summary.json").read_text(encoding="utf-8"))
    assert summary["total"] == summary["executed"] == summary["failed"] == 1
    assert summary["passed"] == summary["skipped"] == summary["interrupted"] == 0
    assert summary["pass_rate"] == 0.0
    assert summary["quality_gate"] == {"status": "blocked", "reasons": ["1 failed test(s)"]}
    assert len(summary["tests"]) == 1
    result = summary["tests"][0]
    assert result["nodeid"] == "test_scenario.py::test_case"
    assert result["status"] == "failed"
    assert f"{phase} failure" in result["error"]
    markdown = (output / "qa-summary.md").read_text(encoding="utf-8")
    assert "Quality gate: **blocked**" in markdown
    assert f"{phase} failure" in markdown


def test_selected_test_reports_inherited_markers_once(tmp_path: Path) -> None:
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n    api: API checks\n    smoke: critical checks\n"
        "    slow: longer checks\n",
        encoding="utf-8",
    )
    (tmp_path / "test_markers.py").write_text(
        """import pytest

pytestmark = pytest.mark.api

@pytest.mark.api
class TestUsers:
    @pytest.mark.api
    @pytest.mark.smoke
    @pytest.mark.slow
    def test_selected(self):
        pass

def test_deselected():
    raise AssertionError("must not run")
""",
        encoding="utf-8",
    )

    completed = _run_reporter(tmp_path, "-m", "smoke", "--strict-markers")

    assert completed.returncode == 0, completed.stdout + completed.stderr
    output = tmp_path / "qa-report"
    summary = json.loads((output / "qa-summary.json").read_text(encoding="utf-8"))
    assert summary["total"] == summary["executed"] == summary["passed"] == 1
    assert summary["quality_gate"] == {"status": "ready", "reasons": []}
    assert summary["tag_counts"] == {"api": 1, "smoke": 1}
    assert len(summary["tests"]) == 1
    assert summary["tests"][0]["nodeid"] == "test_markers.py::TestUsers::test_selected"
    assert summary["tests"][0]["tags"] == ["api", "smoke"]
    markdown = (output / "qa-summary.md").read_text(encoding="utf-8")
    assert "tags: api, smoke)" in markdown
    assert "test_deselected" not in markdown
