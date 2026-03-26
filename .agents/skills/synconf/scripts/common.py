#!/usr/bin/env python3
"""Shared constants and utilities for synconf scripts.

This module provides common functionality used by init_repo.py and other scripts.
Compatible with Python 3.8+ (avoids 3.9+ type syntax).
"""

import difflib
import json
import logging
import platform
import shutil
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

# Configure module-level logger
logger = logging.getLogger("synconf")

# Constants
HOME = Path.home()
IS_MACOS = platform.system() == "Darwin"
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
DEFAULT_REPO_DIR = HOME / ".synconf"
SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS_DIR.parent
REPO_TEMPLATE_DIR = SKILL_DIR / "assets" / "repo-template"

# Placeholder tokens for home path normalization
HOME_TOKEN = "__SYNCONF_HOME__"
HOME_POSIX_TOKEN = "__SYNCONF_HOME_POSIX__"
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
    "scan.py",
    "manage.py",
    "backup.py",
    "restore.py",
    "sync.py",
    "init_repo.py",
    "common.py",
    "config.json",
]
FALLBACK_INSTALL_SCRIPT = """#!/usr/bin/env python3
\"\"\"Install dotfiles by copying repo configs into the local machine.

This script reads manifest.json to determine which configs to install,
then copies them from the repo to the local machine, backing up existing files.
\"\"\"

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


DOTFILES_DIR = Path(__file__).resolve().parent
BACKUP_DIR = Path.home() / ".synconf-backup" / datetime.now().strftime("%Y%m%d-%H%M%S")
MANIFEST_PATH = DOTFILES_DIR / "manifest.json"
HOME_TOKEN = "__SYNCONF_HOME__"
HOME_POSIX_TOKEN = "__SYNCONF_HOME_POSIX__"


def path_from_rel(path_str: str) -> Path:
    \"\"\"Convert a relative path string to Path object.\"\"\"
    return Path(path_str)


def read_text_file(path: Path) -> Optional[str]:
    \"\"\"Read a text file, returning None if not readable as UTF-8.\"\"\"
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def render_text(text: str) -> str:
    \"\"\"Replace placeholders with actual home paths.\"\"\"
    home = Path.home()
    return text.replace(HOME_POSIX_TOKEN, home.as_posix()).replace(HOME_TOKEN, str(home))


def contains_placeholders(path: Path) -> bool:
    \"\"\"Check if a file or directory contains home path placeholders.\"\"\"
    if path.is_dir():
        return any(contains_placeholders(child) for child in path.rglob("*") if child.is_file())
    text = read_text_file(path)
    return bool(text and (HOME_TOKEN in text or HOME_POSIX_TOKEN in text))


def remove_path(path: Path) -> None:
    \"\"\"Remove a file or directory.\"\"\"
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def backup_existing(dst: Path) -> None:
    \"\"\"Backup existing local config before overwriting.\"\"\"
    if not dst.exists() and not dst.is_symlink():
        return

    backup_target = BACKUP_DIR / dst.relative_to(Path.home())
    backup_target.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.move(str(dst), str(backup_target))
    print(f"Backed up {dst} -> {backup_target}")


def copy_path(src: Path, dst: Path) -> None:
    \"\"\"Copy a file or directory.\"\"\"
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)


def copy_with_render(src: Path, dst: Path) -> None:
    \"\"\"Copy a file or directory, rendering placeholders.\"\"\"
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


def install_file(src: Path, dst: Path, is_dir: bool) -> None:
    \"\"\"Copy a repo config into the local machine.\"\"\"
    if dst.exists() or dst.is_symlink():
        backup_existing(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    if contains_placeholders(src):
        copy_with_render(src, dst)
        print(f"Rendered {src} -> {dst}")
        return

    copy_path(src, dst)
    print(f"Copied {src} -> {dst}")


def load_manifest() -> List[Dict[str, object]]:
    \"\"\"Load manifest.json and return the files list.\"\"\"
    if not MANIFEST_PATH.exists():
        return []
    try:
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        return payload.get("files", [])
    except json.JSONDecodeError:
        return []


def main() -> None:
    \"\"\"Main entry point.\"\"\"
    print(f"Installing dotfiles from {DOTFILES_DIR}")
    print()

    files = load_manifest()
    if not files:
        print("No configs found in manifest.json. Nothing to install.")
        return

    for entry in files:
        src = DOTFILES_DIR / path_from_rel(entry["repo_rel"])
        dst = Path.home() / path_from_rel(entry["home_rel"])
        if src.exists():
            install_file(src, dst, entry["is_dir"])
        else:
            print(f"Warning: {src} not found, skipping")

    print()
    print("Dotfiles installed successfully!")
    if BACKUP_DIR.exists():
        print(f"Backup of old files saved to: {BACKUP_DIR}")


if __name__ == "__main__":
    main()
"""


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

    entry: Dict[str, Any]
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


def read_text_file(path: Path) -> Optional[str]:
    """Read a text file, returning None if not readable as UTF-8."""
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def read_text_lines(path: Path) -> Optional[List[str]]:
    """Read a text file as lines."""
    text = read_text_file(path)
    if text is None:
        return None
    return text.splitlines()


def summarize_directory(path: Path) -> List[str]:
    """List all files in a directory recursively."""
    return sorted(
        str(child.relative_to(path)).replace("\\", "/")
        for child in path.rglob("*")
        if child.is_file()
    )


def files_equal(src: Path, dest: Path) -> bool:
    """Check if two files have equal content."""
    src_lines = read_text_lines(src)
    dest_lines = read_text_lines(dest)
    if src_lines is None or dest_lines is None:
        return src.read_bytes() == dest.read_bytes()
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
        same = src.read_bytes() == dest.read_bytes()
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


def save_merge_note(
    entry: Dict[str, Any],
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
        / f"{timestamp}-{direction}-{entry['software'].lower().replace(' ', '-')}.md"
    )
    note_path.write_text(
        "\n".join(
            [
                f"# Merge note for {entry['software']} ({direction})",
                f"- Local path: `{Path.home() / Path(str(entry['home_rel']))}`",
                f"- Repo path: `{repo_dir / Path(str(entry['repo_rel']))}`",
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
    entry: Dict[str, Any],
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
            "software": entry["software"],
            "direction": direction,
            "local_path": str(Path.home() / Path(str(entry["home_rel"]))),
            "repo_path": str(repo_dir / Path(str(entry["repo_rel"]))),
            "reason": reason,
            "merge_note": str(note_path) if note_path else None,
        }
    )
    pending_merges_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Recorded pending merge in {pending_merges_path}")


def prompt_merge_instructions(
    entry: Dict[str, Any],
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
        print(f"{index}. {entry['software']}")
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
        print(f"{index}. {entry['software']}")
        print(f"   {source_label}: {conflict['source']}")
        print(f"   {target_label}: {conflict['target']}")
        override_action = choose_conflict_override(default_action)
        action = override_action or default_action
        decisions[str(entry["repo_rel"])] = {
            "action": action,
            "override": override_action is not None,
        }

    return decisions


def resolve_conflict_action(
    entry: Dict[str, Any],
    default_action: str,
    decisions: Dict[str, ConflictDecision],
) -> str:
    """Resolve the conflict action for one entry."""
    decision = decisions.get(str(entry["repo_rel"]))
    if decision:
        return decision["action"]
    return default_action


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
    category_rules = [
        (".zsh", "shell"),
        (".bash", "shell"),
        (".profile", "shell"),
        (".zprofile", "shell"),
        ("powershell", "shell"),
        ("Microsoft.PowerShell_profile.ps1", "shell"),
        ("Microsoft.VSCode_profile.ps1", "shell"),
        ("fish/config.fish", "shell"),
        (".config/fish", "shell"),
        (".gitconfig", "git"),
        (".gitignore", "git"),
        (".gitmessage", "git"),
        (".vim", "editor"),
        ("nvim", "editor"),
        ("code/user", "editor"),
        ("cursor/user", "editor"),
        ("/zed", "editor"),
        ("sublime text/packages/user", "editor"),
        (".editorconfig", "editor"),
        (".emacs", "editor"),
        (".tmux", "terminal"),
        (".inputrc", "terminal"),
        ("alacritty", "terminal"),
        ("ghostty", "terminal"),
        ("kitty", "terminal"),
        ("wezterm", "terminal"),
        ("Windows Terminal", "terminal"),
        ("iterm2", "terminal"),
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
        ("starship", "prompt"),
        ("oh-my-zsh", "prompt"),
        ("powerlevel10k", "prompt"),
    ]
    text = path.as_posix().lower()
    for pattern, category in category_rules:
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
    software_rules = [
        ("microsoft.powershell_profile.ps1", "PowerShell"),
        ("microsoft.vscode_profile.ps1", "PowerShell"),
        ("fish/config.fish", "Fish"),
        (".config/fish", "Fish"),
        (".zsh", "Zsh"),
        (".bash", "Bash"),
        (".profile", "Shell"),
        ("windows terminal", "Windows Terminal"),
        ("iterm2", "iTerm2"),
        (".tmux", "Tmux"),
        ("alacritty", "Alacritty"),
        ("ghostty", "Ghostty"),
        ("kitty", "Kitty"),
        ("wezterm", "WezTerm"),
        (".inputrc", "Readline"),
        ("code/user", "VS Code"),
        ("cursor/user", "Cursor"),
        ("/zed", "Zed"),
        ("sublime text/packages/user", "Sublime Text"),
        ("nvim", "Neovim"),
        (".vim", "Vim"),
        (".emacs", "Emacs"),
        (".editorconfig", "EditorConfig"),
        (".gitconfig", "Git"),
        (".gitignore", "Git"),
        (".gitmessage", "Git"),
        ("starship", "Starship"),
        ("oh-my-zsh", "Oh My Zsh"),
        ("powerlevel10k", "Powerlevel10k"),
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
    ]
    text = path.as_posix().lower()
    for pattern, software in software_rules:
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


def detect_supported_platforms(src: Path, software: str) -> Optional[List[str]]:
    """Infer platform support for a config path.

    Returns None when the config is cross-platform.
    """
    text = src.as_posix().lower()
    software_lower = software.lower()

    if "appdata/" in text or "appdata\\" in str(src).lower():
        return ["windows"]
    if "library/application support/" in text:
        return ["macos"]
    if "/.config/" in text:
        if software_lower in {"ghostty", "kitty", "zed", "cursor", "vs code"}:
            return ["linux"]
    return None


def setup_logging(verbose: bool) -> None:
    """Configure logging for CLI scripts."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")


def ensure_repo_layout(repo_dir: Path) -> None:
    """Ensure the standard synconf directory layout exists."""
    repo_dir.mkdir(parents=True, exist_ok=True)
    for subdir in REPO_SUBDIRECTORIES:
        (repo_dir / subdir).mkdir(parents=True, exist_ok=True)


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
        shutil.copy2(src, dest)
        if dest.suffix == ".py":
            dest.chmod(0o755)


def ensure_install_script(repo_dir: Path) -> None:
    """Ensure install.py exists at the repo root."""
    install_dest = repo_dir / "install.py"
    install_src = REPO_TEMPLATE_DIR / "install.py"

    if install_src.exists():
        shutil.copy2(install_src, install_dest)
    else:
        install_dest.write_text(FALLBACK_INSTALL_SCRIPT, encoding="utf-8")

    install_dest.chmod(0o755)


def tracked_paths_from_manifest(entries: List[Dict[str, Any]]) -> List[str]:
    """Return stable display paths for README generation."""
    tracked_paths: List[str] = []
    for entry in entries:
        home_rel = str(entry.get("home_rel", "")).strip()
        if not home_rel:
            continue
        tracked_paths.append("~/" + home_rel)
    return sorted(set(tracked_paths))


def write_repo_readme(repo_dir: Path, tracked_paths: List[str]) -> None:
    """Write the root README.md for the synconf repo."""
    configs_block = "\n".join(
        f"- `{path}`" for path in tracked_paths
    ) if tracked_paths else "- (none)"

    readme = f"""# Dotfiles

My personal configuration files, managed with copy-based sync.

Repository path: `{repo_dir}`

## Installation

```bash
cd {repo_dir}
python3 install.py
```

On Windows, run `py -3 install.py` from PowerShell.

## Included Configs

{configs_block}

## Usage

### Quick Start

```bash
# Step 1: Scan for configs and append newly discovered entries to manifest.json
python3 scripts/scan.py

# Step 2: Review and optionally edit manifest.json
# You can manually edit manifest.json to add/remove tracked software

# Step 3: Backup selected configs to repo
python3 scripts/backup.py

# Step 4: (Optional) Restore configs from repo to local
python3 scripts/restore.py

# Step 5: Sync with Git remote
python3 scripts/sync.py
```

### All Commands

- `python3 scripts/scan.py` - Scan home directory and append newly discovered configs to manifest.json without overwriting existing entries
- `python3 scripts/manage.py --list` - List all tracked software in manifest.json
- `python3 scripts/backup.py` - Backup local configs to repo and refresh missing scaffold files
- `python3 scripts/restore.py` - Restore configs with platform filtering
- `python3 scripts/sync.py` - Run repeated sync rounds with Git push
- `python3 install.py` - Install all tracked configs to local machine

Tracked software inventory is persisted in `manifest.json`.
The manifest is human-readable and can be manually edited.

Backup and restore scripts print environment detection details.
Restore filters out backups for other platforms before confirmation.
Manual merge follow-ups are tracked in `merge-notes/pending-merges.json`.
Text configs use `__SYNCONF_HOME__` / `__SYNCONF_HOME_POSIX__` placeholders.

If you later add a remote:

```bash
git remote add origin <repo-url>
git push -u origin main
```
"""
    (repo_dir / "README.md").write_text(readme, encoding="utf-8")


def ensure_repo_scaffold(repo_dir: Path, tracked_paths: List[str]) -> None:
    """Ensure a synconf repo has its expected directories and static files."""
    ensure_repo_layout(repo_dir)
    copy_runtime_scripts(repo_dir)
    ensure_install_script(repo_dir)
    write_repo_readme(repo_dir, tracked_paths)
