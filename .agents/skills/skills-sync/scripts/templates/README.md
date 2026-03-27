# Skills Sync

Scan, export, and restore Claude Code skills across machines.

## Quick Start

### 1. List Available Skills

```bash
python skills_sync.py --scan
```

For JSON output:
```bash
python skills_sync.py --scan --json
```

### 2. Export Skills

Interactive selection:
```bash
python skills_sync.py --scan --output-yaml ./skills.yaml
```

Export all skills:
```bash
python skills_sync.py --scan --output-yaml ./skills.yaml --skills "all"
```

Export specific skills:
```bash
python skills_sync.py --scan --output-yaml ./skills.yaml --skills "skill1,skill2"
```

### 3. Restore Skills

On a new machine, copy this directory and run:
```bash
python restore_skills.py
```

Or restore from a specific YAML file:
```bash
python skills_sync.py --from-yaml ./skills.yaml
```

## Files

- `skills_sync.py` - Main script for scan/export/restore
- `skills_sync_scan.py` - Skill scanning logic
- `skills_sync_yaml.py` - YAML export logic
- `restore_skills.py` - Standalone restore script
- `skills.yaml` - Exported skill metadata (generated)

## YAML Format

```yaml
version: 1
skills:
  - name: skill-name
    source: owner/repo
    source_url: https://github.com/owner/repo.git
    source_type: github
    skill_path: skills/skill-name/SKILL.md
    enabled: true
```

Set `enabled: false` to exclude a skill from restore.

## Requirements

- Python 3.8+
- `npx` and `skills` npm package (for restore)
