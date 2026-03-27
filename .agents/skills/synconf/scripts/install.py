#!/usr/bin/env python3
"""Install dotfiles by copying repo configs into the local machine.

This script reads manifest.json to determine which configs to install,
then copies them from the repo to the local machine, backing up existing files.
"""

import json
import logging
import platform
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Set up logging
logger = logging.getLogger("synconf.install")

DOTFILES_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = Path.home() / ".synconf-backup" / datetime.now().strftime("%Y%m%d-%H%M%S")
MANIFEST_PATH = DOTFILES_DIR / "manifest.json"
HOME_TOKEN = "__SYNCONF_HOME__"
HOME_POSIX_TOKEN = "__SYNCONF_HOME_POSIX__"


def get_current_platform() -> str:
    """Return the normalized current platform name."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    return system


def normalize_platform_name(name: str) -> str:
    """Normalize platform labels for consistent comparison."""
    normalized = name.lower().strip()
    if normalized in ("darwin", "mac", "osx"):
        return "macos"
    if normalized in ("win32", "win", "win64", "nt"):
        return "windows"
    return normalized


def filter_entries_for_platform(
    entries: List[Dict[str, object]],
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """Filter entries to those supported by the current platform."""
    current = get_current_platform()
    supported = []
    skipped = []

    for entry in entries:
        platforms = entry.get("platforms")
        if platforms:
            normalized = [normalize_platform_name(str(p)) for p in platforms]
            if current not in normalized:
                skipped.append(entry)
                continue
        supported.append(entry)

    return supported, skipped


def path_from_rel(path_str: str) -> Path:
    """Convert a relative path string to Path object."""
    return Path(path_str)


def read_text_file(path: Path) -> Optional[str]:
    """Read a text file, returning None if not readable as UTF-8."""
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def render_text(text: str) -> str:
    """Replace placeholders with actual home paths."""
    home = Path.home()
    result = text.replace(HOME_POSIX_TOKEN, home.as_posix())
    return result.replace(HOME_TOKEN, str(home))


def contains_placeholders(path: Path) -> bool:
    """Check if a file or directory contains home path placeholders.

    Args:
        path: Path to check

    Returns:
        True if placeholders found, False otherwise
    """
    try:
        if path.is_dir():
            for child in path.rglob("*"):
                if child.is_file():
                    if contains_placeholders(child):
                        return True
            return False
        text = read_text_file(path)
        return bool(text and (HOME_TOKEN in text or HOME_POSIX_TOKEN in text))
    except (OSError, PermissionError):
        return False


def remove_path(path: Path) -> None:
    """Remove a file or directory."""
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def backup_existing(dst: Path) -> bool:
    """Backup existing local config before overwriting.

    Args:
        dst: Destination path to backup

    Returns:
        True if backup succeeded or wasn't needed, False on failure
    """
    if not dst.exists() and not dst.is_symlink():
        return True

    # Check if dst is within home directory
    home = Path.home()
    try:
        rel_path = dst.relative_to(home)
    except ValueError:
        # dst is not under home - use absolute path as relative
        logger.warning("Backup target %s is not under home directory", dst)
        # Use a safe fallback path
        rel_path = Path("_external") / dst.name

    backup_target = BACKUP_DIR / rel_path
    backup_target.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # Use copy for cross-filesystem safety, then remove original
        if dst.is_dir() and not dst.is_symlink():
            shutil.copytree(dst, backup_target)
            shutil.rmtree(dst)
        else:
            shutil.copy2(dst, backup_target)
            dst.unlink()
        print(f"Backed up {dst} -> {backup_target}")
        return True
    except (OSError, PermissionError) as e:
        print(f"Warning: Failed to backup {dst}: {e}")
        return False


def copy_path(src: Path, dst: Path) -> None:
    """Copy a file or directory."""
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)


def copy_with_render(src: Path, dst: Path) -> None:
    """Copy a file or directory, rendering placeholders."""
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True, exist_ok=True)
        for child in src.rglob("*"):
            rel = child.relative_to(src)
            target = dst / rel
            if child.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            text = read_text_file(child)
            if text is None:
                shutil.copy2(child, target)
            else:
                target.write_text(render_text(text), encoding="utf-8")
        return

    text = read_text_file(src)
    if text is None:
        shutil.copy2(src, dst)
    else:
        dst.write_text(render_text(text), encoding="utf-8")


def install_file(src: Path, dst: Path, is_dir: bool) -> bool:
    """Copy a repo config into the local machine.

    Args:
        src: Source path in repo
        dst: Destination path on local machine
        is_dir: Whether source is a directory

    Returns:
        True if installed successfully, False on failure
    """
    if dst.exists() or dst.is_symlink():
        if not backup_existing(dst):
            print(f"Warning: Skipping {dst} - backup failed")
            return False

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError) as e:
        print(f"Warning: Cannot create parent directory for {dst}: {e}")
        return False

    try:
        if contains_placeholders(src):
            copy_with_render(src, dst)
            print(f"Rendered {src} -> {dst}")
            return True

        copy_path(src, dst)
        print(f"Copied {src} -> {dst}")
        return True
    except (OSError, PermissionError) as e:
        print(f"Warning: Failed to install {src} -> {dst}: {e}")
        return False


def load_manifest() -> List[Dict[str, Any]]:
    """Load manifest.json and return the files list.

    Returns:
        List of file entries from manifest
    """
    if not MANIFEST_PATH.exists():
        return []
    try:
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        files = payload.get("files", [])
        if not isinstance(files, list):
            logger.warning("Manifest 'files' is not a list")
            return []
        return files
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse manifest: %s", e)
        return []
    except OSError as e:
        logger.warning("Failed to read manifest: %s", e)
        return []


def main() -> None:
    """Main entry point."""
    print(f"Installing dotfiles from {DOTFILES_DIR}")
    print()

    files = load_manifest()
    if not files:
        print("No configs found in manifest.json. Nothing to install.")
        return

    # Filter to current platform
    supported, skipped = filter_entries_for_platform(files)

    if skipped:
        print("Skipping configs that do not support this platform:")
        for entry in skipped:
            platforms = entry.get("platforms", [])
            platform_label = ", ".join(str(p).title() for p in platforms)
            software = entry.get('software', 'Unknown')
            print(f"  - {software} (supported: {platform_label})")
        print()

    if not supported:
        print("No configs for this platform found in manifest.json.")
        return

    installed_count = 0
    skipped_count = 0

    for entry in supported:
        # Safely get required fields with defaults
        repo_rel = entry.get("repo_rel")
        home_rel = entry.get("home_rel")
        is_dir = entry.get("is_dir", False)
        software = entry.get("software", "Unknown")

        # Validate required fields
        if not repo_rel:
            print(f"Warning: Entry for {software} missing repo_rel, skipping")
            skipped_count += 1
            continue
        if not home_rel:
            print(f"Warning: Entry for {software} missing home_rel, skipping")
            skipped_count += 1
            continue

        src = DOTFILES_DIR / path_from_rel(str(repo_rel))
        dst = Path.home() / path_from_rel(str(home_rel))

        if not src.exists():
            print(f"Warning: {src} not found, skipping")
            skipped_count += 1
            continue

        if install_file(src, dst, bool(is_dir)):
            installed_count += 1
        else:
            skipped_count += 1

    print()
    print(
        f"Dotfiles installation complete: "
        f"{installed_count} installed, {skipped_count} skipped"
    )
    if BACKUP_DIR.exists():
        print(f"Backup of old files saved to: {BACKUP_DIR}")


if __name__ == "__main__":
    main()
