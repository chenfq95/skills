# AGENTS.md

This repository stores agent skills and the scripts/docs that support them.
The primary active code lives in `.agents/skills/synconf/`, with helper tooling in `.agents/skills/skills-sync/`.

## Scope

- Primary skill: `.agents/skills/synconf/`
- Secondary skill: `.agents/skills/skills-sync/`
- Main code: `.agents/skills/*/scripts/*.py`
- Supporting files: `SKILL.md`, `templates/README.md`, `evals/evals.json`, `config.json`
- There is no root `pyproject.toml`, `pytest.ini`, `tox.ini`, `package.json`, or `Makefile`

## Rule Files

- No Cursor rules were found in `.cursor/rules/`
- No `.cursorrules` file was found
- No Copilot instructions were found in `.github/copilot-instructions.md`
- Treat this file as the top-level agent guidance for the repo

## Repo Priorities

- Keep changes small and targeted
- Preserve synconf's copy-based workflow; do not convert it to symlink-based behavior
- Reuse existing repo structure instead of introducing new frameworks
- Keep scripts, docs, templates, and evals aligned when behavior changes
- Treat wording changes in `SKILL.md` as product changes

## Environment

- Workspace Python is `3.12`, but code intentionally targets Python `3.8+`
- Prefer standard-library-only solutions unless a dependency is clearly justified
- Use `python` in this workspace; `py -3` is not available here

## Build, Lint, and Test

There is no formal build pipeline and no configured linter in the repository root.
Validation is mainly Python syntax checks, CLI help smoke tests, and the custom synconf test runner.

### Repo-wide checks

- Compile all tracked Python:
  - `python -m compileall .agents/skills`
- Syntax-check one file:
  - `python -m py_compile .agents/skills/synconf/scripts/manage.py`

### Synconf commands

- Full test suite:
  - `python .agents/skills/synconf/scripts/tests.py`
- CLI help smoke checks:
  - `python .agents/skills/synconf/scripts/manage.py --help`
  - `python .agents/skills/synconf/scripts/backup.py --help`
  - `python .agents/skills/synconf/scripts/restore.py --help`
  - `python .agents/skills/synconf/scripts/sync.py --help`
  - `python .agents/skills/synconf/scripts/init_repo.py --help`

### Skills-sync commands

- CLI help:
  - `python .agents/skills/skills-sync/scripts/skills_sync.py --help`
- Scan installed skills:
  - `python .agents/skills/skills-sync/scripts/skills_sync.py --scan`
- Export selected skills:
  - `python .agents/skills/skills-sync/scripts/skills_sync.py --scan --output-yaml ./skills.yaml`
- Restore from YAML:
  - `python .agents/skills/skills-sync/scripts/skills_sync.py --from-yaml ./skills.yaml`

### Single-test workflow

There is no `pytest` suite yet.
Run one synconf test by importing `tests.py` and calling a function directly.

- Example:
  - `python -c "import sys; sys.path.insert(0, r'.agents/skills/synconf/scripts'); import tests; tests.test_backup_conflict_detection()"`
- Another example:
  - `python -c "import sys; sys.path.insert(0, r'.agents/skills/synconf/scripts'); import tests; tests.test_selection_order()"`

Available focused tests:

- `test_backup_conflict_detection()`
- `test_restore_conflict_detection()`
- `test_platform_filtering()`
- `test_repo_scaffold_refresh()`
- `test_selection_order()`
- `test_manage_removal_cleanup()`
- `test_manage_removal_cleans_software_directory()`
- `test_repo_relative_path_layout()`
- `test_zed_cross_platform_paths()`
- `test_run_scan_filters_registry_platforms()`

### What to run for common changes

- Docs-only edits:
  - usually just review for consistency unless behavior changed
- `common.py`, `manage.py`, `backup.py`, `restore.py`, or `config.json` changed:
  - `python -m compileall .agents/skills`
  - `python .agents/skills/synconf/scripts/tests.py`
- CLI behavior changed:
  - run the relevant `--help` command
  - run the synconf test suite if behavior changed
- Template or scaffold behavior changed:
  - `python .agents/skills/synconf/scripts/tests.py`

## Runtime Behavior To Preserve

- Default synconf repo path is `~/.synconf`
- Reuse an existing `~/.synconf`; do not delete and recreate it
- Sync is copy-based, not symlink-based
- Selection is per software, not per category
- Tracked inventory lives in `manifest.json`
- Local-only scan state lives in `.state.json`
- Repo backups use `category/software/...`
- Home path normalization uses `__SYNCONF_HOME__` and `__SYNCONF_HOME_POSIX__`
- Pending manual merges live in `merge-notes/pending-merges.json`

## Code Style

Follow the existing style in `.agents/skills/synconf/scripts/*.py` and `.agents/skills/skills-sync/scripts/*.py`.

### Python compatibility

- Target Python `3.8+`
- Do not introduce Python 3.9+ syntax like `list[str]`, `dict[str, Any]`, or `Path | None`
- Prefer `typing.List`, `typing.Dict`, `typing.Optional`, `typing.Tuple`, `typing.Sequence`, and `typing.Mapping`

### Imports

- Group imports as standard library first, then local imports
- Keep imports explicit and stable
- Prefer `from pathlib import Path`
- Remove unused imports when touching a file
- Avoid import-time side effects beyond constants or path setup

### Formatting

- Use 4-space indentation
- Use triple double-quoted docstrings
- Prefer readable multi-line calls over dense one-liners
- Use trailing commas in multi-line literals/calls when helpful
- Prefer f-strings for diagnostics and user-facing output
- Keep files plain ASCII unless Unicode is already established

### Types and data modeling

- Add type hints to new or modified functions
- Use `TypedDict` for JSON-like payloads such as manifest/state data
- Use `@dataclass` for small structured records
- Use `Path` for filesystem values internally; convert at CLI or serialization boundaries
- Keep typing practical; avoid unnecessary abstraction

### Naming

- Files: `lower_snake_case.py`
- Functions and variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Keep user-facing labels human-readable, such as `VS Code`, `Windows Terminal`, and `Oh My Zsh`

### Module organization

- Keep constants and typed payload definitions near the top
- Put reusable helpers before CLI orchestration
- Keep `main()` near the end of CLI modules
- Guard entrypoints with `if __name__ == "__main__":`
- Move shared logic into `common.py` instead of duplicating it

### Error handling

- Raise clear exceptions for real setup failures
- Handle expected environment issues gracefully
- Prefer narrow exception handling such as `ValueError`, `OSError`, `PermissionError`, `UnicodeDecodeError`, and `json.JSONDecodeError`
- When continuing after an error, print a clear warning with the affected path or action
- Do not swallow exceptions silently
- Use `parser.error(...)` for invalid CLI argument combinations

### Filesystem and subprocess work

- Prefer `pathlib.Path` over manual string concatenation
- Be careful with `unlink()` and `shutil.rmtree()`; only remove tracked/generated targets
- Prefer `subprocess.run(..., check=False)` and inspect `returncode`
- Capture stdout/stderr when reporting failures; inherit stdio for interactive flows
- Preserve `.git`, remotes, and repo history

### CLI and UX conventions

- Keep prompts explicit and operational
- Preserve numbered, per-software confirmation flows
- Keep conflict actions consistent: `overwrite`, `skip`, `manual`, `merge`
- Show diffs before overwriting when local and repo versions differ
- End flows with concrete summaries and next actions

### Comments and docs

- Keep comments minimal and only for non-obvious logic
- Prefer better names or helper extraction over explanatory comments
- Update `SKILL.md`, `templates/README.md`, and `evals/evals.json` when behavior changes
- Update this file when commands or workflow expectations change

## Security and Data Handling

- Do not broaden scanning to high-risk credential stores by default
- Exclude secrets, private keys, `.env` files, and credential dumps from tracked content
- Be especially careful around `.aws`, `.docker`, `.kube`, and GitHub CLI config paths
- Preserve the behavior that avoids syncing editor caches and transient runtime files

## Agent Checklist

- Read the relevant `SKILL.md` before changing behavior
- Check whether docs, templates, evals, and scripts all need coordinated updates
- After Python edits, run at least a syntax check on touched files
- After behavior changes, run `python .agents/skills/synconf/scripts/tests.py`
- After CLI changes, run the relevant `--help` command
- If formal linting or pytest is added later, document the exact commands here
