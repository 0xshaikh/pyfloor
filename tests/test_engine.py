"""Tests for pyfloor.engine: declaration parsing, collection, and analysis."""

from __future__ import annotations

from pyfloor import engine


# ---------------------------------------------------------------------------
# parse_version_spec
# ---------------------------------------------------------------------------
def test_parse_spec_ge():
    assert engine.parse_version_spec(">=3.9") == ((3, 9), None)


def test_parse_spec_eq():
    assert engine.parse_version_spec("==3.10") == ((3, 10), (3, 10))


def test_parse_spec_compatible():
    assert engine.parse_version_spec("~=3.11") == ((3, 11), (4, 0))


def test_parse_spec_bare():
    assert engine.parse_version_spec("3.9") == ((3, 9), None)


def test_parse_spec_range():
    # A compound spec: the floor is the lower bound.
    assert engine.parse_version_spec(">=3.9,<3.13") == ((3, 9), None)


def test_parse_spec_empty():
    assert engine.parse_version_spec("") == (None, None)
    assert engine.parse_version_spec("   ") == (None, None)


def test_parse_spec_greater_than():
    # Strictly greater: floor bumps one minor up.
    assert engine.parse_version_spec(">3.8") == ((3, 9), None)


# ---------------------------------------------------------------------------
# Declaration readers
# ---------------------------------------------------------------------------
def test_read_pyproject(write_project):
    root = write_project({"pyproject.toml": '[project]\nrequires-python = ">=3.9"\n'})
    assert engine.read_pyproject(root / "pyproject.toml") == ">=3.9"


def test_read_python_version_file(write_project):
    root = write_project({".python-version": "3.12\n"})
    assert engine.read_python_version_file(root / ".python-version") == "3.12"


def test_read_python_version_tool_versions(write_project):
    root = write_project({".tool-versions": "python 3.11\nnodejs 20.0.0\n"})
    assert engine.read_tool_versions(root / ".tool-versions") == "3.11"


def test_read_workflow_matrix(write_project):
    root = write_project(
        {
            ".github/workflows/ci.yml": (
                "name: CI\n"
                "on: [push]\n"
                "jobs:\n"
                "  test:\n"
                "    strategy:\n"
                "      matrix:\n"
                "        python-version: ['3.11', '3.12']\n"
            )
        }
    )
    versions = engine.read_workflow(root / ".github/workflows/ci.yml")
    assert versions == [(3, 11), (3, 12)]


def test_read_workflow_single_python_version(write_project):
    root = write_project(
        {
            ".github/workflows/ci.yml": (
                "jobs:\n  test:\n    steps:\n"
                "      - uses: actions/setup-python@v5\n"
                "        with:\n"
                "          python-version: '3.10'\n"
            )
        }
    )
    versions = engine.read_workflow(root / ".github/workflows/ci.yml")
    assert versions == [(3, 10)]


def test_read_dockerfile(write_project):
    root = write_project({"Dockerfile": "FROM python:3.10-slim\n\nRUN pip install .\n"})
    assert engine.read_dockerfile(root / "Dockerfile") == [(3, 10)]


def test_read_setup_py(write_project):
    root = write_project({"setup.py": 'setup(python_requires=">=3.9")\n'})
    assert engine.read_setup_py(root / "setup.py") == ">=3.9"


def test_read_tox_ini(write_project):
    root = write_project({"tox.ini": "[tox]\nenvlist = py39, py310, py311\n"})
    assert engine.read_tox_ini(root / "tox.ini") == [(3, 9), (3, 10), (3, 11)]


def test_read_pipfile(write_project):
    root = write_project({"Pipfile": '[[source]]\npython_version = "3.10"\n'})
    assert engine.read_pipfile(root / "Pipfile") == "3.10"


# ---------------------------------------------------------------------------
# collect_declarations
# ---------------------------------------------------------------------------
def test_collect_declarations_count(clean_project):
    decls = engine.collect_declarations(clean_project)
    sources = {d["source"] for d in decls}
    assert "pyproject.toml" in sources
    assert ".python-version" in sources
    assert any("ci.yml" in s for s in sources)


def test_collect_declarations_floor(clean_project):
    decls = engine.collect_declarations(clean_project)
    floors = {d["floor"] for d in decls}
    # All three sites agree on floor 3.9.
    assert floors == {(3, 9)}


# ---------------------------------------------------------------------------
# Finding detection
# ---------------------------------------------------------------------------
def test_decl_mismatch(write_project):
    root = write_project(
        {
            "pyproject.toml": '[project]\nrequires-python = ">=3.9"\n',
            ".python-version": "3.12\n",
        }
    )
    result = engine.analyze_project(root)
    codes = {f["code"] for f in result["findings"]}
    assert "DECL_MISMATCH" in codes


def test_floor_not_tested(write_project):
    # Floor is 3.9, but the CI matrix only tests 3.11 and 3.12.
    root = write_project(
        {
            "pyproject.toml": '[project]\nrequires-python = ">=3.9"\n',
            ".github/workflows/ci.yml": (
                "jobs:\n  test:\n    strategy:\n      matrix:\n"
                "        python-version: ['3.11', '3.12']\n"
            ),
        }
    )
    result = engine.analyze_project(root)
    codes = {f["code"] for f in result["findings"]}
    assert "FLOOR_NOT_TESTED" in codes
    # The offending floor should be called out.
    assert any("3.9" in f["message"] for f in result["findings"])


def test_code_needs_newer_match(write_project):
    # match statement (Python 3.10+) while the floor is 3.8.
    root = write_project(
        {
            ".python-version": "3.8\n",
            "app.py": (
                "def classify(value):\n"
                "    match value:\n"
                "        case 1:\n"
                "            return 'one'\n"
                "        case _:\n"
                "            return 'other'\n"
            ),
        }
    )
    result = engine.analyze_project(root)
    codes = {f["code"] for f in result["findings"]}
    assert "CODE_NEEDS_NEWER" in codes


def test_clean_project_zero_findings(clean_project):
    result = engine.analyze_project(clean_project)
    assert result["findings"] == []
    assert result["summary"]["clean"] is True
    assert result["summary"]["errors"] == 0


def test_summary_floor(clean_project):
    result = engine.analyze_project(clean_project)
    assert result["summary"]["floor"] == "3.9"
    assert result["summary"]["declaration_count"] >= 3
