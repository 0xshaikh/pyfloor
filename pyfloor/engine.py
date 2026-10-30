"""Parsing and analysis engine for pyfloor.

Collects Python version declarations from every common location, checks
mutual consistency, verifies the CI matrix tests the declared floor, and
flags source features that require a newer Python than the floor.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

# Allow importing features whether run as a package or as a script.
try:
    from . import features as _features
except ImportError:  # pragma: no cover - script mode
    import features as _features  # type: ignore

VERSION_RE = re.compile(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?")


def _normalize(value):
    """Normalize a version-ish value to an (int, int) floor tuple."""
    if isinstance(value, (tuple, list)) and value:
        return (int(value[0]), int(value[1]) if len(value) > 1 else 0)
    m = VERSION_RE.match(str(value).strip())
    if not m:
        return None
    major = int(m.group(1))
    minor = int(m.group(2) or 0)
    return (major, minor)


def _fmt_version(version):
    """Format a (major, minor) tuple as a string."""
    if version is None:
        return "?"
    return f"{version[0]}.{version[1]}"


def _fmt_tuple(value):
    return ".".join(str(part) for part in value)


def parse_version_spec(text):
    """Parse a version specifier into a (floor, ceil) tuple.

    Handles ``>=``, ``==``, ``~=``, ``>`` and bare versions. Returns
    ``(floor, ceil)`` where either may be None (open-ended). Ceil is only
    set for ``==`` and ``~=`` specs. Bare versions are treated as floors.
    """
    text = (text or "").strip()
    if not text:
        return (None, None)
    m = re.match(r"^(>=|>|==|~=)?\s*(\d+)(?:\.(\d+))?", text)
    if not m:
        return (None, None)
    op = m.group(1) or ""
    major = int(m.group(2))
    minor = int(m.group(3) or 0)
    floor = (major, minor)
    ceil = None
    if op == "==":
        ceil = (major, minor)
    elif op == "~=":
        # Compatible release: floor to next major (or next minor if
        # patch-pinned; we keep it simple: next minor).
        ceil = (major + 1, 0)
    elif op == ">":
        # Strictly greater: effective floor is one minor up.
        floor = (major, minor + 1) if minor < 99 else (major + 1, 0)  # noqa: PLR2004
        ceil = None
    return (floor, ceil)


def _parse_python_version_text(text):
    """Parse a bare version file (.python-version / .tool-versions)."""
    floor, _ = parse_version_spec(text)
    return floor


def read_pyproject(path):
    """Read requires-python from a pyproject.toml (tomllib or fallback)."""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    data = None
    try:
        import tomllib  # noqa: PLC0415 - only stdlib in 3.11+; fallback below

        data = tomllib.loads(text)
    except Exception:
        data = None
    if data is None:
        # Fallback: naive parse via configparser-ish regex for requires-python.
        m = re.search(r'requires-python\s*=\s*["\']([^"\']+)["\']', text)
        if not m:
            return None
        return m.group(1)
    project = data.get("project", {})
    if isinstance(project, dict):
        requires = project.get("requires-python")
        if requires is not None:
            return str(requires)
    return None


def read_python_version_file(path):
    """Read a bare version file (.python-version / .tool-versions)."""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return None
    # .tool-versions uses "python 3.11" lines; .python-version is a bare
    # version, possibly with multiple lines. Take the first python token.
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "python":  # noqa: PLR2004
            return parts[1]
        # Bare version line.
        if VERSION_RE.match(line):
            return line
    return None


def read_setup_py(path):
    """Extract python_requires from setup.py (regex)."""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"python_requires\s*=\s*[\"']([^\"']+)[\"']", text, re.DOTALL)
    if m:
        return m.group(1)
    # setup.cfg style.
    cfg = re.search(r"python_requires\s*=\s*([^\n]+)", text, re.IGNORECASE)
    if cfg:
        return cfg.group(1).strip()
    return None


def read_setup_cfg(path):
    """Extract python_requires from setup.cfg."""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"python_requires\s*=\s*([^\n]+)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def read_tox_ini(path):
    """Extract python versions from tox.ini envlist / env names."""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    versions = set()
    # envlist = py39, py310, py311
    m = re.search(r"^envlist\s*=\s*(.+)$", text, re.MULTILINE)
    if m:
        for token in re.split(r"[,\s]+", m.group(1)):
            pm = re.match(r"^py(\d)(\d+)$", token.strip())
            if pm:
                versions.add((int(pm.group(1)), int(pm.group(2))))
    # [testenv] deps/basepython lines: basepython = python3.10
    for m in re.finditer(r"basepython\s*=\s*(\S+)", text):
        pm = re.search(r"python(\d)(\d+)", m.group(1))
        if pm:
            versions.add((int(pm.group(1)), int(pm.group(2))))
    # factor-specific envs like py311-django42
    for m in re.finditer(r"^\s*\[testenv:.*?py(\d)(\d+)", text, re.MULTILINE):
        versions.add((int(m.group(1)), int(m.group(2))))
    return sorted(versions)


def read_noxfile(path):
    """Extract python versions from a noxfile.py (nox.session python=...)."""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    versions = set()
    for m in re.finditer(r"python\s*=\s*\[\s*([^\]]+)\]", text, re.DOTALL):
        for tok in re.findall(r"[\"'](?:python)?(\d)\.(\d+)[\"']", m.group(1)):
            versions.add((int(tok[0]), int(tok[1])))
    for m in re.finditer(r"python\s*=\s*[\"'](?:python)?(\d)\.(\d+)[\"']", text):
        versions.add((int(m.group(1)), int(m.group(2))))
    return sorted(versions)


def _extract_matrix_versions(text):
    """Find python versions inside a YAML matrix or setup-python uses."""
    versions = set()
    # python-version: [ "3.10", "3.12" ]  (matrix or setup-python)
    for m in re.finditer(r"python-version\s*:\s*\[([^\]]*)\]", text):
        for tok in re.findall(r"[\"']?(\d)\.(\d+)[\"']?", m.group(1)):
            versions.add((int(tok[0]), int(tok[1])))
    for m in re.finditer(r"python-version\s*:\s*[\"'](\d)\.(\d+)[\"']", text):
        versions.add((int(m.group(1)), int(m.group(2))))
    # matrix: python: [3.10, 3.12] - the re.finditer above already captured
    # matrix python-version lists, so nothing further is needed here.
    return sorted(versions)


def read_workflow(path):
    """Read Python versions from a GitHub Actions workflow YAML.

    Returns a list of (major, minor) tuples found in ``python-version``
    matrix entries and ``setup-python`` uses.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    versions = set()

    # matrix.python / python-version: [3.10, 3.12]
    for m in re.finditer(r"python\s*:\s*\[\s*([^\]]*?)\s*\]", text):
        for tok in re.findall(r"[\"']?(\d)\.(\d+)[\"']?", m.group(1)):
            versions.add((int(tok[0]), int(tok[1])))

    # python-version: [3.10, 3.12]
    for m in re.finditer(r"python-version\s*:\s*\[\s*([^\]]*?)\s*\]", text):
        for tok in re.findall(r"[\"']?(\d)\.(\d+)[\"']?", m.group(1)):
            versions.add((int(tok[0]), int(tok[1])))

    # python-version: "3.10"
    for m in re.finditer(r"python-version\s*:\s*[\"'](\d)\.(\d+)[\"']", text):
        versions.add((int(m.group(1)), int(m.group(2))))

    # python-version: 3.10  (bare, common in matrix rows)
    for m in re.finditer(r"python-version\s*:\s*(\d)\.(\d+)", text):
        versions.add((int(m.group(1)), int(m.group(2))))

    # setup-python with python-version: '3.10'
    return sorted(versions)


def read_dockerfile(path):
    """Read FROM python:X.Y from a Dockerfile. Returns list of versions."""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    versions = []
    for m in re.finditer(r"FROM\s+python:(\d+)\.(\d+)", text):
        versions.append((int(m.group(1)), int(m.group(2))))
    return versions


def read_pipfile(path):
    """Read the python_version from a Pipfile."""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"python_version\s*=\s*[\"'](\d+)\.(\d+)[\"']", text)
    if not m:
        return None
    return f"{m.group(1)}.{m.group(2)}"


def read_tool_versions(path):
    """Read python version from a .tool-versions file."""
    return read_python_version_file(path)


def collect_declarations(root):  # noqa: PLR0912, PLR0915 - handles 8+ manifest types
    """Collect every version declaration site under ``root``.

    Returns a list of dicts with keys ``source``, ``path``, ``floor``,
    ``raw``, and ``ci`` (list of tested versions) / ``line`` where known.
    """
    root = Path(root).resolve()
    declarations = []

    def add(source, path, floor, raw, extra=None):
        if floor is None:
            return
        entry = {
            "source": source,
            "path": str(Path(path).resolve().relative_to(root))
            if _is_relative(Path(path).resolve(), root)
            else str(Path(path).resolve()),
            "floor": tuple(floor),
            "raw": raw,
        }
        if extra:
            entry.update(extra)
        declarations.append(entry)

    def _is_relative(p, base):
        try:
            p.relative_to(base)
            return True
        except ValueError:
            return False

    # pyproject.toml
    for p in [root / "pyproject.toml"]:
        if p.is_file():
            raw = read_pyproject(p)
            if raw:
                floor, _ = parse_version_spec(raw)
                add("pyproject.toml", p, floor, raw)

    # setup.py / setup.cfg
    for name in ("setup.py", "setup.cfg"):
        p = root / name
        if p.is_file():
            raw = read_setup_py(p) if name == "setup.py" else read_setup_cfg(p)
            if raw:
                floor, _ = parse_version_spec(raw)
                add(name, p, floor, raw)

    # .python-version
    p = root / ".python-version"
    if p.is_file():
        raw = read_python_version_file(p)
        if raw:
            floor, _ = parse_version_spec(raw)
            add(".python-version", p, floor, raw)

    # .tool-versions
    p = root / ".tool-versions"
    if p.is_file():
        raw = read_tool_versions(p)
        if raw:
            floor, _ = parse_version_spec(raw)
            add(".tool-versions", p, floor, raw)

    # tox.ini
    p = root / "tox.ini"
    if p.is_file():
        versions = read_tox_ini(p)
        if versions:
            add(
                "tox.ini",
                p,
                min(versions),
                ",".join(_fmt_tuple(v) for v in versions),
                {"ci": versions},
            )

    # noxfile.py / noxfile
    for name in ("noxfile.py", "noxfile"):
        p = root / name
        if p.is_file():
            versions = read_noxfile(p)
            if versions:
                add(
                    name,
                    p,
                    min(versions),
                    ",".join(_fmt_tuple(v) for v in versions),
                    {"ci": versions},
                )

    # Pipfile
    p = root / "Pipfile"
    if p.is_file():
        raw = read_pipfile(p)
        if raw:
            floor, _ = parse_version_spec(raw)
            add("Pipfile", p, floor, raw)

    # GitHub Actions workflows
    workflows = list((root / ".github" / "workflows").glob("*.yml")) + list(
        (root / ".github" / "workflows").glob("*.yaml")
    )
    for wf in workflows:
        versions = read_workflow(wf)
        if versions:
            add(
                wf.name,
                wf,
                min(versions),
                ",".join(_fmt_tuple(v) for v in versions),
                {"ci": versions},
            )

    # Dockerfile(s)
    for name in ("Dockerfile",):
        p = root / name
        if p.is_file():
            versions = read_dockerfile(p)
            if versions:
                add(
                    name,
                    p,
                    min(versions),
                    ",".join(_fmt_tuple(v) for v in versions),
                    {"ci": versions},
                )

    # Recursively search for setup.py, Dockerfile etc. in subdirs.
    for p in sorted(root.rglob("Dockerfile*")):
        if p.parent == root:
            continue
        versions = read_dockerfile(p)
        if versions:
            add(
                str(p.relative_to(root)),
                p,
                min(versions),
                ",".join(_fmt_tuple(v) for v in versions),
                {"ci": versions},
            )

    for p in sorted(root.rglob("setup.py")):
        if p.parent == root:
            continue
        raw = read_setup_py(p)
        if raw:
            floor, _ = parse_version_spec(raw)
            add(str(p.relative_to(root)), p, floor, raw)

    for p in sorted(root.rglob("tox.ini")):
        if p.parent == root:
            continue
        versions = read_tox_ini(p)
        if versions:
            add(
                str(p.relative_to(root)),
                p,
                min(versions),
                ",".join(_fmt_tuple(v) for v in versions),
                {"ci": versions},
            )

    return declarations


def _collect_python_files(
    root,
    exclude_dirs=(
        "venv",
        ".venv",
        "site-packages",
        ".git",
        "node_modules",
        "__pycache__",
    ),
):
    """Collect .py files under root, skipping common noise dirs."""
    root = Path(root)
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for fname in filenames:
            if fname.endswith(".py"):
                files.append(Path(dirpath) / fname)
    return sorted(files)


def _check_code(root, floor):
    """Run feature detection over source files, return finding dicts."""
    findings = []
    files = _collect_python_files(root)
    floor = tuple(floor)
    for path in files:
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            # Can't parse (maybe newer syntax than our interpreter). Try to
            # still run regex-only detectors by passing a dummy tree.
            tree = None
        for hit in _features.detect_feature_usage(str(path), source, tree):
            min_version = tuple(hit["min_version"])
            if min_version > floor:
                findings.append(
                    {
                        "severity": "error",
                        "code": "CODE_NEEDS_NEWER",
                        "message": ("{} requires Python {}.{} but project floor is {}.{}").format(
                            hit["label"],
                            min_version[0],
                            min_version[1],
                            floor[0],
                            floor[1],
                        ),
                        "source": str(path.relative_to(root))
                        if _is_relative(path, root)
                        else str(path),
                        "path": str(path),
                        "line": hit["line"],
                        "extra": {
                            "feature": hit["feature"],
                            "min_version": min_version,
                            "floor": floor,
                        },
                    }
                )
    return findings


def analyze_project(root):
    """Run the full audit against ``root``.

    Returns a dict with keys ``declarations``, ``findings``, ``summary``.
    """
    root = Path(root).resolve()
    declarations = collect_declarations(root)
    findings = []

    # Determine the declared floor: most conservative (lowest) among sites.
    declared_floors = [d["floor"] for d in declarations]
    floor = min(declared_floors) if declared_floors else None

    # DECL_MISMATCH: different sites declare different floors.
    if declared_floors:
        unique = sorted(set(declared_floors))
        if len(unique) > 1:
            # Group by floor for a readable message.
            groups = {}
            for d in declarations:
                groups.setdefault(d["floor"], []).append(d["source"])
            detail = "; ".join(
                "{} ({} in {})".format(_fmt_version(f), ", ".join(srcs), len(srcs))
                for f, srcs in sorted(groups.items())
            )
            findings.append(
                {
                    "severity": "error",
                    "code": "DECL_MISMATCH",
                    "message": "conflicting declared Python floors: " + detail,
                    "source": "project",
                    "path": str(root),
                    "line": 0,
                    "extra": {"floors": [list(f) for f in unique]},
                }
            )

    # FLOOR_NOT_TESTED: floor not present in any CI matrix.
    ci_versions = set()
    for d in declarations:
        for v in d.get("ci", []) or []:
            ci_versions.add(tuple(v))
    if floor is not None and ci_versions and floor not in ci_versions:
        findings.append(
            {
                "severity": "error",
                "code": "FLOOR_NOT_TESTED",
                "message": ("declared floor {} is not present in CI matrix (tested: {})").format(
                    _fmt_version(floor),
                    ", ".join(sorted(_fmt_version(v) for v in ci_versions)),
                ),
                "source": "ci",
                "path": str(root),
                "line": 0,
                "extra": {
                    "floor": list(floor),
                    "tested": [list(v) for v in sorted(ci_versions)],
                },
            }
        )

    # CODE_NEEDS_NEWER
    if floor is not None:
        code_findings = _check_code(root, floor)
        findings.extend(code_findings)

    # Sort findings: errors first, then by file/line.
    findings.sort(key=lambda f: (0 if f["severity"] == "error" else 1, f["path"], f["line"]))

    n_errors = sum(1 for f in findings if f["severity"] == "error")
    n_warnings = sum(1 for f in findings if f["severity"] == "warning")

    summary = {
        "root": str(root),
        "declaration_count": len(declarations),
        "floor": _fmt_version(floor) if floor else None,
        "findings_count": len(findings),
        "errors": n_errors,
        "warnings": n_warnings,
        "clean": len(findings) == 0,
    }

    return {
        "declarations": declarations,
        "findings": findings,
        "summary": summary,
    }


def _is_relative(p, base):
    try:
        p.relative_to(base)
        return True
    except ValueError:
        return False
