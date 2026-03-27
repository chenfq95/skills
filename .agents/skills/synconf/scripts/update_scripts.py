#!/usr/bin/env python3
"""Update synconf scripts in an existing repository.

This script updates the runtime scripts in a synconf repository to the latest
version from the skill source. Useful when the skill has been updated and you
want to sync the improvements to your dotfiles repo.

Usage:
    python3 scripts/update_scripts.py                    # Update ~/.synconf
    python3 scripts/update_scripts.py --repo-dir ~/dotfiles
    python3 scripts/update_scripts.py --dry-run          # Preview changes
    python3 scripts/update_scripts.py --force            # Skip confirmations
"""

import argparse
import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

from common import (
    Colors,
    DEFAULT_REPO_DIR,
    RUNTIME_REPO_FILES,
    SCRIPTS_DIR,
    TEMPLATES_DIR,
    logger,
    prompt_yes_no,
    resolve_repo_dir,
    setup_logging,
)


class FileStatus(NamedTuple):
    """Status of a file comparison."""

    name: str
    source: Path
    target: Path
    source_exists: bool
    target_exists: bool
    is_modified: bool
    source_hash: Optional[str]
    target_hash: Optional[str]


def file_hash(path: Path) -> Optional[str]:
    """Calculate MD5 hash of a file.

    Args:
        path: Path to file

    Returns:
        Hex digest of MD5 hash, or None if file doesn't exist or can't be read
    """
    if not path.exists():
        return None
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()
    except (OSError, PermissionError):
        return None


def get_file_statuses(
    source_dir: Path,
    target_dir: Path,
    files: List[str],
) -> List[FileStatus]:
    """Compare files between source and target directories.

    Args:
        source_dir: Source directory (skill scripts)
        target_dir: Target directory (repo scripts)
        files: List of filenames to compare

    Returns:
        List of FileStatus for each file
    """
    statuses = []
    for name in files:
        source = source_dir / name
        target = target_dir / name
        source_exists = source.exists()
        target_exists = target.exists()
        source_h = file_hash(source) if source_exists else None
        target_h = file_hash(target) if target_exists else None

        is_modified = False
        if source_exists and target_exists:
            is_modified = source_h != target_h
        elif source_exists and not target_exists:
            is_modified = True  # New file

        statuses.append(
            FileStatus(
                name=name,
                source=source,
                target=target,
                source_exists=source_exists,
                target_exists=target_exists,
                is_modified=is_modified,
                source_hash=source_h,
                target_hash=target_h,
            )
        )
    return statuses


def print_status_table(statuses: List[FileStatus]) -> Dict[str, int]:
    """Print a table of file statuses.

    Args:
        statuses: List of file statuses

    Returns:
        Dictionary with counts: new, modified, unchanged, missing
    """
    counts = {"new": 0, "modified": 0, "unchanged": 0, "missing": 0}

    print("Script status:")
    print()
    print(f"  {'File':<20} {'Status':<12} {'Action'}")
    print(f"  {'-'*20} {'-'*12} {'-'*20}")

    for status in statuses:
        if not status.source_exists:
            label = f"{Colors.RED}missing{Colors.RESET}"
            action = "skip (source not found)"
            counts["missing"] += 1
        elif not status.target_exists:
            label = f"{Colors.GREEN}new{Colors.RESET}"
            action = "copy"
            counts["new"] += 1
        elif status.is_modified:
            label = f"{Colors.YELLOW}modified{Colors.RESET}"
            action = "update"
            counts["modified"] += 1
        else:
            label = f"{Colors.CYAN}unchanged{Colors.RESET}"
            action = "skip"
            counts["unchanged"] += 1

        print(f"  {status.name:<20} {label:<21} {action}")

    print()
    return counts


def backup_existing_scripts(
    target_dir: Path,
    statuses: List[FileStatus],
    backup_dir: Optional[Path] = None,
) -> Optional[Path]:
    """Backup existing scripts before updating.

    Args:
        target_dir: Target scripts directory
        statuses: File statuses (to know which files to backup)
        backup_dir: Optional explicit backup directory

    Returns:
        Path to backup directory, or None if no backup needed
    """
    files_to_backup = [
        s for s in statuses if s.target_exists and s.is_modified
    ]
    if not files_to_backup:
        return None

    if backup_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir = target_dir.parent / f".scripts-backup-{timestamp}"

    backup_dir.mkdir(parents=True, exist_ok=True)

    for status in files_to_backup:
        try:
            shutil.copy2(status.target, backup_dir / status.name)
        except (OSError, PermissionError) as e:
            logger.warning("Failed to backup %s: %s", status.name, e)

    return backup_dir


def copy_scripts(
    statuses: List[FileStatus],
    dry_run: bool = False,
) -> Dict[str, int]:
    """Copy updated scripts to target directory.

    Args:
        statuses: File statuses
        dry_run: If True, only print what would be done

    Returns:
        Dictionary with counts: copied, skipped, failed
    """
    counts = {"copied": 0, "skipped": 0, "failed": 0}

    for status in statuses:
        if not status.source_exists:
            counts["skipped"] += 1
            continue

        if not status.is_modified:
            counts["skipped"] += 1
            continue

        if dry_run:
            action = "Would copy" if not status.target_exists else "Would update"
            print(f"  {action}: {status.name}")
            counts["copied"] += 1
            continue

        try:
            status.target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(status.source, status.target)
            # Make Python scripts executable
            if status.target.suffix == ".py":
                try:
                    status.target.chmod(0o755)
                except OSError:
                    pass  # Windows doesn't support chmod
            action = "Copied" if not status.target_exists else "Updated"
            print(f"  {Colors.GREEN}{Colors.check()}{Colors.RESET} {action}: {status.name}")
            counts["copied"] += 1
        except (OSError, PermissionError) as e:
            print(f"  {Colors.RED}Failed{Colors.RESET}: {status.name} - {e}")
            counts["failed"] += 1

    return counts


def update_templates(
    source_templates: Path,
    target_dir: Path,
    dry_run: bool = False,
) -> int:
    """Update template files (gitignore, README).

    Args:
        source_templates: Source templates directory
        target_dir: Target repo directory
        dry_run: If True, only print what would be done

    Returns:
        Number of templates updated
    """
    templates = [
        ("gitignore", ".gitignore"),
        ("README.md", "README.md"),
    ]
    updated = 0

    for source_name, target_name in templates:
        source = source_templates / source_name
        target = target_dir / target_name

        if not source.exists():
            continue

        source_h = file_hash(source)
        target_h = file_hash(target)

        if source_h == target_h:
            continue

        if dry_run:
            if target.exists():
                print(f"  Would update: {target_name}")
            else:
                print(f"  Would copy: {target_name}")
            updated += 1
            continue

        try:
            shutil.copy2(source, target)
            if target.exists():
                print(f"  {Colors.GREEN}{Colors.check()}{Colors.RESET} Updated: {target_name}")
            else:
                print(f"  {Colors.GREEN}{Colors.check()}{Colors.RESET} Copied: {target_name}")
            updated += 1
        except (OSError, PermissionError) as e:
            print(f"  {Colors.RED}Failed{Colors.RESET}: {target_name} - {e}")

    return updated


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Update synconf scripts in an existing repository"
    )
    parser.add_argument(
        "--repo-dir",
        type=str,
        help="Target synconf repo (default: ~/.synconf)",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Show what would be updated without making changes",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Update without confirmation prompts",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backing up existing scripts",
    )
    parser.add_argument(
        "--include-templates",
        action="store_true",
        help="Also update .gitignore and README.md",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )
    args = parser.parse_args()

    setup_logging(args.verbose)

    # Resolve directories
    repo_dir = resolve_repo_dir(args.repo_dir)
    target_scripts_dir = repo_dir / "scripts"

    # Check if repo exists
    if not repo_dir.exists():
        print(f"Error: Repository not found: {repo_dir}")
        print("Run init_repo.py first to create the repository.")
        sys.exit(1)

    print("Synconf Script Updater")
    print("=" * 40)
    print()
    print(f"Source: {SCRIPTS_DIR}")
    print(f"Target: {target_scripts_dir}")
    if args.dry_run:
        print(f"{Colors.YELLOW}(dry-run mode){Colors.RESET}")
    print()

    # Get file statuses
    statuses = get_file_statuses(SCRIPTS_DIR, target_scripts_dir, RUNTIME_REPO_FILES)
    counts = print_status_table(statuses)

    # Check if there's anything to update
    updates_needed = counts["new"] + counts["modified"]
    if updates_needed == 0:
        print("All scripts are up to date.")
        return

    print(f"Updates available: {counts['new']} new, {counts['modified']} modified")
    print()

    # Confirm update
    if not args.force and not args.dry_run:
        if not prompt_yes_no("Proceed with update?"):
            print("Update cancelled.")
            return

    # Backup existing scripts
    backup_path = None
    if not args.no_backup and not args.dry_run:
        backup_path = backup_existing_scripts(target_scripts_dir, statuses)
        if backup_path:
            print(f"Backed up existing scripts to: {backup_path}")
            print()

    # Copy scripts
    print("Updating scripts:")
    copy_counts = copy_scripts(statuses, dry_run=args.dry_run)
    print()

    # Optionally update templates
    if args.include_templates:
        print("Updating templates:")
        template_count = update_templates(TEMPLATES_DIR, repo_dir, dry_run=args.dry_run)
        if template_count == 0:
            print("  All templates are up to date.")
        print()

    # Summary
    if args.dry_run:
        print(f"Dry-run complete: {copy_counts['copied']} files would be updated")
    else:
        print(f"Update complete: {copy_counts['copied']} files updated")
        if copy_counts["failed"] > 0:
            print(f"{Colors.RED}Warning: {copy_counts['failed']} files failed to update{Colors.RESET}")
        if backup_path:
            print(f"Backup saved to: {backup_path}")


if __name__ == "__main__":
    main()
