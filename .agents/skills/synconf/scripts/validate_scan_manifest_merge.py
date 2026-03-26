#!/usr/bin/env python3
"""Validate that scan manifest updates preserve existing tracked entries."""

import json
import sys
import tempfile
from pathlib import Path
from typing import Dict, List


SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import scan


def existing_entry() -> Dict[str, object]:
    """Build an existing manifest entry with extra metadata to preserve."""
    return {
        "software": "Existing Zsh",
        "source": "/custom/source",
        "category": "shell",
        "repo_rel": "shell/.zshrc",
        "home_rel": ".zshrc",
        "exists": True,
        "is_dir": False,
        "size": "1KB",
        "platforms": ["macos"],
        "notes": "keep-me",
    }


def scanned_items() -> List[scan.ConfigItem]:
    """Build scanned entries with one overlap and one new item."""
    return [
        scan.ConfigItem(
            software="Scanned Zsh",
            source=str(Path.home() / ".zshrc"),
            category="shell",
            repo_rel="shell/.zshrc",
            home_rel=".zshrc",
            exists=True,
            is_dir=False,
            size="2KB",
            file_count=None,
            platforms=["macos"],
        ),
        scan.ConfigItem(
            software="New Git",
            source=str(Path.home() / ".gitconfig"),
            category="git",
            repo_rel="git/.gitconfig",
            home_rel=".gitconfig",
            exists=True,
            is_dir=False,
            size="512B",
            file_count=None,
            platforms=["macos"],
        ),
    ]


def main() -> None:
    """Write a fixture manifest and confirm scan updates are additive only."""
    with tempfile.TemporaryDirectory(prefix="synconf-scan-merge-") as temp_dir:
        repo_dir = Path(temp_dir)
        manifest_path = repo_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps({"version": 1, "files": [existing_entry()]}, indent=2),
            encoding="utf-8",
        )

        added, scan_count = scan.update_manifest(scanned_items(), manifest_path)
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = payload.get("files", [])

        if added != 1:
            raise AssertionError("Expected exactly one new entry, got: " + str(added))
        if scan_count != 2:
            raise AssertionError(
                "Expected scan order to include two entries, got: " + str(scan_count)
            )
        if len(files) != 2:
            raise AssertionError(
                "Expected two manifest entries after scan merge, got: "
                + str(len(files))
            )

        existing = next(
            item for item in files if item.get("repo_rel") == "shell/.zshrc"
        )
        new_item = next(
            item for item in files if item.get("repo_rel") == "git/.gitconfig"
        )

        if existing.get("software") != "Existing Zsh":
            raise AssertionError("Existing entry was overwritten: " + str(existing))
        if existing.get("notes") != "keep-me":
            raise AssertionError("Existing metadata was lost: " + str(existing))
        if new_item.get("software") != "New Git":
            raise AssertionError("New entry was not appended correctly: " + str(new_item))
        if payload.get("last_scan_order") != ["shell/.zshrc", "git/.gitconfig"]:
            raise AssertionError(
                "Unexpected last_scan_order: " + str(payload.get("last_scan_order"))
            )

    print("Scan manifest merge validation passed.")


if __name__ == "__main__":
    main()
