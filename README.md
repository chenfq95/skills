# Skills

A collection of agent skills for AI coding tools (Claude Code, Codex, Cursor, Trae, opencode).
All skills live under `.agents/skills/<name>/SKILL.md` and follow the cross-tool conventions in
[`org-agents-handbook/SKILL.md`](.agents/skills/org-agents-handbook/SKILL.md) §M1.

## Skills

| Skill | Path | Purpose |
|---|---|---|
| [`synconf`](.agents/skills/synconf/SKILL.md) | `.agents/skills/synconf/` | Sync dotfiles and software configs across macOS / Linux / Windows using a Git-backed `~/.synconf` repo (copy-based, per-software selection). |
| [`skills-sync`](.agents/skills/skills-sync/SKILL.md) | `.agents/skills/skills-sync/` | Export installed skills to `skills.yaml` and restore them on another machine via `npx skills`. |
| [`org-agents-handbook`](.agents/skills/org-agents-handbook/SKILL.md) | `.agents/skills/org-agents-handbook/` | Docs-only cross-tool handbook for configuring Skills / Rules / Subagents / Hooks / MCP across Claude Code, Codex, Cursor, Trae, and opencode. |

Each skill's `SKILL.md` is the source of truth — read it before changing the skill's behavior.

## Install

Requires Node.js (for `npx`). The `skills` CLI installs into `~/.agents/skills/<name>/`, which all
five covered tools can read (Claude Code / Codex / Cursor 2.4+ / opencode / Trae bridged via symlink).

### Install one skill

```bash
npx skills add chenfq95/skills -g --skill synconf
npx skills add chenfq95/skills -g --skill skills-sync
npx skills add chenfq95/skills -g --skill org-agents-handbook
```

### Install the whole collection

```bash
npx skills collection add https://github.com/chenfq95/skills.git -g
```

### Manual install (no npm)

```bash
git clone https://github.com/chenfq95/skills.git ~/code/skills
mkdir -p ~/.agents/skills
ln -s ~/code/skills/.agents/skills/synconf             ~/.agents/skills/synconf
ln -s ~/code/skills/.agents/skills/skills-sync         ~/.agents/skills/skills-sync
ln -s ~/code/skills/.agents/skills/org-agents-handbook ~/.agents/skills/org-agents-handbook
```

On Windows, replace `ln -s` with directory junctions (`mklink /J`) since symlinks require admin.

## Update

### Update via `npx skills`

```bash
npx skills add chenfq95/skills -g --skill <name>
```

Re-running `add` fetches the latest version and overwrites the installed copy. To update everything
that was originally installed from this repo:

```bash
npx skills collection add https://github.com/chenfq95/skills.git -g
```

### Update via manual install

```bash
git -C ~/code/skills pull --ff-only
```

The symlinks under `~/.agents/skills/` will pick up the new content automatically.

### Update `synconf`'s deployed scripts

`synconf` deploys its scripts into a separate user repo at `~/.synconf`. Updating the skill itself
does **not** update that repo — run the bundled updater from the skill source:

```bash
python3 ~/.agents/skills/synconf/scripts/update_scripts.py --dry-run   # preview
python3 ~/.agents/skills/synconf/scripts/update_scripts.py             # apply
git -C ~/.synconf add -A && git -C ~/.synconf commit -m "Update synconf scripts"
```

See [`synconf/SKILL.md` → Updating Scripts](.agents/skills/synconf/SKILL.md#updating-scripts) for the
full option list (`--force`, `--include-templates`).

## Uninstall

```bash
npx skills remove <name> -g
```

Or, for a manual install, delete the symlink under `~/.agents/skills/`.

## Contributing

- Skill layout, naming, and frontmatter rules: [`org-agents-handbook/SKILL.md` §M1](.agents/skills/org-agents-handbook/SKILL.md)
- Repo-wide build / test / lint commands and code style: [`AGENTS.md`](AGENTS.md)

## License

[MIT](LICENSE)
