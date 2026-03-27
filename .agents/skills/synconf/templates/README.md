# Dotfiles

Personal configuration files, managed with copy-based sync.

## Installation

```bash
git clone <your-repo-url> ~/.synconf
cd ~/.synconf
python3 scripts/install.py
```

On Windows, run `py -3 scripts/install.py` from PowerShell.

## Usage

### Backup

```bash
# Scan for configs
python3 scripts/manage.py init --dry-run

# Add selected configs to manifest
python3 scripts/manage.py init --config '{"files":[...]}' --mode merge

# Backup to repo
python3 scripts/backup.py
```

### Restore

```bash
python3 scripts/restore.py
```

### Commands

| Command | Description |
|---------|-------------|
| `manage.py init --config '...' --mode merge` | Add selected configs to manifest |
| `manage.py init --dry-run` | Preview scan without changes |
| `manage.py list` | List tracked software |
| `manage.py select` | Review and remove tracked entries |
| `backup.py` | Backup local → repo |
| `restore.py` | Restore repo → local (with platform filtering) |
| `sync.py` | Interactive backup/restore with Git sync |
| `install.py` | Install all tracked configs |

Tracked inventory is in `manifest.json`. Manual merge notes are in `merge-notes/`.
