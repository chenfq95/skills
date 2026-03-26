#!/usr/bin/env python3
"""Validate that existing repos get missing scaffold files refreshed."""

import shutil
import sys
import tempfile
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import common


def assert_exists(path: Path) -> None:
    """Raise an error when the expected path is missing."""
    if not path.exists():
        raise AssertionError(f"Expected scaffold path to exist: {path}")


def main() -> None:
    """Confirm scaffold refresh restores missing repo files."""
    with tempfile.TemporaryDirectory(prefix="synconf-scaffold-refresh-") as temp_dir:
        repo_dir = Path(temp_dir)
        (repo_dir / "manifest.json").write_text(
            '{"version": 1, "files": []}\n',
            encoding="utf-8",
        )
        (repo_dir / ".git").mkdir()

        common.ensure_repo_scaffold(repo_dir, ["~/.zshrc"])

        shutil.rmtree(repo_dir / "scripts")
        (repo_dir / "README.md").unlink()
        (repo_dir / "install.py").unlink()

        common.ensure_repo_scaffold(repo_dir, ["~/.zshrc"])

        assert_exists(repo_dir / "README.md")
        assert_exists(repo_dir / "install.py")
        assert_exists(repo_dir / "scripts")
        assert_exists(repo_dir / "scripts" / "backup.py")
        assert_exists(repo_dir / "scripts" / "common.py")
        assert_exists(repo_dir / "scripts" / "init_repo.py")
        assert_exists(repo_dir / "scripts" / "manage.py")
        assert_exists(repo_dir / "scripts" / "restore.py")
        assert_exists(repo_dir / "scripts" / "scan.py")
        assert_exists(repo_dir / "scripts" / "sync.py")
        assert_exists(repo_dir / "scripts" / "config.json")

    print("Repo scaffold refresh validation passed.")


if __name__ == "__main__":
    main()
