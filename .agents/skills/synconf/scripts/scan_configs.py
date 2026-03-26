#!/usr/bin/env python3
"""Scan for common config files in the home directory.

Outputs a categorized list of detected config files with their paths.
Supports --json flag for machine-readable output.
"""

import argparse
import json
import platform
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple


@dataclass
class ConfigItem:
    software: str
    path: str
    repo_path: str
    repo_exists: bool
    exists: bool
    is_dir: bool
    size: str
    file_count: Optional[int] = None


# ANSI colors
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
RESET = "\033[0m"
CHECK = f"{GREEN}\u2713{RESET}"

HOME = Path.home()
IS_MACOS = platform.system() == "Darwin"
IS_WINDOWS = platform.system() == "Windows"
DEFAULT_REPO_DIR = HOME / ".synconf"


CATEGORY_RULES = [
    (".zsh", "shell"),
    (".bash", "shell"),
    (".profile", "shell"),
    (".zprofile", "shell"),
    ("powershell", "shell"),
    ("Microsoft.PowerShell_profile.ps1", "shell"),
    ("Microsoft.VSCode_profile.ps1", "shell"),
    (".git", "git"),
    (".vim", "editor"),
    ("nvim", "editor"),
    ("code/user", "editor"),
    ("cursor/user", "editor"),
    ("/zed", "editor"),
    ("sublime text/packages/user", "editor"),
    (".editorconfig", "editor"),
    (".tmux", "terminal"),
    (".inputrc", "terminal"),
    ("alacritty", "terminal"),
    ("ghostty", "terminal"),
    ("kitty", "terminal"),
    ("wezterm", "terminal"),
    ("Windows Terminal", "terminal"),
    (".npmrc", "dev"),
    ("npmrc", "dev"),
    (".cargo", "dev"),
    (".pylintrc", "dev"),
    (".flake8", "dev"),
    (".eslintrc", "dev"),
    (".prettierrc", "dev"),
    (".rubocop", "dev"),
    ("pip.ini", "dev"),
]


SOFTWARE_RULES = [
    ("microsoft.powershell_profile.ps1", "PowerShell"),
    ("microsoft.vscode_profile.ps1", "PowerShell"),
    ("windows terminal", "Windows Terminal"),
    ("code/user", "VS Code"),
    ("cursor/user", "Cursor"),
    ("/zed", "Zed"),
    ("sublime text/packages/user", "Sublime Text"),
    ("nvim", "Neovim"),
    (".vim", "Vim"),
    (".gitconfig", "Git"),
    (".gitignore", "Git"),
    (".gitmessage", "Git"),
    (".zsh", "Zsh"),
    (".bash", "Bash"),
    (".profile", "Shell"),
    (".tmux", "Tmux"),
    ("alacritty", "Alacritty"),
    ("ghostty", "Ghostty"),
    ("kitty", "Kitty"),
    ("wezterm", "WezTerm"),
    ("starship", "Starship"),
    ("npmrc", "npm"),
    ("pip.ini", "pip"),
    (".cargo", "Cargo"),
    (".pylintrc", "Pylint"),
    (".flake8", "Flake8"),
    (".eslintrc", "ESLint"),
    (".prettierrc", "Prettier"),
    (".editorconfig", "EditorConfig"),
]


def human_size(path: Path) -> str:
    """Return human-readable size for a file or directory."""
    try:
        if path.is_dir():
            total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        else:
            total = path.stat().st_size
    except (OSError, PermissionError):
        return "?"

    for unit in ("B", "KB", "MB", "GB"):
        if total < 1024:
            return f"{total:.0f}{unit}" if unit == "B" else f"{total:.1f}{unit}"
        total /= 1024
    return f"{total:.1f}TB"


def count_files(path: Path) -> int:
    """Count files in a directory."""
    try:
        return sum(1 for _ in path.rglob("*") if _.is_file())
    except (OSError, PermissionError):
        return 0


def relative_to_home(path: Path) -> Path:
    """Return a path relative to the user's home directory when possible."""
    try:
        return path.resolve().relative_to(HOME.resolve())
    except ValueError:
        return Path(path.name)


def infer_category(path: Path) -> str:
    """Infer repository category for a config path."""
    text = path.as_posix().lower()
    for pattern, category in CATEGORY_RULES:
        if pattern.lower() in text:
            return category
    return "other"


def infer_software(path: Path) -> str:
    """Infer a user-facing software name from a config path."""
    text = path.as_posix().lower()
    for pattern, software in SOFTWARE_RULES:
        if pattern.lower() in text:
            return software
    return path.name or path.as_posix()


def repo_relative_path(path: Path) -> Path:
    """Map a local config path to its destination inside ~/.synconf."""
    return Path(infer_category(path)) / relative_to_home(path)


def check_path(path_str: str) -> ConfigItem:
    """Check if a path exists and gather info."""
    path = Path(path_str).expanduser()
    exists = path.exists() or path.is_symlink()
    repo_path = DEFAULT_REPO_DIR / repo_relative_path(path)
    repo_exists = repo_path.exists() or repo_path.is_symlink()
    software = infer_software(path)

    if not exists:
        return ConfigItem(
            software=software,
            path=str(path),
            repo_path=str(repo_path),
            repo_exists=repo_exists,
            exists=False,
            is_dir=False,
            size="0B",
        )

    is_dir = path.is_dir()
    size = human_size(path)
    file_count = count_files(path) if is_dir else None

    return ConfigItem(
        software=software,
        path=str(path),
        repo_path=str(repo_path),
        repo_exists=repo_exists,
        exists=True,
        is_dir=is_dir,
        size=size,
        file_count=file_count,
    )


# Config registry: category -> list of (type, path) tuples
# type is "file" or "dir" (for display hints only)
CONFIG_REGISTRY = {
    "Shell": [
        ("file", "~/.zshrc"),
        ("file", "~/.zprofile"),
        ("file", "~/.zshenv"),
        ("file", "~/.bashrc"),
        ("file", "~/.bash_profile"),
        ("file", "~/.profile"),
        ("file", "~/.bash_aliases"),
        ("file", "~/.zsh_aliases"),
    ],
    "Git": [
        ("file", "~/.gitconfig"),
        ("file", "~/.gitignore_global"),
        ("file", "~/.gitmessage"),
    ],
    "Editor": [
        ("file", "~/.vimrc"),
        ("dir", "~/.vim"),
        ("dir", "~/.config/nvim"),
        ("dir", "~/.config/zed"),
        ("file", "~/.emacs"),
        ("dir", "~/.emacs.d"),
    ],
    "Terminal": [
        ("file", "~/.tmux.conf"),
        ("dir", "~/.tmux"),
        ("dir", "~/.config/alacritty"),
        ("dir", "~/.config/ghostty"),
        ("dir", "~/.config/kitty"),
        ("dir", "~/.config/wezterm"),
        ("file", "~/.inputrc"),
    ],
    "Prompt & Theme": [
        ("file", "~/.config/starship.toml"),
        ("dir", "~/.oh-my-zsh/custom"),
        ("dir", "~/.config/powerlevel10k"),
    ],
    "Dev Tools": [
        ("file", "~/.npmrc"),
        ("file", "~/.yarnrc"),
        ("file", "~/.cargo/config.toml"),
        ("file", "~/.cargo/config"),
        ("file", "~/.pylintrc"),
        ("file", "~/.flake8"),
        ("file", "~/.rubocop.yml"),
        ("file", "~/.eslintrc"),
        ("file", "~/.prettierrc"),
        ("file", "~/.editorconfig"),
    ],
    "Containers & Cloud": [
        ("dir", "~/.docker"),
        ("file", "~/.kube/config"),
        ("dir", "~/.aws"),
        ("dir", "~/.config/gcloud"),
    ],
    "Package Managers": [
        ("file", "~/.nvmrc"),
        ("file", "~/.node-version"),
        ("file", "~/.python-version"),
        ("file", "~/.ruby-version"),
        ("file", "~/.tool-versions"),
    ],
    "Other": [
        ("file", "~/.ssh/config"),
        ("file", "~/.gnupg/gpg-agent.conf"),
        ("dir", "~/.config/gh"),
        ("file", "~/.wgetrc"),
        ("file", "~/.curlrc"),
    ],
}


def add_platform_specific(registry: Dict[str, List[Tuple[str, str]]]) -> None:
    """Add OS-specific config paths."""
    if IS_MACOS:
        registry["Editor"].append(("dir", "~/Library/Application Support/Code/User"))
        registry["Editor"].append(("dir", "~/Library/Application Support/Cursor/User"))
        registry["Editor"].append(("dir", "~/Library/Application Support/Zed"))
        registry["Editor"].append(
            ("dir", "~/Library/Application Support/Sublime Text/Packages/User")
        )
        registry["Terminal"].append(
            ("dir", "~/Library/Application Support/com.mitchellh.ghostty")
        )
        registry["Package Managers"].append(("file", "~/Brewfile"))
    elif IS_WINDOWS:
        # Windows-specific paths
        registry["Editor"].append(("dir", "~/AppData/Roaming/Code/User"))
        registry["Editor"].append(("dir", "~/AppData/Roaming/Cursor/User"))
        registry["Editor"].append(("dir", "~/AppData/Roaming/Zed"))
        registry["Editor"].append(
            ("dir", "~/AppData/Roaming/Sublime Text/Packages/User")
        )
        registry["Terminal"].append(
            ("dir", "~/AppData/Local/Microsoft/Windows Terminal")
        )
        registry["Terminal"].append(("dir", "~/AppData/Roaming/ghostty"))
        registry["Dev Tools"].append(("file", "~/AppData/Roaming/npm/npmrc"))
        registry["Dev Tools"].append(("file", "~/pip/pip.ini"))
        registry["Shell"].extend(
            [
                ("file", "~/Documents/PowerShell/Microsoft.PowerShell_profile.ps1"),
                (
                    "file",
                    "~/Documents/WindowsPowerShell/Microsoft.PowerShell_profile.ps1",
                ),
                ("file", "~/Documents/PowerShell/Microsoft.VSCode_profile.ps1"),
            ]
        )
    else:
        registry["Editor"].append(("dir", "~/.config/Code/User"))
        registry["Editor"].append(("dir", "~/.config/Cursor/User"))
        registry["Editor"].append(("dir", "~/.config/zed"))
        registry["Editor"].append(("dir", "~/.config/sublime-text/Packages/User"))
        registry["Terminal"].append(("dir", "~/.config/ghostty"))


def scan_configs() -> Dict[str, List[ConfigItem]]:
    """Scan for all registered config files."""
    registry = {k: list(v) for k, v in CONFIG_REGISTRY.items()}
    add_platform_specific(registry)

    results = {}
    for category, entries in registry.items():
        items = [check_path(path_str) for _, path_str in entries]
        results[category] = items

    return results


def format_output(results: Dict[str, List[ConfigItem]]) -> str:
    """Format scan results for terminal display."""
    lines = []
    total_found = 0
    software_index = 1

    lines.append(f"{YELLOW}=== Scanning for config files in {HOME} ==={RESET}")
    lines.append("")

    for category, items in results.items():
        visible_items = [item for item in items if item.exists]
        if not visible_items:
            continue
        lines.append(f"{CYAN}[{category}]{RESET}")
        for item in visible_items:
            label = f"{item.size}"
            if item.is_dir and item.file_count is not None:
                label += f", {item.file_count} files"
            lines.append(
                f"  {software_index}. {CHECK} {item.software} {CYAN}({label}){RESET}"
            )
            lines.append(f"      local: {item.path}")
            lines.append(f"      repo:  {item.repo_path}")
            lines.append(
                f"      repo backup exists: {'yes' if item.repo_exists else 'no'}"
            )
            lines.append("      selection: confirm this software individually")
            total_found += 1
            software_index += 1
        lines.append("")

    lines.append(
        f"{YELLOW}=== Scan complete: Found {total_found} config files/directories ==={RESET}"
    )
    lines.append("")
    lines.append(
        "Review each software entry, then choose what to back up into ~/.synconf."
    )
    lines.append(
        "Do not select a whole category; confirm each numbered software item one by one."
    )

    return "\n".join(lines)


def format_json(results: Dict[str, List[ConfigItem]]) -> str:
    """Format scan results as JSON."""
    output = {}
    for category, items in results.items():
        output[category] = [asdict(item) for item in items if item.exists]
    return json.dumps(output, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan for common config files")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    args = parser.parse_args()

    results = scan_configs()

    if args.json:
        print(format_json(results))
    else:
        print(format_output(results))


if __name__ == "__main__":
    main()
