"""Print the next release version (SPEC 11.3). Stdlib only.

Usage: git tag --list | python scripts/next_version.py "<commit message>"

Tags not shaped like vX.Y.Z are ignored. No tags gives v0.1.0. The patch number goes up
by one, unless the message contains [minor] (minor +1, patch 0) or [major] (major +1,
minor and patch 0).
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable

TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
FIRST = "v0.1.0"


def latest(tags: Iterable[str]) -> tuple[int, int, int] | None:
    found = [m.groups() for t in tags if (m := TAG.match(t.strip()))]
    if not found:
        return None
    return max((int(a), int(b), int(c)) for a, b, c in found)


def next_version(tags: Iterable[str], message: str) -> str:
    current = latest(tags)
    if current is None:
        return FIRST
    major, minor, patch = current
    if "[major]" in message:
        return f"v{major + 1}.0.0"
    if "[minor]" in message:
        return f"v{major}.{minor + 1}.0"
    return f"v{major}.{minor}.{patch + 1}"


def main(argv: list[str]) -> int:
    message = argv[1] if len(argv) > 1 else ""
    print(next_version(sys.stdin.read().splitlines(), message))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
