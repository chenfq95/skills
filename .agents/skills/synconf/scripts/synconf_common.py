#!/usr/bin/env python3
"""Shared constants and utilities for synconf scripts.

This module provides common functionality used across scan_configs.py,
generate_sync.py, and check_platform_filtering.py.

Compatible with Python 3.8+ (avoids 3.9+ type syntax).
"""

import logging
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configure module-level logger
logger = logging.getLogger("synconf")

# Constants
HOME = Path.home()
IS_MACOS = platform.system() == "Darwin"
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
DEFAULT_REPO_DIR = HOME / ".synconf"

# Placeholder tokens for home path normalization
HOME_TOKEN = "__SYNCONF_HOME__"
HOME_POSIX_TOKEN = "__SYNCONF_HOME_POSIX__"


# Category detection rules: (pattern, category)
# Order matters - first match wins
CATEGORY_RULES = [
    # Shell
    (".zsh", "shell"),
    (".bash", "shell"),
    (".profile", "shell"),
    (".zprofile", "shell"),
    ("powershell", "shell"),
    ("Microsoft.PowerShell_profile.ps1", "shell"),
    ("Microsoft.VSCode_profile.ps1", "shell"),
    ("fish/config.fish", "shell"),
    (".config/fish", "shell"),
    # Git
    (".git", "git"),
    # Editor
    (".vim", "editor"),
    ("nvim", "editor"),
    ("code/user", "editor"),
    ("cursor/user", "editor"),
    ("/zed", "editor"),
    ("sublime text/packages/user", "editor"),
    (".editorconfig", "editor"),
    (".emacs", "editor"),
    # Terminal
    (".tmux", "terminal"),
    (".inputrc", "terminal"),
    ("alacritty", "terminal"),
    ("ghostty", "terminal"),
    ("kitty", "terminal"),
    ("wezterm", "terminal"),
    ("Windows Terminal", "terminal"),
    ("iterm2", "terminal"),
    # Dev tools
    (".npmrc", "dev"),
    ("npmrc", "dev"),
    (".cargo", "dev"),
    (".pylintrc", "dev"),
    (".flake8", "dev"),
    (".eslintrc", "dev"),
    (".prettierrc", "dev"),
    (".rubocop", "dev"),
    ("pip.ini", "dev"),
    ("pip.conf", "dev"),
    ("pypoetry", "dev"),
    # Prompt/theme
    ("starship", "prompt"),
    ("oh-my-zsh", "prompt"),
    ("powerlevel10k", "prompt"),
]


# Software name inference rules: (pattern, software_name)
# Order matters - first match wins
SOFTWARE_RULES = [
    # Shell
    ("microsoft.powershell_profile.ps1", "PowerShell"),
    ("microsoft.vscode_profile.ps1", "PowerShell"),
    ("fish/config.fish", "Fish"),
    (".config/fish", "Fish"),
    (".zsh", "Zsh"),
    (".bash", "Bash"),
    (".profile", "Shell"),
    # Terminal
    ("windows terminal", "Windows Terminal"),
    ("iterm2", "iTerm2"),
    (".tmux", "Tmux"),
    ("alacritty", "Alacritty"),
    ("ghostty", "Ghostty"),
    ("kitty", "Kitty"),
    ("wezterm", "WezTerm"),
    (".inputrc", "Readline"),
    # Editor
    ("code/user", "VS Code"),
    ("cursor/user", "Cursor"),
    ("/zed", "Zed"),
    ("sublime text/packages/user", "Sublime Text"),
    ("nvim", "Neovim"),
    (".vim", "Vim"),
    (".emacs", "Emacs"),
    (".editorconfig", "EditorConfig"),
    # Git
    (".gitconfig", "Git"),
    (".gitignore", "Git"),
    (".gitmessage", "Git"),
    # Prompt/theme
    ("starship", "Starship"),
    ("oh-my-zsh", "Oh My Zsh"),
    ("powerlevel10k", "Powerlevel10k"),
    # Dev tools
    ("npmrc", "npm"),
    ("pip.ini", "pip"),
    ("pip.conf", "pip"),
    ("pypoetry", "Poetry"),
    (".cargo", "Cargo"),
    (".pylintrc", "Pylint"),
    (".flake8", "Flake8"),
    (".eslintrc", "ESLint"),
    (".prettierrc", "Prettier"),
    (".rubocop", "RuboCop"),
    # Cloud/containers
    (".docker", "Docker"),
    (".kube", "Kubernetes"),
    (".aws", "AWS CLI"),
    ("gcloud", "Google Cloud"),
    (".azure", "Azure CLI"),
    # Other
    (".ssh/config", "SSH"),
    ("gpg-agent", "GPG"),
    ("/gh/", "GitHub CLI"),
]


# Platform-specific path patterns: (pattern, [platforms])
# Used for both backup and restore filtering
PLATFORM_RULES = [
    # Windows-specific
    ("appdata/roaming/code/user", ["windows"]),
    ("appdata/roaming/cursor/user", ["windows"]),
    ("appdata/roaming/zed", ["windows"]),
    ("appdata/roaming/sublime text/packages/user", ["windows"]),
    ("appdata/roaming/ghostty", ["windows"]),
    ("appdata/roaming/npm/npmrc", ["windows"]),
    ("appdata/local/microsoft/windows terminal", ["windows"]),
    ("documents/windowspowershell/", ["windows"]),
    ("documents/powershell/microsoft.powershell_profile.ps1", ["windows"]),
    ("documents/powershell/microsoft.vscode_profile.ps1", ["windows"]),
    ("microsoft/windows terminal", ["windows"]),
    ("/pip/pip.ini", ["windows"]),
    # macOS-specific
    ("library/application support/code/user", ["macos"]),
    ("library/application support/cursor/user", ["macos"]),
    ("library/application support/zed", ["macos"]),
    ("library/application support/sublime text/packages/user", ["macos"]),
    ("library/application support/com.mitchellh.ghostty", ["macos"]),
    ("library/application support/iterm2", ["macos"]),
    ("library/application support/pypoetry", ["macos"]),
    ("/brewfile", ["macos"]),
    # Linux-specific
    (".config/code/user", ["linux"]),
    (".config/cursor/user", ["linux"]),
    (".config/sublime-text/packages/user", ["linux"]),
    # Generic platform markers (catch-all, keep last)
    ("appdata/", ["windows"]),
    ("library/application support/", ["macos"]),
]


# Maximum files to count in a directory (for performance)
MAX_FILE_COUNT = 10000
# Maximum depth for directory scanning (for performance)
MAX_SCAN_DEPTH = 10


@dataclass
class ConfigItem:
    """Represents a detected configuration file or directory."""
    software: str
    path: str
    repo_path: str
    repo_exists: bool
    exists: bool
    is_dir: bool
    size: str
    file_count: Optional[int] = None


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


def infer_category(path: Path) -> str:
    """Infer repository category for a config path.

    Args:
        path: Config file or directory path

    Returns:
        Category name (shell, git, editor, terminal, dev, prompt, other)
    """
    text = path.as_posix().lower()
    for pattern, category in CATEGORY_RULES:
        if pattern.lower() in text:
            return category
    return "other"


def infer_software(path: Path) -> str:
    """Infer a user-facing software name from a config path.

    Args:
        path: Config file or directory path

    Returns:
        Software name (e.g., 'VS Code', 'Neovim', 'Zsh')
    """
    text = path.as_posix().lower()
    for pattern, software in SOFTWARE_RULES:
        if pattern.lower() in text:
            return software
    return path.name or path.as_posix()


def repo_relative_path(src: Path, category: str) -> Path:
    """Map a local config path to its destination inside the repo.

    Args:
        src: Source path (local config location)
        category: Category for grouping in repo

    Returns:
        Relative path like 'editor/.config/nvim'
    """
    rel = relative_to_home(src)
    return Path(category) / rel


def detect_supported_platforms(
    path: Path,
    software: str = "",
    stored_platforms: Optional[List[str]] = None
) -> Optional[List[str]]:
    """Infer which platforms a config path supports.

    Args:
        path: Config file or directory path
        software: Optional software name for additional context
        stored_platforms: Previously stored platform metadata (takes precedence)

    Returns:
        List of platform names, or None if cross-platform
    """
    # Use stored metadata if available
    if isinstance(stored_platforms, list) and stored_platforms:
        normalized = []
        for item in stored_platforms:
            platform_name = normalize_platform_name(str(item))
            if platform_name not in normalized:
                normalized.append(platform_name)
        if normalized:
            return normalized

    # Infer from path patterns
    combined = " ".join([
        path.as_posix().replace("\\", "/").lower(),
        software.strip().lower(),
    ])
    for pattern, platforms in PLATFORM_RULES:
        if pattern in combined:
            return [normalize_platform_name(item) for item in platforms]
    return None


def human_size(path: Path) -> str:
    """Return human-readable size for a file or directory.

    Args:
        path: File or directory path

    Returns:
        Size string like '1.5KB', '32MB', or '?' on error
    """
    try:
        if path.is_dir():
            total = 0
            count = 0
            for f in path.rglob("*"):
                if count >= MAX_FILE_COUNT:
                    logger.debug(
                        "Stopped size calculation for %s after %d files",
                        path, MAX_FILE_COUNT
                    )
                    break
                if f.is_file():
                    try:
                        total += f.stat().st_size
                    except (OSError, PermissionError):
                        pass
                count += 1
        else:
            total = path.stat().st_size
    except (OSError, PermissionError) as e:
        logger.debug("Could not calculate size for %s: %s", path, e)
        return "?"

    for unit in ("B", "KB", "MB", "GB"):
        if total < 1024:
            return f"{total:.0f}{unit}" if unit == "B" else f"{total:.1f}{unit}"
        total /= 1024
    return f"{total:.1f}TB"


def count_files(path: Path, max_count: int = MAX_FILE_COUNT) -> int:
    """Count files in a directory with a limit for performance.

    Args:
        path: Directory path
        max_count: Maximum files to count before stopping

    Returns:
        File count (capped at max_count)
    """
    try:
        count = 0
        for f in path.rglob("*"):
            if f.is_file():
                count += 1
                if count >= max_count:
                    logger.debug(
                        "Stopped counting files for %s at limit %d",
                        path, max_count
                    )
                    break
        return count
    except (OSError, PermissionError) as e:
        logger.debug("Could not count files for %s: %s", path, e)
        return 0


def read_text_file(path: Path) -> Optional[str]:
    """Read a text file with UTF-8 encoding.

    Args:
        path: File path

    Returns:
        File contents, or None if not readable as text
    """
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        logger.debug("Could not read text file %s: %s", path, e)
        return None


def normalize_text(text: str) -> str:
    """Replace home paths with placeholders for portability.

    Args:
        text: Text content that may contain home paths

    Returns:
        Text with home paths replaced by tokens
    """
    home = Path.home()
    # Replace POSIX-style first (more specific), then native style
    return text.replace(home.as_posix(), HOME_POSIX_TOKEN).replace(str(home), HOME_TOKEN)


def render_text(text: str) -> str:
    """Replace placeholders with actual home paths.

    Args:
        text: Text content with placeholders

    Returns:
        Text with placeholders replaced by actual home paths
    """
    home = Path.home()
    # Replace POSIX token first, then native token
    return text.replace(HOME_POSIX_TOKEN, home.as_posix()).replace(HOME_TOKEN, str(home))


# ANSI color codes for terminal output
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

    @classmethod
    def cross(cls) -> str:
        """Return a red cross."""
        return f"{cls.RED}\u2717{cls.RESET}"


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for synconf scripts.

    Args:
        verbose: If True, set DEBUG level; otherwise INFO
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s"
    )
