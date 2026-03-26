#!/usr/bin/env python3
"""Scan installed skills and export selected skills to YAML, or restore directly from YAML."""

import argparse
import sys
from pathlib import Path

from restore_skills import main as restore_from_yaml_main
from skills_sync_scan import (
    get_sorted_skills,
    parse_skill_selection,
    print_scan_results,
    prompt_skill_selection,
    scan_all_skills,
)
from skills_sync_yaml import export_bundle


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
        help="Scan and output discovered skills as JSON",
    )
    parser.add_argument(
        "--output-yaml",
        type=Path,
        metavar="PATH",
        help="After scanning, interactively choose skills and export the confirmed selection to a YAML file",
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

    if args.scan and args.output_yaml:
        all_skills = scan_all_skills()
        if args.skills:
            selected_skills, invalid = parse_skill_selection(args.skills, get_sorted_skills(all_skills))
            if invalid:
                print(f"Error: Invalid selection: {', '.join(invalid)}", file=sys.stderr)
                return 1
            if not selected_skills:
                print("Error: No valid skills selected", file=sys.stderr)
                return 1
        else:
            selected_skills = prompt_skill_selection(all_skills)
            if not selected_skills:
                return 1

        export_bundle(selected_skills, args.output_yaml)
        return 0

    if args.scan:
        all_skills = scan_all_skills()
        print_scan_results(all_skills)
        return 0

    if args.from_yaml:
        sys.argv = [sys.argv[0], "--from-yaml", str(args.from_yaml)]
        return restore_from_yaml_main()

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
