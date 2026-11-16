"""SPEC 11.3: next release version from the tags and the commit message."""

import importlib.util
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "next_version.py"
_spec = importlib.util.spec_from_file_location("next_version", SCRIPT)
assert _spec and _spec.loader
nv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nv)


def test_no_tags_is_first_version() -> None:
    assert nv.next_version([], "anything") == "v0.1.0"
    assert nv.next_version([], "[major]") == "v0.1.0"


def test_patch_bump_uses_highest_tag_not_last() -> None:
    assert nv.next_version(["v0.1.9", "v0.1.10", "v0.1.2"], "T42: fix") == "v0.1.11"


def test_ignores_other_tags() -> None:
    tags = ["v0.2.0", "release-9", "v1.0", "v9.9.9-rc1", "1.5.0", "vX.Y.Z"]
    assert nv.next_version(tags, "") == "v0.2.1"
    assert nv.next_version(["nightly"], "") == "v0.1.0"


def test_minor_resets_patch() -> None:
    assert nv.next_version(["v0.3.7"], "Merge run [minor]") == "v0.4.0"


def test_major_resets_minor_and_patch() -> None:
    assert nv.next_version(["v0.3.7"], "Big one [major]") == "v1.0.0"
    assert nv.next_version(["v0.3.7"], "[major] and [minor]") == "v1.0.0"


def test_cli_reads_tags_from_stdin() -> None:
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "msg [minor]"],
        input="v0.1.4\nfoo\n",
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "v0.2.0"
