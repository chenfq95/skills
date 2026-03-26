#!/usr/bin/env python3
"""Initialize a synconf repository with static scripts and configuration.

This script sets up a new ~/.synconf repository (or reuses an existing one),
copies static sync scripts and configuration, and initializes Git.

Usage:
    python3 scripts/init_repo.py ~/.zshrc ~/.gitconfig
    python3 scripts/init_repo.py --repo-dir ~/dotfiles ~/.zshrc
"""

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from common import (
    DEFAULT_REPO_DIR,
    FileMapping,
    infer_category,
    infer_software,
    relative_to_home,
    display_home_path,
    repo_relative_path,
    detect_supported_platforms,
    setup_logging,
    ensure_repo_scaffold,
)


def write_manifest(dotfiles_dir: Path, mappings: List[FileMapping]) -> None:
    """Persist tracked config metadata for future incremental sync runs."""
    manifest_path = dotfiles_dir / "manifest.json"
    payload: Dict[str, Any] = {
        "version": 1,
        "files": [
            asdict(mapping)
            for mapping in sorted(mappings, key=lambda item: item.repo_rel)
        ],
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("Updated manifest.json")


def load_manifest(dotfiles_dir: Path) -> List[FileMapping]:
    """Load previously tracked mappings from manifest.json."""
    manifest_path = dotfiles_dir / "manifest.json"
    if not manifest_path.exists():
        return []

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    mappings: List[FileMapping] = []
    for item in payload.get("files", []):
        try:
            mappings.append(FileMapping(**item))
        except TypeError:
            continue
    return mappings


def merge_mappings(
    existing: List[FileMapping], new: List[FileMapping]
) -> List[FileMapping]:
    """Merge newly selected mappings into the tracked manifest state."""
    merged: Dict[str, FileMapping] = {mapping.repo_rel: mapping for mapping in existing}
    for mapping in new:
        merged[mapping.repo_rel] = mapping
    return [merged[key] for key in sorted(merged)]


def ensure_repo_dir(dotfiles_dir: Path) -> None:
    """Create the repository directory if needed."""
    dotfiles_dir.mkdir(parents=True, exist_ok=True)


def ensure_git_repo(dotfiles_dir: Path) -> None:
    """Initialize the repository when needed."""
    git_dir = dotfiles_dir / ".git"
    if git_dir.exists():
        print(f"Reusing existing Git repository at {dotfiles_dir}")
        return

    result = subprocess.run(
        ["git", "init", str(dotfiles_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown git error"
        raise RuntimeError(f"Failed to initialize Git repository: {message}")

    print(f"Initialized Git repository at {dotfiles_dir}")


def copy_files(dotfiles_dir: Path, files: List[str]) -> List[FileMapping]:
    """Copy files into categorized directories and return installation mappings."""
    mappings: List[FileMapping] = []

    for file_str in files:
        src = Path(file_str).expanduser().resolve()
        if not src.exists():
            print(f"Warning: {src} not found, skipping")
            continue

        category = infer_category(src)
        software = infer_software(src)
        repo_rel = repo_relative_path(src, category)
        dest = dotfiles_dir / repo_rel
        dest.parent.mkdir(parents=True, exist_ok=True)

        if src.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)

        mappings.append(
            FileMapping(
                source=str(src),
                software=software,
                category=category,
                repo_rel=repo_rel.as_posix(),
                home_rel=relative_to_home(src).as_posix(),
                is_dir=src.is_dir(),
                platforms=detect_supported_platforms(src, software),
            )
        )
        print(f"Copied {src} -> {repo_rel.as_posix()}")

    return mappings


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Initialize a synconf repository with static scripts and configuration"
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Config files to include",
    )
    parser.add_argument(
        "--repo-dir",
        default=str(DEFAULT_REPO_DIR),
        help="Target directory for the synconf repo (default: ~/.synconf)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)
    dotfiles_dir = Path(args.repo_dir).expanduser().resolve()

    ensure_repo_dir(dotfiles_dir)
    ensure_git_repo(dotfiles_dir)

    existing_mappings = load_manifest(dotfiles_dir)

    print(f"Initializing synconf repository at {dotfiles_dir}")
    print()

    print("Environment detection:")
    print(f"- Home: {Path.home()}")
    print(f"- Repo exists: {'yes' if (dotfiles_dir / '.git').exists() else 'no'}")
    print(f"- Python configured: {'yes' if sys.executable else 'no'}")
    print(f"- Python executable: {sys.executable or 'not found'}")
    print(f"- Existing tracked configs: {len(existing_mappings)}")
    print()

    # Copy files and static scripts
    new_mappings = copy_files(dotfiles_dir, args.files) if args.files else []
    mappings = merge_mappings(existing_mappings, new_mappings)
    write_manifest(dotfiles_dir, mappings)
    ensure_repo_scaffold(
        dotfiles_dir,
        sorted(display_home_path(Path(mapping.source)) for mapping in mappings),
    )

    print()
    print(f"=== Synconf repository initialized at {dotfiles_dir} ===")
    print("Config files copied and repo scaffold refreshed.")
    print()
    print("Detailed action checklist:")
    print(f"  1. Review the repository contents in {dotfiles_dir}")
    print(
        f"  2. Run 'python3 {dotfiles_dir}/scripts/scan.py' to scan local configs and append new discoveries to manifest.json without overwriting existing entries"
    )
    print(
        f"  3. Run 'python3 {dotfiles_dir}/scripts/manage.py --select' to choose which software configs should stay tracked"
    )
    print(
        f"  4. Run 'python3 {dotfiles_dir}/scripts/backup.py' to copy the selected configs into the synconf repo"
    )
    print(
        "  5. If any conflicts require manual work, review merge notes in "
        f"{dotfiles_dir / 'merge-notes' / 'pending-merges.json'}"
    )
    print(
        f"  6. Review pending changes with 'git -C {dotfiles_dir} status'"
    )
    print(
        f"  7. Commit with 'git -C {dotfiles_dir} add -A && git -C {dotfiles_dir} commit -m \"Initial synconf\"'"
    )
    print(
        f"  8. Optional: add a remote and push with 'git -C {dotfiles_dir} remote add origin <your-repo-url>' then 'git -C {dotfiles_dir} push -u origin main'"
    )


if __name__ == "__main__":
    main()
