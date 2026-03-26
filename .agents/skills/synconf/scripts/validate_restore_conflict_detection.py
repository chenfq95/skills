#!/usr/bin/env python3
"""Validate that restore conflict detection runs before write decisions."""

import sys
import tempfile
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import restore


def write_file(path: Path, content: str) -> None:
    """Write a UTF-8 text file fixture."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    """Confirm restore conflict detection reports only entries that differ."""
    with tempfile.TemporaryDirectory(prefix="synconf-restore-conflicts-") as temp_dir:
        root = Path(temp_dir)
        home_dir = root / "home"
        repo_dir = root / "repo"

        write_file(repo_dir / "shell/.zshrc", "export PATH=/repo/bin\n")
        write_file(home_dir / ".zshrc", "export PATH=/local/bin\n")

        write_file(repo_dir / "git/.gitconfig", "[user]\nname = same\n")
        write_file(home_dir / ".gitconfig", "[user]\nname = same\n")

        write_file(repo_dir / "editor/.vimrc", "set number\n")

        entries = [
            {
                "software": "Zsh",
                "home_rel": ".zshrc",
                "repo_rel": "shell/.zshrc",
                "is_dir": False,
            },
            {
                "software": "Git",
                "home_rel": ".gitconfig",
                "repo_rel": "git/.gitconfig",
                "is_dir": False,
            },
            {
                "software": "Vim",
                "home_rel": ".vimrc",
                "repo_rel": "editor/.vimrc",
                "is_dir": False,
            },
        ]

        conflicts = restore.collect_conflicts(
            entries,
            home_dir=home_dir,
            repo_dir=repo_dir,
        )

        if len(conflicts) != 1:
            raise AssertionError("Expected one conflict, got: " + str(conflicts))

        conflict = conflicts[0]
        if conflict["entry"]["software"] != "Zsh":
            raise AssertionError("Expected Zsh conflict, got: " + str(conflict))

        decisions = {
            "shell/.zshrc": {
                "action": "manual",
                "override": True,
            }
        }
        resolved = restore.resolve_conflict_action(entries[0], "skip", decisions)
        if resolved != "manual":
            raise AssertionError("Expected override action, got: " + resolved)

        fallback = restore.resolve_conflict_action(entries[1], "skip", decisions)
        if fallback != "skip":
            raise AssertionError("Expected default action, got: " + fallback)

    print("Restore conflict detection validation passed.")


if __name__ == "__main__":
    main()
