#!/usr/bin/env python3
"""Restore skills from a skills.yaml file or from a sibling skills.yaml."""

import argparse
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

yaml = None

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

logger = logging.getLogger("skills_sync")

# Command execution timeout in seconds
COMMAND_TIMEOUT = 300


@dataclass
class SkillInfo:
    """Skill information."""

    name: str
    source: str
    source_url: str
    source_type: str
    skill_path: str
    plugin_name: Optional[str] = None


def get_home_dir() -> Path:
    """Get the current user's home directory."""
    return Path(os.path.expanduser("~"))


def scan_skills_directory(skills_dir: Path) -> List[str]:
    """Return installed skill names from a skills directory."""
    names: List[str] = []
    if not skills_dir.exists():
        return names

    try:
        items = list(skills_dir.iterdir())
    except PermissionError as e:
        logger.warning("Permission denied reading %s: %s", skills_dir, e)
        return names
    except OSError as e:
        logger.warning("Error reading %s: %s", skills_dir, e)
        return names

    for item in items:
        if not (item.is_dir() or item.is_symlink()):
            continue
        try:
            resolved = item.resolve()
        except (OSError, ValueError):
            resolved = item
        if (item / "SKILL.md").exists() or (resolved / "SKILL.md").exists():
            names.append(item.name)

    return names


def get_installed_skill_names() -> List[str]:
    """Return actually installed global skill names across supported locations."""
    home = get_home_dir()
    installed = set()

    installed.update(scan_skills_directory(home / ".agents" / "skills"))
    installed.update(scan_skills_directory(home / ".claude" / "skills"))

    return sorted(installed)


def parse_yaml_simple(content: str) -> Dict[str, Any]:
    """Parse the small skills.yaml schema without PyYAML."""
    result: Dict[str, Any] = {"version": 1, "skills": []}
    current_skill: Optional[Dict[str, Any]] = None

    for line in content.splitlines():
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("version:"):
            try:
                result["version"] = int(stripped.split(":", 1)[1].strip())
            except ValueError:
                logger.warning("Invalid version format, defaulting to 1")
                result["version"] = 1
            continue

        if stripped.startswith("- name:"):
            if current_skill is not None:
                result["skills"].append(current_skill)
            current_skill = {
                "name": stripped.split(":", 1)[1].strip().strip('"'),
                "source": "",
                "source_url": "",
                "source_type": "local",
                "skill_path": "",
                "plugin_name": None,
                "enabled": True,
            }
            continue

        if current_skill is None or ":" not in stripped:
            continue

        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"')

        if key == "source":
            current_skill["source"] = value if value != '""' else ""
        elif key == "source_url":
            current_skill["source_url"] = value if value != '""' else ""
        elif key == "source_type":
            current_skill["source_type"] = value
        elif key == "skill_path":
            current_skill["skill_path"] = value if value != '""' else ""
        elif key == "plugin_name":
            current_skill["plugin_name"] = value if value else None
        elif key == "enabled":
            current_skill["enabled"] = value.lower() == "true"

    if current_skill is not None:
        result["skills"].append(current_skill)

    return result


def load_from_yaml(yaml_path: Path) -> List[Dict[str, Any]]:
    """Load enabled skills from a YAML file."""
    if not yaml_path.exists():
        print(f"Error: YAML file not found: {yaml_path}", file=sys.stderr)
        sys.exit(1)

    try:
        content = yaml_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"Error: Failed to read YAML file: {e}", file=sys.stderr)
        sys.exit(1)
    except UnicodeDecodeError as e:
        print(f"Error: YAML file is not valid UTF-8: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        if HAS_YAML:
            assert yaml is not None
            data = yaml.safe_load(content)
        else:
            data = parse_yaml_simple(content)
    except Exception as e:
        print(f"Error: Failed to parse YAML: {e}", file=sys.stderr)
        sys.exit(1)

    if data is None:
        return []

    if not isinstance(data, dict):
        print("Error: YAML root must be a mapping", file=sys.stderr)
        sys.exit(1)

    skills = data.get("skills", [])
    if not isinstance(skills, list):
        print("Error: 'skills' must be a list", file=sys.stderr)
        sys.exit(1)

    return [
        skill for skill in skills
        if isinstance(skill, dict) and skill.get("enabled", True)
    ]


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
        result = subprocess.run(cmd, check=False, timeout=COMMAND_TIMEOUT)
        if result.returncode == 0:
            print(f"[OK] {description} completed")
            return True
        print(f"[FAILED] {description} (exit code: {result.returncode})")
        return False
    except subprocess.TimeoutExpired:
        print(f"[FAILED] {description} timed out after {COMMAND_TIMEOUT}s")
        return False
    except FileNotFoundError:
        print(f"[FAILED] Command not found: {cmd[0]}")
        return False
    except Exception as exc:
        print(f"[FAILED] Error: {exc}")
        return False


def run_command_and_verify(
    cmd: List[str],
    description: str,
    expected_skill_names: List[str],
) -> bool:
    """Run a command and verify the requested skills are installed afterward."""
    success = run_command(cmd, description)
    if not success:
        return False

    installed = set(get_installed_skill_names())
    missing = [name for name in expected_skill_names if name not in installed]
    if not missing:
        return True

    print(
        "[FAILED] Command finished but the expected skills were not installed: "
        + ", ".join(missing)
    )
    return False


def normalize_registry_source(source: str) -> str:
    """Normalize registry sources to the format expected by the skills CLI."""
    if not source:
        return ""

    normalized = source.strip()
    if not normalized:
        return ""

    if normalized.startswith("http://") or normalized.startswith("https://"):
        try:
            parsed = urlparse(normalized)
            path = parsed.path.strip("/")
            if parsed.netloc == "skills.byted.org" and path:
                return f"{parsed.netloc}/{path}"
        except ValueError:
            # Invalid URL, return as-is
            pass
        return normalized

    return normalized


def install_byted_skills(skills: List[SkillInfo], results: Dict[str, bool]) -> None:
    """Restore Byted-hosted skills with the locator format expected by the CLI."""
    grouped: Dict[str, List[SkillInfo]] = {}

    for skill in skills:
        locator = normalize_registry_source(skill.source_url)
        if not locator:
            locator = normalize_registry_source(skill.source)

        if not locator:
            print(
                f"[FAILED] Byted skill '{skill.name}' is missing both "
                "source_url and source."
            )
            results[skill.name] = False
            continue

        grouped.setdefault(locator, []).append(skill)

    for locator, locator_skills in grouped.items():
        skill_names = [skill.name for skill in locator_skills]
        print(
            "[INFO] Detected Byted source; using direct install mode with locator "
            f"'{locator}'."
        )
        success = run_command_and_verify(
            ["npx", "skills", "add", locator, "-g", "-y", "--skill", *skill_names],
            f"Install Byted skills from {locator}: {', '.join(skill_names)}",
            skill_names,
        )
        for skill in locator_skills:
            results[skill.name] = success


def install_collection_with_fallback(
    skills: List[SkillInfo],
    primary_source: str,
) -> bool:
    """Install a registry collection, falling back to source_url when needed."""
    expected_skill_names = [skill.name for skill in skills]
    normalized_primary_source = normalize_registry_source(primary_source)

    if normalized_primary_source:
        success = run_command_and_verify(
            [
                "npx",
                "skills",
                "collection",
                "add",
                normalized_primary_source,
                "-g",
                "-y",
            ],
            f"Install collection: {normalized_primary_source}",
            expected_skill_names,
        )
        if success:
            return True

    fallback_urls = []
    seen_urls = set()
    for skill in skills:
        normalized_source_url = normalize_registry_source(skill.source_url)
        if not normalized_source_url or normalized_source_url in seen_urls:
            continue
        seen_urls.add(normalized_source_url)
        fallback_urls.append(normalized_source_url)

    for source_url in fallback_urls:
        if normalized_primary_source and source_url == normalized_primary_source:
            continue
        success = run_command_and_verify(
            ["npx", "skills", "collection", "add", source_url, "-g", "-y"],
            f"Install collection via source_url: {source_url}",
            expected_skill_names,
        )
        if success:
            return True

    skill_names = [skill.name for skill in skills]
    if normalized_primary_source:
        success = run_command_and_verify(
            [
                "npx",
                "skills",
                "add",
                normalized_primary_source,
                "-g",
                "-y",
                "--skill",
                *skill_names,
            ],
            f"Install skills from source: {normalized_primary_source}",
            expected_skill_names,
        )
        if success:
            return True

    for source_url in fallback_urls:
        success = run_command_and_verify(
            ["npx", "skills", "add", source_url, "-g", "-y", "--skill", *skill_names],
            f"Install skills via source_url: {source_url}",
            expected_skill_names,
        )
        if success:
            return True

    return False


def restore_registry_skills(skills: List[SkillInfo], results: Dict[str, bool]) -> None:
    """Restore registry skills, using source_url when source is missing or fails."""
    missing_sources = []
    for skill in skills:
        if not skill.source and not skill.source_url:
            missing_sources.append(skill.name)

    if missing_sources:
        print("\n[FAILED] Some registry skills are missing both source and source_url:")
        for name in missing_sources:
            print(f"  - {name}")
            results[name] = False
        print(
            "Please regenerate skills.yaml with a newer export "
            "or fill in source_url manually."
        )

    available_skills = [skill for skill in skills if skill.name not in missing_sources]

    registry_sources = {skill.source for skill in available_skills if skill.source}
    for source in registry_sources:
        source_skills = [skill for skill in available_skills if skill.source == source]
        success = install_collection_with_fallback(source_skills, source)
        for skill in source_skills:
            results[skill.name] = success

    registry_urls = sorted(
        {
            skill.source_url
            for skill in available_skills
            if skill.source_url and not skill.source
        }
    )
    for source_url in registry_urls:
        source_skills = [
            skill
            for skill in available_skills
            if skill.source_url == source_url and not skill.source
        ]
        success = install_collection_with_fallback(source_skills, "")
        for skill in source_skills:
            results[skill.name] = success


def restore_all_skills(skills_to_restore: List[SkillInfo]) -> Dict[str, bool]:
    """Restore all enabled skills."""
    results: Dict[str, bool] = {}

    byted_skills = [
        skill for skill in skills_to_restore if skill.source_type == "byted"
    ]
    registry_skills = [
        skill for skill in skills_to_restore if skill.source_type == "registry"
    ]
    github_skills = [
        skill for skill in skills_to_restore if skill.source_type == "github"
    ]
    local_skills = [
        skill for skill in skills_to_restore if skill.source_type == "local"
    ]

    print("\n" + "=" * 60)
    print("Skills Restore")
    print("=" * 60)
    print(f"Installing {len(skills_to_restore)} skill(s):")
    for skill in skills_to_restore:
        location = skill.source or skill.source_url or "n/a"
        print(f"  - {skill.name} ({skill.source_type}: {location})")
    print("=" * 60)

    if local_skills:
        print("\n[WARNING] The following local-only skills cannot be auto-restored:")
        for skill in local_skills:
            print(f"  - {skill.name}")
            results[skill.name] = False
        print("Please back up these skills manually.\n")

    restorable = byted_skills + registry_skills + github_skills
    if not restorable:
        print("\nNo restorable skills found.")
        return results

    if not check_npx_available():
        print("\n[FAILED] npx not found. Please install Node.js first.")
        print("  Download: https://nodejs.org/")
        sys.exit(1)

    install_byted_skills(byted_skills, results)
    restore_registry_skills(registry_skills, results)

    github_repos: Dict[str, List[SkillInfo]] = {}
    missing_github_sources: List[str] = []
    for skill in github_skills:
        repo = skill.source or skill.source_url
        if not repo:
            missing_github_sources.append(skill.name)
            results[skill.name] = False
            continue
        github_repos.setdefault(repo, []).append(skill)

    if missing_github_sources:
        print("\n[FAILED] Some GitHub skills are missing both source and source_url:")
        for name in missing_github_sources:
            print(f"  - {name}")
        print(
            "Please regenerate skills.yaml with a newer export "
            "or fill in source/source_url manually."
        )

    for repo, skills in github_repos.items():
        skill_names = [skill.name for skill in skills]
        success = run_command_and_verify(
            ["npx", "skills", "add", repo, "-g", "-y", "--skill", *skill_names],
            f"Install from {repo}: {', '.join(skill_names)}",
            skill_names,
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


def resolve_yaml_path(args: argparse.Namespace) -> Path:
    """Resolve the YAML path for direct or generated-script restores."""
    if args.from_yaml is not None:
        return args.from_yaml
    if args.yaml_path is not None:
        return args.yaml_path
    return Path(__file__).with_name("skills.yaml")


def main() -> int:
    """Run restore from YAML."""
    parser = argparse.ArgumentParser(
        description="Restore skills from a skills.yaml file"
    )
    parser.add_argument(
        "yaml_path",
        nargs="?",
        type=Path,
        help="Optional YAML path. Defaults to ./skills.yaml beside this script.",
    )
    parser.add_argument("--from-yaml", type=Path, metavar="PATH")
    args = parser.parse_args()

    if args.from_yaml is not None and args.yaml_path is not None:
        parser.error("use either positional yaml_path or --from-yaml, not both")

    yaml_path = resolve_yaml_path(args)

    try:
        loaded_skills = load_from_yaml(yaml_path)
        if not loaded_skills:
            print(
                f"Error: No enabled skills found in YAML: {yaml_path}", file=sys.stderr
            )
            return 1

        skill_infos = []
        for skill in loaded_skills:
            name = skill.get("name")
            if not name or not isinstance(name, str):
                logger.warning("Skipping skill with missing or invalid name: %s", skill)
                continue
            skill_infos.append(
                SkillInfo(
                    name=name,
                    source=skill.get("source", "") or "",
                    source_url=skill.get("source_url", "") or "",
                    source_type=skill.get("source_type", "local") or "local",
                    skill_path=skill.get("skill_path", "") or "",
                    plugin_name=skill.get("plugin_name"),
                )
            )

        if not skill_infos:
            print("Error: No valid skills found in YAML", file=sys.stderr)
            return 1

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
