#!/usr/bin/env python3
"""Validate that untracking entries also removes their repo backups."""

import json
import sys
import tempfile
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import manage


def write_manifest(repo_dir: Path) -> None:
    """Write a manifest with one kept file and two removable backups."""
    payload = {
        "version": 1,
        "files": [
            {
                "software": "Keep Git",
                "category": "git",
                "repo_rel": "git/.gitconfig",
                "home_rel": ".gitconfig",
                "is_dir": False,
            },
            {
                "software": "Remove Zsh",
                "category": "shell",
                "repo_rel": "shell/.zshrc",
                "home_rel": ".zshrc",
                "is_dir": False,
            },
            {
                "software": "Remove Zed",
                "category": "editor",
                "repo_rel": "editor/.config/zed",
                "home_rel": ".config/zed",
                "is_dir": True,
            },
        ],
    }
    (repo_dir / "manifest.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def write_repo_backups(repo_dir: Path) -> None:
    """Create repo backup fixtures for managed entries."""
    git_backup = repo_dir / "git/.gitconfig"
    git_backup.parent.mkdir(parents=True, exist_ok=True)
    git_backup.write_text("git config\n", encoding="utf-8")

    zsh_backup = repo_dir / "shell/.zshrc"
    zsh_backup.parent.mkdir(parents=True, exist_ok=True)
    zsh_backup.write_text("zsh config\n", encoding="utf-8")

    zed_backup = repo_dir / "editor/.config/zed"
    zed_backup.mkdir(parents=True, exist_ok=True)
    (zed_backup / "settings.json").write_text("{\"theme\": \"one\"}\n", encoding="utf-8")


def main() -> None:
    """Confirm manifest removal also deletes the corresponding repo backups."""
    with tempfile.TemporaryDirectory(prefix="synconf-manage-cleanup-") as temp_dir:
        repo_dir = Path(temp_dir)
        write_manifest(repo_dir)
        write_repo_backups(repo_dir)

        manage.configure_repo_paths(repo_dir)
        manifest = manage.load_manifest()
        manage.select_configs(manifest, keep_indices=[1])

        updated = json.loads((repo_dir / "manifest.json").read_text(encoding="utf-8"))
        files = updated.get("files", [])
        if len(files) != 1 or files[0].get("software") != "Keep Git":
            raise AssertionError("Unexpected manifest after cleanup: " + str(files))

        if not (repo_dir / "git/.gitconfig").exists():
            raise AssertionError("Kept backup was removed unexpectedly")
        if (repo_dir / "shell/.zshrc").exists():
            raise AssertionError("Removed file backup still exists")
        if (repo_dir / "editor/.config/zed").exists():
            raise AssertionError("Removed directory backup still exists")

    print("Manage removal cleanup validation passed.")


if __name__ == "__main__":
    main()
