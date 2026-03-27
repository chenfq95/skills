#!/usr/bin/env python3
"""Sync dotfiles across one or more interactive rounds.

This script runs backup and optional restore in repeated rounds,
then commits and pushes changes to the remote repository.
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from common import check_git_available, prompt_yes_no, resolve_repo_dir


def run(
    cmd: List[str],
    repo_dir: Path,
    capture: bool = False,
    timeout: Optional[int] = None,
) -> subprocess.CompletedProcess:
    """Run a command in the repo directory.

    Args:
        cmd: Command and arguments
        repo_dir: Working directory
        capture: If True, capture output; if False, inherit stdio for interaction
        timeout: Optional timeout in seconds

    Returns:
        CompletedProcess result
    """
    try:
        if capture:
            return subprocess.run(
                cmd,
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        else:
            # Inherit stdin/stdout/stderr for interactive commands
            return subprocess.run(
                cmd,
                cwd=repo_dir,
                timeout=timeout,
            )
    except FileNotFoundError as e:
        # Command not found
        result = subprocess.CompletedProcess(cmd, 127)
        result.stderr = f"Command not found: {e}"
        result.stdout = ""
        return result
    except subprocess.TimeoutExpired:
        result = subprocess.CompletedProcess(cmd, 124)
        result.stderr = f"Command timed out after {timeout}s"
        result.stdout = ""
        return result


def run_backup(repo_dir: Path) -> bool:
    """Run the backup script interactively.

    Args:
        repo_dir: Repository directory

    Returns:
        True if successful, False otherwise
    """
    backup_script = repo_dir / "scripts" / "backup.py"
    if not backup_script.exists():
        print(f"Error: Backup script not found: {backup_script}")
        return False
    result = run([sys.executable, str(backup_script)], repo_dir, capture=False)
    return result.returncode == 0


def run_restore(repo_dir: Path) -> bool:
    """Run the restore script interactively.

    Args:
        repo_dir: Repository directory

    Returns:
        True if successful, False otherwise
    """
    restore_script = repo_dir / "scripts" / "restore.py"
    if not restore_script.exists():
        print(f"Error: Restore script not found: {restore_script}")
        return False
    result = run([sys.executable, str(restore_script)], repo_dir, capture=False)
    return result.returncode == 0


def commit_and_push(repo_dir: Path) -> bool:
    """Commit and push changes to remote.

    Args:
        repo_dir: Repository directory

    Returns:
        True if changes were committed/pushed, False if no changes or error
    """
    # Stage all changes
    result = run(["git", "add", "-A"], repo_dir, capture=True, timeout=30)
    if result.returncode != 0:
        if result.returncode == 127:
            print("Error: git command not found. Please install git.")
            return False
        print(f"Git add failed: {result.stderr}")
        return False

    # Check if there are staged changes
    result = run(
        ["git", "diff", "--cached", "--quiet"], repo_dir, capture=True, timeout=30
    )
    if result.returncode == 0:
        print("No changes to sync")
        return False

    # Commit
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    result = run(
        ["git", "commit", "-m", f"Update configs: {timestamp}"],
        repo_dir,
        capture=True,
        timeout=60,
    )
    if result.returncode != 0:
        print(f"Git commit failed: {result.stderr}")
        return False

    print(f"Committed changes: Update configs: {timestamp}")

    # Push with timeout (may fail if no remote configured, which is OK)
    result = run(["git", "push"], repo_dir, capture=True, timeout=120)
    if result.returncode != 0:
        stderr = result.stderr or ""
        # Check for common non-fatal push issues
        if "No configured push destination" in stderr:
            print("No remote configured. Skipping push.")
            print("To add a remote: git -C ~/.synconf remote add origin <url>")
        elif "no upstream branch" in stderr:
            print("No upstream branch configured. Skipping push.")
            print("To set upstream: git -C ~/.synconf push -u origin main")
        elif "Permission denied" in stderr or "Authentication failed" in stderr:
            print("Push failed: Authentication error.")
            print("Please check your SSH keys or access token.")
            print("Changes committed locally but not pushed.")
        elif "Could not resolve host" in stderr or "unable to access" in stderr:
            print("Push failed: Network error.")
            print("Please check your internet connection.")
            print("Changes committed locally but not pushed.")
        elif result.returncode == 124:
            print("Push timed out after 120 seconds.")
            print("Changes committed locally but not pushed.")
        else:
            print(f"Git push failed: {stderr}")
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

    # Check prerequisites
    if not check_git_available():
        print("Error: git command not found. Please install git first.")
        sys.exit(1)

    if not repo_dir.exists():
        print(f"Error: Repository not found: {repo_dir}")
        print("Run init_repo.py first to create the repository.")
        sys.exit(1)

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
