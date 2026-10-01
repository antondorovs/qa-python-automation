"""Explicit data quality rules for the lab's intentionally imperfect dataset."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuleResult:
    name: str
    actual: int
    expected: int

    @property
    def passed(self) -> bool:
        return self.actual == self.expected


RULES = {
    "duplicate_emails": """
        SELECT COUNT(*) FROM (
            SELECT 1 FROM users
            GROUP BY lower(trim(email)) HAVING COUNT(*) > 1
        )
    """,
    "blank_user_names": "SELECT COUNT(*) FROM users WHERE trim(name) = ''",
    "orphan_orders": """
        SELECT COUNT(*) FROM orders o LEFT JOIN users u ON u.id = o.user_id
        WHERE u.id IS NULL
    """,
    "non_positive_amounts": "SELECT COUNT(*) FROM orders WHERE amount <= 0",
    "invalid_order_statuses": "SELECT COUNT(*) FROM orders WHERE status NOT IN ('NEW', 'PAID')",
    "orphan_payments": """
        SELECT COUNT(*) FROM payments p LEFT JOIN orders o ON o.id = p.order_id
        WHERE o.id IS NULL
    """,
    "invalid_payment_statuses": "SELECT COUNT(*) FROM payments WHERE status != 'SUCCESS'",
    "paid_without_payment": """
        SELECT COUNT(*) FROM orders o
        WHERE o.status = 'PAID' AND NOT EXISTS (
            SELECT 1 FROM payments p WHERE p.order_id = o.id AND p.status = 'SUCCESS'
        )
    """,
}

BASELINE = {
    "duplicate_emails": 1,
    "blank_user_names": 0,
    "orphan_orders": 1,
    "non_positive_amounts": 1,
    "invalid_order_statuses": 0,
    "orphan_payments": 0,
    "invalid_payment_statuses": 0,
    "paid_without_payment": 1,
}


def load_fixture(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(path.read_text(encoding="utf-8"))
    return connection


def evaluate_rules(connection: sqlite3.Connection) -> list[RuleResult]:
    return [
        RuleResult(name, connection.execute(query).fetchone()[0], BASELINE[name])
        for name, query in RULES.items()
    ]
