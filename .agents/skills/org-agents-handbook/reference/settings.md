# Settings / Permissions / Sandbox

> This file is the full survey of the **Settings / Permissions / Sandbox** dimension for [SKILL.md](../SKILL.md).
>
> **What it is**: the runtime configuration that controls **what the agent is allowed to do** (tool allowlists, file write permissions, network access), **how the agent is approved** (auto / on-failure / always-ask), and **how it executes** (sandbox mode, env vars, statusline, model defaults). The single most under-configured dimension — most production incidents are permission misconfigurations, not bad prompts.

## 8.1 Capability Comparison

| Dimension | Claude Code | Codex | Cursor | opencode | Trae |
|---|---|---|---|---|---|
| Project-level config file | `.claude/settings.json` | `.codex/config.toml` | `.cursor/environment.json` (background) + UI | `opencode.json` (repo root) | UI only |
| User-level config file | `~/.claude/settings.json` | `~/.codex/config.toml` | UI (synced) | `~/.config/opencode/opencode.json` | UI only |
| Local-only override | `.claude/settings.local.json` (gitignored) | `[profiles.*]` per-profile | Local UI overrides | `OPENCODE_CONFIG` env var, or inline `OPENCODE_CONFIG_CONTENT` | n/a |
| Permission model | allow/deny/ask **per tool pattern** | **sandbox mode + approval policy** combo | allowlist of bash commands + per-tool toggles | **per-tool allow/deny/ask + per-pattern bash matchers, also per-agent override** | GUI prompts per action |
| Sandbox mode | n/a (uses permission patterns) | ✅ `read-only` / `workspace-write` / `danger-full-access` | ✅ Auto Mode + allowlist | ⚠️ no OS-level sandbox; relies on permission gating | ⚠️ implicit prompts |
| Approval policy | "ask" patterns | ✅ `never` / `on-failure` / `on-request` / `untrusted` | Auto Mode toggle | `"ask"` permission action; per-tool | GUI |
| Env vars in config | ✅ `env: {KEY: "..."}` | ✅ `[env]` table | `.cursor/environment.json` `env` | Per-MCP `environment` table; agent process inherits shell env | n/a |
| Statusline customization | ✅ `statusLine` (shell command) | ❌ | ✅ `statusline` | ✅ via plugin (`statusline` config + plugin event) | ❌ |
| Per-project profiles | ❌ | ✅ `[profiles.*]` | ❌ | ✅ multiple `agent.<name>` blocks act as profiles | ❌ |
| Background / cloud agent config | n/a | `[profiles.*]` for headless | `.cursor/environment.json` | Non-interactive mode (`opencode run` with flags) | n/a |
| Org-level / admin-pushed config | ❌ | ❌ | Enterprise dashboard | ✅ remote `.well-known/opencode` + macOS managed `.mobileconfig` (MDM) | ❌ |
| Cross-tool standard | ❌ none — each tool's own schema | ❌ | ❌ | ❌ | ❌ |

> Settings is the **least portable** dimension. Even concepts like "allow `npm test`" map to wildly different mechanisms per tool.
>
> **opencode has the deepest config layering** of all five tools (8 levels: org remote → user → env override → project → `.opencode/` dirs → inline env → managed dir → MDM), designed for enterprise rollout.

## 8.2 Permission Model — Per-tool Detail

### Claude Code: Pattern allowlists

```jsonc
// .claude/settings.json
{
  "permissions": {
    "allow": [
      "Read(**)",
      "Edit(./src/**)",
      "Bash(npm test:*)",
      "Bash(npm run lint:*)",
      "Bash(git status:*)",
      "Bash(git diff:*)"
    ],
    "deny": [
      "Edit(./.git/**)",
      "Edit(./node_modules/**)",
      "Bash(rm -rf:*)",
      "Bash(sudo:*)"
    ],
    "ask": [
      "Bash(git push:*)",
      "Bash(npm publish:*)"
    ]
  },
  "env": {
    "NODE_ENV": "development"
  }
}
```

**Pattern syntax**:
- `Tool(pattern)` — pattern is glob for file tools, prefix-with-`:*` for Bash
- `**` matches any path
- Order: `deny` wins > `ask` > `allow`; if no match, falls back to default (ask)

### Codex: Sandbox + Approval Policy

Two orthogonal axes — combine them:

| `sandbox_mode` | Effect |
|---|---|
| `read-only` | Cannot write, cannot execute, cannot network. Safest default for exploration |
| `workspace-write` | Can edit files **within workspace**, can run commands in workspace. No network. **Recommended production default** |
| `danger-full-access` | No sandbox. Full host access. **Only for CI/headless under your control** |

| `approval_policy` | Effect |
|---|---|
| `never` | Never asks user. Use with `read-only` for unattended explore, or `danger-full-access` only in CI |
| `on-failure` | Asks only when a tool errors. Good for "trust but verify" |
| `on-request` | Agent decides when to ask. Most balanced default |
| `untrusted` | Asks on every potentially-mutating operation. Use for sensitive repos |

```toml
# ~/.codex/config.toml or project .codex/config.toml
sandbox_mode = "workspace-write"
approval_policy = "on-request"

[profiles.ci]
sandbox_mode = "workspace-write"
approval_policy = "never"
model = "gpt-5-codex"

[profiles.prod-debug]
sandbox_mode = "read-only"
approval_policy = "untrusted"

[env]
NODE_ENV = "production"
```

**Activate a profile**: `codex --profile ci` (CLI) or set `CODEX_PROFILE=ci`.

### Cursor: Auto Mode + Allowlist

```jsonc
// Cursor settings (UI) — exported shape
{
  "cursor.chat.autoMode": true,
  "cursor.chat.allowedCommands": [
    "npm test",
    "npm run lint",
    "git status",
    "git diff"
  ],
  "cursor.chat.deniedCommands": [
    "rm -rf",
    "sudo",
    "npm publish"
  ]
}
```

- **Auto Mode ON** → all whitelisted commands run without confirmation
- **Auto Mode OFF** → every command requires click-to-approve
- Per-tool toggles (Read, Edit, Terminal, MCP) are also UI-level

### Trae: GUI prompts only

No declarative permission file. Every potentially-mutating tool invocation triggers a GUI prompt unless you've previously chosen "Allow always for this command" (which is stored in user IDE settings, not the repo).

**Implication**: Trae cannot encode team-wide permission policy in the repo. Use git pre-commit hooks + CI as the real gate.

### opencode: per-tool + per-pattern + per-agent

opencode has the most granular permission model of the five tools. Permissions live in `opencode.json`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "permission": {
    "edit": "allow",
    "bash": {
      "*": "ask",
      "git status": "allow",
      "git diff*": "allow",
      "git log*": "allow",
      "npm test*": "allow",
      "rm -rf*": "deny",
      "sudo*": "deny"
    },
    "webfetch": "ask",
    "skill": {
      "*": "allow",
      "internal-*": "deny",
      "experimental-*": "ask"
    }
  },
  "agent": {
    "reviewer": {
      "permission": {
        "edit": "deny",
        "bash": { "*": "deny", "git diff*": "allow", "git log*": "allow" },
        "webfetch": "deny"
      }
    }
  }
}
```

- **Permission keys**: `read`, `edit`, `glob`, `grep`, `list`, `bash`, `task`, `external_directory`, `lsp`, `skill` — each accepts shorthand (`"allow" | "ask" | "deny"`) or a pattern map
- **Pattern matching** applies to bash commands, skill names, and MCP tool names equally: `"mymcp_*": "deny"` denies every tool from a given MCP server
- **Per-agent override**: a stricter agent (e.g. reviewer) can deny what the global config allows; a more privileged agent (e.g. release-bot) can re-enable specific patterns
- **No OS-level sandbox**: opencode does not run inside a Seatbelt / landlock sandbox like Codex — the permission model is the only gate. For strong isolation, run opencode inside a container or VM

## 8.3 Sandbox Model (Codex) — Deeper Detail

Codex is the only tool with a true OS-level sandbox. Modes map to platform mechanisms:

- **macOS**: `sandbox-exec` profile (Seatbelt) — restricts writes to workspace, denies network
- **Linux**: `landlock` + `seccomp` — same effect
- **Windows**: limited; effectively advisory

```toml
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = false        # default
exclude_tmpdir_env_var = false
exclude_slash_tmp = false
writable_roots = ["./build", "./node_modules/.cache"]
```

**Common pitfalls**:
- `network_access = false` blocks `npm install`. Either flip to `true` or pre-install dependencies and run with the network off
- `writable_roots` is **additive** to workspace — use it to allow build caches outside repo

## 8.4 Background / Cloud Agents — `.cursor/environment.json`

Cursor's background agents (and cloud agents) run in an ephemeral container that needs explicit setup:

```jsonc
// .cursor/environment.json
{
  "snapshot": "ubuntu-22.04",
  "install": "npm ci && npm run build",
  "terminals": [
    { "name": "dev-server", "command": "npm run dev" }
  ],
  "env": {
    "NODE_ENV": "development",
    "API_BASE_URL": "https://api.staging.example.com"
  }
}
```

- `snapshot` — base image; agent waits for it to be ready
- `install` — one-time setup command; cached across runs of the same snapshot
- `terminals` — long-running processes the agent can attach to (dev server, watch mode)
- `env` — env vars the agent process sees; **do not put secrets here**, reference them via `${env:NAME}` and configure secrets in Cursor settings

**Commit `.cursor/environment.json` to Git** — it's team config, not personal.

## 8.5 Project Config Best Practices

### Layering: project, user, local

| File | Committed | Purpose |
|---|---|---|
| `.claude/settings.json` | ✅ | Team policy: permissions, hooks, statusline, env defaults |
| `.claude/settings.local.json` | ❌ (gitignored) | Personal overrides on top of project (developer-specific keys, looser permissions for explore) |
| `~/.claude/settings.json` | n/a | User defaults across all repos |
| `.codex/config.toml` (project) | ✅ | Team profile, model, sandbox mode for this repo |
| `~/.codex/config.toml` | n/a | Personal default + profiles |
| `.cursor/environment.json` | ✅ | Team config for background agents |
| `opencode.json` (project) | ✅ | Team config for opencode: permissions, agents, MCP, plugins, providers |
| `~/.config/opencode/opencode.json` | n/a | User defaults across all opencode repos |
| `.opencode/` directories | ✅ | Per-repo agents/, commands/, skills/, plugins/, modes/ |

### Critical rules

1. **Always commit project settings; always gitignore local settings**. The matrix of files above is intentional — designed so team policy is shared while personal exceptions don't leak.

2. **`deny` > `ask` > `allow`**. Write deny rules for anything destructive (`rm -rf`, `sudo`, `git push --force`, `npm publish`, `kubectl delete`) at project level. Never trust user-level for these.

3. **Default to `workspace-write` + `on-request` (Codex)** for human-supervised dev. Promote to `never` only when paired with `read-only` or in CI under your control.

4. **Secrets via env var indirection, never inline.** Interpolation syntax is per-tool — see [`mcp.md`](mcp.md) §4.3 for the syntax table. Claude / Cursor / Codex use `${env:NAME}`; opencode uses `${NAME}`; Trae does not support env interpolation at all and needs OS-level env injection.
   ```json
   "env": { "GITHUB_TOKEN": "${env:GITHUB_TOKEN}" }   // ✅ Claude / Cursor / Codex
   "env": { "GITHUB_TOKEN": "ghp_xxxxx" }              // ❌ committed to Git
   ```

5. **Mirror the permission spirit across tools that can't share format**. If Claude's `permissions.deny` blocks `Bash(rm -rf:*)`, then on Codex set `sandbox_mode = "workspace-write"` (which blocks system writes) and on Cursor add `rm -rf` to `deniedCommands`. **Same intent, three configurations** — there is no DRY here.

6. **Document the policy in AGENTS.md**, even though it's enforced via settings. Future contributors need to know **why** the permission set is what it is.

7. **Background-agent setup belongs in `.cursor/environment.json`, not in the agent's prompt**. Don't ask the agent to run `npm install` — pre-install via `install:` so the agent starts in a usable state.

8. **Test permission denials**. Periodically try `Bash(sudo ls)` or `Edit(./.git/HEAD)` in each tool to verify your deny rules still bite. Permission systems drift silently.

## 8.6 Per-tool Notes

### Claude Code

- 💡 Permission patterns use **glob** for file paths and **`prefix:*`** for Bash — they are not the same syntax
- 💡 `/permissions` slash command opens an editor for the live permission set
- ⚠️ `allowed-tools` in skill/command frontmatter is separate from `permissions` in settings — frontmatter is **pre-approval list**, settings is **gate**. The intersection wins
- 💡 `statusLine` runs a shell command on every render — keep it < 100ms or it visibly lags the UI
- 💡 `additionalDirectories` in settings lets the agent see paths outside the project root (use sparingly)
- ⚠️ Local settings (`settings.local.json`) shallow-merges with project — nested arrays replace, not append. Surprising for `permissions.allow`

### Codex

- 💡 **Single config file at `~/.codex/config.toml` is read by CLI, VS Code extension, and Desktop** — no per-IDE drift
- 💡 `--profile <name>` flag swaps the entire `[profiles.<name>]` block in; very clean for CI vs local
- ⚠️ `sandbox_mode` changes take effect on **new sessions only** — current TUI session uses what was loaded at startup
- 💡 `[env]` table is injected into every tool invocation; combine with `${env:NAME}` interpolation for secrets
- ⚠️ On macOS, `workspace-write` denies network by default — `npm install` fails silently if you don't set `network_access = true` or pre-install

### Cursor

- 💡 Most settings live in the UI / synced settings; very few file-based
- 💡 `.cursor/environment.json` is the **only repo-committable runtime config** (besides `.cursor/rules/` and `.cursor/mcp.json`)
- ⚠️ "Auto Mode" is a single global switch — there is no allowlist that's auto-on for safe commands and prompt for the rest. Either everything in the allowlist auto-runs, or nothing does
- 💡 Background Agents bill separately and use `.cursor/environment.json` as the source of truth for their environment
- 💡 Settings → Privacy controls telemetry / training opt-out — set at org level via MDM if you ship enterprise

### Trae

- ⚠️ **No file-based permission system**. All gates are GUI prompts cached in user-IDE storage
- 💡 Team policy can only be enforced via git pre-commit hooks + CI — not at agent runtime
- 💡 International (`~/.trae/`) vs China (`~/.trae-cn/`) builds have separate settings — beware of cross-build assumptions

### opencode

- 💡 **8-level config priority** (lowest to highest, last wins):
  1. Remote `.well-known/opencode` (org defaults)
  2. Global `~/.config/opencode/opencode.json`
  3. `OPENCODE_CONFIG` env var (custom config path)
  4. Project `opencode.json`
  5. `.opencode/` directories (agents/, commands/, skills/, plugins/, modes/)
  6. `OPENCODE_CONFIG_CONTENT` env var (inline JSON)
  7. Managed `/Library/Application Support/opencode/` (macOS, admin-controlled)
  8. macOS managed preferences via MDM `.mobileconfig` — **highest, user cannot override**
- 💡 **Single JSON file** holds agents, commands, MCP, plugins, permissions, models, providers, themes — easier to audit than the multi-file scatter of other tools
- 💡 **Plural subdirectory convention is current**: `agents/`, `commands/`, `skills/`, `plugins/`, `modes/`, `tools/`, `themes/`; singular forms (`agent/`, `command/`, …) still load for backwards compat
- 💡 **No OS-level sandbox** like Codex; rely on `permission` + container isolation for production
- 💡 **MDM-pushed settings** are unique to opencode in this group — invaluable for enterprise endpoint policy
- 💡 **Use the schema**: `"$schema": "https://opencode.ai/config.json"` at the top of `opencode.json` enables full editor autocomplete + validation
- ⚠️ Local plugins under `.opencode/plugins/` can declare npm dependencies in `.opencode/package.json` — opencode runs `bun install` at startup; review dependencies as carefully as you'd review hook scripts

### Defense-in-depth recommendation

Because no tool's permission system is portable, the only durable team-wide policy is **multi-layered**:

1. **Agent runtime gates** (Claude permissions, Codex sandbox, Cursor allowlist, Trae GUI) — first line, tool-specific
2. **Git pre-commit hooks** — catches anything that escaped the agent
3. **CI quality gates** — final line, regardless of which agent or human pushed
4. **AGENTS.md documentation** — captures intent so future contributors know what the layers are protecting against

Single-layer policy (e.g. "we have a deny rule in Claude settings") will fail the moment someone opens the same repo in Codex or Trae.
