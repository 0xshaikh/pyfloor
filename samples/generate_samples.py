"""Generator for pyfloor sample fixtures.

Run from the repo root:  python samples/generate_samples.py
Regenerates samples/good/ and samples/broken/ deterministically.
"""

from __future__ import annotations

import random
import shutil
from pathlib import Path

random.seed(42)

SAMPLES = Path(__file__).resolve().parent

GOOD_FILES = {
    "pyproject.toml": """\
[project]
name = "sample-good"
version = "0.1.0"
description = "A clean sample project that declares floor >=3.10 and tests it."
requires-python = ">=3.10"

[tool.setuptools]
packages = []
""",
    ".github/workflows/ci.yml": """\
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e .
      - run: python -m pytest
""",
    "src/good.py": """\
\"\"\"A clean module using only pre-3.10 features.\"\"\"

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Union


@dataclass
class Point:
    x: float
    y: float

    def dist(self) -> float:
        return (self.x * self.x + self.y * self.y) ** 0.5


def scale(points: List[Point], factor: float) -> List[Point]:
    return [Point(p.x * factor, p.y * factor) for p in points]


def maybe_value(flag: bool) -> Optional[str]:
    if flag:
        return "yes"
    return None


def union_demo(value: Union[int, str]) -> str:
    return str(value)
""",
}

BROKEN_FILES = {
    "pyproject.toml": """\
[project]
name = "sample-broken"
version = "0.1.0"
description = "A broken sample: floor >=3.9 but CI tests only 3.11/3.12."
requires-python = ">=3.9"

[tool.setuptools]
packages = []
""",
    ".python-version": "3.9\n",
    ".github/workflows/ci.yml": """\
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e .
      - run: python -m pytest
""",
    "src/broken.py": """\
\"\"\"A module that uses features newer than the declared 3.9 floor.\"\"\"


def parse(data: dict) -> str:
    match data.get("kind"):
        case "a":
            return "alpha"
        case "b":
            return "beta"
        case _:
            return "other"


def read_toml(path: str) -> dict:
    import tomllib

    with open(path, "rb") as fh:
        return tomllib.load(fh)
""",
}


def write_tree(base: Path, files: dict) -> None:
    for rel, content in files.items():
        target = base / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def main() -> None:
    for name in ("good", "broken"):
        target = SAMPLES / name
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
    write_tree(SAMPLES / "good", GOOD_FILES)
    write_tree(SAMPLES / "broken", BROKEN_FILES)
    print("Wrote samples/good/ and samples/broken/")


if __name__ == "__main__":
    main()
