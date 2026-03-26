#!/usr/bin/env python3
"""Manage tracked software configs in manifest.json.

This script provides an interactive interface to list and select
which software configs to include in backup or restore operations.

Usage:
    python3 scripts/manage.py                      # List all tracked software
    python3 scripts/manage.py --list               # List all tracked software
    python3 scripts/manage.py --select             # Interactively select which configs to track
    python3 scripts/manage.py --select --keep 1,3  # Explicitly keep selected indices
"""

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


CONFIG_PATH = Path(__file__).parent / "config.json"
HOME = Path.home()

# Global flag for non-interactive mode
AUTO_YES = False
DOTFILES_DIR = Path(__file__).resolve().parent.parent
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
    global MANIFEST_PATH
    DOTFILES_DIR = repo_dir
    MANIFEST_PATH = repo_dir / "manifest.json"


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


def get_selection_view(
    manifest: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], bool]:
    """Return manifest entries in the same order shown by the latest scan."""
    files = manifest.get("files", [])
    scan_order = manifest.get("last_scan_order")
    if not isinstance(scan_order, list) or not scan_order:
        return files, False

    file_map = {
        str(entry.get("repo_rel")): entry
        for entry in files
        if entry.get("repo_rel")
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


def remove_repo_backup(entry: Dict[str, Any]) -> bool:
    """Remove the tracked backup file or directory for a manifest entry."""
    repo_path = DOTFILES_DIR / Path(str(entry["repo_rel"]))
    if not repo_path.exists() and not repo_path.is_symlink():
        return False

    try:
        if repo_path.is_symlink() or repo_path.is_file():
            repo_path.unlink()
        elif repo_path.is_dir():
            shutil.rmtree(repo_path)
        else:
            repo_path.unlink()
    except (OSError, PermissionError) as err:
        print(f"Warning: failed to remove backup {repo_path}: {err}")
        return False

    return True


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json."""
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def prompt_yes_no(message: str, default: bool = False) -> bool:
    """Prompt for yes/no confirmation."""
    if AUTO_YES:
        return True
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(message + " " + suffix + " ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def format_platforms(platforms: Optional[List[str]], config: Dict[str, Any]) -> str:
    """Format platform list for display."""
    if not platforms:
        return "all"

    # Use platform labels from config if available
    labels = {"macos": "macOS", "windows": "Windows", "linux": "Linux"}
    return ", ".join(labels.get(p, p) for p in platforms)


def list_software(manifest: Dict[str, Any], config: Dict[str, Any]) -> None:
    """List all tracked software in manifest."""
    files = manifest.get("files", [])
    if not files:
        print("No software tracked in manifest.json")
        print("\nRun 'python3 scripts/scan.py' to detect configs first.")
        return

    print("Tracked software in manifest.json:")
    print()
    for index, entry in enumerate(files, start=1):
        repo_path = DOTFILES_DIR / entry["repo_rel"]
        local_path = HOME / entry["home_rel"]
        repo_exists = repo_path.exists()
        local_exists = local_path.exists()
        platforms = format_platforms(entry.get("platforms"), config)

        status = []
        if local_exists:
            status.append("local:yes")
        else:
            status.append("local:no")
        if repo_exists:
            status.append("repo:yes")
        else:
            status.append("repo:no")

        print(f"{index}. {entry['software']}")
        print(f"   category: {entry['category']}")
        print(f"   local:  {local_path}")
        print(f"   repo:   {repo_path}")
        print(f"   platforms: {platforms}")
        print(f"   status: {', '.join(status)}")
        print()

    print(f"Total: {len(files)} software entries")


def select_for_backup(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Interactively select software for backup."""
    files = manifest.get("files", [])
    if not files:
        print("No software tracked in manifest.json")
        print("\nRun 'python3 scripts/scan.py' to detect configs first.")
        return []

    print("Select which software configs to back up:")
    print("Confirm each numbered software entry individually.")
    print()

    selected: List[Dict[str, Any]] = []
    for index, entry in enumerate(files, start=1):
        local_path = HOME / entry["home_rel"]
        repo_path = DOTFILES_DIR / entry["repo_rel"]
        local_exists = local_path.exists()
        repo_exists = repo_path.exists()

        print(f"{index}. {entry['software']} ({entry['category']})")
        print(f"   local:  {local_path} {'(exists)' if local_exists else '(missing)'}")
        print(f"   repo:   {repo_path} {'(exists)' if repo_exists else '(new)'}")

        if not local_exists:
            print(f"   {entry['software']} local config not found, skipping")
            print()
            continue

        if prompt_yes_no(f"   Back up {entry['software']}?"):
            selected.append(entry)
        print()

    return selected


def select_for_restore(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Interactively select software for restore."""
    files = manifest.get("files", [])
    if not files:
        print("No software tracked in manifest.json")
        return []

    print("Select which software configs to restore from repo:")
    print("Confirm each numbered software entry individually.")
    print()

    selected: List[Dict[str, Any]] = []
    for index, entry in enumerate(files, start=1):
        local_path = HOME / entry["home_rel"]
        repo_path = DOTFILES_DIR / entry["repo_rel"]
        local_exists = local_path.exists()
        repo_exists = repo_path.exists()

        print(f"{index}. {entry['software']} ({entry['category']})")
        print(f"   repo:   {repo_path} {'(exists)' if repo_exists else '(missing)'}")
        print(f"   local:  {local_path} {'(exists)' if local_exists else '(new)'}")

        if not repo_exists:
            print(f"   {entry['software']} repo backup not found, skipping")
            print()
            continue

        if prompt_yes_no(f"   Restore {entry['software']} to local?"):
            selected.append(entry)
        print()

    return selected


def parse_keep_indices(raw_value: str, total_count: int) -> List[int]:
    """Parse a comma-separated list of 1-based indices."""
    if raw_value.strip().lower() == "all":
        return list(range(1, total_count + 1))

    indices: List[int] = []
    for chunk in raw_value.split(","):
        value = chunk.strip()
        if not value:
            continue
        try:
            index = int(value)
        except ValueError as err:
            raise ValueError(f"Invalid selection index: {value}") from err
        if index < 1 or index > total_count:
            raise ValueError(f"Selection index out of range: {index}")
        if index not in indices:
            indices.append(index)

    if not indices:
        raise ValueError("No valid selection indices provided")
    return indices


def select_configs(
    manifest: Dict[str, Any],
    keep_indices: Optional[List[int]] = None,
) -> None:
    """Interactively select which configs to track after scan."""
    files, using_scan_order = get_selection_view(manifest)
    if not files:
        print("No configs found in manifest.json")
        print("\nRun 'python3 scripts/scan.py' to detect configs first.")
        return

    print("Select which configs to track for backup:")
    print("Confirm each numbered entry individually.")
    print(f"Found {len(files)} config entries in manifest.json")
    if using_scan_order:
        print("Selection order matches the most recent scan results.")
    print()

    to_keep: List[Dict[str, Any]] = []
    to_remove: List[Dict[str, Any]] = []

    keep_set = set(keep_indices or [])

    for index, entry in enumerate(files, start=1):
        local_path = HOME / entry["home_rel"]
        local_exists = local_path.exists()
        size = entry.get("size", "?")
        is_dir = entry.get("is_dir", False)
        file_count = entry.get("file_count")
        platforms = entry.get("platforms")

        # Format size info
        size_info = size
        if is_dir and file_count is not None:
            size_info += f", {file_count} files"

        # Format platform info
        platform_info = ""
        if platforms:
            platform_info = f" [{', '.join(platforms)}]"

        print(f"{index}. {entry['software']}{platform_info}")
        print(f"   category: {entry['category']}")
        print(f"   path:  {local_path}")
        print(f"   size:  {size_info}")
        print(f"   exists: {'yes' if local_exists else 'no'}")

        if not local_exists:
            print(f"   {entry['software']} config not found, keeping current manifest entry")
            to_keep.append(entry)
            print()
            continue

        if keep_indices is not None:
            should_keep = index in keep_set
            print(
                f"   selection: {'keep' if should_keep else 'remove'} "
                f"(from --keep)"
            )
        else:
            should_keep = prompt_yes_no(f"   Track {entry['software']} for backup?")

        if should_keep:
            to_keep.append(entry)
        else:
            to_remove.append(entry)
        print()

    if to_remove:
        manifest["files"] = to_keep
        save_manifest(manifest)
        removed_backups = 0
        print("Removing repo backups for untracked entries:")
        for entry in to_remove:
            removed = remove_repo_backup(entry)
            status = "removed" if removed else "not found"
            print(f"  - {entry['software']}: {entry['repo_rel']} ({status})")
            if removed:
                removed_backups += 1

        print(
            "Updated manifest.json: "
            f"kept {len(to_keep)}, removed {len(to_remove)}, "
            f"cleaned {removed_backups} repo backups"
        )
    else:
        print(f"All {len(to_keep)} entries kept in manifest.json")

    if to_keep:
        print()
        print("Selected configs for tracking:")
        for index, entry in enumerate(to_keep, start=1):
            print(f"  {index}. {entry['software']} ({entry['category']})")


# ANSI color codes
class Colors:
    """ANSI color codes for terminal output."""

    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    CYAN = "\033[0;36m"
    RED = "\033[0;31m"
    RESET = "\033[0m"


def main() -> None:
    """Main entry point."""
    global AUTO_YES
    parser = argparse.ArgumentParser(
        description="Manage tracked software configs in manifest.json"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all tracked software",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Select software for backup",
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Select software for restore",
    )
    parser.add_argument(
        "--select",
        action="store_true",
        help="Interactively select which configs to track",
    )
    parser.add_argument(
        "--keep",
        type=str,
        help="Explicit 1-based indices to keep for --select, e.g. 1,3,5 or all",
    )
    parser.add_argument(
        "--repo-dir",
        type=str,
        help="Target synconf repo to manage (default: ~/.synconf when it exists)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output selected entries to a JSON file",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip all interactive confirmations (non-interactive mode)",
    )
    args = parser.parse_args()
    AUTO_YES = args.yes
    configure_repo_paths(resolve_repo_dir(args.repo_dir))

    # Load configuration
    config = load_config()
    manifest = load_manifest()

    if args.list:
        list_software(manifest, config)
        return

    if args.select:
        keep_indices = None
        if args.keep is not None:
            try:
                keep_indices = parse_keep_indices(
                    args.keep,
                    len(get_selection_view(manifest)[0]),
                )
            except ValueError as err:
                parser.error(str(err))
        select_configs(manifest, keep_indices)
        return

    if args.backup:
        selected = select_for_backup(manifest)
    elif args.restore:
        selected = select_for_restore(manifest)
    else:
        # Default: show list
        list_software(manifest, config)
        return

    if selected:
        print(f"Selected {len(selected)} software for operation:")
        for index, entry in enumerate(selected, start=1):
            print(f"  {index}. {entry['software']}")
        print()

        if args.output:
            output_path = Path(args.output)
            output_path.write_text(
                json.dumps({"files": selected}, indent=2),
                encoding="utf-8",
            )
            print(f"Saved selection to {output_path}")
    else:
        print("No software selected")


if __name__ == "__main__":
    main()
