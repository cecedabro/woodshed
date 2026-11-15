"""Tests for media helpers: kind detection, safe upload, and deletion (SPEC 3.5, backend.md §media).

Uses real files under ``tmp_path`` so disk I/O and partial-file cleanup are
exercised end-to-end.
"""

import io
from pathlib import Path

import pytest

from app.media import TooLarge, delete_file, kind_for_filename, save_upload

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeUploadFile:
    """Minimal ``UploadFile``-ish object for unit testing ``save_upload``.

    Matches the FastAPI ``UploadFile`` interface: ``.filename`` and ``.file``.
    """

    def __init__(self, data: bytes, filename: str = "test.gp5") -> None:
        self.file = io.BytesIO(data)
        self.filename = filename


# ---------------------------------------------------------------------------
# kind_for_filename
# ---------------------------------------------------------------------------


def test_kind_for_filename_tab_gp() -> None:
    """SPEC 3.5: .gp → tab."""
    assert kind_for_filename("solo.gp") == "tab"


def test_kind_for_filename_tab_uppercase_gre5() -> None:
    """SPEC 3.5: .GP5 upper case → tab."""
    assert kind_for_filename("gimme.GP5") == "tab"


def test_kind_for_filename_tab_all_exts() -> None:
    """SPEC 3.5: all tab extensions recognised (case-insensitive)."""
    for ext in (".gp", ".gp3", ".gp4", ".gp5", ".gpx", ".musicxml", ".xml", ".mxl"):
        assert kind_for_filename(f"file{ext}") == "tab"
        assert kind_for_filename(f"file{ext.upper()}") == "tab"


def test_kind_for_filename_pdf() -> None:
    """SPEC 3.5: .pdf → pdf."""
    assert kind_for_filename("solo.pdf") == "pdf"


def test_kind_for_filename_audio_exts() -> None:
    """SPEC 3.5: audio extensions → audio."""
    for ext in (".mp3", ".m4a", ".wav", ".flac", ".ogg", ".opus", ".webm"):
        assert kind_for_filename(f"track{ext}") == "audio"


def test_kind_for_filename_exe_unknown() -> None:
    """SPEC 3.5: .exe → None."""
    assert kind_for_filename("trojan.exe") is None


def test_kind_for_filename_other_unknown() -> None:
    """SPEC 3.5: other unknown extensions → None."""
    assert kind_for_filename("doc.docx") is None
    assert kind_for_filename("archive.zip") is None


# ---------------------------------------------------------------------------
# save_upload
# ---------------------------------------------------------------------------

_ONE_MIB = 1 * 1024 * 1024


def test_save_upload_stores_file(tmp_path: Path) -> None:
    """save_upload copies the data and stores it under media_dir/<subdir>."""
    data = b"hello world"
    upload = _FakeUploadFile(data, filename="test.gp")
    media_dir = tmp_path / "media"

    stored_name, size = save_upload(upload, "attachments", 1024, media_dir)

    assert size == len(data)
    # stored_name should be uuid4 hex + extension
    assert stored_name.endswith(".gp")
    uuid_part = stored_name[:-3]
    assert len(uuid_part) == 32  # uuid4 hex is 32 chars
    int(uuid_part, 16)  # should parse as hex
    # file exists on disk
    assert (media_dir / "attachments" / stored_name).read_bytes() == data


def test_save_upload_creates_subdir(tmp_path: Path) -> None:
    """save_upload creates the target directory if it does not exist."""
    data = b"hello"
    upload = _FakeUploadFile(data, filename="test.gp")
    media_dir = tmp_path / "media"

    save_upload(upload, "new/subdir", 1024, media_dir)

    files = list((media_dir / "new/subdir").iterdir())
    assert len(files) == 1
    assert files[0].read_bytes() == data


def test_save_upload_exact_limit_ok(tmp_path: Path) -> None:
    """SPEC: limit exact = ok — file stored successfully."""
    data = b"x" * _ONE_MIB
    upload = _FakeUploadFile(data, filename="chunk.gp")
    media_dir = tmp_path / "media"

    stored_name, size = save_upload(upload, "attachments", _ONE_MIB, media_dir)

    assert size == _ONE_MIB
    assert (media_dir / "attachments" / stored_name).read_bytes() == data


def test_save_upload_limit_plus_one_raises(tmp_path: Path) -> None:
    """SPEC: limit + 1 = TooLarge and no file left."""
    data = b"x" * (_ONE_MIB + 1)
    upload = _FakeUploadFile(data, filename="overflow.gp")
    media_dir = tmp_path / "media"

    with pytest.raises(TooLarge):
        save_upload(upload, "attachments", _ONE_MIB, media_dir)

    # No partial file left on disk (the directory itself may have been created
    # before the overflow; check that it contains no files).
    target_dir = media_dir / "attachments"
    files = [f for f in target_dir.iterdir()] if target_dir.exists() else []
    assert files == [], f"Partial file(s) left: {files}"


def test_save_upload_within_limit(tmp_path: Path) -> None:
    """Upload well within limit succeeds."""
    data = b"a" * 500
    upload = _FakeUploadFile(data, filename="small.gp")
    media_dir = tmp_path / "media"

    stored_name, size = save_upload(upload, "takes", 1024, media_dir)

    assert size == 500
    assert (media_dir / "takes" / stored_name).read_bytes() == data


def test_save_upload_multiple_chunks(tmp_path: Path) -> None:
    """Upload larger than 1 MiB but within limit copies all chunks."""
    data = b"b" * (_ONE_MIB * 2)
    upload = _FakeUploadFile(data, filename="big.gp")
    media_dir = tmp_path / "media"

    stored_name, size = save_upload(upload, "attachments", _ONE_MIB * 3, media_dir)

    assert size == len(data)
    assert (media_dir / "attachments" / stored_name).read_bytes() == data


# ---------------------------------------------------------------------------
# delete_file
# ---------------------------------------------------------------------------


def test_delete_file_removes_file(tmp_path: Path) -> None:
    """delete_file removes an existing stored file."""
    media_dir = tmp_path / "media"
    target_dir = media_dir / "attachments"
    target_dir.mkdir(parents=True)
    stored_name = "abc123def456.gp"
    (target_dir / stored_name).write_bytes(b"delete me")

    delete_file(media_dir, "attachments", stored_name)

    assert not (target_dir / stored_name).exists()


def test_delete_file_no_error_when_missing(tmp_path: Path) -> None:
    """delete_file: a missing file is not an error (SPEC §media)."""
    media_dir = tmp_path / "media"

    delete_file(media_dir, "takes", "nonexistent.gp")  # should not raise
