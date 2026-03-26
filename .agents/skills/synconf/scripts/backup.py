#!/usr/bin/env python3
"""Interactively backup current configs into the dotfiles repo.

This script reads manifest.json to determine which configs to track,
then backs up selected software configs from the local machine to the repo.
"""

import argparse
import json
import os
import platform
import shutil
import stat
import sys
from pathlib import Path
from typing import Dict, List, Optional, TypedDict, cast

from common import (
    ConflictDecision,
    ConflictRecord,
    OperationRecord,
    append_pending_merge,
    choose_conflict_decisions,
    choose_conflict_plan,
    entries_equal,
    ensure_repo_scaffold,
    print_diff,
    print_conflict_preview,
    print_operation_records,
    prompt_merge_instructions,
    read_text_file,
    resolve_conflict_action,
    tracked_paths_from_manifest,
)


HOME_TOKEN = "__SYNCONF_HOME__"
HOME_POSIX_TOKEN = "__SYNCONF_HOME_POSIX__"

# Global flag for non-interactive mode
AUTO_YES = False
DOTFILES_DIR = Path(__file__).resolve().parent.parent
MERGE_NOTES_DIR = DOTFILES_DIR / "merge-notes"
PENDING_MERGES_PATH = MERGE_NOTES_DIR / "pending-merges.json"
MANIFEST_PATH = DOTFILES_DIR / "manifest.json"


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


class ManifestEntry(TypedDict):
    """Tracked config entry stored in manifest.json."""

    software: str
    home_rel: str
    repo_rel: str
    is_dir: bool


class ManifestPayload(TypedDict):
    """Manifest payload stored in manifest.json."""

    version: int
    files: List[ManifestEntry]


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


def empty_manifest() -> ManifestPayload:
    """Return an empty manifest payload."""
    return {
        "version": 1,
        "files": [],
    }


def load_manifest() -> ManifestPayload:
    """Load manifest.json or return default structure."""
    if not MANIFEST_PATH.exists():
        return empty_manifest()
    try:
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return empty_manifest()
    return cast(ManifestPayload, payload)


def save_manifest(payload: ManifestPayload) -> None:
    """Save manifest.json."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def detect_environment(manifest: ManifestPayload) -> None:
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
    entries: List[ManifestEntry],
    home_dir: Optional[Path] = None,
    repo_dir: Optional[Path] = None,
) -> List[ConflictRecord]:
    """Collect entries whose local and repo versions both exist and differ."""
    resolved_home = home_dir or Path.home()
    resolved_repo = repo_dir or DOTFILES_DIR
    conflicts: List[ConflictRecord] = []

    for entry in entries:
        src = resolved_home / path_from_rel(entry["home_rel"])
        dest = resolved_repo / path_from_rel(entry["repo_rel"])
        if not src.exists() or not (dest.exists() or dest.is_symlink()):
            continue
        if entries_equal(src, dest, entry["is_dir"]):
            continue
        conflicts.append(
            {
                "entry": entry,
                "source": str(src),
                "target": str(dest),
            }
        )

    return conflicts


def update_manifest_entries(entries: List[ManifestEntry]) -> None:
    """Merge backed-up entries into manifest."""
    payload = load_manifest()
    file_map = {item["repo_rel"]: item for item in payload.get("files", [])}
    for entry in entries:
        file_map[entry["repo_rel"]] = entry
    payload["files"] = [file_map[key] for key in sorted(file_map)]
    save_manifest(payload)


def ignore_unsupported_entries(
    root: str,
    names: List[str],
) -> List[str]:
    """Skip sockets, broken symlinks, and transient filesystem entries."""
    ignored = []
    root_path = Path(root)
    for name in names:
        child = root_path / name
        try:
            child_stat = os.lstat(child)
        except FileNotFoundError:
            print(f"Warning: skipped missing path during backup: {child}")
            ignored.append(name)
            continue
        except OSError as err:
            print(f"Warning: skipped unreadable path during backup: {child} ({err})")
            ignored.append(name)
            continue

        mode = child_stat.st_mode
        if stat.S_ISSOCK(mode):
            print(f"Warning: skipped socket during backup: {child}")
            ignored.append(name)
            continue
        if stat.S_ISFIFO(mode) or stat.S_ISCHR(mode) or stat.S_ISBLK(mode):
            print(f"Warning: skipped unsupported special file during backup: {child}")
            ignored.append(name)
            continue
        if stat.S_ISLNK(mode) and not child.exists():
            print(f"Warning: skipped broken symlink during backup: {child}")
            ignored.append(name)

    return ignored


def copy_entry(src: Path, dest: Path, is_dir: bool) -> None:
    """Copy local config to repo with placeholder normalization."""
    if is_dir:
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(
            src,
            dest,
            ignore=ignore_unsupported_entries,
            ignore_dangling_symlinks=True,
        )
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


def choose_entries(entries: List[ManifestEntry]) -> List[ManifestEntry]:
    """Prompt user to select which configs to back up."""
    print(f"Select which software configs to back up into {DOTFILES_DIR}:")
    print("Confirm each numbered software entry individually.")
    chosen = []
    for index, entry in enumerate(entries, start=1):
        local_path = Path.home() / path_from_rel(entry["home_rel"])
        repo_path = DOTFILES_DIR / path_from_rel(entry["repo_rel"])
        repo_exists = repo_path.exists() or repo_path.is_symlink()
        print(f"{index}. {entry['software']}")
        print(f"   local: {local_path}")
        print(f"   repo:  {repo_path}")
        print(f"   repo backup exists: {'yes' if repo_exists else 'no'}")
        print("   selection: confirm this software individually")
        if prompt_yes_no("   Back up this software config?"):
            chosen.append(entry)

    print()
    if chosen:
        print("Selected software:")
        for index, entry in enumerate(chosen, start=1):
            print(f"  {index}. {entry['software']}")
    else:
        print("Selected software: none")
    return chosen


def matches_only_filter(entry: ManifestEntry, only_filters: List[str]) -> bool:
    """Return True when an entry matches any explicit filter."""
    software = entry["software"].lower()
    home_rel = entry["home_rel"].lower()
    repo_rel = entry["repo_rel"].lower()
    for raw_filter in only_filters:
        value = raw_filter.strip().lower()
        if not value:
            continue
        if value in {software, home_rel, repo_rel}:
            return True
    return False


def filter_entries(
    entries: List[ManifestEntry],
    only_filters: Optional[str],
) -> List[ManifestEntry]:
    """Restrict entries to an explicit subset when requested."""
    if not only_filters:
        return entries

    requested = [item.strip() for item in only_filters.split(",") if item.strip()]
    chosen = [entry for entry in entries if matches_only_filter(entry, requested)]
    if not chosen:
        raise ValueError(
            "No manifest entries matched --only. "
            "Use software names, home_rel, or repo_rel values."
        )
    return chosen


def main() -> None:
    global AUTO_YES
    parser = argparse.ArgumentParser(description="Backup configs to dotfiles repo")
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip all interactive confirmations (non-interactive mode)",
    )
    parser.add_argument(
        "--only",
        type=str,
        help="Limit backup to selected manifest entries by software, home_rel, or repo_rel",
    )
    parser.add_argument(
        "--repo-dir",
        type=str,
        help="Target synconf repo to back up into (default: ~/.synconf when it exists)",
    )
    args = parser.parse_args()
    AUTO_YES = args.yes
    configure_repo_paths(resolve_repo_dir(args.repo_dir))

    manifest = load_manifest()
    ensure_repo_scaffold(
        DOTFILES_DIR,
        tracked_paths_from_manifest(manifest.get("files", [])),
    )
    try:
        available_entries = filter_entries(manifest.get("files", []), args.only)
    except ValueError as err:
        parser.error(str(err))

    print("Backing up current configs to dotfiles repo...")
    print(f"Repository: {DOTFILES_DIR}")
    print()
    detect_environment(manifest)
    selected_entries = choose_entries(available_entries)
    if not selected_entries:
        print("No configs selected. Nothing to back up.")
        return
    conflicts = collect_conflicts(selected_entries)
    print_conflict_preview(conflicts, "backup writes any files")
    default_conflict_action = choose_conflict_plan(
        conflicts,
        AUTO_YES,
        "Detected conflicts before backup:",
        "local",
        "repo",
        "use the local version for every conflict",
        "leave every conflicting repo backup unchanged",
    )
    conflict_decisions = choose_conflict_decisions(
        conflicts,
        default_conflict_action,
        AUTO_YES,
        "Review per-conflict exceptions before backup writes any files.",
        "local",
        "repo",
    )

    summary: Dict[str, List[str]] = {
        "backed_up": [],
        "unchanged": [],
        "skipped": [],
        "manual": [],
        "missing": [],
    }
    operations: List[OperationRecord] = []

    for entry in selected_entries:
        src = Path.home() / path_from_rel(entry["home_rel"])
        dest = DOTFILES_DIR / path_from_rel(entry["repo_rel"])
        target_exists_before = dest.exists() or dest.is_symlink()

        if not src.exists():
            print(f"Warning: {src} not found, skipping")
            summary["missing"].append(entry["software"])
            operations.append(
                {
                    "software": entry["software"],
                    "source": str(src),
                    "target": str(dest),
                    "target_exists_before": target_exists_before,
                    "action": "skip-missing-source",
                }
            )
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)

        if target_exists_before:
            print()
            print(f"Reviewing {entry['software']}")
            print(f"- Local: {src}")
            print(f"- Repo:  {dest}")
            if entries_equal(src, dest, entry["is_dir"]):
                print(
                    "No differences detected. Repo backup already matches the local config."
                )
                summary["unchanged"].append(entry["software"])
                operations.append(
                    {
                        "software": entry["software"],
                        "source": str(src),
                        "target": str(dest),
                        "target_exists_before": target_exists_before,
                        "action": "unchanged",
                    }
                )
                continue
            differs = print_diff(src, dest, entry["is_dir"], "local", "repo")
            if differs:
                note_path = None
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
                        "backup",
                    )
                    action = choose_conflict_action("backup")
                if action == "skip":
                    print(f"Skipped {entry['software']}")
                    summary["skipped"].append(entry["software"])
                    operations.append(
                        {
                            "software": entry["software"],
                            "source": str(src),
                            "target": str(dest),
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
                            "backup",
                        )
                    append_pending_merge(
                        entry,
                        note_path,
                        "manual merge requested",
                        PENDING_MERGES_PATH,
                        DOTFILES_DIR,
                        "backup",
                    )
                    print(f"Left {entry['software']} unchanged for manual merge later")
                    summary["manual"].append(entry["software"])
                    operations.append(
                        {
                            "software": entry["software"],
                            "source": str(src),
                            "target": str(dest),
                            "target_exists_before": target_exists_before,
                            "action": "manual-merge-later",
                        }
                    )
                    continue

        copy_entry(src, dest, entry["is_dir"])

        print(f"Backed up {src} -> {entry['repo_rel']}")
        summary["backed_up"].append(entry["software"])
        operations.append(
            {
                "software": entry["software"],
                "source": str(src),
                "target": str(dest),
                "target_exists_before": target_exists_before,
                "action": "overwrite" if target_exists_before else "create",
            }
        )

    print()
    print("Backup complete!")
    print(f"- Backed up: {len(summary['backed_up'])}")
    print(f"- Unchanged: {len(summary['unchanged'])}")
    print(f"- Skipped: {len(summary['skipped'])}")
    print(f"- Manual merge later: {len(summary['manual'])}")
    print(f"- Missing locally: {len(summary['missing'])}")
    if summary["manual"]:
        print(f"Pending manual merges recorded in: {PENDING_MERGES_PATH}")
    update_manifest_entries(selected_entries)
    refreshed_manifest = load_manifest()
    ensure_repo_scaffold(
        DOTFILES_DIR,
        tracked_paths_from_manifest(refreshed_manifest.get("files", [])),
    )
    print_operation_records(operations)


if __name__ == "__main__":
    main()
