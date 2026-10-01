from pathlib import Path

import pytest

from qa_python_lab.data_quality import BASELINE, evaluate_rules, load_fixture


@pytest.mark.data
@pytest.mark.contract
def test_schema_contract(fixture_sql: Path) -> None:
    expected_columns = {
        "users": ["id", "name", "email"],
        "orders": ["id", "user_id", "status", "amount"],
        "payments": ["id", "order_id", "status"],
    }
    with load_fixture(fixture_sql) as connection:
        actual_columns = {
            table: [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
            for table in expected_columns
        }
    assert actual_columns == expected_columns


@pytest.mark.data
@pytest.mark.contract
def test_known_quality_baseline(fixture_sql: Path) -> None:
    with load_fixture(fixture_sql) as connection:
        results = evaluate_rules(connection)
    assert {result.name: result.actual for result in results} == BASELINE
    assert all(result.passed for result in results)


@pytest.mark.data
def test_new_bad_order_changes_baseline(fixture_sql: Path) -> None:
    with load_fixture(fixture_sql) as connection:
        connection.execute("INSERT INTO orders VALUES (5, 999, 'PAID', -1)")
        results = {result.name: result for result in evaluate_rules(connection)}
    assert results["orphan_orders"].actual == BASELINE["orphan_orders"] + 1
    assert results["non_positive_amounts"].actual == BASELINE["non_positive_amounts"] + 1
    assert results["paid_without_payment"].actual == BASELINE["paid_without_payment"] + 1
    assert not results["orphan_orders"].passed


@pytest.mark.data
def test_duplicate_email_with_surrounding_whitespace_changes_baseline(fixture_sql: Path) -> None:
    with load_fixture(fixture_sql) as connection:
        connection.execute(
            "INSERT INTO users VALUES (4, 'Duplicate Brian', ' BRIAN@example.com ')"
        )
        results = {result.name: result for result in evaluate_rules(connection)}
    assert results["duplicate_emails"].actual == BASELINE["duplicate_emails"] + 1
    assert not results["duplicate_emails"].passed


@pytest.mark.data
@pytest.mark.parametrize("name", ["", "  ", "\t", "\n", " \t\r\n "])
def test_blank_user_name_changes_only_its_rule(fixture_sql: Path, name: str) -> None:
    with load_fixture(fixture_sql) as connection:
        connection.execute("INSERT INTO users VALUES (4, ?, 'casey@example.com')", (name,))
        results = {result.name: result for result in evaluate_rules(connection)}
    assert results["blank_user_names"].actual == 1
    assert not results["blank_user_names"].passed
    assert all(result.passed for name, result in results.items() if name != "blank_user_names")


@pytest.mark.data
def test_blank_user_name_rule_counts_each_bad_row(fixture_sql: Path) -> None:
    with load_fixture(fixture_sql) as connection:
        connection.executemany(
            "INSERT INTO users VALUES (?, ?, ?)",
            [
                (4, "", "casey@example.com"),
                (5, "\t \n", "drew@example.com"),
                (6, " Eve ", "eve@example.com"),
            ],
        )
        results = {result.name: result for result in evaluate_rules(connection)}
    assert results["blank_user_names"].actual == 2
    assert not results["blank_user_names"].passed
    assert all(result.passed for name, result in results.items() if name != "blank_user_names")


@pytest.mark.data
def test_unknown_order_status_changes_only_its_rule(fixture_sql: Path) -> None:
    with load_fixture(fixture_sql) as connection:
        connection.execute("UPDATE orders SET status = 'UNKNOWN' WHERE id = 3")
        results = {result.name: result for result in evaluate_rules(connection)}
    assert results["invalid_order_statuses"].actual == 1
    assert not results["invalid_order_statuses"].passed
    assert all(
        result.passed for name, result in results.items() if name != "invalid_order_statuses"
    )


@pytest.mark.data
def test_orphan_payment_changes_only_its_rule(fixture_sql: Path) -> None:
    with load_fixture(fixture_sql) as connection:
        connection.execute("INSERT INTO payments VALUES (2, 999, 'SUCCESS')")
        results = {result.name: result for result in evaluate_rules(connection)}
    assert results["orphan_payments"].actual == 1
    assert not results["orphan_payments"].passed
    assert all(result.passed for name, result in results.items() if name != "orphan_payments")


@pytest.mark.data
def test_unknown_payment_status_changes_only_its_rule(fixture_sql: Path) -> None:
    with load_fixture(fixture_sql) as connection:
        connection.execute("INSERT INTO payments VALUES (2, 3, 'PENDING')")
        results = {result.name: result for result in evaluate_rules(connection)}
    assert results["invalid_payment_statuses"].actual == 1
    assert not results["invalid_payment_statuses"].passed
    assert all(
        result.passed for name, result in results.items() if name != "invalid_payment_statuses"
    )


@pytest.mark.data
@pytest.mark.parametrize(
    ("payment_status", "invalid_statuses", "paid_without_payment"),
    [("SUCCESS", 0, 0), ("PENDING", 1, 1)],
)
def test_payment_status_controls_paid_order_coverage(
    fixture_sql: Path,
    payment_status: str,
    invalid_statuses: int,
    paid_without_payment: int,
) -> None:
    with load_fixture(fixture_sql) as connection:
        connection.execute("INSERT INTO payments VALUES (2, 2, ?)", (payment_status,))
        results = {result.name: result for result in evaluate_rules(connection)}

    expected = BASELINE | {
        "invalid_payment_statuses": invalid_statuses,
        "paid_without_payment": paid_without_payment,
    }
    assert {name: result.actual for name, result in results.items()} == expected
    assert {name: result.passed for name, result in results.items()} == {
        name: actual == BASELINE[name] for name, actual in expected.items()
    }
