"""A module that uses features newer than the declared 3.9 floor.

Uses a match statement (3.10) and tomllib (3.11), so pyfloor should flag
CODE_NEEDS_NEWER for both.
"""


def parse(data: dict) -> str:
    match data.get("kind"):
        case "a":
            return "alpha"
        case "b":
            return "beta"
        case _:
            return "other"


def read_toml(path: str) -> dict:
    import tomllib

    with open(path, "rb") as fh:
        return tomllib.load(fh)
