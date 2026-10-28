from pathlib import Path

import pytest

from qa_python_lab.pytest_reporter import QaReporter
from qa_python_lab.qa_report import QaTestResult, build_summary, render_markdown


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
