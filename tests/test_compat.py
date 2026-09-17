"""Tests for cross-platform compatibility utilities in promptmaster_studio.compat."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from promptmaster_studio.compat import (
    DEFAULT_ENCODING_FALLBACKS,
    IS_LINUX,
    IS_MACOS,
    IS_WINDOWS,
    SYSTEM,
    atomic_write_bytes,
    atomic_write_text,
    get_app_dir,
    get_platform_info,
    read_json_safe,
    read_text_safe,
    safe_mkdir,
    safe_path,
    safe_remove,
    sanitize_filename,
    write_json_safe,
)


class TestPlatformInfo:
    """Test platform detection and metadata inspection."""

    def test_get_platform_info_returns_dict(self):
        info = get_platform_info()
        assert isinstance(info, dict)
        assert "system" in info
        assert "python_version" in info
        assert "is_windows" in info
        assert "is_macos" in info
        assert "is_linux" in info
        assert info["system"] == SYSTEM
        assert info["is_windows"] == IS_WINDOWS
        assert info["is_macos"] == IS_MACOS
        assert info["is_linux"] == IS_LINUX


class TestSanitizeFilename:
    """Test filename sanitization across operating systems."""

    def test_basic_sanitize(self):
        assert sanitize_filename("valid_name.txt") == "valid_name.txt"
        assert sanitize_filename("hello world.json") == "hello world.json"

    def test_illegal_characters_replaced(self):
        dirty = 'bad:name*with?illegal"chars<and>pipes|slash/back\\slash.txt'
        cleaned = sanitize_filename(dirty)
        for char in '<>:"/\\|?*':
            assert char not in cleaned

    def test_windows_reserved_names(self):
        cleaned_con = sanitize_filename("CON.txt")
        assert not cleaned_con.startswith("CON.")
        cleaned_nul = sanitize_filename("NUL")
        assert not cleaned_nul.startswith("NUL")

    def test_empty_and_trailing_characters(self):
        assert sanitize_filename("") == "unnamed_file"
        assert sanitize_filename("   ") == "unnamed_file"
        # Trailing dots/spaces are stripped
        sanitized = sanitize_filename("my_file... ")
        assert not sanitized.endswith(".")
        assert not sanitized.endswith(" ")

    def test_max_length_truncation(self):
        long_name = "a" * 300 + ".txt"
        cleaned = sanitize_filename(long_name, max_length=50)
        assert len(cleaned) <= 50
        assert cleaned.endswith(".txt")


class TestSafePathAndSafeMkdir:
    """Test path sanitization, directory traversal guards, and safe_mkdir."""

    def test_safe_path_normalization(self, tmp_path: Path):
        p = safe_path(tmp_path / "subdir" / ".." / "file.txt")
        assert p == (tmp_path / "file.txt").resolve() or p.name == "file.txt"

    def test_safe_path_traversal_guard(self, tmp_path: Path):
        base = tmp_path / "sandbox"
        base.mkdir()
        valid = safe_path(base / "nested" / "doc.md", base_dir=base)
        assert valid.name == "doc.md"

        # Traversal attempt
        with pytest.raises(ValueError, match="Path traversal detected"):
            safe_path(base / ".." / "escaped.txt", base_dir=base)

    def test_safe_mkdir(self, tmp_path: Path):
        target = tmp_path / "a" / "b" / "c"
        res = safe_mkdir(target)
        assert res.exists()
        assert res.is_dir()
        # Call again with exist_ok
        safe_mkdir(target, exist_ok=True)


class TestAtomicWriteAndRead:
    """Test atomic file writing and resilient reading."""

    def test_atomic_write_text_and_read(self, tmp_path: Path):
        target = tmp_path / "test.txt"
        content = "Hello, PromptMaster Studio! 🚀 Special chars: \u2705 \u2764\ufe0f"
        written = atomic_write_text(target, content)
        assert written.exists()
        read_back = read_text_safe(target)
        assert read_back == content

    def test_atomic_write_bytes(self, tmp_path: Path):
        target = tmp_path / "test.bin"
        data = b"\x00\x01\x02\x03\xff\xfe"
        written = atomic_write_bytes(target, data)
        assert written.exists()
        assert target.read_bytes() == data

    def test_atomic_write_overwrites_existing(self, tmp_path: Path):
        target = tmp_path / "overwrite.txt"
        atomic_write_text(target, "Version 1")
        assert read_text_safe(target) == "Version 1"
        atomic_write_text(target, "Version 2")
        assert read_text_safe(target) == "Version 2"

    def test_read_text_safe_missing_file(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            read_text_safe(tmp_path / "non_existent.txt")


class TestSafeJsonOperations:
    """Test safe JSON reading and writing."""

    def test_write_json_safe_and_read(self, tmp_path: Path):
        target = tmp_path / "data.json"
        data = {
            "name": "PromptMaster",
            "version": "1.0.0",
            "features": ["optimizer", "linter", "mcp"],
            "nested": {"active": True, "count": 42},
        }
        write_json_safe(target, data)
        loaded = read_json_safe(target)
        assert loaded == data

    def test_read_json_safe_missing_with_default(self, tmp_path: Path):
        missing = tmp_path / "does_not_exist.json"
        assert read_json_safe(missing, default={"fallback": True}) == {"fallback": True}

    def test_read_json_safe_missing_without_default(self, tmp_path: Path):
        missing = tmp_path / "does_not_exist.json"
        with pytest.raises(FileNotFoundError):
            read_json_safe(missing)


class TestSafeRemoveAndAppDir:
    """Test file deletion and user application directory resolution."""

    def test_safe_remove_file(self, tmp_path: Path):
        f = tmp_path / "to_delete.txt"
        f.write_text("temporary")
        assert f.exists()
        deleted = safe_remove(f)
        assert deleted is True
        assert not f.exists()

    def test_safe_remove_nonexistent(self, tmp_path: Path):
        f = tmp_path / "never_existed.txt"
        deleted = safe_remove(f, missing_ok=True)
        assert deleted is False

    def test_get_app_dir(self):
        app_dir = get_app_dir("test_promptmaster_tmp")
        assert app_dir.exists()
        assert app_dir.is_dir()
        assert "test_promptmaster_tmp" in str(app_dir)
        # Cleanup
        safe_remove(app_dir)
