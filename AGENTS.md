# AGENTS.md

This repository stores agent skills and their supporting long-form documentation. Top-level layout:

| Path | Purpose | Agent surface? |
|---|---|---|
| `.agents/skills/<name>/` | Skills — actionable, agent-facing (auto-discovered by 5 tools via SKILL.md `description`) | ✅ |
| `docs/<topic>/` | Long-form research / reports backing a skill (too verbose for SKILL.md's 500-line cap) | ❌ human-readable only |
| `README.md` | Install / update / uninstall instructions for end users | ❌ |
| `AGENTS.md` (this file) | Top-level agent guidance | ✅ (where supported) |

Three skills live here:

| Skill | Path | Shape | Backing doc |
|---|---|---|---|
| `synconf` | `.agents/skills/synconf/` | Python scripts + templates + evals | — |
| `skills-sync` | `.agents/skills/skills-sync/` | Python scripts | — |
| `org-agents-handbook` | `.agents/skills/org-agents-handbook/` | docs-only (`SKILL.md` + `reference/*.md`) | [`docs/org-agents-handbook/full-report.md`](docs/org-agents-handbook/full-report.md) |

Each skill's `SKILL.md` is the source of truth — read it before changing the skill's behavior. There is no root `pyproject.toml`, `pytest.ini`, `package.json`, or `Makefile`, and no `.cursor/rules/`, `.cursorrules`, or `.github/copilot-instructions.md`. Treat this file as the top-level guidance.

## Mandatory rules for new skills

`org-agents-handbook` is the cross-tool reference for configuring AI coding agents — **its rules apply to this repo's own skills too**. When adding any skill (existing or new), follow `org-agents-handbook/SKILL.md` §M1:

- Path: `.agents/skills/<name>/SKILL.md` (never under `.cursor/`, `.claude/`, `.codex/`, `.opencode/`, or `.trae/`)
- `name`: matches `^[a-z0-9]+(-[a-z0-9]+)*$`, 1–64 chars, equal to the parent directory name
- `description`: 1–1024 chars, third person, states both WHAT it does and WHEN it activates
- Frontmatter stays portable; tool-specific fields only when required, and document the deviation in the body
- Body ≤ 500 lines; overflow goes into sibling files (e.g. `reference/*.md`)

## Repo priorities

- Keep changes small and targeted; reuse existing structure over new frameworks
- Treat `SKILL.md` wording changes as product changes
- Keep scripts, docs (`SKILL.md`, `templates/README.md`), and `evals/evals.json` aligned when behavior changes
- For `org-agents-handbook` edits, re-check the routing tables and reference index in its `SKILL.md`; if a §M1 rule changes, mirror it in this file

## `docs/` folder

Long-form documentation that **supplements** skills but does NOT belong in any `SKILL.md` body (which is capped at 500 lines per `org-agents-handbook/SKILL.md` §M1). Currently:

| File | Backs which skill | Purpose |
|---|---|---|
| `docs/org-agents-handbook/full-report.md` | `.agents/skills/org-agents-handbook/` | Full ~2700-line cross-tool research report (capability matrices, decision trees, per-tool deep dives, verification recipes). The skill's `SKILL.md` is the actionable surface; this report is the evidence base. |

Rules for `docs/`:

- **Human-facing only** — no tool reads it natively; no SKILL.md frontmatter, no scripts, no auto-activation
- **One subdirectory per topic**, mirroring the matching `.agents/skills/<name>/` when applicable (e.g. `docs/org-agents-handbook/` ↔ `.agents/skills/org-agents-handbook/`)
- **Bidirectional consistency** — when a SKILL.md / `reference/*.md` rule changes the underlying fact, update the matching `docs/` file too (and vice versa); a single commit should cover both
- Do **not** move agent-facing content here to dodge size limits — split into `reference/*.md` instead; `docs/` is for long-form prose, research notes, and report-style write-ups
- Do **not** add `docs/` paths to skill routing tables — agents reach `docs/` only when a human or AGENTS.md explicitly links to them

## Test & validate

| Change | Run |
|---|---|
| Any Python edit | `python -m compileall .agents/skills` |
| `synconf/scripts/*.py` or `config.json` behavior | `python .agents/skills/synconf/scripts/tests.py` |
| Any CLI surface change | the relevant `--help` (e.g. `python .agents/skills/synconf/scripts/manage.py --help`) |
| `org-agents-handbook` docs | re-check routing-table links resolve; `SKILL.md` body ≤ 500 lines |
| `docs/<topic>/*.md` edits | review for consistency with the backing skill's `SKILL.md` + `reference/*.md`; no compile/test needed |
| Docs-only edits elsewhere | review for consistency; no compile/test needed |

Single test: `python -c "import sys; sys.path.insert(0, '.agents/skills/synconf/scripts'); import tests; tests.test_backup_conflict_detection()"`. Available tests are defined at module level in `synconf/scripts/tests.py` — run any of them by name.

CLIs available for `--help` checks: `synconf/scripts/{manage,backup,restore,sync,init_repo}.py`, `skills-sync/scripts/skills_sync.py`.

## Synconf runtime behavior — preserve

- Default repo path is `~/.synconf`; reuse an existing one, never delete-and-recreate
- Sync is **copy-based**, not symlink-based
- Selection is **per software**, not per category
- Tracked inventory in `manifest.json`; local-only scan state in `.state.json`
- Repo backups use `category/software/...` layout
- Home path normalization uses `__SYNCONF_HOME__` and `__SYNCONF_HOME_POSIX__`
- Pending manual merges live in `merge-notes/pending-merges.json`
- Conflict actions are always `overwrite | skip | manual | merge`; show diffs before overwriting

## Org-agents-handbook conventions

- Layout is fixed: `SKILL.md` (≤ 500 lines) + `reference/*.md` (one file per dimension: agents-md, rules, skills, commands, subagents, hooks, settings, mcp)
- Docs-only — do not introduce scripts, templates, or evals
- New reference docs must be added to both the routing table and reference index in `SKILL.md`
- Each reference doc is self-contained (readers load one at a time)
- The tools-covered list (Claude Code / Codex / Cursor / Trae / opencode) is canonical — do not silently expand or shrink
- The long-form research report lives at [`docs/org-agents-handbook/full-report.md`](docs/org-agents-handbook/full-report.md), **not** inside the skill — keep `SKILL.md` + `reference/*.md` actionable and concise; push prose, justification, and deep dives to the report. When the report changes a fact that affects a §M1 rule, mirror the change in `SKILL.md` (and in this file's Mandatory rules section)

## Code style (Python)

Match the existing style in `.agents/skills/synconf/scripts/*.py` and `.agents/skills/skills-sync/scripts/*.py`.

- **Target Python 3.8+** — no `list[str]`, `dict[str, Any]`, or `X | None` syntax; use `typing.List/Dict/Optional/Tuple/Sequence/Mapping`
- **Standard library only** unless a dependency is clearly justified; workspace Python is 3.12 but code stays 3.8-compatible
- `from pathlib import Path`; group stdlib imports before local; no import-time side effects beyond constants
- 4-space indent, triple-double-quoted docstrings, f-strings for output, ASCII unless Unicode is already established
- Type-hint new/modified functions; `TypedDict` for JSON payloads, `@dataclass` for small records
- Names: `lower_snake_case.py`, `snake_case` funcs/vars, `PascalCase` classes, `UPPER_SNAKE_CASE` constants; keep user-facing labels human-readable (`VS Code`, `Windows Terminal`)
- Narrow exceptions (`ValueError`, `OSError`, `PermissionError`, `UnicodeDecodeError`, `json.JSONDecodeError`); never swallow silently; use `parser.error(...)` for bad CLI args
- Be careful with `unlink()` / `shutil.rmtree()` — only remove tracked/generated targets; preserve `.git`, remotes, history
- Prefer `subprocess.run(..., check=False)` and inspect `returncode`
- Comments only for non-obvious intent — prefer better names or helper extraction
- Move shared logic into `common.py` instead of duplicating

## Security

- Do not broaden scanning to high-risk credential stores by default
- Exclude secrets, private keys, `.env` files, and credential dumps from tracked content
- Be especially careful around `.aws`, `.docker`, `.kube`, and GitHub CLI config paths
- Do not sync editor caches or transient runtime files

## Environment

- `python` is available; `py -3` is not
- Update this file when commands, runtime behavior, or workflow expectations change
