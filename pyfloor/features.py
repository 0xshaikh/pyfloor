"""Curated feature detection for pyfloor.

This module maps well-known Python syntax and stdlib API features to the
minimum Python version that introduced them. Detection is AST-based or
source-regex based. The set is deliberately curated; exhaustive stdlib
API detection is vermin's job.

Each FEATURES entry maps a feature name to a dict with:
    min_version  - the minimum Python version (major, minor) as a tuple
    label        - a human-readable description of the feature
    kind         - "ast" or "regex"
    ast_type     - (for kind "ast") the ast node class name to look for
    pattern      - (for kind "regex") a compiled regex searched in source

A feature may instead carry a custom ``detect`` callable taking
``(source, tree)`` and returning a list of ``(line, description)``.
"""

from __future__ import annotations

import ast
import inspect

# Minimum version helpers.
PY37 = (3, 7)
PY38 = (3, 8)
PY39 = (3, 9)
PY310 = (3, 10)
PY311 = (3, 11)


def _line_of(node: ast.AST) -> int:
    """Return the 1-based line of a node, or 0 if unknown."""
    return int(getattr(node, "lineno", 0) or 0)


def _find_by_ast_type(tree: ast.AST, type_name: str):
    """Yield (line, description) for every node of the given AST class."""
    for node in ast.walk(tree):
        if type(node).__name__ == type_name:
            yield _line_of(node), type_name


def _find_namedexpr(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.NamedExpr):
            yield _line_of(node), "walrus operator (:=)"


def _find_posonly(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for _arg in node.args.posonlyargs:
                yield _line_of(node), "positional-only parameter"


def _find_match(tree: ast.AST):
    for node in ast.walk(tree):
        if type(node).__name__ == "Match":
            yield _line_of(node), "match statement"


def _find_exceptstar(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.TryStar):
            yield _line_of(node), "except* (exception groups)"


def _find_tomllib(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "tomllib":
                    yield _line_of(node), "import tomllib"
        elif isinstance(node, ast.ImportFrom) and node.module == "tomllib":
            yield _line_of(node), "from tomllib import ..."


def _find_typing_self(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("typing", "typing_extensions"):
                    yield _line_of(node), "import typing"
        elif isinstance(node, ast.ImportFrom) and node.module in (
            "typing",
            "typing_extensions",
        ):
            for alias in node.names:
                if alias.name == "Self":
                    yield _line_of(node), "typing.Self"


def _find_union_pipe(tree: ast.AST):
    """PEP 604 union ``int | str`` in annotations."""
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            # Only flag if it looks like an annotation (either side is a
            # Name/Subscript/Attribute that names a type). We conservatively
            # flag any `X | Y` binop to avoid false negatives; this is a
            # curated heuristic.
            yield _line_of(node), "PEP 604 union type (X | Y)"


def _find_dict_union(tree: ast.AST):
    """PEP 584 dict union ``dict_a | dict_b``."""
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            left, right = node.left, node.right
            if isinstance(left, ast.Dict) or isinstance(right, ast.Dict):
                yield _line_of(node), "PEP 584 dict union (|)"


def _find_removeprefix_removesuffix(source: str, tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in (
            "removeprefix",
            "removesuffix",
        ):
            yield _line_of(node), "str." + node.attr


def _find_zoneinfo(source: str, tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "zoneinfo":
                    yield _line_of(node), "import zoneinfo"
        elif isinstance(node, ast.ImportFrom) and node.module == "zoneinfo":
            yield _line_of(node), "from zoneinfo import ..."


def _find_cache(source: str, tree: ast.AST):
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "cache"
            and isinstance(node.value, ast.Name)
            and node.value.id == "functools"
        ):
            yield _line_of(node), "functools.cache"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "functools":
                    yield _line_of(node), "import functools"
        elif isinstance(node, ast.ImportFrom) and node.module == "functools":
            for alias in node.names:
                if alias.name == "cache":
                    yield _line_of(node), "functools.cache"


def _find_graphlib(source: str, tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "graphlib":
                    yield _line_of(node), "import graphlib"
        elif isinstance(node, ast.ImportFrom) and node.module == "graphlib":
            yield _line_of(node), "from graphlib import ..."


def _find_bit_count(source: str, tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "bit_count":
            yield _line_of(node), "int.bit_count()"


def _find_math_comb_perm(source: str, tree: ast.AST):
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr in ("comb", "perm")
            and isinstance(node.value, ast.Name)
            and node.value.id == "math"
        ):
            yield _line_of(node), "math." + node.attr
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "math":
                    yield _line_of(node), "import math"
        elif isinstance(node, ast.ImportFrom) and node.module == "math":
            for alias in node.names:
                if alias.name in ("comb", "perm"):
                    yield _line_of(node), "math." + alias.name


def _find_protocol_literal(source: str, tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in (
            "typing",
            "typing_extensions",
        ):
            for alias in node.names:
                if alias.name in ("Protocol", "Literal"):
                    yield _line_of(node), "typing." + alias.name


def _find_dataclasses(source: str, tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "dataclasses":
                    yield _line_of(node), "import dataclasses"
        elif isinstance(node, ast.ImportFrom) and node.module == "dataclasses":
            yield _line_of(node), "from dataclasses import ..."


def _find_breakpoint(source: str, tree: ast.AST):
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "breakpoint"
        ):
            yield _line_of(node), "breakpoint()"


def _find_future_annotations(source: str, tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            for alias in node.names:
                if alias.name == "annotations":
                    yield _line_of(node), "from __future__ import annotations"


# Curated feature table. Key is the feature name.
FEATURES = {
    "match_statement": {
        "min_version": PY310,
        "label": "match statement (PEP 634)",
        "detect": _find_match,
    },
    "walrus": {
        "min_version": PY38,
        "label": "walrus operator := (PEP 572)",
        "detect": _find_namedexpr,
    },
    "positional_only": {
        "min_version": PY38,
        "label": "positional-only parameters (PEP 570)",
        "detect": _find_posonly,
    },
    "except_star": {
        "min_version": PY311,
        "label": "except* / exception groups (PEP 654)",
        "detect": _find_exceptstar,
    },
    "tomllib": {
        "min_version": PY311,
        "label": "tomllib module",
        "detect": _find_tomllib,
    },
    "typing_self": {
        "min_version": PY311,
        "label": "typing.Self (PEP 673)",
        "detect": _find_typing_self,
    },
    "pep604_union": {
        "min_version": PY310,
        "label": "PEP 604 union types (X | Y)",
        "detect": _find_union_pipe,
    },
    "pep584_dict_union": {
        "min_version": PY39,
        "label": "PEP 584 dict union (|)",
        "detect": _find_dict_union,
    },
    "str_removeprefix": {
        "min_version": PY39,
        "label": "str.removeprefix / str.removesuffix",
        "detect": _find_removeprefix_removesuffix,
    },
    "zoneinfo": {
        "min_version": PY39,
        "label": "zoneinfo module",
        "detect": _find_zoneinfo,
    },
    "functools_cache": {
        "min_version": PY39,
        "label": "functools.cache",
        "detect": _find_cache,
    },
    "graphlib": {
        "min_version": PY39,
        "label": "graphlib module",
        "detect": _find_graphlib,
    },
    "int_bit_count": {
        "min_version": PY38,
        "label": "int.bit_count()",
        "detect": _find_bit_count,
    },
    "math_comb_perm": {
        "min_version": PY38,
        "label": "math.comb / math.perm",
        "detect": _find_math_comb_perm,
    },
    "typing_protocol": {
        "min_version": PY38,
        "label": "typing.Protocol",
        "detect": _find_protocol_literal,
    },
    "typing_literal": {
        "min_version": PY38,
        "label": "typing.Literal",
        "detect": _find_protocol_literal,
    },
    "dataclasses": {
        "min_version": PY37,
        "label": "dataclasses module",
        "detect": _find_dataclasses,
    },
    "breakpoint": {
        "min_version": PY37,
        "label": "breakpoint() builtin",
        "detect": _find_breakpoint,
    },
    "future_annotations": {
        "min_version": PY37,
        "label": "from __future__ import annotations (PEP 563)",
        "detect": _find_future_annotations,
    },
}


def detect_feature_usage(file_path, source, tree):
    """Detect feature usage in one module.

    Args:
        file_path: path of the file (string).
        source: the module source text (string).
        tree: the parsed ``ast.AST`` (or None to skip AST-only checks).

    Returns:
        A list of dicts with keys ``feature``, ``min_version`` (tuple),
        ``line`` and ``file``.
    """
    results = []
    for feature_name, spec in FEATURES.items():
        detector = spec.get("detect")
        if detector is None:
            continue
        try:
            # Detectors may be declared as (tree) or (source, tree).
            if len(inspect.signature(detector).parameters) >= 2:  # noqa: PLR2004
                hits = detector(source, tree)
            else:
                hits = detector(tree)
            # Iterate INSIDE the try: generators walk the AST lazily, so a
            # None tree (unparseable source) raises only on first next().
            for line, description in hits:
                results.append(
                    {
                        "feature": feature_name,
                        "label": description or spec["label"],
                        "min_version": spec["min_version"],
                        "line": int(line or 0),
                        "file": file_path,
                    }
                )
        except Exception:  # noqa: S112 - a detector bug must not abort the scan
            continue
    return results
