#!/usr/bin/env python3
"""Scan installed skills, export YAML plus a restore script, or restore from YAML."""

import argparse
import sys
from pathlib import Path

from restore_skills import main as restore_from_yaml_main
from skills_sync_scan import (
    get_sorted_skills,
    parse_skill_selection,
    print_scan_results,
    print_skill_list,
    prompt_skill_selection,
    scan_all_skills,
)
from skills_sync_yaml import export_bundle, load_from_yaml

# Python version check
if sys.version_info < (3, 8):
    print("Error: This script requires Python 3.8 or higher")
    sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan skills and manage skills.yaml",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Scan and list discovered non-local skills",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output scan results as JSON instead of human-readable list",
    )
    parser.add_argument(
        "--output-yaml",
        type=Path,
        metavar="PATH",
        help="Export selection to a YAML file plus restore_skills.py",
    )
    parser.add_argument(
        "--from-yaml",
        type=Path,
        metavar="PATH",
        help="Restore skills directly from a YAML file",
    )
    parser.add_argument(
        "--skills",
        type=str,
        help="Comma-separated list of skill names to export without prompts",
    )

    args = parser.parse_args()

    # Validate conflicting options
    if args.from_yaml and args.scan:
        parser.error("--from-yaml and --scan are mutually exclusive")

    if args.skills and not args.output_yaml:
        parser.error("--skills requires --output-yaml")

    if args.json and not args.scan:
        parser.error("--json requires --scan")

    # Scan with output-yaml: export mode
    if args.scan and args.output_yaml:
        try:
            all_skills = scan_all_skills()
        except Exception as e:
            print(f"Error scanning skills: {e}", file=sys.stderr)
            return 1

        if args.skills:
            selected_skills, invalid = parse_skill_selection(
                args.skills, get_sorted_skills(all_skills)
            )
            if invalid:
                print(
                    f"Error: Invalid selection: {', '.join(invalid)}", file=sys.stderr
                )
                return 1
            if not selected_skills:
                print("Error: No valid skills selected", file=sys.stderr)
                return 1
        else:
            selected_skills = prompt_skill_selection(all_skills)
            if not selected_skills:
                return 1

        try:
            export_bundle(selected_skills, args.output_yaml)
        except (OSError, FileNotFoundError) as e:
            print(f"Error exporting: {e}", file=sys.stderr)
            return 1
        return 0

    # Scan only: list or JSON output
    if args.scan:
        try:
            all_skills = scan_all_skills()
        except Exception as e:
            print(f"Error scanning skills: {e}", file=sys.stderr)
            return 1
        if args.json:
            print_scan_results(all_skills)
        else:
            print_skill_list(all_skills)
        return 0

    if args.from_yaml:
        if not args.from_yaml.exists():
            print(f"Error: YAML file not found: {args.from_yaml}", file=sys.stderr)
            return 1
        # Validate YAML can be loaded before calling restore
        try:
            load_from_yaml(args.from_yaml)
        except (FileNotFoundError, ValueError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        sys.argv = [sys.argv[0], "--from-yaml", str(args.from_yaml)]
        return restore_from_yaml_main()

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
