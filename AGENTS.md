# AGENTS.md

This repository stores agent skills and supporting scripts. The active codebase is the `synconf` skill under `.agents/skills/synconf/`, which is plain Python 3 plus instruction-heavy Markdown and JSON.

## Repo Snapshot

- Primary working area: `.agents/skills/synconf/`
- Main Python entrypoints:
  - `.agents/skills/synconf/scripts/manage.py`
  - `.agents/skills/synconf/scripts/backup.py`
  - `.agents/skills/synconf/scripts/restore.py`
  - `.agents/skills/synconf/scripts/sync.py`
  - `.agents/skills/synconf/scripts/init_repo.py`
  - `.agents/skills/synconf/scripts/install.py`
  - `.agents/skills/synconf/scripts/common.py`
  - `.agents/skills/synconf/scripts/tests.py`
- Supporting assets:
  - `.agents/skills/synconf/SKILL.md`
  - `.agents/skills/synconf/evals/evals.json`
  - `.agents/skills/synconf/scripts/config.json`
  - `.agents/skills/synconf/templates/README.md`
  - `.agents/skills/synconf/templates/gitignore`
- There is no `pyproject.toml`, `pytest.ini`, `tox.ini`, `package.json`, or `Makefile`.

## Repo-Specific Rules Files

- No Cursor rules were found in `.cursor/rules/` or `.cursorrules`.
- No Copilot instructions were found in `.github/copilot-instructions.md`.
- Treat this `AGENTS.md` as the top-level agent guidance file.

## Agent Priorities

- Preserve the repo's simplicity; avoid introducing new frameworks or tooling unless clearly needed.
- Prefer small, targeted edits over broad rewrites.
- Keep product behavior aligned across `SKILL.md`, scripts, templates, and evals.
- Remember that wording changes in skill docs can be product changes.
- Do not silently change the synconf workflow contract when editing scripts.

## Build, Lint, and Test Commands

There is no dedicated build pipeline and no configured linter. Validation in this repo means Python syntax checks, CLI smoke checks, and the consolidated test runner.

### Core validation

- Syntax-check all current synconf scripts:
  - `python -m py_compile .agents/skills/synconf/scripts/common.py .agents/skills/synconf/scripts/manage.py .agents/skills/synconf/scripts/backup.py .agents/skills/synconf/scripts/restore.py .agents/skills/synconf/scripts/sync.py .agents/skills/synconf/scripts/init_repo.py .agents/skills/synconf/scripts/install.py .agents/skills/synconf/scripts/tests.py`
- Run the consolidated test suite:
  - `python .agents/skills/synconf/scripts/tests.py`
- Smoke-check CLI help for interactive entrypoints:
  - `python .agents/skills/synconf/scripts/manage.py --help`
  - `python .agents/skills/synconf/scripts/backup.py --help`
  - `python .agents/skills/synconf/scripts/restore.py --help`
  - `python .agents/skills/synconf/scripts/sync.py --help`
  - `python .agents/skills/synconf/scripts/init_repo.py --help`

### Recommended validation by change type

- Docs or eval text only:
  - Read for consistency; no code command required unless behavior changed.
- `common.py`, `manage.py`, `backup.py`, `restore.py`, or `config.json` changed:
  - Run full `py_compile`
  - Run `python .agents/skills/synconf/scripts/tests.py`
- CLI contract changed:
  - Run the relevant `--help` command
  - Run the full test suite if the CLI affects behavior
- Template changes:
  - Check the template files directly
  - Run `python .agents/skills/synconf/scripts/tests.py` if scaffold behavior may be affected

### Single-test workflow

There is no `pytest` suite yet. The closest equivalent to a single test is invoking one test function from `tests.py`.

- Example single test:
  - `python -c "import sys; sys.path.insert(0, r'.agents/skills/synconf/scripts'); import tests; tests.test_platform_filtering()"`
- Other useful one-test targets:
  - `tests.test_backup_conflict_detection()`
  - `tests.test_restore_conflict_detection()`
  - `tests.test_repo_scaffold_refresh()`
  - `tests.test_selection_order()`
  - `tests.test_manage_removal_cleanup()`
  - `tests.test_manage_removal_cleans_software_directory()`
  - `tests.test_repo_relative_path_layout()`
  - `tests.test_zed_cross_platform_paths()`
  - `tests.test_run_scan_filters_registry_platforms()`

### Fastest narrow checks

- Syntax-check one file:
  - `python -m py_compile .agents/skills/synconf/scripts/manage.py`
- Run one behavioral test:
  - `python -c "import sys; sys.path.insert(0, r'.agents/skills/synconf/scripts'); import tests; tests.test_selection_order()"`
- Check one CLI contract:
  - `python .agents/skills/synconf/scripts/backup.py --help`

### If a formal test runner is added later

- Prefer `pytest`.
- Update this file immediately with exact commands for:
  - full suite
  - one file
  - one test function

## Runtime and Workflow Notes

- Default synconf repo path is `~/.synconf`.
- Reuse an existing `~/.synconf`; do not delete or recreate it.
- Use copy-based flows; do not switch synconf to symlink-based install or restore.
- Selection is per software, not per category.
- Persist tracked inventory in `manifest.json`.
- Persist local-only scan/selection state in `.state.json`.
- Store repo backups under `category/software/...`, not raw machine paths.
- Normalize home-directory text with `__SYNCONF_HOME__` and `__SYNCONF_HOME_POSIX__`.
- Keep pending manual merge tracking in `merge-notes/pending-merges.json`.

## Code Style

Follow the existing house style in `synconf/scripts/*.py` unless a stronger repo convention is introduced.

### Python version and dependencies

- Target Python 3.8+.
- Do not use Python 3.9+ type syntax such as `list[str]`, `dict[str, Any]`, or `Path | None`.
- Prefer standard-library modules only.
- If you believe a new dependency is necessary, document why in the change.

### Imports

- Group imports as: standard library, then local imports.
- Keep imports stable and roughly alphabetical within a group.
- Prefer explicit imports such as `from pathlib import Path`.
- Remove unused imports when touching a file.
- Avoid hidden side effects at import time.

### Formatting

- Use 4-space indentation.
- Use triple double-quoted docstrings.
- Prefer readable multi-line calls and literals over compressed one-liners.
- Keep line length reasonable; readability matters more than strict width.
- Use trailing commas in multi-line literals and calls when it improves diffs.
- Prefer f-strings for diagnostics and user-facing output.

### Types and data modeling

- Add type hints to new or changed functions.
- Use `typing` imports such as `List`, `Dict`, `Optional`, `Tuple`, `Sequence`, and `Mapping`.
- Use `TypedDict` for JSON-shaped payloads like manifest or state entries.
- Use `@dataclass` for simple structured records like `FileMapping`.
- Use `Path` internally for filesystem operations; convert to `str` only at I/O boundaries.
- Keep types pragmatic; overly complex typing is not necessary in this repo.

### Naming

- Files: `lower_snake_case.py`
- Functions and variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- User-facing labels should remain human-readable title case, such as `VS Code` or `Windows Terminal`.
- Prefer descriptive names like `manifest_entry_identity`, `collect_backup_conflicts`, and `platform_rules` over short abbreviations.

### Module structure

- Keep constants and typed payload definitions near the top.
- Put small reusable helpers before command orchestration.
- Keep `main()` near the end of each CLI module.
- Guard entrypoints with `if __name__ == "__main__":`.
- Prefer explicit control flow over clever abstraction.
- When several scripts share logic, move it into `common.py` instead of duplicating it.

### Error handling

- Fail loudly for true setup failures.
- Gracefully handle expected environment issues like missing files, unreadable text, or absent repo state.
- Catch narrow exceptions such as `json.JSONDecodeError`, `OSError`, `PermissionError`, and `UnicodeDecodeError`.
- When continuing after an error, print a clear warning with the affected path or action.
- Do not swallow exceptions silently.

### Filesystem and subprocess behavior

- Prefer `pathlib.Path` over string concatenation.
- Be careful with destructive operations like `shutil.rmtree` and `unlink`.
- Only remove generated or tracked targets when the workflow clearly requires it.
- For subprocesses, prefer `subprocess.run(..., check=False)` and inspect `returncode`.
- Capture stdout/stderr when surfacing a failure reason; inherit stdio for interactive flows.
- Preserve repo structure and avoid deleting `.git`, remotes, or history.

### CLI and user interaction

- Keep prompts explicit and operational.
- Preserve numbered, per-software selection flows.
- Use consistent behavior words: `overwrite`, `skip`, `manual`, `merge`.
- Show diffs before overwriting when repo and local versions differ.
- Keep final summaries concrete and action-oriented.

### Comments and docs

- Keep comments minimal and useful.
- Prefer better names or helper extraction over explanatory comments.
- Update `SKILL.md` and `evals/evals.json` when user-visible behavior changes.
- Update templates if scaffolded repo output changes.

## Security and Data Handling

- Never broaden scanning to high-risk credential stores by default.
- Exclude secrets, private keys, `.env` files, and credential dumps from tracked content.
- Be especially careful around `.aws`, `.docker`, `.kube`, and GitHub CLI config paths.
- Preserve the current behavior that avoids syncing editor caches and runtime junk.

## Editing Checklist For Agents

- Read the relevant parts of `.agents/skills/synconf/SKILL.md` before changing synconf behavior.
- Check whether docs, evals, templates, and scripts all need coordinated updates.
- After Python edits, run at least `py_compile` on touched files.
- After behavior changes, run `python .agents/skills/synconf/scripts/tests.py`.
- After CLI changes, run the relevant `--help` command.
- If you add tooling or tests, document the exact commands here.
