#!/usr/bin/env python3
"""Consolidated tests for synconf scripts."""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import common  # noqa: E402
from manage import get_selection_view, prune_configs  # noqa: E402


def write_file(path: Path, content: str) -> None:
    """Write a UTF-8 text file fixture."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def assert_exists(path: Path) -> None:
    """Raise an error when the expected path is missing."""
    if not path.exists():
        raise AssertionError(f"Expected path to exist: {path}")


# -----------------------------------------------------------------------------
# Test: Backup conflict detection
# -----------------------------------------------------------------------------
def test_backup_conflict_detection() -> None:
    """Confirm conflict detection reports only entries that actually differ."""
    with tempfile.TemporaryDirectory(prefix="synconf-test-") as temp_dir:
        root = Path(temp_dir)
        home_dir = root / "home"
        repo_dir = root / "repo"

        write_file(home_dir / ".zshrc", "export PATH=$HOME/bin\n")
        write_file(repo_dir / "shell/zsh/.zshrc", "export PATH=/old/home/bin\n")
        write_file(home_dir / ".gitconfig", "[user]\nname = local\n")
        write_file(repo_dir / "git/git/.gitconfig", "[user]\nname = local\n")
        write_file(home_dir / ".vimrc", "set number\n")

        entries: List[common.ManifestEntry] = [
            {
                "software": "Zsh",
                "home_rel": ".zshrc",
                "repo_rel": "shell/zsh/.zshrc",
                "is_dir": False,
            },
            {
                "software": "Git",
                "home_rel": ".gitconfig",
                "repo_rel": "git/git/.gitconfig",
                "is_dir": False,
            },
            {
                "software": "Vim",
                "home_rel": ".vimrc",
                "repo_rel": "editor/vim/.vimrc",
                "is_dir": False,
            },
        ]

        conflicts = common.collect_backup_conflicts(
            entries, repo_dir=repo_dir, home_dir=home_dir
        )
        assert len(conflicts) == 1, f"Expected one conflict, got: {conflicts}"
        assert common.entry_software(conflicts[0]["entry"]) == "Zsh"

        decisions = {
            "shell/zsh/.zshrc": common.ConflictDecision(
                action="manual",
                override=True,
            )
        }
        assert common.resolve_conflict_action(entries[0], "skip", decisions) == "manual"
        assert common.resolve_conflict_action(entries[1], "skip", decisions) == "skip"

    print("  [PASS] backup_conflict_detection")


# -----------------------------------------------------------------------------
# Test: Restore conflict detection
# -----------------------------------------------------------------------------
def test_restore_conflict_detection() -> None:
    """Confirm restore conflict detection reports only entries that differ."""
    with tempfile.TemporaryDirectory(prefix="synconf-test-") as temp_dir:
        root = Path(temp_dir)
        home_dir = root / "home"
        repo_dir = root / "repo"

        write_file(repo_dir / "shell/zsh/.zshrc", "export PATH=/repo/bin\n")
        write_file(home_dir / ".zshrc", "export PATH=/local/bin\n")
        write_file(repo_dir / "git/git/.gitconfig", "[user]\nname = same\n")
        write_file(home_dir / ".gitconfig", "[user]\nname = same\n")
        write_file(repo_dir / "editor/vim/.vimrc", "set number\n")

        entries: List[common.ManifestEntry] = [
            {
                "software": "Zsh",
                "home_rel": ".zshrc",
                "repo_rel": "shell/zsh/.zshrc",
                "is_dir": False,
            },
            {
                "software": "Git",
                "home_rel": ".gitconfig",
                "repo_rel": "git/git/.gitconfig",
                "is_dir": False,
            },
            {
                "software": "Vim",
                "home_rel": ".vimrc",
                "repo_rel": "editor/vim/.vimrc",
                "is_dir": False,
            },
        ]

        conflicts = common.collect_restore_conflicts(
            entries, repo_dir=repo_dir, home_dir=home_dir
        )
        assert len(conflicts) == 1, f"Expected one conflict, got: {conflicts}"
        assert common.entry_software(conflicts[0]["entry"]) == "Zsh"

    print("  [PASS] restore_conflict_detection")


# -----------------------------------------------------------------------------
# Test: Platform filtering
# -----------------------------------------------------------------------------
def test_platform_filtering() -> None:
    """Confirm restore filters out entries for other platforms."""
    with tempfile.TemporaryDirectory(prefix="synconf-test-") as temp_dir:
        repo_dir = Path(temp_dir)
        manifest_path = repo_dir / "manifest.json"

        current = common.get_current_platform()
        other = "windows" if current != "windows" else "macos"

        payload = {
            "version": 1,
            "files": [
                {
                    "software": "Cross",
                    "category": "shell",
                    "repo_rel": "shell/cross/.cross",
                    "home_rel": ".cross",
                    "is_dir": False,
                },
                {
                    "software": "Native",
                    "category": "shell",
                    "repo_rel": "shell/native/.native",
                    "home_rel": ".native",
                    "is_dir": False,
                    "platforms": [current],
                },
                {
                    "software": "Other",
                    "category": "shell",
                    "repo_rel": "shell/other/.other",
                    "home_rel": ".other",
                    "is_dir": False,
                    "platforms": [other],
                },
            ],
        }
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        # Create repo backups
        for f in ["shell/cross/.cross", "shell/native/.native", "shell/other/.other"]:
            write_file(repo_dir / f, "content\n")

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "restore.py"),
                "-y",
                "--repo-dir",
                str(repo_dir),
            ],
            capture_output=True,
            text=True,
            cwd=str(SCRIPTS_DIR),
        )
        output = result.stdout + result.stderr

        # Cross and Native should appear, Other should be filtered
        assert re.search(r"\d+\. Cross", output), "Cross should be in selection"
        assert re.search(r"\d+\. Native", output), "Native should be in selection"
        assert not re.search(r"(?m)^\d+\. Other$", output), (
            "Other should be filtered out"
        )

    print("  [PASS] platform_filtering")


# -----------------------------------------------------------------------------
# Test: Repo scaffold refresh
# -----------------------------------------------------------------------------
def test_repo_scaffold_refresh() -> None:
    """Confirm scaffold refresh restores missing repo files."""
    with tempfile.TemporaryDirectory(prefix="synconf-test-") as temp_dir:
        repo_dir = Path(temp_dir)
        (repo_dir / "manifest.json").write_text(
            '{"version": 1, "files": []}\n', encoding="utf-8"
        )
        (repo_dir / ".git").mkdir()

        common.ensure_repo_scaffold(repo_dir)
        shutil.rmtree(repo_dir / "scripts")
        (repo_dir / "README.md").unlink()

        common.ensure_repo_scaffold(repo_dir)

        assert_exists(repo_dir / "README.md")
        assert_exists(repo_dir / "scripts")
        assert_exists(repo_dir / "scripts" / "install.py")
        assert_exists(repo_dir / "scripts" / "backup.py")
        assert_exists(repo_dir / "scripts" / "common.py")
        assert_exists(repo_dir / "scripts" / "manage.py")

    print("  [PASS] repo_scaffold_refresh")


# -----------------------------------------------------------------------------
# Test: Selection order (prune follows scan order)
# -----------------------------------------------------------------------------
def test_selection_order() -> None:
    """Confirm prune indices honor the stored last scan order."""
    with tempfile.TemporaryDirectory(prefix="synconf-test-") as temp_dir:
        repo_dir = Path(temp_dir)
        manifest_path = repo_dir / "manifest.json"
        state_path = repo_dir / ".state.json"

        manifest_payload = {
            "version": 1,
            "files": [
                {
                    "software": "Git",
                    "category": "git",
                    "repo_rel": "git/git/.gitconfig",
                    "home_rel": ".gitconfig",
                    "is_dir": False,
                },
                {
                    "software": "Vim",
                    "category": "editor",
                    "repo_rel": "editor/vim/.vimrc",
                    "home_rel": ".vimrc",
                    "is_dir": False,
                },
                {
                    "software": "Zsh",
                    "category": "shell",
                    "repo_rel": "shell/zsh/.zshrc",
                    "home_rel": ".zshrc",
                    "is_dir": False,
                },
            ],
        }
        state_payload = {
            "last_scan_order": [
                "shell/zsh/.zshrc",
                "git/git/.gitconfig",
                "editor/vim/.vimrc",
            ],
        }
        manifest_path.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")
        state_path.write_text(json.dumps(state_payload, indent=2), encoding="utf-8")

        manifest = common.load_manifest(manifest_path)
        state = common.load_state(repo_dir)
        view, using_scan_order = get_selection_view(manifest, state)

        assert using_scan_order, "Expected to use last_scan_order"
        assert [str(e.get("repo_rel", "")) for e in view] == [
            "shell/zsh/.zshrc",
            "git/git/.gitconfig",
            "editor/vim/.vimrc",
        ]

        # Remove index 2 (git/git/.gitconfig in scan order)
        prune_configs(
            manifest, state, repo_dir, manifest_path, remove_indices=[2], auto_yes=True
        )

        updated = json.loads(manifest_path.read_text(encoding="utf-8"))
        kept = [e["repo_rel"] for e in updated.get("files", [])]
        assert kept == ["shell/zsh/.zshrc", "editor/vim/.vimrc"], (
            f"Unexpected kept: {kept}"
        )

    print("  [PASS] selection_order")


# -----------------------------------------------------------------------------
# Test: Manage removal cleanup
# -----------------------------------------------------------------------------
def test_manage_removal_cleanup() -> None:
    """Confirm manifest removal also deletes the corresponding repo backups."""
    with tempfile.TemporaryDirectory(
        prefix="synconf-test-", dir=common.HOME
    ) as temp_dir:
        temp_path = Path(temp_dir)
        repo_dir = temp_path / "repo"
        home_dir = temp_path / "home_sim"
        repo_dir.mkdir(parents=True)
        home_dir.mkdir(parents=True)

        # Create manifest with home_rel pointing to home_sim
        payload = {
            "version": 1,
            "files": [
                {
                    "software": "Keep Git",
                    "category": "git",
                    "repo_rel": "git/keep-git/.gitconfig",
                    "home_rel": str(
                        (home_dir / ".gitconfig").relative_to(common.HOME)
                    ).replace("\\", "/"),
                    "is_dir": False,
                },
                {
                    "software": "Remove Zsh",
                    "category": "shell",
                    "repo_rel": "shell/remove-zsh/.zshrc",
                    "home_rel": str(
                        (home_dir / ".zshrc").relative_to(common.HOME)
                    ).replace("\\", "/"),
                    "is_dir": False,
                },
                {
                    "software": "Remove Zed",
                    "category": "editor",
                    "repo_rel": "editor/remove-zed",
                    "home_rel": str(
                        (home_dir / ".config/zed").relative_to(common.HOME)
                    ).replace("\\", "/"),
                    "is_dir": True,
                },
            ],
        }
        manifest_path = repo_dir / "manifest.json"
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        # Create repo backups
        write_file(repo_dir / "git/keep-git/.gitconfig", "git config\n")
        write_file(repo_dir / "shell/remove-zsh/.zshrc", "zsh config\n")
        (repo_dir / "editor/remove-zed").mkdir(parents=True)
        write_file(repo_dir / "editor/remove-zed/settings.json", '{"theme": "one"}\n')

        # Create local files
        write_file(home_dir / ".gitconfig", "local git\n")
        write_file(home_dir / ".zshrc", "local zsh\n")
        (home_dir / ".config/zed").mkdir(parents=True)
        write_file(home_dir / ".config/zed/settings.json", '{"local": true}\n')

        manifest = common.load_manifest(manifest_path)
        state = common.load_state(repo_dir)
        prune_configs(
            manifest, state, repo_dir, manifest_path, remove_indices=[2, 3], auto_yes=True
        )

        updated = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = updated.get("files", [])
        assert len(files) == 1 and files[0].get("software") == "Keep Git"
        assert (repo_dir / "git/keep-git/.gitconfig").exists(), (
            "Kept backup was removed"
        )
        assert not (repo_dir / "shell/remove-zsh/.zshrc").exists(), (
            "Removed file backup still exists"
        )
        assert not (repo_dir / "editor/remove-zed").exists(), (
            "Removed dir backup still exists"
        )

    print("  [PASS] manage_removal_cleanup")


def test_manage_removal_cleans_software_directory() -> None:
    """Confirm removing a file-backed entry also clears its software directory."""
    with tempfile.TemporaryDirectory(
        prefix="synconf-test-", dir=common.HOME
    ) as temp_dir:
        temp_path = Path(temp_dir)
        repo_dir = temp_path / "repo"
        home_dir = temp_path / "home_sim"
        repo_dir.mkdir(parents=True)
        home_dir.mkdir(parents=True)

        payload = {
            "version": 1,
            "files": [
                {
                    "software": "Remove Zed Settings",
                    "category": "editor",
                    "repo_rel": "editor/remove-zed-settings/settings.json",
                    "home_rel": str(
                        (home_dir / ".config/zed/settings.json").relative_to(
                            common.HOME
                        )
                    ).replace("\\", "/"),
                    "is_dir": False,
                }
            ],
        }
        manifest_path = repo_dir / "manifest.json"
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        write_file(
            repo_dir / "editor/remove-zed-settings/settings.json", '{"theme": "one"}\n'
        )
        write_file(repo_dir / "editor/remove-zed-settings/keymap.json", "[]\n")
        write_file(home_dir / ".config/zed/settings.json", '{"theme": "local"}\n')

        manifest = common.load_manifest(manifest_path)
        state = common.load_state(repo_dir)
        prune_configs(
            manifest, state, repo_dir, manifest_path, remove_indices=[1], auto_yes=True
        )

        assert not (repo_dir / "editor/remove-zed-settings").exists(), (
            "Software directory should be removed when entry is cleared"
        )

    print("  [PASS] manage_removal_cleans_software_directory")


def test_repo_relative_path_layout() -> None:
    """Confirm repo paths use category/software layout with original names preserved."""
    file_path = common.repo_relative_path(
        Path.home() / ".gitconfig",
        "git",
        "Git",
        False,
    )
    dir_path = common.repo_relative_path(
        Path.home() / "AppData/Roaming/Code/User",
        "editor",
        "VS Code",
        True,
        platforms=["windows"],
    )

    assert file_path.as_posix() == "git/git/.gitconfig"
    # Directory preserves its original name under category/software/platform/
    assert dir_path.as_posix() == "editor/vs-code/windows/User"

    print("  [PASS] repo_relative_path_layout")


def test_zed_cross_platform_paths() -> None:
    """Confirm Zed path definitions match platform-specific config locations."""
    config = common.load_config()

    base_editor_entries = config["config_registry"]["categories"]["Editor"]
    base_editor_paths = [item["path"] for item in base_editor_entries]
    macos_editor_paths = [
        item["path"] for item in config["platform_specific_configs"]["macos"]["Editor"]
    ]
    windows_editor_paths = [
        item["path"]
        for item in config["platform_specific_configs"]["windows"]["Editor"]
    ]
    linux_editor_paths = [
        item["path"] for item in config["platform_specific_configs"]["linux"]["Editor"]
    ]

    zed_settings_entry = next(
        item
        for item in base_editor_entries
        if item["path"] == "~/.config/zed/settings.json"
    )
    zed_keymap_entry = next(
        item
        for item in base_editor_entries
        if item["path"] == "~/.config/zed/keymap.json"
    )

    assert "~/.config/zed/settings.json" in base_editor_paths
    assert "~/.config/zed/keymap.json" in base_editor_paths
    assert zed_settings_entry.get("platforms") == ["macos", "linux"]
    assert zed_keymap_entry.get("platforms") == ["macos", "linux"]
    assert "~/Library/Application Support/Zed/settings.json" not in macos_editor_paths
    assert "~/AppData/Roaming/Zed/settings.json" in windows_editor_paths
    assert "~/AppData/Roaming/Zed/keymap.json" in windows_editor_paths
    assert "~/.config/zed/settings.json" not in linux_editor_paths

    print("  [PASS] zed_cross_platform_paths")


def test_run_scan_filters_registry_platforms() -> None:
    """Confirm scan ignores registry paths that do not support the current OS."""
    with tempfile.TemporaryDirectory(prefix="synconf-test-") as temp_dir:
        temp_path = Path(temp_dir)
        current = common.get_current_platform()
        other = "windows" if current != "windows" else "macos"

        native_path = temp_path / "native.conf"
        cross_path = temp_path / "cross.conf"
        other_path = temp_path / "other.conf"

        write_file(native_path, "native\n")
        write_file(cross_path, "cross\n")
        write_file(other_path, "other\n")

        config = {
            "config_registry": {
                "categories": {
                    "Editor": [
                        {
                            "type": "file",
                            "path": str(native_path),
                            "platforms": [current],
                        },
                        {"type": "file", "path": str(cross_path)},
                        {
                            "type": "file",
                            "path": str(other_path),
                            "platforms": [other],
                        },
                    ]
                }
            },
            "platform_specific_configs": {},
            "category_rules": {"rules": []},
            "software_rules": {"rules": []},
            "platform_rules": {"rules": []},
        }

        results = common.run_scan(config)
        native_rel = common.relative_to_home(native_path).as_posix()
        cross_rel = common.relative_to_home(cross_path).as_posix()
        other_rel = common.relative_to_home(other_path).as_posix()
        scanned_paths = {
            str(entry.get("home_rel", "")) for entry in results if entry.get("home_rel")
        }

        assert native_rel in scanned_paths
        assert cross_rel in scanned_paths
        assert other_rel not in scanned_paths

        native_entry = next(
            entry for entry in results if entry.get("home_rel") == native_rel
        )
        assert native_entry.get("platforms") == [current]

    print("  [PASS] run_scan_filters_registry_platforms")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main() -> None:
    """Run all tests."""
    print("Running synconf tests...\n")

    tests = [
        test_backup_conflict_detection,
        test_restore_conflict_detection,
        test_platform_filtering,
        test_repo_scaffold_refresh,
        test_selection_order,
        test_manage_removal_cleanup,
        test_manage_removal_cleans_software_directory,
        test_repo_relative_path_layout,
        test_zed_cross_platform_paths,
        test_run_scan_filters_registry_platforms,
    ]

    failed = []
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"  [FAIL] {test.__name__}: {e}")
            failed.append(test.__name__)

    print()
    if failed:
        print(f"FAILED: {len(failed)}/{len(tests)} tests")
        for name in failed:
            print(f"  - {name}")
        sys.exit(1)
    else:
        print(f"PASSED: {len(tests)}/{len(tests)} tests")


if __name__ == "__main__":
    main()
