#!/usr/bin/env python3
"""Interactively sync configs from the dotfiles repo back to the local machine.

This script reads manifest.json to determine which configs to track,
then syncs selected software configs from the repo to the local machine.
"""

import argparse
import shutil
from pathlib import Path
from typing import Dict, List, Sequence

from common import (
    DiskSpaceError,
    HOME,
    ManifestEntry,
    OperationRecord,
    PathValidationError,
    append_pending_merge,
    check_disk_space,
    choose_conflict_action,
    choose_conflict_decisions,
    choose_conflict_plan,
    collect_restore_conflicts,
    detect_environment,
    detect_supported_platforms_from_entry,
    entry_home_rel,
    entry_is_dir,
    entry_repo_rel,
    entry_software,
    entries_equal,
    filter_entries_for_platform,
    format_platform_name,
    get_current_platform,
    get_directory_size,
    get_platform_rules,
    is_safe_symlink,
    is_symlink_to_directory,
    load_manifest,
    logger,
    path_from_rel,
    print_conflict_preview,
    print_diff,
    print_operation_records,
    prompt_merge_instructions,
    prompt_yes_no,
    read_text_file,
    render_text,
    resolve_conflict_action,
    resolve_repo_dir,
    safe_remove_tree,
    validate_path_within_home,
)


def report_filtered_entries(
    entries: Sequence[ManifestEntry],
    platform_rules: List[Dict[str, object]],
) -> None:
    """Print list of entries filtered out for this platform."""
    if not entries:
        return

    print("Skipping repo backups that do not support this platform:")
    for entry in entries:
        platforms = detect_supported_platforms_from_entry(entry, platform_rules) or []
        platform_label = ", ".join(format_platform_name(item) for item in platforms)
        print(f"- {entry_software(entry)} (supported: {platform_label})")
    print()


def copy_entry(src: Path, dest: Path, is_dir: bool) -> None:
    """Copy repo config to local with placeholder rendering.

    Args:
        src: Source path (repo location)
        dest: Destination path (local config)
        is_dir: Whether source is a directory

    Raises:
        DiskSpaceError: If insufficient disk space
        PermissionError: If write permission denied
        OSError: If copy fails
    """
    # Check disk space before copying
    if is_dir:
        required_size = get_directory_size(src)
    else:
        try:
            required_size = src.stat().st_size
        except OSError:
            required_size = 0

    try:
        check_disk_space(dest, required_size)
    except DiskSpaceError as e:
        logger.error("Disk space check failed: %s", e)
        raise

    if is_dir:
        # Safety check: don't blindly rmtree a symlink to a directory
        if dest.exists() or dest.is_symlink():
            if is_symlink_to_directory(dest):
                logger.warning(
                    "Destination %s is a symlink to a directory. "
                    "Removing symlink only, not the target.",
                    dest
                )
                dest.unlink()
            elif not safe_remove_tree(dest, follow_symlinks=False):
                raise OSError(f"Cannot safely remove existing destination: {dest}")

        shutil.copytree(src, dest)
        for child in dest.rglob("*"):
            if not child.is_file():
                continue
            text = read_text_file(child)
            if text is not None:
                try:
                    child.write_text(render_text(text), encoding="utf-8")
                except PermissionError as e:
                    logger.warning("Cannot write to %s: %s", child, e)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Remove existing file/symlink safely
        if dest.exists() or dest.is_symlink():
            try:
                dest.unlink()
            except PermissionError as e:
                raise PermissionError(f"Cannot remove existing file {dest}: {e}")

        text = read_text_file(src)
        if text is None:
            shutil.copy2(src, dest)
        else:
            dest.write_text(render_text(text), encoding="utf-8")


def choose_entries(
    entries: List[ManifestEntry],
    repo_dir: Path,
    auto_yes: bool,
) -> List[ManifestEntry]:
    """Prompt user to select which configs to restore."""
    print("Scan results: repo backup + local environment")
    print("Confirm each numbered software entry individually before syncing to local.")
    chosen: List[ManifestEntry] = []

    for index, entry in enumerate(entries, start=1):
        repo_path = repo_dir / path_from_rel(entry_repo_rel(entry))
        local_path = HOME / path_from_rel(entry_home_rel(entry))
        local_exists = local_path.exists() or local_path.is_symlink()
        print(f"{index}. {entry_software(entry)}")
        print(f"   repo:   {repo_path}")
        print(f"   local:  {local_path}")
        print(
            f"   repo backup exists: {'yes' if repo_path.exists() or repo_path.is_symlink() else 'no'}"
        )
        print(f"   local config exists: {'yes' if local_exists else 'no'}")
        print("   selection: confirm this software individually")
        if prompt_yes_no(
            "   Sync this software from repo to local?", auto_yes=auto_yes
        ):
            chosen.append(entry)

    print()
    if chosen:
        print("Selected software for repo-to-local sync:")
        for index, entry in enumerate(chosen, start=1):
            print(f"  {index}. {entry_software(entry)}")
    else:
        print("Selected software: none")
    return chosen


def main() -> None:
    """Main entry point."""
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
    auto_yes = args.yes
    repo_dir = resolve_repo_dir(args.repo_dir)
    manifest_path = repo_dir / "manifest.json"
    merge_notes_dir = repo_dir / "merge-notes"
    pending_merges_path = merge_notes_dir / "pending-merges.json"

    print("Syncing configs from repo to local machine...")
    print(f"Repository: {repo_dir}")
    print()

    manifest = load_manifest(manifest_path)
    detect_environment(repo_dir, manifest)

    # Load platform rules once and reuse
    platform_rules = get_platform_rules()
    current_platform = get_current_platform()

    supported_entries, filtered_entries = filter_entries_for_platform(
        manifest.get("files", []),
        current_platform,
        platform_rules,
    )
    report_filtered_entries(filtered_entries, platform_rules)

    selected_entries = choose_entries(supported_entries, repo_dir, auto_yes)
    if not selected_entries:
        if not supported_entries:
            print("No compatible repo backups are available for this platform.")
        else:
            print("No configs selected. Nothing to sync.")
        return

    conflicts = collect_restore_conflicts(selected_entries, repo_dir)
    print_conflict_preview(conflicts, "restore writes any files")

    default_conflict_action = choose_conflict_plan(
        conflicts,
        auto_yes,
        "Detected conflicts before repo-to-local sync:",
        "repo",
        "local",
        "use the repo version for every conflict",
        "leave every conflicting local config unchanged",
    )
    conflict_decisions = choose_conflict_decisions(
        conflicts,
        default_conflict_action,
        auto_yes,
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
        software = entry_software(entry)
        home_rel = entry_home_rel(entry)
        repo_rel = entry_repo_rel(entry)

        # Validate that local path doesn't escape HOME
        try:
            validate_path_within_home(path_from_rel(home_rel))
        except PathValidationError as e:
            print(f"Warning: {software} - {e}")
            operations.append(
                {
                    "software": software,
                    "source": str(repo_dir / path_from_rel(repo_rel)),
                    "target": str(HOME / path_from_rel(home_rel)),
                    "target_exists_before": False,
                    "action": "skip-invalid-path",
                }
            )
            continue

        repo_path = repo_dir / path_from_rel(repo_rel)
        local_path = HOME / path_from_rel(home_rel)
        is_dir = entry_is_dir(entry)
        target_exists_before = local_path.exists() or local_path.is_symlink()

        # Check for broken symlinks in source
        if repo_path.is_symlink() and not is_safe_symlink(repo_path):
            print(f"Warning: {repo_path} is a broken or circular symlink, skipping")
            summary["missing_in_repo"].append(software)
            operations.append(
                {
                    "software": software,
                    "source": str(repo_path),
                    "target": str(local_path),
                    "target_exists_before": target_exists_before,
                    "action": "skip-broken-symlink",
                }
            )
            continue

        if not repo_path.exists():
            print(f"Warning: {repo_path} not found in repo, skipping")
            summary["missing_in_repo"].append(software)
            operations.append(
                {
                    "software": software,
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
            print(f"Reviewing {software}")
            print(f"- Repo:   {repo_path}")
            print(f"- Local:  {local_path}")

            if entries_equal(repo_path, local_path, is_dir):
                print(
                    "No differences detected. Local config already matches the repo backup."
                )
                summary["unchanged"].append(software)
                operations.append(
                    {
                        "software": software,
                        "source": str(repo_path),
                        "target": str(local_path),
                        "target_exists_before": target_exists_before,
                        "action": "unchanged",
                    }
                )
                continue

            note_path = None
            if print_diff(repo_path, local_path, is_dir, "repo", "local"):
                action = resolve_conflict_action(
                    entry, default_conflict_action, conflict_decisions
                )

                if default_conflict_action == "review":
                    note_path = prompt_merge_instructions(
                        entry, auto_yes, merge_notes_dir, repo_dir, "restore"
                    )
                    action = choose_conflict_action(auto_yes, "restore")

                if action == "skip":
                    print(f"Skipped {software}")
                    summary["skipped"].append(software)
                    operations.append(
                        {
                            "software": software,
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
                            entry, auto_yes, merge_notes_dir, repo_dir, "restore"
                        )
                    append_pending_merge(
                        entry,
                        note_path,
                        "manual repo-to-local merge requested",
                        pending_merges_path,
                        repo_dir,
                        "restore",
                    )
                    print(f"Left {software} unchanged for manual merge later")
                    summary["manual"].append(software)
                    operations.append(
                        {
                            "software": software,
                            "source": str(repo_path),
                            "target": str(local_path),
                            "target_exists_before": target_exists_before,
                            "action": "manual-merge-later",
                        }
                    )
                    continue

        try:
            copy_entry(repo_path, local_path, is_dir)
            print(f"Synced {repo_rel} -> {local_path}")
            summary["synced"].append(software)
            operations.append(
                {
                    "software": software,
                    "source": str(repo_path),
                    "target": str(local_path),
                    "target_exists_before": target_exists_before,
                    "action": "overwrite" if target_exists_before else "create",
                }
            )
        except DiskSpaceError as e:
            print(f"Error: {e}")
            print(f"Skipped {software} due to insufficient disk space")
            summary["skipped"].append(software)
            operations.append(
                {
                    "software": software,
                    "source": str(repo_path),
                    "target": str(local_path),
                    "target_exists_before": target_exists_before,
                    "action": "skip-disk-space",
                }
            )
        except PermissionError as e:
            print(f"Error: Permission denied for {software}: {e}")
            print(f"Skipped {software} due to permission error")
            summary["skipped"].append(software)
            operations.append(
                {
                    "software": software,
                    "source": str(repo_path),
                    "target": str(local_path),
                    "target_exists_before": target_exists_before,
                    "action": "skip-permission-denied",
                }
            )
        except OSError as e:
            print(f"Error copying {software}: {e}")
            summary["skipped"].append(software)
            operations.append(
                {
                    "software": software,
                    "source": str(repo_path),
                    "target": str(local_path),
                    "target_exists_before": target_exists_before,
                    "action": "skip-copy-error",
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
        print(f"Pending manual merges recorded in: {pending_merges_path}")

    print_operation_records(operations)


if __name__ == "__main__":
    main()
