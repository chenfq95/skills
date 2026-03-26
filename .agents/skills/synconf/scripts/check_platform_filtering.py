#!/usr/bin/env python3
"""Validate restore-time platform filtering for generated synconf repos."""

import json
import platform
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from synconf_common import normalize_platform_name


REPO_ROOT = Path(__file__).resolve().parents[4]
GENERATOR_PATH = REPO_ROOT / ".agents/skills/synconf/scripts/generate_sync.py"


def run_command(
    cmd: List[str], cwd: Optional[Path] = None, input_text: str = ""
) -> str:
    """Run a command and return stdout, raising on failure."""
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError("Command failed: " + " ".join(cmd) + "\n" + message)
    return result.stdout


def make_entry(
    software: str,
    home_rel: str,
    repo_rel: str,
    platforms: Optional[List[str]] = None,
) -> Dict[str, object]:
    """Build a manifest entry for generated restore.py validation."""
    return {
        "source": str(Path.home() / Path(home_rel)),
        "software": software,
        "category": repo_rel.split("/", 1)[0],
        "repo_rel": repo_rel,
        "home_rel": home_rel,
        "is_dir": False,
        "platforms": platforms,
    }


def current_platform_entry() -> Dict[str, object]:
    """Return one definitely supported entry for the current platform."""
    current_platform = normalize_platform_name(platform.system())
    if current_platform == "windows":
        return make_entry(
            "Metadata Current Windows",
            "AppData/Roaming/Code/User/settings.json",
            "editor/AppData/Roaming/Code/User/settings.json",
            ["windows"],
        )
    if current_platform == "macos":
        return make_entry(
            "Metadata Current macOS",
            "Library/Application Support/Zed/settings.json",
            "editor/Library/Application Support/Zed/settings.json",
            ["macos"],
        )
    return make_entry(
        "Metadata Current Linux",
        ".config/ghostty/config",
        "terminal/.config/ghostty/config",
        ["linux"],
    )


def other_platform_entry() -> Dict[str, object]:
    """Return one definitely unsupported entry for the current platform."""
    current_platform = normalize_platform_name(platform.system())
    if current_platform != "windows":
        return make_entry(
            "Metadata Other Windows",
            "AppData/Local/Microsoft/Windows Terminal/settings.json",
            "terminal/AppData/Local/Microsoft/Windows Terminal/settings.json",
            ["windows"],
        )
    return make_entry(
        "Metadata Other macOS",
        "Library/Application Support/Cursor/User/settings.json",
        "editor/Library/Application Support/Cursor/User/settings.json",
        ["macos"],
    )


def fallback_entries() -> Tuple[List[Dict[str, object]], List[str], List[str]]:
    """Build old-manifest fixtures without platforms metadata."""
    entries = [
        make_entry(
            "Fallback Windows",
            "AppData/Local/Microsoft/Windows Terminal/settings.json",
            "terminal/AppData/Local/Microsoft/Windows Terminal/settings.json",
            None,
        ),
        make_entry(
            "Fallback macOS",
            "Library/Application Support/Zed/settings.json",
            "editor/Library/Application Support/Zed/settings.json",
            None,
        ),
        make_entry(
            "Fallback Linux",
            ".config/Cursor/User/settings.json",
            "editor/.config/Cursor/User/settings.json",
            None,
        ),
        make_entry(
            "Fallback Git",
            ".gitconfig",
            "git/.gitconfig",
            None,
        ),
    ]

    current_platform = normalize_platform_name(platform.system())
    supported = ["Fallback Git"]
    skipped = []
    if current_platform == "windows":
        supported.append("Fallback Windows")
        skipped.extend(["Fallback macOS", "Fallback Linux"])
    elif current_platform == "macos":
        supported.append("Fallback macOS")
        skipped.extend(["Fallback Windows", "Fallback Linux"])
    else:
        supported.append("Fallback Linux")
        skipped.extend(["Fallback Windows", "Fallback macOS"])

    return entries, supported, skipped


def write_manifest(repo_dir: Path, entries: List[Dict[str, object]]) -> None:
    """Write a manifest and create matching repo files."""
    payload = {"version": 1, "files": entries}
    (repo_dir / "manifest.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    for entry in entries:
        repo_path = repo_dir / str(entry["repo_rel"])
        repo_path.parent.mkdir(parents=True, exist_ok=True)
        repo_path.write_text(str(entry["software"]) + "\n", encoding="utf-8")


def assert_selected(output: str, software: str) -> None:
    """Assert that a software name appears in the numbered selection list."""
    marker = software + "\n   repo:"
    if marker not in output:
        raise AssertionError("Expected selection entry for: " + software)


def assert_filtered(output: str, software: str) -> None:
    """Assert that a software name appears only in the filtered section."""
    filtered_pattern = r"(?m)^- " + re.escape(software) + r" \(supported: .+\)$"
    selected_pattern = r"(?m)^\d+\. " + re.escape(software) + r"$"
    if not re.search(filtered_pattern, output):
        raise AssertionError("Expected filtered entry for: " + software)
    if re.search(selected_pattern, output):
        raise AssertionError(
            "Filtered entry still appeared in selection list: " + software
        )


def validate_case(
    repo_dir: Path,
    entries: List[Dict[str, object]],
    supported: List[str],
    skipped: List[str],
) -> None:
    """Run restore.py and validate supported vs skipped entries."""
    write_manifest(repo_dir, entries)
    restore_script = repo_dir / "scripts/restore.py"
    output = run_command(
        [sys.executable, str(restore_script)],
        cwd=repo_dir,
        input_text="n\n" * 12,
    )

    for software in supported:
        assert_selected(output, software)
    for software in skipped:
        assert_filtered(output, software)


def main() -> None:
    """Generate a temp repo and validate restore-time platform filtering."""
    with tempfile.TemporaryDirectory(prefix="synconf-platform-check-") as temp_dir:
        repo_dir = Path(temp_dir) / "repo"
        run_command([sys.executable, str(GENERATOR_PATH), "--repo-dir", str(repo_dir)])

        metadata_entries = [
            current_platform_entry(),
            other_platform_entry(),
            make_entry("Metadata Common Git", ".gitconfig", "git/.gitconfig", None),
        ]
        metadata_supported = [
            str(metadata_entries[0]["software"]),
            str(metadata_entries[2]["software"]),
        ]
        metadata_skipped = [str(metadata_entries[1]["software"])]
        validate_case(repo_dir, metadata_entries, metadata_supported, metadata_skipped)

        old_entries, old_supported, old_skipped = fallback_entries()
        validate_case(repo_dir, old_entries, old_supported, old_skipped)

    print("Platform filtering validation passed.")


if __name__ == "__main__":
    main()
