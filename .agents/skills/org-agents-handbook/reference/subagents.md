# Subagents (Custom Agents)

> This file is the full survey of the **Subagents** dimension for [SKILL.md](../SKILL.md).
>
> **What it is**: file-based custom agents with their own system prompt, tool allowlist, model, and **isolated context window**. Sibling concept to Skills (short callable workflow) and Commands (legacy slash command), but with longer lifetime and full context separation.

## 6.1 Capability Comparison

| Dimension | Claude Code | opencode | Cursor | Codex | Trae |
|---|---|---|---|---|---|
| Dedicated subagent system | ✅ file-based | ✅ file-based **or** `opencode.json` `agent` field | ✅ Custom Modes (UI) | ⚠️ SDK / Task tool only | ⚠️ GUI personas |
| Project-level path | `.claude/agents/<name>.md` | `.opencode/agents/<name>.md` (plural, current) or `.opencode/agent/` (legacy compat) | Settings JSON in repo | — | — |
| User-level path | `~/.claude/agents/<name>.md` | `~/.config/opencode/agents/<name>.md` | User-level Custom Modes | — | — |
| Invocation | Task tool, `/agents` panel, or auto-route by `description` | `@agent` or `/agent` | Mode selector in chat panel | `Task` tool call from main agent | Persona switcher in panel |
| frontmatter / config fields | `name`, `description`, `tools`, `model` | `description`, `model`, `tools`, `mode` | `name`, `description`, `tools`, `model` (JSON) | n/a | n/a |
| Independent context window | ✅ | ✅ | ✅ | ✅ (Task tool) | ✅ |
| Inherits root AGENTS.md / CLAUDE.md | ❌ by default | ❌ | ⚠️ depends on mode | ✅ | ⚠️ |
| Inherits rules / skills | ❌ subagent runs clean | ❌ | ⚠️ | ✅ | ⚠️ |
| Auto-selected by `description` | ✅ Claude routes to matching agent | ⚠️ partial | ❌ user picks mode | ✅ | ❌ |
| Tool allowlist | ✅ `tools: [Read, Edit, Bash]` | ✅ | ✅ | n/a | n/a |
| Cross-tool reusable | ❌ Claude-only format | ❌ opencode-only | ❌ Cursor-only JSON | ❌ | ❌ |

> No cross-tool standard for subagents exists. Unlike Skills (`.agents/skills/`), there is **no `.agents/agents/` convention** that multiple tools natively read.

## 6.2 Standard Subagent Format

### Claude Code

```markdown
---
name: code-reviewer
description: Use this agent to perform thorough code review on a pull request or diff. Catches security issues, perf regressions, and style violations. Invoke proactively after any non-trivial code change.
tools: [Read, Grep, Glob, Bash(git diff:*), Bash(npm test:*)]
model: claude-sonnet-4-20250514
---

You are a senior code reviewer. Your job is to:
1. Read the diff carefully.
2. Flag security issues, perf regressions, and style violations.
3. Return a structured report with severity (blocker / warn / nit) for each finding.

Do not modify code. Only report.
```

**Field rules**:

- `name` — required, lowercase + hyphens, must match filename
- `description` — required; **this is what Claude uses to auto-route**, so write it as a clear capability statement
- `tools` — optional; if omitted, subagent inherits parent's allowed tools (often broader than you want)
- `model` — optional; defaults to session model

### opencode

```markdown
---
description: PR reviewer with security focus
mode: subagent
model: anthropic/claude-sonnet-4-20250514
temperature: 0.1
permission:
  edit: deny
  bash:
    "*": ask
    "git diff": allow
    "git log*": allow
    "grep *": allow
  webfetch: deny
---

You are a senior code reviewer...
```

**Permission keys**: `read`, `edit`, `glob`, `grep`, `list`, `bash`, `task`, `external_directory`, `lsp`, `skill` accept either a shorthand (`"allow" | "ask" | "deny"`) or an object of glob/pattern → action for fine-grained control. The same syntax also matches MCP tool names (e.g. `"mymcp_*": "deny"` denies every tool from a given MCP server).

### Cursor Custom Modes

Defined via Settings → Chat → Custom Modes (UI), exported as JSON:

```json
{
  "name": "Reviewer",
  "description": "Code review mode",
  "tools": ["read", "grep", "terminal"],
  "model": "claude-sonnet-4",
  "instructions": "You are a senior code reviewer..."
}
```

## 6.3 Subagents vs Skills vs Commands

| Dimension | Skills | Commands | Subagents |
|---|---|---|---|
| Context | Shares parent's | Shares parent's | **Isolated, fresh** |
| Lifetime | Single workflow execution | Single message | Multiple turns until done |
| Tool allowlist | ✅ | ✅ (Claude) | ✅ |
| Auto-activated by `description` | ✅ common skill trigger across covered tools | ❌ | ✅ Claude |
| Manual invocation | `/name` or by name | `/name` | `Task` tool or `@name` |
| Best fit | Reusable SOP/workflow | Manual prompt snippet (legacy) | Long-running specialist with separate context |
| Cross-tool standard | ✅ `.agents/skills/` (5 native readers; Claude / Trae via symlink) | ❌ Claude/opencode each have their own (different fields) | ❌ none |

**Decision tree**:

```
Need to encapsulate a reusable behavior?
├── Short workflow, runs in main context → Skills (default)
├── Manual-only prompt snippet → Skills with `disable-model-invocation: true`
│   (Commands is legacy on every tool — including opencode; see commands.md)
└── Long-running specialist that should NOT see main context → Subagents
    │   (PR reviewer, security auditor, doc-generator from scratch, etc.)
    └── Cross-tool need? → Re-implement per tool, no shared format
```

## 6.4 Best Practices

### When to use subagents

✅ **Good fits**:
- Specialist that benefits from a clean context (reviewer, debugger, doc-writer)
- Restricted-tool agent (read-only researcher, no Edit/Bash)
- Long-running task that would pollute main context (test runner, security scan)
- Cost optimization: route cheap tasks to a smaller model via `model:`

❌ **Bad fits**:
- One-shot prompt → use a Skill
- Needs full access to main session's history → use main agent
- You want cross-tool portability → no subagent format is portable

### Critical rules

1. **Write `description` as a routing trigger**, not a feature description. Bad: "Reviews code". Good: "Use this agent **after any code change** to catch security and perf issues — invoke proactively, before user asks".

2. **Tighten `tools`** — by default Claude subagents may inherit the parent's tools, which usually includes Edit/Bash. Whitelist explicitly to enforce read-only specialists.

3. **Do not duplicate AGENTS.md** in the subagent body. Subagents don't inherit AGENTS.md; if the agent genuinely needs project context, either:
   - Pass it via the `Task` call (parent agent assembles context)
   - Reference key files in the system prompt (`Read these first: AGENTS.md, packages/<x>/AGENTS.md`)

4. **One agent per concern**. Don't build a generic "helper" agent — Claude's auto-routing degrades with overlapping `description`s.

5. **Version-control project subagents** (`.claude/agents/*.md` committed). User-level (`~/.claude/agents/`) is for personal helpers only.

### Subagent ↔ Skill boundary

If your subagent's system prompt is mostly a **procedure** (numbered steps), it should probably be a Skill instead — Skills are cheaper (no context split), portable, and easier to test.

Keep it a subagent only when **context isolation** is the actual feature.

## 6.5 Per-tool Notes

### Claude Code

- 💡 `/agents` panel lists active subagents and lets you invoke manually
- 💡 Auto-routing: when Claude detects a user request matches a subagent's `description`, it offers to invoke (or invokes automatically depending on settings)
- ⚠️ **Subagents do NOT inherit CLAUDE.md / AGENTS.md / rules** — they start clean. If you need project context, reference files explicitly in the system prompt
- ⚠️ **`tools:` defaults to "all parent's tools"** if omitted — explicitly list to enforce restrictions
- 💡 Project agents shadow user agents on same name
- 💡 Subagents can themselves invoke other subagents via `Task` (mind the recursion)

### opencode

- 💡 `mode: subagent` distinguishes from main (primary) agents
- 💡 **Permissions are first-class in the agent frontmatter** — much finer-grained than Claude's `tools:` list. Bash patterns can be granular (`"git diff": allow`, `"git push *": deny`)
- 💡 The markdown filename becomes the agent name (`review.md` → `review` agent)
- 💡 Two equivalent ways to define an agent: markdown file under `agents/` **or** an entry in `opencode.json` `agent` object — the markdown form is usually preferred for shareability
- ⚠️ **Plural `agents/` is current; singular `agent/` is legacy compat** — matches the wider opencode convention (commands/, plugins/, skills/, modes/, etc.)
- 💡 Built-in agents can be **customized** (override `model`, `permission`, prompt) rather than replaced
- ⚠️ Auto-routing is less aggressive than Claude — usually invoked manually via `@agent-name`

### Cursor

- 💡 **Custom Modes** is the closest analog. Configured via Settings UI, not files
- 💡 Each mode has its own `tools`, `model`, and system prompt
- ⚠️ Modes are user-level; team sharing requires manual export/import or settings sync
- 💡 Background Agents (cloud) effectively run as a fixed subagent mode (see [`settings.md`](settings.md) §8.4 for `.cursor/environment.json`)

### Codex

- ❌ **No file-based subagent system**. Subagent behavior is achieved at SDK / programmatic level via the `Task` tool
- 💡 In CLI / TUI, you can simulate by switching `[profiles.*]` (different model/sandbox/prompt) — see [`settings.md`](settings.md)

### Trae

- ⚠️ Persona / custom agent configuration is **GUI-only**; no file-based format
- 💡 Personas are user-level — not shareable through the repo
- 💡 If you need a portable specialist, write it as a Skill instead

### Cross-tool reuse limit

There is no `.agents/agents/` standard. If you need the same specialist across the tools covered by this handbook:

1. **Write the system prompt once** as a Markdown file under `.agents/personas/<name>.md` (your own convention)
2. **Wrap it as a Skill** in the shared `.agents/skills/` catalogue, bridging Claude / Trae via symlink where appropriate — Skills can host long system-prompt-like bodies, just lose context isolation
3. **Re-encode as a Claude subagent** (`.claude/agents/<name>.md`) only when you truly need isolated context

Most teams find that 90% of "subagent" use cases are actually well-served by Skills. Reach for subagents only when context isolation is essential.
