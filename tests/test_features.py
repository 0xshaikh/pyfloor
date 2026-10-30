"""Tests for pyfloor.features: curated feature detection."""

from __future__ import annotations

import ast
import sys

import pytest

from pyfloor import features


def _detect(source):
    tree = ast.parse(source)
    return features.detect_feature_usage("app.py", source, tree)


def test_walrus_detected():
    hits = _detect("if (n := 10) > 5:\n    pass\n")
    assert any(h["feature"] == "walrus" and h["min_version"] == (3, 8) for h in hits)


@pytest.mark.skipif(sys.version_info < (3, 11), reason="except* syntax requires Python 3.11+")
def test_except_star_detected():
    hits = _detect("try:\n    pass\nexcept* ValueError:\n    pass\n")
    assert any(h["feature"] == "except_star" and h["min_version"] == (3, 11) for h in hits)


def test_tomllib_detected():
    hits = _detect("import tomllib\n")
    assert any(h["feature"] == "tomllib" and h["min_version"] == (3, 11) for h in hits)


def test_dict_union_detected():
    hits = _detect("merged = {'a': 1} | {'b': 2}\n")
    assert any(h["feature"] == "pep584_dict_union" and h["min_version"] == (3, 9) for h in hits)


def test_str_removeprefix_detected():
    hits = _detect("name = 'demo'.removeprefix('d')\n")
    assert any(h["feature"] == "str_removeprefix" and h["min_version"] == (3, 9) for h in hits)


def test_match_statement_detected():
    hits = _detect("match 1:\n    case _:\n        pass\n")
    assert any(h["feature"] == "match_statement" and h["min_version"] == (3, 10) for h in hits)


def test_pep604_union_detected():
    hits = _detect("def f(x: int | str):\n    return x\n")
    assert any(h["feature"] == "pep604_union" and h["min_version"] == (3, 10) for h in hits)


def test_plain_code_no_hits():
    hits = _detect("def add(a, b):\n    return a + b\n")
    assert hits == []


def test_detect_invalid_source_safe():
    # A syntax error should not raise; detection degrades gracefully.
    source = "def broken(:\n    pass\n"
    hits = features.detect_feature_usage("app.py", source, None)
    assert isinstance(hits, list)


def test_feature_usage_reports_line():
    hits = _detect("x = 1\nif (n := 2) > 1:\n    pass\n")
    walrus = [h for h in hits if h["feature"] == "walrus"]
    assert walrus and walrus[0]["line"] == 2
    assert walrus[0]["file"] == "app.py"
