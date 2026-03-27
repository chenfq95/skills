#!/usr/bin/env python3
"""Shared constants and utilities for synconf scripts.

This module provides common functionality used by all synconf scripts.
Compatible with Python 3.8+ (avoids 3.9+ type syntax).
"""

import difflib
import fcntl
import json
import logging
import os
import platform
import shutil
import signal
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Mapping, Optional, Sequence, Tuple, TypedDict

# Configure module-level logger
logger = logging.getLogger("synconf")

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

HOME = Path.home()
IS_MACOS = platform.system() == "Darwin"
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
DEFAULT_REPO_DIR = HOME / ".synconf"
SCRIPTS_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = SCRIPTS_DIR.parent / "templates"
CONFIG_PATH = SCRIPTS_DIR / "config.json"

# Placeholder tokens for home path normalization
HOME_TOKEN = "__SYNCONF_HOME__"
HOME_POSIX_TOKEN = "__SYNCONF_HOME_POSIX__"

# Path constraints
MAX_PATH_COMPONENT_LENGTH = 200  # Max length for path components after slugify
MAX_FILE_SIZE_FOR_FULL_READ = 50 * 1024 * 1024  # 50MB limit for full file reads
MAX_SYMLINK_DEPTH = 40  # Maximum symlink resolution depth

REPO_SUBDIRECTORIES = [
    "shell",
    "git",
    "editor",
    "terminal",
    "dev",
    "prompt",
    "scripts",
    "other",
    "merge-notes",
]

RUNTIME_REPO_FILES = [
    "manage.py",
    "backup.py",
    "restore.py",
    "sync.py",
    "install.py",
    "common.py",
    "config.json",
]


# -----------------------------------------------------------------------------
# Type Definitions
# -----------------------------------------------------------------------------


class ManifestEntry(TypedDict, total=False):
    """Tracked config entry stored in manifest.json."""

    software: str
    category: str
    home_rel: str
    repo_rel: str
    is_dir: bool
    size: str
    file_count: int
    platforms: List[str]
    exists: bool
    source: str


class ManifestPayload(TypedDict, total=False):
    """Manifest payload stored in manifest.json."""

    version: int
    files: List[ManifestEntry]


class StatePayload(TypedDict, total=False):
    """Local-only state stored in .state.json (gitignored)."""

    last_scan_order: List[str]
    last_selected_repo_rels: List[str]


@dataclass
class FileMapping:
    """Represents a mapping between local config and repo location."""

    source: str
    software: str
    category: str
    repo_rel: str
    home_rel: str
    is_dir: bool
    platforms: Optional[List[str]] = None


class ConflictRecord(TypedDict):
    """Detected conflict between two sync endpoints."""

    entry: ManifestEntry
    source: str
    target: str


class ConflictDecision(TypedDict):
    """Resolved conflict handling decision for one entry."""

    action: str
    override: bool


class OperationRecord(TypedDict):
    """Detailed file operation record for final reporting."""

    software: str
    source: str
    target: str
    target_exists_before: bool
    action: str


def entry_software(entry: Mapping[str, Any]) -> str:
    """Return the software label for a manifest-like entry."""
    return str(entry.get("software", "Unknown"))


def entry_home_rel(entry: Mapping[str, Any]) -> str:
    """Return the home-relative path for a manifest-like entry."""
    return str(entry.get("home_rel", "")).strip()


def entry_repo_rel(entry: Mapping[str, Any]) -> str:
    """Return the repo-relative path for a manifest-like entry."""
    return str(entry.get("repo_rel", "")).strip()


def entry_is_dir(entry: Mapping[str, Any]) -> bool:
    """Return whether the manifest-like entry points to a directory."""
    return bool(entry.get("is_dir", False))


# -----------------------------------------------------------------------------
# File Locking
# -----------------------------------------------------------------------------


class FileLockError(Exception):
    """Raised when a file lock cannot be acquired."""


@contextmanager
def file_lock(
    path: Path,
    timeout: float = 10.0,
    shared: bool = False,
) -> Generator[None, None, None]:
    """Context manager for file-based locking.

    Args:
        path: Path to the file to lock (a .lock file will be created)
        timeout: Maximum time to wait for lock in seconds
        shared: If True, acquire a shared (read) lock; otherwise exclusive (write)

    Raises:
        FileLockError: If lock cannot be acquired within timeout
    """
    lock_path = path.parent / f".{path.name}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    lock_type = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
    lock_fd = None

    try:
        lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)

        # Set up alarm for timeout (Unix only)
        def timeout_handler(signum: int, frame: Any) -> None:
            raise FileLockError(f"Timeout acquiring lock on {path}")

        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(int(timeout))

        try:
            fcntl.flock(lock_fd, lock_type)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

        yield

    finally:
        if lock_fd is not None:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
            # Clean up lock file if possible
            try:
                lock_path.unlink()
            except OSError:
                pass


@contextmanager
def file_lock_windows(
    path: Path,
    timeout: float = 10.0,
    shared: bool = False,
) -> Generator[None, None, None]:
    """Fallback file locking for Windows (no-op with warning)."""
    logger.debug("File locking not fully supported on Windows: %s", path)
    yield


def get_file_lock() -> Any:
    """Return the appropriate file lock context manager for the platform."""
    if IS_WINDOWS:
        return file_lock_windows
    return file_lock


# -----------------------------------------------------------------------------
# ANSI Colors
# -----------------------------------------------------------------------------


class Colors:
    """ANSI color codes for terminal output."""

    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    CYAN = "\033[0;36m"
    RED = "\033[0;31m"
    RESET = "\033[0m"

    @classmethod
    def check(cls) -> str:
        """Return a green checkmark."""
        return f"{cls.GREEN}\u2713{cls.RESET}"


# -----------------------------------------------------------------------------
# Path Validation
# -----------------------------------------------------------------------------


class PathValidationError(Exception):
    """Raised when a path fails validation checks."""


def validate_path_within_home(path: Path, home: Optional[Path] = None) -> None:
    """Validate that a path is safely within the home directory.

    Args:
        path: Path to validate (can be relative to home)
        home: Home directory (defaults to HOME)

    Raises:
        PathValidationError: If path escapes home directory
    """
    resolved_home = (home or HOME).resolve()
    try:
        resolved_path = (resolved_home / path).resolve()
        resolved_path.relative_to(resolved_home)
    except ValueError:
        raise PathValidationError(
            f"Path '{path}' escapes home directory. "
            "Refusing to operate on paths outside HOME."
        )


def validate_not_reserved_name(name: str) -> None:
    """Validate that a filename is not a Windows reserved name.

    Args:
        name: Filename to check

    Raises:
        PathValidationError: If name is reserved
    """
    reserved = {
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    }
    base_name = name.upper().split(".")[0]
    if base_name in reserved:
        raise PathValidationError(f"'{name}' is a reserved Windows filename")


def is_safe_symlink(path: Path, max_depth: int = MAX_SYMLINK_DEPTH) -> bool:
    """Check if a symlink is safe to follow (no loops, exists).

    Args:
        path: Path to check
        max_depth: Maximum symlink resolution depth

    Returns:
        True if safe, False if broken or circular
    """
    try:
        seen = set()
        current = path
        for _ in range(max_depth):
            if not current.is_symlink():
                return current.exists()
            real = current.resolve()
            if real in seen:
                return False  # Circular symlink
            seen.add(real)
            current = real
        return False  # Too deep
    except (OSError, ValueError):
        return False


# -----------------------------------------------------------------------------
# Configuration Loading
# -----------------------------------------------------------------------------


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def get_category_rules(config: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    """Get category inference rules from config."""
    if config is None:
        config = load_config()
    return config.get("category_rules", {}).get("rules", [])


def get_software_rules(config: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    """Get software name inference rules from config."""
    if config is None:
        config = load_config()
    return config.get("software_rules", {}).get("rules", [])


def get_platform_rules(config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Get platform detection rules from config."""
    if config is None:
        config = load_config()
    return config.get("platform_rules", {}).get("rules", [])


# -----------------------------------------------------------------------------
# Platform Utilities
# -----------------------------------------------------------------------------


def normalize_platform_name(name: str) -> str:
    """Normalize platform labels for consistent comparison.

    Args:
        name: Raw platform name (e.g., 'Darwin', 'win32', 'Linux')

    Returns:
        Normalized name: 'macos', 'windows', 'linux', or lowercased original
    """
    lowered = name.strip().lower()
    if lowered == "darwin":
        return "macos"
    if lowered in {"windows", "win32"}:
        return "windows"
    if lowered == "linux":
        return "linux"
    return lowered or "unknown"


def format_platform_name(name: str) -> str:
    """Format platform name for human-readable display.

    Args:
        name: Normalized platform name

    Returns:
        Display-friendly name (e.g., 'macOS', 'Windows', 'Linux')
    """
    labels = {"macos": "macOS", "windows": "Windows", "linux": "Linux"}
    return labels.get(name, name)


def get_current_platform() -> str:
    """Return the normalized current platform name."""
    return normalize_platform_name(platform.system())


def normalize_platform_list(platforms: Optional[Sequence[str]]) -> List[str]:
    """Normalize and deduplicate a platform list."""
    normalized: List[str] = []
    if not platforms:
        return normalized

    for item in platforms:
        name = normalize_platform_name(str(item))
        if name not in normalized:
            normalized.append(name)
    return normalized


def merge_supported_platforms(
    *platform_groups: Optional[Sequence[str]],
) -> Optional[List[str]]:
    """Merge multiple platform lists into one normalized list."""
    merged: List[str] = []
    for group in platform_groups:
        for name in normalize_platform_list(group):
            if name not in merged:
                merged.append(name)
    return merged or None


def entry_supports_platform(
    entry: Mapping[str, Any],
    target_platform: Optional[str] = None,
) -> bool:
    """Return True when a registry entry supports the target platform."""
    if target_platform is None:
        target_platform = get_current_platform()

    supported_platforms = normalize_platform_list(entry.get("platforms"))
    if not supported_platforms:
        return True
    return target_platform in supported_platforms


def detect_platforms_from_path(
    path: Path,
    software: str,
    platform_rules: Optional[List[Dict[str, Any]]] = None,
) -> Optional[List[str]]:
    """Infer which platforms a config path supports.

    Args:
        path: Config file or directory path
        software: Software name
        platform_rules: Optional list of platform rules (loads from config if None)

    Returns:
        List of supported platforms, or None if cross-platform
    """
    if platform_rules is None:
        platform_rules = get_platform_rules()

    combined = " ".join(
        [
            path.as_posix().replace("\\", "/").lower(),
            software.strip().lower(),
        ]
    )

    for rule in platform_rules:
        if rule["pattern"] in combined:
            return [normalize_platform_name(p) for p in rule["platforms"]]

    return None


def detect_supported_platforms_from_entry(
    entry: Mapping[str, Any],
    platform_rules: Optional[List[Dict[str, Any]]] = None,
) -> Optional[List[str]]:
    """Infer which platforms a manifest entry supports.

    Args:
        entry: Manifest entry dict
        platform_rules: Optional list of platform rules

    Returns:
        List of supported platforms, or None if cross-platform
    """
    stored = entry.get("platforms")
    if isinstance(stored, list) and stored:
        normalized = normalize_platform_list(stored)
        if normalized:
            return normalized

    if platform_rules is None:
        platform_rules = get_platform_rules()

    combined = " ".join(
        [
            str(entry.get("home_rel", "")).replace("\\", "/").lower(),
            str(entry.get("repo_rel", "")).replace("\\", "/").lower(),
            str(entry.get("software", "")).strip().lower(),
        ]
    )

    for rule in platform_rules:
        if rule["pattern"] in combined:
            return [normalize_platform_name(p) for p in rule["platforms"]]

    return None


def filter_entries_for_platform(
    entries: Sequence[ManifestEntry],
    target_platform: Optional[str] = None,
    platform_rules: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[List[ManifestEntry], List[ManifestEntry]]:
    """Separate entries into supported and unsupported for a platform.

    Args:
        entries: List of manifest entries
        target_platform: Platform to filter for (defaults to current)
        platform_rules: Optional platform rules

    Returns:
        Tuple of (supported entries, skipped entries)
    """
    if target_platform is None:
        target_platform = get_current_platform()

    supported = []
    skipped = []

    for entry in entries:
        platforms = detect_supported_platforms_from_entry(entry, platform_rules)
        if platforms and target_platform not in platforms:
            skipped.append(entry)
        else:
            supported.append(entry)

    return supported, skipped


# -----------------------------------------------------------------------------
# Path Utilities
# -----------------------------------------------------------------------------


def resolve_repo_dir(repo_dir: Optional[str]) -> Path:
    """Resolve the target synconf repository directory.

    Args:
        repo_dir: Optional explicit repo path

    Returns:
        Resolved repo directory path
    """
    if repo_dir:
        return Path(repo_dir).expanduser().resolve()
    if DEFAULT_REPO_DIR.exists():
        return DEFAULT_REPO_DIR
    return SCRIPTS_DIR.parent


def relative_to_home(path: Path) -> Path:
    """Return a path relative to the user's home directory.

    Args:
        path: Absolute or relative path

    Returns:
        Path relative to HOME, or just the filename if not under HOME
    """
    try:
        return path.resolve().relative_to(HOME.resolve())
    except ValueError:
        return Path(path.name)


def display_home_path(path: Path) -> str:
    """Return a stable ~/ prefixed path for display.

    Args:
        path: Path to format

    Returns:
        String like '~/.config/nvim'
    """
    rel = relative_to_home(path)
    return "~/" + rel.as_posix() if rel.as_posix() != "." else "~"


def path_from_rel(path_str: str) -> Path:
    """Convert a relative path string to Path object."""
    return Path(path_str)


# -----------------------------------------------------------------------------
# Text Processing
# -----------------------------------------------------------------------------


def read_text_file(path: Path, max_size: int = MAX_FILE_SIZE_FOR_FULL_READ) -> Optional[str]:
    """Read a text file, returning None if not readable as UTF-8.

    Args:
        path: Path to read
        max_size: Maximum file size in bytes (default 50MB)

    Returns:
        File contents as string, or None if binary/too large/unreadable
    """
    try:
        # Check file size first to avoid loading huge files
        size = path.stat().st_size
        if size > max_size:
            logger.warning(
                "File %s is too large (%d bytes > %d), treating as binary",
                path, size, max_size
            )
            return None
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def read_text_lines(path: Path) -> Optional[List[str]]:
    """Read a text file as lines."""
    text = read_text_file(path)
    if text is None:
        return None
    return text.splitlines()


def normalize_text(text: str) -> str:
    """Replace home paths with placeholders for portability."""
    return text.replace(HOME.as_posix(), HOME_POSIX_TOKEN).replace(
        str(HOME), HOME_TOKEN
    )


def render_text(text: str) -> str:
    """Replace placeholders with actual home paths."""
    return text.replace(HOME_POSIX_TOKEN, HOME.as_posix()).replace(
        HOME_TOKEN, str(HOME)
    )


# -----------------------------------------------------------------------------
# Inference Functions
# -----------------------------------------------------------------------------


def infer_category(
    path: Path,
    rules: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Infer repository category for a config path.

    Args:
        path: Config file or directory path
        rules: Optional category rules (loads from config if None)

    Returns:
        Category name (shell, git, editor, terminal, dev, prompt, other)
    """
    if rules is None:
        rules = get_category_rules()

    text = path.as_posix().lower()
    for rule in rules:
        if rule["pattern"].lower() in text:
            return rule["category"]
    return "other"


def infer_software(
    path: Path,
    rules: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Infer a user-facing software name from a config path.

    Args:
        path: Config file or directory path
        rules: Optional software rules (loads from config if None)

    Returns:
        Software name (e.g., 'VS Code', 'Neovim', 'Zsh')
    """
    if rules is None:
        rules = get_software_rules()

    text = path.as_posix().lower()
    for rule in rules:
        if rule["pattern"].lower() in text:
            return rule["software"]
    return path.name or path.as_posix()


def slugify_path_component(value: str, max_length: int = MAX_PATH_COMPONENT_LENGTH) -> str:
    """Convert a user-facing label into a stable repo path component.

    Args:
        value: Input string to slugify
        max_length: Maximum output length

    Returns:
        Slugified string safe for use in file paths
    """
    lowered = value.strip().lower()
    chars = []
    last_was_dash = False

    for char in lowered:
        if char.isalnum():
            chars.append(char)
            last_was_dash = False
            continue

        if not last_was_dash:
            chars.append("-")
            last_was_dash = True

    result = "".join(chars).strip("-") or "item"

    # Truncate if too long
    if len(result) > max_length:
        result = result[:max_length].rstrip("-")

    # Validate not a reserved name
    try:
        validate_not_reserved_name(result)
    except PathValidationError:
        result = f"_{result}"

    return result


def platform_path_component(platforms: Optional[Sequence[str]]) -> Optional[str]:
    """Return a stable platform path segment when an entry is platform-scoped."""
    normalized = normalize_platform_list(platforms)
    if not normalized:
        return None
    return "-".join(normalized)


def repo_relative_path(
    src: Path,
    category: str,
    software: str,
    is_dir: bool,
    platforms: Optional[Sequence[str]] = None,
) -> Path:
    """Map a local config path to its destination inside the repo.

    Args:
        src: Source path (local config location)
        category: Category for grouping in repo
        software: Software name for grouping in repo
        is_dir: Whether the source is a directory
        platforms: Optional supported platform list

    Returns:
        Relative path like 'editor/vs-code/windows' or 'git/git/.gitconfig'
    """
    repo_root = Path(category) / slugify_path_component(software)
    platform_component = platform_path_component(platforms)
    if platform_component:
        repo_root = repo_root / platform_component
    # Both files and directories keep their original name under repo_root
    return repo_root / src.name


def manifest_entry_identity(entry: Mapping[str, Any]) -> str:
    """Return the stable logical identity for a manifest entry.

    Args:
        entry: Manifest entry dict

    Returns:
        Identity string (home_rel preferred, then repo_rel, then software name)
    """
    home_rel = entry_home_rel(entry)
    if home_rel:
        return home_rel
    repo_rel = entry_repo_rel(entry)
    if repo_rel:
        return repo_rel
    # Fallback to software name to avoid empty identity
    software = entry_software(entry)
    if software and software != "Unknown":
        return f"__software__{software}"
    # Last resort: generate a unique-ish identity
    return f"__entry__{id(entry)}"


# -----------------------------------------------------------------------------
# File Comparison
# -----------------------------------------------------------------------------


def summarize_directory(path: Path, max_depth: int = MAX_SYMLINK_DEPTH) -> List[str]:
    """List all files in a directory recursively, safely handling symlinks.

    Args:
        path: Directory to summarize
        max_depth: Maximum symlink resolution depth

    Returns:
        Sorted list of relative file paths
    """
    results = []
    seen_real_paths: set = set()

    def walk_dir(current: Path, rel_prefix: str, depth: int) -> None:
        if depth > max_depth:
            logger.warning("Max depth reached while walking %s", current)
            return

        try:
            children = list(current.iterdir())
        except (OSError, PermissionError) as e:
            logger.warning("Cannot read directory %s: %s", current, e)
            return

        for child in children:
            rel_path = f"{rel_prefix}/{child.name}" if rel_prefix else child.name

            try:
                # Detect symlink loops
                if child.is_symlink():
                    real_path = child.resolve()
                    if real_path in seen_real_paths:
                        logger.warning("Symlink loop detected at %s", child)
                        continue
                    if not real_path.exists():
                        logger.warning("Broken symlink at %s", child)
                        continue
                    seen_real_paths.add(real_path)

                if child.is_file():
                    results.append(rel_path.replace("\\", "/"))
                elif child.is_dir():
                    walk_dir(child, rel_path, depth + 1)
            except (OSError, PermissionError) as e:
                logger.warning("Cannot access %s: %s", child, e)

    walk_dir(path, "", 0)
    return sorted(results)


def files_equal(src: Path, dest: Path) -> bool:
    """Check if two files have equal content.

    Args:
        src: Source file path
        dest: Destination file path

    Returns:
        True if files have identical content, False otherwise
    """
    try:
        # Quick size check first
        src_stat = src.stat()
        dest_stat = dest.stat()
        if src_stat.st_size != dest_stat.st_size:
            return False
    except OSError as e:
        logger.warning("Cannot stat files for comparison: %s", e)
        return False

    src_lines = read_text_lines(src)
    dest_lines = read_text_lines(dest)
    if src_lines is None or dest_lines is None:
        # Binary comparison
        try:
            # Compare in chunks for large files
            chunk_size = 8192
            with open(src, 'rb') as f1, open(dest, 'rb') as f2:
                while True:
                    chunk1 = f1.read(chunk_size)
                    chunk2 = f2.read(chunk_size)
                    if chunk1 != chunk2:
                        return False
                    if not chunk1:
                        return True
        except OSError as e:
            logger.warning("Cannot compare binary files: %s", e)
            return False
    return src_lines == dest_lines


def directories_equal(src: Path, dest: Path) -> bool:
    """Check if two directories have equal content."""
    src_entries = summarize_directory(src)
    dest_entries = summarize_directory(dest)
    if src_entries != dest_entries:
        return False
    return all(files_equal(src / rel_path, dest / rel_path) for rel_path in src_entries)


def entries_equal(src: Path, dest: Path, is_dir: bool) -> bool:
    """Check if source and destination entries are equal."""
    if not dest.exists():
        return False
    if is_dir:
        return directories_equal(src, dest)
    return files_equal(src, dest)


# -----------------------------------------------------------------------------
# Diff Display
# -----------------------------------------------------------------------------


def diff_file(
    src: Path,
    dest: Path,
    src_label: str = "src",
    dest_label: str = "dest",
) -> bool:
    """Show unified diff between two files. Returns True if files differ."""
    src_lines = read_text_lines(src)
    dest_lines = read_text_lines(dest)
    if src_lines is None or dest_lines is None:
        try:
            same = src.read_bytes() == dest.read_bytes()
        except OSError:
            same = False
        if not same:
            print("Binary or non-UTF8 file differs; review manually.")
        return not same

    if src_lines == dest_lines:
        return False

    for line in difflib.unified_diff(
        dest_lines,
        src_lines,
        fromfile=f"{dest_label}/{dest}",
        tofile=f"{src_label}/{src}",
        lineterm="",
    ):
        print(line)
    return True


def print_diff(
    src: Path,
    dest: Path,
    is_dir: bool,
    src_label: str = "src",
    dest_label: str = "dest",
) -> bool:
    """Show diff for file or directory. Returns True if content differs."""
    if is_dir:
        src_entries = summarize_directory(src)
        dest_entries = summarize_directory(dest)
        differs = False
        if src_entries != dest_entries:
            differs = True
            print("Directory file list differs:")
            for line in difflib.unified_diff(
                dest_entries,
                src_entries,
                fromfile=f"{dest_label}/{dest}",
                tofile=f"{src_label}/{src}",
                lineterm="",
            ):
                print(line)

        for rel_path in sorted(set(src_entries) & set(dest_entries)):
            src_file = src / rel_path
            dest_file = dest / rel_path
            if files_equal(src_file, dest_file):
                continue
            differs = True
            print()
            print(f"Diff for {rel_path}:")
            diff_file(src_file, dest_file, src_label, dest_label)

        return differs

    print("File contents differ:")
    return diff_file(src, dest, src_label, dest_label)


# -----------------------------------------------------------------------------
# Manifest Operations
# -----------------------------------------------------------------------------


def empty_manifest() -> ManifestPayload:
    """Return an empty manifest payload."""
    return {"version": 1, "files": []}


def load_manifest(manifest_path: Path) -> ManifestPayload:
    """Load manifest.json or return default structure.

    Args:
        manifest_path: Path to manifest.json

    Returns:
        Manifest payload dict
    """
    if not manifest_path.exists():
        return empty_manifest()
    try:
        lock_fn = get_file_lock()
        with lock_fn(manifest_path, shared=True):
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            return payload
    except (json.JSONDecodeError, FileLockError) as e:
        logger.warning("Failed to load manifest: %s", e)
        return empty_manifest()


def save_manifest(payload: ManifestPayload, manifest_path: Path) -> None:
    """Save manifest.json with file locking.

    Args:
        payload: Manifest data to save
        manifest_path: Path to manifest.json
    """
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fn = get_file_lock()
    try:
        with lock_fn(manifest_path, shared=False):
            # Write to temp file first, then rename for atomicity
            temp_path = manifest_path.with_suffix(".json.tmp")
            temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temp_path.replace(manifest_path)
    except FileLockError as e:
        logger.error("Failed to acquire lock for manifest: %s", e)
        raise


def load_state(repo_dir: Path) -> StatePayload:
    """Load .state.json or return empty structure."""
    state_path = repo_dir / ".state.json"
    if not state_path.exists():
        return {}
    try:
        lock_fn = get_file_lock()
        with lock_fn(state_path, shared=True):
            return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileLockError) as e:
        logger.warning("Failed to load state: %s", e)
        return {}


def save_state(state: StatePayload, repo_dir: Path) -> None:
    """Save .state.json (local-only, gitignored) with file locking."""
    state_path = repo_dir / ".state.json"
    lock_fn = get_file_lock()
    try:
        with lock_fn(state_path, shared=False):
            temp_path = state_path.with_suffix(".json.tmp")
            temp_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
            temp_path.replace(state_path)
    except FileLockError as e:
        logger.warning("Failed to save state: %s", e)


# -----------------------------------------------------------------------------
# User Prompts
# -----------------------------------------------------------------------------


def prompt_yes_no(message: str, default: bool = False, auto_yes: bool = False) -> bool:
    """Prompt for yes/no confirmation.

    Args:
        message: Prompt message
        default: Default answer if user presses Enter
        auto_yes: If True, always return True without prompting

    Returns:
        True for yes, False for no
    """
    if auto_yes:
        return True
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(message + " " + suffix + " ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def choose_conflict_action(auto_yes: bool = False, direction: str = "backup") -> str:
    """Prompt user to choose how to handle a conflict.

    Args:
        auto_yes: If True, return "overwrite" without prompting
        direction: "backup" or "restore" for context-appropriate messages

    Returns:
        "overwrite", "skip", or "manual"
    """
    if auto_yes:
        return "overwrite"

    if direction == "restore":
        print("Choose what to do with this sync conflict:")
        print("  1. overwrite - replace the local version with the repo version")
        print("  2. skip - keep the local version unchanged for now")
    else:
        print("Choose what to do with this conflict:")
        print("  1. overwrite - replace the repo version with the local version")
        print("  2. skip - keep the repo version unchanged for now")
    print("  3. manual - leave both as-is and resolve manually later")

    while True:
        answer = input("Select [1/2/3]: ").strip().lower()
        if answer in {"1", "overwrite", "o"}:
            return "overwrite"
        if answer in {"2", "skip", "s"}:
            return "skip"
        if answer in {"3", "manual", "m", "manual-merge"}:
            return "manual"
        print("Please enter 1, 2, or 3.")


# -----------------------------------------------------------------------------
# Merge Notes
# -----------------------------------------------------------------------------


def save_merge_note(
    entry: Mapping[str, Any],
    note: str,
    merge_notes_dir: Path,
    repo_dir: Path,
    direction: str = "backup",
) -> Path:
    """Save merge instructions to a markdown file."""
    merge_notes_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    note_path = (
        merge_notes_dir
        / f"{timestamp}-{direction}-{entry_software(entry).lower().replace(' ', '-')}.md"
    )
    note_path.write_text(
        "\n".join(
            [
                f"# Merge note for {entry_software(entry)} ({direction})",
                f"- Local path: `{HOME / Path(entry_home_rel(entry))}`",
                f"- Repo path: `{repo_dir / Path(entry_repo_rel(entry))}`",
                "",
                "## User instructions",
                note.strip() or "(none)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Saved merge note to {note_path}")
    return note_path


def append_pending_merge(
    entry: Mapping[str, Any],
    note_path: Optional[Path],
    reason: str,
    pending_merges_path: Path,
    repo_dir: Path,
    direction: str = "backup",
) -> None:
    """Record a pending merge that needs manual resolution."""
    pending_merges_path.parent.mkdir(parents=True, exist_ok=True)
    if pending_merges_path.exists():
        try:
            payload = json.loads(pending_merges_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {"items": []}
    else:
        payload = {"items": []}

    payload.setdefault("items", []).append(
        {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "software": entry_software(entry),
            "direction": direction,
            "local_path": str(HOME / Path(entry_home_rel(entry))),
            "repo_path": str(repo_dir / Path(entry_repo_rel(entry))),
            "reason": reason,
            "merge_note": str(note_path) if note_path else None,
        }
    )
    pending_merges_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Recorded pending merge in {pending_merges_path}")


def prompt_merge_instructions(
    entry: Mapping[str, Any],
    auto_yes: bool,
    merge_notes_dir: Path,
    repo_dir: Path,
    direction: str = "backup",
) -> Optional[Path]:
    """Prompt user for merge instructions."""
    if auto_yes:
        return None
    print("Describe how these two versions should be merged.")
    print("Press Enter on an empty line to finish. Leave blank to skip.")
    lines = []
    while True:
        line = input("> ")
        if not line:
            break
        lines.append(line)
    if lines:
        return save_merge_note(
            entry,
            "\n".join(lines),
            merge_notes_dir,
            repo_dir,
            direction,
        )
    return None


# -----------------------------------------------------------------------------
# Conflict Handling
# -----------------------------------------------------------------------------


def print_operation_records(records: List[OperationRecord]) -> None:
    """Print a detailed checklist of file operations."""
    print()
    print("Detailed file operations:")
    if not records:
        print("- none")
        return

    for index, record in enumerate(records, start=1):
        print(f"{index}. {record['software']}")
        print(f"   source: {record['source']}")
        print(f"   target: {record['target']}")
        print(
            "   target existed before: "
            + ("yes" if record["target_exists_before"] else "no")
        )
        print(f"   action: {record['action']}")


def print_conflict_preview(
    conflicts: List[ConflictRecord],
    write_label: str,
) -> None:
    """Show a compact summary of detected conflicts."""
    if not conflicts:
        print()
        print("No repo/local conflicts detected for the selected software.")
        return

    print()
    print(f"Detected {len(conflicts)} repo/local conflicts in the selected software.")
    print(f"A default conflict strategy will be chosen before {write_label}.")


def choose_conflict_plan(
    conflicts: List[ConflictRecord],
    auto_yes: bool,
    summary_title: str,
    source_label: str,
    target_label: str,
    overwrite_label: str,
    skip_label: str,
) -> str:
    """Choose a default strategy for all detected conflicts."""
    if not conflicts:
        return "review"
    if auto_yes:
        return "overwrite"

    print()
    print(summary_title)
    for index, conflict in enumerate(conflicts, start=1):
        entry = conflict["entry"]
        print(f"{index}. {entry_software(entry)}")
        print(f"   {source_label}: {conflict['source']}")
        print(f"   {target_label}: {conflict['target']}")

    print()
    print("Choose how to handle detected conflicts before writing any files:")
    print(f"  1. overwrite-all - {overwrite_label}")
    print(f"  2. skip-all - {skip_label}")
    print("  3. manual-all - leave every conflict for manual merge later")
    print("  4. review-each - inspect diffs and decide one conflict at a time")

    while True:
        answer = input("Select [1/2/3/4]: ").strip().lower()
        if answer in {"1", "overwrite-all", "overwrite", "o"}:
            return "overwrite"
        if answer in {"2", "skip-all", "skip", "s"}:
            return "skip"
        if answer in {"3", "manual-all", "manual", "m"}:
            return "manual"
        if answer in {"4", "review-each", "review", "r"}:
            return "review"
        print("Please enter 1, 2, 3, or 4.")


def choose_conflict_override(default_action: str) -> Optional[str]:
    """Allow overriding the default action for one conflict."""
    print(f"Default action: {default_action}")
    print("Press Enter to keep the default, or choose an override:")
    print("  1. overwrite")
    print("  2. skip")
    print("  3. manual")
    while True:
        answer = input("Select [Enter/1/2/3]: ").strip().lower()
        if not answer:
            return None
        if answer in {"1", "overwrite", "o"}:
            return "overwrite"
        if answer in {"2", "skip", "s"}:
            return "skip"
        if answer in {"3", "manual", "m"}:
            return "manual"
        print("Please press Enter, or enter 1, 2, or 3.")


def choose_conflict_decisions(
    conflicts: List[ConflictRecord],
    default_action: str,
    auto_yes: bool,
    intro_line: str,
    source_label: str,
    target_label: str,
) -> Dict[str, ConflictDecision]:
    """Resolve per-conflict actions after choosing a default strategy."""
    decisions: Dict[str, ConflictDecision] = {}
    if not conflicts:
        return decisions
    if auto_yes or default_action == "review":
        return decisions

    print()
    print(intro_line)
    print("Leave a conflict on the default action unless it needs special handling.")

    for index, conflict in enumerate(conflicts, start=1):
        entry = conflict["entry"]
        print()
        print(f"{index}. {entry_software(entry)}")
        print(f"   {source_label}: {conflict['source']}")
        print(f"   {target_label}: {conflict['target']}")
        override_action = choose_conflict_override(default_action)
        action = override_action or default_action
        decisions[entry_repo_rel(entry)] = {
            "action": action,
            "override": override_action is not None,
        }

    return decisions


def resolve_conflict_action(
    entry: Mapping[str, Any],
    default_action: str,
    decisions: Dict[str, ConflictDecision],
) -> str:
    """Resolve the conflict action for one entry."""
    decision = decisions.get(entry_repo_rel(entry))
    if decision:
        return decision["action"]
    return default_action


# -----------------------------------------------------------------------------
# Conflict Detection
# -----------------------------------------------------------------------------


def collect_backup_conflicts(
    entries: Sequence[ManifestEntry],
    repo_dir: Path,
    home_dir: Optional[Path] = None,
) -> List[ConflictRecord]:
    """Collect entries whose local and repo versions both exist and differ.

    Args:
        entries: List of manifest entries
        repo_dir: Repository directory
        home_dir: Home directory (defaults to HOME)

    Returns:
        List of conflict records
    """
    resolved_home = home_dir or HOME
    conflicts: List[ConflictRecord] = []

    for entry in entries:
        src = resolved_home / path_from_rel(entry_home_rel(entry))
        dest = repo_dir / path_from_rel(entry_repo_rel(entry))
        if not src.exists() or not (dest.exists() or dest.is_symlink()):
            continue
        if entries_equal(src, dest, entry_is_dir(entry)):
            continue
        conflicts.append(
            {
                "entry": entry,
                "source": str(src),
                "target": str(dest),
            }
        )

    return conflicts


def collect_restore_conflicts(
    entries: Sequence[ManifestEntry],
    repo_dir: Path,
    home_dir: Optional[Path] = None,
) -> List[ConflictRecord]:
    """Collect entries whose repo and local versions both exist and differ.

    Args:
        entries: List of manifest entries
        repo_dir: Repository directory
        home_dir: Home directory (defaults to HOME)

    Returns:
        List of conflict records
    """
    resolved_home = home_dir or HOME
    conflicts: List[ConflictRecord] = []

    for entry in entries:
        repo_path = repo_dir / path_from_rel(entry_repo_rel(entry))
        local_path = resolved_home / path_from_rel(entry_home_rel(entry))
        if not repo_path.exists() or not (
            local_path.exists() or local_path.is_symlink()
        ):
            continue
        if entries_equal(repo_path, local_path, entry_is_dir(entry)):
            continue
        conflicts.append(
            {
                "entry": entry,
                "source": str(repo_path),
                "target": str(local_path),
            }
        )

    return conflicts


# -----------------------------------------------------------------------------
# Environment Detection
# -----------------------------------------------------------------------------


def detect_environment(repo_dir: Path, manifest: ManifestPayload) -> None:
    """Print environment detection summary."""
    config_roots = [
        "~/.config",
        "~/Library/Application Support",
        "~/AppData/Roaming",
        "~/AppData/Local",
        "~/Documents/PowerShell",
    ]
    print("Environment detection:")
    print("- OS: " + platform.system())
    print("- Home: " + str(HOME))
    print("- Repo: " + str(repo_dir))
    print("- Repo exists: " + ("yes" if repo_dir.exists() else "no"))
    print("- Python configured: " + ("yes" if sys.executable else "no"))
    print("- Python executable: " + (sys.executable or "not found"))
    print("- Existing tracked configs: " + str(len(manifest.get("files", []))))
    print("- Config roots: " + ", ".join(config_roots))
    print()


# -----------------------------------------------------------------------------
# Logging Setup
# -----------------------------------------------------------------------------


def setup_logging(verbose: bool) -> None:
    """Configure logging for CLI scripts."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")


# -----------------------------------------------------------------------------
# Repo Scaffold
# -----------------------------------------------------------------------------


def ensure_repo_layout(repo_dir: Path) -> None:
    """Ensure the standard synconf directory layout exists."""
    repo_dir.mkdir(parents=True, exist_ok=True)
    for subdir in REPO_SUBDIRECTORIES:
        (repo_dir / subdir).mkdir(parents=True, exist_ok=True)


def _safe_copy(src: Path, dest: Path, retries: int = 3) -> bool:
    """Copy file with retry logic for Windows file locking issues."""
    import time
    for attempt in range(retries):
        try:
            # On Windows, try removing dest first if it exists and is locked
            if dest.exists():
                try:
                    dest.unlink()
                except (OSError, PermissionError):
                    pass
            shutil.copy2(src, dest)
            return True
        except PermissionError as e:
            if attempt < retries - 1:
                time.sleep(0.1 * (attempt + 1))
                continue
            logger.warning("Cannot copy %s -> %s: %s", src, dest, e)
            return False
    return False


def copy_runtime_scripts(repo_dir: Path) -> None:
    """Ensure runtime scripts and config.json exist in the repo."""
    scripts_dest = repo_dir / "scripts"
    scripts_dest.mkdir(parents=True, exist_ok=True)

    for name in RUNTIME_REPO_FILES:
        src = SCRIPTS_DIR / name
        dest = scripts_dest / name
        if not src.exists():
            logger.warning("Static runtime file missing: %s", src)
            continue
        if not _safe_copy(src, dest):
            continue
        if dest.suffix == ".py":
            try:
                dest.chmod(0o755)
            except OSError:
                pass  # Windows doesn't support chmod


def write_repo_readme(repo_dir: Path) -> None:
    """Write the root README.md for the synconf repo."""
    template_path = TEMPLATES_DIR / "README.md"
    if template_path.exists():
        content = template_path.read_text(encoding="utf-8")
    else:
        content = "# Dotfiles\n\nManaged with synconf.\n"
    (repo_dir / "README.md").write_text(content, encoding="utf-8")


def is_running_from_repo(repo_dir: Path) -> bool:
    """Check if the current script is running from inside the repo."""
    try:
        scripts_dir = SCRIPTS_DIR.resolve()
        repo_scripts = (repo_dir / "scripts").resolve()
        return scripts_dir == repo_scripts
    except (OSError, ValueError):
        return False


def ensure_repo_scaffold(repo_dir: Path) -> None:
    """Ensure a synconf repo has its expected directories and static files.

    When running from within the repo, only ensures directory layout and
    skips copying scripts, .gitignore, and README to avoid overwriting
    user customizations.
    """
    ensure_repo_layout(repo_dir)
    # Skip copying static files if already running from within the repo
    if not is_running_from_repo(repo_dir):
        ensure_gitignore(repo_dir)
        copy_runtime_scripts(repo_dir)
        write_repo_readme(repo_dir)


def ensure_gitignore(repo_dir: Path) -> None:
    """Create .gitignore with common exclusions if it doesn't exist."""
    gitignore_path = repo_dir / ".gitignore"
    if gitignore_path.exists():
        return

    template_path = TEMPLATES_DIR / "gitignore"
    if template_path.exists():
        content = template_path.read_text(encoding="utf-8")
    else:
        content = ".state.json\n__pycache__/\n"
    gitignore_path.write_text(content, encoding="utf-8")


# -----------------------------------------------------------------------------
# Disk Space and Safe File Operations
# -----------------------------------------------------------------------------


class DiskSpaceError(Exception):
    """Raised when there is insufficient disk space."""


def get_directory_size(path: Path, max_files: int = 10000) -> int:
    """Calculate total size of a directory in bytes.

    Args:
        path: Directory path
        max_files: Maximum files to count before returning estimate

    Returns:
        Total size in bytes
    """
    total = 0
    count = 0
    try:
        for f in path.rglob("*"):
            if count >= max_files:
                # Estimate remaining based on average
                avg_size = total / count if count > 0 else 0
                remaining = sum(1 for _ in path.rglob("*")) - count
                total += int(avg_size * remaining * 0.5)  # Conservative estimate
                break
            if _should_exclude_path(f):
                continue
            if f.is_file():
                try:
                    total += f.stat().st_size
                except (OSError, PermissionError):
                    pass
            count += 1
    except (OSError, PermissionError):
        pass
    return total


def check_disk_space(dest: Path, required_bytes: int, safety_margin: float = 1.1) -> None:
    """Check if there is sufficient disk space for an operation.

    Args:
        dest: Destination path (uses its filesystem)
        required_bytes: Bytes needed for the operation
        safety_margin: Multiplier for required space (default 10% extra)

    Raises:
        DiskSpaceError: If insufficient space available
    """
    # Find existing parent directory to check space
    check_path = dest
    while not check_path.exists():
        check_path = check_path.parent
        if check_path == check_path.parent:
            break

    try:
        stat = shutil.disk_usage(check_path)
        needed = int(required_bytes * safety_margin)
        if stat.free < needed:
            raise DiskSpaceError(
                f"Insufficient disk space. Need {needed / (1024*1024):.1f}MB, "
                f"only {stat.free / (1024*1024):.1f}MB available on {check_path}"
            )
    except OSError as e:
        logger.warning("Could not check disk space: %s", e)


def safe_copy_with_space_check(
    src: Path,
    dest: Path,
    is_dir: bool,
) -> None:
    """Copy file or directory with disk space check.

    Args:
        src: Source path
        dest: Destination path
        is_dir: Whether source is a directory

    Raises:
        DiskSpaceError: If insufficient disk space
        OSError: If copy fails
    """
    # Calculate required space
    if is_dir:
        required = get_directory_size(src)
    else:
        try:
            required = src.stat().st_size
        except OSError:
            required = 0

    # Check available space
    check_disk_space(dest, required)


def is_symlink_to_directory(path: Path) -> bool:
    """Check if path is a symlink pointing to a directory.

    Args:
        path: Path to check

    Returns:
        True if symlink to directory, False otherwise
    """
    try:
        return path.is_symlink() and path.resolve().is_dir()
    except (OSError, ValueError):
        return False


def safe_remove_tree(path: Path, follow_symlinks: bool = False) -> bool:
    """Safely remove a directory tree.

    Args:
        path: Path to remove
        follow_symlinks: If False, refuse to remove symlinks to directories

    Returns:
        True if removed, False if skipped or failed
    """
    if not path.exists() and not path.is_symlink():
        return True

    # Safety check for symlinks
    if path.is_symlink():
        if not follow_symlinks and is_symlink_to_directory(path):
            logger.warning(
                "Refusing to remove symlink to directory: %s -> %s",
                path, path.resolve()
            )
            return False
        try:
            path.unlink()
            return True
        except OSError as e:
            logger.warning("Failed to remove symlink %s: %s", path, e)
            return False

    try:
        shutil.rmtree(path)
        return True
    except (OSError, PermissionError) as e:
        logger.warning("Failed to remove directory %s: %s", path, e)
        return False


def check_git_available() -> bool:
    """Check if git command is available.

    Returns:
        True if git is available, False otherwise
    """
    import subprocess
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# -----------------------------------------------------------------------------
# Scanning
# -----------------------------------------------------------------------------


# Directories to exclude from editor config backups (cache, history, workspace state)
EDITOR_EXCLUDE_DIRS = {
    "History",
    "Cache",
    "CachedData",
    "CachedExtensions",
    "CachedExtensionVSIXs",
    "Code Cache",
    "GPUCache",
    "Service Worker",
    "WebStorage",
    "blob_storage",
    "databases",
    "workspaceStorage",
    "globalStorage",
    "logs",
    "Backups",
    "Crashpad",
    "DawnCache",
    "Network",
    "Session Storage",
    "Local Storage",
    "IndexedDB",
    "__pycache__",
    ".cache",
    "node_modules",
    ".git",
    "User Data",
}


def _should_exclude_path(path: Path) -> bool:
    """Check if a path should be excluded from size/count calculations."""
    for part in path.parts:
        if part in EDITOR_EXCLUDE_DIRS:
            return True
    return False


def human_size(path: Path) -> str:
    """Return human-readable size for a file or directory (excludes cache dirs)."""
    MAX_FILE_COUNT = 10000
    try:
        if path.is_dir():
            total = 0
            count = 0
            for f in path.rglob("*"):
                if count >= MAX_FILE_COUNT:
                    break
                if _should_exclude_path(f):
                    continue
                if f.is_file():
                    try:
                        total += f.stat().st_size
                    except (OSError, PermissionError):
                        pass
                count += 1
        else:
            total = path.stat().st_size
    except (OSError, PermissionError):
        return "?"

    for unit in ("B", "KB", "MB", "GB"):
        if total < 1024:
            return f"{total:.0f}{unit}" if unit == "B" else f"{total:.1f}{unit}"
        total /= 1024
    return f"{total:.1f}TB"


def count_files(path: Path, max_count: int = 10000) -> int:
    """Count files in a directory with a limit for performance (excludes cache dirs)."""
    try:
        count = 0
        for f in path.rglob("*"):
            if _should_exclude_path(f):
                continue
            if f.is_file():
                count += 1
                if count >= max_count:
                    break
        return count
    except (OSError, PermissionError):
        return 0


def detect_platforms_for_scan(
    path: Path,
    software: str,
    platform_rules: List[Dict[str, Any]],
) -> Optional[List[str]]:
    """Infer which platforms a config path supports during scanning."""
    combined = " ".join(
        [
            path.as_posix().replace("\\", "/").lower(),
            software.strip().lower(),
        ]
    )
    for rule in platform_rules:
        if rule["pattern"] in combined:
            return normalize_platform_list(rule["platforms"])
    return None


def scan_config_path(
    path_str: str,
    category_rules: List[Dict[str, str]],
    software_rules: List[Dict[str, str]],
    platform_rules: List[Dict[str, Any]],
    supported_platforms: Optional[Sequence[str]] = None,
) -> Optional[ManifestEntry]:
    """Check if a path exists and build a manifest entry."""
    path = Path(path_str).expanduser()
    if not path.exists():
        return None

    is_dir = path.is_dir()
    rel = relative_to_home(path)
    category = infer_category(path, category_rules)
    software = infer_software(path, software_rules)
    size = human_size(path)
    file_count = count_files(path) if is_dir else None
    platforms = merge_supported_platforms(
        supported_platforms,
        detect_platforms_for_scan(path, software, platform_rules),
    )
    repo_rel = repo_relative_path(
        path,
        category,
        software,
        is_dir,
        platforms=platforms,
    )

    entry: ManifestEntry = {
        "software": software,
        "category": category,
        "repo_rel": repo_rel.as_posix(),
        "home_rel": rel.as_posix(),
        "is_dir": is_dir,
        "size": size,
    }
    if file_count is not None:
        entry["file_count"] = file_count
    if platforms is not None:
        entry["platforms"] = platforms
    return entry


def run_scan(config: Optional[Dict[str, Any]] = None) -> List[ManifestEntry]:
    """Scan for all registered config files and return manifest entries."""
    if config is None:
        config = load_config()
    if not config:
        return []

    registry: Dict[str, List[Dict[str, str]]] = {}
    for cat, entries in config.get("config_registry", {}).get("categories", {}).items():
        registry[cat] = list(entries)

    platform_configs = config.get("platform_specific_configs", {})
    current_platform = get_current_platform()

    if current_platform in platform_configs:
        for category, entries in platform_configs[current_platform].items():
            if category in registry:
                registry[category].extend(entries)
            else:
                registry[category] = list(entries)

    category_rules = get_category_rules(config)
    software_rules = get_software_rules(config)
    platform_rules = get_platform_rules(config)

    seen_paths = set()
    results: List[ManifestEntry] = []
    for entries in registry.values():
        for entry in entries:
            if not entry_supports_platform(entry, current_platform):
                continue
            normalized_path = (
                Path(entry["path"]).expanduser().as_posix().replace("\\", "/").lower()
            )
            if normalized_path in seen_paths:
                continue
            seen_paths.add(normalized_path)
            item = scan_config_path(
                entry["path"],
                category_rules,
                software_rules,
                platform_rules,
                supported_platforms=entry.get("platforms"),
            )
            if item:
                results.append(item)

    return results
