"""Shared pytest fixtures for pyfloor's test suite.

Offline by construction: every fixture builds a tiny fake project on disk
in a tmp_path, never touching the network.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def write_project(tmp_path):
    """Return a callable that writes files into tmp_path and returns it.

    Usage::

        root = write_project({
            "pyproject.toml": '[project]\\nrequires-python = ">=3.9"\\n',
            ".python-version": "3.9\\n",
        })
    """

    def _write(files):
        for relpath, content in files.items():
            path = tmp_path / relpath
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return tmp_path

    return _write


@pytest.fixture
def clean_project(write_project):
    """A fully consistent, clean project: one floor, tested in CI, no bad code."""
    return write_project(
        {
            "pyproject.toml": (
                '[project]\nname = "demo"\nversion = "0.1.0"\nrequires-python = ">=3.9"\n'
            ),
            ".python-version": "3.9\n",
            ".github/workflows/ci.yml": (
                "name: CI\n"
                "on: [push]\n"
                "jobs:\n"
                "  test:\n"
                "    strategy:\n"
                "      matrix:\n"
                "        python-version: ['3.9', '3.11', '3.12']\n"
                "    steps:\n"
                "      - uses: actions/setup-python@v5\n"
                "        with:\n"
                "          python-version: ${{ matrix.python-version }}\n"
            ),
            "app.py": "def add(a, b):\n    return a + b\n",
        }
    )
