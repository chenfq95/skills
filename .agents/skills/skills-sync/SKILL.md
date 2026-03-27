---
name: skills-sync
description: >-
  Scan locally installed skills, export a selected subset to skills.yaml plus a companion restore_skills.py script, and restore directly from YAML when needed. Use when the user mentions
  "export skills", "backup skills", "sync skills", "restore skills", "migrate skills to a new machine",
  "generate skills install script", or wants to list installed skills, share skill configs with others,
  or sync skill environments across multiple machines.
---

# Skills Sync

Scan locally installed skills from `~/.agents/` and `~/.claude/` directories, export the selected non-local skills to a YAML metadata file plus a companion Python restore script, then restore either with that generated script or directly from YAML. Exported metadata includes the download URL so registry-backed skills can still be restored when a short source identifier is not enough.

## Workflow

### 1. Scan, Choose Skills, and Export Artifacts

Run the scan script to discover all installed non-local skills. After scanning, it will prompt the user to choose which skills should be exported, then ask for confirmation before writing the files:

```bash
python <skill-path>/scripts/skills_sync.py --scan --output-yaml ./skills.yaml
```

For non-interactive selection, pass skill names directly:

```bash
python <skill-path>/scripts/skills_sync.py --scan --output-yaml ./skills.yaml --skills "skill1,skill2"
```

This writes both:
- `skills.yaml`
- `restore_skills.py`

### 2. Let User Edit YAML (Optional)

User can manually edit the YAML file to:
- Set `enabled: false` to exclude skills
- Add comments or notes
- Reorder skills
- Share with teammates

### 3. Restore with the Generated Script

```bash
python ./restore_skills.py
```

The generated script reads the sibling `skills.yaml` automatically.

### 4. Restore Directly from YAML

```bash
python <skill-path>/scripts/skills_sync.py --from-yaml ./skills.yaml
```

This remains available if the user wants to restore without the generated script.

### Parameters

| Parameter | Description |
|-----------|-------------|
| `--scan` | Scan and output discovered non-local skills as JSON, including source URLs |
| `--output-yaml <path>` | After scanning, choose non-local skills and export both `skills.yaml` and `restore_skills.py` |
| `--from-yaml <path>` | Restore skills directly from a YAML file |
| `--skills <names>` | Comma-separated skill names to export without prompts |

## YAML Schema

```yaml
version: 1  # Schema version
skills:
  - name: string        # Skill name (required)
    source: string      # Source identifier (e.g., "owner/repo")
    source_url: string  # Download URL or collection URL used for restore fallback
    source_type: string # "github" | "registry" | "byted" | "local"
    skill_path: string  # Path to SKILL.md in source repo
    plugin_name: string # Optional plugin name
    enabled: boolean    # Whether to include in restore (default: true)
```

## Notes

- Scans both `~/.agents/` and `~/.claude/` directories
- Pure local skills are ignored during scan/export because they cannot be auto-restored
- Export writes both `skills.yaml` and a portable `restore_skills.py`
- Byted-hosted skills preserve `source_type: byted` and restore directly with `npx skills add skills.byted.org/... --skill ...`, which matches the CLI's working install path
- Generated YAML includes a note that `source_type: byted` uses the dedicated restore path, and restore logs explicitly announce when that mode is selected
- Other registry skills retain `source_url` so restore can fall back across collection and direct skill install paths when the short `source` identifier is missing, ambiguous, fails, or reports success without actually installing the requested skill
- YAML file can be version-controlled and shared
- Restore requires `npx` and the `skills` npm package
