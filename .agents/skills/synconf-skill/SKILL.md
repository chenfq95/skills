---
name: synconf
description: Sync software configurations across devices using Git on macOS, Linux, and Windows. Use this skill when users want to back up dotfiles, manage configs across multiple machines, migrate to a new computer, or organize shell/editor/tool settings including PowerShell, Windows Terminal, VS Code, Zed, Ghostty, and cross-platform setup flows. Trigger on keywords like dotfiles, config sync, backup settings, new machine setup, sync configs, dotfile manager, chezmoi, stow, PowerShell profile, Windows Terminal config, developer environment migration, and config restore.
---

# SynConf

Manage software configuration backup and restore with a reusable Git repo at `~/.synconf`.

## Core Rules

- All bundled scripts and generated scripts must run on Python 3.8+; avoid Python 3.9+ type syntax such as `list[str]`, `dict[str, object]`, and `Path | None`.
- Always start with environment detection before selection or sync.
- Default to `~/.synconf` and reuse it in place.
- Never delete, recreate, or replace `~/.synconf` itself; preserve `.git`, remotes, branches, and history.
- Use copy-based install and restore flows; do not rely on symlinks.
- Selection is always per software, never per category.
- Persist tracked inventory in `~/.synconf/manifest.json` so later runs can be incremental.

## When To Use

- User wants to back up dotfiles or app configs
- User is setting up a new machine and wants configs restored
- User wants to sync configs across work and personal devices
- User asks about dotfile managers such as `chezmoi`, `stow`, or `yadm`
- User wants cross-platform support for PowerShell, Windows Terminal, VS Code, Cursor, Zed, Ghostty, or AppData-based settings

## Workflow

### 1. Detect Environment

Before any scan, backup, restore, or incremental update, detect and summarize:

- OS
- home directory
- repo path
- whether `~/.synconf` already exists
- whether Python is configured for the current user
- Python executable path
- major config roots that will be scanned, such as `~/.config`, `~/Library/Application Support`, `~/AppData/Roaming`, `~/AppData/Local`, and `~/Documents/PowerShell`
- existing tracked config count from `~/.synconf/manifest.json`, if present

If the repo already exists, frame the run as incremental sync rather than first-time setup.

### 2. Scan Configurations

Run the scanner:

```bash
python3 <skill-path>/scripts/scan_configs.py
```

For machine-readable output:

```bash
python3 <skill-path>/scripts/scan_configs.py --json
```

The scanner should show, for each detected software entry:

- software name
- local config path
- target path inside `~/.synconf`
- whether a repo backup already exists

Categories may be used for display only. They are never selection units.

### 3. Confirm Software Individually

Require the user to confirm each software item one by one.

- Number each software entry
- Keep scan and backup UI consistent
- Never allow selecting an entire category in one step

If five software entries appear under one category, ask five separate confirmation questions.

### 4. Back Up To `~/.synconf`

Back up selected software into `~/.synconf`.

- Preserve home-relative paths in the repo
- Normalize machine-specific home paths in text configs to placeholders like `__SYNCONF_HOME__` and `__SYNCONF_HOME_POSIX__`
- If local and repo versions differ, show detailed diffs before writing
- For directories, show both file-list changes and content diffs for shared files
- Ask the user how the versions should be merged
- Save merge instructions under `~/.synconf/merge-notes/`
- Offer explicit conflict actions: overwrite, skip, manual merge later
- Record manual follow-up items in `~/.synconf/merge-notes/pending-merges.json`
- Skip rewriting configs that already match
- Print a final summary of backed up / unchanged / skipped / manual / missing items

### 5. Restore Or Sync To Local Machine

Support repo-to-local sync with the same interaction quality as backup.

- Scan both repo backup state and the current local environment
- Ask for per-software confirmation before restoring
- Use copy-based writes only
- Render `__SYNCONF_HOME__` and `__SYNCONF_HOME_POSIX__` placeholders to the current machine's home path
- Show diffs before overwriting differing local configs
- Offer overwrite, skip, and manual merge later
- Skip items that already match
- Print a final sync summary

### 6. Support Incremental Sync

Treat `~/.synconf/manifest.json` as the tracked inventory.

- On first run, create it from the selected software set
- On later runs, merge newly selected software into the manifest
- Do not rebuild the repo from scratch when adding new software
- Keep existing tracked entries unless the user explicitly asks to remove one

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
├── manifest.json
├── install.py
├── merge-notes/
├── shell/
├── git/
├── editor/
├── terminal/
├── dev/
└── scripts/
    ├── backup.py
    ├── restore.py
    └── sync.py
```

## Generator Usage

Use the bundled generator when scaffolding or extending the repo:

```bash
python3 <skill-path>/scripts/generate_sync.py <selected-paths...>
```

Windows:

```powershell
py -3 <skill-path>/scripts/generate_sync.py <selected-paths...>
```

Custom repo dir:

```bash
python3 <skill-path>/scripts/generate_sync.py --repo-dir ~/dotfiles <selected-paths...>
```

If the repo already exists and `manifest.json` is present, use the generator incrementally instead of rebuilding from scratch.

## Script Expectations

- `install.py`: copy repo configs into local paths; back up existing local files into `~/.synconf-backup/<timestamp>/...`
- `backup.py`: interactive local-to-repo sync with diffs, merge notes, and incremental manifest-aware behavior
- `restore.py`: interactive repo-to-local sync with diffs, merge notes, and placeholder rendering
- `sync.py`: repeated interactive rounds combining backup, optional restore, and Git sync

## Supported Software Examples

- Zsh, Bash, PowerShell
- Git
- Vim, Neovim, VS Code, Cursor, Zed, Sublime Text
- Tmux, Alacritty, Ghostty, Kitty, WezTerm, Windows Terminal
- npm, Cargo, pip, EditorConfig, ESLint, Prettier, Flake8, Pylint

See `references/common-paths.md` for the detailed path matrix.

## Safety Notes

- Exclude secrets such as API keys, private SSH keys, private GPG keys, `.env` files with credentials, and netrc credentials.
- Keep `~/.synconf` intact; modify contents in place rather than destroying the repo.
- Prefer explicit merge review over silent overwrites whenever repo and local versions differ.
