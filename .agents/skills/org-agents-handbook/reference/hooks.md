# Hooks (Event-driven Automation)

> This file is the full survey of the **Hooks** dimension for [SKILL.md](../SKILL.md).
>
> **What it is**: shell commands, scripts, or programmatic plugins that fire on agent lifecycle events (before/after tool use, on user message, on session end, etc.). Used for **safety enforcement** (block sensitive commands), **audit logging**, **auto-formatting**, and **policy gates**. The only systematic way to enforce behavior — Rules / AGENTS.md are advisory; hooks are mechanical.
>
> **Tool coverage (2026-06)**: native hooks now ship on **Claude Code, Codex, Cursor, opencode**. Codex's hook schema is intentionally Claude-compatible (same `hooks.json` skeleton, same stdin contract, same exit-2 = block) so a single script can serve both. **Trae is the only one of the five without native hooks** — multiple feature requests open but unmerged.

## 7.1 Capability Comparison

| Dimension | Claude Code | opencode | Cursor | Codex | Trae |
|---|---|---|---|---|---|
| Dedicated hook system | ✅ rich, shell-script based | ✅ rich, **JS/TS plugin based** | ✅ (newer), shell-script | ✅ **stable since v0.117** (Claude-compatible shape, shell-script) | ❌ (FR open: Trae-AI/TRAE#2436, bytedance/trae-agent#397) |
| Config location | `.claude/settings.json` `hooks` block, or `.claude/hooks.json` | `.opencode/plugins/` or `~/.config/opencode/plugins/`, or npm package via `"plugin": [...]` in `opencode.json` | `.cursor/hooks/` + `hooks.json` | `~/.codex/hooks.json` or inline `[hooks]` in `~/.codex/config.toml`; plugin bundles via `hooks/hooks.json`; managed bundles via `requirements.toml` | n/a |
| Hookable events | PreToolUse, PostToolUse, UserPromptSubmit, Notification, Stop, PreCompact, SessionStart, SessionEnd | 25+ events: `tool.execute.before/after`, `session.created/idle/error/updated`, `file.edited`, `command.executed`, `experimental.session.compacting`, ... | PreToolUse, PostToolUse, BeforeSubmit, AfterResponse | 10 events: SessionStart, SubagentStart, PreToolUse, **PermissionRequest** (Codex-only), PostToolUse, PreCompact, PostCompact, UserPromptSubmit, SubagentStop, Stop | n/a |
| Tool-name matcher | ✅ glob/regex `matcher: "Bash"` | ✅ via JS conditional on `input.tool` | ✅ | ✅ regex; canonical names `Bash`, `apply_patch`, `mcp__server__tool`; `apply_patch` also matches `Edit`/`Write` aliases (input still reports `apply_patch`) | n/a |
| Can block tool execution | ✅ exit code 2 + stderr | ✅ throw / return blocking response in hook | ✅ | ✅ exit code 2 + stderr **or** stdout JSON `{"decision":"block","reason":"…"}` | n/a |
| Receives event data | ✅ via stdin JSON | ✅ as JS function arguments | ✅ | ✅ via stdin JSON (Claude-compatible field shape: `hookEventName`, `session_id`, `cwd`, `tool_name`, `tool_input`, ...) | n/a |
| Sync (blocking) vs async | Synchronous (agent waits) | Async-native (returns Promise) | Sync | Synchronous; per-handler `timeout` field | — |
| Project + user level | ✅ project > user | ✅ both load, hooks run in sequence | ✅ | ✅ user-level (`~/.codex/`) + plugin-bundled + `requirements.toml`-managed; all matching handlers run in declaration order | — |
| Cross-tool standard | ❌ each tool's own schema | ❌ JS plugin API is opencode-specific | ❌ | ⚠️ **shape Claude-compatible** (same `hooks.json` skeleton, `matcher` + `type: "command"`); `hookshot` and similar router scripts work across both | — |

> **Codex hooks landed and stabilized** (v0.114 SessionStart/Stop → v0.117 PreToolUse/PostToolUse + UserPromptSubmit → current SubagentStart/Stop + PreCompact/PostCompact + Codex-only PermissionRequest). The feature flag `[features].hooks` is enabled by default; the legacy `codex_hooks = true` key still works as a deprecated alias. The schema is intentionally aligned with Claude Code so the same script can serve both runtimes.
>
> **Trae is now the only one of the five tools without native hooks.** Multiple feature requests are open (Trae-AI/TRAE#2436, bytedance/trae-agent#397, forum.trae.cn #18062) but none have been implemented. For Trae, the only mechanical enforcement remains git pre-commit + CI; in-IDE permissions are GUI prompts.
>
> **opencode is still the odd one out on shape**: while Claude / Codex / Cursor use declarative JSON + shell scripts, opencode uses **JavaScript/TypeScript plugins** that subscribe to 25+ lifecycle events. The plugin can also register new tools and replace the compaction prompt — it is more programmatic, less declarative.

## 7.2 Standard Hook Configuration

### Claude Code (`.claude/settings.json`)

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/block-dangerous-bash.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "npx prettier --write \"$CLAUDE_TOOL_FILE_PATH\""
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          { "type": "command", "command": ".claude/hooks/log-prompt.sh" }
        ]
      }
    ]
  }
}
```

### Example hook script (`.claude/hooks/block-dangerous-bash.sh`)

```bash
#!/usr/bin/env bash
# Reads tool-call JSON from stdin, exits 2 to block.
INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if echo "$CMD" | grep -Eq '\brm -rf /|\bsudo|\bcurl .* \| sh\b'; then
  echo "BLOCKED: dangerous command pattern" >&2
  exit 2
fi
exit 0
```

**Exit-code contract** (Claude Code):

| Exit code | Behavior |
|---|---|
| 0 | Allow, no message |
| 1 | Allow, but stderr surfaces as warning |
| 2 | **Block** the tool call, stderr surfaces to model as feedback |

### opencode (`.opencode/plugins/<plugin>.ts`)

opencode hooks are **JavaScript/TypeScript plugins**, not shell scripts. A plugin is an async function returning an object whose keys are event names:

```typescript
// .opencode/plugins/audit.ts
import type { Plugin } from "@opencode-ai/plugin";

export const AuditPlugin: Plugin = async (ctx) => {
  return {
    "tool.execute.before": async (input, output) => {
      // Block dangerous bash commands
      if (input.tool === "bash" && /\brm -rf \/|\bsudo\b/.test(input.params.command)) {
        throw new Error(`BLOCKED: dangerous command pattern in ${input.params.command}`);
      }
      // Log every tool call
      await ctx.fs.appendFile(".opencode/audit.jsonl",
        JSON.stringify({ ts: Date.now(), tool: input.tool, params: input.params }) + "\n");
    },
    "session.idle": async () => {
      console.log("[audit] session ended");
    },
  };
};
```

**Load mechanism**: place file under `.opencode/plugins/` (project) or `~/.config/opencode/plugins/` (global), or register an npm package in `opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": ["opencode-helicone-session", "@my-org/audit-plugin"]
}
```

**Key events** (partial — see opencode plugin docs for the full list of 25+ events):

| Event | Fires when |
|---|---|
| `tool.execute.before` | Before any tool call; throw to block, mutate `input` to modify |
| `tool.execute.after` | After tool returns; inspect `output` |
| `command.executed` | After a slash command runs |
| `session.created` / `session.idle` / `session.error` / `session.updated` | Session lifecycle |
| `file.edited` | After agent edits a file |
| `experimental.session.compacting` | Before context compaction — inject domain context or replace the compaction prompt entirely |

### Cursor (`.cursor/hooks.json` + scripts in `.cursor/hooks/`)

```json
{
  "preToolUse": [
    { "matcher": "terminal", "command": ".cursor/hooks/lint-cmd.sh" }
  ],
  "postToolUse": [
    { "matcher": "editFile", "command": ".cursor/hooks/format.sh" }
  ]
}
```

### Codex (`~/.codex/hooks.json` — Claude-compatible JSON)

Codex deliberately mirrors Claude Code's schema, so a single script can serve both runtimes. Hooks live at the user level (project-scoped hooks land via **plugins** or `requirements.toml`-managed bundles, see below). Enable / disable via `[features].hooks = true|false` in `config.toml`; the older `codex_hooks` key is a deprecated alias.

```json
{
  "hooks": {
    "SessionStart": [
      { "matcher": "startup|resume",
        "hooks": [{ "type": "command", "command": "$HOME/.codex/hooks/load-context.sh", "timeout": 15 }] }
    ],
    "PreToolUse": [
      { "matcher": "Bash|apply_patch|mcp__.*",
        "hooks": [{ "type": "command", "command": "$HOME/.codex/hooks/block-dangerous.sh", "timeout": 5 }] }
    ],
    "PostToolUse": [
      { "matcher": "apply_patch",
        "hooks": [{ "type": "command", "command": "$HOME/.codex/hooks/format-edited.sh", "timeout": 30 }] }
    ],
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command", "command": "$HOME/.codex/hooks/log-prompt.sh" }] }
    ],
    "Stop": [
      { "hooks": [{ "type": "command", "command": "$HOME/.codex/hooks/session-summary.sh", "timeout": 30 }] }
    ]
  }
}
```

Equivalent inline TOML in `~/.codex/config.toml`:

```toml
[[hooks.PreToolUse]]
matcher = "Bash|apply_patch|mcp__.*"

[[hooks.PreToolUse.hooks]]
type = "command"
command = "$HOME/.codex/hooks/block-dangerous.sh"
timeout = 5
```

**Codex hook script — same stdin/stdout contract as Claude**:

```bash
#!/usr/bin/env bash
# Codex PreToolUse hook — block dangerous bash. Works unchanged for Claude.
INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name')
CMD=$(echo "$INPUT"  | jq -r '.tool_input.command // empty')

if [ "$TOOL" = "Bash" ] && echo "$CMD" | grep -Eq '\brm -rf /|\bsudo|\bcurl .* \| sh\b'; then
  echo "BLOCKED: dangerous command pattern" >&2
  exit 2     # exit 2 + stderr → block, feedback returned to model
fi
exit 0
```

Codex also accepts a richer JSON response on stdout (Claude superset):

```json
{ "decision": "block", "reason": "rm -rf / blocked by policy", "systemMessage": "Use rm -rf ./build instead." }
```

**Exit-code contract** (Codex — identical to Claude on 0/1/2, plus structured JSON):

| Exit code | Behavior |
|---|---|
| 0 | Allow; if stdout is JSON, fields like `decision`, `systemMessage`, `updatedInput`, `continue` apply |
| 1 | Allow; stderr surfaced as warning |
| 2 | **Block** the tool call; stderr surfaced to model as feedback |

**Project-scoped hooks**: Codex does **not** look at `.codex/hooks.json` in the repo. Project policy goes through one of:

- **Plugin bundle** — ship `hooks/hooks.json` (or the path declared by `"hooks"` in the plugin manifest) inside an installable plugin
- **`requirements.toml`** — a per-repo file that opts into managed hooks: `[features].hooks = true` plus `[[hooks.PreToolUse]]` tables; Codex prompts the user once to trust the manifest

This is the main shape difference from Claude (`.claude/settings.json` in repo is enough) — for Codex you commit a manifest the user explicitly trusts.

## 7.3 Project Config Best Practices

### Common patterns

| Pattern | Event | Purpose |
|---|---|---|
| **Audit log** | `UserPromptSubmit`, `PreToolUse` | Append to `.claude/audit.jsonl` for postmortem / compliance |
| **Block dangerous commands** | `PreToolUse` (`matcher: Bash`) | Pattern-match on `rm -rf`, `curl ... | sh`, `sudo`, secret exfiltration |
| **Auto-format on edit** | `PostToolUse` (`matcher: Edit|Write`) | Run prettier / rustfmt / black on the edited file |
| **Lint guard** | `PostToolUse` (`matcher: Edit|Write`) | Run linter, exit 1 to surface as warning so model self-corrects |
| **Notify on long-running** | `Notification` | Slack / desktop notification when agent waits for user |
| **Session bookend** | `SessionStart`, `SessionEnd` | Snapshot context, record duration / cost for analytics |
| **Compaction guard** | `PreCompact` | Save pre-compaction state to disk so you can recover if compaction loses info |

### Critical rules

1. **Hooks are synchronous — keep them fast**. Anything > 1s perceptibly slows the agent. For heavy work (full test suite), run async in a background process and surface results elsewhere.

2. **Always exit 0 on the happy path**. Forgetting `exit 0` after a successful branch can accidentally block tools.

3. **Never `exit 2` with a hostile message**. The stderr text is fed back to the model as guidance — write it like an error message the agent should learn from: *"Blocked: file X is read-only per `.agents/rules/protected-paths.md`. Use Y instead."*

4. **Commit `.claude/hooks/`, `.claude/settings.json` hook block, etc.** to Git. Hooks are team policy, not personal preference.

5. **User-level hooks (in `~/.claude/settings.json`) must not assume repo context**. They run in every repo — write defensively.

6. **Do not call MCP servers or tools from hooks** — recursion / re-entry is unsupported and dangerous.

7. **Treat hook scripts as arbitrary code execution paths**: they run with the user's existing shell privileges on every matching event, so any compromise propagates to the whole session (file access, network, secrets in env). **Review every hook script the way you would a shell function you `source` from your shell rc** — including dependencies pulled in by the script. Pin script paths (`.claude/hooks/...`) — never `eval` JSON from stdin into shell, and reject hook PRs as carefully as auth-related PRs.

### Layering with other dimensions

| Concern | Right home |
|---|---|
| "Don't edit `vendor/`" advisory | AGENTS.md / Rules |
| "Don't edit `vendor/`" enforced | Hook (`PreToolUse` `matcher: Edit`, check path, exit 2) |
| "Run prettier after every edit" | Hook (`PostToolUse`) |
| "After all changes, run `npm test`" | Skill (workflow) — too heavy for a hook |
| "Block secret commits" | Pre-commit git hook (outside agent) + `PreToolUse` for `Bash(git commit:*)` as defense in depth |

## 7.4 Per-tool Notes

### Claude Code

- 💡 Hooks block lives in `.claude/settings.json` (project) or `~/.claude/settings.json` (user) — same schema
- 💡 `matcher` accepts tool names or regex: `"Bash"`, `"Edit|Write"`, `"*"` (all)
- 💡 Hook stdin payload includes: `tool_name`, `tool_input`, `session_id`, `transcript_path`
- 💡 Common env vars set by Claude: `$CLAUDE_TOOL_FILE_PATH`, `$CLAUDE_SESSION_ID`
- ⚠️ Hooks defined in both project and user settings **all run** — project does not shadow user
- ⚠️ Hook failures are not retried — make scripts idempotent
- 💡 `/hooks` slash command shows registered hooks and recent invocations

### opencode

- 💡 **Plugins (not shell hooks)**: written in JS/TS, async-native, can subscribe to 25+ events and even register custom tools
- 💡 Local plugins go in `.opencode/plugins/` (project) or `~/.config/opencode/plugins/` (global); npm packages via `"plugin": [...]` in `opencode.json`
- 💡 Load order: global config → project config → global plugins dir → project plugins dir; **all hooks run in sequence** (no shadowing)
- 💡 Plugin can ship a sidecar SKILL.md to teach the agent how to use its registered tools
- ⚠️ Bun is used to install plugin dependencies at startup (`bun install` auto-runs if `.opencode/package.json` exists)
- 💡 `experimental.session.compacting` is the only place to alter context compaction — strong lever for long sessions

### Cursor

- 💡 Hooks are newer (added 2026) — feature parity with Claude is ~80%
- ⚠️ Editing `hooks.json` requires Reload Window (Cmd+Shift+P)
- 💡 Background Agents respect hooks too (great for CI-side enforcement)

### Codex

- ✅ **Native hooks, stable** since v0.117 (PreToolUse / PostToolUse + UserPromptSubmit; SessionStart/Stop from v0.114; SubagentStart/Stop, PreCompact/PostCompact, and **PermissionRequest** added later). Feature flag `[features].hooks = true` is the default; the legacy `codex_hooks` key is a deprecated alias
- 💡 **Schema is intentionally Claude-compatible**: same `hooks.json` skeleton, same `matcher` + `type: "command"` shape, same stdin JSON contract, same exit-code 2 = block semantics → one shell script can serve both Codex and Claude unchanged
- 💡 **`PermissionRequest` is Codex-only** — fires only when Codex is about to surface an approval prompt to the user; useful to auto-approve / auto-deny based on policy without touching `PreToolUse`
- ⚠️ **Matcher canonical names** are `Bash`, `apply_patch`, and `mcp__server__tool`. File-edit aliases `Edit` / `Write` are accepted for the `apply_patch` matcher, but the stdin payload still reports `tool_name: "apply_patch"` — write hook logic against canonical names, not aliases
- ⚠️ **Bash bridge** (Codex 0.130+): most file edits actually route through `Bash` rather than `apply_patch` / `Edit` / `Write`. The recommended `PreToolUse` / `PostToolUse` matcher is `Bash|apply_patch|mcp__.*` if you want to catch all edits
- ⚠️ **No `.codex/hooks.json` in the repo**: project-scoped policy is delivered via (a) **plugin bundle** (`hooks/hooks.json` inside an installable plugin) or (b) **`requirements.toml`** (managed bundle the user explicitly trusts). User-level hooks always live at `~/.codex/hooks.json` or `~/.codex/config.toml [hooks]`
- 💡 `PreToolUse` supports `updatedInput` to **mutate** a tool call (e.g. rewrite the command line) — Claude doesn't have this lever
- 💡 Sandbox + `approval_policy` remain a useful second layer for blast-radius limiting — see [`settings.md`](settings.md) §8.3 — but hooks now cover the "block / log / format" use cases that previously required external glue

### Trae

- ❌ **Still no native hooks** as of 2026-06. Multiple open feature requests track this work:
  - [Trae-AI/TRAE#2436](https://github.com/Trae-AI/TRAE/issues/2436) — Lifecycle hooks for Builder/Agent mode
  - [bytedance/trae-agent#397](https://github.com/bytedance/trae-agent/issues/397) — Lifecycle hooks for external tool integration
  - [forum.trae.cn #18062](https://forum.trae.cn/t/topic/18062) — `beforeToolCall` Hook API
- 💡 In-IDE permissions live in GUI prompts only — no programmatic block / mutate
- 💡 Until hooks land, fall back to **git pre-commit + CI** for team policy enforcement; treat Trae as "no agent-runtime enforcement available"

### Cross-tool defense in depth

There is no fully portable hook format, but **Claude + Codex share enough schema that one shell script + one `hooks.json` skeleton covers both**. For policies that must hold across all five tools, layer:

1. **Git pre-commit / pre-push hooks** — catches at commit time regardless of which agent edited (the only layer that works for Trae)
2. **CI checks** — final gate, catches anything that slipped through
3. **Tool-specific agent-runtime hooks**: Claude + Codex (shared script), opencode (JS/TS plugin), Cursor (shell)
4. **Sandbox modes** as blast-radius limiter (Codex; opencode permission system) — complementary to hooks, not a replacement
5. **AGENTS.md advisory rules** as documentation of intent

Hooks are the **only mechanical enforcement at agent runtime** for the four tools that support them; everything else is either pre-runtime (git/CI) or advisory (AGENTS.md / Rules). Trae remains the gap that requires pre-runtime enforcement only.
