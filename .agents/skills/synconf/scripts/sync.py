#!/usr/bin/env python3
"""Sync dotfiles across one or more interactive rounds.

This script runs backup and optional restore in repeated rounds,
then commits and pushes changes to the remote repository.
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List

from common import prompt_yes_no, resolve_repo_dir


def run(
    cmd: List[str],
    repo_dir: Path,
    capture: bool = False,
) -> subprocess.CompletedProcess:
    """Run a command in the repo directory.

    Args:
        cmd: Command and arguments
        repo_dir: Working directory
        capture: If True, capture output; if False, inherit stdio for interaction

    Returns:
        CompletedProcess result
    """
    if capture:
        return subprocess.run(
            cmd,
            cwd=repo_dir,
            capture_output=True,
            text=True,
        )
    else:
        # Inherit stdin/stdout/stderr for interactive commands
        return subprocess.run(
            cmd,
            cwd=repo_dir,
        )


def run_backup(repo_dir: Path) -> bool:
    """Run the backup script interactively.

    Returns:
        True if successful, False otherwise
    """
    backup_script = repo_dir / "scripts" / "backup.py"
    result = run([sys.executable, str(backup_script)], repo_dir, capture=False)
    return result.returncode == 0


def run_restore(repo_dir: Path) -> bool:
    """Run the restore script interactively.

    Returns:
        True if successful, False otherwise
    """
    restore_script = repo_dir / "scripts" / "restore.py"
    result = run([sys.executable, str(restore_script)], repo_dir, capture=False)
    return result.returncode == 0


def commit_and_push(repo_dir: Path) -> bool:
    """Commit and push changes to remote.

    Returns:
        True if changes were committed/pushed, False if no changes
    """
    # Stage all changes
    result = run(["git", "add", "-A"], repo_dir, capture=True)
    if result.returncode != 0:
        print(f"Git add failed: {result.stderr}")
        return False

    # Check if there are staged changes
    result = run(["git", "diff", "--cached", "--quiet"], repo_dir, capture=True)
    if result.returncode == 0:
        print("No changes to sync")
        return False

    # Commit
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    result = run(
        ["git", "commit", "-m", f"Update configs: {timestamp}"],
        repo_dir,
        capture=True,
    )
    if result.returncode != 0:
        print(f"Git commit failed: {result.stderr}")
        return False

    print(f"Committed changes: Update configs: {timestamp}")

    # Push (may fail if no remote configured, which is OK)
    result = run(["git", "push"], repo_dir, capture=True)
    if result.returncode != 0:
        if "No configured push destination" in result.stderr or "no upstream branch" in result.stderr:
            print("No remote configured. Skipping push.")
            print("To add a remote: git -C ~/.synconf remote add origin <url>")
        else:
            print(f"Git push failed: {result.stderr}")
            print("Changes committed locally but not pushed.")
        return True  # Commit succeeded even if push failed

    print("Changes pushed to remote")
    return True


def run_round(round_number: int, repo_dir: Path) -> None:
    """Run one sync round."""
    print(f"\n{'='*50}")
    print(f"Sync round {round_number}")
    print(f"{'='*50}\n")

    if not run_backup(repo_dir):
        print("\nBackup encountered issues. Continuing anyway...")

    print()
    if prompt_yes_no("Run repo-to-local sync after backup?"):
        if not run_restore(repo_dir):
            print("\nRestore encountered issues. Continuing anyway...")

    print()
    commit_and_push(repo_dir)


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Sync dotfiles with Git")
    parser.add_argument(
        "--repo-dir",
        type=str,
        help="Target synconf repo (default: ~/.synconf when it exists)",
    )
    args = parser.parse_args()

    repo_dir = resolve_repo_dir(args.repo_dir)

    print("Syncing dotfiles...")
    print(f"Repository: {repo_dir}")

    round_number = 1
    while True:
        run_round(round_number, repo_dir)
        print()
        if not prompt_yes_no("Run another sync round?"):
            break
        round_number += 1

    print("\nSync complete!")


if __name__ == "__main__":
    main()
