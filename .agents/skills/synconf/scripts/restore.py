#!/usr/bin/env python3
"""Interactively sync configs from the dotfiles repo back to the local machine.

This script reads manifest.json to determine which configs to track,
then syncs selected software configs from the repo to the local machine.
"""

import argparse
import json
import platform
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict

from common import (
    ConflictDecision,
    ConflictRecord,
    OperationRecord,
    append_pending_merge,
    choose_conflict_decisions,
    choose_conflict_plan,
    entries_equal,
    print_diff,
    print_conflict_preview,
    print_operation_records,
    prompt_merge_instructions,
    read_text_file,
    resolve_conflict_action,
)


HOME_TOKEN = "__SYNCONF_HOME__"
HOME_POSIX_TOKEN = "__SYNCONF_HOME_POSIX__"

# Global flag for non-interactive mode
AUTO_YES = False
DOTFILES_DIR = Path(__file__).resolve().parent.parent
MERGE_NOTES_DIR = DOTFILES_DIR / "merge-notes"
PENDING_MERGES_PATH = MERGE_NOTES_DIR / "pending-merges.json"
MANIFEST_PATH = DOTFILES_DIR / "manifest.json"

PLATFORM_RULES: List[Tuple[str, List[str]]] = [
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

CURRENT_PLATFORM: Optional[str] = None


def resolve_repo_dir(repo_dir: Optional[str]) -> Path:
    """Resolve the target synconf repository directory."""
    if repo_dir:
        return Path(repo_dir).expanduser().resolve()
    default_repo_dir = Path.home() / ".synconf"
    if default_repo_dir.exists():
        return default_repo_dir
    return Path(__file__).resolve().parent.parent


def configure_repo_paths(repo_dir: Path) -> None:
    """Update module-level paths to target the selected repository."""
    global DOTFILES_DIR
    global MERGE_NOTES_DIR
    global PENDING_MERGES_PATH
    global MANIFEST_PATH
    DOTFILES_DIR = repo_dir
    MERGE_NOTES_DIR = repo_dir / "merge-notes"
    PENDING_MERGES_PATH = MERGE_NOTES_DIR / "pending-merges.json"
    MANIFEST_PATH = repo_dir / "manifest.json"


def path_from_rel(path_str: str) -> Path:
    """Convert a relative path string to Path object."""
    return Path(path_str)


def normalize_text(text: str) -> str:
    """Replace home paths with placeholders for portability."""
    home = Path.home()
    return text.replace(home.as_posix(), HOME_POSIX_TOKEN).replace(
        str(home), HOME_TOKEN
    )


def render_text(text: str) -> str:
    """Replace placeholders with actual home paths."""
    home = Path.home()
    return text.replace(HOME_POSIX_TOKEN, home.as_posix()).replace(
        HOME_TOKEN, str(home)
    )


def prompt_yes_no(message: str, default: bool = False) -> bool:
    """Prompt for yes/no confirmation."""
    if AUTO_YES:
        return True
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(message + " " + suffix + " ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def load_manifest() -> Dict[str, Any]:
    """Load manifest.json or return default structure."""
    if not MANIFEST_PATH.exists():
        return {"version": 1, "files": []}
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "files": []}


def save_manifest(payload: Dict[str, Any]) -> None:
    """Save manifest.json."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def detect_environment(manifest: Dict[str, Any]) -> None:
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
    print("- Home: " + str(Path.home()))
    print("- Repo: " + str(DOTFILES_DIR))
    print("- Repo exists: yes")
    print("- Python configured: " + ("yes" if sys.executable else "no"))
    print("- Python executable: " + (sys.executable or "not found"))
    print("- Existing tracked configs: " + str(len(manifest.get("files", []))))
    print("- Config roots: " + ", ".join(config_roots))
    print()


def choose_conflict_action(direction: str = "backup") -> str:
    """Prompt user to choose how to handle a conflict."""
    if AUTO_YES:
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


def collect_conflicts(
    entries: List[Dict[str, Any]],
    home_dir: Optional[Path] = None,
    repo_dir: Optional[Path] = None,
) -> List[ConflictRecord]:
    """Collect selected restore entries whose repo and local versions differ."""
    resolved_home = home_dir or Path.home()
    resolved_repo = repo_dir or DOTFILES_DIR
    conflicts: List[ConflictRecord] = []

    for entry in entries:
        repo_path = resolved_repo / path_from_rel(entry["repo_rel"])
        local_path = resolved_home / path_from_rel(entry["home_rel"])
        if not repo_path.exists() or not (local_path.exists() or local_path.is_symlink()):
            continue
        if entries_equal(repo_path, local_path, entry["is_dir"]):
            continue
        conflicts.append(
            {
                "entry": entry,
                "source": str(repo_path),
                "target": str(local_path),
            }
        )

    return conflicts


# ANSI color codes
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


def normalize_platform_name(name: str) -> str:
    """Normalize platform labels for consistent comparison."""
    lowered = name.strip().lower()
    if lowered == "darwin":
        return "macos"
    if lowered in {"windows", "win32"}:
        return "windows"
    if lowered == "linux":
        return "linux"
    return lowered or "unknown"


CURRENT_PLATFORM = normalize_platform_name(platform.system())


def format_platform_name(name: str) -> str:
    """Format platform name for display."""
    labels = {"macos": "macOS", "windows": "Windows", "linux": "Linux"}
    return labels.get(name, name)


def detect_supported_platforms(entry: Dict[str, Any]) -> Optional[List[str]]:
    """Infer which platforms a config entry supports."""
    stored = entry.get("platforms")
    if isinstance(stored, list) and stored:
        normalized: List[str] = []
        for item in stored:
            platform_name = normalize_platform_name(str(item))
            if platform_name not in normalized:
                normalized.append(platform_name)
        if normalized:
            return normalized

    combined = " ".join(
        [
            str(entry.get("home_rel", "")).replace("\\", "/").lower(),
            str(entry.get("repo_rel", "")).replace("\\", "/").lower(),
            str(entry.get("software", "")).strip().lower(),
        ]
    )
    for pattern, platforms in PLATFORM_RULES:
        if pattern in combined:
            return [normalize_platform_name(item) for item in platforms]
    return None


def filter_entries_for_current_platform(
    entries: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Separate entries into supported and unsupported for current platform."""
    supported: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    for entry in entries:
        platforms = detect_supported_platforms(entry)
        if platforms and CURRENT_PLATFORM not in platforms:
            skipped.append(entry)
            continue
        supported.append(entry)
    return supported, skipped


def report_filtered_entries(entries: List[Dict[str, Any]]) -> None:
    """Print list of entries filtered out for this platform."""
    if not entries:
        return

    print("Skipping repo backups that do not support this platform:")
    for entry in entries:
        platforms = detect_supported_platforms(entry) or []
        platform_label = ", ".join(format_platform_name(item) for item in platforms)
        print(f"- {entry['software']} (supported: {platform_label})")
    print()


def copy_entry(src: Path, dest: Path, is_dir: bool) -> None:
    """Copy repo config to local with placeholder rendering."""
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


def choose_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Prompt user to select which configs to restore."""
    print("Scan results: repo backup + local environment")
    print("Confirm each numbered software entry individually before syncing to local.")
    chosen: List[Dict[str, Any]] = []
    for index, entry in enumerate(entries, start=1):
        repo_path = DOTFILES_DIR / path_from_rel(entry["repo_rel"])
        local_path = Path.home() / path_from_rel(entry["home_rel"])
        local_exists = local_path.exists() or local_path.is_symlink()
        print(f"{index}. {entry['software']}")
        print(f"   repo:   {repo_path}")
        print(f"   local:  {local_path}")
        print(
            f"   repo backup exists: {'yes' if repo_path.exists() or repo_path.is_symlink() else 'no'}"
        )
        print(f"   local config exists: {'yes' if local_exists else 'no'}")
        print("   selection: confirm this software individually")
        if prompt_yes_no("   Sync this software from repo to local?"):
            chosen.append(entry)

    print()
    if chosen:
        print("Selected software for repo-to-local sync:")
        for index, entry in enumerate(chosen, start=1):
            print(f"  {index}. {entry['software']}")
    else:
        print("Selected software: none")
    return chosen


def main() -> None:
    """Main entry point."""
    global AUTO_YES
    parser = argparse.ArgumentParser(description="Restore configs from dotfiles repo")
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip all interactive confirmations (non-interactive mode)",
    )
    parser.add_argument(
        "--repo-dir",
        type=str,
        help="Target synconf repo to restore from (default: ~/.synconf when it exists)",
    )
    args = parser.parse_args()
    AUTO_YES = args.yes
    configure_repo_paths(resolve_repo_dir(args.repo_dir))

    print("Syncing configs from repo to local machine...")
    print(f"Repository: {DOTFILES_DIR}")
    print()

    manifest = load_manifest()
    detect_environment(manifest)
    supported_entries, filtered_entries = filter_entries_for_current_platform(
        manifest.get("files", [])
    )
    report_filtered_entries(filtered_entries)
    selected_entries = choose_entries(supported_entries)
    if not selected_entries:
        if not supported_entries:
            print("No compatible repo backups are available for this platform.")
        else:
            print("No configs selected. Nothing to sync.")
        return
    conflicts = collect_conflicts(selected_entries)
    print_conflict_preview(conflicts, "restore writes any files")
    default_conflict_action = choose_conflict_plan(
        conflicts,
        AUTO_YES,
        "Detected conflicts before repo-to-local sync:",
        "repo",
        "local",
        "use the repo version for every conflict",
        "leave every conflicting local config unchanged",
    )
    conflict_decisions = choose_conflict_decisions(
        conflicts,
        default_conflict_action,
        AUTO_YES,
        "Review per-conflict exceptions before repo-to-local sync writes any files.",
        "repo",
        "local",
    )

    summary: Dict[str, List[str]] = {
        "synced": [],
        "unchanged": [],
        "skipped": [],
        "manual": [],
        "missing_in_repo": [],
    }
    operations: List[OperationRecord] = []

    for entry in selected_entries:
        repo_path = DOTFILES_DIR / path_from_rel(entry["repo_rel"])
        local_path = Path.home() / path_from_rel(entry["home_rel"])
        target_exists_before = local_path.exists() or local_path.is_symlink()

        if not repo_path.exists():
            print(f"Warning: {repo_path} not found in repo, skipping")
            summary["missing_in_repo"].append(entry["software"])
            operations.append(
                {
                    "software": entry["software"],
                    "source": str(repo_path),
                    "target": str(local_path),
                    "target_exists_before": target_exists_before,
                    "action": "skip-missing-source",
                }
            )
            continue

        local_path.parent.mkdir(parents=True, exist_ok=True)

        if target_exists_before:
            print()
            print(f"Reviewing {entry['software']}")
            print(f"- Repo:   {repo_path}")
            print(f"- Local:  {local_path}")
            if entries_equal(repo_path, local_path, entry["is_dir"]):
                print(
                    "No differences detected. Local config already matches the repo backup."
                )
                summary["unchanged"].append(entry["software"])
                operations.append(
                    {
                        "software": entry["software"],
                        "source": str(repo_path),
                        "target": str(local_path),
                        "target_exists_before": target_exists_before,
                        "action": "unchanged",
                    }
                )
                continue

            note_path = None
            if print_diff(repo_path, local_path, entry["is_dir"], "repo", "local"):
                action = resolve_conflict_action(
                    entry,
                    default_conflict_action,
                    conflict_decisions,
                )
                if default_conflict_action == "review":
                    note_path = prompt_merge_instructions(
                        entry,
                        AUTO_YES,
                        MERGE_NOTES_DIR,
                        DOTFILES_DIR,
                        "restore",
                    )
                    action = choose_conflict_action("restore")
                if action == "skip":
                    print(f"Skipped {entry['software']}")
                    summary["skipped"].append(entry["software"])
                    operations.append(
                        {
                            "software": entry["software"],
                            "source": str(repo_path),
                            "target": str(local_path),
                            "target_exists_before": target_exists_before,
                            "action": "skip-conflict",
                        }
                    )
                    continue
                if action == "manual":
                    if note_path is None:
                        note_path = prompt_merge_instructions(
                            entry,
                            AUTO_YES,
                            MERGE_NOTES_DIR,
                            DOTFILES_DIR,
                            "restore",
                        )
                    append_pending_merge(
                        entry,
                        note_path,
                        "manual repo-to-local merge requested",
                        PENDING_MERGES_PATH,
                        DOTFILES_DIR,
                        "restore",
                    )
                    print(f"Left {entry['software']} unchanged for manual merge later")
                    summary["manual"].append(entry["software"])
                    operations.append(
                        {
                            "software": entry["software"],
                            "source": str(repo_path),
                            "target": str(local_path),
                            "target_exists_before": target_exists_before,
                            "action": "manual-merge-later",
                        }
                    )
                    continue

        copy_entry(repo_path, local_path, entry["is_dir"])
        print(f"Synced {entry['repo_rel']} -> {local_path}")
        summary["synced"].append(entry["software"])
        operations.append(
            {
                "software": entry["software"],
                "source": str(repo_path),
                "target": str(local_path),
                "target_exists_before": target_exists_before,
                "action": "overwrite" if target_exists_before else "create",
            }
        )

    print()
    print("Repo-to-local sync complete!")
    print(f"- Synced: {len(summary['synced'])}")
    print(f"- Unchanged: {len(summary['unchanged'])}")
    print(f"- Skipped: {len(summary['skipped'])}")
    print(f"- Manual merge later: {len(summary['manual'])}")
    print(f"- Missing in repo: {len(summary['missing_in_repo'])}")
    if summary["manual"]:
        print(f"Pending manual merges recorded in: {PENDING_MERGES_PATH}")
    print_operation_records(operations)


if __name__ == "__main__":
    main()
