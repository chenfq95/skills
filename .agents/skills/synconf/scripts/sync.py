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


DOTFILES_DIR = Path(__file__).parent.parent.resolve()


def run(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    return subprocess.run(cmd, cwd=DOTFILES_DIR, capture_output=True, text=True, **kwargs)


def prompt_yes_no(message: str, default: bool = False) -> bool:
    """Prompt for yes/no confirmation."""
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(message + " " + suffix + " ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def run_backup() -> None:
    """Run the backup script."""
    backup_script = DOTFILES_DIR / "scripts" / "backup.py"
    result = run([sys.executable, str(backup_script)])
    if result.returncode != 0:
        print(f"Backup failed: {result.stderr}")
        sys.exit(1)
    print(result.stdout, end="")


def run_restore() -> None:
    """Run the restore script."""
    restore_script = DOTFILES_DIR / "scripts" / "restore.py"
    result = run([sys.executable, str(restore_script)])
    if result.returncode != 0:
        print(f"Restore failed: {result.stderr}")
        sys.exit(1)
    print(result.stdout, end="")


def commit_and_push() -> bool:
    """Commit and push changes to remote."""
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
    """Run one sync round."""
    print(f"=== Sync round {round_number} ===")
    run_backup()
    if prompt_yes_no("Run repo-to-local sync after backup?"):
        run_restore()
    commit_and_push()
    print()


def main() -> None:
    """Main entry point."""
    print("Syncing dotfiles...")
    round_number = 1
    while True:
        run_round(round_number)
        if not prompt_yes_no("Run another sync round?"):
            break
        round_number += 1


if __name__ == "__main__":
    main()
