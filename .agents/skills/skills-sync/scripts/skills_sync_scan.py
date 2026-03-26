#!/usr/bin/env python3
"""Scan installed skills and optionally export selected skills to YAML."""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REGISTRY_SOURCE_TYPES = {"registry", "byted", "marketplace"}


def get_home_dir() -> Path:
    """Get user home directory."""
    return Path(os.path.expanduser("~"))


def load_lock_file(lock_path: Path) -> Dict[str, Any]:
    """Load skill-lock.json if it exists."""
    if not lock_path.exists():
        return {"skills": {}}

    with open(lock_path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_source_type(source_type: str) -> str:
    """Normalize source type to standard values."""
    if not source_type:
        return "local"
    if source_type.lower() in REGISTRY_SOURCE_TYPES:
        return "registry"
    return source_type.lower()


def scan_skills_directory(skills_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Scan a skills directory and return skill metadata keyed by skill name."""
    skills: Dict[str, Dict[str, Any]] = {}
    if not skills_dir.exists():
        return skills

    for item in skills_dir.iterdir():
        if item.is_dir() or item.is_symlink():
            skill_md = item / "SKILL.md"
            try:
                resolved = item.resolve()
                if skill_md.exists() or (resolved / "SKILL.md").exists():
                    skills[item.name] = {
                        "path": str(item),
                        "resolved_path": str(resolved),
                        "is_symlink": item.is_symlink(),
                    }
            except (OSError, ValueError):
                pass

    return skills


def scan_all_skills() -> Dict[str, Dict[str, Any]]:
    """Scan all non-local skills from .agents and .claude directories."""
    home = get_home_dir()
    all_skills: Dict[str, Dict[str, Any]] = {}

    agents_lock = load_lock_file(home / ".agents" / ".skill-lock.json")
    lock_skills = agents_lock.get("skills", {})

    agents_skills = scan_skills_directory(home / ".agents" / "skills")
    claude_skills = scan_skills_directory(home / ".claude" / "skills")

    all_skill_names = set(lock_skills.keys()) | set(agents_skills.keys()) | set(claude_skills.keys())

    for name in all_skill_names:
        skill_info: Dict[str, Any] = {
            "name": name,
            "source": "",
            "source_type": "local",
            "skill_path": "",
            "location": [],
            "plugin_name": None,
        }

        if name in lock_skills:
            lock_info = lock_skills[name]
            skill_info["source"] = lock_info.get("source", "")
            skill_info["source_type"] = normalize_source_type(lock_info.get("sourceType", ""))
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
    """Parse comma-separated selection by index or skill name."""
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
        if token.isdigit():
            index = int(token)
            if 1 <= index <= len(sorted_skills):
                skill = sorted_skills[index - 1]
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


def prompt_skill_selection(skills: Dict[str, Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    """Prompt the user to choose which scanned skills to export."""
    sorted_skills = get_sorted_skills(skills)
    if not sorted_skills:
        print("No skills found to export.", file=sys.stderr)
        return None

    while True:
        print("\nDiscovered skills:")
        for index, skill in enumerate(sorted_skills, start=1):
            source = skill["source"] or "n/a"
            locations = ", ".join(skill["location"]) or "unknown"
            print(
                f"  {index}. {skill['name']} "
                f"[{skill['source_type']}] source={source} locations={locations}"
            )

        print("\nSelect the skills to export to YAML.")
        print("Enter comma-separated numbers or skill names, or 'all' for every discovered skill.")
        try:
            selection = input("> ").strip()
        except EOFError:
            print(
                "Interactive selection requires a terminal. Use --skills for non-interactive selection.",
                file=sys.stderr,
            )
            return None

        if not selection:
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
            confirm = input("Generate skills.yaml with these skills? [y/N]: ").strip().lower()
        except EOFError:
            print(
                "Interactive confirmation requires a terminal. Use --skills for non-interactive selection.",
                file=sys.stderr,
            )
            return None

        if confirm in {"y", "yes"}:
            return selected_skills

        try:
            retry = input("Reselect skills? [Y/n]: ").strip().lower()
        except EOFError:
            print("Selection cancelled. No YAML file generated.", file=sys.stderr)
            return None

        if retry in {"", "y", "yes"}:
            continue

        print("Selection cancelled. No YAML file generated.", file=sys.stderr)
        return None
