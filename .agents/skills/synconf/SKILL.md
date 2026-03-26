---
name: synconf
description: Sync software configurations across devices using Git on macOS, Linux, and Windows. Use this skill when users want to back up dotfiles, manage configs across multiple machines, migrate to a new computer, or organize shell/editor/tool settings including PowerShell, Windows Terminal, VS Code, Zed, Ghostty, and cross-platform setup flows. Trigger on keywords like dotfiles, config sync, backup settings, new machine setup, sync configs, dotfile manager, chezmoi, stow, PowerShell profile, Windows Terminal config, developer environment migration, and config restore.
---

# SynConf

Manage software configuration backup and restore with a reusable Git repo at `~/.synconf`.

## Skill Layout

Keep the skill source organized by responsibility:

- `SKILL.md`: Product behavior and workflow contract
- `scripts/`: Runtime scripts copied into `~/.synconf/scripts` plus local validation helpers
- `assets/repo-template/install.py`: Root-level install script copied into generated repos
- `evals/`: Prompt/expectation coverage for the skill

The skill source layout is separate from the generated `~/.synconf` repository layout described below.

## Core Rules

- All bundled scripts and generated scripts must run on Python 3.8+; avoid Python 3.9+ type syntax such as `list[str]`, `dict[str, object]`, and `Path | None`.
- Always start with environment detection before selection or sync.
- Default to `~/.synconf` and reuse it in place.
- Never delete, recreate, or replace `~/.synconf` itself; preserve `.git`, remotes, branches, and history.
- Use copy-based install and restore flows; do not rely on symlinks.
- Selection is always per software, never per category.
- Persist tracked inventory in `~/.synconf/manifest.json`; the manifest is human-readable and can be manually edited to add, remove, or adjust tracked software entries.
- When running scripts from the skill source tree during development, pass `--repo-dir ~/.synconf` or another explicit repo path so the source checkout does not write into its own fixture directory by accident.

## When To Use

- User wants to back up dotfiles or app configs
- User is setting up a new machine and wants configs restored
- User wants to sync configs across work and personal devices
- User asks about dotfile managers such as `chezmoi`, `stow`, or `yadm`
- User wants cross-platform support for PowerShell, Windows Terminal, VS Code, Cursor, Zed, Ghostty, or AppData-based settings

## Non-Interactive Mode

All interactive scripts (`backup.py`, `restore.py`, `manage.py`) support a `-y` / `--yes` flag for non-interactive execution. When enabled, all prompts default to "yes" and conflict resolution defaults to "overwrite".

**EXCEPTION: `--select` must NOT use `-y`**

The `--select` command requires explicit user choice. Never combine `--select -y` as it defeats the purpose of user selection.

```bash
# ✓ CORRECT: Let user choose which configs to track
python3 scripts/manage.py --select

# ✗ WRONG: Auto-selecting all configs defeats user choice
python3 scripts/manage.py --select -y

# ✓ OK: Auto-confirm backup after user has selected configs
python3 scripts/backup.py -y

# ✓ OK: Auto-confirm restore
python3 scripts/restore.py -y
```

## Quick Start

**First time setup on a new machine:**

```bash
# 1. Initialize synconf repository (one-time)
python3 ~/.synconf/scripts/init_repo.py

# 2. Scan for existing configs
python3 ~/.synconf/scripts/scan.py

# 3. Select which configs to track (REQUIRED - do not skip)
python3 ~/.synconf/scripts/manage.py --select

# 4. Backup selected configs to repo
python3 ~/.synconf/scripts/backup.py -y

# 5. Commit to Git
git -C ~/.synconf add -A && git -C ~/.synconf commit -m "Backup configs"
```

**IMPORTANT: Agent Execution Flow**

When the agent executes this skill, it MUST follow these rules:

1. **Always show scan results** before any backup/restore operation
2. **Never use `-y` with `--select`** - the user must explicitly choose which configs to track
3. **Ask the user** which configs to include by listing all discovered configs with indices
4. **Wait for user response** specifying which indices to keep (e.g., "1,3,5" or "all")
5. **Update manifest.json** using `manage.py --select` with user's selection before proceeding
6. **Immediately after selection, detect repo/local conflicts for the selected entries before writing anything**
7. **If conflicts exist, show a numbered conflict summary and ask the user for an upfront default strategy**: `overwrite-all`, `skip-all`, `manual-all`, or `review-each`
8. **If the user chooses a bulk strategy, allow per-conflict exceptions before any write begins**
9. **After finishing the requested work, give the user a detailed action checklist** covering what was completed, which files or software were affected, any manual follow-up items, and the exact next commands if Git commit/push or restore steps are still pending

Example agent interaction:
```
Agent: Found 15 config files. Which ones do you want to backup?
  1. Zsh (~/.zshrc) - 5.1KB
  2. Git (~/.gitconfig) - 52B
  3. VS Code (Library/Application Support/Code/User) - 35.0MB
  ...
User: 1,2,5
Agent: [Updates manifest.json with only selected configs, checks the selected entries for conflicts, gets a conflict decision, then runs backup]
```

At the end of a completed run, the agent should summarize the result with an explicit checklist, for example:
```

The completed run summary must also include a detailed file operation checklist. For each processed entry, include:
- source path
- target path
- whether the target path existed before the action
- the actual action taken, such as `create`, `overwrite`, `unchanged`, `skip-conflict`, `manual-merge-later`, or `skip-missing-source`
Completed:
1. Scanned local configs and updated ~/.synconf/manifest.json
2. Kept entries 1,2,5 in the tracked inventory
3. Backed up Zsh, Git, and VS Code into ~/.synconf

Follow-up checklist:
1. Review pending merges in ~/.synconf/merge-notes/pending-merges.json
2. Inspect changed files with git -C ~/.synconf status
3. Commit with git -C ~/.synconf add -A && git -C ~/.synconf commit -m "Update synconf"
4. Push with git -C ~/.synconf push
```

**Restore on another machine:**

```bash
# 1. Clone your synconf repo (or copy from another machine)
git clone <your-repo-url> ~/.synconf

# 2. Restore selected configs
python3 ~/.synconf/scripts/restore.py
```

## Workflow

### 1. Detect Environment

Before any scan, backup, restore, or incremental update, detect and summarize:

- OS
- home directory
- repo path
- whether `~/.synconf` already exists
- whether Python is configured for the current user
- Python executable path
- existing tracked config count from `~/.synconf/manifest.json`, if present

If the repo already exists, frame the run as incremental sync rather than first-time setup.

### 2. Scan Configurations

Run the scanner to detect configs and append new entries to manifest.json:

```bash
python3 scripts/scan.py
```

When running the skill source checkout instead of the copied runtime scripts, target the real repo explicitly:

```bash
python3 <skill-path>/scripts/scan.py --repo-dir ~/.synconf
```

For machine-readable output:

```bash
python3 scripts/scan.py --json
```

The scanner:
- Detects config files in the home directory
- Shows software name, local path, repo target path, and size
- Adds new entries to `manifest.json` automatically
- Preserves existing `manifest.json` entries instead of overwriting them during scan
- Saves the latest scan display order in `manifest.json` so follow-up `manage.py --select --keep ...` uses the same numbering the user saw
- Reports existing tracked config count

Categories are for display only. Selection is always per software.

### 3. Select Configs To Track (REQUIRED)

After scanning, interactively choose which configs to track:

```bash
python3 scripts/manage.py --select
```

For agent-driven incremental updates, an explicit non-interactive selection is also allowed as long as the user has already chosen the indices:

```bash
python3 scripts/manage.py --select --keep 1,3,5
```

The selection step shows each config with:
- Software name and category
- Local path and size
- File count (for directories)
- Platform compatibility
- Existence status

Users confirm or skip each entry. Unselected entries are removed from `manifest.json`.
When an entry is explicitly untracked through `manage.py --select`, remove its corresponding backup file or directory from the repo as part of the same operation.

`--keep` accepts explicit 1-based indices or `all`. It must reflect the user's prior choice; do not invent the selection.
When `last_scan_order` is present in `manifest.json`, `--keep` indices are interpreted against that latest scan order instead of raw manifest storage order.

**Agent Rule:** When executing this step, the agent MUST:
1. First run `scan.py` to discover all configs
2. Display the discovered configs to the user with numbered indices
3. Ask the user which configs to track (e.g., "Enter indices like 1,3,5 or 'all'")
4. Only proceed after receiving explicit user selection

### 3.5. Preflight Conflict Review (REQUIRED before backup or restore writes)

After the user has selected which configs to track or back up, but before any file copy starts:

1. Detect conflicts only within the selected subset
2. Show a numbered summary of selected entries whose local and repo versions both exist and differ
3. Ask the user to choose a default conflict strategy:
   - `overwrite-all`
   - `skip-all`
   - `manual-all`
   - `review-each`
4. If the user chose a bulk strategy, give them one pass to override individual conflicts before writing
5. Only after this preflight decision step is complete may backup start changing repo files or restore start changing local files

This preflight step is part of the skill execution contract, not an optional UX enhancement.

### 4. Manage Tracked Software (Optional)

Use the management tool to manage `manifest.json`:

```bash
# List all tracked software
python3 scripts/manage.py --list
```

Users can also manually edit `manifest.json` to add, remove, or adjust tracked software entries.

### 4. Back Up To `~/.synconf`

Run backup with per-software confirmation:

```bash
python3 scripts/backup.py
```

To back up only the entries involved in the current incremental change, pass an explicit filter:

```bash
python3 scripts/backup.py --only .zshrc,.zprofile
```

The backup script:
- Reads `manifest.json` for tracked software
- Prompts for per-software confirmation
- Supports `--only` to constrain backup to a specific manifest subset during incremental sync
- After the user finishes selecting software, scans the selected entries for repo/local conflicts before writing anything
- Lets the user choose an upfront default conflict strategy for the detected conflicts: `overwrite-all`, `skip-all`, `manual-all`, or `review-each`
- When the user picks a bulk conflict strategy, allows per-conflict exceptions before write operations begin
- Skips unsupported special filesystem entries such as sockets and broken symlinks inside tracked directories instead of aborting the entire backup
- Shows diffs if repo and local versions differ
- Normalizes home paths to `__SYNCONF_HOME__` / `__SYNCONF_HOME_POSIX__` placeholders
- Saves merge notes to `~/.synconf/merge-notes/`
- Records pending merges in `~/.synconf/merge-notes/pending-merges.json`
- Updates `manifest.json` with backed-up entries
- Prints a final summary
- Prints a detailed file operation checklist with source, target, target existence, and actual action

For agent-driven incremental sync after a numbered selection, prefer:

```bash
python3 scripts/backup.py -y --only .zshrc,.zprofile
```

That keeps the non-interactive backup aligned with the user's explicit selection even if unrelated tracked entries already exist in `manifest.json`.
When conflicts are expected, the agent should tell the user that conflict detection happens immediately after selection and before any backup writes occur.

### 5. Restore Or Sync To Local Machine

Run restore with per-software confirmation:

```bash
python3 scripts/restore.py
```

The restore script:
- Reads `manifest.json` for tracked software
- Filters out entries not supported on current platform
- Prompts for per-software confirmation
- After the user finishes selecting software, scans the selected entries for repo/local conflicts before writing anything
- Lets the user choose an upfront default conflict strategy for the detected conflicts: `overwrite-all`, `skip-all`, `manual-all`, or `review-each`
- When the user picks a bulk conflict strategy, allows per-conflict exceptions before write operations begin
- Renders placeholders to current home path
- Shows diffs before overwriting
- Offers overwrite, skip, or manual merge options
- Prints a final sync summary
- Prints a detailed file operation checklist with source, target, target existence, and actual action

### 6. Support Incremental Sync

Treat `~/.synconf/manifest.json` as the tracked inventory.

- On first run, create it from the selected software set
- On later runs, merge newly selected software into the manifest
- Do not rebuild the repo from scratch when adding new software
- Keep existing tracked entries unless the user explicitly asks to remove one
- The manifest is human-readable JSON; users can manually edit it to add, remove, or adjust tracked software entries between sync rounds

### 7. Support Repeated Sync Rounds

`scripts/sync.py` should support multiple interactive rounds in one session.

Each round can:

- run backup
- optionally run repo-to-local restore
- commit and push changes if anything changed

After each round, offer another round without restarting the repo workflow.

## Repository Shape

Typical layout:

```text
.synconf/
├── README.md
├── manifest.json       # Human-editable tracked software inventory
├── install.py          # Static script: install configs to local machine
├── merge-notes/
├── shell/
├── git/
├── editor/
├── terminal/
├── dev/
└── scripts/
    ├── config.json     # Static config: path mappings, category/software/platform rules
    ├── scan.py         # Static script: scan configs and append new manifest entries without overwriting existing ones
    ├── manage.py       # Static script: manage tracked software selection
    ├── backup.py       # Static script: backup local configs to repo
    ├── restore.py      # Static script: restore configs from repo to local
    └── sync.py         # Static script: run repeated sync rounds
```

All scripts are static files that read `manifest.json` and `config.json` to determine which configs to process.

Within this skill repo, the initializer copies:

- `scripts/*.py` and `scripts/config.json` into `~/.synconf/scripts/`
- `assets/repo-template/install.py` into `~/.synconf/install.py`
- If `~/.synconf` already exists but is missing scaffold files such as `README.md`, `install.py`, or runtime scripts, refresh them in place instead of assuming the repo is complete

The `config.json` file contains:
- **category_rules**: Patterns to infer category from path (shell, git, editor, etc.)
- **software_rules**: Patterns to infer software name from path (VS Code, Neovim, Zsh, etc.)
- **platform_rules**: Path patterns to infer platform compatibility (macOS, Windows, Linux)
- **config_registry**: Default config paths to scan, organized by category
- **platform_specific_configs**: OS-specific config paths for macOS, Windows, and Linux

Users can manually edit `config.json` to add custom path mappings or modify detection rules.

## Initialization

Use the bundled initializer when scaffolding or extending the repo:

```bash
python3 <skill-path>/scripts/init_repo.py <selected-paths...>
```

Windows:

```powershell
py -3 <skill-path>/scripts/init_repo.py <selected-paths...>
```

Custom repo dir:

```bash
python3 <skill-path>/scripts/init_repo.py --repo-dir ~/dotfiles <selected-paths...>
```

If the repo already exists and `manifest.json` is present, use the initializer incrementally instead of rebuilding from scratch.

## Script Expectations

All scripts are static files copied by the initializer, not generated at runtime. They read `manifest.json` to determine which configs to process:

- `init_repo.py`: Initialize a new synconf repository with static scripts and configuration (one-time setup)
- `scan.py`: Scan home directory for configs, display results, and auto-populate `manifest.json` with new entries
- `manage.py`: Manage tracked software, including `--list`, interactive `--select`, and explicit `--keep` for user-provided index selections during incremental automation
- `backup.py`: Interactive local-to-repo sync with per-software confirmation, diffs, merge notes, manifest updates, optional `--only` filtering, and automatic in-place refresh of missing repo scaffold files
- `restore.py`: Interactive repo-to-local sync with platform-aware filtering, per-software confirmation, diffs, merge notes, and optional `--repo-dir`
- `sync.py`: Repeated interactive rounds combining backup, optional restore, and Git sync
- `install.py`: One-time installation of all tracked configs to local machine (copies all files without confirmation; use `restore.py` for interactive selection)

When the agent uses these scripts for the user, the final response should include a detailed operational checklist:
- what commands were run
- which software entries were scanned, selected, backed up, restored, skipped, or filtered
- whether `manifest.json` changed
- whether `merge-notes/pending-merges.json` needs review
- a per-entry file operation checklist with source path, target path, target existence before the action, and actual action taken
- which Git commands the user should run next, if any

## Supported Software Examples

- Zsh, Bash, PowerShell
- Git
- Vim, Neovim, VS Code, Cursor, Zed, Sublime Text
- Tmux, Alacritty, Ghostty, Kitty, WezTerm, Windows Terminal
- npm, Cargo, pip, EditorConfig, ESLint, Prettier, Flake8, Pylint

See `scripts/config.json` for the complete list of supported paths and detection rules.

## Safety Notes

- Exclude secrets such as API keys, private SSH keys, private GPG keys, `.env` files with credentials, and netrc credentials.
- Keep `~/.synconf` intact; modify contents in place rather than destroying the repo.
- Prefer explicit merge review over silent overwrites whenever repo and local versions differ.
