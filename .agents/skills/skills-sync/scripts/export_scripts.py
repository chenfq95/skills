#!/usr/bin/env python3
"""Export skills-sync scripts for standalone usage.

This module is used by the skill workflow to export all necessary scripts
to a directory so users can run them independently with interactive selection.
"""

import argparse
import shutil
import sys
from pathlib import Path

SCRIPTS_TO_EXPORT = [
    "skills_sync.py",
    "skills_sync_scan.py",
    "skills_sync_yaml.py",
    "restore_skills.py",
]

TEMPLATES_TO_EXPORT = [
    "README.md",
    ".gitignore",
]


def export_scripts(output_dir: Path) -> bool:
    """Export all scripts for standalone usage.

    Args:
        output_dir: Directory to export scripts to

    Returns:
        True if successful, False otherwise
    """
    scripts_dir = Path(__file__).parent
    templates_dir = scripts_dir / "templates"
    output_dir.mkdir(parents=True, exist_ok=True)

    exported = []

    # Export Python scripts
    for script_name in SCRIPTS_TO_EXPORT:
        source = scripts_dir / script_name
        if not source.exists():
            print(f"Error: Script not found: {source}", file=sys.stderr)
            return False

        target = output_dir / script_name
        try:
            shutil.copy2(source, target)
            exported.append(script_name)
        except OSError as e:
            print(f"Error: Failed to copy {script_name}: {e}", file=sys.stderr)
            return False

    # Export template files (README.md, .gitignore)
    for template_name in TEMPLATES_TO_EXPORT:
        source = templates_dir / template_name
        if source.exists():
            target = output_dir / template_name
            try:
                shutil.copy2(source, target)
                exported.append(template_name)
            except OSError as e:
                print(f"Warning: Failed to copy {template_name}: {e}", file=sys.stderr)

    print(f"Scripts exported to: {output_dir}")
    print()
    print("Exported files:")
    for name in exported:
        print(f"  - {name}")
    print()
    print("Usage:")
    print(f"  cd {output_dir}")
    print("  python skills_sync.py --list")
    print('  python skills_sync.py --scan --output-yaml ./skills.yaml --skills "all"')
    print("  python restore_skills.py")

    return True


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Export skills-sync scripts for standalone usage"
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Directory to export scripts to",
    )

    args = parser.parse_args()

    if export_scripts(args.output_dir):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
