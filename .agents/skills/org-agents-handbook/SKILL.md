---
name: org-agents-handbook
description: Org-wide handbook for configuring AI coding agents across Claude Code, Codex, Cursor, Trae, and opencode. Use when creating or editing Skills, Rules, Subagents, Hooks, MCP servers, AGENTS.md/CLAUDE.md, slash commands, Cursor Custom Modes, settings, permissions, sandboxes, or approval policies; bootstrapping, auditing, or migrating a repo; or answering where rules should live and how to make behavior portable, enforced, blocked, or sandboxed across the five tools. Applies to files under .agents/, .codex/, .cursor/, .claude/, .opencode/, .trae/, AGENTS.md, CLAUDE.md, opencode.json, MCP configs, hook configs, and tool settings. Contains mandatory cross-tool rules plus routing to reference docs; always apply mandatory rules first, then read the matching reference.
---

# Org Agents Handbook

This skill has **two layers**:

1. **Mandatory Rules** (this file, below) — cross-tool hard constraints the agent MUST apply. These override any per-tool default behavior, including the default scaffolders of Cursor / Trae / Claude / opencode CLI. Apply them every time without re-asking the user.
2. **Reference docs** (`reference/*.md`) — factual standards only: capability matrices, per-tool behavior, decision trees, examples. The reference docs do NOT prescribe; they document. Read them after applying the Mandatory Rules.

**Required behavior**: when the task matches a Mandatory Rule (see §M1 below), apply that rule unconditionally. For everything else, Read the matching reference doc before acting. Never act from memory on per-tool behavior — always verify against the reference doc.

## Routing — which reference to read

| Touching this file / path | Read this reference |
|---|---|
| Root `AGENTS.md`, submodule `AGENTS.md`, `CLAUDE.md`, `~/.config/opencode/AGENTS.md`, `opencode.json` `instructions` array | [`reference/agents-md.md`](reference/agents-md.md) |
| `.cursor/rules/*.mdc`, `.claude/rules/*.md`, `.trae/rules/*.md`, `.agents/rules/*.md` | [`reference/rules.md`](reference/rules.md) |
| Any `SKILL.md`, files under `.agents/skills/`, `.codex/skills/`, `.claude/skills/`, `.cursor/skills/`, `.opencode/skills/`, `.trae/skills/` | [`reference/skills.md`](reference/skills.md) |
| `.claude/commands/*.md`, `.opencode/commands/*.md`, any slash-command file | [`reference/commands.md`](reference/commands.md) |
| `.claude/agents/*.md`, `.opencode/agents/*.md`, Cursor Custom Modes JSON, `opencode.json` `agent` block | [`reference/subagents.md`](reference/subagents.md) |
| `.claude/hooks/`, `.claude/settings.json` `hooks` block, `~/.codex/hooks.json`, `~/.codex/config.toml [hooks]`, plugin-bundled `hooks/hooks.json`, `requirements.toml`, `.opencode/plugins/*.ts`, `.cursor/hooks.json` | [`reference/hooks.md`](reference/hooks.md) |
| `.claude/settings.json`, `.claude/settings.local.json`, `.codex/config.toml` (non-MCP keys), `.cursor/environment.json`, `opencode.json` (non-MCP keys), any `permissions` / `sandbox` / `approval_policy` field | [`reference/settings.md`](reference/settings.md) |
| `.mcp.json`, `.codex/config.toml` (mcp_servers), `.cursor/mcp.json`, `.trae/mcp.json`, `opencode.json` `mcp` block, user-level MCP configs | [`reference/mcp.md`](reference/mcp.md) |

## Multi-dimension tasks — read more than one

| Task | Read |
|---|---|
| **Create / scaffold a new Skill (in any IDE)** | **§M1 (mandatory) first**, then `skills.md` for details |
| Add a new submodule (AGENTS.md + skills) | `agents-md.md` + `skills.md` + §M1 for any new skills |
| Migrate per-tool rules into AGENTS.md / Skills | `rules.md` + `agents-md.md` + `skills.md` |
| Migrate legacy `.claude/commands/` to Skills | `commands.md` + `skills.md` |
| Decide between Skill, Subagent, or Command for a new capability | `skills.md` + `subagents.md` + `commands.md` |
| Enforce "no `rm -rf`, no `sudo`" across all five tools | `hooks.md` + `settings.md` |
| Set up safe defaults (sandbox + approval policy + allowlists) | `settings.md` + `hooks.md` |
| Bootstrap a fresh monorepo for all five tools | all eight |
| User asks "why is it designed this way?" | The Best Practices section in the matching dimension doc |

## Workflow

1. **Check the Mandatory Rules section first** (§M1) — if the task matches one, apply that rule unconditionally before doing anything else
2. **Identify the dimension** from the routing table above
3. **Read the matching reference doc** (each is self-contained — one is usually enough)
4. **Apply the decision tree + critical rules** from that doc
5. **Do not invent new mechanisms** — if a need is not covered, ask the user before extending

## Mandatory Rules (non-negotiable, apply without asking)

These are hard rules the handbook enforces across all five tools. Apply them every time the matching trigger fires, regardless of which IDE the user is in, what the IDE's scaffolder defaulted to, or what the user's request literally said. If a rule cannot be met because the user explicitly requested a tool-specific capability, **record the deviation in the artifact itself** (e.g. a comment in the SKILL.md body) so future readers know the artifact is not fully portable.

> **Scope**: these rules apply to **repo-owned skills** — skills the user is creating, scaffolding, or editing as part of a project's own source tree (root `.agents/skills/` or submodule `packages/<m>/.agents/skills/`). They do **not** apply to **consumer-side installs** of third-party skills via `npx skills add ...` or any equivalent that drops a skill folder into `~/.agents/skills/<name>/` globally — those skills are vendored content; you only consume them, you don't reshape them. In particular §M1.6 and §M1.7 below are monorepo-side concerns; consumer installs skip both.

### §M1. Creating a new Skill — cross-tool pre-flight

**Trigger**: any task of the form "create / add / scaffold a new skill", regardless of whether the user is in Cursor, Claude, Codex, Trae, or opencode, and regardless of where the IDE's `/skill new` command (or equivalent) defaulted to.

1. **Path — `.agents/skills/` only**:
   - **Root skill**: `.agents/skills/<name>/SKILL.md`
   - **Submodule skill**: `packages/<m>/.agents/skills/<name>/SKILL.md`
   - **Never** create the skill under `.cursor/skills/`, `.claude/skills/`, `.codex/skills/`, `.opencode/skills/`, or `.trae/skills/` — those are tool-specific paths that break cross-tool reuse. If the IDE scaffolded the folder under a tool-specific path, **move the folder to `.agents/skills/<name>/` before adding content**.
   - **Why**: `.agents/skills/` is the only path read natively by ≥ 5 current readers (Codex / Cursor 2.4+ / opencode / Copilot / Gemini); Claude / Trae need to be bridged (see §M1.6). See [`reference/skills.md`](reference/skills.md) §3.3 for the source-of-truth matrix.

2. **`name` rule — opencode strictness is the floor** (so all five tools accept the same file):
   - `^[a-z0-9]+(-[a-z0-9]+)*$` — lowercase a–z and digits only, single hyphens, no `_` / `.` / `--`, no leading or trailing `-`
   - **1–64 characters**
   - **Must equal the parent directory name** (`name: deploy-prod` ⇒ folder `deploy-prod/`)
   - **Why**: opencode silently drops the skill on any name-rule violation; **and on Claude / Codex / Cursor / Trae the activation slug is derived from the folder name** when `name` differs from the directory, so frontmatter `name` is effectively meaningless unless it matches. Enforcing `name === parent directory` is the only writing convention that produces the same skill identity on all five tools.

3. **`description` rule**:
   - **1–1024 characters** (opencode upper bound)
   - Must contain both **WHAT** the skill does and **WHEN** the agent should invoke it (concrete trigger keywords / scenarios) — without the WHEN clause, auto-activation is unreliable on every tool that uses `description` as the routing signal (Claude / Codex / Cursor / opencode / Trae)
   - Write in third person
   - **Why**: `description` is the only common auto-activation signal across the five covered tools. opencode in particular has **no other** routing signal (no `paths`, no nesting); a vague description means the skill is dead code there.

4. **Portable frontmatter only** by default. Add tool-specific fields **only** when the user explicitly asks for that tool's capability; when you do, note the limitation in the SKILL.md body.

   | Field | Who actually honors it | Add unconditionally? |
   |---|---|---|
   | `name` | all 5 | ✅ required |
   | `description` | all 5 (auto-activation signal) | ✅ required |
   | `allowed-tools` | Claude pre-approves in CLI (SDK ignores); Cursor / Trae ignore; opencode uses `opencode.json` `permission.skill` patterns instead | ⚠️ Claude-leaning — document if used |
   | `disallowed-tools` | Claude only (v2.1.152+) | ❌ Claude-only |
   | `disable-model-invocation` | Claude only | ⚠️ **Only** set to `true` when the skill is intentionally **slash-only** and the agent must not proactively suggest it (e.g. a Commands-style manual command migrated to Skills, see [`reference/commands.md`](reference/commands.md) §5.4). **Never set "for safety"** — for high-risk skills, instead narrow `allowed-tools` and add a confirmation step **inside** the SKILL.md body, so the agent can still surface the skill when relevant. Setting this defensively silently disables auto-activation on every tool that honors it. |
   | `context: fork` | Claude only (isolated sub-agent execution) | ❌ Claude-only |
   | `paths` | Claude only (subtree scoping) | **Submodule skills**: ✅ required (see §M1.7). **Root skills**: ❌ omit — root skills should be globally visible by design |
   | `model` | Claude / Codex / opencode read; Cursor / Trae ignore | ⚠️ optional |
   | `license` / `compatibility` / `metadata` | opencode only (unknown fields silently ignored elsewhere) | ❌ opencode-only |

5. **Body length ≤ 500 lines** — anything larger MUST be split into sibling files (`reference.md`, `examples.md`, `scripts/`). Oversized SKILL.md bloats the always-loaded catalogue and degrades activation on every tool.

6. **Claude / Trae visibility for repo-owned root skills** — Claude only reads `.claude/skills/` and Trae only reads `.trae/skills/`, so a repo that publishes skills under `.agents/skills/` must bridge those two paths back to `.agents/skills/` for Claude / Trae users. **Cross-device compatibility caveats apply** — symlinks behave differently across Windows / macOS / Linux / WSL / network drives, Git treats committed symlinks inconsistently across platforms, and the bridge interacts with whatever the user installed locally (e.g. via `npx skills add`) in their `~/.claude/skills/` and `~/.trae/skills/`. **Pick a bridging strategy that fits your team's OS mix and contributor workflow; this handbook deliberately does not prescribe one.** See [`reference/skills.md`](reference/skills.md) §3.5.2 for the trade-offs to weigh.

7. **Submodule skills also need two extra things** (because nested `.agents/skills/` discovery is not portable across all covered tools):
   - Add a `paths: ["packages/<m>/**"]` line to the SKILL.md frontmatter (Claude-only — prevents scope pollution into other submodules)
   - Add an entry under `## Workflows` in the **submodule's** `AGENTS.md` so every tool has a consistent route to the SKILL.md when working in that submodule

**Verification before declaring the skill done**: every one of the seven items above is satisfied (or its deviation is documented in the SKILL.md body).

## Reference index

- [`reference/agents-md.md`](reference/agents-md.md) — two-tier × two-slot structure (project root + submodule, each split into `AGENTS.md` + `.agents/`), routing tables, Codex 32 KiB limit, per-tool bridging
- [`reference/rules.md`](reference/rules.md) — when to keep per-tool rules, migration path to AGENTS.md / Skills
- [`reference/skills.md`](reference/skills.md) — project-root vs submodule skills, discovery, cross-device compatibility notes for bridging Claude / Trae to `.agents/skills/` (no prescribed recipe), `paths` for Claude
- [`reference/commands.md`](reference/commands.md) — slash commands (deprecated on all five tools by this handbook — including opencode), migration recipes from `.claude/commands/` and `.opencode/commands/` to `.agents/skills/`, the one `agent:` edge case
- [`reference/subagents.md`](reference/subagents.md) — `.claude/agents/`, `.opencode/agents/`, Cursor Custom Modes; context isolation, when to use vs Skills, no cross-tool standard
- [`reference/hooks.md`](reference/hooks.md) — native hooks on **Claude / Codex (Claude-compatible) / Cursor / opencode**; Trae still has none. Events (PreToolUse / PostToolUse / UserPromptSubmit / Stop / Codex's PermissionRequest), exit-code contract, single-script-two-runtimes pattern (Claude + Codex), opencode JS/TS plugins, defense in depth with git hooks (only layer for Trae)
- [`reference/settings.md`](reference/settings.md) — permissions (Claude), sandbox + approval (Codex), Auto Mode + allowlist (Cursor), `.cursor/environment.json` for background agents, project vs user vs local layering
- [`reference/mcp.md`](reference/mcp.md) — project vs user level, secret handling, per-tool config formats

> **Tools covered**: Claude Code / OpenAI Codex / Cursor / Trae / opencode
> **Last updated**: 2026/06
