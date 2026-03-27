---
name: synconf
description: Sync software configurations across devices using Git on macOS, Linux, and Windows. Use this skill when users want to back up dotfiles, manage configs across multiple machines, migrate to a new computer, or organize shell/editor/tool settings including PowerShell, Windows Terminal, VS Code, Zed, Ghostty, and cross-platform setup flows. Trigger on keywords like dotfiles, config sync, backup settings, new machine setup, sync configs, dotfile manager, chezmoi, stow, PowerShell profile, Windows Terminal config, developer environment migration, and config restore.
---

# SynConf

Manage software configuration backup and restore with a reusable Git repo at `~/.synconf`.

## Core Rules

- Python 3.8+ compatible (avoid `list[str]`, `dict[str, Any]`, `Path | None`)
- Default to `~/.synconf`, reuse in place, never delete/recreate
- Copy-based sync, no symlinks
- Per-software selection, never per-category
- Pass `--repo-dir ~/.synconf` when running from skill source tree
- Do not scan high-risk credential stores like `.aws`, `.docker`, `.kube`, or `gh` config by default
- During scan, only consider config paths supported by the current OS
- Store backups inside the repo as `category/software/...` instead of mirroring raw system paths

## Quick Start

**Backup:**
```bash
python3 scripts/init_repo.py              # One-time setup
python3 -c "from scripts.common import run_scan; import json; print(json.dumps({'files': run_scan()}, ensure_ascii=False))"
python3 scripts/manage.py --repo-dir ~/.synconf -y init --config '<selected-json>' --mode merge
python3 scripts/backup.py --repo-dir ~/.synconf -y --last-selection
git -C ~/.synconf add -A && git -C ~/.synconf commit -m "Backup"
```

**Note:** The `-y` flag must appear **before** the subcommand (e.g., `-y init`, `-y prune`), not after.

**Restore:**
```bash
git clone <your-repo-url> ~/.synconf
python3 ~/.synconf/scripts/restore.py
```

## Commands

| Command | Description |
|---------|-------------|
| `manage.py -y init --config '{"files":[...]}' --mode merge` | Write a selected subset into the manifest (non-interactive) |
| `manage.py init --dry-run` | Preview scan without changes |
| `manage.py list` | List tracked software |
| `manage.py select` | Review already tracked entries and remove ones you no longer want |
| `manage.py -y prune 2,4` | Remove entries by index (also deletes repo backups) |
| `backup.py -y` | Backup local → repo (non-interactive) |
| `backup.py --only .zshrc` | Backup specific entries only |
| `backup.py -y --last-selection` | Backup only the subset selected by the latest `manage.py init` |
| `restore.py` | Restore repo → local with platform filtering |
| `sync.py` | Multi-round interactive backup/restore |

All commands support `-y` for non-interactive mode, **except `select`** which requires explicit user choice. The `-y` flag must appear before the subcommand.

## Agent Execution Flow

1. Scan the machine for syncable software configs:
   ```bash
   python3 -c "from scripts.common import run_scan; import json; print(json.dumps({'files': run_scan()}, ensure_ascii=False))"
   ```
2. Show a numbered list to the user and ask which entries to include (by index)
3. Build a JSON payload containing only the confirmed entries
4. Run `manage.py --repo-dir ~/.synconf -y init --config '<selected-json>' --mode merge`
5. Run `backup.py --repo-dir ~/.synconf -y --last-selection` to back up exactly that subset
6. Print checklist: completed actions, pending merges, next Git commands

When operating from the skill source tree, always use `from scripts.common import run_scan` (not `from common import ...`).

**Important:** The `-y` flag must be placed **before** the subcommand to work correctly.

`manage.py init --select ...` remains available as a lower-level script shortcut, but agents should prefer the JSON-to-`--config` flow so the selected entries are explicit in the command invocation.

## Repository Layout

```
~/.synconf/
├── manifest.json       # Tracked software inventory
├── install.py          # One-time bulk install
├── merge-notes/        # Conflict resolution notes
├── shell/git/editor/terminal/dev/  # Config backups grouped as category/software
└── scripts/
    ├── config.json     # Path mappings and detection rules
    ├── common.py       # Shared utilities
    ├── manage.py       # init/list/select/prune
    ├── backup.py       # Local → repo
    ├── restore.py      # Repo → local
    └── sync.py         # Multi-round sync
```

**Directory structure rule:** Both files and directories preserve their original names under `category/software/`. For example:
- `~/.vimrc` (file) → `editor/vim/.vimrc`
- `~/.vim` (directory) → `editor/vim/.vim/`

This prevents conflicts when a software has both a config file and a config directory.

## Supported Software

Zsh, Bash, PowerShell, Git, Vim, Neovim, VS Code, Cursor, Zed, Sublime Text, Tmux, Alacritty, Ghostty, Kitty, WezTerm, Windows Terminal, npm, Cargo, pip, EditorConfig, ESLint, Prettier

See `scripts/config.json` for complete path mappings.

Typical repo targets look like `editor/vs-code/windows`, `editor/zed/windows/settings.json`, and `git/git/.gitconfig`.

For Zed specifically, prefer the user config locations that differ by platform:

- macOS/Linux: `~/.config/zed/settings.json` and `~/.config/zed/keymap.json`
- Windows: `~/AppData/Roaming/Zed/settings.json` and `~/AppData/Roaming/Zed/keymap.json`

## Safety

- Exclude secrets (API keys, SSH/GPG private keys, `.env`, netrc)
- Skip scanning high-risk credential directories such as `.aws`, `.docker`, `.kube`, and `~/.config/gh` by default
- Auto-exclude editor cache directories during backup: History, Cache, CachedData, workspaceStorage, globalStorage, logs, etc.
- Never overwrite without showing diff first
- Pending merges tracked in `merge-notes/pending-merges.json`
