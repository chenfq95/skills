---
name: skills-sync
description: >-
  Export and restore Claude Code skills across machines. Use when the user mentions
  "export skills", "backup skills", "sync skills", "restore skills", "migrate skills",
  "generate skills script", or wants to share skill configs across machines.
---

# Skills Sync

Scan installed skills from `~/.agents/skills/`, help user select which skills to export, generate YAML config and Python scripts for restoring on new machines.

## Workflow (Follow These Steps)

### Step 1: Scan and Show Available Skills

Run the scan command and show the results to the user:

```bash
python <skill-path>/scripts/skills_sync.py --scan
```

Display the skill list to user and ask: **"Which skills would you like to export? You can specify skill names (comma-separated) or 'all' for all skills."**

### Step 2: Ask User for Output Directory

Ask user where to export. Suggest current working directory or a subdirectory like `./skills-sync`.

The output directory should be a location the user can commit to git (e.g., their dotfiles repo or a dedicated skills backup repo).

### Step 3: Generate skills.yaml

Based on user's selection, export the skills:

```bash
# If user selected specific skills
python <skill-path>/scripts/skills_sync.py --scan --output-yaml <output-dir>/skills.yaml --skills "skill1,skill2"

# If user selected all
python <skill-path>/scripts/skills_sync.py --scan --output-yaml <output-dir>/skills.yaml --skills "all"
```

Show the generated `skills.yaml` content to user for confirmation.

### Step 4: Export Scripts

Export the complete script toolkit to the same directory:

```bash
python <skill-path>/scripts/export_scripts.py <output-dir>
```

### Step 5: Commit to Git

Help user commit the exported files to git:

```bash
cd <output-dir>
git init  # if not already a git repo
git add .
git commit -m "Add skills-sync configuration"
```

Or if exporting to an existing repo, just add and commit the new files.

### Step 6: Show Summary

Tell user what was exported and how to use:

**Exported files in `<output-dir>/`:**
- `skills.yaml` - skill metadata
- `skills_sync.py` - main script
- `skills_sync_scan.py` - scanning logic
- `skills_sync_yaml.py` - YAML export logic
- `restore_skills.py` - restore script
- `README.md` - usage instructions
- `.gitignore` - git ignore rules

**Usage on new machine:**
```bash
git clone <repo-url>
cd <output-dir>
python restore_skills.py
```

## Command Reference

### skills_sync.py

| Parameter | Description |
|-----------|-------------|
| `--scan` | Scan and list installed non-local skills |
| `--scan --json` | Output scan results as JSON |
| `--scan --output-yaml <path>` | Export skills to YAML file |
| `--skills "name1,name2"` | Specify skill names (use with --output-yaml) |
| `--skills "all"` | Export all skills (use with --output-yaml) |
| `--from-yaml <path>` | Restore skills from YAML file |

### export_scripts.py

```bash
python export_scripts.py <output-dir>
```

### restore_skills.py

```bash
python restore_skills.py
```

## YAML Format

```yaml
version: 1
skills:
  - name: skill-name
    source: owner/repo
    source_url: https://github.com/owner/repo.git
    source_type: github  # github | registry | byted | git
    skill_path: skills/skill-name/SKILL.md
    enabled: true        # set to false to exclude
```

## Notes

- Only scans `~/.agents/skills/` directory
- Local skills (no remote source) are not exported
- Restore requires `npx` and `skills` npm package
- YAML file can be version-controlled and shared
