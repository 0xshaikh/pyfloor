"""Command-line interface for pyfloor.

Uses plain ASCII output only (Windows cp1252 safe).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from . import (
        __version__,
        engine,
    )
except ImportError:  # pragma: no cover - script mode
    import __version__  # type: ignore
    import engine  # type: ignore


def _reconfigure_stdout():
    """Make stdout/stderr UTF-8 tolerant on non-tty (e.g. piped) output."""
    for stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: S110 - stream reconfigure is best-effort
            pass


def _format_version(version):
    if version is None:
        return "?"
    return f"{version[0]}.{version[1]}"


def _print_table(headers, rows):
    """Print an ASCII-aligned table without box-drawing glyphs."""
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    # Header.
    header_line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
    print(header_line)
    print("  ".join("-" * widths[i] for i in range(len(headers))))
    for row in rows:
        print("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)))


def _render_findings(findings, strict=False):
    """Render findings to ASCII lines. Returns (lines, exit_status)."""
    lines = []
    has_error = False
    for f in findings:
        sev = f["severity"]
        if sev == "error":
            tag = "FAIL"
            has_error = True
        elif sev == "warning":
            tag = "WARN"
        else:
            tag = "INFO"
        loc = f.get("path", "")
        if f.get("line"):
            loc = "{}:{}".format(loc, f["line"])
        lines.append(
            "[{tag}] {code}: {message}  ({source})".format(
                tag=tag,
                code=f["code"],
                message=f["message"],
                source=loc or f.get("source", ""),
            )
        )
    return lines, has_error


def cmd_check(args):
    root = Path(args.path)
    if not root.is_dir():
        print(f"ERROR: not a directory: {root}", file=sys.stderr)
        return 2
    result = engine.analyze_project(root)
    findings = result["findings"]
    decls = result["declarations"]
    summary = result["summary"]
    has_error = any(f["severity"] == "error" for f in findings)

    if args.strict:
        # Also treat warnings as failures.
        has_error = has_error or any(f["severity"] == "warning" for f in findings)

    if args.json:
        payload = {
            "root": str(root.resolve()),
            "summary": summary,
            "declarations": [
                {
                    "source": d["source"],
                    "path": d["path"],
                    "floor": list(d["floor"]),
                    "raw": d.get("raw", ""),
                    "ci": [list(v) for v in (d.get("ci") or [])],
                }
                for d in decls
            ],
            "findings": [
                {
                    "severity": f["severity"],
                    "code": f["code"],
                    "message": f["message"],
                    "source": f.get("source", ""),
                    "path": f.get("path", ""),
                    "line": f.get("line", 0),
                    "extra": f.get("extra", {}),
                }
                for f in findings
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        if has_error and not args.no_fail:
            return 1
        return 0

    print(f"pyfloor audit: {root.resolve()}")
    print("Declared floor: {}".format(summary["floor"] or "none found"))
    print("Declaration sites: {}".format(summary["declaration_count"]))
    print("Findings: {}".format(summary["findings_count"]))

    if decls:
        print()
        rows = []
        for d in decls:
            ci = d.get("ci")
            ci_str = ",".join(_format_version(v) for v in ci) if ci else ""
            rows.append(
                (
                    d["source"],
                    d["path"],
                    _format_version(d["floor"]),
                    d.get("raw", ""),
                    ci_str,
                )
            )
        _print_table(["SOURCE", "PATH", "FLOOR", "RAW", "CI"], rows)

    if findings:
        print()
        lines, _ = _render_findings(findings, strict=args.strict)
        for line in lines:
            print(line)

    if has_error and not args.no_fail:
        return 1
    return 0


def cmd_declarations(args):
    root = Path(args.path)
    if not root.is_dir():
        print(f"ERROR: not a directory: {root}", file=sys.stderr)
        return 2
    decls = engine.collect_declarations(root)
    print(f"Version declaration sites under {root.resolve()}")
    if not decls:
        print("  (none found)")
        return 0
    rows = []
    for d in decls:
        ci = d.get("ci")
        ci_str = ",".join(_format_version(v) for v in ci) if ci else ""
        rows.append(
            (
                d["source"],
                d["path"],
                _format_version(d["floor"]),
                d.get("raw", ""),
                ci_str,
            )
        )
    _print_table(["SOURCE", "PATH", "FLOOR", "RAW", "CI"], rows)
    return 0


def cmd_features(args):
    root = Path(args.path)
    if not root.is_dir():
        print(f"ERROR: not a directory: {root}", file=sys.stderr)
        return 2
    result = engine.analyze_project(root)
    decls = result["declarations"]
    floors = [d["floor"] for d in decls]
    floor = min(floors) if floors else (3, 7)
    # Run code check only (reuse analyze but filter findings).
    code_findings = [f for f in result["findings"] if f["code"] == "CODE_NEEDS_NEWER"]
    print(f"Feature usage requiring newer Python than floor {_format_version(floor)}:")
    if not code_findings:
        print("  (no problematic features found)")
        return 0
    for f in code_findings:
        loc = f.get("path", "")
        if f.get("line"):
            loc = "{}:{}".format(loc, f["line"])
        print(
            "  [{}] {} ({}): {}".format(
                f["extra"]["min_version"][0],
                f["extra"]["min_version"][1],
                loc,
                f["message"],
            )
        )
    if not args.no_fail:
        return 1
    return 0


def cmd_version(args):
    print(f"pyfloor {__version__}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="pyfloor",
        description="Audit the Python version floor of a project.",
    )
    sub = parser.add_subparsers(dest="command", help="subcommand")

    p_check = sub.add_parser("check", help="scan project and report findings")
    p_check.add_argument("path", nargs="?", default=".", help="project root")
    p_check.add_argument("--json", action="store_true", help="machine-readable JSON output")
    p_check.add_argument("--no-fail", action="store_true", help="always exit 0")
    p_check.add_argument("--strict", action="store_true", help="also flag INFO-level")
    p_check.set_defaults(func=cmd_check)

    p_decl = sub.add_parser("declarations", help="list version declaration sites")
    p_decl.add_argument("path", nargs="?", default=".", help="project root")
    p_decl.set_defaults(func=cmd_declarations)

    p_feat = sub.add_parser("features", help="run only the code-feature check")
    p_feat.add_argument("path", nargs="?", default=".", help="project root")
    p_feat.add_argument("--no-fail", action="store_true", help="always exit 0")
    p_feat.set_defaults(func=cmd_features)

    p_ver = sub.add_parser("version", help="print version")
    p_ver.set_defaults(func=cmd_version)

    return parser


def main(argv=None):
    _reconfigure_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
