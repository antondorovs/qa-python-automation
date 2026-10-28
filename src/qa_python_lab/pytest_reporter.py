"""pytest hooks that save a QA summary after every selected test run."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qa_python_lab.qa_report import QaTestResult, build_summary, render_markdown

QA_TAGS = {"api", "contract", "data", "smoke", "ui"}


class QaReporter:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.selected: dict[str, tuple[str, ...]] = {}
        self.outcomes: dict[str, str] = {}
        self.durations: dict[str, int] = {}
        self.errors: dict[str, str] = {}

    @pytest.hookimpl
    def pytest_collection_finish(self, session: pytest.Session) -> None:
        self.selected = {
            item.nodeid: tuple(sorted(marker.name for marker in item.iter_markers()
                                      if marker.name in QA_TAGS))
            for item in session.items
        }

    @pytest.hookimpl
    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        nodeid = report.nodeid
        self.durations[nodeid] = self.durations.get(nodeid, 0) + round(report.duration * 1000)
        if report.failed:
            self.outcomes[nodeid] = "failed"
            error = report.longreprtext
            crash = getattr(report.longrepr, "reprcrash", None)
            if crash is not None:
                error = f"{error}\n{crash.message}"
            self.errors[nodeid] = error[-1000:]
        elif report.skipped and self.outcomes.get(nodeid) != "failed":
            self.outcomes[nodeid] = "skipped"
        elif report.when == "call" and report.passed and self.outcomes.get(nodeid) != "failed":
            self.outcomes[nodeid] = "passed"

    @pytest.hookimpl
    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        results = [
            QaTestResult(
                nodeid=nodeid,
                status=self.outcomes.get(nodeid, "interrupted"),
                duration_ms=self.durations.get(nodeid, 0),
                tags=tags,
                error=self.errors.get(nodeid),
            )
            for nodeid, tags in self.selected.items()
        ]
        summary = build_summary(results, int(exitstatus))
        output = self.root / "qa-report"
        output.mkdir(exist_ok=True)
        (output / "qa-summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (output / "qa-summary.md").write_text(render_markdown(summary), encoding="utf-8")


def pytest_configure(config: pytest.Config) -> None:
    config.pluginmanager.register(QaReporter(config.rootpath), "qa-python-reporter")
