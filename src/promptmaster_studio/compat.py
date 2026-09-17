"""Cross-platform compatibility utilities for PromptMaster Studio.

Provides safe filesystem operations, atomic writes, encoding fallbacks,
and platform normalization across Linux, macOS, Windows, and Termux.
100% Python Standard Library.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Platform detection constants
SYSTEM = platform.system()
IS_WINDOWS = SYSTEM == "Windows"
IS_MACOS = SYSTEM == "Darwin"
IS_LINUX = SYSTEM == "Linux"
IS_TERMUX = "TERMUX_VERSION" in os.environ or os.path.exists("/data/data/com.termux")
IS_CYGWIN = SYSTEM.startswith("CYGWIN") or SYSTEM.startswith("MSYS") or SYSTEM.startswith("MINGW")

# Common encodings to attempt when reading files
DEFAULT_ENCODING_FALLBACKS: List[str] = [
    "utf-8",
    "utf-8-sig",
    "cp1252",
    "latin-1",
    "iso-8859-1",
]

# Invalid characters for filenames on Windows and general safe sanitization
INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED_WINDOWS_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def get_platform_info() -> Dict[str, Any]:
    """Return runtime platform metadata for diagnostic and configuration purposes."""
    return {
        "system": SYSTEM,
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "is_windows": IS_WINDOWS,
        "is_macos": IS_MACOS,
        "is_linux": IS_LINUX,
        "is_termux": IS_TERMUX,
        "filesystem_encoding": sys.getfilesystemencoding(),
        "default_encoding": sys.getdefaultencoding(),
    }


def sanitize_filename(name: str, replacement: str = "_", max_length: int = 255) -> str:
    """Sanitize a string so it is valid and safe as a filename across all supported OSes.
    
    Args:
        name: The candidate filename.
        replacement: Character to replace illegal characters with.
        max_length: Maximum allowed length for the filename.
        
    Returns:
        A sanitized filename string.
    """
    if not name:
        return "unnamed_file"
    
    # Strip leading/trailing whitespaces and dots (dots at end are problematic on Windows)
    clean_name = name.strip().rstrip(". ")
    
    # Replace illegal characters
    clean_name = INVALID_FILENAME_CHARS.sub(replacement, clean_name)
    
    # Collapse multiple replacement characters
    if replacement:
        double_rep = re.escape(replacement) + r"+"
        clean_name = re.sub(double_rep, replacement, clean_name)
    
    # Check Windows reserved base names (e.g. CON.txt, NUL)
    base_stem = clean_name.split(".")[0].upper()
    if base_stem in RESERVED_WINDOWS_NAMES:
        clean_name = f"{replacement}{clean_name}"
        
    # Enforce max length while preserving extension if possible
    if len(clean_name) > max_length:
        parts = clean_name.rsplit(".", 1)
        if len(parts) == 2 and len(parts[1]) < 10:
            ext = f".{parts[1]}"
            clean_name = parts[0][: max_length - len(ext)] + ext
        else:
            clean_name = clean_name[:max_length]
            
    return clean_name or "unnamed_file"


def safe_path(
    path: Union[str, Path],
    base_dir: Optional[Union[str, Path]] = None,
    allow_symlinks: bool = True,
) -> Path:
    """Normalize and validate a filesystem path safely across platforms.
    
    Expands user `~` and environment variables (`$VAR` or `%VAR%`).
    Optionally enforces path containment under a `base_dir` to guard against
    directory traversal attacks.
    
    Args:
        path: Path string or Path object.
        base_dir: Optional base directory that the path must reside within.
        allow_symlinks: Whether to allow symlinks when checking containment.
        
    Returns:
        Resolved and normalized Path.
        
    Raises:
        ValueError: If path escapes `base_dir` or is malformed.
    """
    path_str = str(path)
    
    # Expand environment variables and user home
    expanded = os.path.expandvars(os.path.expanduser(path_str))
    
    # Normalize path separators
    normalized = Path(os.path.normpath(expanded))
    
    if base_dir is not None:
        base_resolved = Path(os.path.expandvars(os.path.expanduser(str(base_dir)))).resolve()
        
        # If the target path doesn't exist yet, resolve its parent
        try:
            target_resolved = normalized.resolve()
        except (OSError, RuntimeError):
            target_resolved = normalized.absolute()
            
        try:
            # Python 3.9+ is_relative_to
            is_subpath = target_resolved.is_relative_to(base_resolved)
        except AttributeError:
            try:
                target_resolved.relative_to(base_resolved)
                is_subpath = True
            except ValueError:
                is_subpath = False
                
        if not is_subpath:
            raise ValueError(
                f"Path traversal detected: '{path_str}' resolves outside base directory '{base_dir}'"
            )
            
    return normalized


def safe_mkdir(dirpath: Union[str, Path], exist_ok: bool = True, mode: int = 0o755) -> Path:
    """Create directory hierarchy safely with standard permissions.
    
    Args:
        dirpath: Path to create.
        exist_ok: If True, do not raise if directory exists.
        mode: Directory permissions mode (POSIX).
        
    Returns:
        Path of the created or existing directory.
    """
    path = safe_path(dirpath)
    path.mkdir(parents=True, exist_ok=exist_ok, mode=mode)
    return path


def atomic_write_text(
    filepath: Union[str, Path],
    content: str,
    encoding: str = "utf-8",
    errors: str = "replace",
    make_parents: bool = True,
    sync: bool = True,
) -> Path:
    """Write text content to a file atomically to prevent partial writes and corruption.
    
    Writes to a temporary file in the same directory, flushes and syncs to disk,
    and replaces the target file atomically.
    
    Args:
        filepath: Target file path.
        content: Text content to write.
        encoding: Output character encoding (default utf-8).
        errors: Encoding error handling scheme.
        make_parents: Create parent directories if missing.
        sync: Whether to call os.fsync for physical disk persistence.
        
    Returns:
        Path of written file.
    """
    target = safe_path(filepath)
    parent_dir = target.parent
    
    if make_parents:
        parent_dir.mkdir(parents=True, exist_ok=True)
        
    # Use temp file in the same directory to guarantee atomic rename across filesystems
    fd, temp_path = tempfile.mkstemp(
        dir=str(parent_dir),
        prefix=f".tmp_{target.name}_",
        text=False,
    )
    
    temp_p = Path(temp_path)
    try:
        with open(fd, "w", encoding=encoding, errors=errors) as f:
            f.write(content)
            f.flush()
            if sync and hasattr(os, "fsync"):
                os.fsync(f.fileno())
                
        # Atomic replace
        if IS_WINDOWS:
            # On Windows, os.replace replaces existing file atomically in Python 3.3+
            # If target exists and is locked, attempt retry with small delay
            import time
            for attempt in range(5):
                try:
                    os.replace(str(temp_p), str(target))
                    break
                except PermissionError:
                    if attempt == 4:
                        raise
                    time.sleep(0.05)
        else:
            os.replace(str(temp_p), str(target))
            
        # Ensure default read/write permissions
        try:
            target.chmod(0o644)
        except OSError:
            pass
            
        return target
    except Exception:
        # Clean up temporary file if write or replace failed
        if temp_p.exists():
            try:
                temp_p.unlink(missing_ok=True)
            except OSError:
                pass
        raise


def atomic_write_bytes(
    filepath: Union[str, Path],
    data: bytes,
    make_parents: bool = True,
    sync: bool = True,
) -> Path:
    """Write binary data to a file atomically.
    
    Args:
        filepath: Target file path.
        data: Raw bytes to write.
        make_parents: Create parent directories if missing.
        sync: Call fsync to flush physical buffers.
        
    Returns:
        Path of written file.
    """
    target = safe_path(filepath)
    parent_dir = target.parent
    
    if make_parents:
        parent_dir.mkdir(parents=True, exist_ok=True)
        
    fd, temp_path = tempfile.mkstemp(
        dir=str(parent_dir),
        prefix=f".tmp_{target.name}_",
    )
    
    temp_p = Path(temp_path)
    try:
        with open(fd, "wb") as f:
            f.write(data)
            f.flush()
            if sync and hasattr(os, "fsync"):
                os.fsync(f.fileno())
                
        os.replace(str(temp_p), str(target))
        try:
            target.chmod(0o644)
        except OSError:
            pass
        return target
    except Exception:
        if temp_p.exists():
            try:
                temp_p.unlink(missing_ok=True)
            except OSError:
                pass
        raise


def read_text_safe(
    filepath: Union[str, Path],
    default_encoding: str = "utf-8",
    fallback_encodings: Optional[List[str]] = None,
) -> str:
    """Read text file with automatic encoding fallback handling and BOM stripping.
    
    Args:
        filepath: Path to text file.
        default_encoding: First encoding to attempt.
        fallback_encodings: List of fallback encodings to try if default fails.
        
    Returns:
        The decoded text contents.
        
    Raises:
        FileNotFoundError: If file does not exist.
        UnicodeDecodeError: If all candidate encodings fail.
    """
    path = safe_path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: '{path}'")
        
    encodings = [default_encoding]
    if fallback_encodings:
        for enc in fallback_encodings:
            if enc not in encodings:
                encodings.append(enc)
    else:
        for enc in DEFAULT_ENCODING_FALLBACKS:
            if enc not in encodings:
                encodings.append(enc)
                
    raw_bytes = path.read_bytes()
    
    last_error: Optional[Exception] = None
    for enc in encodings:
        try:
            return raw_bytes.decode(enc)
        except UnicodeDecodeError as e:
            last_error = e
            continue
            
    # Final permissive fallback if standard fallbacks fail
    return raw_bytes.decode("utf-8", errors="replace")


def read_json_safe(filepath: Union[str, Path], default: Any = None) -> Any:
    """Safely read and parse a JSON file with encoding fallback.
    
    Args:
        filepath: Path to JSON file.
        default: Return value if file does not exist or is empty and default is provided.
        
    Returns:
        Parsed JSON data structure.
    """
    path = safe_path(filepath)
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(f"JSON file not found: '{path}'")
        
    text = read_text_safe(path)
    if not text.strip():
        if default is not None:
            return default
        return None
    return json.loads(text)


def write_json_safe(
    filepath: Union[str, Path],
    data: Any,
    indent: int = 2,
    ensure_ascii: bool = False,
    sort_keys: bool = False,
) -> Path:
    """Serialize data to JSON and write atomically to disk.
    
    Args:
        filepath: Destination file path.
        data: JSON-serializable Python data structure.
        indent: Indentation level.
        ensure_ascii: If False, writes non-ASCII UTF-8 characters as-is.
        sort_keys: Whether to sort dictionary keys.
        
    Returns:
        Path of written JSON file.
    """
    content = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii, sort_keys=sort_keys)
    return atomic_write_text(filepath, content + "\n")


def safe_remove(filepath: Union[str, Path], missing_ok: bool = True) -> bool:
    """Safely delete a file if it exists.
    
    Args:
        filepath: File to delete.
        missing_ok: If True, do not raise if file does not exist.
        
    Returns:
        True if file was deleted, False if it was not found.
    """
    path = safe_path(filepath)
    try:
        if path.is_file() or path.is_symlink():
            path.unlink(missing_ok=missing_ok)
            return True
        elif path.is_dir():
            shutil.rmtree(str(path))
            return True
        return False
    except FileNotFoundError:
        if missing_ok:
            return False
        raise


def get_app_dir(app_name: str = "promptmaster_studio") -> Path:
    """Determine the standard user data/config directory for this application across OSes.
    
    - Linux / Termux: `$XDG_DATA_HOME` or `~/.local/share/<app_name>`
    - macOS: `~/Library/Application Support/<app_name>`
    - Windows: `%APPDATA%/<app_name>`
    
    Returns:
        Path to application data directory (created if not present).
    """
    if IS_WINDOWS:
        appdata = os.environ.get("APPDATA")
        if appdata:
            base = Path(appdata)
        else:
            base = Path.home() / "AppData" / "Roaming"
    elif IS_MACOS:
        base = Path.home() / "Library" / "Application Support"
    else:
        # Linux, Termux, BSD
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            base = Path(xdg_data)
        elif IS_TERMUX:
            base = Path.home() / ".local" / "share"
        else:
            base = Path.home() / ".local" / "share"
            
    app_path = base / app_name
    safe_mkdir(app_path)
    return app_path
