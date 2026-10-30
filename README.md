# pyfloor

Audit the Python version floor of your project before it silently breaks in CI

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](https://github.com/0xshaikh/pyfloor/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-zero-informational.svg)](https://pypi.org/project/pyfloor/)

Your `pyproject.toml` says `requires-python = ">=3.9"`. CI only runs 3.11 and 3.12.
Docker builds on `python:3.12`. Someone merged a `match` statement and an `X | Y`
type annotation. It works on your machine. It will break the first time anyone
installs it on an interpreter that actually honors the floor.

The floor is a promise. pyfloor checks whether your project keeps it.

## Install

Zero runtime dependencies, pure standard library, Python 3.10+.

```bash
# One-shot, no install pollution
pipx run pyfloor check .

# Or install it
pip install pyfloor
pyfloor --help
```

## Quick start

```bash
cd /path/to/your/project
pyfloor check            # scan the current directory
pyfloor check --json     # machine-readable findings
pyfloor check --no-fail  # report but always exit 0
pyfloor check --strict   # also flag non-fatal inconsistencies
```

A realistic run against a project whose floor is out of sync with reality:

```
$ pyfloor check .
pyfloor audit: /home/you/project
Declared floor: 3.9
Declaration sites: 3
Findings: 3

SOURCE           PATH                      FLOOR  RAW        CI
---------------  ------------------------  -----  ---------  ---------
pyproject.toml   pyproject.toml            3.9    >=3.9
Dockerfile       Dockerfile                3.12   3.12
ci.yml           .github/workflows/ci.yml  3.11   3.11,3.12  3.11,3.12

[FAIL] DECL_MISMATCH: conflicting declared Python floors: 3.9 (pyproject.toml); 3.12 (Dockerfile); 3.11 (ci.yml)
[FAIL] FLOOR_NOT_TESTED: declared floor 3.9 is not present in CI matrix (tested: 3.11, 3.12)
[FAIL] CODE_NEEDS_NEWER: match statement requires Python 3.10 but project floor is 3.9  (src/project/main.py:9)
exit 1
```

## What it detects

pyfloor produces three kinds of findings:

| Code | Meaning |
| --- | --- |
| `DECL_MISMATCH` | Two places declare different Python floors (e.g. `pyproject.toml` says `>=3.9` but `Dockerfile` pins `3.12`). |
| `FLOOR_NOT_TESTED` | The declared floor is not present in the CI matrix (e.g. floor is 3.9, CI only runs 3.11/3.12). |
| `CODE_NEEDS_NEWER` | Source code uses a syntax or API feature that requires a newer Python than the declared floor (e.g. a `match` statement with a 3.9 floor). |

Concrete examples:

```python
# DECL_MISMATCH: pyproject.toml requires-python = ">=3.9"
#                Dockerfile FROM python:3.12
#
# FLOOR_NOT_TESTED: floor >=3.9, but .github/workflows/ci.yml matrix: [3.11, 3.12]
#
# CODE_NEEDS_NEWER: floor >=3.9, and src/main.py contains:
match value:  # match requires 3.10+
    case 1:
        ...
```

## Features

| Feature | Description |
| --- | --- |
| Multi-manifest scan | Reads version floors from `pyproject.toml`, `setup.cfg`, `setup.py`, `.python-version`, `tox.ini`, `noxfile.py`, GitHub Actions workflows, `Dockerfile`, `Pipfile`, and `.tool-versions`. |
| CI floor coverage | Verifies the CI matrix actually runs the declared floor, so the floor is exercised, not just claimed. |
| Code feature floor check | Flags source syntax/API features that need a newer Python than the declared floor. |
| JSON output | `--json` emits findings as machine-readable JSON for gates and dashboards. |
| CI gate | Exit 1 on any finding (0 when clean), or `--no-fail` to report only. |
| Zero dependencies | Pure standard library, installable anywhere Python 3.10+ runs. |
| Read-only | Never modifies your files or your manifests. |

## Manifest types scanned

| Manifest | Floor source |
| --- | --- |
| `pyproject.toml` | `[project] requires-python` |
| `setup.cfg` | `python_requires` |
| `setup.py` | `python_requires=` argument |
| `.python-version` | the pinned version |
| `tox.ini` / `noxfile.py` | `basepython` / `pyX.Y` environments |
| `.github/workflows/*.yml` | `matrix.python-version` / `setup-python` |
| `Dockerfile` | `FROM python:X.Y` |
| `Pipfile` | `python_version` |
| `.tool-versions` | the `python` line |

## CLI

### `pyfloor check [path]`

Scan a project (default: current directory) and report findings.

```bash
$ pyfloor check .
pyfloor audit: /home/you/project
Declared floor: 3.9
Declaration sites: 3
Findings: 1

[FAIL] CODE_NEEDS_NEWER: match statement requires Python 3.10 but project floor is 3.9  (src/project/main.py:9)
```

Exit 1 if any finding, 0 if clean. Flags: `--json`, `--no-fail`, `--strict`.

### `pyfloor declarations [path]`

List every version floor declared across all manifests.

```bash
$ pyfloor declarations .
Version declaration sites under /home/you/project
SOURCE           PATH                      FLOOR  RAW        CI
---------------  ------------------------  -----  ---------  ---------
pyproject.toml   pyproject.toml            3.9    >=3.9
Dockerfile       Dockerfile                3.12   3.12
ci.yml           .github/workflows/ci.yml  3.11   3.11,3.12  3.11,3.12
```

### `pyfloor features [path]`

Scan source code for features that may need a newer Python than the floor.

```bash
$ pyfloor features .
Feature usage requiring newer Python than floor 3.9:
  [3] 10 (/home/you/project/src/project/main.py:9): match statement requires Python 3.10 but project floor is 3.9
  [3] 10 (/home/you/project/src/project/utils.py:21): PEP 604 union type (X | Y) requires Python 3.10 but project floor is 3.9
```

### `pyfloor version`

Print the installed pyfloor version.

```bash
$ pyfloor version
pyfloor 0.1.0
```

## How it works

Manifest parsers read every version declaration, the engine compares them against
each other and the CI matrix, a curated feature detector scans source files, and a
reporter formats the findings.

```
 pyproject.toml --+
 setup.cfg -------+
 setup.py --------+
 .python-version--+
 tox.ini ---------+    +-----------+    +---------------+    +-----------+
 noxfile.py ------+--->|  Manifest |--->|    Engine      |--->|  Reporter |
 .github/ --------+    |  parsers  |    |  (consistency, |    | (table /  |
 Dockerfile ------+    +-----------+    |   CI floor,    |    |   JSON)   |
 Pipfile ---------+                     |   code floor)  |    +-----------+
 .tool-versions --+                     +---------------+
```

## Sample output

Against the bundled `samples/broken` project, a full run:

```bash
$ pyfloor check samples/broken
pyfloor audit: /home/you/pyfloor/samples/broken
Declared floor: 3.9
Declaration sites: 3
Findings: 4

SOURCE           PATH                      FLOOR  RAW        CI
---------------  ------------------------  -----  ---------  ---------
pyproject.toml   pyproject.toml            3.9    >=3.9
.python-version  .python-version           3.9    3.9
ci.yml           .github/workflows/ci.yml  3.11   3.11,3.12  3.11,3.12

[FAIL] DECL_MISMATCH: conflicting declared Python floors: 3.9 (pyproject.toml, .python-version in 2); 3.11 (ci.yml in 1)
[FAIL] FLOOR_NOT_TESTED: declared floor 3.9 is not present in CI matrix (tested: 3.11, 3.12)
[FAIL] CODE_NEEDS_NEWER: match statement requires Python 3.10 but project floor is 3.9  (src/broken.py:9)
[FAIL] CODE_NEEDS_NEWER: import tomllib requires Python 3.11 but project floor is 3.9  (src/broken.py:19)
exit 1
```

## Why not vermin?

[vermin](https://pypi.org/project/vermin/) does exhaustive stdlib API feature
detection and is excellent at it. pyfloor is not a replacement.

pyfloor focuses on a different problem: **cross-file version declaration
consistency and CI floor coverage**. It asks "do all the places you claim a floor
actually agree, and does CI actually test that floor?" That is a coherence audit
of your manifest set, which vermin does not do. On top of that, pyfloor runs a
**curated feature subset** covering the most common modern syntax features
(`match`, `X | Y` unions, `except*`, positional-only params, walrus, and
similar). For exhaustive stdlib API detection, run vermin.

| | pyfloor | vermin |
| --- | --- | --- |
| Cross-manifest floor consistency | Yes | No |
| CI matrix floor coverage | Yes | No |
| Syntax feature detection | Curated subset | Broad |
| Exhaustive stdlib API detection | No | Yes |
| Read-only | Yes | Yes |

## Limitations

Honest caveats:

- **Curated feature subset, not exhaustive.** pyfloor detects a curated set of
  syntax features, not every stdlib API. For exhaustive API detection, use vermin.
- **Age from files only.** The floor is derived from manifest files present in the
  scanned tree; if a manifest is absent, that declaration is simply not seen.
- **Ignores renames.** No history or git integration (pyfloor never uses git), so
  it reports the tree as it is now, not how it evolved.
- **Git not required.** pyfloor never calls git; it works on any file tree.

## License

MIT. See [LICENSE](LICENSE).
