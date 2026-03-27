#!/usr/bin/env python3
"""Scan installed skills and optionally export selected skills to YAML."""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Configure logging
logger = logging.getLogger("skills_sync")

REGISTRY_SOURCE_TYPES = {"registry", "marketplace"}

# Max symlink resolution depth to prevent infinite loops
MAX_SYMLINK_DEPTH = 40


def get_home_dir() -> Path:
    """Get user home directory."""
    return Path(os.path.expanduser("~"))


def load_lock_file(lock_path: Path) -> Dict[str, Any]:
    """Load skill-lock.json if it exists.

    Args:
        lock_path: Path to the lock file

    Returns:
        Parsed JSON data or empty structure on error
    """
    if not lock_path.exists():
        return {"skills": {}}

    try:
        content = lock_path.read_text(encoding="utf-8")
        data = json.loads(content)
        if not isinstance(data, dict):
            logger.warning("Lock file %s is not a JSON object", lock_path)
            return {"skills": {}}
        return data
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse lock file %s: %s", lock_path, e)
        return {"skills": {}}
    except OSError as e:
        logger.warning("Failed to read lock file %s: %s", lock_path, e)
        return {"skills": {}}
    except UnicodeDecodeError as e:
        logger.warning("Lock file %s is not valid UTF-8: %s", lock_path, e)
        return {"skills": {}}


def normalize_source_type(source_type: str) -> str:
    """Normalize source type to standard values."""
    if not source_type:
        return "local"
    if source_type.lower() == "byted":
        return "byted"
    if source_type.lower() in REGISTRY_SOURCE_TYPES:
        return "registry"
    return source_type.lower()


def is_safe_symlink(path: Path, max_depth: int = MAX_SYMLINK_DEPTH) -> bool:
    """Check if a symlink is safe to follow (no loops, exists).

    Args:
        path: Path to check
        max_depth: Maximum symlink resolution depth

    Returns:
        True if safe, False if broken or circular
    """
    try:
        seen = set()
        current = path
        for _ in range(max_depth):
            if not current.is_symlink():
                return current.exists()
            real = current.resolve()
            if real in seen:
                return False  # Circular symlink
            seen.add(real)
            current = real
        return False  # Too deep
    except (OSError, ValueError):
        return False


def scan_skills_directory(skills_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Scan a skills directory and return skill metadata keyed by skill name.

    Args:
        skills_dir: Directory containing skill subdirectories

    Returns:
        Dict mapping skill names to their metadata
    """
    skills: Dict[str, Dict[str, Any]] = {}
    if not skills_dir.exists():
        return skills

    try:
        items = list(skills_dir.iterdir())
    except PermissionError as e:
        logger.warning("Permission denied reading %s: %s", skills_dir, e)
        return skills
    except OSError as e:
        logger.warning("Error reading %s: %s", skills_dir, e)
        return skills

    for item in items:
        # Skip hidden files and validate name
        if not item.name or item.name.startswith("."):
            continue

        if not (item.is_dir() or item.is_symlink()):
            continue

        # Check symlink safety
        if item.is_symlink() and not is_safe_symlink(item):
            logger.warning("Skipping broken or circular symlink: %s", item)
            continue

        skill_md = item / "SKILL.md"
        try:
            resolved = item.resolve()
            if skill_md.exists() or (resolved / "SKILL.md").exists():
                skills[item.name] = {
                    "path": str(item),
                    "resolved_path": str(resolved),
                    "is_symlink": item.is_symlink(),
                }
        except (OSError, ValueError) as e:
            logger.debug("Error resolving %s: %s", item, e)

    return skills


def scan_all_skills() -> Dict[str, Dict[str, Any]]:
    """Scan all non-local skills from .agents and .claude directories."""
    home = get_home_dir()
    all_skills: Dict[str, Dict[str, Any]] = {}

    agents_lock = load_lock_file(home / ".agents" / ".skill-lock.json")
    lock_skills = agents_lock.get("skills", {})

    agents_skills = scan_skills_directory(home / ".agents" / "skills")
    claude_skills = scan_skills_directory(home / ".claude" / "skills")

    all_skill_names = (
        set(lock_skills.keys()) | set(agents_skills.keys()) | set(claude_skills.keys())
    )

    for name in all_skill_names:
        skill_info: Dict[str, Any] = {
            "name": name,
            "source": "",
            "source_url": "",
            "source_type": "local",
            "skill_path": "",
            "location": [],
            "plugin_name": None,
        }

        if name in lock_skills:
            lock_info = lock_skills[name]
            skill_info["source"] = lock_info.get("source", "")
            skill_info["source_url"] = lock_info.get("sourceUrl", "")
            skill_info["source_type"] = normalize_source_type(
                lock_info.get("sourceType", "")
            )
            skill_info["skill_path"] = lock_info.get("skillPath", "")
            skill_info["plugin_name"] = lock_info.get("pluginName")

        if name in agents_skills:
            skill_info["location"].append(".agents")
        if name in claude_skills:
            skill_info["location"].append(".claude")

        if skill_info["source_type"] == "local":
            continue

        all_skills[name] = skill_info

    return all_skills


def print_scan_results(skills: Dict[str, Dict[str, Any]]) -> None:
    """Print scan results as JSON."""
    output = {"total": len(skills), "skills": list(skills.values())}
    print(json.dumps(output, indent=2, ensure_ascii=False))


def get_sorted_skills(skills: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return skills sorted for display/export."""
    return sorted(
        skills.values(),
        key=lambda s: (s["source_type"] == "local", s["name"]),
    )


def parse_skill_selection(
    selection: str,
    sorted_skills: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Parse comma-separated selection by index or skill name.

    Args:
        selection: User input string with indices or names
        sorted_skills: List of available skills

    Returns:
        Tuple of (selected skills, invalid tokens)
    """
    tokens = [token.strip() for token in selection.split(",") if token.strip()]
    if not tokens:
        return [], []

    if len(tokens) == 1 and tokens[0].lower() == "all":
        return sorted_skills, []

    name_map = {skill["name"]: skill for skill in sorted_skills}
    selected: List[Dict[str, Any]] = []
    invalid: List[str] = []
    seen = set()

    for token in tokens:
        skill = None
        # Only treat as index if it's a positive integer
        if token.isdigit() and token != "0":
            index = int(token)
            if 1 <= index <= len(sorted_skills):
                skill = sorted_skills[index - 1]
            else:
                invalid.append(f"{token} (out of range 1-{len(sorted_skills)})")
                continue
        else:
            skill = name_map.get(token)

        if skill is None:
            invalid.append(token)
            continue

        if skill["name"] in seen:
            continue

        seen.add(skill["name"])
        selected.append(skill)

    return selected, invalid


def prompt_skill_selection(
    skills: Dict[str, Dict[str, Any]],
) -> Optional[List[Dict[str, Any]]]:
    """Prompt the user to choose which scanned skills to export.

    Args:
        skills: Dict of available skills

    Returns:
        List of selected skills, or None if cancelled
    """
    sorted_skills = get_sorted_skills(skills)
    if not sorted_skills:
        print("No skills found to export.", file=sys.stderr)
        return None

    max_attempts = 10  # Prevent infinite loops
    attempts = 0

    while attempts < max_attempts:
        attempts += 1
        print("\nDiscovered skills:")
        for index, skill in enumerate(sorted_skills, start=1):
            source = skill["source"] or "n/a"
            locations = ", ".join(skill["location"]) or "unknown"
            print(
                f"  {index}. {skill['name']} "
                f"[{skill['source_type']}] source={source} locations={locations}"
            )

        print("\nSelect the skills to export to YAML.")
        print(
            "Enter comma-separated numbers or skill names, "
            "or 'all' for every discovered skill."
        )
        print("Enter 'q' or empty to cancel.")
        try:
            selection = input("> ").strip()
        except EOFError:
            print(
                "\nNon-interactive mode detected. "
                "Use --skills for non-interactive selection.",
                file=sys.stderr,
            )
            return None
        except KeyboardInterrupt:
            print("\nSelection cancelled.", file=sys.stderr)
            return None

        if not selection or selection.lower() in ("q", "quit", "exit"):
            print("Selection cancelled. No YAML file generated.", file=sys.stderr)
            return None

        selected_skills, invalid = parse_skill_selection(selection, sorted_skills)
        if invalid:
            print(f"Invalid selection: {', '.join(invalid)}", file=sys.stderr)
            continue

        if not selected_skills:
            print("No valid skills selected.", file=sys.stderr)
            continue

        print("\nSelected skills:")
        for skill in selected_skills:
            print(f"  - {skill['name']} ({skill['source_type']})")

        try:
            confirm = (
                input("Generate skills.yaml with these skills? [y/N]: ").strip().lower()
            )
        except (EOFError, KeyboardInterrupt):
            print("\nSelection cancelled.", file=sys.stderr)
            return None

        if confirm in {"y", "yes"}:
            return selected_skills

        try:
            retry = input("Reselect skills? [Y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nSelection cancelled. No YAML file generated.", file=sys.stderr)
            return None

        if retry in {"", "y", "yes"}:
            continue

        print("Selection cancelled. No YAML file generated.", file=sys.stderr)
        return None

    print("Too many attempts. Selection cancelled.", file=sys.stderr)
    return None
