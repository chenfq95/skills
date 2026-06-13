# Rules System

> This file is the full survey of the **Rules** dimension for [SKILL.md](../SKILL.md).

## 2.1 Capability Comparison

| Dimension | Claude Code | Codex | Cursor | opencode | Trae |
|---|---|---|---|---|---|
| Dedicated Rules system | ✅ | ❌ | ✅ | ❌ (uses AGENTS.md only) | ✅ |
| Project-level path | `.claude/rules/` | — | `.cursor/rules/` | — (AGENTS.md is the rules file) | `.trae/rules/` |
| User-level path | `~/.claude/rules/` | — | UI config + Team dashboard | — | `~/.trae/rules/` |
| Extension | `.md` | — | `.mdc` (`.md` is ignored) | — | `.md` |
| frontmatter fields | `paths` | — | `description` / `globs` / `alwaysApply` | — (use `instructions` array in `opencode.json` to attach extra rule files) | configured in IDE panel |
| Always-on | ✅ when `paths` is absent | — | `alwaysApply: true` | ✅ (AGENTS.md is always loaded) | "always-on" mode |
| Path matching | ✅ `paths: [globs]` | — | ✅ `globs: [...]` | ❌ (no path-scoped rules concept) | "applies to specific files" |
| AI smart activation | ❌ | — | ✅ via description | ❌ | ✅ via description |
| Manual trigger | ❌ | — | ✅ `@rule-name` | ❌ | ✅ `#Rule` (highest priority) |
| Subdirectory recursion | ✅ | — | ✅ | ✅ via nested AGENTS.md walk | ✅ |
| Trigger timing | when Claude **Reads** a matching file | — | matching file enters context | always-on (or per-agent override) | on edit / Read |
| Reads `.agents/rules/` | ❌ | — | ❌ | ❌ (not part of opencode's lookup) | ❌ |

## 2.2 Monorepo Support

All Rules-supporting tools recursively scan subdirectories, but **none** auto-scope by location like AGENTS.md does — you must explicitly configure `path` / `glob` / `scope`:

```
.cursor/rules/
├── frontend/
│   └── react.mdc          # globs: ["packages/frontend/**/*.tsx"]
└── backend/
    └── api.mdc            # globs: ["packages/backend/**"]
```

## 2.3 Project Config Best Practices

> **🎯 Core strategy: drop per-tool Rules systems and route content via AGENTS.md**
>
> The Rules-supporting tools (Claude / Cursor / Trae) differ in path, frontmatter fields, and activation behavior (see §2.1), and the core mechanisms are already frozen — they will never converge. Codex and opencode have no separate Rules system at all (they put everything in AGENTS.md). **The optimal solution for production projects is to bypass per-tool Rules entirely**, splitting content into the four buckets below:
>
> | Content type | Migrate to | Cross-tool compatibility |
> |---|---|---|
> | **Project-wide hard constraints** (do-not-touch, naming, commit format) | **Root `AGENTS.md`** body | ✅ all five tools |
> | **Project-level rules** (applicable across multiple submodules, e.g. coding style, security baseline) | **Root `.agents/rules/*.md`** (referenced from root AGENTS.md Rules Reference) | ⚠️ no native auto-load, relies on AGENTS.md routing |
> | **Submodule-only rules** (e.g. frontend React conventions) | **`packages/<name>/.agents/rules/*.md`** (referenced from `packages/<name>/AGENTS.md`) | ✅ Codex / Cursor / opencode auto-load submodule AGENTS.md + Claude / Trae via root Module Reference Map |
> | **Triggerable workflows / SOPs** (release, audit, scaffold) | **`.agents/skills/<name>/SKILL.md`** at the appropriate tier | ✅ root-level skills auto-discovered by 5 native readers; Claude / Trae via symlink; submodule skills routed via Workflows table |
>
> Submodule rule files live in `packages/<name>/.agents/rules/`, mirroring the root `.agents/rules/` layout. The submodule AGENTS.md stays slim — it only holds the submodule's stack info + a Rules Reference table that points to the local `.agents/rules/*.md` files.

### Decision tree: where should a rule live?

```
You want to write a rule / workflow / piece of knowledge
        ↓
Must the agent always obey it? (naming, commit format, do-not-touch)
        ├── Yes → write into root AGENTS.md body
        └── No ↓
            Is it a workflow / SOP the agent should execute on a trigger?
                ├── Yes → write as a Skill (`.agents/skills/<name>/SKILL.md`)
                │         + at the appropriate tier (root or submodule).
                │         See `skills.md` and `agents-md.md` §1.3.4c.
                └── No (declarative knowledge) ↓
                    Does it apply across the whole project (multiple
                    submodules may consult it), or only inside one
                    submodule?
                        ├── Whole project →
                        │     root `.agents/rules/<topic>.md`
                        │     + add a row to root AGENTS.md Rules Reference
                        └── One submodule →
                              `packages/<name>/.agents/rules/<topic>.md`
                              + add a row to that submodule's
                                AGENTS.md Rules Reference
                              + if the submodule AGENTS.md does not yet
                                exist, also add a row to root AGENTS.md
                                Module Reference Map
```

### Migration path: from per-tool Rules to AGENTS.md + .agents/rules + Skills

**Step 1**: Move always-loaded rules to root AGENTS.md

```diff
- .cursor/rules/coding-style.mdc (alwaysApply: true)
- .claude/rules/coding-style.md (no paths)
- .trae/rules/project_rules.md
+ AGENTS.md  ## Code Style section
```

**Step 2**: Move project-specific path-scoped rules to the submodule's `.agents/rules/`

```diff
- .cursor/rules/this-project-react.mdc (globs: ["packages/frontend/**/*.tsx"])
- .claude/rules/this-project-react.md (paths: ["packages/frontend/**/*.tsx"])
+ packages/frontend/.agents/rules/react-conventions.md
+ packages/frontend/AGENTS.md  ## Rules Reference (add row pointing to the file)
```

Submodule layout mirrors root:

```
packages/frontend/
├── AGENTS.md                       # slim: scope + stack + Rules Reference + Workflows
└── .agents/
    ├── rules/                      # project-specific submodule rules
    │   ├── react-conventions.md
    │   └── state-management.md
    └── skills/                     # (optional) submodule-only workflows
        └── update-design-tokens/SKILL.md
```

Submodule AGENTS.md "Rules Reference" example:

```markdown
# packages/frontend/AGENTS.md

Scope: `packages/frontend/**`

## Stack
React 18 + TypeScript strict + zustand

## Rules Reference

Read on demand when working in the matching domain:

| Trigger                               | File                                              |
|---------------------------------------|---------------------------------------------------|
| Writing or editing React components   | `packages/frontend/.agents/rules/react-conventions.md` |
| Touching state management             | `packages/frontend/.agents/rules/state-management.md`  |
```

**Step 3**: Move project-level rules (those that apply across multiple submodules) to root `.agents/rules/`, referenced from root AGENTS.md

```diff
- .cursor/rules/coding-style.mdc (no path scope, but is content-driven knowledge)
- .claude/rules/typescript-strict.md (project-wide TS strict-mode constraints)
+ .agents/rules/coding-style.md
+ .agents/rules/typescript-strict.md
+ AGENTS.md  ## 0a. Rules Reference (add references)
```

**Step 4**: Move "on-demand long SOPs / smart-activation content" to Skills

```diff
- .cursor/rules/deploy.mdc (no frontmatter, @manual invocation)
- .cursor/rules/security-audit.mdc (description-based smart activation)
+ .agents/skills/deploy/SKILL.md
+ .agents/skills/security-audit/SKILL.md
```

> 💡 **Step 2 vs Step 3**: rules that only one submodule cares about go to Step 2 (`packages/<name>/.agents/rules/`, co-located with the submodule code); rules consulted across multiple submodules go to Step 3 (root `.agents/rules/`).
>
> 💡 **Why submodule `.agents/rules/` instead of cramming rules into submodule AGENTS.md**: keeps each rule file focused on one topic, mirrors the root `.agents/rules/` layout (low cognitive load), and avoids bloating the submodule AGENTS.md beyond Codex's 32 KiB silent-truncation limit.

### When you still need per-tool Rules

Even though migration is recommended, the scenarios below **still require per-tool Rules** — AGENTS.md and Skills cannot replace them:

| Scenario | Tool that requires Rules | Reason |
|---|---|---|
| Cursor `@rule-name` manual reference | Cursor `.cursor/rules/` (no frontmatter) | Cursor-specific interaction |
| Trae `#Rule` manual trigger (highest priority) | Trae `.trae/rules/` | Trae-specific, priority overrides everything |
| Tool-specific IDE behavior (e.g. Cursor Team Rules dashboard) | Cursor Team Rules | Enterprise governance |
| Claude path-scoped rules that should **not** go through AGENTS.md routing | Claude `.claude/rules/*.md` + `paths` | Rare case |

> 💡 **80/20 rule**: 80% of rules migrate to AGENTS.md + Skills; 20% tool-specific ones stay in per-tool Rules.
>
> ⚠️ **Trade-off — what you give up by migrating**: Cursor's `.mdc` has two capabilities that AGENTS.md / `.agents/rules/` do not have natively:
> - **Smart activation by `description`** (Cursor's `description` + globs only loads the rule when the file pattern matches the current edit) — `.agents/rules/*.md` is route-driven (loaded only when the agent reads AGENTS.md and follows the Rules Reference). For unsophisticated models this can mean the rule effectively never fires.
> - **Glob-scoped auto-loading** (`globs: ["packages/frontend/**/*.tsx"]`) — `.agents/rules/` does not auto-load at all; you replace this with "submodule `.agents/rules/` referenced from the submodule's AGENTS.md", which works on Codex / Cursor / opencode (nested AGENTS.md auto-loads), but on Claude / Trae depends on the agent following the Module Reference Map chain.
>
> If your team relies heavily on Cursor's smart activation today and is single-tool, the migration may be a net loss. The migration is worth it when (a) you have ≥ 2 tools to support, or (b) you accept the routing-driven discovery cost.

### Before/After example

**Before** (rules scattered across three places, mutually incompatible):
```
.cursor/rules/
  ├── coding-style.mdc (alwaysApply)
  ├── react.mdc (globs)
  └── deploy.mdc (manual)
.claude/rules/
  ├── coding-style.md
  ├── react.md (paths)
  └── deploy.md
.trae/rules/
  └── project_rules.md
```

**After** (unified via AGENTS.md routing + `.agents/rules/` + Skills):
```
AGENTS.md                                              # hard constraints + routing tables (always-on)
.agents/rules/                                         # (optional) project-level rules
packages/frontend/AGENTS.md                            # slim: scope + Rules Reference + Workflows
packages/frontend/.agents/rules/react-conventions.md   # submodule-only rules
.agents/skills/deploy/SKILL.md                         # deploy SOP (on-demand, replaces manual rules)
```

- File count: 7 → 4 (or 5 with project-level `.agents/rules/`)
- Cross-tool compatibility: 0% → 100%
- Context cost: only root AGENTS.md is always loaded; submodule AGENTS.md / `.agents/rules/` / Skills load on demand
- Discovery chain: root AGENTS.md `Module Reference Map` → submodule AGENTS.md → submodule `.agents/rules/*.md` (Codex/Cursor auto-load the chain; Claude/Trae actively Read each step)

## 2.4 Per-tool Notes

### Claude Code

- 💡 The field is `paths` (not `globs`); single-line unquoted form avoids some parser bugs: `paths: src/api/**/*.ts, lib/**/*.ts`
- ⚠️ Path-scoped rules trigger only when Claude **Reads** a matching file — **editing or creating new files may not trigger them**
- 💡 `/memory` audits currently loaded rules
- ❌ No description-based smart activation, no `@rule` manual invocation (use Skills instead)

### Cursor

- ⚠️ `.md` files (no frontmatter) under `.cursor/rules/` **are ignored** — must be `.mdc`
- 💡 Since 2.2+, new rules are saved as **folders** (`.cursor/rules/<name>/RULE.md`); legacy `.mdc` still works
- 💡 Team Rules are managed centrally via the Team / Enterprise dashboard
- ⚠️ `CLAUDE.md` is **always fully loaded** in Cursor (ignores `alwaysApply`) — used for cross-tool compatibility

### Trae

- 💡 Activation mode is configured in the IDE Settings panel (not frontmatter) — the team must agree on a convention
- 💡 `#Rule rule-name` is the highest priority and force-loads even when the rule is in a different mode
- 💡 `.trae/settings.local.json` is gitignored by default — useful for personal local overrides

### Codex

- ❌ No dedicated Rules system; all "rules" are expressed through AGENTS.md + directory nesting

### opencode

- ❌ **No dedicated Rules system** — everything routes through `AGENTS.md` (same philosophy as Codex)
- 💡 **Extra rule files without copying into AGENTS.md**: set the `instructions` field in `opencode.json` to point at additional files (`["./docs/coding-style.md", "./docs/security.md"]`); contents are appended to every session's context
- 💡 **Global rules**: `~/.config/opencode/AGENTS.md` is loaded into every opencode session — equivalent to "always-on user-level rules"
- 💡 **Per-agent scoping**: a subagent's `permission` block (in its agent markdown) can deny tools that would otherwise let it violate a rule (e.g. `edit: deny` for a read-only reviewer)
- 💡 Recommended migration: any Cursor `.mdc` or Claude `.md` rule that was `alwaysApply: true` → straight into root `AGENTS.md`; scoped rules → `instructions` array or submodule AGENTS.md routing (same as the org standard above)
