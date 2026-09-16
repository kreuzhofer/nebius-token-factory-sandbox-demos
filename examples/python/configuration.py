"""Read configuration at entrypoints; consumers receive explicit values."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_env(path=None):
    """Read a local file without mutating process state; existing environment wins."""
    values = dict(os.environ)
    path = Path(path) if path else ROOT / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith("#"):
                name, value = line.split("=", 1)
                values.setdefault(name.strip(), value.strip())
    return values


@dataclass(frozen=True)
class SandboxConfig:
    token: str = field(repr=False)
    project: str | None = None
    base_url: str | None = None

    @classmethod
    def from_env(cls, values):
        token = values.get("CONTREE_TOKEN") or values.get("NEBIUS_API_KEY")
        if not token:
            raise RuntimeError(
                "Configure CONTREE_TOKEN or NEBIUS_API_KEY with python -m basic_demo configure"
            )
        return cls(token, values.get("CONTREE_PROJECT"), values.get("CONTREE_BASE_URL"))

    def to_env(self):
        values = {"CONTREE_TOKEN": self.token}
        for name, value in (("CONTREE_PROJECT", self.project), ("CONTREE_BASE_URL", self.base_url)):
            if value:
                values[name] = value
        return values
