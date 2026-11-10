"""Turn a reproducible failure into a short Markdown bug report."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BugReport:
    title: str
    steps: tuple[str, ...]
    expected: str
    actual: str
    environment: str = "local"

    def to_markdown(self) -> str:
        steps = []
        for number, step in enumerate(self.steps, 1):
            marker = f"{number}. "
            first, *rest = step.split("\n")
            steps.append(marker + first)
            indent = " " * len(marker)
            steps.extend(indent + line if line.strip() else "" for line in rest)
        reproduction = "\n".join(steps)
        return (
            f"# {self.title}\n\nEnvironment: {self.environment}\n\n"
            f"## Steps to reproduce\n{reproduction}\n\n"
            f"## Expected\n{self.expected}\n\n## Actual\n{self.actual}\n"
        )
