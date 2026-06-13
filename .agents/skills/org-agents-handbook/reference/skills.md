# Skills System

> This file is the full survey of the **Skills** dimension for [SKILL.md](../SKILL.md).

## 3.1 Capability Comparison

| Dimension | Claude Code | Codex | Cursor | opencode | Trae |
|---|---|---|---|---|---|
| Project-level path | `.claude/skills/` | `.agents/skills/` (along the dir chain) | `.cursor/skills/` + `.agents/skills/` | `.opencode/skills/` + `.claude/skills/` + `.agents/skills/` | `.trae/skills/` |
| User-level path | `~/.claude/skills/` | `~/.agents/skills/` | `~/.cursor/skills/` + `~/.agents/skills/` | `~/.config/opencode/skills/` + `~/.claude/skills/` + `~/.agents/skills/` | `~/.trae/skills/` |
| Admin / system level | — | `/etc/codex/skills/` + built-in | — | — | — |
| Compat path fallback | — | — | `.claude/skills/` + `.codex/skills/` | `.claude/skills/`, `.agents/skills/` (both native, not fallback) | Audit-only: `.agents/`, `.claude/`, `.github/` |
| SKILL.md frontmatter | ✅ full support | ✅ + `agents/openai.yaml` | ✅ (some fields ignored) | ✅ `name`, `description` required; `license` / `compatibility` / `metadata` optional | ✅ |
| Invocation | `/skill-name` or auto | `$skill-name` or auto | `/skill-name` / `@-mention` / auto | Auto via `skill` tool (loaded on-demand) | `/skill-name` or auto |
| `allowed-tools` behavior | ⚠️ pre-approves listed tools in CLI (SDK ignores); not a restriction | — | ❌ ignored | Controlled via `opencode.json` `permission.skill` patterns (`allow` / `deny` / `ask`) | — |
| `disallowed-tools` | ✅ v2.1.152+ | — | ❌ | — | — |
| `context: fork` sub-agent isolation | ✅ | — | — | — | — |
| `!command` injecting shell output | ✅ | — | — | — | — |
| Supports scripts + assets | ✅ | ✅ | ✅ | ✅ | ✅ |
| Per-agent skill override | — | — | — | ✅ `agent.<name>.permission.skill` overrides global | — |

## 3.2 Standard SKILL.md Format

**Minimum viable** (cross-tool compatible):

```markdown
---
name: my-skill
description: One-line purpose and trigger scenarios
---

# My Skill

Detailed steps...
```

**Full Claude Code fields**:

```markdown
---
name: my-skill
description: Task automation skill
allowed-tools: Read, Grep, Glob, Bash(npm test:*)
disallowed-tools: Write, Edit
disable-model-invocation: false
context: fork              # execute in an isolated sub-agent
model: claude-sonnet-4-20250514
---
```

## 3.3 Cross-tool Compatibility Matrix (2026/06)

| Path | Claude Code | Codex | Cursor 2.4+ | opencode | Trae | Copilot | Gemini CLI |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `.agents/skills/` | ❌ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| `.claude/skills/` | ✅ | ❌ | ✅ fallback | ✅ native | ❌ | ✅ | ❌ |
| `.cursor/skills/` | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `.opencode/skills/` | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| `.trae/skills/` | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| `.codex/skills/` | ❌ | ✅ | ✅ fallback | ❌ | ❌ | ❌ | ❌ |

> **`.agents/skills/` has become the de-facto cross-tool standard** — **5 current readers** read it natively (Codex / Cursor 2.4+ / opencode / Copilot / Gemini CLI), up from 4 with the addition of opencode.
> **Claude Code and Trae are the only islands**: Claude only reads `.claude/skills/`, Trae only reads `.trae/skills/`. opencode helpfully reads BOTH `.claude/skills/` AND `.agents/skills/` natively (no fallback semantics), so Claude-shaped repos work without modification on opencode.
> **Nobody reads `.trae/skills/`** except Trae itself.

## 3.4 Monorepo Nested-loading Behavior

The five tools differ greatly in how they scan and scope subdirectory skills — this is the factual basis for the configuration layout in §3.5.

| Dimension | Claude Code | Codex | Cursor | opencode | Trae |
|---|---|---|---|---|---|
| **Scans subdirectories** | ✅ recursive across repo | ✅ walks cwd → repo root, hitting every `.agents/skills/` | ✅ nested `.cursor/skills/` or `.agents/skills/` | ❌ only the top-level skill directories | ❌ only the top-level `.trae/skills/` |
| **Scoping** | All skills loaded into one catalogue; triggered via SKILL.md `paths` / `description` | Walks up the dir chain and discovers each `.agents/skills/` layer; same-name skills are not merged and can both appear in selection | Scoped to the current edited file's directory (same mechanism as nested AGENTS.md) | All discovered skills go into one on-demand catalogue accessed via the `skill` tool; `description` is the only routing signal | All loaded into catalogue, triggered via `description` |
| **Available frontmatter scoping** | `paths: ["packages/frontend/**"]` | no documented `paths` support in SKILL.md; use `agents/openai.yaml` invocation policy for implicit-vs-explicit behavior | Fields are read but **not used to filter visibility**; relies on `description` smart activation | No `paths` field — write trigger keywords into `description` instead, or restrict via `opencode.json` `permission.skill` patterns | `paths` field is experimental |
| **Multi-layer `agents/openai.yaml`** | — | ✅ each layer independent; use `policy.allow_implicit_invocation` per layer | — | — | — |
| **Max nesting depth** | unlimited | unlimited (32 KB quota per layer) | same as nested AGENTS.md (some versions unstable) | n/a (no nesting) | nesting not supported |
| **Same-name conflict** | last loaded wins | not merged; duplicate names can both be exposed for selection | nearer wins | **must be unique** across all 6 search locations — duplicates cause skill to be silently dropped | only one copy |

**Key differences**:

- **Codex / Cursor**: treat skills as "directory-context resources" — **placing a skill next to the submodule makes it discoverable from that subtree** — broadly aligned with nested AGENTS.md behavior
- **Claude Code**: loads all skills flatly; to scope a skill to a submodule you **must** write `paths` in SKILL.md frontmatter
- **opencode**: flat too, BUT reads 6 paths (project+global × `.opencode/skills/` / `.claude/skills/` / `.agents/skills/`). For submodule skills the only viable path is **routing via the submodule AGENTS.md Workflows section + `permission.skill` denylist on root** — same pattern as Trae
- **Trae**: no nested catalogue support — submodule skills are discovered through the submodule AGENTS.md Workflows section, then the agent actively Reads the referenced SKILL.md

## 3.5 Project Config Best Practices

### 3.5.1 Core Idea: Two Tiers (Project Root + Submodule)

Aligned with the AGENTS.md structure (see `agents-md.md` §1.3.1), skills sit in two tiers:

| Tier | Location | Content |
|---|---|---|
| **L1 — Project-root skills** | `.agents/skills/<name>/` | Workflows applicable to the whole project (release, security-audit, scaffold) |
| **L2 — Submodule skills** | `packages/<name>/.agents/skills/<name>/` | Workflows that only one submodule needs (e.g. frontend's `update-design-tokens`) |

**Per-tool auto-scoping behavior**:

- **Codex / Cursor**: a nested skill root under `packages/frontend/.agents/skills/` is discoverable when the agent works inside `packages/frontend/**`; still add the Workflows route for portable behavior
- **Claude Code / Trae / opencode**: do not auto-scope nested `.agents/skills/` by location — use the fallback in §3.5.3

### 3.5.2 Recommended Directory Layout

```
your-repo/
├── AGENTS.md                              # contains Rules Reference + Module Reference Map (see AGENTS.md dimension doc)
│
├── .agents/skills/                        # ★ project-root skills (native: Codex/Cursor/opencode/Copilot/Gemini)
│   ├── deploy-prod/SKILL.md               #   whole-project deploy flow
│   ├── security-audit/SKILL.md            #   whole-repo security audit
│   └── release/
│       ├── SKILL.md
│       ├── scripts/bump-version.sh
│       └── templates/release-notes.md
│
├── .claude/skills/ → ../.agents/skills/   # symlink so Claude also sees root skills
├── .trae/skills/   → ../.agents/skills/   # same for root shared skills only
│
└── packages/
    ├── frontend/
    │   ├── AGENTS.md
    │   └── .agents/skills/                # ★ frontend-only skills
    │       └── update-design-tokens/
    │           ├── SKILL.md               #   frontmatter: paths: packages/frontend/**
    │           └── scripts/sync.ts
    └── backend/
        ├── AGENTS.md
        └── .agents/skills/
            └── run-migration/SKILL.md
```

#### Bridging Claude / Trae to `.agents/skills/` — cross-device compatibility note

Claude only reads `.claude/skills/` and Trae only reads `.trae/skills/`. A repo whose root skills live under `.agents/skills/` therefore needs **some mechanism** to make those skills visible at the two tool-specific paths — symlinks, junctions, recursive copies, build-time generators, or `npx skills add --agent claude/trae` invocations all work.

**This handbook deliberately does not prescribe a single recipe.** The choice depends on constraints that vary by team:

| Dimension | What to consider |
|---|---|
| **OS mix** | Windows symbolic links need admin / Developer Mode; NTFS junctions don't, but only work same-volume / same-NTFS. macOS / Linux symlinks are unconstrained. WSL ↔ native Windows can see each other's links differently. |
| **Git behavior** | `git config core.symlinks` defaults to `false` on Windows (mangles committed symlinks into text files). Committed vs. generated / gitignored links produce very different cross-platform outcomes. |
| **Network / non-NTFS drives** | FAT32 / exFAT / SMB shares / cloud-sync folders do not support junctions or symlinks; falling back to copy is the only option, but copy-based bridges drift on edit and must be refreshed. |
| **Coexistence with `~/.agents/skills/` global installs** | If contributors also use `npx skills add ...` (or any tool that writes into `~/.claude/skills/` / `~/.trae/skills/`), an automated bridge that **deletes existing content** at those paths to re-link will silently destroy globally-installed skills. Any script-based approach **must** distinguish "managed by this repo" from "installed externally" before clobbering. |
| **Maintenance ownership** | Solo developer can do a one-time manual `ln -s`; a team usually needs the bridge regenerated on `clone` / `pull`, which means hooks or `npm install` scripts; CI runners need their own setup. |
| **Edit-loop latency** | Symlinks / junctions reflect SKILL.md edits instantly; copy-based bridges only after the next refresh — affects active skill authoring. |

**Pick a strategy that fits your team's constraints, document it in your repo's README / contributor docs, and verify with [§9.9 of the full report](../../../../docs/org-agents-handbook/full-report.md#99-agent--skill-配置验证清单).** What the agent must see is fixed; how you get there is local to your team.

> ⚠️ Whatever you build, **never blindly delete an existing `.claude/skills/` or `.trae/skills/` directory** to "refresh" the bridge — those paths are also where `npx skills add ...` and similar consumer-side installers land third-party skills. Test for "is this path one I created?" before destructive operations, or limit the bridge to a sentinel subfolder that you own (e.g. `.claude/skills/_repo/`).

### 3.5.3 Skill Discovery and Scoping

The two tiers are discovered very differently.

#### L1 project-root skills: place in root `.agents/skills/`, no AGENTS.md declaration needed

Examples: `deploy-prod`, `security-audit`, `scaffold-new-package`. These skills are inherently globally available; covered tools reach them either through native scanning or through the Claude / Trae symlink bridge.

| Tool | Discovery mechanism |
|---|---|
| Codex / Cursor / opencode / Copilot / Gemini | Native scan of `.agents/skills/` |
| Claude Code | symlink `.claude/skills/ → .agents/skills/` + full-repo recursive scan |
| Trae | symlink `.trae/skills/ → .agents/skills/` + top-level scan |

**The only thing you need to do: write a good SKILL.md `description`** — the agent decides when to invoke just by reading it:

```markdown
---
name: deploy-prod
description: Deploy current branch to production. Use when user asks to ship, release, or push live.
---
```

> No need to re-declare it in AGENTS.md — `description` itself is the trigger protocol. Duplicate declarations only add maintenance cost without adding information.

#### L2 submodule skills: declare the workflow in the submodule AGENTS.md

Example: `packages/frontend/.agents/skills/update-design-tokens/`.

**Recommended approach: declare available skills in a "Workflows" section in the submodule AGENTS.md**

```markdown
# packages/frontend/AGENTS.md

## Workflows
- Sync design tokens: `packages/frontend/.agents/skills/update-design-tokens/`
- React major upgrade: `packages/frontend/.agents/skills/react-major-upgrade/` (must back up lockfile first)
```

How it works end to end:

- **Codex / Cursor**: editing a submodule file → auto-loads the nearest submodule AGENTS.md; nested skill roots under that submodule are also discoverable from the same subtree. The `Workflows` reference remains the portable, documented route.
- **opencode**: editing a submodule file → auto-loads the nearest submodule AGENTS.md → sees the `Workflows` reference → actively Reads SKILL.md and executes
- **Claude / Trae**: root AGENTS.md Module Reference Map directs the agent → agent actively Reads the submodule AGENTS.md → sees the `Workflows` reference → actively Reads SKILL.md and executes

Why submodule skills go through AGENTS.md (vs. the "auto-discover via description" strategy used at L1):

- **Local maintenance**: the submodule owner manages workflows in their own AGENTS.md — no file switching, no syncing root files
- **Submodule-specific trigger context**: the SKILL.md `description` field is space-limited and can't express "submodule-specific preconditions" (e.g. "back up lockfile before upgrade"); the AGENTS.md Workflows section is the natural place for this
- **The portable discovery path for Claude / Trae / opencode**: these tools do not scan nested `.agents/skills/` under submodules, so only AGENTS.md references make the agent actively Read SKILL.md and use it (no catalogue registration required)

**Supporting technical config: solving tool-specific scope issues**

| Tool | Config | Solves |
|---|---|---|
| Codex / Cursor | None | Nearest AGENTS.md auto-loads; nested skill roots are already discoverable from the matching subtree |
| opencode | Use the submodule AGENTS.md `Workflows` section; optionally add `permission.skill` patterns at root | opencode does not scan nested `.agents/skills/`, so the AGENTS.md route is the discovery path |
| Claude Code | Add `paths` to SKILL.md frontmatter | Claude scans every SKILL.md across the repo; without `paths`, backend would see frontend's skill (scope pollution) |
| Trae | None | Agent reads SKILL.md directly via the AGENTS.md reference |

Claude `paths` syntax:

```markdown
---
name: update-design-tokens
description: Sync design tokens from Figma to packages/frontend/src/tokens
paths: ["packages/frontend/**"]            # ← Claude-only; Codex/Cursor ignore
---
```

### 3.5.4 Per-tool Monorepo Notes

| Tool | Key pitfalls / tips |
|---|---|
| **Codex** | Each `.agents/skills/` layer can have its own `agents/openai.yaml`; `policy.allow_implicit_invocation: false` forces explicit invocation for that layer |
| **Cursor** | Nested scoping is unstable in some versions; you can turn off loading of a layer via Settings → Rules, Skills and Subagents; moving a submodule directory causes scope drift |
| **Claude Code** | **Skills without `paths` are globally visible** — submodule skills must include `paths`, otherwise they pollute other submodules' context; on same-name conflicts last loaded wins and submodule overrides root |
| **Trae** | No nested catalogue support; **submodule skills stay under `packages/<name>/.agents/skills/`** and are discovered from that submodule's AGENTS.md Workflows section, then actively Read and executed |

### 3.5.5 General Tips

1. **Process by tier** (see §3.5.3): L1 project-root skills go to root `.agents/skills/` and are auto-discovered via `description`; L2 submodule skills are declared in the submodule AGENTS.md's Workflows section, and Claude additionally needs `paths` to prevent scope pollution
2. **In Trae projects, use symlinks only for root skills** — submodule skills are not aggregated; they are referenced from the owning submodule AGENTS.md and actively Read when needed
3. **Be careful with same-name skills**: avoid duplicate names across submodules. Codex may expose duplicate names for selection, while Cursor / Claude have different override behavior; use unique names plus Claude `paths` for predictable activation
4. **Shared scripts referenced by multiple submodule skills**: put them under root `.agents/skills/<shared>/scripts/`; submodule skills reference them via `../../../.agents/skills/<shared>/scripts/X.sh`

### 3.5.6 Authoring Constraints

1. **`name` must be lowercase with hyphens, ≤ 64 chars** — use the strictest shared convention so every tool accepts the same skill; opencode is the tightest constraint here and silently skips invalid names
2. **SKILL.md body ≤ 500 lines** — anything longer should be pushed to sibling files (`reference.md`, `examples.md`, `scripts/`); large SKILL.md inflates the always-loaded skill catalogue
3. **`disable-model-invocation` usage** (Claude-only field; ignored elsewhere):
   - **Only** set to `true` when the skill is intentionally **slash-only** — e.g. a Commands-flavored manual command migrated to Skills (see [`commands.md`](commands.md) §5.4), or a `/release-tag-v2` style invocation the user must explicitly type
   - **Do NOT** set to `true` defensively for high-risk skills (prod deploy, irreversible operations, etc.). Doing so prevents the agent from even proposing the skill when context matches — the user loses the discovery benefit and falls back to remembering the slug. Instead, for high-risk workflows: (a) narrow `allowed-tools` to read-only + the specific destructive command, and (b) write an explicit confirmation step **inside** the SKILL.md body ("Before proceeding, restate the target environment and wait for the user to type `confirm`"). That keeps auto-discovery on while putting the safety gate where it belongs — in the workflow, not in the routing.
   - **Omit the field** when you want the agent to auto-invoke from ambient context (the common case)
4. **`description` is the trigger protocol** — write in third person, include WHAT the skill does + WHEN (trigger keywords) the agent should invoke it; without trigger keywords, auto-activation is unreliable across all five tools

## 3.6 Per-tool Notes

### Claude Code

- 💡 **Skills = Slash Commands unified**: `.claude/commands/deploy.md` and `.claude/skills/deploy/SKILL.md` both create `/deploy`; skill wins on same name
- ⚠️ `allowed-tools` pre-approves listed tools in CLI but does **not** restrict the skill to only those tools; SDK invocations ignore it and use the main `allowedTools` option
- ✅ **Unique capabilities**: `context: fork` (isolated sub-agent execution), `!command` (inject shell output), `disable-model-invocation` (forbid auto-invocation)
- 💡 `~/.claude/skills/` is globally available, reusable across projects

### Codex

- ✅ **Unique capability**: `agents/openai.yaml` configures UI metadata + invocation policy + MCP dependency declarations
- 💡 `policy.allow_implicit_invocation: false` forces `$skill` explicit invocation only
- 💡 Admin-level `/etc/codex/skills/` supports org-wide distribution
- 💡 Plugin system packages multiple skills + MCP config + assets

### Cursor

- 💡 **Concurrent multi-path**: project `.cursor/skills/` + `.agents/skills/`; same two sets at global level; plus `.claude/skills/` / `.codex/skills/` compat paths
- 💡 Explicit invocation via `/slash` or `@-mention`
- ⚠️ `allowed-tools` frontmatter is **ignored**; permissions go through Cursor's own settings
- 💡 You can disable fallback path loading in Settings → Rules, Skills and Subagents

### opencode

- ✅ **Natively reads `.agents/skills/`, `.claude/skills/`, AND `.opencode/skills/`** — the shared `.agents/skills/` folder works natively on opencode, Codex, Cursor 2.4+, Copilot, and Gemini CLI; Claude Code and Trae need a bridge (see §3.5.2). **opencode is the most compatible reader**.
- 💡 Skills are loaded **on-demand** via a built-in `skill` tool — the SKILL.md body is not always-in-context; the agent reads `name` + `description` first and pulls the full body when triggered
- 💡 Permissions are pattern-based in `opencode.json` `permission.skill`:
  ```json
  { "permission": { "skill": { "*": "allow", "internal-*": "deny", "experimental-*": "ask" } } }
  ```
- 💡 Per-agent override: in `agent.<name>.permission.skill` you can tighten / loosen per agent
- ⚠️ **`name` rules are stricter** than other tools: 1-64 chars, lowercase alphanumeric, single hyphens (no `--`), cannot start/end with `-`, MUST match the parent directory name → SKILL.md is silently skipped on any violation
- ⚠️ **Skill names must be globally unique** across all six search locations — if two skills share a name, opencode picks one and drops the other silently
- 💡 `description` must be 1-1024 chars and is the only routing signal — write WHAT + WHEN, no `paths`
- 💡 Frontmatter accepts `license`, `compatibility`, `metadata` (string-to-string map); unknown keys are silently ignored
- 💡 To disable the skill tool entirely (e.g. for sub-agents that should not auto-load skills), set per-agent

### Trae

- ⚠️ **At runtime only catalogues `.trae/skills/`** — does NOT natively scan `.agents/skills/` / `.claude/skills/`. For root-shared skills, bridge `.trae/skills/ → .agents/skills/` using a strategy that fits your OS mix (see §3.5.2)
- ⚠️ **No nesting support**: doesn't auto-scope by subdirectory; submodule skills should be discovered through the owning submodule AGENTS.md Workflows section and actively Read from `packages/<name>/.agents/skills/`
- 💡 Trae's built-in `Skills-creator` skill can generate new skills via chat
- 💡 In Trae projects, a practical content split is: short rules for constraints, skills for detailed workflows, and MCP for external tool capability
- 💡 International version (`~/.trae/`) vs China version (`~/.trae-cn/`) require separate config
