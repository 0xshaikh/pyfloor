"""pyfloor - a Python version floor auditor.

pyfloor scans a project for every place a Python version is declared
(pyproject.toml, setup.py/setup.cfg, .python-version, tox.ini, noxfile,
GitHub Actions workflows, Dockerfiles, Pipfile, .tool-versions), checks
that all declared floors are mutually consistent, verifies that the CI
matrix actually tests the declared floor, and checks whether the source
code uses syntax/API features that require a NEWER Python than the
declared floor.

Standard library only. Python 3.10+.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
