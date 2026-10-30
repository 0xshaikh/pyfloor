# Changelog

All notable changes to pyfloor are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/) and this
project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-30

Initial release.

### Added

- `pyfloor check [path]` command: scans a project and reports findings.
  - `--json` for machine-readable output.
  - `--no-fail` to report but always exit 0.
  - `--strict` to also flag non-fatal inconsistencies.
- `pyfloor declarations [path]` command: lists every version floor declared
  across all supported manifests.
- `pyfloor features [path]` command: scans source code for syntax/API features
  that need a newer Python than the declared floor.
- `pyfloor version` command: prints the installed version.
- Multi-manifest scanning of `pyproject.toml`, `setup.cfg`, `setup.py`,
  `.python-version`, `tox.ini`, `noxfile.py`, GitHub Actions workflows,
  `Dockerfile`, `Pipfile`, and `.tool-versions`.
- Three finding codes:
  - `DECL_MISMATCH`: two places declare different Python floors.
  - `FLOOR_NOT_TESTED`: the declared floor is absent from the CI matrix.
  - `CODE_NEEDS_NEWER`: source code requires a newer Python than the floor.
- Exit code 1 on any finding, 0 when clean.
- Zero runtime dependencies; pure standard library, Python 3.10+.

[0.1.0]: https://github.com/0xshaikh/pyfloor/releases/tag/v0.1.0
