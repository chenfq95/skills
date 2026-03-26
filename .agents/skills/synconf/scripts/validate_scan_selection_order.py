#!/usr/bin/env python3
"""Validate that --keep indices follow the latest scan display order."""

import json
import sys
import tempfile
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import manage


def write_manifest(repo_dir: Path) -> None:
    """Write a manifest whose storage order differs from scan display order."""
    payload = {
        "version": 1,
        "last_scan_order": [
            "shell/.zshrc",
            "git/.gitconfig",
            "editor/.vimrc",
        ],
        "files": [
            {
                "software": "Git",
                "category": "git",
                "repo_rel": "git/.gitconfig",
                "home_rel": ".gitconfig",
                "is_dir": False,
            },
            {
                "software": "Vim",
                "category": "editor",
                "repo_rel": "editor/.vimrc",
                "home_rel": ".vimrc",
                "is_dir": False,
            },
            {
                "software": "Zsh",
                "category": "shell",
                "repo_rel": "shell/.zshrc",
                "home_rel": ".zshrc",
                "is_dir": False,
            },
        ],
    }
    (repo_dir / "manifest.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    """Confirm --keep indices honor the stored last scan order."""
    with tempfile.TemporaryDirectory(prefix="synconf-scan-selection-order-") as temp_dir:
        repo_dir = Path(temp_dir)
        write_manifest(repo_dir)

        manage.configure_repo_paths(repo_dir)
        manifest = manage.load_manifest()
        view, using_scan_order = manage.get_selection_view(manifest)

        if not using_scan_order:
            raise AssertionError("Expected selection view to use last_scan_order")

        ordered_repo_rels = [entry["repo_rel"] for entry in view]
        if ordered_repo_rels != [
            "shell/.zshrc",
            "git/.gitconfig",
            "editor/.vimrc",
        ]:
            raise AssertionError(
                "Unexpected selection order: " + str(ordered_repo_rels)
            )

        manage.select_configs(manifest, keep_indices=[1, 3])

        updated = json.loads((repo_dir / "manifest.json").read_text(encoding="utf-8"))
        kept = [entry["repo_rel"] for entry in updated.get("files", [])]
        if kept != ["shell/.zshrc", "editor/.vimrc"]:
            raise AssertionError("Unexpected kept entries: " + str(kept))

    print("Scan selection order validation passed.")


if __name__ == "__main__":
    main()
