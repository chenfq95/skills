# Commands (Slash Commands)

> This file is the full survey of the **Commands** dimension for [SKILL.md](../SKILL.md).
>
> ⚠️ **Recommendation: do not introduce new Commands. Use Skills instead — on every tool, including opencode.**
>
> - Claude Code has officially marked `.claude/commands/` as legacy and recommends `.claude/skills/<name>/SKILL.md`.
> - opencode treats both Commands and Skills as first-class, but Skills give you (a) auto-activation via `description`, (b) cross-tool reuse via `.agents/skills/`, and (c) multi-file folder layout — none of which Commands offer. The only notable Commands-only edge case today is `agent:` frontmatter for sub-agent routing.
> - Codex / Cursor / Trae do not have a Commands concept at all.
>
> This file is therefore mostly a **migration guide**. Keep an existing `.claude/commands/` or `.opencode/commands/` library running while you move it to `.agents/skills/`; do not start new content in either place.

## 5.1 Capability Comparison

| Dimension | Claude Code | opencode | Codex | Cursor | Trae |
|---|---|---|---|---|---|
| Dedicated commands system | ⚠️ legacy | ✅ native | ❌ | ❌ | ❌ |
| Project-level path | `.claude/commands/<name>.md` | `.opencode/commands/<name>.md` (plural, current) or `.opencode/command/` (singular, legacy compat) | — | — | — |
| User-level path | `~/.claude/commands/<name>.md` | `~/.config/opencode/commands/<name>.md` | — | — | — |
| Invocation | `/name` (manual only) | `/name` (manual only) | — | — | — |
| frontmatter fields | `description`, `argument-hint`, `allowed-tools`, `model` | `description`, `agent` | — | — | — |
| Auto-activation by description | ❌ never (manual only) | ❌ | — | — | — |
| Subdirectory namespacing | ✅ `frontend/component.md` → `/component (project:frontend)` | ✅ | — | — | — |
| Same-name conflict | Project wins over user; **commands also shadowed by same-name skill** | n/a | — | — | — |
| Officially recommended | ❌ "legacy format, prefer Skills" | ⚠️ still supported but Skills give a strict superset | — | — | — |
| **Org recommendation (this handbook)** | ❌ migrate to Skills | ❌ migrate to Skills | n/a | n/a | n/a |
| Reads `.agents/commands/` | ❌ | ❌ | ❌ | ❌ | ❌ |

> Codex / Cursor / Trae do not have a "commands" folder concept at all. Slash commands in those tools are either IDE-built-in or expressed through Skills.

## 5.2 Standard Command File Format

**Claude Code minimum**:

```markdown
---
description: One-line summary shown in the command palette
---

Body of the prompt. Use $ARGUMENTS to interpolate user-supplied args.
```

**Claude Code full fields**:

```markdown
---
description: Refactor the selected code following the project style guide
argument-hint: <file-path> [--strict]
allowed-tools: Read, Edit, Bash(npm test:*)
model: claude-sonnet-4-20250514
---

Refactor $ARGUMENTS following the conventions in AGENTS.md.
...
```

**opencode**:

```markdown
---
description: Short description shown in the command palette
agent: review
---

Instructions passed to the named agent when this command is invoked.
```

## 5.3 Commands vs Skills — Why Skills Win

Claude Code's own docs:

> The `.claude/commands/` directory is the **legacy format**. The recommended format is `.claude/skills/<name>/SKILL.md`, which supports the same slash-command invocation (`/name`) plus autonomous invocation by Claude.

| Dimension | `.claude/commands/<name>.md` | `.claude/skills/<name>/SKILL.md` |
|---|---|---|
| `/name` manual invocation | ✅ | ✅ identical UX |
| Auto-activation via `description` | ❌ never | ✅ optional (omit `disable-model-invocation`) |
| Single-file prompt | ✅ trivial | ✅ also possible (just a one-file skill) |
| Multi-file (scripts, reference, assets) | ❌ single file only | ✅ full skill folder |
| Tool whitelisting | ✅ `allowed-tools` | ✅ `allowed-tools` + `disallowed-tools` |
| Sub-agent isolation | ❌ | ✅ `context: fork` |
| Cross-tool reuse | ❌ Claude / opencode only (different fields) | ✅ Cursor 2.4+/Codex/opencode/Copilot/Gemini native on `.agents/skills/`, Claude/Trae via symlink |
| Status | ❌ Claude legacy; opencode supported but strictly subsumed by Skills | ✅ recommended on all five tools |

**Net**: Skills can do everything Commands can do, plus more. The only thing "command-flavored" you might want is **pure manual triggering with no auto-activation** — Skills achieve this by setting `disable-model-invocation: true` in the SKILL.md frontmatter.

## 5.4 Project Config Best Practices

### When to (still) keep Commands

The default for any new content is **Skills, not Commands** — on every tool, including opencode. The only acceptable reasons to keep a Commands file alive are:

| Condition | What to do |
|---|---|
| You have an existing `.claude/commands/` or `.opencode/commands/` library and a wholesale rewrite is expensive | Keep the existing files working; migrate one at a time as you touch them (see the Migration Path section below) |
| You want a personal `~/.claude/commands/*.md` / `~/.config/opencode/commands/*.md` for one-line prompts and don't care about cross-tool reuse | Slightly less ceremony than a single-file skill — fine for personal scratch |

For **everything that ships in a repo**, use `.agents/skills/<name>/SKILL.md`.

### Migration Path: Commands → Skills

A 1-file command maps cleanly to a 1-file skill (one folder, one `SKILL.md`):

```diff
# Claude Code
- .claude/commands/refactor.md
+ .agents/skills/refactor/SKILL.md          # bridge .claude/skills/ → .agents/skills/, see skills.md §3.5.2

# opencode
- .opencode/commands/refactor.md
+ .agents/skills/refactor/SKILL.md          # opencode natively reads .agents/skills/
```

Frontmatter mapping (covers both Claude Code and opencode commands):

| Commands frontmatter | Skills frontmatter | Notes |
|---|---|---|
| `description: ...` | `description: ...` | Same field, same purpose. **In Skills this also drives auto-activation** — include both WHAT and WHEN if you want auto-invocation, or set `disable-model-invocation: true` to preserve commands-flavored "manual only" behavior |
| `argument-hint: ...` (Claude) | `argument-hint: ...` | Same field |
| `allowed-tools: ...` (Claude) | `allowed-tools: ...` | Same field |
| `model: ...` (Claude) | `model: ...` | Same field |
| `agent: <name>` (opencode) | (no equivalent — see note below) | opencode commands route to a named sub-agent. In Skills you either: (a) drop the routing if the skill is self-contained, or (b) keep the sub-agent and have the skill instruct the user / parent agent to dispatch via the `agent` tool. For most refactor / format / triage workflows, option (a) is the right move |
| n/a | `name: refactor` | Required by Skills — must match folder name, lowercase + hyphens, ≤ 64 chars (opencode validates this strictly) |

Body content moves verbatim. `$ARGUMENTS` interpolation works identically in Skills on Claude Code; on opencode the `$ARGUMENTS` placeholder is handled the same way inside `.agents/skills/<name>/SKILL.md`.

#### Concrete example (Claude Code)

Before — `.claude/commands/refactor.md`:

```markdown
---
description: Refactor the selected code following the project style guide
argument-hint: <file-path> [--strict]
allowed-tools: Read, Edit, Bash(npm test:*)
---

Refactor $ARGUMENTS following the conventions in AGENTS.md.
```

After — `.agents/skills/refactor/SKILL.md`:

```markdown
---
name: refactor
description: Refactor a file to match the project style guide. Use when the user asks to refactor, clean up, or restyle a specific file path.
argument-hint: <file-path> [--strict]
allowed-tools: Read, Edit, Bash(npm test:*)
disable-model-invocation: true    # keep manual-only — drop this to enable auto-activation
---

Refactor $ARGUMENTS following the conventions in AGENTS.md.
```

> 💡 `disable-model-invocation: true` here is **intentional** — the original was a manual slash command (no auto-invocation), and we want the migrated skill to preserve that behavior. This is the **only sanctioned use** of the field per SKILL.md §M1.4: opt in when the workflow is deliberately slash-only, never set it defensively. If you want the skill to also auto-activate when the description matches, omit the line.

#### Concrete example (opencode)

Before — `.opencode/commands/refactor.md`:

```markdown
---
description: Refactor the selected file following the project style guide
agent: code-reviewer
---

Refactor $ARGUMENTS following the conventions in AGENTS.md.
```

After — `.agents/skills/refactor/SKILL.md` (opencode reads `.agents/skills/` natively):

```markdown
---
name: refactor
description: Refactor a file to match the project style guide. Use when the user asks to refactor, clean up, or restyle a specific file path.
---

Refactor $ARGUMENTS following the conventions in AGENTS.md.

(If the `code-reviewer` sub-agent should drive this, ask the user to invoke
via `@code-reviewer run /refactor <path>`, or — for fully autonomous
delegation — keep using the legacy command until opencode adds a frontmatter
field to route a skill to a named agent.)
```

If the `agent:` routing is essential (e.g. the workflow must run in an isolated context), this is the **one** opencode-specific case where keeping the file under `.opencode/commands/` is currently the simpler option. Reassess once opencode adds a per-skill `agent:` field.

#### Optional: `.opencode/commands/` thin wrapper for in-IDE discoverability

opencode lists commands in its slash palette by scanning `.opencode/commands/`. If you want a migrated skill to keep appearing in that palette as a slash command after moving the body to `.agents/skills/`, leave a one-line wrapper:

```markdown
---
description: Refactor a file to match the project style guide
---

Run the `refactor` skill on $ARGUMENTS.
```

The body lives in `.agents/skills/refactor/SKILL.md` (auto-discovered + cross-tool); the wrapper exists only to surface the slash command in opencode's UI.

### After Migration: Recommended Layout

```
.agents/skills/
├── refactor/SKILL.md          # disable-model-invocation: true (manual-only, command-flavored)
├── changelog/SKILL.md          # auto-activates when user asks about releases
├── triage-issue/SKILL.md       # disable-model-invocation: true
└── deploy-prod/SKILL.md        # auto-activates when user mentions ship/release
```

A single Skills folder now hosts both "command-flavored" (manual-only) and "skill-flavored" (auto-activating) workflows — one mental model, one toolchain, cross-tool compatible across all five tools.

### Why there is no `.agents/commands/`

Unlike `.agents/skills/`, **no major tool natively scans `.agents/commands/`**:

- Claude Code's `/init` and CLI only look at `.claude/commands/`
- opencode looks at `.opencode/commands/` (plural, current — `.opencode/command/` is accepted as legacy compat)
- Cross-tool community templates sometimes create `.agents/commands/` aspirationally, but it's a dead letter — no runtime picks it up

Combined with the legacy status of commands themselves, there is **no reason to introduce a `.agents/commands/` directory** in a new project. Migrate to `.agents/skills/` and bridge `.claude/skills/` / `.trae/skills/` back to it using whichever cross-platform strategy fits your team (see [`skills.md`](skills.md) §3.5.2).

## 5.5 Per-tool Notes

### Claude Code

- ⚠️ **`/init` will scaffold `.claude/commands/`** if you start fresh, but the docs state this is legacy — overwrite or empty it and use `.claude/skills/` instead
- 💡 **Same-name shadow rule**: a `.claude/skills/foo/SKILL.md` shadows `.claude/commands/foo.md` — handy for incremental migration (drop a SKILL.md alongside the command and the skill wins)
- 💡 **Project commands shadow user commands**: `.claude/commands/review.md` in a repo hides your personal `~/.claude/commands/review.md` while in that repo
- 💡 **Subdirectory namespacing**: `.claude/commands/frontend/component.md` becomes `/component` with namespace `(project:frontend)` in the palette
- 💡 `$ARGUMENTS` placeholder works identically in commands and skills

### opencode

- ⚠️ **Even though opencode treats Commands as first-class, this handbook recommends Skills**: opencode also natively reads `.agents/skills/`, and Skills are a strict superset (auto-activation, cross-tool reuse, multi-file folder). New workflows belong under `.agents/skills/`; only keep `.opencode/commands/` for already-shipped libraries or for personal one-liners
- 💡 **Sub-agent routing (`agent:` frontmatter)** is the one Commands-only capability that has no direct Skills equivalent today — if a workflow *must* run inside a specific sub-agent's isolated context, keep it as a Command until opencode adds the equivalent field to skills, or have a thin `.opencode/commands/` wrapper that delegates to a Skill (see §5.4)
- 💡 Subdirectory paths under `.opencode/commands/` are supported as namespacing
- ⚠️ **Singular `.opencode/command/` is legacy compat** — current docs recommend plural everywhere (`agents/`, `commands/`, `skills/`, `plugins/` etc.); only pre-existing repos should keep singular
- 💡 Commands can also be defined inline in `opencode.json` under the `command` key as an alternative to markdown files — same recommendation applies: prefer Skills

### Codex / Cursor / Trae

- ❌ No `commands/` directory concept. Slash commands either come from the IDE itself (e.g. Cursor's built-in `/edit`, `/explain`) or from Skills
- 💡 If you need a "command-flavored" workflow that all five tools can invoke, write it as a SKILL.md with `disable-model-invocation: true` and use `name` as the slash trigger

### Cross-tool reuse limitation

Even with symlinks, you cannot make Commands cross-tool:

```
.cursor/commands/  ← .claude/commands/    # ❌ Cursor doesn't scan this path
.codex/commands/   ← .claude/commands/    # ❌ Codex has no commands concept
.opencode/commands/← .claude/commands/    # ⚠️ opencode scans but format differs (agent: vs allowed-tools:)
.trae/commands/    ← .claude/commands/    # ❌ Trae has no commands concept
```

This is the fundamental reason Skills supersede Commands at the ecosystem level — `.agents/skills/` is the only path **five current readers** natively read (Codex / Cursor 2.4+ / opencode / Copilot / Gemini), with Claude / Trae bridged via symlink. See [`skills.md`](skills.md) §3.3.
