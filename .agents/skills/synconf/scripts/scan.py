#!/usr/bin/env python3
"""Scan for config files and append new entries to manifest.json.

This script scans the local machine for configuration files,
detects their existence, and appends newly discovered entries to manifest.json.
Existing manifest entries are preserved so manual edits and tracked metadata are not lost.
Users can then manually edit manifest.json to select which configs to track.

Usage:
    python3 scripts/scan.py                      # Human-readable output
    python3 scripts/scan.py --json               # JSON output for scripting
    python3 scripts/scan.py --repo-dir ~/.synconf
"""

import argparse
import json
import platform
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


CONFIG_PATH = Path(__file__).parent / "config.json"
HOME = Path.home()
IS_MACOS = platform.system() == "Darwin"
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"


def resolve_repo_dir(repo_dir: Optional[str]) -> Path:
    """Resolve the target synconf repository directory."""
    if repo_dir:
        return Path(repo_dir).expanduser().resolve()
    default_repo_dir = Path.home() / ".synconf"
    if default_repo_dir.exists():
        return default_repo_dir
    return Path(__file__).resolve().parent.parent


@dataclass
class ConfigItem:
    """Represents a detected configuration file or directory."""
    software: str
    source: str
    category: str
    repo_rel: str
    home_rel: str
    exists: bool
    is_dir: bool
    size: str
    file_count: Optional[int] = None
    platforms: Optional[List[str]] = None


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def relative_to_home(path: Path) -> Path:
    """Return a path relative to the user's home directory."""
    try:
        return path.resolve().relative_to(HOME.resolve())
    except ValueError:
        return Path(path.name)


def infer_category(path: Path, category_rules: List[Dict[str, Any]]) -> str:
    """Infer repository category for a config path."""
    text = path.as_posix().lower()
    for rule in category_rules:
        if rule["pattern"].lower() in text:
            return rule["category"]
    return "other"


def infer_software(path: Path, software_rules: List[Dict[str, Any]]) -> str:
    """Infer a user-facing software name from a config path."""
    text = path.as_posix().lower()
    for rule in software_rules:
        if rule["pattern"].lower() in text:
            return rule["software"]
    return path.name or path.as_posix()


def detect_platforms(
    path: Path,
    software: str,
    platform_rules: List[Dict[str, Any]]
) -> Optional[List[str]]:
    """Infer which platforms a config path supports."""
    combined = " ".join([
        path.as_posix().replace("\\", "/").lower(),
        software.strip().lower(),
    ])
    for rule in platform_rules:
        if rule["pattern"] in combined:
            return [p.strip().lower() for p in rule["platforms"]]
    return None


def human_size(path: Path) -> str:
    """Return human-readable size for a file or directory."""
    MAX_FILE_COUNT = 10000
    try:
        if path.is_dir():
            total = 0
            count = 0
            for f in path.rglob("*"):
                if count >= MAX_FILE_COUNT:
                    break
                if f.is_file():
                    try:
                        total += f.stat().st_size
                    except (OSError, PermissionError):
                        pass
                count += 1
        else:
            total = path.stat().st_size
    except (OSError, PermissionError):
        return "?"

    for unit in ("B", "KB", "MB", "GB"):
        if total < 1024:
            return f"{total:.0f}{unit}" if unit == "B" else f"{total:.1f}{unit}"
        total /= 1024
    return f"{total:.1f}TB"


def count_files(path: Path, max_count: int = 10000) -> int:
    """Count files in a directory with a limit for performance."""
    try:
        count = 0
        for f in path.rglob("*"):
            if f.is_file():
                count += 1
                if count >= max_count:
                    break
        return count
    except (OSError, PermissionError):
        return 0


def check_path(path_str: str, config: Dict) -> Optional[ConfigItem]:
    """Check if a path exists and gather info."""
    path = Path(path_str).expanduser()
    if not path.exists():
        return None

    is_dir = path.is_dir()
    rel = relative_to_home(path)

    category_rules = config["category_rules"]["rules"]
    software_rules = config["software_rules"]["rules"]
    platform_rules = config["platform_rules"]["rules"]

    category = infer_category(path, category_rules)
    software = infer_software(path, software_rules)
    repo_rel = Path(category) / rel
    size = human_size(path)
    file_count = count_files(path) if is_dir else None
    platforms = detect_platforms(path, software, platform_rules)

    return ConfigItem(
        software=software,
        source=str(path),
        category=category,
        repo_rel=repo_rel.as_posix(),
        home_rel=rel.as_posix(),
        exists=True,
        is_dir=is_dir,
        size=size,
        file_count=file_count,
        platforms=platforms,
    )


def get_current_platform() -> str:
    """Return the current platform name."""
    if IS_MACOS:
        return "macos"
    if IS_WINDOWS:
        return "windows"
    return "linux"


def scan_configs(config: Dict[str, Any]) -> Dict[str, List[ConfigItem]]:
    """Scan for all registered config files."""
    registry: Dict[str, List[Dict[str, str]]] = config["config_registry"]["categories"]
    platform_configs = config["platform_specific_configs"]
    current_platform = get_current_platform()

    # Add platform-specific configs
    if current_platform in platform_configs:
        for category, entries in platform_configs[current_platform].items():
            if category in registry:
                registry[category].extend(entries)
            else:
                registry[category] = entries

    results: Dict[str, List[ConfigItem]] = {}
    for category, entries in registry.items():
        items = []
        for entry in entries:
            item = check_path(entry["path"], config)
            if item:
                items.append(item)
        if items:
            results[category] = items

    return results


def flatten_results(
    results: Dict[str, List[ConfigItem]],
) -> List[ConfigItem]:
    """Flatten categorized scan results into display order."""
    all_items: List[ConfigItem] = []
    for items in results.values():
        all_items.extend(items)
    return all_items


def update_manifest(
    items: List[ConfigItem],
    manifest_path: Path,
) -> Tuple[int, int]:
    """Append newly scanned items to manifest.json without overwriting existing entries."""
    if manifest_path.exists():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {"version": 1, "files": []}
    else:
        payload = {"version": 1, "files": []}

    existing_files = payload.get("files", [])
    existing_keys = {
        item["repo_rel"]
        for item in existing_files
        if "repo_rel" in item
    }
    added = 0
    scan_order = []

    for item in items:
        scan_order.append(item.repo_rel)
        if item.repo_rel in existing_keys:
            continue
        existing_files.append(asdict(item))
        existing_keys.add(item.repo_rel)
        added += 1

    payload["files"] = existing_files
    payload["last_scan_order"] = scan_order
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return added, len(scan_order)


# ANSI color codes
class Colors:
    """ANSI color codes for terminal output."""
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    CYAN = "\033[0;36m"
    RED = "\033[0;31m"
    RESET = "\033[0m"

    @classmethod
    def check(cls) -> str:
        """Return a green checkmark."""
        return f"{cls.GREEN}\u2713{cls.RESET}"


def format_output(
    results: Dict[str, List[ConfigItem]],
    manifest_count: int,
    repo_dir: Path,
) -> str:
    """Format scan results for terminal display."""
    lines = []
    total_found = 0
    software_index = 1

    lines.append(f"{Colors.YELLOW}=== Scanning for config files in {HOME} ==={Colors.RESET}")
    lines.append("")
    lines.append(f"Existing tracked configs in manifest.json: {manifest_count}")
    lines.append("Scan behavior: new discoveries are appended; existing entries are preserved.")
    lines.append("")

    for category, items in results.items():
        lines.append(f"{Colors.CYAN}[{category}]{Colors.RESET}")
        for item in items:
            label = f"{item.size}"
            if item.is_dir and item.file_count is not None:
                label += f", {item.file_count} files"
            lines.append(
                f"  {software_index}. {Colors.check()} {item.software} {Colors.CYAN}({label}){Colors.RESET}"
            )
            lines.append(f"      local: {item.source}")
            lines.append(f"      repo:  {repo_dir / item.repo_rel}")
            lines.append("      selection: confirm this software individually")
            total_found += 1
            software_index += 1
        lines.append("")

    lines.append(
        f"{Colors.YELLOW}=== Scan complete: Found {total_found} config files/directories ==={Colors.RESET}"
    )
    lines.append("")
    lines.append("Next steps:")
    lines.append("  1. Review the scan results above")
    lines.append(
        f"  2. Review {repo_dir / 'manifest.json'}; existing entries were kept and new ones were appended"
    )
    lines.append("  3. Run 'python3 scripts/backup.py' to backup selected configs")

    return "\n".join(lines)


def format_json(results: Dict[str, List[ConfigItem]]) -> str:
    """Format scan results as JSON."""
    output: Dict[str, List[Dict[str, Any]]] = {}
    for category, items in results.items():
        output[category] = [asdict(item) for item in items]
    return json.dumps(output, indent=2)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Scan for common config files")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--repo-dir",
        type=str,
        help="Target synconf repo to update (default: ~/.synconf when it exists)",
    )
    args = parser.parse_args()
    repo_dir = resolve_repo_dir(args.repo_dir)
    manifest_path = repo_dir / "manifest.json"

    # Load configuration
    try:
        config = load_config()
    except FileNotFoundError as err:
        print(f"Error: {err}", flush=True)
        import sys
        sys.exit(1)

    # Load existing manifest count
    manifest_count = 0
    if manifest_path.exists():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_count = len(payload.get("files", []))
        except json.JSONDecodeError:
            pass

    results = scan_configs(config)

    all_items = flatten_results(results)
    added, scan_count = update_manifest(all_items, manifest_path)

    if args.json:
        print(format_json(results))
    else:
        print(format_output(results, manifest_count, repo_dir))
        if added > 0:
            print(
                f"\n{Colors.GREEN}Appended {added} new entries to {manifest_path}; existing entries were preserved{Colors.RESET}"
            )
        else:
            print(
                f"\n{Colors.CYAN}No new entries to append; existing manifest entries were left unchanged{Colors.RESET}"
            )
        print(
            f"{Colors.CYAN}Saved last scan order for {scan_count} entries to support follow-up selection by index{Colors.RESET}"
        )


if __name__ == "__main__":
    main()
