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

> **🎯 Core strategy: single source of truth at `.agents/rules/`, bridged into each tool's native rules path**
>
> The Rules-supporting tools (Claude / Cursor / Trae) differ in path, frontmatter fields, and activation behavior (see §2.1), and the core mechanisms are already frozen — they will never converge. Rather than abandon those native rules systems (which would forfeit Cursor's smart activation and Trae's `#Rule` triggers) or duplicate rule files per tool (which drifts), **keep one canonical copy of every rule under `.agents/rules/<topic>.md` and bridge each rules-supporting tool to it** in the tool's preferred shape. The four content buckets below tell you where each piece of content lives; the bridge recipes (§2.3.1) tell you how every tool reaches it.
>
> | Content type | Lives at | How each tool reaches it |
> |---|---|---|
> | **Project-wide hard constraints** (do-not-touch, naming, commit format) | **Root `AGENTS.md`** body | All 5 tools — always-loaded by Codex / Cursor / opencode; Claude via `@AGENTS.md` from `CLAUDE.md`; Trae once "Include AGENTS.md" is toggled |
> | **Project-level rules** (coding style, TS strict, security baseline) | **Root `.agents/rules/<topic>.md`** | Claude / Trae auto-load via directory symlink (§2.3.1); Cursor auto-loads via `.mdc` shim per file (§2.3.1); Codex / opencode reach them via root AGENTS.md `Rules Reference` table |
> | **Submodule-only rules** (e.g. frontend React conventions) | **`packages/<name>/.agents/rules/<topic>.md`** | All 5 tools route via the submodule AGENTS.md `Rules Reference` table (the L1 directory bridge does not cover L2 by design — see §2.3.1) |
> | **Triggerable workflows / SOPs** (release, audit, scaffold) | **`.agents/skills/<name>/SKILL.md`** at the appropriate tier | See [`skills.md`](skills.md) — separate dimension |
>
> Submodule rule files mirror the root `.agents/rules/` layout. The submodule AGENTS.md stays slim — it only holds the submodule's stack info + a Rules Reference table that points to the local `.agents/rules/*.md` files.

### 2.3.1 Bridging Claude / Trae / Cursor to `.agents/rules/`

Canonical content lives in `.agents/rules/<topic>.md`. Each rules-supporting tool reaches it via its own native path:

| Tool | Bridge mechanism | Notes |
|---|---|---|
| **Claude Code** | **Directory symlink** `.claude/rules → .agents/rules` (or per-file symlinks if you want to expose only a subset) | Claude reads `.md` natively. Path scoping uses Claude's `paths` frontmatter — add it **in the canonical file** (Trae ignores unknown frontmatter; Codex / opencode never read these files directly). |
| **Trae** | **Directory symlink** `.trae/rules → .agents/rules` (same shape as Claude) | Trae reads `.md` natively. Activation mode is configured per-rule in the Trae IDE settings panel, not via frontmatter — establish a team convention. |
| **Cursor** | **`.mdc` shim per rule** at `.cursor/rules/<topic>.mdc` containing Cursor-specific frontmatter (`description` / `globs` / `alwaysApply`) plus either a one-line redirect to the canonical file or an inlined copy of the body | Cursor only reads `.mdc` — a plain `.md` symlink will be ignored. The shim is small (frontmatter + a short body); preserve Cursor's smart-activation by writing meaningful `description` / `globs`. |
| **Codex** | No rules system — content is reached via root AGENTS.md `Rules Reference` table | Same as today |
| **opencode** | Same as Codex — content is reached via root AGENTS.md, or via the `instructions` array in `opencode.json` pointing at `.agents/rules/*.md` files directly | Same as today |

**Two Cursor shim styles** — pick one and apply consistently:

*Redirect shim* (smaller, but rule body needs an active Read by the agent):

```mdc
---
description: TypeScript strict-mode conventions for this repo
globs: ["**/*.ts", "**/*.tsx"]
alwaysApply: false
---

Apply the conventions documented in [`.agents/rules/typescript-strict.md`](../../.agents/rules/typescript-strict.md). Read that file before continuing.
```

*Inline shim* (heavier, but Cursor sees content immediately on activation; must be regenerated when the canonical file changes — a tiny script that copies `.agents/rules/*.md` → `.cursor/rules/*.mdc` with prepended frontmatter is the standard pattern):

```mdc
---
description: TypeScript strict-mode conventions for this repo
globs: ["**/*.ts", "**/*.tsx"]
alwaysApply: false
---

<!-- AUTO-GENERATED from .agents/rules/typescript-strict.md — edit the canonical file, not this shim -->

# TypeScript Strict Mode
...(body copied from canonical)...
```

> ⚠️ **Cross-device caveats apply** — the same constraints described for skill bridging in [`skills.md`](skills.md) §3.5.2 apply here verbatim (Windows symlink permissions / `git config core.symlinks` / FAT32 / network drives / coexistence with `~/.claude/rules/` and `~/.trae/rules/` from `npx skills add` and similar installers). Pick a bridging strategy that fits your team's OS mix; this handbook deliberately does not prescribe a single recipe. **Never blindly delete an existing `.claude/rules/` / `.trae/rules/` directory to "refresh" the bridge** — those paths may already hold rules another consumer-side installer dropped in.

**Submodule rules stay routed, not bridged.** The L1 directory symlink only exposes the root `.agents/rules/` files. Submodule rules under `packages/<name>/.agents/rules/` continue to be routed via the submodule AGENTS.md `Rules Reference` table — this keeps the submodule's rules visible only when working in that subtree (which is the desired scoping) and avoids exposing every submodule's internals into Claude/Trae's flat rules catalogue.

**Root AGENTS.md `Rules Reference` table is still required** — it's the only discovery path for Codex / opencode (which have no native rules system) and the canonical human-facing index. With bridges, Claude / Cursor / Trae auto-load the same files; the `Rules Reference` table simply becomes the cross-tool documentation of intent.

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

### Migration path: from per-tool Rules to `.agents/rules/` + bridges + Skills

**Step 1**: Move always-loaded rules to root AGENTS.md (these don't need any bridge — every tool already has a way to read AGENTS.md)

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

**Step 3**: Move project-level rules (those that apply across multiple submodules) to root `.agents/rules/`, and bridge the rules-supporting tools to it

```diff
- .cursor/rules/coding-style.mdc (no path scope, but is content-driven knowledge)
- .claude/rules/typescript-strict.md (project-wide TS strict-mode constraints)
+ .agents/rules/coding-style.md                                  # canonical
+ .agents/rules/typescript-strict.md                              # canonical
+ .claude/rules → .agents/rules                                   # symlink (or per-file)
+ .trae/rules   → .agents/rules                                   # symlink
+ .cursor/rules/coding-style.mdc                                  # .mdc shim per rule
+ .cursor/rules/typescript-strict.mdc                             # .mdc shim per rule
+ AGENTS.md  ## 0a. Rules Reference                               # for Codex / opencode discovery
```

**Step 4**: Move "on-demand long SOPs / smart-activation content" to Skills

```diff
- .cursor/rules/deploy.mdc (no frontmatter, @manual invocation)
- .cursor/rules/security-audit.mdc (description-based smart activation)
+ .agents/skills/deploy/SKILL.md
+ .agents/skills/security-audit/SKILL.md
```

> 💡 **Step 2 vs Step 3**: rules that only one submodule cares about go to Step 2 (`packages/<name>/.agents/rules/`, co-located with the submodule code, routed via the submodule AGENTS.md — no bridge); rules consulted across multiple submodules go to Step 3 (root `.agents/rules/` + L1 bridges).
>
> 💡 **Why submodule `.agents/rules/` instead of cramming rules into submodule AGENTS.md**: keeps each rule file focused on one topic, mirrors the root `.agents/rules/` layout (low cognitive load), and avoids bloating the submodule AGENTS.md beyond Codex's 32 KiB silent-truncation limit.

### Tool-specific edge cases the bridge does not cover

The bridge handles the common case (a rule the agent should read in the matching context). The scenarios below still need additional per-tool plumbing on top of the canonical file:

| Scenario | What to do | Reason |
|---|---|---|
| Cursor `@rule-name` manual reference | `@rule-name` resolves against the `.mdc` shim filename — keep shim filename equal to the canonical filename without extension | Cursor's manual `@` syntax matches shim names directly; no extra work as long as shims mirror canonical filenames 1-to-1 |
| Trae `#Rule rule-name` manual trigger (highest priority, force-loads) | Same — `#Rule` resolves against the filename under `.trae/rules/`, which is the symlinked canonical file | Works through the symlink unchanged |
| Tool-specific IDE behavior (e.g. Cursor Team Rules dashboard) | Continue to manage via the tool's enterprise dashboard; treat as out-of-band from the canonical `.agents/rules/` | Enterprise governance lives at the tool layer, not the file layer |
| Claude path-scoped rules | Put `paths: [...]` frontmatter in the **canonical** file under `.agents/rules/` — the symlink exposes the same file to Claude, which honors `paths`; Trae / Codex / opencode ignore the unknown field | One file, one frontmatter block, no duplication |

### Recommended layout

```
AGENTS.md                                              # hard constraints + Rules Reference (Codex/opencode discovery)
.agents/rules/                                         # canonical content (single source of truth)
  ├── coding-style.md                                  #   always-on style rule
  └── typescript-strict.md                             #   contains Claude `paths` frontmatter; ignored by other tools
.claude/rules → .agents/rules                          # bridge: directory symlink
.trae/rules   → .agents/rules                          # bridge: directory symlink
.cursor/rules/                                         # bridge: per-rule .mdc shim (frontmatter + redirect or inline)
  ├── coding-style.mdc                                 #   description / alwaysApply
  └── typescript-strict.mdc                            #   description / globs
packages/frontend/AGENTS.md                            # slim: scope + Rules Reference + Workflows
packages/frontend/.agents/rules/react-conventions.md   # submodule-only rules — routed, not bridged
.agents/skills/deploy/SKILL.md                         # deploy SOP (on-demand, replaces manual rules)
```

Properties of this layout:

- One canonical file per rule under `.agents/rules/`; bridges (symlinks + small `.mdc` shims) carry no rule content
- Cross-tool compatibility: every tool reaches the same canonical text
- Smart activation preserved: Cursor `.mdc` shim keeps `description` / `globs` smart activation; Trae IDE-side activation modes still work; Claude `paths` honored via canonical-file frontmatter
- Context cost: only root AGENTS.md is always loaded; submodule AGENTS.md / submodule `.agents/rules/` / Skills load on demand; L1 `.agents/rules/*.md` loads when its bridge fires on its corresponding tool

## 2.4 Per-tool Notes

### Claude Code

- 💡 With the bridge in place (`.claude/rules → .agents/rules`), Claude sees every canonical file natively — no extra setup beyond the symlink
- 💡 The field is `paths` (not `globs`); single-line unquoted form avoids some parser bugs: `paths: src/api/**/*.ts, lib/**/*.ts`. Put `paths` in the **canonical** file under `.agents/rules/`; other tools ignore unknown frontmatter
- ⚠️ Path-scoped rules trigger only when Claude **Reads** a matching file — **editing or creating new files may not trigger them**
- 💡 `/memory` audits currently loaded rules
- ❌ No description-based smart activation, no `@rule` manual invocation natively (Cursor's `@rule-name` is Cursor-specific and works through the `.mdc` shim, not in Claude)

### Cursor

- ⚠️ **Only reads `.mdc`** — `.md` files under `.cursor/rules/` (and any plain `.md` symlink) are ignored. This is why bridging uses **per-file `.mdc` shims** rather than a directory symlink (see §2.3.1)
- 💡 Shim styles (redirect vs. inline) trade body size for active-Read latency; the inline form usually wins for short rules, redirect form for long ones
- 💡 Since 2.2+, new rules are also accepted as **folders** (`.cursor/rules/<name>/RULE.md`); the bridging shim works either way
- 💡 Team Rules are managed centrally via the Team / Enterprise dashboard — these stay out-of-band from `.agents/rules/`
- ⚠️ `CLAUDE.md` is **always fully loaded** in Cursor (ignores `alwaysApply`) — used for cross-tool compatibility

### Trae

- 💡 With the bridge in place (`.trae/rules → .agents/rules`), Trae sees every canonical file natively
- 💡 Activation mode is configured per-rule in the IDE Settings panel (not frontmatter) — the team must agree on a convention and document it next to the canonical file
- 💡 `#Rule rule-name` resolves against the filename under `.trae/rules/`, so it works through the symlink unchanged and is the highest priority (force-loads even when the rule is in a different activation mode)
- 💡 `.trae/settings.local.json` is gitignored by default — useful for personal local overrides

### Codex

- ❌ No dedicated Rules system; all "rules" are expressed through AGENTS.md + directory nesting. The root AGENTS.md `Rules Reference` table is how Codex reaches `.agents/rules/*.md`

### opencode

- ❌ **No dedicated Rules system** — everything routes through `AGENTS.md` (same philosophy as Codex)
- 💡 **Extra rule files without copying into AGENTS.md**: set the `instructions` field in `opencode.json` to point at canonical files (`["./.agents/rules/coding-style.md", "./.agents/rules/typescript-strict.md"]`); contents are appended to every session's context — this is opencode's equivalent of the bridge for global rules
- 💡 **Global rules**: `~/.config/opencode/AGENTS.md` is loaded into every opencode session — equivalent to "always-on user-level rules"
- 💡 **Per-agent scoping**: a subagent's `permission` block (in its agent markdown) can deny tools that would otherwise let it violate a rule (e.g. `edit: deny` for a read-only reviewer)
