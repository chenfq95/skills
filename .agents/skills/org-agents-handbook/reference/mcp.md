# MCP (Model Context Protocol)

> This file is the full survey of the **MCP** dimension for [SKILL.md](../SKILL.md).

## 4.1 Capability Comparison

| Dimension | Claude Code | Codex | Cursor | opencode | Trae |
|---|---|---|---|---|---|
| Project-level config | `.mcp.json` (repo root) | `.codex/config.toml` | `.cursor/mcp.json` | `opencode.json` `mcp` block (root) | `.trae/mcp.json` ⚠️ |
| User-level config | `~/.claude.json` | `~/.codex/config.toml` | `~/.cursor/mcp.json` | `~/.config/opencode/opencode.json` `mcp` block | OS-specific path |
| Number of scopes | 3 (local / project / user) | 2 (project / user) | 2 (project / user) | 2 (project / user); also remote `.well-known/opencode` for org defaults | 2 (project / user) |
| Config format | JSON | TOML | JSON | JSON (nested in `opencode.json`) | JSON |
| Project-level committed to Git | ✅ designed for team sharing | ✅ | ✅ | ✅ | ✅ |
| Project-level stability | ✅ stable | ✅ stable | ✅ stable | ✅ stable | ⚠️ **experimental / Beta** |
| Priority (same-name conflict) | local > project > user | project > user > system | project > global | inline env > project > global > remote / managed | project > global |
| Env variable interpolation | ✅ | ✅ | ✅ `${env:NAME}` `${workspaceFolder}` | ✅ via per-server `environment` table | ✅ `${workspaceFolder}` |
| CLI management commands | `claude mcp add/list/remove` | `codex mcp add/list/login` | UI + edit file | edit `opencode.json` directly | UI + edit file |
| Remote SSE / HTTP | ✅ | ✅ | ✅ | ✅ `type: "remote"` + OAuth support | ✅ |
| Enable / disable without removing | ✅ | ✅ | ✅ | ✅ `"enabled": false` toggle | ✅ |
| Per-agent enable / disable | ❌ | ❌ | ❌ | ✅ disable globally, re-enable in `agent.<name>.tools` | ❌ |

## 4.2 Config File Examples

### Claude Code `.mcp.json`

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${env:GITHUB_TOKEN}"
      }
    }
  }
}
```

### Codex `~/.codex/config.toml` (or project `.codex/config.toml`)

```toml
[mcp_servers.github]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]

[mcp_servers.github.env]
GITHUB_PERSONAL_ACCESS_TOKEN = "${env:GITHUB_TOKEN}"
```

### Cursor `.cursor/mcp.json`

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "python",
      "args": ["${workspaceFolder}/tools/mcp_server.py"],
      "env": {
        "API_KEY": "${env:API_KEY}"
      }
    },
    "remote-api": {
      "url": "https://api.example.com/mcp",
      "headers": {
        "Authorization": "Bearer ${env:TOKEN}"
      }
    }
  }
}
```

### Trae `.trae/mcp.json` (⚠️ experimental)

```json
{
  "mcpServers": {
    "supabase_local": {
      "command": "supabase",
      "args": ["mcp"],
      "env": {
        "SUPABASE_ACCESS_TOKEN": "${env:SUPABASE_TOKEN}"
      }
    }
  }
}
```

### opencode `opencode.json` (project or `~/.config/opencode/opencode.json` for global)

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "github": {
      "type": "local",
      "command": ["bunx", "@modelcontextprotocol/server-github"],
      "environment": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
      },
      "enabled": true
    },
    "company-docs": {
      "type": "remote",
      "url": "https://docs.example.com/mcp",
      "headers": { "Authorization": "Bearer ${env:DOCS_TOKEN}" },
      "timeout": 8000,
      "enabled": true
    }
  },
  // Disable all tools from an MCP server globally, then re-enable per agent
  "tools": { "github_*": false },
  "agent": {
    "release-bot": {
      "tools": { "github_*": true }
    }
  }
}
```

**Notes specific to opencode**:
- Key is `mcp` (not `mcpServers`)
- Local servers: `type: "local"` + `command: [...]` (array, not string)
- Remote: `type: "remote"` + `url` + optional `headers` / `oauth` / `timeout` (ms, default 5000)
- `enabled: false` is a non-destructive disable
- Tool gating via the top-level `tools` map (wildcard patterns); per-agent overrides via `agent.<name>.tools`

## 4.3 Project Config Best Practices

1. **Commit `.mcp.json`-like files to Git, but reference secrets via env variables.** Interpolation syntax is **not portable** — pick the right form per tool:

   | Tool | Syntax in config file | Notes |
   |---|---|---|
   | Claude Code | `"${env:GITHUB_TOKEN}"` (JSON) | `env:` prefix required |
   | Cursor | `"${env:GITHUB_TOKEN}"` (JSON); also `${workspaceFolder}` | same prefix as Claude |
   | Codex | `"${env:GITHUB_TOKEN}"` inside TOML `[mcp_servers.*.env]` table | works in any string value |
   | opencode | `"${GITHUB_TOKEN}"` (JSON) — **no `env:` prefix** | shell-style interpolation |
   | Trae | `"${workspaceFolder}"` only | env-var interpolation is **not** supported on Trae; if you need it, fall back to OS-level env injection before launching the IDE |

   Same intent across all five, but the exact string differs — copying a config from one tool to another usually means rewriting the interpolation tokens.

2. **Add `.env`, `.cursor/.env`, etc. (any helper file with real values) to `.gitignore`**

3. **Put project-specific servers (e.g. project DB) at project level**; put generic tools (GitHub, web search) at user level

4. **After any config change, you must restart / reload the tool**:
   - Cursor: Cmd+Shift+P → "Reload Window"
   - Claude Code: restart session, or `/mcp reconnect`
   - Codex: restart session (TUI loads only once at startup)
   - Trae: Reload Window

## 4.4 Per-tool Notes

### Claude Code

- ⚠️ **Do NOT treat Claude Desktop's `claude_desktop_config.json` as Claude Code config** — they are different apps
- 💡 Migrate from Desktop: `claude mcp add-from-claude-desktop`
- ⚠️ The first time a project-scope server is loaded, the user is **prompted to approve it** — this is an intentional safety gate; do not bypass
- 💡 Specify the scope explicitly: `claude mcp add -s {local|project|user}`
- 💡 `/mcp` shows connection status; `/mcp reconnect` reconnects

### Codex

- 💡 **Single config stack**: CLI, VS Code, and Desktop all read the same `config.toml`
- 💡 Manage via `codex mcp add/list/login`, which writes the TOML for you
- ⚠️ Every MCP server injects its tool schema into context — disable unused ones to save tokens
- 💡 Priority: CLI flags → profile → project config → user config → system default

### Cursor

- 💡 **`mcp.json` format is nearly identical to Claude Desktop**, so configs are reusable
- ⚠️ Must Reload Window after editing (Cmd+Shift+P)
- 💡 Project `.cursor/mcp.json` and global `~/.cursor/mcp.json` are auto-merged; project wins on same-name conflict
- 💡 Settings → MCP panel shows live connection status, error details, and tool counts
- 💡 Enterprises can register MCP programmatically via the extension API, no `mcp.json` edits required

### Trae

- ⚠️ **Project-level MCP is experimental / Beta**; some docs explicitly warn "agent cannot access project-level MCP servers" — prefer global config in production
- 💡 Enable project-level MCP: Settings → MCP → toggle "Enable project-level MCP"
- 💡 Global path varies by OS:
  - macOS: `~/Library/Application Support/Trae/User/mcp.json`
  - Windows: `%APPDATA%\Trae\User\mcp.json`
  - Linux: `~/.config/Trae/User/mcp.json`
- 💡 Built-in MCP marketplace with one-click install
- 💡 Only supports `${workspaceFolder}` interpolation — less flexible than Cursor

### opencode

- 💡 **MCP config is nested inside `opencode.json`** (not a separate file like other tools) — same file holds agents, commands, plugins, models, providers, permissions, mcp
- 💡 **First-class per-agent gating**: globally disable a noisy MCP server's tools (`"tools": { "myserver_*": false }`) and re-enable only for the agent that needs it (`agent.<name>.tools.myserver_*: true`) — saves context tokens for agents that don't need that MCP
- 💡 **Remote MCP supports OAuth** natively via the `oauth` object — Claude / Codex / Cursor only support bearer headers
- 💡 **Use `bunx`** (not `npx`) as the command runner — opencode ships with Bun and starts servers faster
- 💡 The schema URL `https://opencode.ai/config.json` gives full JSON schema autocomplete in editors
- 💡 **Org-level distribution**: `.well-known/opencode` lets an organization push default config (including MCP) to all users — useful for enterprise rollouts
- 💡 AGENTS.md can document MCP usage hints (e.g. *"When you need to search docs, use the `context7` MCP server"*) — opencode reads them naturally as part of the always-on rules
