# AGENTS.md

This repository is for developing, debugging, and storing personal agent skills.
Most code today lives under `.agents/skills/synconf/` and is plain Python 3.

## Repo Snapshot

- Primary assets: skill docs, Python helper scripts, references, and eval fixtures.
- Main Python sources:
  - `.agents/skills/synconf/scripts/scan_configs.py`
  - `.agents/skills/synconf/scripts/generate_sync.py`
- There is currently no `package.json`, `pyproject.toml`, `pytest.ini`, `tox.ini`, or `Makefile`.
- There is currently no checked-in formal test suite.
- No Cursor rules were found in `.cursor/rules/` or `.cursorrules`.
- No Copilot instructions were found in `.github/copilot-instructions.md`.

## Agent Priorities

- Preserve the repo's current simplicity; do not introduce heavy tooling without a clear need.
- Prefer small, targeted edits over broad refactors.
- Keep guidance in sync across `SKILL.md`, scripts, references, and evals when behavior changes.
- Treat this repo as instruction-heavy: wording changes can be product changes.

## Build / Lint / Test Commands

There is no dedicated build pipeline right now. For this repo, "build/test" mostly means syntax checks and script smoke checks.

### Core validation commands

- Syntax-check all current Python scripts:
  - `python3 -m py_compile .agents/skills/synconf/scripts/scan_configs.py .agents/skills/synconf/scripts/generate_sync.py`
  - `python3 -m py_compile .agents/skills/synconf/scripts/backup.py`
  - `python3 -m py_compile .agents/skills/synconf/scripts/restore.py`
  - `python3 -m py_compile .agents/skills/synconf/scripts/validate_platform_filtering.py`
  - `python3 -m py_compile .agents/skills/synconf/scripts/validate_backup_conflict_detection.py`
  - `python3 -m py_compile .agents/skills/synconf/scripts/validate_restore_conflict_detection.py`
  - `python3 -m py_compile .agents/skills/synconf/scripts/validate_scan_manifest_merge.py`
  - `python3 -m py_compile .agents/skills/synconf/scripts/validate_scan_selection_order.py`
  - `python3 -m py_compile .agents/skills/synconf/scripts/validate_manage_removal_cleanup.py`
  - `python3 -m py_compile .agents/skills/synconf/scripts/validate_repo_scaffold_refresh.py`
- Smoke-check CLI help for the scanner:
  - `python3 .agents/skills/synconf/scripts/scan_configs.py --help`
- Smoke-check CLI help for the generator:
  - `python3 .agents/skills/synconf/scripts/generate_sync.py --help`
- Validate generated restore platform filtering:
  - `python3 .agents/skills/synconf/scripts/validate_platform_filtering.py`
- Validate that backup detects repo/local conflicts before write decisions:
  - `python3 .agents/skills/synconf/scripts/validate_backup_conflict_detection.py`
- Validate that restore detects repo/local conflicts before write decisions:
  - `python3 .agents/skills/synconf/scripts/validate_restore_conflict_detection.py`
- Validate that scan preserves existing manifest entries:
  - `python3 .agents/skills/synconf/scripts/validate_scan_manifest_merge.py`
- Validate that explicit selection indices follow the latest scan order:
  - `python3 .agents/skills/synconf/scripts/validate_scan_selection_order.py`
- Validate that untracking entries also removes repo backups:
  - `python3 .agents/skills/synconf/scripts/validate_manage_removal_cleanup.py`
- Validate that existing repos get missing scaffold files refreshed:
  - `python3 .agents/skills/synconf/scripts/validate_repo_scaffold_refresh.py`

### Run the main scripts

- Scan configs in human-readable mode:
  - `python3 .agents/skills/synconf/scripts/scan_configs.py`
- Scan configs in JSON mode:
  - `python3 .agents/skills/synconf/scripts/scan_configs.py --json`
- Show generator usage:
  - `python3 .agents/skills/synconf/scripts/generate_sync.py --help`
- Generate a sync repo for selected paths:
  - `python3 .agents/skills/synconf/scripts/generate_sync.py ~/.zshrc ~/.gitconfig`
- Generate into a custom repo directory:
  - `python3 .agents/skills/synconf/scripts/generate_sync.py --repo-dir ~/dotfiles ~/.zshrc`

### "Single test" equivalents

Because there is no formal unit test runner yet, use one of these targeted checks as the closest equivalent to a single test:

- Syntax-check one file:
  - `python3 -m py_compile .agents/skills/synconf/scripts/scan_configs.py`
  - `python3 -m py_compile .agents/skills/synconf/scripts/generate_sync.py`
  - `python3 -m py_compile .agents/skills/synconf/scripts/backup.py`
  - `python3 -m py_compile .agents/skills/synconf/scripts/restore.py`
  - `python3 -m py_compile .agents/skills/synconf/scripts/validate_platform_filtering.py`
  - `python3 -m py_compile .agents/skills/synconf/scripts/validate_backup_conflict_detection.py`
  - `python3 -m py_compile .agents/skills/synconf/scripts/validate_restore_conflict_detection.py`
  - `python3 -m py_compile .agents/skills/synconf/scripts/validate_scan_manifest_merge.py`
  - `python3 -m py_compile .agents/skills/synconf/scripts/validate_scan_selection_order.py`
  - `python3 -m py_compile .agents/skills/synconf/scripts/validate_manage_removal_cleanup.py`
  - `python3 -m py_compile .agents/skills/synconf/scripts/validate_repo_scaffold_refresh.py`
- Smoke-check one script's CLI contract:
  - `python3 .agents/skills/synconf/scripts/scan_configs.py --help`
  - `python3 .agents/skills/synconf/scripts/generate_sync.py --help`
- Run one narrow behavior manually:
  - `python3 .agents/skills/synconf/scripts/scan_configs.py --json`
  - `python3 .agents/skills/synconf/scripts/validate_platform_filtering.py`
  - `python3 .agents/skills/synconf/scripts/validate_backup_conflict_detection.py`
  - `python3 .agents/skills/synconf/scripts/validate_restore_conflict_detection.py`
  - `python3 .agents/skills/synconf/scripts/validate_scan_manifest_merge.py`
  - `python3 .agents/skills/synconf/scripts/validate_scan_selection_order.py`
  - `python3 .agents/skills/synconf/scripts/validate_manage_removal_cleanup.py`
  - `python3 .agents/skills/synconf/scripts/validate_repo_scaffold_refresh.py`

### If you add tests later

- Prefer `pytest` if a test suite is introduced.
- Keep single-test invocation documented in this file, for example:
  - `pytest path/to/test_file.py`
  - `pytest path/to/test_file.py -k test_name`
  - `pytest path/to/test_file.py::test_name`

## Code Style

The existing codebase is consistent enough to infer a house style. Follow it unless the repo adopts explicit tooling later.

### Python version and compatibility

- Target Python 3.8+.
- Do not use Python 3.9+ typing syntax such as `list[str]`, `dict[str, object]`, or `Path | None`.
- Import collection types from `typing` instead, e.g. `List`, `Dict`, `Optional`, `Tuple`.
- Keep generated scripts compatible with the same Python floor as the source generator.

### Imports

- Use standard-library imports only unless there is a strong reason to add a dependency.
- Group imports in the normal Python order: standard library first, then local imports if any.
- Within a group, keep imports stable and roughly alphabetical.
- Prefer explicit imports like `from pathlib import Path` over module-qualified path usage everywhere.
- Remove unused imports when touching a file.

### Formatting

- Use 4 spaces for indentation.
- Use triple double-quoted docstrings.
- Prefer readable multi-line literals and function calls over dense one-liners.
- Keep line length reasonable; the current code occasionally exceeds 88 chars, but readability matters more than strict wrapping.
- Use trailing commas in multi-line collections/calls when it improves diffs.
- Prefer f-strings for user-facing output and diagnostics.

### Types and data modeling

- Add type hints to new functions.
- Use `@dataclass` for simple structured records, matching `ConfigItem` and `FileMapping`.
- Use `Path` instead of raw path strings internally when working with filesystem logic.
- Convert to `str` at process boundaries, serialized output, or terminal display.
- Keep JSON-like payload typing pragmatic; `Dict[str, object]` is acceptable in this repo.

### Naming conventions

- Files: lower_snake_case, e.g. `scan_configs.py`.
- Functions and variables: `snake_case`.
- Classes: `PascalCase`.
- Constants: `UPPER_SNAKE_CASE`.
- User-facing software labels should be human-readable title case, e.g. `Windows Terminal`, `VS Code`.
- Registry and rules tables should use descriptive names like `CONFIG_REGISTRY`, `CATEGORY_RULES`, `SOFTWARE_RULES`.

### Control flow and structure

- Keep top-level modules easy to scan: constants near the top, helpers next, `main()` near the end.
- Prefer small helper functions for repeated logic such as path normalization, diffing, and manifest handling.
- Keep CLI entrypoints behind `if __name__ == "__main__":`.
- Favor explicit branching over clever abstractions.
- When generating scripts as strings, keep the generated code readable and aligned with the style of handwritten code.

### Error handling

- Fail loudly for unrecoverable setup problems, e.g. raise `RuntimeError` when Git init fails.
- Gracefully skip expected environmental issues such as missing files or unreadable text configs.
- Catch narrow exceptions when possible, as the current code does with `json.JSONDecodeError`, `OSError`, `PermissionError`, and `UnicodeDecodeError`.
- When continuing after an error, print a clear warning that includes the affected path or action.
- Avoid swallowing exceptions without either handling them meaningfully or explaining the fallback.

### Filesystem and subprocess behavior

- Prefer `pathlib.Path` operations over string concatenation.
- Preserve home-relative structure when copying or mapping files.
- Be careful with destructive operations like `shutil.rmtree`; only remove generated/copied targets when logic clearly requires replacement.
- For subprocesses, use `subprocess.run(..., check=False)` and inspect `returncode` when the script needs custom error messages.
- Capture stdout/stderr when surfacing a helpful failure reason to the user.

### User interaction and CLI text

- Keep CLI prompts explicit and operational.
- Default to numbered, per-software selection flows where the skill requires them.
- Prefer concise status text with enough detail to support debugging.
- Preserve important behavior words that recur in the skill spec, such as `overwrite`, `skip`, and `manual`.
- Keep terminology consistent across scripts, docs, and evals.

### Comments and docstrings

- Keep module and function docstrings when they explain behavior succinctly.
- Add comments only when the code would otherwise be non-obvious.
- Prefer improving names or extracting helpers over adding explanatory comments.

## Behavior Rules Derived From The Skill

When editing `synconf` files, preserve these repo-specific expectations unless intentionally changing the product behavior everywhere:

- Default repo path is `~/.synconf`.
- Reuse existing `~/.synconf`; do not delete or recreate it.
- Use copy-based install/restore flows; do not switch to symlinks.
- Selection is per software, not per category.
- Persist tracked state in `manifest.json`.
- Support incremental sync rather than rebuild-only flows.
- Show diffs before overwriting when versions differ.
- Track manual merge follow-ups in `merge-notes/pending-merges.json`.
- Normalize machine-specific home paths with `__SYNCONF_HOME__` and `__SYNCONF_HOME_POSIX__` placeholders.
- Exclude secrets, private keys, credential files, and `.env`-style sensitive data.

## Editing Checklist For Agents

- Read the relevant `SKILL.md` section before changing script behavior.
- Update evals if behavior or wording expectations change.
- Update references if supported software paths change.
- Run syntax checks after Python edits.
- Run at least one script smoke check after CLI changes.
- Do not assume hidden tooling exists; inspect the repo first.

## Current Gaps

- No formal linter is configured.
- No formatter is enforced.
- No automated tests are checked in.
- No workspace-level agent rule files are present besides this document.

If you add any of those, update this file immediately with exact commands, especially the one-file / one-test workflow.
