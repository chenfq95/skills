#!/usr/bin/env python3
"""Interactively backup current configs into the dotfiles repo.

This script reads manifest.json to determine which configs to track,
then backs up selected software configs from the local machine to the repo.
"""

import argparse
import os
import shutil
import stat
from pathlib import Path
from typing import Dict, List, Optional

from common import (
    EDITOR_EXCLUDE_DIRS,
    HOME,
    ManifestEntry,
    OperationRecord,
    append_pending_merge,
    choose_conflict_action,
    choose_conflict_decisions,
    choose_conflict_plan,
    collect_backup_conflicts,
    detect_environment,
    entry_home_rel,
    entry_is_dir,
    entry_repo_rel,
    entry_software,
    entries_equal,
    ensure_repo_scaffold,
    load_manifest,
    load_state,
    manifest_entry_identity,
    normalize_text,
    path_from_rel,
    print_conflict_preview,
    print_diff,
    print_operation_records,
    prompt_merge_instructions,
    prompt_yes_no,
    read_text_file,
    resolve_conflict_action,
    resolve_repo_dir,
    save_manifest,
)


def update_manifest_entries(
    entries: List[ManifestEntry],
    manifest_path: Path,
) -> None:
    """Merge backed-up entries into manifest."""
    payload = load_manifest(manifest_path)
    file_map = {
        manifest_entry_identity(item): item for item in payload.get("files", [])
    }
    for entry in entries:
        file_map[manifest_entry_identity(entry)] = entry
    payload["files"] = [file_map[key] for key in sorted(file_map)]
    save_manifest(payload, manifest_path)


def ignore_unsupported_entries(root: str, names: List[str]) -> List[str]:
    """Skip sockets, broken symlinks, transient entries, and editor cache dirs."""
    ignored = []
    root_path = Path(root)

    for name in names:
        # Skip editor cache/history directories
        if name in EDITOR_EXCLUDE_DIRS:
            ignored.append(name)
            continue
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


def choose_entries(
    entries: List[ManifestEntry],
    repo_dir: Path,
    auto_yes: bool,
) -> List[ManifestEntry]:
    """Prompt user to select which configs to back up."""
    print(f"Select which software configs to back up into {repo_dir}:")
    print("Confirm each numbered software entry individually.")
    chosen = []

    for index, entry in enumerate(entries, start=1):
        local_path = HOME / path_from_rel(entry_home_rel(entry))
        repo_path = repo_dir / path_from_rel(entry_repo_rel(entry))
        repo_exists = repo_path.exists() or repo_path.is_symlink()
        print(f"{index}. {entry_software(entry)}")
        print(f"   local: {local_path}")
        print(f"   repo:  {repo_path}")
        print(f"   repo backup exists: {'yes' if repo_exists else 'no'}")
        print("   selection: confirm this software individually")
        if prompt_yes_no("   Back up this software config?", auto_yes=auto_yes):
            chosen.append(entry)

    print()
    if chosen:
        print("Selected software:")
        for index, entry in enumerate(chosen, start=1):
            print(f"  {index}. {entry_software(entry)}")
    else:
        print("Selected software: none")
    return chosen


def matches_only_filter(entry: ManifestEntry, only_filters: List[str]) -> bool:
    """Return True when an entry matches any explicit filter."""
    software = entry_software(entry).lower()
    home_rel = entry_home_rel(entry).lower()
    repo_rel = entry_repo_rel(entry).lower()

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
    last_selected_repo_rels: Optional[List[str]] = None,
) -> List[ManifestEntry]:
    """Restrict entries to an explicit subset when requested."""
    if last_selected_repo_rels:
        selected_set = set(last_selected_repo_rels)
        entries = [
            entry for entry in entries if entry.get("repo_rel", "") in selected_set
        ]
        if not entries:
            raise ValueError(
                "No manifest entries matched the last init selection. "
                "Run manage.py init again or use --only."
            )

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
    parser.add_argument(
        "--last-selection",
        action="store_true",
        help="Limit backup to entries selected by the latest manage.py init run",
    )
    args = parser.parse_args()
    auto_yes = args.yes
    repo_dir = resolve_repo_dir(args.repo_dir)
    manifest_path = repo_dir / "manifest.json"
    merge_notes_dir = repo_dir / "merge-notes"
    pending_merges_path = merge_notes_dir / "pending-merges.json"

    manifest = load_manifest(manifest_path)
    ensure_repo_scaffold(repo_dir)

    last_selected_repo_rels = None
    if args.last_selection:
        state = load_state(repo_dir)
        last_selected_repo_rels = state.get("last_selected_repo_rels", [])
        if not last_selected_repo_rels:
            parser.error(
                "No last selection recorded. Run manage.py init first or use --only."
            )

    try:
        available_entries = filter_entries(
            manifest.get("files", []),
            args.only,
            last_selected_repo_rels=last_selected_repo_rels,
        )
    except ValueError as err:
        parser.error(str(err))

    print("Backing up current configs to dotfiles repo...")
    print(f"Repository: {repo_dir}")
    print()
    detect_environment(repo_dir, manifest)

    selected_entries = choose_entries(available_entries, repo_dir, auto_yes)
    if not selected_entries:
        print("No configs selected. Nothing to back up.")
        return

    conflicts = collect_backup_conflicts(selected_entries, repo_dir)
    print_conflict_preview(conflicts, "backup writes any files")

    default_conflict_action = choose_conflict_plan(
        conflicts,
        auto_yes,
        "Detected conflicts before backup:",
        "local",
        "repo",
        "use the local version for every conflict",
        "leave every conflicting repo backup unchanged",
    )
    conflict_decisions = choose_conflict_decisions(
        conflicts,
        default_conflict_action,
        auto_yes,
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
        software = entry_software(entry)
        src = HOME / path_from_rel(entry_home_rel(entry))
        dest = repo_dir / path_from_rel(entry_repo_rel(entry))
        is_dir = entry_is_dir(entry)
        target_exists_before = dest.exists() or dest.is_symlink()

        if not src.exists():
            print(f"Warning: {src} not found, skipping")
            summary["missing"].append(software)
            operations.append(
                {
                    "software": software,
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
            print(f"Reviewing {software}")
            print(f"- Local: {src}")
            print(f"- Repo:  {dest}")

            if entries_equal(src, dest, is_dir):
                print(
                    "No differences detected. Repo backup already matches the local config."
                )
                summary["unchanged"].append(software)
                operations.append(
                    {
                        "software": software,
                        "source": str(src),
                        "target": str(dest),
                        "target_exists_before": target_exists_before,
                        "action": "unchanged",
                    }
                )
                continue

            differs = print_diff(src, dest, is_dir, "local", "repo")
            if differs:
                note_path = None
                action = resolve_conflict_action(
                    entry, default_conflict_action, conflict_decisions
                )

                if default_conflict_action == "review":
                    note_path = prompt_merge_instructions(
                        entry, auto_yes, merge_notes_dir, repo_dir, "backup"
                    )
                    action = choose_conflict_action(auto_yes, "backup")

                if action == "skip":
                    print(f"Skipped {software}")
                    summary["skipped"].append(software)
                    operations.append(
                        {
                            "software": software,
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
                            entry, auto_yes, merge_notes_dir, repo_dir, "backup"
                        )
                    append_pending_merge(
                        entry,
                        note_path,
                        "manual merge requested",
                        pending_merges_path,
                        repo_dir,
                        "backup",
                    )
                    print(f"Left {software} unchanged for manual merge later")
                    summary["manual"].append(software)
                    operations.append(
                        {
                            "software": software,
                            "source": str(src),
                            "target": str(dest),
                            "target_exists_before": target_exists_before,
                            "action": "manual-merge-later",
                        }
                    )
                    continue

        copy_entry(src, dest, is_dir)
        print(f"Backed up {src} -> {entry_repo_rel(entry)}")
        summary["backed_up"].append(software)
        operations.append(
            {
                "software": software,
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
        print(f"Pending manual merges recorded in: {pending_merges_path}")

    update_manifest_entries(selected_entries, manifest_path)
    ensure_repo_scaffold(repo_dir)
    print_operation_records(operations)


if __name__ == "__main__":
    main()
