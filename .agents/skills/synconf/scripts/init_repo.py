#!/usr/bin/env python3
"""Initialize a synconf repository with static scripts and configuration.

This script sets up a new ~/.synconf repository (or reuses an existing one),
copies static sync scripts and configuration, and initializes Git.

Usage:
    python3 scripts/init_repo.py ~/.zshrc ~/.gitconfig
    python3 scripts/init_repo.py --repo-dir ~/dotfiles ~/.zshrc
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

from common import (
    DEFAULT_REPO_DIR,
    HOME,
    FileMapping,
    ManifestEntry,
    detect_platforms_from_path,
    ensure_gitignore,
    ensure_repo_scaffold,
    get_category_rules,
    get_platform_rules,
    get_software_rules,
    infer_category,
    infer_software,
    load_manifest,
    manifest_entry_identity,
    relative_to_home,
    repo_relative_path,
    save_manifest,
    setup_logging,
)


def file_mapping_to_manifest_entry(mapping: FileMapping) -> ManifestEntry:
    """Convert a copied file mapping into a manifest entry."""
    entry: ManifestEntry = {
        "source": mapping.source,
        "software": mapping.software,
        "category": mapping.category,
        "repo_rel": mapping.repo_rel,
        "home_rel": mapping.home_rel,
        "is_dir": mapping.is_dir,
    }
    if mapping.platforms:
        entry["platforms"] = mapping.platforms
    return entry


def write_manifest(dotfiles_dir: Path, entries: List[ManifestEntry]) -> None:
    """Persist tracked config metadata for future incremental sync runs."""
    manifest_path = dotfiles_dir / "manifest.json"
    payload = load_manifest(manifest_path)
    payload["version"] = 1
    payload["files"] = sorted(entries, key=lambda item: str(item.get("repo_rel", "")))
    save_manifest(payload, manifest_path)
    print("Updated manifest.json")


def merge_mappings(
    existing: List[ManifestEntry], new: List[FileMapping]
) -> List[ManifestEntry]:
    """Merge newly selected mappings into the tracked manifest state."""
    merged: Dict[str, ManifestEntry] = {
        manifest_entry_identity(entry): entry
        for entry in existing
        if manifest_entry_identity(entry)
    }
    for mapping in new:
        entry = file_mapping_to_manifest_entry(mapping)
        merged[manifest_entry_identity(entry)] = entry
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

    # Load rules once for efficiency
    category_rules = get_category_rules()
    software_rules = get_software_rules()
    platform_rules = get_platform_rules()

    for file_str in files:
        src = Path(file_str).expanduser().resolve()
        if not src.exists():
            print(f"Warning: {src} not found, skipping")
            continue

        category = infer_category(src, category_rules)
        software = infer_software(src, software_rules)
        is_dir = src.is_dir()
        platforms = detect_platforms_from_path(src, software, platform_rules)
        repo_rel = repo_relative_path(
            src,
            category,
            software,
            is_dir,
            platforms=platforms,
        )
        dest = dotfiles_dir / repo_rel
        dest.parent.mkdir(parents=True, exist_ok=True)

        if is_dir:
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
                is_dir=is_dir,
                platforms=platforms,
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
    ensure_gitignore(dotfiles_dir)

    manifest_path = dotfiles_dir / "manifest.json"
    existing_manifest = load_manifest(manifest_path)
    existing_entries = existing_manifest.get("files", [])

    print(f"Initializing synconf repository at {dotfiles_dir}")
    print()

    print("Environment detection:")
    print(f"- Home: {HOME}")
    print(f"- Repo exists: {'yes' if (dotfiles_dir / '.git').exists() else 'no'}")
    print(f"- Python configured: {'yes' if sys.executable else 'no'}")
    print(f"- Python executable: {sys.executable or 'not found'}")
    print(f"- Existing tracked configs: {len(existing_entries)}")
    print()

    # Copy files and static scripts
    new_mappings = copy_files(dotfiles_dir, args.files) if args.files else []
    entries = merge_mappings(existing_entries, new_mappings)
    write_manifest(dotfiles_dir, entries)
    ensure_repo_scaffold(dotfiles_dir)

    print()
    print(f"=== Synconf repository initialized at {dotfiles_dir} ===")
    print("Config files copied and repo scaffold refreshed.")
    print()
    print("Detailed action checklist:")
    print(f"  1. Review the repository contents in {dotfiles_dir}")
    print(
        f"  2. Scan configs, confirm the subset you want, then run 'python3 {dotfiles_dir}/scripts/manage.py init --config <selected-json> --mode merge'"
    )
    print(
        f"  3. Run 'python3 {dotfiles_dir}/scripts/backup.py' to copy the selected configs into the synconf repo"
    )
    print("  4. If any conflicts require manual work, review merge notes in the repo")
    print(
        "  5. If any conflicts require manual work, review merge notes in "
        f"{dotfiles_dir / 'merge-notes' / 'pending-merges.json'}"
    )
    print(f"  6. Review pending changes with 'git -C {dotfiles_dir} status'")
    print(
        f"  7. Commit with 'git -C {dotfiles_dir} add -A && git -C {dotfiles_dir} commit -m \"Initial synconf\"'"
    )
    print(
        f"  8. Optional: add a remote and push with 'git -C {dotfiles_dir} remote add origin <your-repo-url>' then 'git -C {dotfiles_dir} push -u origin main'"
    )


if __name__ == "__main__":
    main()
