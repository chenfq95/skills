#!/usr/bin/env python3
"""Scan for common config files in the home directory.

Outputs a categorized list of detected config files with their paths.
Supports --json flag for machine-readable output.
"""

import argparse
import json
import platform
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Tuple

from synconf_common import (
    HOME,
    IS_MACOS,
    IS_WINDOWS,
    DEFAULT_REPO_DIR,
    ConfigItem,
    Colors,
    infer_category,
    infer_software,
    relative_to_home,
    human_size,
    count_files,
    setup_logging,
)


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
        ("file", "~/.config/fish/config.fish"),
        ("dir", "~/.config/fish"),
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
        ("file", "~/.pip/pip.conf"),
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
        registry["Terminal"].append(
            ("dir", "~/Library/Application Support/iTerm2")
        )
        registry["Dev Tools"].append(
            ("dir", "~/Library/Application Support/pypoetry")
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
        # Linux
        registry["Editor"].append(("dir", "~/.config/Code/User"))
        registry["Editor"].append(("dir", "~/.config/Cursor/User"))
        registry["Editor"].append(("dir", "~/.config/zed"))
        registry["Editor"].append(("dir", "~/.config/sublime-text/Packages/User"))
        registry["Terminal"].append(("dir", "~/.config/ghostty"))
        registry["Dev Tools"].append(("dir", "~/.config/pypoetry"))


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

    lines.append(f"{Colors.YELLOW}=== Scanning for config files in {HOME} ==={Colors.RESET}")
    lines.append("")

    for category, items in results.items():
        visible_items = [item for item in items if item.exists]
        if not visible_items:
            continue
        lines.append(f"{Colors.CYAN}[{category}]{Colors.RESET}")
        for item in visible_items:
            label = f"{item.size}"
            if item.is_dir and item.file_count is not None:
                label += f", {item.file_count} files"
            lines.append(
                f"  {software_index}. {Colors.check()} {item.software} {Colors.CYAN}({label}){Colors.RESET}"
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
        f"{Colors.YELLOW}=== Scan complete: Found {total_found} config files/directories ==={Colors.RESET}"
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
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    setup_logging(args.verbose)
    results = scan_configs()

    if args.json:
        print(format_json(results))
    else:
        print(format_output(results))


if __name__ == "__main__":
    main()
