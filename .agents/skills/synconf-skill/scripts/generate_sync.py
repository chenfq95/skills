#!/usr/bin/env python3
"""Generate a dotfiles repository with install, backup, and sync scripts.

Usage:
    python3 generate_sync.py ~/.zshrc ~/.gitconfig ~/.vimrc
    python3 generate_sync.py --repo-dir ~/dotfiles ~/.zshrc ~/.gitconfig
"""

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


DEFAULT_REPO_DIR = Path.home() / ".synconf"


# Category detection rules: (pattern, category)
# Order matters - first match wins
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


@dataclass
class FileMapping:
    source: str
    software: str
    category: str
    repo_rel: str
    home_rel: str
    is_dir: bool


def write_manifest(dotfiles_dir: Path, mappings: List[FileMapping]) -> None:
    """Persist tracked config metadata for future incremental sync runs."""
    manifest_path = dotfiles_dir / "manifest.json"
    payload = {
        "version": 1,
        "files": [
            asdict(mapping)
            for mapping in sorted(mappings, key=lambda item: item.repo_rel)
        ],
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Updated manifest.json")


def load_manifest(dotfiles_dir: Path) -> List[FileMapping]:
    """Load previously tracked mappings from manifest.json."""
    manifest_path = dotfiles_dir / "manifest.json"
    if not manifest_path.exists():
        return []

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    mappings = []
    for item in payload.get("files", []):
        try:
            mappings.append(FileMapping(**item))
        except TypeError:
            continue
    return mappings


def merge_mappings(
    existing: List[FileMapping], new: List[FileMapping]
) -> List[FileMapping]:
    """Merge newly selected mappings into the tracked manifest state."""
    merged = {mapping.repo_rel: mapping for mapping in existing}
    for mapping in new:
        merged[mapping.repo_rel] = mapping
    return [merged[key] for key in sorted(merged)]


SOFTWARE_RULES = [
    ("microsoft.powershell_profile.ps1", "PowerShell"),
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


def categorize_file(path: Path) -> str:
    """Determine the category for a config file."""
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


def relative_to_home(path: Path) -> Path:
    """Return a path relative to the user's home directory when possible."""
    home = Path.home().resolve()
    try:
        return path.resolve().relative_to(home)
    except ValueError:
        return Path(path.name)


def display_home_path(path: Path) -> str:
    """Return a stable ~/ path for display."""
    rel = relative_to_home(path)
    return "~/" + rel.as_posix() if rel.as_posix() != "." else "~"


def repo_relative_path(src: Path, category: str) -> Path:
    """Place copied configs under category while preserving home-relative structure."""
    rel = relative_to_home(src)
    return Path(category) / rel


def ensure_repo_dir(dotfiles_dir: Path) -> None:
    """Create the repository directory if needed."""
    dotfiles_dir.mkdir(parents=True, exist_ok=True)


def ensure_git_repo(dotfiles_dir: Path) -> None:
    """Initialize the repository when needed."""
    git_dir = dotfiles_dir / ".git"
    if git_dir.exists():
        print(f"Reusing existing Git repository at {dotfiles_dir}")
        return

    result = subprocess.run(
        ["git", "init", str(dotfiles_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown git error"
        raise RuntimeError(f"Failed to initialize Git repository: {message}")

    print(f"Initialized Git repository at {dotfiles_dir}")


def copy_files(dotfiles_dir: Path, files: List[str]) -> List[FileMapping]:
    """Copy files into categorized directories and return installation mappings."""
    mappings = []

    for file_str in files:
        src = Path(file_str).expanduser().resolve()
        if not src.exists():
            print(f"Warning: {src} not found, skipping")
            continue

        category = categorize_file(src)
        repo_rel = repo_relative_path(src, category)
        dest = dotfiles_dir / repo_rel
        dest.parent.mkdir(parents=True, exist_ok=True)

        if src.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)

        mappings.append(
            FileMapping(
                source=str(src),
                software=infer_software(src),
                category=category,
                repo_rel=repo_rel.as_posix(),
                home_rel=relative_to_home(src).as_posix(),
                is_dir=src.is_dir(),
            )
        )
        print(f"Copied {src} -> {repo_rel.as_posix()}")

    return mappings


def generate_install(dotfiles_dir: Path, mappings: List[FileMapping]) -> None:
    """Generate install.py script."""
    entries = [
        asdict(mapping) for mapping in sorted(mappings, key=lambda item: item.repo_rel)
    ]

    script = f'''#!/usr/bin/env python3
"""Install dotfiles by copying repo configs into the local machine."""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional


DOTFILES_DIR = Path(__file__).resolve().parent
BACKUP_DIR = Path.home() / ".synconf-backup" / datetime.now().strftime("%Y%m%d-%H%M%S")
HOME_TOKEN = "__SYNCONF_HOME__"
HOME_POSIX_TOKEN = "__SYNCONF_HOME_POSIX__"

FILES = {entries!r}


def path_from_rel(path_str: str) -> Path:
    return Path(path_str)


def normalize_text(text: str) -> str:
    home = Path.home()
    return text.replace(home.as_posix(), HOME_POSIX_TOKEN).replace(str(home), HOME_TOKEN)


def render_text(text: str) -> str:
    home = Path.home()
    return text.replace(HOME_POSIX_TOKEN, home.as_posix()).replace(HOME_TOKEN, str(home))


def read_text_file(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def contains_placeholders(path: Path) -> bool:
    if path.is_dir():
        return any(contains_placeholders(child) for child in path.rglob("*") if child.is_file())
    text = read_text_file(path)
    return bool(text and (HOME_TOKEN in text or HOME_POSIX_TOKEN in text))


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def backup_existing(dst: Path) -> None:
    if not dst.exists() and not dst.is_symlink():
        return

    backup_target = BACKUP_DIR / dst.relative_to(Path.home())
    backup_target.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.move(str(dst), str(backup_target))
    print(f"Backed up {{dst}} -> {{backup_target}}")


def copy_path(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)


def copy_with_render(src: Path, dst: Path) -> None:
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
    """Copy a repo config into the local machine."""
    if dst.exists() or dst.is_symlink():
        backup_existing(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    if contains_placeholders(src):
        copy_with_render(src, dst)
        print(f"Rendered {{src}} -> {{dst}}")
        return

    copy_path(src, dst)
    print(f"Copied {{src}} -> {{dst}}")


def main() -> None:
    print(f"Installing dotfiles from {{DOTFILES_DIR}}")

    for entry in FILES:
        src = DOTFILES_DIR / path_from_rel(entry["repo_rel"])
        dst = Path.home() / path_from_rel(entry["home_rel"])
        if src.exists():
            install_file(src, dst, entry["is_dir"])
        else:
            print(f"Warning: {{src}} not found, skipping")

    print()
    print(f"Dotfiles installed successfully!")
    if BACKUP_DIR.exists():
        print(f"Backup of old files saved to: {{BACKUP_DIR}}")


if __name__ == "__main__":
    main()
'''
    script_path = dotfiles_dir / "install.py"
    script_path.write_text(script)
    script_path.chmod(0o755)
    print(f"Generated install.py")


def generate_backup(dotfiles_dir: Path, mappings: List[FileMapping]) -> None:
    """Generate backup.py script."""
    entries = [
        asdict(mapping) for mapping in sorted(mappings, key=lambda item: item.repo_rel)
    ]

    script = f'''#!/usr/bin/env python3
"""Interactively backup current configs into the dotfiles repo."""

import difflib
import json
import platform
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


DOTFILES_DIR = Path(__file__).resolve().parent.parent
MERGE_NOTES_DIR = DOTFILES_DIR / "merge-notes"
PENDING_MERGES_PATH = MERGE_NOTES_DIR / "pending-merges.json"
MANIFEST_PATH = DOTFILES_DIR / "manifest.json"
HOME_TOKEN = "__SYNCONF_HOME__"
HOME_POSIX_TOKEN = "__SYNCONF_HOME_POSIX__"

FILES = {entries!r}


def path_from_rel(path_str: str) -> Path:
    return Path(path_str)


def read_text_file(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def normalize_text(text: str) -> str:
    home = Path.home()
    return text.replace(home.as_posix(), HOME_POSIX_TOKEN).replace(str(home), HOME_TOKEN)


def load_manifest() -> Dict[str, object]:
    if not MANIFEST_PATH.exists():
        return {{"version": 1, "files": FILES}}
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {{"version": 1, "files": FILES}}


def save_manifest(payload: Dict[str, object]) -> None:
    MANIFEST_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def update_manifest_entries(entries: List[Dict[str, object]]) -> None:
    payload = load_manifest()
    file_map = dict((item["repo_rel"], item) for item in payload.get("files", []))
    for entry in entries:
        file_map[entry["repo_rel"]] = entry
    payload["files"] = [file_map[key] for key in sorted(file_map)]
    save_manifest(payload)


def detect_environment(manifest: Dict[str, object]) -> None:
    config_roots = [
        "~/.config",
        "~/Library/Application Support",
        "~/AppData/Roaming",
        "~/AppData/Local",
        "~/Documents/PowerShell",
    ]
    print("Environment detection:")
    print("- OS: " + platform.system())
    print("- Home: " + str(Path.home()))
    print("- Repo: " + str(DOTFILES_DIR))
    print("- Repo exists: yes")
    print("- Python configured: " + ("yes" if sys.executable else "no"))
    print("- Python executable: " + (sys.executable or "not found"))
    print("- Existing tracked configs: " + str(len(manifest.get("files", []))))
    print("- Config roots: " + ", ".join(config_roots))
    print()


def prompt_yes_no(message: str, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(message + " " + suffix + " ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def read_text_lines(path: Path) -> Optional[List[str]]:
    text = read_text_file(path)
    if text is None:
        return None
    return text.splitlines()


def summarize_directory(path: Path) -> List[str]:
    return sorted(
        str(child.relative_to(path)).replace('\\\\', '/')
        for child in path.rglob('*')
        if child.is_file()
    )


def files_equal(src: Path, dest: Path) -> bool:
    src_lines = read_text_lines(src)
    dest_lines = read_text_lines(dest)
    if src_lines is None or dest_lines is None:
        return src.read_bytes() == dest.read_bytes()
    return src_lines == dest_lines


def directories_equal(src: Path, dest: Path) -> bool:
    src_entries = summarize_directory(src)
    dest_entries = summarize_directory(dest)
    if src_entries != dest_entries:
        return False
    return all(files_equal(src / rel_path, dest / rel_path) for rel_path in src_entries)


def entries_equal(src: Path, dest: Path, is_dir: bool) -> bool:
    if not dest.exists():
        return False
    if is_dir:
        return directories_equal(src, dest)
    return files_equal(src, dest)


def diff_file(src: Path, dest: Path) -> bool:
    src_lines = read_text_lines(src)
    dest_lines = read_text_lines(dest)
    if src_lines is None or dest_lines is None:
        same = src.read_bytes() == dest.read_bytes()
        if not same:
            print("Binary or non-UTF8 file differs; review manually before merging.")
        return not same

    if src_lines == dest_lines:
        return False

    for line in difflib.unified_diff(
        dest_lines,
        src_lines,
        fromfile=f"repo/{{dest}}",
        tofile=f"local/{{src}}",
        lineterm="",
    ):
        print(line)
    return True


def print_diff(src: Path, dest: Path, is_dir: bool) -> bool:
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
                fromfile=f"repo/{{dest}}",
                tofile=f"local/{{src}}",
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
            print(f"Diff for {{rel_path}}:")
            diff_file(src_file, dest_file)

        if not differs:
            return False
        return True

    print("File contents differ:")
    return diff_file(src, dest)


def save_merge_note(entry: Dict[str, object], note: str) -> Path:
    MERGE_NOTES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    note_path = MERGE_NOTES_DIR / f"{{timestamp}}-{{entry['software'].lower().replace(' ', '-')}}.md"
    note_path.write_text(
        "\n".join(
            [
                f"# Merge note for {{entry['software']}}",
                f"- Local path: `{{Path.home() / path_from_rel(entry['home_rel'])}}`",
                f"- Repo path: `{{DOTFILES_DIR / path_from_rel(entry['repo_rel'])}}`",
                "",
                "## User instructions",
                note.strip() or "(none)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Saved merge note to {{note_path}}")
    return note_path


def append_pending_merge(entry: Dict[str, object], note_path: Optional[Path], reason: str) -> None:
    MERGE_NOTES_DIR.mkdir(parents=True, exist_ok=True)
    if PENDING_MERGES_PATH.exists():
        try:
            payload = json.loads(PENDING_MERGES_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {"items": []}
    else:
        payload = {"items": []}

    payload.setdefault("items", []).append(
        {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
            "software": entry["software"],
            "local_path": str(Path.home() / path_from_rel(entry["home_rel"])),
            "repo_path": str(DOTFILES_DIR / path_from_rel(entry["repo_rel"])),
            "reason": reason,
            "merge_note": str(note_path) if note_path else None,
        }
    )
    PENDING_MERGES_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Recorded pending merge in {{PENDING_MERGES_PATH}}")


def copy_entry(src: Path, dest: Path, is_dir: bool) -> None:
    if is_dir:
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        for child in dest.rglob("*"):
            if not child.is_file():
                continue
            text = read_text_file(child)
            if text is not None:
                child.write_text(normalize_text(text), encoding="utf-8")
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = read_text_file(src)
        if text is None:
            shutil.copy2(src, dest)
        else:
            dest.write_text(normalize_text(text), encoding="utf-8")


def prompt_merge_instructions(entry: Dict[str, object]) -> Optional[Path]:
    print("Describe how these two versions should be merged.")
    print("Press Enter on an empty line to finish. Leave blank to skip.")
    lines = []
    while True:
        line = input("> ")
        if not line:
            break
        lines.append(line)
    if lines:
        return save_merge_note(entry, "\n".join(lines))
    return None


def choose_conflict_action() -> str:
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


def choose_entries(entries: List[Dict[str, object]]) -> List[Dict[str, object]]:
    print("Select which software configs to back up into ~/.synconf:")
    print("Confirm each numbered software entry individually.")
    chosen = []
    for index, entry in enumerate(entries, start=1):
        local_path = Path.home() / path_from_rel(entry["home_rel"])
        repo_path = DOTFILES_DIR / path_from_rel(entry["repo_rel"])
        repo_exists = repo_path.exists() or repo_path.is_symlink()
        print(f"{{index}}. {{entry['software']}}")
        print(f"   local: {{local_path}}")
        print(f"   repo:  {{repo_path}}")
        print(f"   repo backup exists: {{'yes' if repo_exists else 'no'}}")
        print("   selection: confirm this software individually")
        if prompt_yes_no("   Back up this software config?"):
            chosen.append(entry)

    print()
    if chosen:
        print("Selected software:")
        for index, entry in enumerate(chosen, start=1):
            print(f"  {{index}}. {{entry['software']}}")
    else:
        print("Selected software: none")
    return chosen


def main() -> None:
    print("Backing up current configs to dotfiles repo...")
    print(f"Repository: {{DOTFILES_DIR}}")
    print()

    manifest = load_manifest()
    detect_environment(manifest)
    selected_entries = choose_entries(manifest.get("files", FILES))
    if not selected_entries:
        print("No configs selected. Nothing to back up.")
        return

    summary = {
        "backed_up": [],
        "unchanged": [],
        "skipped": [],
        "manual": [],
        "missing": [],
    }

    for entry in selected_entries:
        src = Path.home() / path_from_rel(entry["home_rel"])
        dest = DOTFILES_DIR / path_from_rel(entry["repo_rel"])

        if not src.exists():
            print(f"Warning: {{src}} not found, skipping")
            summary["missing"].append(entry["software"])
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)

        if dest.exists():
            print()
            print(f"Reviewing {{entry['software']}}")
            print(f"- Local: {{src}}")
            print(f"- Repo:  {{dest}}")
            if entries_equal(src, dest, entry["is_dir"]):
                print("No differences detected. Repo backup already matches the local config.")
                summary["unchanged"].append(entry["software"])
                continue
            differs = print_diff(src, dest, entry["is_dir"])
            if differs:
                note_path = prompt_merge_instructions(entry)
                action = choose_conflict_action()
                if action == "skip":
                    print(f"Skipped {{entry['software']}}")
                    summary["skipped"].append(entry["software"])
                    continue
                if action == "manual":
                    append_pending_merge(entry, note_path, "manual merge requested")
                    print(f"Left {{entry['software']}} unchanged for manual merge later")
                    summary["manual"].append(entry["software"])
                    continue

        copy_entry(src, dest, entry["is_dir"])

        print(f"Backed up {{src}} -> {{entry['repo_rel']}}")
        summary["backed_up"].append(entry["software"])

    print()
    print("Backup complete!")
    print(f"- Backed up: {{len(summary['backed_up'])}}")
    print(f"- Unchanged: {{len(summary['unchanged'])}}")
    print(f"- Skipped: {{len(summary['skipped'])}}")
    print(f"- Manual merge later: {{len(summary['manual'])}}")
    print(f"- Missing locally: {{len(summary['missing'])}}")
    if summary["manual"]:
        print(f"Pending manual merges recorded in: {{PENDING_MERGES_PATH}}")
    update_manifest_entries(selected_entries)


if __name__ == "__main__":
    main()
'''
    scripts_dir = dotfiles_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    script_path = scripts_dir / "backup.py"
    script_path.write_text(script)
    script_path.chmod(0o755)
    print(f"Generated scripts/backup.py")


def generate_restore(dotfiles_dir: Path, mappings: List[FileMapping]) -> None:
    """Generate restore.py script."""
    entries = [
        asdict(mapping) for mapping in sorted(mappings, key=lambda item: item.repo_rel)
    ]

    script = f'''#!/usr/bin/env python3
"""Interactively sync configs from the dotfiles repo back to the local machine."""

import difflib
import json
import platform
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


DOTFILES_DIR = Path(__file__).resolve().parent.parent
MERGE_NOTES_DIR = DOTFILES_DIR / "merge-notes"
PENDING_MERGES_PATH = MERGE_NOTES_DIR / "pending-merges.json"
MANIFEST_PATH = DOTFILES_DIR / "manifest.json"

FILES = {entries!r}


def path_from_rel(path_str: str) -> Path:
    return Path(path_str)


def load_manifest() -> Dict[str, object]:
    if not MANIFEST_PATH.exists():
        return {{"version": 1, "files": FILES}}
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {{"version": 1, "files": FILES}}


def read_text_file(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def render_text(text: str) -> str:
    home = Path.home()
    return text.replace(HOME_POSIX_TOKEN, home.as_posix()).replace(HOME_TOKEN, str(home))


def detect_environment(manifest: Dict[str, object]) -> None:
    config_roots = [
        "~/.config",
        "~/Library/Application Support",
        "~/AppData/Roaming",
        "~/AppData/Local",
        "~/Documents/PowerShell",
    ]
    print("Environment detection:")
    print("- OS: " + platform.system())
    print("- Home: " + str(Path.home()))
    print("- Repo: " + str(DOTFILES_DIR))
    print("- Repo exists: yes")
    print("- Python configured: " + ("yes" if sys.executable else "no"))
    print("- Python executable: " + (sys.executable or "not found"))
    print("- Existing tracked configs: " + str(len(manifest.get("files", []))))
    print("- Config roots: " + ", ".join(config_roots))
    print()


def prompt_yes_no(message: str, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(message + " " + suffix + " ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def read_text_lines(path: Path) -> Optional[List[str]]:
    text = read_text_file(path)
    if text is None:
        return None
    return text.splitlines()


def summarize_directory(path: Path) -> List[str]:
    return sorted(
        str(child.relative_to(path)).replace('\\\\', '/')
        for child in path.rglob('*')
        if child.is_file()
    )


def files_equal(src: Path, dest: Path) -> bool:
    src_lines = read_text_lines(src)
    dest_lines = read_text_lines(dest)
    if src_lines is None or dest_lines is None:
        return src.read_bytes() == dest.read_bytes()
    return src_lines == dest_lines


def directories_equal(src: Path, dest: Path) -> bool:
    src_entries = summarize_directory(src)
    dest_entries = summarize_directory(dest)
    if src_entries != dest_entries:
        return False
    return all(files_equal(src / rel_path, dest / rel_path) for rel_path in src_entries)


def entries_equal(src: Path, dest: Path, is_dir: bool) -> bool:
    if not dest.exists():
        return False
    if is_dir:
        return directories_equal(src, dest)
    return files_equal(src, dest)


def diff_file(repo_path: Path, local_path: Path) -> bool:
    repo_lines = read_text_lines(repo_path)
    local_lines = read_text_lines(local_path)
    if repo_lines is None or local_lines is None:
        same = repo_path.read_bytes() == local_path.read_bytes()
        if not same:
            print("Binary or non-UTF8 file differs; review manually before syncing.")
        return not same

    if repo_lines == local_lines:
        return False

    for line in difflib.unified_diff(
        local_lines,
        repo_lines,
        fromfile=f"local/{{local_path}}",
        tofile=f"repo/{{repo_path}}",
        lineterm="",
    ):
        print(line)
    return True


def print_diff(repo_path: Path, local_path: Path, is_dir: bool) -> bool:
    if is_dir:
        repo_entries = summarize_directory(repo_path)
        local_entries = summarize_directory(local_path)
        differs = False
        if repo_entries != local_entries:
            differs = True
            print("Directory file list differs:")
            for line in difflib.unified_diff(
                local_entries,
                repo_entries,
                fromfile=f"local/{{local_path}}",
                tofile=f"repo/{{repo_path}}",
                lineterm="",
            ):
                print(line)

        for rel_path in sorted(set(repo_entries) & set(local_entries)):
            repo_file = repo_path / rel_path
            local_file = local_path / rel_path
            if files_equal(repo_file, local_file):
                continue
            differs = True
            print()
            print(f"Diff for {{rel_path}}:")
            diff_file(repo_file, local_file)

        return differs

    print("File contents differ:")
    return diff_file(repo_path, local_path)


def save_merge_note(entry: Dict[str, object], note: str) -> Path:
    MERGE_NOTES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    note_path = MERGE_NOTES_DIR / f"{{timestamp}}-restore-{{entry['software'].lower().replace(' ', '-')}}.md"
    note_path.write_text(
        "\n".join(
            [
                f"# Restore merge note for {{entry['software']}}",
                f"- Repo path: `{{DOTFILES_DIR / path_from_rel(entry['repo_rel'])}}`",
                f"- Local path: `{{Path.home() / path_from_rel(entry['home_rel'])}}`",
                "",
                "## User instructions",
                note.strip() or "(none)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Saved merge note to {{note_path}}")
    return note_path


def append_pending_merge(entry: Dict[str, object], note_path: Optional[Path], reason: str) -> None:
    MERGE_NOTES_DIR.mkdir(parents=True, exist_ok=True)
    if PENDING_MERGES_PATH.exists():
        try:
            payload = json.loads(PENDING_MERGES_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {{"items": []}}
    else:
        payload = {{"items": []}}

    payload.setdefault("items", []).append(
        {{
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "software": entry["software"],
            "direction": "repo_to_local",
            "local_path": str(Path.home() / path_from_rel(entry["home_rel"])),
            "repo_path": str(DOTFILES_DIR / path_from_rel(entry["repo_rel"])),
            "reason": reason,
            "merge_note": str(note_path) if note_path else None,
        }}
    )
    PENDING_MERGES_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Recorded pending merge in {{PENDING_MERGES_PATH}}")


def copy_entry(src: Path, dest: Path, is_dir: bool) -> None:
    if is_dir:
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        for child in dest.rglob("*"):
            if not child.is_file():
                continue
            text = read_text_file(child)
            if text is not None:
                child.write_text(render_text(text), encoding="utf-8")
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = read_text_file(src)
        if text is None:
            shutil.copy2(src, dest)
        else:
            dest.write_text(render_text(text), encoding="utf-8")


def prompt_merge_instructions(entry: Dict[str, object]) -> Optional[Path]:
    print("Describe how the repo version should be merged into the local version.")
    print("Press Enter on an empty line to finish. Leave blank to skip.")
    lines = []
    while True:
        line = input("> ")
        if not line:
            break
        lines.append(line)
    if lines:
        return save_merge_note(entry, "\n".join(lines))
    return None


def choose_conflict_action() -> str:
    print("Choose what to do with this sync conflict:")
    print("  1. overwrite - replace the local version with the repo version")
    print("  2. skip - keep the local version unchanged for now")
    print("  3. manual - leave both as-is and resolve manually later")
    while True:
        answer = input("Select [1/2/3]: ").strip().lower()
        if answer in {{"1", "overwrite", "o"}}:
            return "overwrite"
        if answer in {{"2", "skip", "s"}}:
            return "skip"
        if answer in {{"3", "manual", "m", "manual-merge"}}:
            return "manual"
        print("Please enter 1, 2, or 3.")


def choose_entries(entries: List[Dict[str, object]]) -> List[Dict[str, object]]:
    print("Scan results: repo backup + local environment")
    print("Confirm each numbered software entry individually before syncing to local.")
    chosen = []
    for index, entry in enumerate(entries, start=1):
        repo_path = DOTFILES_DIR / path_from_rel(entry["repo_rel"])
        local_path = Path.home() / path_from_rel(entry["home_rel"])
        local_exists = local_path.exists() or local_path.is_symlink()
        print(f"{{index}}. {{entry['software']}}")
        print(f"   repo:   {{repo_path}}")
        print(f"   local:  {{local_path}}")
        print(f"   repo backup exists: {{'yes' if repo_path.exists() or repo_path.is_symlink() else 'no'}}")
        print(f"   local config exists: {{'yes' if local_exists else 'no'}}")
        print("   selection: confirm this software individually")
        if prompt_yes_no("   Sync this software from repo to local?"):
            chosen.append(entry)

    print()
    if chosen:
        print("Selected software for repo-to-local sync:")
        for index, entry in enumerate(chosen, start=1):
            print(f"  {{index}}. {{entry['software']}}")
    else:
        print("Selected software: none")
    return chosen


def main() -> None:
    print("Syncing configs from repo to local machine...")
    print(f"Repository: {{DOTFILES_DIR}}")
    print()

    manifest = load_manifest()
    detect_environment(manifest)
    selected_entries = choose_entries(manifest.get("files", FILES))
    if not selected_entries:
        print("No configs selected. Nothing to sync.")
        return

    summary = {{
        "synced": [],
        "unchanged": [],
        "skipped": [],
        "manual": [],
        "missing_in_repo": [],
    }}

    for entry in selected_entries:
        repo_path = DOTFILES_DIR / path_from_rel(entry["repo_rel"])
        local_path = Path.home() / path_from_rel(entry["home_rel"])

        if not repo_path.exists():
            print(f"Warning: {{repo_path}} not found in repo, skipping")
            summary["missing_in_repo"].append(entry["software"])
            continue

        local_path.parent.mkdir(parents=True, exist_ok=True)

        if local_path.exists():
            print()
            print(f"Reviewing {{entry['software']}}")
            print(f"- Repo:   {{repo_path}}")
            print(f"- Local:  {{local_path}}")
            if entries_equal(repo_path, local_path, entry["is_dir"]):
                print("No differences detected. Local config already matches the repo backup.")
                summary["unchanged"].append(entry["software"])
                continue

            note_path = None
            if print_diff(repo_path, local_path, entry["is_dir"]):
                note_path = prompt_merge_instructions(entry)
                action = choose_conflict_action()
                if action == "skip":
                    print(f"Skipped {{entry['software']}}")
                    summary["skipped"].append(entry["software"])
                    continue
                if action == "manual":
                    append_pending_merge(entry, note_path, "manual repo-to-local merge requested")
                    print(f"Left {{entry['software']}} unchanged for manual merge later")
                    summary["manual"].append(entry["software"])
                    continue

        copy_entry(repo_path, local_path, entry["is_dir"])
        print(f"Synced {{entry['repo_rel']}} -> {{local_path}}")
        summary["synced"].append(entry["software"])

    print()
    print("Repo-to-local sync complete!")
    print(f"- Synced: {{len(summary['synced'])}}")
    print(f"- Unchanged: {{len(summary['unchanged'])}}")
    print(f"- Skipped: {{len(summary['skipped'])}}")
    print(f"- Manual merge later: {{len(summary['manual'])}}")
    print(f"- Missing in repo: {{len(summary['missing_in_repo'])}}")
    if summary["manual"]:
        print(f"Pending manual merges recorded in: {{PENDING_MERGES_PATH}}")
'''
    scripts_dir = dotfiles_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    script_path = scripts_dir / "restore.py"
    script_path.write_text(script)
    script_path.chmod(0o755)
    print(f"Generated scripts/restore.py")


def generate_sync(dotfiles_dir: Path) -> None:
    """Generate sync.py script."""
    script = '''#!/usr/bin/env python3
"""Sync dotfiles across one or more interactive rounds."""

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List


DOTFILES_DIR = Path(__file__).parent.parent.resolve()


def run(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    return subprocess.run(cmd, cwd=DOTFILES_DIR, capture_output=True, text=True, **kwargs)


def prompt_yes_no(message: str, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(message + " " + suffix + " ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def run_backup() -> None:
    backup_script = Path(__file__).parent / "backup.py"
    result = run([sys.executable, str(backup_script)])
    if result.returncode != 0:
        print(f"Backup failed: {result.stderr}")
        sys.exit(1)
    print(result.stdout, end="")


def run_restore() -> None:
    restore_script = Path(__file__).parent / "restore.py"
    result = run([sys.executable, str(restore_script)])
    if result.returncode != 0:
        print(f"Restore failed: {result.stderr}")
        sys.exit(1)
    print(result.stdout, end="")


def commit_and_push() -> bool:
    result = run(["git", "add", "-A"])
    if result.returncode != 0:
        print(f"Git add failed: {result.stderr}")
        sys.exit(1)

    result = run(["git", "diff", "--cached", "--quiet"])
    if result.returncode == 0:
        print("No changes to sync")
        return False

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    result = run(["git", "commit", "-m", f"Update configs: {timestamp}"])
    if result.returncode != 0:
        print(f"Git commit failed: {result.stderr}")
        sys.exit(1)

    result = run(["git", "push"])
    if result.returncode != 0:
        print(f"Git push failed: {result.stderr}")
        sys.exit(1)

    print("Dotfiles synced successfully!")
    return True


def run_round(round_number: int) -> None:
    print(f"=== Sync round {round_number} ===")
    run_backup()
    if prompt_yes_no("Run repo-to-local sync after backup?"):
        run_restore()
    commit_and_push()
    print()


def main() -> None:
    print("Syncing dotfiles...")
    round_number = 1
    while True:
        run_round(round_number)
        if not prompt_yes_no("Run another sync round?"):
            break
        round_number += 1


if __name__ == "__main__":
    main()
'''
    scripts_dir = dotfiles_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    script_path = scripts_dir / "sync.py"
    script_path.write_text(script)
    script_path.chmod(0o755)
    print(f"Generated scripts/sync.py")


def generate_readme(dotfiles_dir: Path, files: List[str]) -> None:
    """Generate README.md."""
    config_list = []
    for f in files:
        p = Path(f).expanduser()
        if p.exists():
            config_list.append(f"- `{display_home_path(p)}`")

    configs_block = "\n".join(config_list) if config_list else "- (none)"

    readme = f"""# Dotfiles

My personal configuration files, managed with copy-based sync.

Repository path: `{dotfiles_dir}`

## Installation

```bash
cd {dotfiles_dir}
python3 install.py
```

On Windows, run `py -3 install.py` from PowerShell.

## Included Configs

{configs_block}

## Usage

- `python3 install.py` - Install dotfiles by copying repo files into local config paths
- `python3 scripts/backup.py` - Review configs, confirm each software, and back up selected items
- `python3 scripts/restore.py` - Scan repo + local config state, confirm each software, and sync selected backups to this machine
- `python3 scripts/sync.py` - Run one or more interactive sync rounds with backup, optional repo-to-local sync, commit, and push

Tracked software inventory is persisted in `manifest.json` so later runs can add configs incrementally without rebuilding the repo.

Backup and restore scripts begin by printing environment detection details, including Python availability and tracked manifest count.

Manual merge follow-ups are tracked in `merge-notes/pending-merges.json`.

Text configs may contain `__SYNCONF_HOME__` / `__SYNCONF_HOME_POSIX__` placeholders so they can restore cleanly on a different home directory.

If you later add a remote:

```bash
git remote add origin <repo-url>
git push -u origin main
```
"""
    readme_path = dotfiles_dir / "README.md"
    readme_path.write_text(readme)
    print(f"Generated README.md")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a dotfiles repository with Python scripts"
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Config files to include",
    )
    parser.add_argument(
        "--repo-dir",
        default=str(DEFAULT_REPO_DIR),
        help="Target directory for the dotfiles repo (default: ~/.synconf)",
    )

    args = parser.parse_args()
    dotfiles_dir = Path(args.repo_dir).expanduser().resolve()

    ensure_repo_dir(dotfiles_dir)
    ensure_git_repo(dotfiles_dir)

    existing_mappings = load_manifest(dotfiles_dir)

    # Create directory structure
    for subdir in [
        "shell",
        "git",
        "editor",
        "terminal",
        "dev",
        "scripts",
        "other",
        "merge-notes",
    ]:
        (dotfiles_dir / subdir).mkdir(parents=True, exist_ok=True)

    print(f"Creating dotfiles repo at {dotfiles_dir}")
    print()

    print("Environment detection:")
    print(f"- Home: {Path.home()}")
    print(f"- Repo exists: {'yes' if (dotfiles_dir / '.git').exists() else 'no'}")
    print(f"- Python configured: {'yes' if sys.executable else 'no'}")
    print(f"- Python executable: {sys.executable or 'not found'}")
    print(f"- Existing tracked configs: {len(existing_mappings)}")
    print()

    # Copy files and generate scripts
    new_mappings = copy_files(dotfiles_dir, args.files) if args.files else []
    mappings = merge_mappings(existing_mappings, new_mappings)
    write_manifest(dotfiles_dir, mappings)

    generate_install(dotfiles_dir, mappings)
    generate_backup(dotfiles_dir, mappings)
    generate_restore(dotfiles_dir, mappings)
    generate_sync(dotfiles_dir)
    generate_readme(dotfiles_dir, [mapping.source for mapping in mappings])

    print()
    print(f"=== Dotfiles repo created at {dotfiles_dir} ===")
    print("Files copied and scripts generated.")
    print()
    print("Next steps:")
    print(f"  1. Review the generated files in {dotfiles_dir}")
    print(f"  2. Run python3 {dotfiles_dir / 'install.py'} (or py -3 on Windows)")
    print(
        f"  3. git -C {dotfiles_dir} add -A && git -C {dotfiles_dir} commit -m 'Initial dotfiles'"
    )
    print(
        f"  4. Optional: git -C {dotfiles_dir} remote add origin <your-repo-url> && git -C {dotfiles_dir} push -u origin main"
    )


if __name__ == "__main__":
    main()
