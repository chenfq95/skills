#!/usr/bin/env python3
"""Manage tracked software configs in manifest.json.

Usage:
    python3 scripts/manage.py list                 # List all tracked software
    python3 scripts/manage.py init --config '{"files":[...]}' --mode merge  # Merge selected JSON entries
    python3 scripts/manage.py init --dry-run      # Preview scan without changes
    python3 scripts/manage.py init --mode overwrite  # Replace existing manifest
    python3 scripts/manage.py init --config '{"files":[...]}'  # From JSON string
    python3 scripts/manage.py select               # Review tracked configs and remove unwanted ones
    python3 scripts/manage.py prune 2,4            # Remove entries 2 and 4
"""

import argparse
import json
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from common import (
    HOME,
    ManifestEntry,
    ManifestPayload,
    StatePayload,
    detect_supported_platforms_from_entry,
    format_platform_name,
    get_current_platform,
    get_file_lock,
    get_platform_rules,
    load_manifest,
    load_state,
    logger,
    manifest_entry_identity,
    prompt_yes_no,
    resolve_repo_dir,
    run_scan,
    safe_remove_tree,
    save_manifest,
    save_state,
)


def filter_entries_for_current_platform(
    entries: List[ManifestEntry],
) -> Tuple[List[ManifestEntry], List[ManifestEntry]]:
    """Filter entries to those supported by the current platform.

    Returns:
        Tuple of (supported_entries, skipped_entries)
    """
    current_platform = get_current_platform()
    platform_rules = get_platform_rules()
    supported = []
    skipped = []

    for entry in entries:
        platforms = detect_supported_platforms_from_entry(entry, platform_rules)
        if platforms and current_platform not in platforms:
            skipped.append(entry)
        else:
            supported.append(entry)

    return supported, skipped


def report_platform_skipped(skipped: List[ManifestEntry]) -> None:
    """Print list of entries skipped due to platform mismatch."""
    if not skipped:
        return
    platform_rules = get_platform_rules()
    print("Skipping configs that do not support this platform:")
    for entry in skipped:
        platforms = detect_supported_platforms_from_entry(entry, platform_rules) or []
        platform_label = ", ".join(format_platform_name(p) for p in platforms)
        print(f"  - {entry.get('software', 'Unknown')} (supported: {platform_label})")
    print()


def get_selection_view(
    manifest: ManifestPayload, state: StatePayload
) -> Tuple[List[ManifestEntry], bool]:
    """Return manifest entries in the same order shown by the latest scan."""
    files = manifest.get("files", [])
    scan_order = state.get("last_scan_order")
    if not isinstance(scan_order, list) or not scan_order:
        return files, False

    file_map = {
        str(entry.get("repo_rel")): entry for entry in files if entry.get("repo_rel")
    }
    ordered = []
    seen = set()

    for repo_rel in scan_order:
        if repo_rel not in file_map:
            continue
        ordered.append(file_map[repo_rel])
        seen.add(repo_rel)

    for entry in files:
        repo_rel = str(entry.get("repo_rel"))
        if repo_rel in seen:
            continue
        ordered.append(entry)

    return ordered, True


def remove_repo_backup(entry: ManifestEntry, repo_dir: Path) -> bool:
    """Remove the tracked backup file or directory for a manifest entry.

    Args:
        entry: Manifest entry to remove
        repo_dir: Repository directory

    Returns:
        True if removed, False if not found or failed
    """
    repo_path = repo_dir / Path(str(entry.get("repo_rel", "")))
    if not repo_path.exists() and not repo_path.is_symlink():
        return False

    return safe_remove_tree(repo_path, follow_symlinks=False)


def remove_empty_repo_parent_dirs(entry: ManifestEntry, repo_dir: Path) -> int:
    """Remove empty parent directories left behind by a backup removal."""
    repo_path = repo_dir / Path(str(entry.get("repo_rel", "")))
    current = repo_path.parent
    removed_count = 0

    while current.exists() and current != repo_dir and current.parent != repo_dir:
        try:
            next(current.iterdir())
            break
        except StopIteration:
            try:
                current.rmdir()
            except (OSError, PermissionError) as err:
                print(f"Warning: failed to remove empty directory {current}: {err}")
                break
            removed_count += 1
            current = current.parent

    return removed_count


def cleanup_software_directory(
    entry: ManifestEntry,
    repo_dir: Path,
    kept_entries: List[ManifestEntry],
) -> bool:
    """Remove the software-specific repo directory when no kept entries remain in it.

    Args:
        entry: Entry being removed
        repo_dir: Repository directory
        kept_entries: Entries that will remain after removal

    Returns:
        True if directory was removed, False otherwise
    """
    repo_rel = Path(str(entry.get("repo_rel", "")))
    if not repo_rel.parts:
        return False

    if entry.get("is_dir"):
        target_rel = repo_rel
    else:
        if len(repo_rel.parts) <= 2:
            return False
        target_rel = repo_rel.parent

    target_path = repo_dir / target_rel
    if not target_path.exists() or not target_path.is_dir():
        return False

    target_rel_posix = target_rel.as_posix()
    target_prefix = target_rel_posix + "/"
    for kept_entry in kept_entries:
        kept_repo_rel = str(kept_entry.get("repo_rel", ""))
        if kept_repo_rel == target_rel_posix or kept_repo_rel.startswith(target_prefix):
            return False

    return safe_remove_tree(target_path, follow_symlinks=False)


def format_platforms(platforms: Optional[List[str]]) -> str:
    """Format platform list for display."""
    if not platforms:
        return "all"
    return ", ".join(format_platform_name(p) for p in platforms)


def list_software(
    manifest: ManifestPayload,
    repo_dir: Path,
) -> None:
    """List all tracked software in manifest."""
    files = manifest.get("files", [])
    if not files:
        print("No software tracked in manifest.json")
        print("\nRun 'python3 scripts/manage.py init' to scan configs first.")
        return

    # Filter to current platform
    supported, skipped = filter_entries_for_current_platform(files)
    report_platform_skipped(skipped)

    if not supported:
        print("No software tracked for this platform in manifest.json")
        return

    print("Tracked software in manifest.json:")
    print()

    for index, entry in enumerate(supported, start=1):
        repo_path = repo_dir / str(entry.get("repo_rel", ""))
        local_path = HOME / str(entry.get("home_rel", ""))
        repo_exists = repo_path.exists()
        local_exists = local_path.exists()
        platforms = format_platforms(entry.get("platforms"))

        status = []
        status.append("local:yes" if local_exists else "local:no")
        status.append("repo:yes" if repo_exists else "repo:no")

        print(f"{index}. {entry.get('software', 'Unknown')}")
        print(f"   category: {entry.get('category', 'other')}")
        print(f"   local:  {local_path}")
        print(f"   repo:   {repo_path}")
        print(f"   platforms: {platforms}")
        print(f"   status: {', '.join(status)}")
        print()

    print(f"Total: {len(supported)} software entries for this platform")


def parse_remove_indices(raw_value: str, total_count: int) -> List[int]:
    """Parse indices to remove, supporting ranges like 1-3,5.

    Args:
        raw_value: User input string with indices/ranges
        total_count: Total number of items (for bounds checking)

    Returns:
        List of valid 1-based indices

    Raises:
        ValueError: If input is invalid or out of bounds
    """
    if total_count <= 0:
        raise ValueError("No items available to select")

    indices: List[int] = []
    for chunk in raw_value.split(","):
        value = chunk.strip()
        if not value:
            continue
        if "-" in value:
            parts = value.split("-", 1)
            left_part = parts[0].strip()
            right_part = parts[1].strip()

            # Handle negative numbers (not valid indices)
            if not left_part or not right_part:
                raise ValueError(f"Invalid range format: {value}")

            try:
                start = int(left_part)
                end = int(right_part)
            except ValueError as err:
                raise ValueError(f"Invalid range (non-integer): {value}") from err

            # Check bounds
            if start < 1:
                raise ValueError(f"Range start must be >= 1: {value}")
            if end > total_count:
                raise ValueError(f"Range end {end} exceeds total count {total_count}")
            if start > end:
                raise ValueError(f"Range start > end: {value} (did you mean {end}-{start}?)")

            for i in range(start, end + 1):
                if i not in indices:
                    indices.append(i)
        else:
            try:
                index = int(value)
            except ValueError as err:
                raise ValueError(f"Invalid index (non-integer): {value}") from err
            if index < 1:
                raise ValueError(f"Index must be >= 1: {index}")
            if index > total_count:
                raise ValueError(f"Index {index} out of range (max: {total_count})")
            if index not in indices:
                indices.append(index)

    if not indices:
        raise ValueError("No valid indices provided")
    return indices


def parse_selection_indices(raw_value: str, total_count: int) -> List[int]:
    """Parse indices for selection, supporting ranges like 1-3,5."""
    return parse_remove_indices(raw_value, total_count)


def resolve_init_selection(
    raw_value: Optional[str],
    total_count: int,
    auto_yes: bool,
) -> Optional[List[int]]:
    """Resolve which scanned entries should be added to the manifest."""
    if raw_value is None:
        if auto_yes:
            print(f"Auto-selecting all {total_count} entries (-y flag)")
            return list(range(1, total_count + 1))

        print(
            "Enter indices to add (e.g., 1,3,5 or 1-3,5 or 'all'), or 'none' to cancel:"
        )
        raw_value = input("> ").strip()
    else:
        print(f"Using explicit selection: {raw_value}")

    user_input = raw_value.strip().lower()
    if user_input in ("none", "n", ""):
        print("No changes made to manifest.json")
        return None

    if user_input == "all":
        return list(range(1, total_count + 1))

    try:
        return parse_selection_indices(user_input, total_count)
    except ValueError as err:
        print(f"Error: {err}")
        return None


def select_configs(
    manifest: ManifestPayload,
    state: StatePayload,
    repo_dir: Path,
    manifest_path: Path,
    auto_yes: bool = False,
) -> None:
    """Interactively select which configs to track."""
    files, using_scan_order = get_selection_view(manifest, state)
    if not files:
        print("No configs found in manifest.json")
        print("\nRun 'python3 scripts/manage.py init' to scan configs first.")
        return

    # Filter to current platform
    supported, skipped = filter_entries_for_current_platform(files)
    report_platform_skipped(skipped)

    if not supported:
        print("No configs for this platform found in manifest.json")
        return

    print("Select which configs to track:")
    print(f"Found {len(supported)} entries for this platform in manifest.json")
    if using_scan_order:
        print("Order matches the most recent scan.")
    print()

    to_keep: List[ManifestEntry] = []
    to_remove: List[ManifestEntry] = []

    for index, entry in enumerate(supported, start=1):
        local_path = HOME / str(entry.get("home_rel", ""))
        local_exists = local_path.exists()
        platforms = entry.get("platforms")
        platform_info = f" [{', '.join(platforms)}]" if platforms else ""

        print(f"{index}. {entry.get('software', 'Unknown')}{platform_info}")
        print(f"   path: {local_path}")
        print(f"   exists: {'yes' if local_exists else 'no'}")

        if not local_exists:
            print("   keeping (config not found locally)")
            to_keep.append(entry)
            print()
            continue

        if prompt_yes_no(
            f"   Keep {entry.get('software', 'Unknown')}?", auto_yes=auto_yes
        ):
            to_keep.append(entry)
        else:
            to_remove.append(entry)
        print()

    # Add back skipped platform entries to keep list (they stay in manifest)
    to_keep.extend(skipped)
    _apply_removals(manifest, repo_dir, manifest_path, to_keep, to_remove)


def prune_configs(
    manifest: ManifestPayload,
    state: StatePayload,
    repo_dir: Path,
    manifest_path: Path,
    remove_indices: List[int],
    auto_yes: bool = False,
) -> None:
    """Remove specific entries from manifest by index."""
    files, _ = get_selection_view(manifest, state)
    if not files:
        print("No configs found in manifest.json")
        return

    # Filter to current platform
    supported, skipped = filter_entries_for_current_platform(files)
    report_platform_skipped(skipped)

    if not supported:
        print("No configs for this platform found in manifest.json")
        return

    remove_set = set(remove_indices)
    to_keep: List[ManifestEntry] = []
    to_remove: List[ManifestEntry] = []

    print("Entries to remove:")
    for index, entry in enumerate(supported, start=1):
        if index in remove_set:
            print(
                f"  {index}. {entry.get('software', 'Unknown')} ({entry.get('category', 'other')})"
            )
            to_remove.append(entry)
        else:
            to_keep.append(entry)

    if not to_remove:
        print("No entries selected for removal.")
        return

    print()
    if not prompt_yes_no(
        f"Remove {len(to_remove)} entries from manifest?", auto_yes=auto_yes
    ):
        print("No changes made.")
        return

    # Add back skipped platform entries to keep list (they stay in manifest)
    to_keep.extend(skipped)
    _apply_removals(manifest, repo_dir, manifest_path, to_keep, to_remove)


def _apply_removals(
    manifest: ManifestPayload,
    repo_dir: Path,
    manifest_path: Path,
    to_keep: List[ManifestEntry],
    to_remove: List[ManifestEntry],
) -> None:
    """Apply removal changes to manifest and clean up repo backups."""
    if not to_remove:
        print(f"All {len(to_keep)} entries kept.")
        return

    manifest["files"] = to_keep
    save_manifest(manifest, manifest_path)

    removed_backups = 0
    removed_software_dirs = 0
    removed_dirs = 0
    print("Removing repo backups:")
    for entry in to_remove:
        removed = remove_repo_backup(entry, repo_dir)
        cleaned_dir = cleanup_software_directory(entry, repo_dir, to_keep)
        removed_dirs += remove_empty_repo_parent_dirs(entry, repo_dir)
        status = "removed" if removed else "not found"
        if cleaned_dir:
            status += ", software dir removed"
            removed_software_dirs += 1
        print(
            f"  - {entry.get('software', 'Unknown')}: {entry.get('repo_rel', '')} ({status})"
        )
        if removed:
            removed_backups += 1

    print(
        "Updated manifest: "
        f"kept {len(to_keep)}, removed {len(to_remove)}, "
        f"cleaned {removed_backups} backups, removed {removed_software_dirs} software directories, "
        f"removed {removed_dirs} empty directories"
    )

    if to_keep:
        print()
        print("Remaining entries:")
        for index, entry in enumerate(to_keep, start=1):
            print(
                f"  {index}. {entry.get('software', 'Unknown')} ({entry.get('category', 'other')})"
            )


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Manage tracked software configs in manifest.json"
    )
    parser.add_argument(
        "--repo-dir", type=str, help="Target synconf repo (default: ~/.synconf)"
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip interactive confirmations"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init subcommand
    init_parser = subparsers.add_parser(
        "init", help="Initialize manifest from scan or config"
    )
    init_parser.add_argument("--config", type=str, help="JSON string with entries")
    init_parser.add_argument(
        "--config-file", type=str, help="Path to JSON file with entries"
    )
    init_parser.add_argument(
        "--mode",
        choices=["merge", "overwrite"],
        default="merge",
        help="merge (default) or overwrite",
    )
    init_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show scan results without modifying manifest",
    )
    init_parser.add_argument(
        "--select", type=str, help="Explicit indices to add, e.g. 1,3,5 or all"
    )

    # select subcommand
    subparsers.add_parser("select", help="Interactively select which configs to track")

    # prune subcommand
    prune_parser = subparsers.add_parser(
        "prune", help="Remove specific entries from manifest"
    )
    prune_parser.add_argument(
        "indices", type=str, help="1-based indices to remove, e.g. 2,4 or 1-3,5"
    )

    # list subcommand
    subparsers.add_parser("list", help="List all tracked software")

    args = parser.parse_args()

    auto_yes = args.yes
    repo_dir = resolve_repo_dir(args.repo_dir)
    manifest_path = repo_dir / "manifest.json"
    manifest = load_manifest(manifest_path)
    state = load_state(repo_dir)

    if args.command == "init":
        dry_run = getattr(args, "dry_run", False)
        # Use --select all when -y is given and no explicit selection
        effective_selection = args.select
        if auto_yes and not effective_selection:
            effective_selection = "all"
        init_manifest(
            manifest,
            manifest_path,
            repo_dir,
            auto_yes,
            config_json=args.config,
            config_file=args.config_file,
            mode=args.mode,
            dry_run=dry_run,
            selection=effective_selection,
        )
        return

    if args.command == "select":
        select_configs(manifest, state, repo_dir, manifest_path, auto_yes)
        return

    if args.command == "prune":
        try:
            remove_indices = parse_remove_indices(
                args.indices,
                len(get_selection_view(manifest, state)[0]),
            )
        except ValueError as err:
            parser.error(str(err))
        prune_configs(manifest, state, repo_dir, manifest_path, remove_indices, auto_yes)
        return

    if args.command == "list":
        list_software(manifest, repo_dir)
        return

    # Default: show list
    list_software(manifest, repo_dir)


def parse_config_entries(
    config_json: Optional[str],
    config_file: Optional[str],
) -> Optional[List[ManifestEntry]]:
    """Parse entries from JSON string or file.

    Args:
        config_json: JSON string with entries
        config_file: Path to JSON file with entries

    Returns:
        List of manifest entries, or None if parsing failed
    """
    if config_json:
        try:
            data = json.loads(config_json)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("files", [])
            print(f"Error: Expected JSON object or array, got {type(data).__name__}")
            return None
        except json.JSONDecodeError as err:
            print(f"Error: Invalid JSON string: {err}")
            return None

    if config_file:
        config_path = Path(config_file)
        if not config_path.exists():
            print(f"Error: Config file not found: {config_file}")
            return None
        try:
            content = config_path.read_text(encoding="utf-8")
            if not content.strip():
                print(f"Error: Config file is empty: {config_file}")
                return None
            data = json.loads(content)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("files", [])
            print(f"Error: Expected JSON object or array, got {type(data).__name__}")
            return None
        except json.JSONDecodeError as err:
            print(f"Error: Invalid JSON in {config_file}: {err}")
            return None
        except OSError as err:
            print(f"Error: Cannot read config file {config_file}: {err}")
            return None

    return None


def init_manifest(
    manifest: ManifestPayload,
    manifest_path: Path,
    repo_dir: Path,
    auto_yes: bool,
    config_json: Optional[str] = None,
    config_file: Optional[str] = None,
    mode: str = "merge",
    dry_run: bool = False,
    selection: Optional[str] = None,
) -> None:
    """Initialize manifest from scan or provided config.

    Flow: scan → display results → user selects → write selected to manifest

    Args:
        manifest: Current manifest payload
        manifest_path: Path to manifest.json
        repo_dir: Path to synconf repo (for saving state)
        auto_yes: Skip confirmations (adds all scanned entries)
        config_json: JSON string with entries
        config_file: Path to JSON file with entries
        mode: "merge" to add to existing, "overwrite" to replace all
        dry_run: Show scan results without modifying manifest
        selection: Explicit indices to add, e.g. "1,3,5" or "all"
    """
    provided_entries = parse_config_entries(config_json, config_file)

    if provided_entries is not None:
        entries = provided_entries
        print(f"Loaded {len(entries)} entries from config")
    else:
        print("Scanning for config files...")
        entries = run_scan()
        if not entries:
            print("No config files found on this machine.")
            return

    # Always show scan results first
    existing_map = {
        manifest_entry_identity(e): e
        for e in manifest.get("files", [])
        if manifest_entry_identity(e)
    }

    new_entries: List[ManifestEntry] = []
    existing_entries: List[ManifestEntry] = []
    for entry in entries:
        identity = manifest_entry_identity(entry)
        if identity in existing_map:
            existing_entries.append(entry)
        else:
            new_entries.append(entry)

    print(f"\nFound {len(entries)} config files:")
    print(f"  Already tracked: {len(existing_entries)}")
    print(f"  New: {len(new_entries)}")
    print()

    if not new_entries:
        print("No new configs to add.")
        return

    # Display new entries with indices
    print("New configs found:\n")
    for index, entry in enumerate(new_entries, start=1):
        software = entry.get("software", "Unknown")
        category = entry.get("category", "other")
        home_rel = entry.get("home_rel", "")
        size = entry.get("size", "?")
        print(f"  {index}. {software} ({category})")
        print(f"     path: ~/{home_rel}")
        print(f"     size: {size}")
    print()

    if dry_run:
        print(f"Dry-run: {len(new_entries)} new entries shown (no changes made)")
        return

    selected_indices = resolve_init_selection(selection, len(new_entries), auto_yes)
    if selected_indices is None:
        return

    # Collect selected entries
    selected_entries = [new_entries[i - 1] for i in selected_indices]
    print(f"\nAdding {len(selected_entries)} entries to manifest...")

    # Apply changes based on mode
    if mode == "overwrite":
        manifest["files"] = sorted(
            selected_entries, key=lambda e: e.get("repo_rel", "")
        )
    else:  # merge
        for entry in selected_entries:
            identity = manifest_entry_identity(entry)
            if identity:
                existing_map[identity] = entry
        manifest["files"] = [existing_map[key] for key in sorted(existing_map)]

    save_manifest(manifest, manifest_path)

    # Save scan order and selection to state file (gitignored)
    state: StatePayload = {
        "last_scan_order": [e.get("repo_rel", "") for e in entries],
        "last_selected_repo_rels": [e.get("repo_rel", "") for e in selected_entries],
    }
    save_state(state, repo_dir)

    print(f"Updated manifest.json: {len(manifest['files'])} total entries")
    print()
    print("Added:")
    for entry in selected_entries:
        print(f"  - {entry.get('software', 'Unknown')}")
    print()
    print("Next steps:")
    print("  1. Run 'python3 scripts/backup.py' to backup selected configs")


if __name__ == "__main__":
    main()
