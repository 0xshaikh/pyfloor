"""End-to-end CLI tests: exercise main(argv) and assert exit codes/output."""

from __future__ import annotations

import json

import pytest

from pyfloor.cli import main


@pytest.fixture
def _conflicting_project(write_project):
    """pyproject says >=3.9, .python-version says 3.12 -> DECL_MISMATCH."""
    return write_project(
        {
            "pyproject.toml": '[project]\nrequires-python = ">=3.9"\n',
            ".python-version": "3.12\n",
        }
    )


def test_cli_check_clean_exit_zero(clean_project, capsys):
    code = main(["check", str(clean_project)])
    out = capsys.readouterr().out
    assert code == 0
    assert "Declared floor: 3.9" in out
    assert "Findings: 0" in out


def test_cli_check_findings_exit_one(_conflicting_project, capsys):
    root = _conflicting_project
    code = main(["check", str(root)])
    out = capsys.readouterr().out
    assert code == 1
    assert "DECL_MISMATCH" in out


def test_cli_check_output_is_ascii(_conflicting_project, capsys):
    root = _conflicting_project
    code = main(["check", str(root)])
    out = capsys.readouterr().out
    assert code == 1
    # No box-drawing / non-ASCII glyphs allowed.
    out.encode("ascii")  # raises UnicodeEncodeError if not ASCII


def test_cli_json_valid(_conflicting_project, capsys):
    root = _conflicting_project
    code = main(["check", "--json", str(root)])
    out = capsys.readouterr().out
    assert code == 1
    idx = out.index("{\n")
    payload = json.loads(out[idx:])
    assert isinstance(payload["findings"], list)
    assert payload["findings"]
    assert payload["summary"]["errors"] >= 1
    assert payload["declarations"]
    # Each finding is a plain, JSON-serializable dict.
    for f in payload["findings"]:
        assert set(f) >= {"severity", "code", "message", "source", "path", "line"}


def test_cli_json_clean_project(clean_project, capsys):
    code = main(["check", "--json", str(clean_project)])
    out = capsys.readouterr().out
    assert code == 0
    idx = out.index("{\n")
    payload = json.loads(out[idx:])
    assert payload["summary"]["clean"] is True
    assert payload["findings"] == []


def test_cli_no_fail_returns_zero(_conflicting_project, capsys):
    root = _conflicting_project
    code = main(["check", "--no-fail", str(root)])
    out = capsys.readouterr().out
    assert code == 0
    # Findings are still reported, just not fatal.
    assert "DECL_MISMATCH" in out


def test_cli_version(capsys):
    code = main(["version"])
    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith("pyfloor ")
    assert "0.1.0" in out


def test_cli_declarations(clean_project, capsys):
    code = main(["declarations", str(clean_project)])
    out = capsys.readouterr().out
    assert code == 0
    assert "SOURCE" in out
    assert "pyproject.toml" in out


def test_cli_features_subcommand(_conflicting_project, capsys):
    # With a mismatch, features subcommand still runs and exits per findings.
    root = _conflicting_project
    code = main(["features", str(root)])
    capsys.readouterr()
    assert code in (0, 1)


def test_cli_features_detects_bad_code(write_project, capsys):
    # Floor 3.8, code uses a walrus (3.8 is fine) -> use match (3.10) instead.
    root = write_project(
        {
            ".python-version": "3.8\n",
            "app.py": ("def go(v):\n    match v:\n        case _:\n            return 0\n"),
        }
    )
    code = main(["features", str(root)])
    out = capsys.readouterr().out
    assert code == 1
    assert "match statement" in out


def test_cli_check_nonexistent_dir_exit_two(capsys):
    code = main(["check", "/no/such/path/xyzzy"])
    err = capsys.readouterr().err
    assert code == 2
    assert "not a directory" in err
