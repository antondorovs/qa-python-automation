from qa_python_lab.bug_report import BugReport


def test_bug_report_contains_reproduction_and_outcome() -> None:
    report = BugReport(
        title="User lookup returns 500",
        steps=("Open the users endpoint", "Request user 1"),
        expected="HTTP 200 with user data",
        actual="HTTP 500",
    )
    markdown = report.to_markdown()
    assert "1. Open the users endpoint" in markdown
    assert "2. Request user 1" in markdown
    assert "HTTP 200 with user data" in markdown
    assert "HTTP 500" in markdown


def test_multiline_reproduction_step_stays_inside_ordered_list() -> None:
    report = BugReport(
        title="Search returns the wrong result",
        steps=("Run this query:\n\n```sql\nSELECT 1;\n```", "Inspect the result"),
        expected="One row",
        actual="No rows",
    )

    assert (
        "1. Run this query:\n\n"
        "   ```sql\n"
        "   SELECT 1;\n"
        "   ```\n"
        "2. Inspect the result\n"
    ) in report.to_markdown()
