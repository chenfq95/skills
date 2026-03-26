#!/usr/bin/env python3
"""Restore skills directly from a skills.yaml file."""

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from skills_sync_yaml import load_from_yaml


@dataclass
class SkillInfo:
    """Skill information."""

    name: str
    source: str
    source_type: str
    skill_path: str
    plugin_name: Optional[str] = None


def check_npx_available() -> bool:
    """Check if npx is available."""
    return shutil.which("npx") is not None


def run_command(cmd: List[str], description: str) -> bool:
    """Run command and return success status."""
    print(f"\n{'=' * 60}")
    print(f"Executing: {description}")
    print(f"Command: {' '.join(cmd)}")
    print("=" * 60)

    try:
        result = subprocess.run(cmd, check=False)
        if result.returncode == 0:
            print(f"[OK] {description} completed")
            return True
        print(f"[FAILED] {description} (exit code: {result.returncode})")
        return False
    except FileNotFoundError:
        print(f"[FAILED] Command not found: {cmd[0]}")
        return False
    except Exception as exc:
        print(f"[FAILED] Error: {exc}")
        return False


def restore_all_skills(skills_to_restore: List[SkillInfo]) -> Dict[str, bool]:
    """Restore all enabled skills."""
    results: Dict[str, bool] = {}

    registry_skills = [skill for skill in skills_to_restore if skill.source_type == "registry"]
    github_skills = [skill for skill in skills_to_restore if skill.source_type == "github"]
    local_skills = [skill for skill in skills_to_restore if skill.source_type == "local"]

    print("\n" + "=" * 60)
    print("Skills Restore")
    print("=" * 60)
    print(f"Installing {len(skills_to_restore)} skill(s):")
    for skill in skills_to_restore:
        print(f"  - {skill.name} ({skill.source_type}: {skill.source or 'n/a'})")
    print("=" * 60)

    if local_skills:
        print("\n[WARNING] The following local-only skills cannot be auto-restored:")
        for skill in local_skills:
            print(f"  - {skill.name}")
            results[skill.name] = False
        print("Please back up these skills manually.\n")

    restorable = registry_skills + github_skills
    if not restorable:
        print("\nNo restorable skills found.")
        return results

    if not check_npx_available():
        print("\n[FAILED] npx not found. Please install Node.js first.")
        print("  Download: https://nodejs.org/")
        sys.exit(1)

    registry_sources = {skill.source for skill in registry_skills}
    for source in registry_sources:
        source_skills = [skill for skill in registry_skills if skill.source == source]
        success = run_command(
            ["npx", "skills", "collection", "add", source, "-g", "-y"],
            f"Install collection: {source}",
        )
        for skill in source_skills:
            results[skill.name] = success

    github_repos: Dict[str, List[SkillInfo]] = {}
    for skill in github_skills:
        github_repos.setdefault(skill.source, []).append(skill)

    for repo, skills in github_repos.items():
        skill_names = [skill.name for skill in skills]
        success = run_command(
            ["npx", "skills", "add", repo, "-g", "-y", "--skill", *skill_names],
            f"Install from {repo}: {', '.join(skill_names)}",
        )
        for skill in skills:
            results[skill.name] = success

    return results


def print_summary(results: Dict[str, bool]) -> None:
    """Print installation summary."""
    print("\n" + "=" * 60)
    print("Installation Summary")
    print("=" * 60)

    success_count = sum(1 for success in results.values() if success)
    fail_count = len(results) - success_count

    for name, success in results.items():
        status = "[OK]" if success else "[FAILED]"
        print(f"  {status} {name}")

    print("-" * 60)
    print(f"Total: {success_count} succeeded, {fail_count} failed")
    print("=" * 60)

    if fail_count > 0:
        print("\nTip: For failed skills, try manual installation:")
        print("  npx skills add <source> -g --skill <skill-name>")


def main() -> int:
    """Run restore from YAML."""
    parser = argparse.ArgumentParser(description="Restore skills from a skills.yaml file")
    parser.add_argument("--from-yaml", type=Path, required=True, metavar="PATH")
    args = parser.parse_args()

    try:
        loaded_skills = load_from_yaml(args.from_yaml)
        if not loaded_skills:
            print("Error: No enabled skills found in YAML", file=sys.stderr)
            return 1

        skill_infos = [
            SkillInfo(
                name=skill["name"],
                source=skill.get("source", ""),
                source_type=skill.get("source_type", "local"),
                skill_path=skill.get("skill_path", ""),
                plugin_name=skill.get("plugin_name"),
            )
            for skill in loaded_skills
        ]

        results = restore_all_skills(skill_infos)
        print_summary(results)

        success_count = sum(1 for success in results.values() if success)
        if success_count == len(results):
            return 0
        if success_count > 0:
            return 1
        return 2
    except KeyboardInterrupt:
        print("\n\nOperation cancelled")
        return 130
    except Exception as exc:
        print(f"\nError: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
