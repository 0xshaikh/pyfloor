# Contributing to pyfloor

Thanks for contributing! This project is small, focused, and dependency-free by
design. Please keep it that way.

## Development setup

```bash
git clone https://github.com/0xshaikh/pyfloor.git
cd pyfloor
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

`[dev]` installs pytest, ruff, and any other tooling required for development.

## Running tests

```bash
pytest
```

Run a single test file:

```bash
pytest tests/test_engine.py
```

## Linting

```bash
ruff check .
ruff format --check .
```

## Commit message convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/).
Commit messages take the form:

```
<type>(<scope>): <subject>
```

- `type`: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `perf`, `style`
- `scope`: optional, e.g. `engine`, `cli`, `parsers`, `reporter`
- `subject`: imperative, lowercase, no trailing period, <= 72 characters

Examples:

```
feat(engine): detect match statement above declared floor
fix(parsers): read python_requires from setup.cfg with extras
docs: clarify DECL_MISMATCH semantics
```

## What to keep in mind

- **Zero runtime dependencies.** New functionality must use only the standard
  library.
- **Python 3.10+ only.** The tool targets 3.10 and newer; do not use features
  newer than 3.10 in the source.
- **Read-only.** pyfloor must never modify the tree it scans.
- **Tests.** Every new finding code or parser should come with tests in
  `tests/` and a matching sample under `samples/`.

## Reporting bugs and opening PRs

Open an issue first if the change is non-trivial, then a pull request. Keep
changes small and focused. Run `pytest` and `ruff check .` before submitting.
