# Claude Code / Codex / Cursor / Trae / opencode AI 编程工具配置在Monorepo中的最佳落地实践

> **覆盖工具**：Claude Code（Anthropic）/ OpenAI Codex / Cursor / Trae（ByteDance）/ opencode（sst）
> **覆盖维度**：AGENTS.md / Rules / Skills / Commands / Subagents / Hooks / MCP / Settings·Permissions·Sandbox
> **数据来源**：五款工具 2026 年最新官方文档（code.claude.com、developers.openai.com、cursor.com/docs、docs.trae.ai、opencode.ai/docs）
> **更新时间**：2026/06
>

---

## 目录

- [全局速查矩阵](#-全局速查矩阵)
- [一、AGENTS.md 项目说明文件](#一agentsmd-项目说明文件)
- [二、Rules 规则系统](#二rules-规则系统)
- [三、Skills 技能系统](#三skills-技能系统)
- [四、Commands（Slash Commands，legacy）](#四commandsslash-commandslegacy)
- [五、Subagents（子智能体）](#五subagents子智能体)
- [六、Hooks（事件钩子）](#六hooks事件钩子)
- [七、MCP（Model Context Protocol）](#七mcpmodel-context-protocol)
- [八、Settings / Permissions / Sandbox](#八settings--permissions--sandbox)
- [九、Monorepo 完整最佳实践](#九monorepo-完整最佳实践)
- [十、每家工具关键坑点速查](#十每家工具关键坑点速查生产环境必看)
- [十一、TL;DR 一图流总结](#十一tldr--一图流总结)

---

## 🔍 全局速查矩阵

| 维度 | Claude Code | Codex | Cursor | opencode | Trae |
|---|---|---|---|---|---|
| **AGENTS.md 原生读取** | ❌（需 `@import`） | ✅ 原生 | ✅ 原生（根 + 嵌套） | ✅ 原生（向上 walk，含 CLAUDE.md fallback） | ⚠️ 需开关 |
| **Rules 系统路径** | `.claude/rules/` | 无（用 AGENTS.md） | `.cursor/rules/*.mdc` | 无（用 AGENTS.md + `opencode.json` `instructions`） | `.trae/rules/` |
| **Rules 激活模式数** | 2（始终 / paths） | 1（始终） | 4（始终/globs/智能/手动） | 1（始终）+ per-agent override | 4（同 Cursor） |
| **Skills 系统路径** | `.claude/skills/` | `.agents/skills/` | `.cursor/skills/` + `.agents/skills/` | `.opencode/skills/` + `.claude/skills/` + `.agents/skills/`（**6 路径全原生**） | `.trae/skills/` |
| **`.agents/skills/` 跨工具兼容** | ❌ | ✅ 原生 | ✅ v2.4+ | ✅ 原生（不是 fallback） | ❌（需 symlink 或 CLI 同步到 `.trae/skills/`） |
| **Commands（slash 命令）路径** | `.claude/commands/` ⚠️ legacy | — | — | `.opencode/commands/`（plural 当前）/ `command/`（legacy compat） | — |
| **Subagents（独立 context）路径** | `.claude/agents/<n>.md` | ❌（仅 SDK Task） | Custom Modes（GUI） | `.opencode/agents/<n>.md` + `opencode.json` `agent` 块 | persona（GUI） |
| **Hooks（事件钩子）路径** | `.claude/settings.json` `hooks` 块（shell 脚本） | `~/.codex/hooks.json` / `~/.codex/config.toml [hooks]`（shell 脚本，**与 Claude 兼容**）；项目级走 plugin bundle 或 `requirements.toml` | `.cursor/hooks.json` + `.cursor/hooks/`（shell 脚本） | `.opencode/plugins/*.ts`（**JS/TS plugin**，非 shell） | ❌（FR 已开未实现） |
| **MCP 项目级配置文件** | `.mcp.json` | `.codex/config.toml` | `.cursor/mcp.json` | `opencode.json` `mcp` 块（与其它配置同文件） | `.trae/mcp.json`（实验性） |
| **MCP 用户级配置文件** | `~/.claude.json` | `~/.codex/config.toml` | `~/.cursor/mcp.json` | `~/.config/opencode/opencode.json` | `~/Library/.../Trae/User/mcp.json` |
| **Settings 项目级文件** | `.claude/settings.json` + `.local.json` | `.codex/config.toml` | `.cursor/environment.json` + UI | `opencode.json`（聚合全部配置） | 仅 UI |
| **权限模型** | allow/deny/ask 模式 | sandbox + approval_policy | Auto Mode + 白名单 | per-tool + per-pattern + per-agent（最细粒度） | GUI 提示 |
| **真 OS 级 sandbox** | ❌ | ✅ Seatbelt / landlock | ⚠️ Auto Mode | ❌（靠 permission gating） | ❌ |
| **Background / Cloud Agent** | n/a | `[profiles.*]` headless | `.cursor/environment.json` | `opencode run` 非交互模式 | n/a |
| **配置层级数** | 3（local/project/user） | 2~3（含 profiles） | 2（project/user） | **8 层**（含 remote `.well-known/opencode` + MDM） | 2 |
| **Monorepo 嵌套 AGENTS.md** | ⚠️ 不自动读 | ✅ 完整 | ✅ 子目录覆盖 | ✅ 向上 walk | ⚠️ 主要根级 |
| **子 Agent 继承规则** | ❌ | ✅ | — | ❌（subagent 干净启动，permission 单独配） | — |
| **配置文件格式** | JSON + Markdown | TOML + Markdown | JSON + MDC | JSON + Markdown + **TypeScript plugin** | JSON + Markdown |

---

## 一、AGENTS.md 项目说明文件

### 1.1 能力对比

| 维度 | Claude Code | Codex | Cursor | opencode | Trae |
|---|---|---|---|---|---|
| 是否原生 | ❌ | ✅ 主文件 | ✅ 原生 | ✅ 主文件 | ⚠️ 兼容（默认关） |
| 桥接方式 | `CLAUDE.md` 用 `@AGENTS.md` | — | — | 无 AGENTS.md 时自动读 `CLAUDE.md`；全局也 fallback `~/.claude/CLAUDE.md` | Settings 勾选开关 |
| 根级文件 | `CLAUDE.md` | `AGENTS.md` | `AGENTS.md` | `AGENTS.md`（或 `CLAUDE.md` 作 fallback） | `AGENTS.md`（开启开关后直接读） |
| 全局 / 用户级文件 | `~/.claude/CLAUDE.md` | — | — | `~/.config/opencode/AGENTS.md` | — |
| 子目录嵌套 | ⚠️ 需 Read 主动加载 | ✅ 路径上每层一份 | ✅ 子目录覆盖父目录 | ✅ 从 cwd 向上 walk（类似 Codex） | ⚠️ 弱支持 |
| Override 机制 | — | ✅ `AGENTS.override.md` | — | `opencode.json` `instructions` 数组指向附加文件 | — |
| 大小限制 | 主文件 ≤ 200 行 / 25KB | **32 KiB 静默截断** | 无公开上限 | 无公开上限 | 推荐 < 1000 字符 |
| 优先级规则 | 低层级补充高层级 | 越靠近 cwd 越后置 = 越优先 | 子目录优先 | 本地 > 全局；同级 AGENTS.md > CLAUDE.md | 项目 > 用户 > 默认 |
| `/init` 命令 | ✅ 生成 `CLAUDE.md` | ✅ | ✅ | ✅ 生成 `AGENTS.md` | ❌（手动） |

### 1.2 Monorepo 支持

| 工具 | Monorepo 嵌套行为 |
|---|---|
| **Codex** | 从 Git 根 → cwd 沿路径自动拼接每层 `AGENTS.md`/`AGENTS.override.md`，每层至多一份。后置优先。**最强 Monorepo 支持**。 |
| **Cursor** | 嵌套 `AGENTS.md` 自动按位置 scope（"file at `subproject_A/x/AGENTS.md` is treated as a rule with implicit glob `subproject_A/x/**`"）。子目录优先。**支持度第二**。 |
| **Claude Code** | **不会**自动加载子目录 `CLAUDE.md`/`AGENTS.md`。需要根 AGENTS.md 显式声明子模块路径，由 agent 主动 Read。 |
| **Trae** | Settings 开启开关后读根级 `AGENTS.md`，子目录嵌套支持弱。同样依赖根 AGENTS.md 引导主动 Read。 |

> **结论**：五家原生差异巨大。最佳实践是**子项目就近内嵌 AGENTS.md + 根 AGENTS.md 做 Reference 路由**——既保留 Codex / Cursor / opencode 的自动加载，又用 reference 引导 Claude / Trae 主动 Read，详见 1.3。

### 1.3 项目配置最佳实践

#### 1.3.1 核心思想：两层 × 两块

整个仓库只有 **两层**——项目根（L1）和每个子模块（L2）。每一层都由相同的 **两块** 组成：

- **AGENTS.md**：真源 + 路由入口（在该层 scope 内**始终加载**）
- **`.agents/`**：按需加载的内容，分成 `rules/`（声明性知识）和 `skills/`（操作性工作流）

整章只需记住这张矩阵：

| | AGENTS.md（始终加载块） | `.agents/rules/`（按需，规则） | `.agents/skills/`（按需，工作流） |
|---|---|---|---|
| **L1 — 项目根** | 根 `AGENTS.md`：强约束 + 自身 `.agents/` 引用 + 各子模块路由 | 根 `.agents/rules/*.md`：项目级规则（多个子模块都会查阅） | 根 `.agents/skills/<name>/SKILL.md`：项目级工作流（5 家工具通过 `description` 自动发现） |
| **L2 — 子模块** | `packages/<m>/AGENTS.md`：scope + stack + 局部 `.agents/rules/` 和 `.agents/skills/` 的路由 | `packages/<m>/.agents/rules/*.md`：仅该子模块需要的规则 | `packages/<m>/.agents/skills/<n>/SKILL.md`：仅该子模块需要的工作流（必须显式路由——没有工具会扫嵌套 skill 目录） |

判断一条内容该放哪里，**只需问两个问题**：

1. **是项目级还是子模块级？** → 决定层（L1 vs L2）
2. **是规则还是工作流？** → 决定槽位（`.agents/rules/` vs `.agents/skills/`）

每次会话都必须遵守的项目级强约束**不是"放在某个文件里的规则"**——它们写在**根 AGENTS.md 的正文**里（L1 的始终加载块）。

**发现机制总览**（谁能用什么方式到达每种资源）：

| 资源 | 原生自动加载 | 路由式主动 Read |
|---|---|---|
| L1 根 `AGENTS.md` | Codex / Cursor / opencode（Trae 打开开关后） | Claude 通过 `CLAUDE.md` 中的 `@AGENTS.md` |
| L1 根 `.agents/rules/*` | Claude / Trae：通过把正本桥接到 `.claude/rules/` 与 `.trae/rules/`（目录 symlink）自动加载；Cursor：通过每条规则一份 `.cursor/rules/*.mdc` shim 自动加载。见 §2.3.1 | Codex / opencode——通过根 AGENTS.md 的 **Rules Reference** 表（这两家无原生 rules 系统可桥接） |
| L1 根 `.agents/skills/*` | **5 家原生** 通过 SKILL.md `description`（Codex / Cursor 2.4+ / opencode / Copilot / Gemini） | Claude / Trae——通过桥接到 `.claude/skills/` / `.trae/skills/`（详见 §3.5.2 的跨设备兼容性提示） |
| L2 子模块 `AGENTS.md` | Codex / Cursor / opencode（近端层自动加载） | Claude / Trae——通过根 AGENTS.md 的 **Module Reference Map** |
| L2 子模块 `.agents/rules/*` | **无** | 全部工具——通过该子模块 AGENTS.md 的 **Rules Reference** 表 |
| L2 子模块 `.agents/skills/*` | **无**（没有工具会扫嵌套 skill 目录） | 全部工具——通过该子模块 AGENTS.md 的 **Workflows** 表 |

§1.3.7 列出该方案的优势，§1.3.8 列出实施要点。

#### 1.3.2 推荐目录结构

```
your-repo/
├── AGENTS.md                          # ★ L1 始终加载块：强约束 + 路由
├── CLAUDE.md                          # 一行：@AGENTS.md
│
├── .agents/                           # ── L1 按需加载块（项目级） ────────────────────────
│   ├── rules/                         # 项目级规则（从根 AGENTS.md 路由）
│   │   ├── coding-style.md
│   │   ├── typescript-strict.md
│   │   ├── rest-api-design.md
│   │   └── security-baseline.md
│   └── skills/                        # 项目级工作流（5 家工具自动发现）
│       ├── deploy-prod/SKILL.md
│       └── security-audit/SKILL.md
│
├── packages/                          # ── L2：子模块 ──────────────────────────────────────
│   ├── frontend/
│   │   ├── AGENTS.md                  # L2 始终加载块
│   │   └── .agents/                   # L2 按需加载块
│   │       ├── rules/                 #   一文件一主题
│   │       │   ├── react-conventions.md
│   │       │   └── state-management.md
│   │       └── skills/                #   子模块作用域工作流（必须显式路由）
│   │           ├── update-design-tokens/SKILL.md
│   │           └── new-component/SKILL.md
│   ├── backend/
│   │   ├── AGENTS.md
│   │   └── .agents/
│   │       ├── rules/
│   │       │   └── api-design.md
│   │       └── skills/
│   │           └── regenerate-prisma/SKILL.md
│   └── payments/
│       ├── AGENTS.md
│       └── .agents/
│           ├── rules/
│           │   └── pci-compliance.md
│           └── skills/
│               └── run-pci-audit/SKILL.md
│
└── infra/                             # L2（packages/ 外的另一个子模块）
    ├── AGENTS.md
    └── .agents/
        ├── rules/
        │   └── terraform-style.md
        └── skills/
            └── plan-and-apply/SKILL.md
```

**对称性**：每个子模块（L2）镜像项目根（L1）——同样的两块（`AGENTS.md` 始终加载 + `.agents/rules/` + `.agents/skills/` 按需），同样的路由模式。唯一区别是位置与作用范围。

> Trae 无需额外文件，只要在 Settings → Rules & Skills 勾选 "Include AGENTS.md in the context" 即可直接读根 AGENTS.md。

#### 1.3.3 根 AGENTS.md 模板

**章节骨架**：

```markdown
## 0a. Rules Reference        — 路由到根 .agents/rules/*.md
## 0b. Module Reference Map   — 路由到各子模块 AGENTS.md
## 0c. Tool-specific Loading  — 告知 Claude/Trae 需主动 Read
## 1. Project Overview        — 业务定位、技术栈、关键目录
## 2. Setup & Run             — 包管理器、安装/构建/运行命令
## 3. Test & Lint             — 必须跑的验证命令
## 4. Code Style              — 语言/框架/命名/import 顺序
## 5. Architecture Rules      — 模块边界、跨包调用约束
## 6. Do Not Touch            — 禁区文件列表
## 7. Commit & PR             — 提交规范、PR 大小约束
```

**完整可粘贴示例**：

```markdown
# AGENTS.md

## 0a. Rules Reference

The following project-level rules live under `.agents/rules/` and are NOT
auto-loaded by any tool — **Read on demand** when working in the matching
domain.

| Domain / Trigger                             | Reference File                       |
|----------------------------------------------|--------------------------------------|
| Writing or editing React components          | `.agents/rules/react-conventions.md` |
| Working with TypeScript strict mode features | `.agents/rules/typescript-strict.md` |
| Designing / changing REST API endpoints      | `.agents/rules/rest-api-design.md`   |
| Touching auth, secrets, input validation     | `.agents/rules/security-baseline.md` |

(Project-level skills under `.agents/skills/` are auto-discovered by Codex /
Cursor 2.4+ / opencode / Copilot / Gemini via each SKILL.md's `description`
— no routing needed here. Claude / Trae users invoke them via `/skill-name`
or symlink.)

## 0b. Module Reference Map

This is a monorepo. Before editing files under a submodule, also read the
corresponding submodule AGENTS.md, which then routes further into its own
`.agents/rules/` (via a Rules Reference table) and `.agents/skills/` (via a
Workflows table). Submodule-local rules override conflicting root rules on
overlapping topics.

| Path Pattern               | Submodule AGENTS.md           |
|----------------------------|-------------------------------|
| `packages/frontend/**`     | `packages/frontend/AGENTS.md` |
| `packages/backend/**`      | `packages/backend/AGENTS.md`  |
| `packages/payments/**`     | `packages/payments/AGENTS.md` |
| `infra/**`, `terraform/**` | `infra/AGENTS.md`             |

## 0c. Tool-specific Loading

- **Codex / Cursor / opencode**: nested AGENTS.md auto-loads — no manual
  read needed.
- **Claude Code / Trae**: nested AGENTS.md is NOT auto-loaded. You MUST
  use your file-read tool to Read the submodule AGENTS.md before editing
  files in that subtree.
- **All tools**: `.agents/rules/*.md` files (at any tier) are NEVER
  auto-loaded. Read on demand based on the matching tier's Rules Reference
  table.
- **All tools except Codex / Cursor 2.4+ / opencode / Copilot / Gemini**:
  root `.agents/skills/` is not auto-discovered — Claude reads them via
  `.claude/skills/` symlinks, Trae via `.trae/skills/` mirror.
- **All tools**: submodule skills under `packages/*/.agents/skills/` are
  NEVER auto-discovered (no tool scans nested skill catalogues) — they
  are routed via each submodule AGENTS.md's Workflows table.

## 1. Project Overview
...
```

#### 1.3.4 子模块 AGENTS.md 示例（仅路由）

子模块 AGENTS.md 保持 slim：scope、stack、Rules Reference 表、Workflows 表。**不写规则内容**（内容在同级 `.agents/rules/*.md`），**也不写工作流内容**（工作流在同级 `.agents/skills/<name>/SKILL.md`）。

```markdown
# Frontend Module

Scope: `packages/frontend/**`

## Stack
- React 18 + TypeScript strict
- Vite, Tailwind, zustand

## Rules Reference

Read on demand when working in the matching domain. These files live in
`packages/frontend/.agents/rules/` and are NOT auto-loaded by any tool.

| Trigger                                 | File                                                  |
|-----------------------------------------|-------------------------------------------------------|
| Writing or editing React components     | `packages/frontend/.agents/rules/react-conventions.md` |
| Touching state management               | `packages/frontend/.agents/rules/state-management.md`  |

## Workflows

The following skills are scoped to this submodule and are NOT auto-loaded
by any tool. When the trigger matches, Read the SKILL.md first, then follow
its steps.

| Trigger                                | Skill                                                            |
|----------------------------------------|------------------------------------------------------------------|
| Update design tokens from Figma export | `packages/frontend/.agents/skills/update-design-tokens/SKILL.md` |
| Generate a new React component         | `packages/frontend/.agents/skills/new-component/SKILL.md`        |

## Do Not Touch
- packages/frontend/src/legacy/**
```

#### 1.3.4b 子模块规则文件示例

```markdown
# React Conventions (Frontend Module)

Scope: `packages/frontend/**/*.{ts,tsx}`

## Component Style
- 仅函数式组件 + hooks
- props 必须显式定义 type，禁止 any

## State
- 状态管理用 zustand，不要引入 redux
- 跨组件状态走 context 或 zustand

## API
- 所有 API 调用统一用 `packages/api-client`
```

#### 1.3.4c 子模块 skills 必须通过 Workflows 表路由

§1.3.4 子模块 AGENTS.md 的 `Workflows` 段路由到同级 `.agents/skills/` 目录。原因如下：

**问题**：没有任何工具会扫**嵌套**的 skill 目录。

| 工具 | 扫描位置 | 是否扫嵌套 skill 目录？ |
|---|---|---|
| Codex | `.agents/skills/`（根） | ❌ |
| Cursor 2.4+ | `.cursor/skills/` + `.agents/skills/`（根） | ❌ |
| opencode | `.opencode/skills/` + `.claude/skills/` + `.agents/skills/`（根 + 全局） | ❌ |
| Claude Code | `.claude/skills/`（根） | ❌ |
| Trae | `.trae/skills/`（根） | ❌ |

放在 `packages/frontend/.agents/skills/render/SKILL.md` 的 skill **对所有工具默认不可见**——即使 Codex / Cursor / opencode（它们原生读根 `.agents/skills/`）也看不到。

**解决**：通过子模块 AGENTS.md 的 `Workflows` 表路由（机制与 Rules Reference 完全一致）。

**各工具的发现路径**：

| 工具 | 子模块 skill 如何变得可达 |
|---|---|
| **Codex / Cursor / opencode** | 自动加载 `packages/frontend/AGENTS.md`（嵌套 AGENTS.md 原生） → 读 `Workflows` 表 → 触发匹配时 Read SKILL.md |
| **Claude Code / Trae** | 根 AGENTS.md 的 Module Reference Map 指向 `packages/frontend/AGENTS.md` → agent 主动 Read → 读 `Workflows` 表 → 触发匹配时 Read SKILL.md |

5 家工具最终都走到同一行为，**不依赖任何工具去扫嵌套 skill 目录**。skill 内容与子模块代码同目录，发现完全由 AGENTS.md 链承担。

> **为什么用 `Workflows` 而不是 `Rules Reference`？** skills 是操作性 SOP / playbook，rules 是声明性知识。两段名字承载角色：`Workflows` 表里的是"X 发生时做这些步骤"，`Rules Reference` 表里的是"在 Y 领域工作时查阅这些知识"。

#### 1.3.5 `.agents/rules/` vs `.agents/skills/` 的分工

两块在两层（项目根、子模块）下含义相同。差异在 **形态**（声明性知识 vs 操作步骤）和 **发现方式**：

| 维度 | `.agents/rules/*.md` | `.agents/skills/<name>/SKILL.md` |
|---|---|---|
| **本质** | 规范库（声明性知识，agent 应"查阅"） | 工作流（操作步骤，agent 应"执行"） |
| **触发** | L1：Claude / Cursor / Trae 通过桥接原生自动加载（见 §2.3.1）；Codex / opencode 经 AGENTS.md `Rules Reference` 表路由。L2：所有工具都经子模块 AGENTS.md 路由 → agent 主动 Read（不做桥接） | 项目根：通过 `description` 自动发现（5 家原生）；子模块：通过 Workflows 表路由 |
| **跨工具原生发现** | L1：✅ 5 家通用——桥接覆盖 Claude / Cursor / Trae，AGENTS.md 路由覆盖 Codex / opencode。L2：❌ 无原生支持，始终路由式 | ✅ 项目根：**5 家原生**（Codex / Cursor 2.4+ / opencode / Copilot / Gemini）；❌ 子模块：不会被扫描，始终路由式 |
| **典型内容** | "React 规范"、"REST API 设计准则" | "发布到 prod"、"安全审计"、"重生成 Prisma client" |
| **加载粒度** | 文件级（按需 Read） | 整个 skill folder（按 frontmatter 元信息） |
| **选用判据** | agent 应"查阅"的知识 | agent 应"执行"的步骤 |

#### 1.3.6 决策指南：一条内容该放哪里？

两个问题，按顺序问：

```
你要写一条规则 / 知识 / 工作流
        ↓
Q1: 是项目级强约束、每次会话都必须遵守吗？
    （命名、提交规范、do-not-touch、架构边界）
    ├── 是 → 写进根 AGENTS.md 正文——结束。
    └── 否 ↓
        Q2a: 它适用于整个项目（多个子模块都可能查阅），
             还是只在某一个子模块里有意义？
            ├── 整个项目 → 层 = L1（项目根）
            └── 某一个子模块 → 层 = L2（该子模块）
        Q2b: 是声明性知识（规则）还是操作性工作流（skill）？
            ├── 声明性 → 写进 <层>/.agents/rules/<topic>.md
            │     + 在该层 AGENTS.md 的 Rules Reference 加一行
            └── 操作性 → 写进 <层>/.agents/skills/<name>/SKILL.md
                  + 如果层 = L2：在该子模块 AGENTS.md
                    的 Workflows 表加一行（见 §1.3.4c）
                  + 如果该子模块 AGENTS.md 还不存在，
                    同时在根 AGENTS.md 的 Module Reference Map 加一行
```

跨仓库共享是"组织分发"问题，与"层"无关：想跨仓库共享某个 `.agents/rules/` 或 `.agents/skills/`，就把它做成 git submodule。

#### 1.3.7 该方案的优势

| 优势 | 说明 |
|---|---|
| **只问两个问题** | 层（项目 / 子模块） + 形态（规则 / 工作流），决策面就这么大 |
| **L1 ↔ L2 布局对称** | 两层都有同样两块（AGENTS.md + `.agents/rules/` + `.agents/skills/`），学会 L1 就等于学会 L2 |
| **始终加载 vs 按需加载是槽位属性** | 每层中 AGENTS.md 都是始终加载块，`.agents/` 都是按需加载块——形态在两层完全一致 |
| **充分利用原生能力** | L1 AGENTS.md + L2 AGENTS.md 在 Codex / Cursor / opencode 上自动加载；L1 skills 在 5 家上自动发现——常见场景零胶水 |
| **CR 友好** | L2 改动（AGENTS.md + rules + skills）都和子模块代码在同一 PR diff 里可见 |
| **行为最终一致** | 根 AGENTS.md 的路由表让 Claude / Trae 跟上 Codex / Cursor / opencode 的自动加载，5 家最终收敛到相同内容 |
| **不受 Codex 32KB 限制** | 每个 AGENTS.md 都有独立配额；规则与 skill 内容拆到独立文件，谁都不会顶到上限 |
| **一文件一主题** | 规则文件聚焦，易 grep、易演进 |
| **新工具友好** | 路由表 + 标准位置，任何能 Read 文件的 agent 都能跟上 |

#### 1.3.8 实施要点

**两层通用**：
1. **AGENTS.md 是始终加载块，`.agents/` 是按需加载块**——除了 §0a/§0b 路由表（以及 L1 的 §1–§7 强约束段），不要把规则或 skill 正文塞进 AGENTS.md
2. **根 AGENTS.md 的 0c 段（Tool-specific Loading）必须保留**——告知 agent 哪些自动加载、哪些需要主动 Read，避免静默漏读
3. **避免规则与 skill 内容重复**：同一份内容只放一个位置，按 §1.3.5 二选一

**L1（项目根）**：
4. **根 AGENTS.md 的两张路由表必须维护**——Rules Reference（根 `.agents/rules/`）和 Module Reference Map（各子模块 AGENTS.md）是 Claude / Trae 走出始终加载块的唯一线索
5. **L1 规则文件命名**：用能反映规则覆盖范围的名字（`react-conventions.md`、`typescript-strict.md`、`rest-api-design.md`）；每个文件顶部写 `Scope:` 段
6. **L1 skill 的 `description` 是 5 家原生工具自动发现的唯一信号**——必须包含 WHAT + WHEN
7. **L1 skills 不能假设子模块上下文**——如有歧义，移到子模块或通过 prompt 参数化
8. **Claude / Trae 桥接 L1 skills**：让 `.claude/skills/` 和 `.trae/skills/` 看到 `.agents/skills/` 的内容；具体方案根据团队 OS 组合 / 工作流自选（详见 §3.5.2 的跨设备兼容性提示——本手册不规定单一方案）

**L2（子模块）**：
9. **新增子模块时**：先建 `<module>/AGENTS.md`（slim — scope + stack + Rules Reference + Workflows），再去根 AGENTS.md 的 Module Reference Map 加一行
10. **保持子模块 AGENTS.md slim**：是路由入口、不是规则容器——规则内容推到 `<module>/.agents/rules/*.md`，工作流内容推到 `<module>/.agents/skills/`
11. **顶部写 `Scope: <glob>`**，子模块 AGENTS.md 和每个规则文件都写——与子模块 scope 匹配或更窄
12. **一文件一主题** 放 `<module>/.agents/rules/` 下——易 grep、易演进
13. **每个子模块规则文件必须被引用**：从该子模块 AGENTS.md 的 Rules Reference 引一行，否则任何工具都不会 Read 它
14. **每个子模块 skill 必须出现在 Workflows 表中**（见 §1.3.4c）——没有工具会扫嵌套 skill 目录，未路由的子模块 skill 就是死代码。即使 Codex / Cursor / opencode 也**不会**通过 `description` 字段冒泡嵌套 SKILL.md
15. **同一个 commit 加 Workflows / Rules Reference 表行**：新建规则 / skill 时同 PR 更新对应表，否则上线即不可见
16. **更深嵌套也支持**：如 `packages/frontend/components/AGENTS.md`，Codex / Cursor / opencode 会再次自动近端加载；想让 Claude / Trae 也读到需在父级 AGENTS.md 做二级路由

### 1.4 各工具特殊注意事项

#### Claude Code

- ❌ **不原生读 AGENTS.md**，必须 `@AGENTS.md` 桥接或建 symlink `CLAUDE.md -> AGENTS.md`
- ⚠️ **subagent 不继承**：`Task` 派发的子 agent 不会加载 CLAUDE.md/AGENTS.md，需在 prompt 中显式贴入
- 💡 `/init` 命令会自动把 `AGENTS.md` + `.cursorrules` + `.windsurfrules` 合并到生成的 `CLAUDE.md`

#### Codex

- ⚠️ **32 KiB 静默截断**（无任何警告）。`~/.codex/config.toml` 中 `project_doc_max_bytes = 65536` 可调高
- 💡 `AGENTS.override.md` 同级取代 `AGENTS.md`，可做"完全替换"
- 💡 `project_doc_fallback_filenames` 可加入 `TEAM_GUIDE.md` 等遗留文件名
- 验证：`codex --ask-for-approval never "Summarize the current instructions."`

#### Cursor

- 💡 嵌套 `AGENTS.md` 自动 scope，**根 AGENTS.md 只写跨子系统通用内容**
- ⚠️ 部分版本嵌套加载有 bug，必要时 `@AGENTS.md` 手动引用
- 💡 与 `.cursor/rules/*.mdc` 共存，AGENTS.md 优先级在 .mdc 之后

#### opencode

- ✅ **原生主文件**：`AGENTS.md` 是推荐 rules 文件（opencode 是 AGENTS.md 标准的早期推动者之一）
- 💡 **fallback 到 `CLAUDE.md`**：同级目录没有 `AGENTS.md` 时自动读 `CLAUDE.md`——对已经在用 Claude 的项目无缝
- 💡 **全局规则**：`~/.config/opencode/AGENTS.md` 在所有 opencode 会话中自动加载
- 💡 **全局 Claude fallback**：没有全局 opencode AGENTS.md 时还会读 `~/.claude/CLAUDE.md`（可关）
- 💡 `/init` 扫描仓库并创建 / 更新 `AGENTS.md`，必要时询问澄清问题
- 💡 **外部规则文件**：`opencode.json` 的 `instructions` 字段可指向附加文件，团队复用共享规则无需 copy 到 AGENTS.md
- ⚠️ 查找顺序很重要：同级同时存在 `AGENTS.md` 和 `CLAUDE.md` 时，**AGENTS.md 胜出**（另一个被忽略，不合并）

#### Trae

- ⚠️ **默认不读** AGENTS.md，需 Settings → Rules & Skills → 勾选 "Include AGENTS.md in the context"
- 💡 **推荐做法**：开启开关后直接复用根 `AGENTS.md`，不要再额外写 `.trae/rules/project_rules.md` 薄壳——避免规则分裂
- 💡 仅当需要 Trae 专属规则（如 `#Rule` 触发、特定生效模式）时，才创建 `.trae/rules/` 下的文件
- ⚠️ 修改 `AGENTS.md` 后需 Reload Window 才生效
- 💡 中国版（trae.cn）和国际版（trae.ai）路径不同：`~/.trae-cn/` vs `~/.trae/`

---

## 二、Rules 规则系统

### 2.1 能力对比

| 维度 | Claude Code | Codex | Cursor | opencode | Trae |
|---|---|---|---|---|---|
| 独立 Rules 系统 | ✅ | ❌ | ✅ | ❌（只用 AGENTS.md） | ✅ |
| 项目级路径 | `.claude/rules/` | — | `.cursor/rules/` | — （AGENTS.md 即规则文件） | `.trae/rules/` |
| 用户级路径 | `~/.claude/rules/` | — | UI 配置 + Team 仪表盘 | — | `~/.trae/rules/` |
| 扩展名 | `.md` | — | `.mdc`（`.md` 被忽略） | — | `.md` |
| frontmatter 字段 | `paths` | — | `description`/`globs`/`alwaysApply` | — （用 `opencode.json` `instructions` 数组挂额外文件） | 在 IDE 面板配置 |
| 始终生效 | ✅ 无 paths | — | `alwaysApply: true` | ✅ AGENTS.md 始终加载 | "始终生效"模式 |
| 路径匹配 | ✅ `paths: [globs]` | — | ✅ `globs: [...]` | ❌（无路径 scoped rule 概念） | "指定文件生效" |
| AI 智能激活 | ❌ | — | ✅ description | ❌ | ✅ description |
| 手动触发 | ❌ | — | ✅ `@rule-name` | ❌ | ✅ `#Rule`（最高优先级） |
| 子目录递归 | ✅ | — | ✅ | ✅（沿 AGENTS.md 向上 walk） | ✅ |
| 触发时机 | Claude **Read** 匹配文件时 | — | 匹配文件入 context | 始终（或 per-agent 覆盖） | 编辑/Read 时 |
| 是否支持 `.agents/rules/` | ❌ | — | ❌ | ❌ |

### 2.2 Monorepo 支持

所有支持 rules 的工具都支持**子目录递归扫描**，但都不像 AGENTS.md 那样自动按位置 scope——需要显式配置 path/glob/scope：

```
.cursor/rules/
├── frontend/
│   └── react.mdc          # globs: ["packages/frontend/**/*.tsx"]
└── backend/
    └── api.mdc            # globs: ["packages/backend/**"]
```

### 2.3 项目配置最佳实践

> **🎯 核心策略：规则正本只放在 `.agents/rules/`，再分别桥接到各家原生 rules 路径**
>
> Rules 五家路径、frontmatter 字段、激活机制全部不兼容（详见 §2.1），且核心机制基本定型、未来不会统一。但**放弃各家原生 rules 系统**会失去 Cursor 的智能激活、Trae 的 `#Rule` 触发等独有能力；**每家复制一份**又会随时间漂移。最优解是把每条规则的正本保留在 `.agents/rules/<topic>.md`，再让支持 rules 的三家工具按自己的格式桥接到同一个文件——内容按以下四类分流，桥接方式见 §2.3.1：
>
> | 内容类型 | 正本位置 | 各工具如何到达 |
> |---|---|---|
> | **项目级强约束**（禁区、命名规范、提交格式） | **根 `AGENTS.md`** 正文 | 5 家通用——Codex / Cursor / opencode 始终加载；Claude 通过 `CLAUDE.md` 中 `@AGENTS.md` 引用；Trae 启用 "Include AGENTS.md" 开关后加载 |
> | **项目级规则**（coding-style、TS strict、security-baseline 等） | **根 `.agents/rules/<topic>.md`** | Claude / Trae：目录符号链桥接自动加载（§2.3.1）；Cursor：每条规则一份 `.mdc` shim 自动加载；Codex / opencode：经根 AGENTS.md `Rules Reference` 表 |
> | **子模块独占规则**（如前端 React 规范） | **`packages/<name>/.agents/rules/<topic>.md`** | 5 家统一经子模块 AGENTS.md `Rules Reference` 表路由（L1 目录桥不覆盖 L2，详见 §2.3.1 设计取舍） |
> | **可触发的工作流 / SOP**（发布、审计、scaffold） | 对应层的 **`.agents/skills/<name>/SKILL.md`** | 见 §3.5——属于另一个维度 |
>
> 子模块规则文件镜像根 `.agents/rules/` 布局。子模块 AGENTS.md 保持 slim——只放该模块的 stack 信息 + 一张 Rules Reference 表，指向本地的 `.agents/rules/*.md`。

#### 2.3.1 把 Claude / Trae / Cursor 桥接到 `.agents/rules/`

规则正本统一放在 `.agents/rules/<topic>.md`，三家支持 rules 的工具按各自原生路径桥接到它：

| 工具 | 桥接方式 | 备注 |
|---|---|---|
| **Claude Code** | **目录符号链** `.claude/rules → .agents/rules`（或只暴露子集时使用单文件 symlink） | Claude 原生读 `.md`。路径限定用 Claude 的 `paths` frontmatter——直接写在**正本文件**里（Trae 会忽略未知字段；Codex / opencode 永远不直接读这些文件）。 |
| **Trae** | **目录符号链** `.trae/rules → .agents/rules`（与 Claude 同形） | Trae 原生读 `.md`。激活模式在 Trae IDE 设置面板按 rule 配置，不是 frontmatter——团队约定一套约定即可。 |
| **Cursor** | **每条规则一份 `.mdc` shim** 放在 `.cursor/rules/<topic>.mdc`，内含 Cursor 专属 frontmatter（`description` / `globs` / `alwaysApply`），body 要么写一行指向正本的链接、要么 inline 正本内容 | Cursor 只读 `.mdc`，纯 `.md` symlink 会被忽略。shim 本身很轻量（frontmatter + 几行 body），但能保留 Cursor 的智能激活——`description` 和 `globs` 要写得有意义。 |
| **Codex** | 无 rules 系统——经根 AGENTS.md `Rules Reference` 表到达 | 不变 |
| **opencode** | 同 Codex——经根 AGENTS.md 到达；或在 `opencode.json` 的 `instructions` 数组里直接指向 `.agents/rules/*.md` | 不变 |

**Cursor shim 有两种风格**——选一种全局统一：

*Redirect shim*（更轻，但 body 要 agent 主动 Read 正本）：

```mdc
---
description: TypeScript strict-mode conventions for this repo
globs: ["**/*.ts", "**/*.tsx"]
alwaysApply: false
---

Apply the conventions documented in [`.agents/rules/typescript-strict.md`](../../.agents/rules/typescript-strict.md). Read that file before continuing.
```

*Inline shim*（重一些，但 Cursor 激活时立即看到内容；正本变更后需要重生成——一个把 `.agents/rules/*.md` 拷贝到 `.cursor/rules/*.mdc` 并加上 frontmatter 的小脚本是标准做法）：

```mdc
---
description: TypeScript strict-mode conventions for this repo
globs: ["**/*.ts", "**/*.tsx"]
alwaysApply: false
---

<!-- AUTO-GENERATED from .agents/rules/typescript-strict.md — edit the canonical file, not this shim -->

# TypeScript Strict Mode
...(body 从正本拷贝)...
```

> ⚠️ **跨设备兼容性同样适用**——skills 桥接在 §3.5.2 描述的所有约束在这里完全一致（Windows symlink 权限 / `git config core.symlinks` / FAT32 / 网络盘 / 与 `~/.claude/rules/`、`~/.trae/rules/` 等 `npx skills add` 等消费侧安装路径共存）。选择适合团队 OS 组合的桥接策略，本 handbook 故意不给出"标准脚本"。**绝不要为了"刷新桥接"而直接删除已存在的 `.claude/rules/` / `.trae/rules/` 目录**——里面可能已经有消费侧安装器或别的来源写入的内容。

**子模块规则只走路由，不桥接。** L1 目录 symlink 只暴露根 `.agents/rules/` 文件。`packages/<name>/.agents/rules/` 下的子模块规则继续走子模块 AGENTS.md 的 `Rules Reference` 表路由——这样既能让规则只在工作于该子树时被看到（这正是期望的 scoping），又避免把每个子模块的内部细节灌进 Claude / Trae 平铺的 rules 目录。

**根 AGENTS.md `Rules Reference` 表依然必须保留**——它是 Codex / opencode（无 native rules 系统）的唯一发现路径，也是给人看的索引。桥接到位之后，Claude / Cursor / Trae 自动加载这些文件；`Rules Reference` 表退化为跨工具的意图说明。

#### 决策树：一条规则该写在哪？

```
你想写一条规则 / 工作流 / 知识
        ↓
是否每次都要 agent 遵守？（命名规范、提交格式、禁区文件）
        ├── 是 → 写进根 AGENTS.md 正文
        └── 否 ↓
            是不是 agent 应该按触发执行的工作流 / SOP？
                ├── 是 → 写成 Skill（`.agents/skills/<name>/SKILL.md`）
                │         + 放在合适的层（项目根或子模块）。
                │         详见 §3.5 和 §1.3.4c
                └── 否（声明性知识）↓
                    它适用于整个项目（多个子模块都可能查阅），
                    还是只在某一个子模块里有意义？
                        ├── 整个项目 → 写进根 `.agents/rules/<topic>.md`
                        │              并在根 AGENTS.md 的 Rules Reference 加一行
                        └── 某一个子模块 → 写进
                              `packages/<name>/.agents/rules/<topic>.md`
                              并在该子模块 AGENTS.md 的 Rules Reference 加一行
                              （如果该子模块 AGENTS.md 还不存在，同时在根
                               AGENTS.md 的 Module Reference Map 加一行）
```

#### 迁移路线：从各家 rules 到 `.agents/rules/` + 桥接 + Skills

**Step 1**：把 always-loaded 规则迁到根 AGENTS.md（不需要桥接——每家都能读 AGENTS.md）

```diff
- .cursor/rules/coding-style.mdc (alwaysApply: true)
- .claude/rules/coding-style.md (无 paths)
- .trae/rules/project_rules.md
+ AGENTS.md  ## Code Style 章节
```

**Step 2**：把"项目特定"的 path-scoped 规则迁到子模块的 `.agents/rules/`

```diff
- .cursor/rules/this-project-react.mdc (globs: ["packages/frontend/**/*.tsx"])
- .claude/rules/this-project-react.md (paths: ["packages/frontend/**/*.tsx"])
+ packages/frontend/.agents/rules/react-conventions.md
+ packages/frontend/AGENTS.md  ## Rules Reference（加一行指向上面文件）
```

子模块布局镜像根布局：

```
packages/frontend/
├── AGENTS.md                       # slim：scope + stack + Rules Reference + Workflows
└── .agents/
    ├── rules/                      # 项目特定子模块规则
    │   ├── react-conventions.md
    │   └── state-management.md
    └── skills/                     # （可选）仅本子模块用的 workflows
        └── update-design-tokens/SKILL.md
```

子模块 AGENTS.md 的 "Rules Reference" 示例：

```markdown
# packages/frontend/AGENTS.md

Scope: `packages/frontend/**`

## Stack
React 18 + TypeScript strict + zustand

## Rules Reference

Read on demand when working in the matching domain:

| Trigger                               | File                                                  |
|---------------------------------------|-------------------------------------------------------|
| Writing or editing React components   | `packages/frontend/.agents/rules/react-conventions.md` |
| Touching state management             | `packages/frontend/.agents/rules/state-management.md`  |
```

**Step 3**：把"项目级规则"（多个子模块都会查阅的规则）迁到根 `.agents/rules/`，并把三家 rules-支持工具桥接到它

```diff
- .cursor/rules/coding-style.mdc (无路径限定，但是知识性内容)
- .claude/rules/typescript-strict.md (项目范围 TS 严格模式约束)
+ .agents/rules/coding-style.md                                  # 正本
+ .agents/rules/typescript-strict.md                              # 正本
+ .claude/rules → .agents/rules                                   # 桥接（目录 symlink，或单文件 symlink）
+ .trae/rules   → .agents/rules                                   # 桥接（目录 symlink）
+ .cursor/rules/coding-style.mdc                                  # 桥接（每条规则一份 .mdc shim）
+ .cursor/rules/typescript-strict.mdc                             # 桥接（每条规则一份 .mdc shim）
+ AGENTS.md  ## 0a. Rules Reference                               # 给 Codex / opencode 用
```

**Step 4**：把"按需触发的长 SOP / 智能激活内容"迁到 Skills

```diff
- .cursor/rules/deploy.mdc (无 frontmatter，@手动调用)
- .cursor/rules/security-audit.mdc (description 智能激活)
+ .agents/skills/deploy/SKILL.md
+ .agents/skills/security-audit/SKILL.md
```

> 💡 **Step 2 vs Step 3 区别**：仅某一个子模块关心的规则放 Step 2（`packages/<name>/.agents/rules/`，与子模块代码同目录维护）；多个子模块都会查阅的规则放 Step 3（根 `.agents/rules/`）。
>
> 💡 **为什么用子模块 `.agents/rules/` 而不是把规则塞进子模块 AGENTS.md**：保证每个规则文件聚焦单一主题、镜像根 `.agents/rules/` 布局（认知负担更低），且避免子模块 AGENTS.md 超过 Codex 32 KiB 静默截断阈值。

#### 桥接覆盖不到的工具特有场景

桥接覆盖了"在合适的上下文里 agent 该读规则"这个常见诉求。下列场景需要在正本之上额外做一点工具侧配置：

| 场景 | 处理方式 | 理由 |
|---|---|---|
| Cursor `@rule-name` 手动引用 | `@rule-name` 按 `.mdc` shim 的文件名解析——保持 shim 文件名（不含扩展名）与正本文件名一致即可 | Cursor 的 `@` 语法直接匹配 shim 名；只要 1-to-1 镜像就不用额外配置 |
| Trae `#Rule rule-name` 手动触发（最高优先级，强制加载） | 同理——`#Rule` 按 `.trae/rules/` 下的文件名解析，而该文件就是正本的 symlink | 通过 symlink 直通，无需改动 |
| 工具专属的 IDE 行为（如 Cursor Team Rules 仪表盘） | 继续通过工具自身的企业仪表盘管理；视作 `.agents/rules/` 之外的带外通道 | 企业治理在工具层而非文件层 |
| Claude path-scoped 规则 | 把 `paths: [...]` frontmatter 写在 `.agents/rules/` 下的**正本**文件里——symlink 把同一个文件暴露给 Claude，Claude 会读取 `paths`；Trae / Codex / opencode 会忽略这个未知字段 | 单文件、单 frontmatter、不重复 |

#### 推荐布局

```
AGENTS.md                                              # 强约束 + Rules Reference 表（给 Codex/opencode 发现）
.agents/rules/                                         # 正本（唯一来源）
  ├── coding-style.md                                  #   always-on 风格规则
  └── typescript-strict.md                             #   含 Claude `paths` frontmatter，其他工具忽略
.claude/rules → .agents/rules                          # 桥接：目录 symlink
.trae/rules   → .agents/rules                          # 桥接：目录 symlink
.cursor/rules/                                         # 桥接：每条规则一份 .mdc shim（frontmatter + redirect 或 inline）
  ├── coding-style.mdc                                 #   description / alwaysApply
  └── typescript-strict.mdc                            #   description / globs
packages/frontend/AGENTS.md                            # slim：scope + Rules Reference + Workflows
packages/frontend/.agents/rules/react-conventions.md   # 子模块独占规则——只走路由，不桥接
.agents/skills/deploy/SKILL.md                         # 部署 SOP（按需加载，替代 manual rules）
```

该布局的性质：

- 每条规则只有一份正本放在 `.agents/rules/` 下；桥接（symlink + 精简 `.mdc` shim）不携带规则内容
- 跨工具兼容：每家工具都到同一份正本
- 智能激活保留：Cursor `.mdc` shim 保留 `description` / `globs` 智能激活；Trae IDE 侧的激活模式继续生效；Claude `paths` 通过正本文件 frontmatter 生效
- Context 消耗：仅根 AGENTS.md 始终加载；子模块 AGENTS.md / 子模块 `.agents/rules/` / Skills 按需加载；L1 `.agents/rules/*.md` 在对应工具的桥接触发时加载

### 2.4 各工具特殊注意事项

#### Claude Code

- 💡 配置好桥接（`.claude/rules → .agents/rules`）之后，Claude 原生看到每个正本文件——除了这条 symlink 之外没有别的设置
- 💡 字段叫 `paths`（不是 globs），单行无引号格式可避免某些 parser bug：`paths: src/api/**/*.ts, lib/**/*.ts`。把 `paths` 写在 `.agents/rules/` 下的**正本**文件里，其他工具会忽略未知 frontmatter
- ⚠️ path-scoped 只在 Claude **Read** 匹配文件时触发，**编辑新建文件可能不触发**
- 💡 `/memory` 命令审计当前实际加载的规则
- ❌ 原生不支持 description 智能激活、不支持 `@rule` 手动调用（Cursor 的 `@rule-name` 仅在 Cursor 中、通过 `.mdc` shim 工作）

#### Cursor

- ⚠️ **只读 `.mdc`**——`.cursor/rules/` 下的 `.md` 文件（以及任何指向 `.md` 的 symlink）会被忽略。这就是桥接到 Cursor 必须用**每文件一份 `.mdc` shim**、而不能用目录 symlink 的原因（见 §2.3.1）
- 💡 shim 风格（redirect vs inline）权衡 body 大小与 active-Read 延迟；短规则通常 inline 更划算，长规则 redirect 更划算
- 💡 2.2+ 起新规则也接受**文件夹形式**保存（`.cursor/rules/<name>/RULE.md`），shim 两种形式都兼容
- 💡 Team Rules 通过 Team / Enterprise 仪表盘统一管理——这些不进入 `.agents/rules/`
- ⚠️ `CLAUDE.md` 在 Cursor 中**始终全量加载**（无视 alwaysApply），用于跨工具兼容

#### Trae

- 💡 配置好桥接（`.trae/rules → .agents/rules`）之后，Trae 原生看到每个正本文件
- 💡 激活模式在 IDE Settings 面板按 rule 配置（不是 frontmatter）——团队需统一约定并在正本文件旁记录
- 💡 `#Rule rule-name` 按 `.trae/rules/` 下的文件名解析，通过 symlink 直通无需改动；且是最高优先级（即使该规则设为其他激活模式也强制加载）
- 💡 `.trae/settings.local.json` 默认 gitignore，可做个人本地覆盖

#### Codex

- ❌ 无独立 rules 系统，所有"规则"通过 AGENTS.md 表达 + 目录嵌套实现。根 AGENTS.md `Rules Reference` 表是 Codex 到达 `.agents/rules/*.md` 的唯一入口

#### opencode

- ❌ **无独立 Rules 系统**——一切走 `AGENTS.md`（理念与 Codex 相同）
- 💡 **不复制到 AGENTS.md 也能挂额外规则文件**：在 `opencode.json` 设置 `instructions: ["./.agents/rules/coding-style.md", "./.agents/rules/typescript-strict.md"]`，正本会被附加到每次会话的 context——这是 opencode 对全局规则的桥接等价物
- 💡 **全局规则**：`~/.config/opencode/AGENTS.md` 在每个 opencode 会话中加载——等价于"用户级常驻规则"
- 💡 **per-agent scope**：subagent 的 `permission` 块（在 agent markdown 里）可以 deny 让它违反规则的工具（例如 reviewer 设 `edit: deny`）

---

## 三、Skills 技能系统

### 3.1 能力对比

| 维度 | Claude Code | Codex | Cursor | opencode | Trae |
|---|---|---|---|---|---|
| 项目级路径 | `.claude/skills/` | `.agents/skills/`（沿目录链） | `.cursor/skills/` + `.agents/skills/` | `.opencode/skills/` + `.claude/skills/` + `.agents/skills/` | `.trae/skills/` |
| 用户级路径 | `~/.claude/skills/` | `~/.agents/skills/` | `~/.cursor/skills/` + `~/.agents/skills/` | `~/.config/opencode/skills/` + `~/.claude/skills/` + `~/.agents/skills/` | `~/.trae/skills/` |
| Admin/系统级 | — | `/etc/codex/skills/` + 内置 | — | — | — |
| 兼容路径 fallback | — | — | `.claude/skills/` + `.codex/skills/` | `.claude/skills/` 与 `.agents/skills/` 都**原生**（不是 fallback） | Audit: `.agents/`, `.claude/`, `.github/` |
| SKILL.md frontmatter | ✅ 完整支持 | ✅ + `agents/openai.yaml` | ✅（部分字段忽略） | ✅ `name` / `description` 必填；可选 `license` / `compatibility` / `metadata` | ✅ |
| 调用方式 | `/skill-name` 或自动 | `$skill-name` 或自动 | `/skill-name` / `@-mention` / 自动 | 自动（通过内置 `skill` 工具按需加载） | `/skill-name` 或自动 |
| `allowed-tools` 行为 | ⚠️ CLI 中预批准列出的工具（SDK 忽略），不是限制 | — | ❌ 忽略 | 通过 `opencode.json` `permission.skill` 模式控制（`allow`/`deny`/`ask`） | — |
| `disallowed-tools` | ✅ v2.1.152+ | — | ❌ | — | — |
| `context: fork` 子 agent 隔离 | ✅ | — | — | — | — |
| `!command` 注入 shell 输出 | ✅ | — | — | — | — |
| 支持脚本 + 资产 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Per-agent skill override | — | — | — | ✅ `agent.<name>.permission.skill` 覆盖全局 | — |

### 3.2 SKILL.md 标准格式

**最小可用**（跨工具兼容）：

```markdown
---
name: my-skill
description: 一句话说明用途与触发场景
---

# My Skill

详细操作步骤...
```

**Claude Code 完整字段**：

```markdown
---
name: my-skill
description: 任务自动化技能
allowed-tools: Read, Grep, Glob, Bash(npm test:*)
disallowed-tools: Write, Edit
disable-model-invocation: false
context: fork              # 在隔离子 agent 中执行
model: claude-sonnet-4-20250514
---
```

### 3.3 跨工具兼容性矩阵（2026/06）

| 路径 | Claude Code | Codex | Cursor 2.4+ | opencode | Trae | Copilot | Gemini CLI |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `.agents/skills/` | ❌ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| `.claude/skills/` | ✅ | ❌ | ✅ fallback | ✅ 原生 | ❌ | ✅ | ❌ |
| `.cursor/skills/` | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `.opencode/skills/` | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| `.trae/skills/` | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| `.codex/skills/` | ❌ | ✅ | ✅ fallback | ❌ | ❌ | ❌ | ❌ |

> **`.agents/skills/` 已成事实跨工具标准**——**5 个工具原生读取**（Codex / Cursor 2.4 / opencode / Copilot / Gemini CLI），随着 opencode 加入从 4 个升至 5 个。
> **Claude Code 与 Trae 是仅有的孤岛**：Claude 只读 `.claude/skills/`，Trae 只读 `.trae/skills/`。opencode 同时原生读 `.claude/skills/` 和 `.agents/skills/`（非 fallback 语义），所以 Claude 形态的仓库在 opencode 上无需任何修改就可工作。
> **没人读 `.trae/skills/`** 除了 Trae 自己。

### 3.4 Monorepo 嵌套加载行为对比

五个工具对子目录 skills 的扫描与 scope 机制差异巨大，这是后续 §3.5 设计配置布局的事实基础。

| 维度 | Claude Code | Codex | Cursor | opencode | Trae |
|---|---|---|---|---|---|
| **是否扫子目录** | ✅ 全仓递归 | ✅ cwd→repo root 沿路径每层 `.agents/skills/` | ✅ 嵌套 `.cursor/skills/` 或 `.agents/skills/` | ❌ 仅扫顶层 skill 目录 | ❌ 仅扫 `.trae/skills/` 顶层 |
| **scope 方式** | 全部 skill 一次性进 catalogue，靠 SKILL.md `paths`/`description` 触发 | 沿目录链发现每层 `.agents/skills/`；同名 skill 不合并，可能同时出现在 selector 中 | 跟随当前编辑文件所在目录就近 scope（与嵌套 AGENTS.md 同机制） | 所有发现的 skill 进单一 on-demand catalogue，靠 `skill` 工具按需加载；`description` 是唯一路由信号 | 全部进 catalogue，靠 `description` 触发 |
| **可用 frontmatter 限制范围** | `paths: ["packages/frontend/**"]` | SKILL.md 暂无官方 `paths` 字段；用 `agents/openai.yaml` invocation policy 控制隐式/显式触发 | 字段会被读但**不会过滤显示**，靠 `description` 智能激活 | 无 `paths` 字段——在 `description` 写触发关键词，或用 `opencode.json` `permission.skill` 模式限制 | `paths` 字段实验性 |
| **多层 `agents/openai.yaml`** | — | ✅ 每层独立；用 `policy.allow_implicit_invocation` 控制该层是否允许隐式触发 | — | — | — |
| **最大嵌套深度** | 无限制 | 无限制（每层独立 32KB 配额） | 与嵌套 AGENTS.md 同（部分版本不稳定） | n/a（不支持嵌套） | 不支持嵌套 |
| **同名 skill 冲突解决** | 后加载覆盖前面 | 不合并；重复名称可能同时暴露给 selector | 近端覆盖远端 | **6 个搜索路径下全局必须唯一**——重名会被静默丢弃 | 仅一份 |

**关键差异**：

- **Codex / Cursor**：把 skills 当成"目录上下文资源"，**子模块就近放就能在该子树发现**——与嵌套 AGENTS.md 行为大体对齐
- **Claude Code**：扁平加载所有 skills，要让 skill 只在子模块下激活**必须**在 SKILL.md frontmatter 写 `paths`
- **opencode**：扁平加载但读 6 个路径（项目 + 全局 × `.opencode/skills/` / `.claude/skills/` / `.agents/skills/`）。子模块 skill 唯一可行的方案是**通过子模块 AGENTS.md Workflows 段 + 根上 `permission.skill` 黑名单路由**——与 Trae 同模式
- **Trae**：不支持嵌套 catalogue；子模块 skills 通过子模块 AGENTS.md 的 Workflows 段主动发现，再由 agent Read 对应 SKILL.md

### 3.5 项目配置最佳实践

#### 3.5.1 核心思想：根公共 + 子模块就近（双层结构）

与 §1.3 AGENTS.md 的两层结构对齐，**Skills 也分两层**：

| 层级 | 存放位置 | 适用内容 |
|---|---|---|
| **L1 — 项目根 skills** | `.agents/skills/<name>/` | 适用于整个项目的工作流（release、security-audit、scaffold） |
| **L2 — 子模块 skills** | `packages/<name>/.agents/skills/<name>/` | 仅某一个子模块需要的工作流（如 frontend 的 `update-design-tokens`） |

**各工具的自动 scope 行为**：

- **Codex / Cursor**：编辑 `packages/frontend/**` 时自动 scope 到 `packages/frontend/.agents/skills/`，无需任何配置
- **Claude Code / Trae**：不会自动按位置 scope，需要走 §3.5.3 的兜底方案

#### 3.5.2 推荐目录结构

```
your-repo/
├── AGENTS.md                              # 含 Rules Reference + Module Reference Map（§1.3）
│
├── .agents/skills/                        # ★ 项目根 skills（Codex/Cursor/Copilot/Gemini 原生）
│   ├── deploy-prod/SKILL.md               #   整个项目的部署流程
│   ├── security-audit/SKILL.md            #   全仓安全审计
│   └── release/
│       ├── SKILL.md
│       ├── scripts/bump-version.sh
│       └── templates/release-notes.md
│
├── .claude/skills/ → ../.agents/skills/   # symlink，让 Claude 也读到根 skills
├── .trae/skills/   → ../.agents/skills/   # 同上，仅联通根 skills
│
└── packages/
    ├── frontend/
    │   ├── AGENTS.md
    │   └── .agents/skills/                # ★ 仅前端用的 skills
    │       └── update-design-tokens/
    │           ├── SKILL.md               #   frontmatter: paths: packages/frontend/**
    │           └── scripts/sync.ts
    └── backend/
        ├── AGENTS.md
        └── .agents/skills/
            └── run-migration/SKILL.md
```

#### 把 Claude / Trae 桥接到 `.agents/skills/` — 跨设备兼容性提示

Claude 只读 `.claude/skills/`，Trae 只读 `.trae/skills/`。所以根 skill 放在 `.agents/skills/` 的项目，必须有**某种机制**让这两个工具特定路径看到 `.agents/skills/` 里的内容——symlink、junction、递归 copy、构建时生成、或调用 `npx skills add --agent claude/trae` 都能做到。

**本手册有意不规定单一方案**，因为合适的选型依赖团队具体约束：

| 维度 | 需要权衡的点 |
|---|---|
| **OS 组合** | Windows symbolic link 需要管理员 / Developer Mode；NTFS junction 不需要权限但仅同卷 / 同 NTFS；macOS / Linux symlink 无约束；WSL ↔ 原生 Windows 互看链接行为不一致 |
| **Git 行为** | `git config core.symlinks` 在 Windows 上默认 `false`（会把已提交的 symlink 变成文本文件）。"链接进 Git" vs "链接由脚本生成且 gitignored"，跨平台后果差异巨大 |
| **网络盘 / 非 NTFS** | FAT32 / exFAT / SMB / 云同步盘不支持 junction 或 symlink；只能 copy，但 copy 在 SKILL.md 改动后会失同步，必须主动刷新 |
| **与 `~/.agents/skills/` 全局安装共存** | 如果开发者同时也用 `npx skills add ...`（或其它会写入 `~/.claude/skills/` / `~/.trae/skills/` 的工具）装第三方 skill，**任何"先删后建"的自动桥接脚本会静默销毁这些全局安装内容**。任何脚本方案必须能区分"本仓库管的"和"外部装的"，否则就把桥接限制在一个独占子目录里（例如 `.claude/skills/_repo/`） |
| **维护归属** | 单人项目跑一次 `ln -s` 即可；多人团队通常需要在 `clone` / `pull` 时自动重建，意味着 git hook 或 `npm install` 脚本；CI 还要单独配 |
| **编辑回环延迟** | symlink / junction 即时反映 SKILL.md 编辑；copy 桥接必须等下次刷新才生效，影响活跃 skill 开发 |

**选一个适合你团队 OS 组合和工作流的方案，把它写进仓库 README / 贡献者文档，用 [§9.9 验证清单](#99-agent--skill-配置验证清单)校验生效。** Agent 最终要看到什么是固定的，怎么让它看到由你团队自己决定。

> ⚠️ 无论你选什么方案，**不要无条件删除已存在的 `.claude/skills/` 或 `.trae/skills/` 目录**——这两个路径同时是 `npx skills add ...` 等消费侧工具落第三方 skill 的位置。所有破坏性操作前先判断"这个目录是不是我建的"，或者把桥接限定到你独占的 sentinel 子目录。

#### 3.5.3 Skill 发现与 scope 配置

两层的发现机制完全不同。

##### L1 项目根 skills：放根 `.agents/skills/`，无需 AGENTS.md 声明

例：`deploy-prod`、`security-audit`、`scaffold-new-package`。这类 skill 天然全局可用，所有工具靠原生扫描就能发现。

| 工具 | 发现机制 |
|---|---|
| Codex / Cursor / Copilot / Gemini | 原生扫 `.agents/skills/` |
| Claude Code | symlink `.claude/skills/ → .agents/skills/` + 全仓递归扫 |
| Trae | symlink `.trae/skills/ → .agents/skills/` + 扫顶层 |

**唯一要做的事：写好 SKILL.md 的 `description`**——agent 看一眼就知道何时调用：

```markdown
---
name: deploy-prod
description: Deploy current branch to production. Use when user asks to ship, release, or push live.
---
```

> 不需要在 AGENTS.md 再列一遍——`description` 本身就是触发协议；重复声明只增加维护成本，没有信息增量。

##### L2 子模块 skill：在子模块 AGENTS.md 声明工作流

例：`packages/frontend/.agents/skills/update-design-tokens/`。

**推荐方案：子模块 AGENTS.md 的 Workflows 段集中声明可用 skill**

```markdown
# packages/frontend/AGENTS.md

## Workflows
- 同步设计 tokens：`packages/frontend/.agents/skills/update-design-tokens/`
- 升级 React 主版本：`packages/frontend/.agents/skills/react-major-upgrade/`（必须先备份 lockfile）
```

工作链路：

- **Codex / Cursor**：编辑子模块文件 → 自动近端加载子模块 AGENTS.md + 自动 scope `.agents/skills/` 子目录 → 看到 Workflows 引用即调用
- **Claude / Trae**：根 AGENTS.md 的 Module Reference Map 引导 → agent 主动 Read 子模块 AGENTS.md → 看到 Workflows 引用 → 主动 Read SKILL.md 执行

为什么 L2 子模块 skill 推荐走 AGENTS.md（与 L1 "靠 description 自动发现" 的策略不同）：

- **就近维护**：子模块 owner 在自己的 AGENTS.md 内一并管理工作流，无需切换文件、无需同步根文件
- **子模块特定触发上下文**：SKILL.md `description` 字段空间有限，难以表达"子模块特定的前提"（如"升级前必须备份 lockfile"）；AGENTS.md Workflows 段是自然的承载位置
- **对 Trae 是唯一可行的发现路径**：Trae 不扫子模块下的 `.agents/skills/`，skill 不在 catalogue 里——只有靠 AGENTS.md 引用让 agent 主动 Read SKILL.md 才能用到（不依赖 catalogue 注册）

**配套技术配置：解决工具特有的 scope 问题**

| 工具 | 配置 | 解决什么 |
|---|---|---|
| Codex / Cursor | 无需 | 自动近端加载 AGENTS.md + 自动 scope `.agents/skills/` 子目录 |
| Claude Code | SKILL.md 加 `paths` frontmatter | Claude 全仓递归扫所有 SKILL.md，无 `paths` 时 backend 也会看到 frontend 的 skill（scope 污染） |
| Trae | 无需 | 经 AGENTS.md 引用，agent 直接 Read SKILL.md 执行 |

Claude 的 `paths` 写法：

```markdown
---
name: update-design-tokens
description: Sync design tokens from Figma to packages/frontend/src/tokens
paths: ["packages/frontend/**"]            # ← Claude 专用，Codex/Cursor 忽略
---
```

#### 3.5.4 各工具 Monorepo 注意事项

| 工具 | 关键坑 / 技巧 |
|---|---|
| **Codex** | 每层 `.agents/skills/` 可独立带 `agents/openai.yaml`；`policy.allow_implicit_invocation: false` 可强制该层只显式调用 |
| **Cursor** | 嵌套 scope 在部分版本不稳定，可用 Settings → Rules, Skills and Subagents 关闭某层加载；移动子模块目录会导致 scope 漂移 |
| **Claude Code** | **没有 `paths` 的 skill 全仓可见**——子模块 skill 必须写 paths，否则会污染其他子模块上下文；同名 skill 后加载覆盖前面，子模块覆盖根层 |
| **Trae** | 不支持嵌套 catalogue；**子模块 skills 留在 `packages/<name>/.agents/skills/`**，由该子模块 AGENTS.md Workflows 段主动发现并 Read |

#### 3.5.5 通用建议

1. **按层处理**（见 §3.5.3）：L1 项目根 skill 放根 `.agents/skills/` 靠 `description` 自动发现；L2 子模块 skill 在子模块 AGENTS.md 的 Workflows 段声明，Claude 额外加 `paths` 防 scope 污染
2. **Trae 项目只对项目根 skills 使用 symlink**；子模块 skills 不聚合，靠所属子模块 AGENTS.md 主动发现并 Read
3. **同名 skill 谨慎**：避免不同子模块使用同名 skill。Codex 可能把重复名称同时暴露给 selector，Cursor / Claude 的覆盖行为也不同；用唯一名称 + Claude `paths` 才更可预测
4. **多个子模块共享的脚本**：放根 `.agents/skills/<shared>/scripts/`，子模块 skill 通过 `../../../.agents/skills/<shared>/scripts/X.sh` 引用

### 3.6 各工具特殊注意事项

#### Claude Code

- 💡 **Skills = Slash Commands 统一**：`.claude/commands/deploy.md` 和 `.claude/skills/deploy/SKILL.md` 都创建 `/deploy`，同名时 skill 优先
- ⚠️ `allowed-tools` 在 CLI 中预批准列出的工具，但**不限制** skill 只能用这些工具；SDK 调用时忽略该字段，改由主 `allowedTools` 选项控制
- ✅ **独有能力**：`context: fork`（隔离子 agent 执行）、`!command`（注入 shell 输出）、`disable-model-invocation`（禁止自动调用）
- 💡 `~/.claude/skills/` 全局可用，跨项目复用

#### Codex

- ✅ **独有能力**：`agents/openai.yaml` 配置 UI 元数据 + invocation policy + MCP 依赖声明
- 💡 `policy.allow_implicit_invocation: false` 强制只允许 `$skill` 显式调用
- 💡 admin 级 `/etc/codex/skills/` 支持组织统一分发
- 💡 Plugin 系统可打包多个 skills + MCP 配置 + 资产

#### Cursor

- 💡 **多路径并发**：项目 `.cursor/skills/` + `.agents/skills/`，全局同样有两套，外加 `.claude/skills/` / `.codex/skills/` 兼容路径
- 💡 可用 `/slash` 或 `@-mention` 显式调用
- ⚠️ `allowed-tools` frontmatter **被忽略**，权限走 Cursor 自身设置
- 💡 可在 Settings → Rules, Skills and Subagents 中关闭 fallback 路径加载

#### opencode

- ✅ **同时原生读 `.agents/skills/`、`.claude/skills/`、`.opencode/skills/`**——同一个 skill 目录可在 Claude Code / opencode / Codex / Cursor 2.4+ / Copilot / Gemini CLI 上零胶水使用。**opencode 是兼容性最好的 reader**
- 💡 Skills **按需加载**：通过内置 `skill` 工具——SKILL.md 正文不是常驻 context，agent 先看 `name` + `description`，触发后再拉取全文
- 💡 权限是 `opencode.json` `permission.skill` 的模式匹配：
  ```json
  { "permission": { "skill": { "*": "allow", "internal-*": "deny", "experimental-*": "ask" } } }
  ```
- 💡 Per-agent 覆盖：`agent.<name>.permission.skill` 可在某个 agent 上收紧/放宽
- ⚠️ **`name` 校验比其它工具更严**：1-64 字符、全小写字母数字、单连字符（不允许 `--`）、不能首尾为 `-`，且必须与父目录名相同——任一违规 skill 被静默跳过
- ⚠️ **Skill 名跨 6 个搜索位置必须全局唯一**——重名时 opencode 任选其一，另一个被静默丢弃
- 💡 `description` 长度 1-1024 字符且是唯一路由信号——必须写 WHAT + WHEN，没有 `paths`
- 💡 frontmatter 接受 `license` / `compatibility` / `metadata`（字符串到字符串映射），未知字段静默忽略
- 💡 可以完全关闭 skill 工具（例如不应自动加载 skill 的 sub-agent），在 agent 配置里 per-agent 关掉

#### Trae

- ⚠️ **运行时只把 `.trae/skills/` 编入 catalogue**，不原生扫描 `.agents/skills/` / `.claude/skills/`。根层公共 skills 可用 symlink 或 `npx skills add --agent trae` 同步到 `.trae/skills/`
- ⚠️ **不支持嵌套 catalogue**：不会自动按子目录 scope；子模块 skills 通过所属子模块 AGENTS.md Workflows 段主动发现并 Read
- 💡 Trae 内置 `Skills-creator` skill，可对话生成新 skill
- 💡 推荐三层架构：Rules（< 1000 字符）+ Skills（详细规范）+ MCP（工具能力）
- 💡 国际版（`~/.trae/`）vs 中国版（`~/.trae-cn/`）需分别配置

---

## 四、Commands（Slash Commands，legacy）

> ⚠️ **本手册的建议：不要新增 Commands，一律改用 Skills——在每家工具上、包括 opencode。**
>
> - Claude Code 官方已把 `.claude/commands/` 标为 legacy，推荐 `.claude/skills/<name>/SKILL.md`。
> - opencode 虽然把 Commands 与 Skills 都当作一等公民，但 Skills 提供了 (a) 通过 `description` 自动激活、(b) 通过 `.agents/skills/` 跨工具复用、(c) 多文件 folder 结构——这三件 Commands 都做不到。opencode 上没有任何场景必须用 Commands。
> - Codex / Cursor / Trae 完全没有 Commands 概念。
>
> 因此本章主要作为**迁移指南**：让已有的 `.claude/commands/` 或 `.opencode/commands/` 继续工作，并把它们逐步迁到 `.agents/skills/`；新内容一律不要再放进这两个目录。

### 4.1 能力对比

| 维度 | Claude Code | opencode | Codex | Cursor | Trae |
|---|---|---|---|---|---|
| 是否有独立 commands 系统 | ⚠️ legacy | ✅ 原生 | ❌ | ❌ | ❌ |
| 项目级路径 | `.claude/commands/<name>.md` | `.opencode/commands/<name>.md`（plural，当前标准）或 `.opencode/command/`（单数、legacy compat） | — | — | — |
| 用户级路径 | `~/.claude/commands/<name>.md` | `~/.config/opencode/commands/<name>.md` | — | — | — |
| 触发方式 | `/name`（仅手动） | `/name`（仅手动） | — | — | — |
| frontmatter 字段 | `description`、`argument-hint`、`allowed-tools`、`model` | `description`、`agent` | — | — | — |
| 是否能 description 自动激活 | ❌ 永远不会 | ❌ | — | — | — |
| 子目录命名空间 | ✅ `frontend/component.md` → `/component (project:frontend)` | ✅ | — | — | — |
| 同名冲突处理 | 项目级 > 用户级；**且被同名 skill 遮蔽** | n/a | — | — | — |
| 官方推荐 | ❌ "legacy format, prefer Skills" | ⚠️ 仍支持，但 Skills 是严格超集 | — | — | — |
| **本手册建议** | ❌ 迁到 Skills | ❌ 迁到 Skills | n/a | n/a | n/a |
| 是否扫 `.agents/commands/` | ❌ | ❌ | ❌ | ❌ | ❌ |

> Codex / Cursor / Trae 完全没有 commands 文件夹概念。它们的 slash 命令要么内置在 IDE 里，要么走 Skills 表达。

### 4.2 标准命令文件格式

**Claude Code 最小**：

```markdown
---
description: 命令面板里的一句话简述
---

Prompt body. 用 $ARGUMENTS 插值用户输入参数。
```

**Claude Code 完整字段**：

```markdown
---
description: Refactor 选中代码，按项目风格指南
argument-hint: <file-path> [--strict]
allowed-tools: Read, Edit, Bash(npm test:*)
model: claude-sonnet-4-20250514
---

Refactor $ARGUMENTS following the conventions in AGENTS.md.
...
```

**opencode**：

```markdown
---
description: 命令面板里的简述
agent: review
---

调用时传给指定 agent 的指令。
```

### 4.3 Commands vs Skills：为什么 Skills 全面胜出

Claude Code 官方原话：

> The `.claude/commands/` directory is the **legacy format**. The recommended format is `.claude/skills/<name>/SKILL.md`, which supports the same slash-command invocation (`/name`) plus autonomous invocation by Claude.

| 维度 | `.claude/commands/<name>.md` | `.claude/skills/<name>/SKILL.md` |
|---|---|---|
| `/name` 手动触发 | ✅ | ✅ UX 完全一致 |
| 通过 `description` 自动激活 | ❌ 永远不会 | ✅ 可选（不设 `disable-model-invocation`） |
| 单文件 prompt | ✅ 极简 | ✅ 同样支持（单文件 skill） |
| 多文件（scripts / reference / assets） | ❌ 仅单文件 | ✅ 完整 skill 文件夹 |
| 工具白名单 | ✅ `allowed-tools` | ✅ `allowed-tools` + `disallowed-tools` |
| 子 agent 隔离执行 | ❌ | ✅ `context: fork` |
| 跨工具复用 | ❌ 仅 Claude / opencode（且字段不一致） | ✅ Cursor 2.4+/Codex/opencode/Copilot/Gemini 原生读 `.agents/skills/`，Claude/Trae 通过 symlink 桥接 |
| 官方状态 | ❌ Claude legacy；opencode 仍支持但被 Skills 严格超集 | ✅ 五家全适用，本手册推荐 |

**结论**：Skills 能做 Commands 能做的所有事，并且更多。仅当你要"纯手动触发、禁止自动激活"的 commands 行为时，Skills 也能模拟——在 SKILL.md frontmatter 加 `disable-model-invocation: true` 即可。

### 4.4 项目配置最佳实践

#### 什么时候仍需要保留 Commands

新内容一律走 **Skills 而非 Commands**——包括 opencode。仅以下两种情况可以保留 Commands 不动：

| 场景 | 处理方式 |
|---|---|
| 已有 `.claude/commands/` 或 `.opencode/commands/` 库，整体重写成本高 | 让旧文件继续工作，逐文件迁（见下方迁移指南） |
| 个人 `~/.claude/commands/*.md` / `~/.config/opencode/commands/*.md` 单行 prompt，不需要跨工具复用 | 单文件 commands 比单文件 skills 仪式更轻，作为个人草稿可以保留 |

其他所有**会进 repo 的内容** → 一律走 `.agents/skills/<name>/SKILL.md`。

#### Commands → Skills 迁移路径

单文件 command 可平移到单文件 skill（一个文件夹、一份 `SKILL.md`）：

```diff
# Claude Code
- .claude/commands/refactor.md
+ .agents/skills/refactor/SKILL.md          # 把 .claude/skills/ 桥接到 .agents/skills/，方案自选见 §3.5.2

# opencode
- .opencode/commands/refactor.md
+ .agents/skills/refactor/SKILL.md          # opencode 原生读取 .agents/skills/
```

frontmatter 字段映射（同时覆盖 Claude Code 和 opencode commands）：

| Commands 字段 | Skills 字段 | 说明 |
|---|---|---|
| `description: ...` | `description: ...` | 同名同义。**在 Skills 里同时是自动激活的依据**——想自动调用就写清 WHAT + WHEN，想保留 commands 那种"纯手动"行为就同时设 `disable-model-invocation: true` |
| `argument-hint: ...`（Claude） | `argument-hint: ...` | 同名同义 |
| `allowed-tools: ...`（Claude） | `allowed-tools: ...` | 同名同义 |
| `model: ...`（Claude） | `model: ...` | 同名同义 |
| `agent: <name>`（opencode） | （没有直接对应字段——见下方说明） | opencode commands 可路由到指定 sub-agent。迁到 Skills 时可二选一：(a) 如果工作流自包含，直接放弃这条路由；(b) 如果一定要在某个 sub-agent 的隔离上下文里跑，让 skill 在正文里指引用户/父 agent 用 `agent` 工具显式分派。绝大多数 refactor/format/triage 类工作流选 (a) |
| 无 | `name: refactor` | Skills 必填，必须匹配文件夹名，lowercase + 连字符，≤ 64 字符（opencode 校验最严） |

Body 内容原样搬过去。`$ARGUMENTS` 插值在 Claude Code 的 Skills 里行为一致；opencode 在 `.agents/skills/<name>/SKILL.md` 里也是相同处理。

#### 完整示例（Claude Code）

迁移前 `.claude/commands/refactor.md`：

```markdown
---
description: Refactor 选中文件，按项目风格指南
argument-hint: <file-path> [--strict]
allowed-tools: Read, Edit, Bash(npm test:*)
---

Refactor $ARGUMENTS following the conventions in AGENTS.md.
```

迁移后 `.agents/skills/refactor/SKILL.md`：

```markdown
---
name: refactor
description: Refactor a file to match the project style guide. Use when the user asks to refactor, clean up, or restyle a specific file path.
argument-hint: <file-path> [--strict]
allowed-tools: Read, Edit, Bash(npm test:*)
disable-model-invocation: true    # 仅手动；删掉这行即可启用自动激活
---

Refactor $ARGUMENTS following the conventions in AGENTS.md.
```

#### 完整示例（opencode）

迁移前 `.opencode/commands/refactor.md`：

```markdown
---
description: Refactor 选中文件，按项目风格指南
agent: code-reviewer
---

Refactor $ARGUMENTS following the conventions in AGENTS.md.
```

迁移后 `.agents/skills/refactor/SKILL.md`（opencode 原生读取 `.agents/skills/`）：

```markdown
---
name: refactor
description: Refactor a file to match the project style guide. Use when the user asks to refactor, clean up, or restyle a specific file path.
---

Refactor $ARGUMENTS following the conventions in AGENTS.md.

（如果一定要由 `code-reviewer` 这个 sub-agent 来执行：
让用户使用 `@code-reviewer run /refactor <path>` 调用；
或在 opencode 给 skill 加上"路由到指定 agent"字段之前，
继续保留这一个工作流在 `.opencode/commands/`。）
```

如果 `agent:` 路由是硬性需求（例如必须在隔离上下文中执行），这是 opencode 上**唯一**值得继续放在 `.opencode/commands/` 的特殊情况。等 opencode 给 skill frontmatter 加上对应字段后再重新评估。

#### 可选：`.opencode/commands/` 薄壳保留 slash 入口

opencode 的命令面板只扫描 `.opencode/commands/`。如果迁移到 Skills 后仍希望在面板里看到这个 slash 命令，可以在原位留一个一行的薄壳：

```markdown
---
description: Refactor a file to match the project style guide
---

Run the `refactor` skill on $ARGUMENTS.
```

正文已经搬到 `.agents/skills/refactor/SKILL.md`（自动发现 + 跨工具），薄壳只是为了让 slash 命令在 opencode UI 里继续可见。

#### 迁移后的推荐布局

```
.agents/skills/
├── refactor/SKILL.md          # disable-model-invocation: true（仅手动，commands 风格）
├── changelog/SKILL.md          # 自动激活：用户提到 release 时
├── triage-issue/SKILL.md       # disable-model-invocation: true
└── deploy-prod/SKILL.md        # 自动激活：用户提到 ship/release 时
```

一个 Skills 文件夹同时承载"commands 风格"（仅手动）和"skills 风格"（自动激活）的工作流——一种心智模型、一套工具链、跨五家工具兼容。

#### 为什么没有 `.agents/commands/`

与 `.agents/skills/` 不同，**没有任何主流工具原生扫描 `.agents/commands/`**：

- Claude Code 的 `/init` 和 CLI 只看 `.claude/commands/`
- opencode 看 `.opencode/commands/`（plural，当前标准；`.opencode/command/` 单数是 legacy compat）
- 社区跨工具模板有时会建 `.agents/commands/` 作为目标位，但实际是死信——没有 runtime 拿来用

加上 Commands 本身被本手册标为不推荐，新项目**没有理由建 `.agents/commands/` 目录**。请直接迁到 `.agents/skills/`，并把 `.claude/skills/` / `.trae/skills/` 桥接到它（方案自选——详见 §3.5.2 的跨设备兼容性提示）。

### 4.5 各工具特殊注意事项

#### Claude Code

- ⚠️ **`/init` 仍会脚手架出 `.claude/commands/`**，但文档说这是 legacy——覆盖或清空它，改用 `.claude/skills/`
- 💡 **同名遮蔽规则**：`.claude/skills/foo/SKILL.md` 会遮蔽 `.claude/commands/foo.md`——对增量迁移很友好（放个 SKILL.md 在旁边，skill 自动胜出）
- 💡 **项目级遮蔽用户级**：仓库内的 `.claude/commands/review.md` 在该仓库内会遮蔽你的 `~/.claude/commands/review.md`
- 💡 **子目录命名空间**：`.claude/commands/frontend/component.md` 在面板里显示为 `/component`，带命名空间 `(project:frontend)`
- 💡 `$ARGUMENTS` 占位符在 commands 和 skills 里行为一致

#### opencode

- ⚠️ **尽管 opencode 把 Commands 当一等公民，本手册仍推荐改用 Skills**：opencode 同样原生读取 `.agents/skills/`，且 Skills 是严格超集（自动激活、跨工具复用、多文件 folder）。新工作流应放进 `.agents/skills/`；只把 `.opencode/commands/` 留给已经上线的旧库或个人单行 prompt
- 💡 **sub-agent 路由（`agent:` frontmatter）** 是 Commands 唯一没有 Skills 对应物的能力——如果某个工作流**必须**在指定 sub-agent 的隔离上下文中跑，先继续保留为 Command，等 opencode 给 skill 加上对应字段；或在 `.opencode/commands/` 放一个薄壳，由它去委托 Skill（见 §4.4）
- 💡 `.opencode/commands/` 下子目录路径支持作为命名空间
- ⚠️ **单数 `.opencode/command/` 是 legacy compat**——当前文档推荐所有目录都用复数（`agents/`、`commands/`、`skills/`、`plugins/` 等）；只有遗留 repo 保留单数
- 💡 Commands 也可以在 `opencode.json` 的 `command` 键下内联定义——同样的建议：优先 Skills

#### Codex / Cursor / Trae

- ❌ 没有 commands 目录概念。slash 命令要么来自 IDE（如 Cursor 内置的 `/edit`、`/explain`），要么来自 Skills
- 💡 想做一个"command 风格"的工作流让五家都能调？写成 SKILL.md，frontmatter 设 `disable-model-invocation: true`，`name` 作为 slash 触发词

#### 跨工具复用限制

即使用 symlink，也无法让 Commands 跨工具：

```
.cursor/commands/  ← .claude/commands/   # ❌ Cursor 根本不扫这个路径
.codex/commands/   ← .claude/commands/   # ❌ Codex 没有 commands 概念
.opencode/commands/← .claude/commands/   # ⚠️ opencode 会扫，但 frontmatter 字段不一致（agent: vs allowed-tools:）
.trae/commands/    ← .claude/commands/   # ❌ Trae 没有 commands 概念
```

这是 Skills 在生态层面超越 Commands 的根本原因——`.agents/skills/` 是**五家工具中唯一被多个原生读取**的路径（Codex / Cursor 2.4+ / opencode / Copilot / Gemini），Claude / Trae 通过 symlink 桥接（详见 §3.3）。

---

## 五、Subagents（子智能体）

> **什么是**：基于文件配置的"长生命周期专项 agent"，拥有自己的 system prompt、工具白名单、模型选择和**独立 context window**。与 Skills（短工作流）/ Commands（legacy slash）同属"可调用单元"家族，区别在于：Subagents context 完全隔离、跨多轮存活。

### 5.1 能力对比

| 维度 | Claude Code | opencode | Cursor | Codex | Trae |
|---|---|---|---|---|---|
| 是否独立 subagent 系统 | ✅ 文件式 | ✅ 文件式 | ✅ Custom Modes（GUI） | ⚠️ 仅 SDK / Task 工具 | ⚠️ GUI persona |
| 项目级路径 | `.claude/agents/<name>.md` | `agent/<name>.md` | 仓库内 settings JSON | — | — |
| 用户级路径 | `~/.claude/agents/<name>.md` | `~/.config/opencode/agent/<name>.md` | 用户级 Custom Modes | — | — |
| 触发方式 | Task 工具 / `/agents` 面板 / 按 `description` 自动路由 | `@agent` 或 `/agent` | chat 面板模式切换 | 主 agent 内 `Task` 调用 | persona 切换 |
| frontmatter 字段 | `name`、`description`、`tools`、`model` | `description`、`model`、`tools`、`mode` | `name`、`description`、`tools`、`model`（JSON） | n/a | n/a |
| 独立 context | ✅ | ✅ | ✅ | ✅（Task） | ✅ |
| 继承根 AGENTS.md/CLAUDE.md | ❌ 默认不继承 | ❌ | ⚠️ 视模式 | ✅ | ⚠️ |
| 继承 rules / skills | ❌ 干净启动 | ❌ | ⚠️ | ✅ | ⚠️ |
| 按 `description` 自动选用 | ✅ | ⚠️ 部分 | ❌ 用户选 | ✅ | ❌ |
| 工具白名单 | ✅ | ✅ | ✅ | n/a | n/a |
| 跨工具复用 | ❌ Claude 专属 | ❌ opencode 专属 | ❌ Cursor 专属 | ❌ | ❌ |

> 没有跨工具的 subagent 标准。与 Skills 不同，**没有 `.agents/agents/` 这种被多家原生扫描的约定路径**。

### 5.2 标准 Subagent 文件格式

**Claude Code**：

```markdown
---
name: code-reviewer
description: PR / diff 的彻底 code review。能发现安全漏洞、性能回归、风格违规。任何非琐碎代码变更后主动调用。
tools: [Read, Grep, Glob, Bash(git diff:*), Bash(npm test:*)]
model: claude-sonnet-4-20250514
---

你是一名资深 code reviewer。任务：
1. 仔细阅读 diff
2. 标注安全 / 性能 / 风格问题
3. 按严重程度（blocker / warn / nit）输出结构化报告

不要修改代码，只输出报告。
```

**字段要点**：

- `name` — 必填，小写 + 连字符，必须等于文件名
- `description` — 必填；**这是 Claude 自动路由的依据**，写成清晰的"能力声明"
- `tools` — 可选；省略 = 继承父 agent 的工具（通常太宽），明确列出以收紧
- `model` — 可选；省略 = 用 session 默认

**opencode**：

```markdown
---
description: PR reviewer with security focus
model: anthropic/claude-sonnet-4
tools:
  read: true
  edit: false
  bash: true
mode: subagent
---
```

**Cursor Custom Modes**（通过 Settings → Chat → Custom Modes GUI 定义，导出 JSON）：

```json
{
  "name": "Reviewer",
  "tools": ["read", "grep", "terminal"],
  "model": "claude-sonnet-4",
  "instructions": "你是资深 code reviewer..."
}
```

### 5.3 Subagents vs Skills vs Commands

| 维度 | Skills | Commands | Subagents |
|---|---|---|---|
| context | 共享父 | 共享父 | **隔离、全新** |
| 生命周期 | 单次工作流执行 | 单条消息 | 多轮直到完成 |
| 工具白名单 | ✅ | ✅（Claude） | ✅ |
| 按 `description` 自动激活 | ✅ Claude/Codex/Cursor | ❌ | ✅ Claude |
| 手动调用 | `/name` 或按名 | `/name` | `Task` 工具或 `@name` |
| 最佳场景 | 可复用 SOP / 工作流 | 手动 prompt 片段（legacy） | 需要 context 隔离的长任务专家 |
| 跨工具标准 | ✅ `.agents/skills/`（5 家原生） | ❌ 仅 Claude/opencode 各自一份 | ❌ 无 |

**决策树**：

```
要封装一个可复用行为？
├── 短工作流，在主 context 中执行 → Skills（默认选择）
├── 手动 prompt 片段 → Skills（单文件 Skill，加 disable-model-invocation: true）
│   （Commands 已 legacy；opencode 上也优先 Skills——见 §四）
└── 长任务专家，不应看主 context → Subagents
    │   （PR reviewer、security auditor、从零生成文档等）
    └── 需要跨工具？→ 各工具分别重新实现，无共享格式
```

### 5.4 项目配置最佳实践

#### 何时该用 Subagents

✅ **适合**：
- 用 clean context 更好的专家（reviewer、debugger、doc-writer）
- 需要工具收紧的 agent（只读 researcher，无 Edit / Bash）
- 长任务，不想污染主 context（test runner、安全扫描）
- 成本优化：通过 `model:` 把便宜任务路由到小模型

❌ **不适合**：
- 一次性 prompt → 用 Skill
- 需要主 session 完整历史 → 用主 agent
- 想跨工具可移植 → 没有 subagent 格式是可移植的

#### 关键规则

1. **`description` 写成路由触发器，不是功能描述**。差："Reviews code"。好："任何代码变更**后主动调用**以捕获安全和性能问题——不等用户开口"

2. **明确收紧 `tools`**——Claude 默认继承父 agent 工具（通常含 Edit/Bash）。明确列出以强制只读

3. **不要在 subagent body 中重复 AGENTS.md**。Subagents 不继承 AGENTS.md；如果确实需要项目上下文，要么：
   - 通过 `Task` 调用传入（父 agent 组装 context）
   - 在 system prompt 中显式引用关键文件（`先读：AGENTS.md、packages/<x>/AGENTS.md`）

4. **一个 agent 一个职责**。不要写通用"helper"——Claude 的自动路由在 `description` 重叠时退化

5. **项目级 subagent 进 Git**（`.claude/agents/*.md` commit）。用户级（`~/.claude/agents/`）只放个人助手

#### Subagent ↔ Skill 边界

如果你的 subagent system prompt 主要是**流程**（带编号的步骤），它大概率应该是 Skill——Skills 更便宜（不分裂 context）、可移植、好测试。

只有当 **context 隔离本身**就是要的特性时，才用 subagent。

### 5.5 各工具特殊注意事项

#### Claude Code

- 💡 `/agents` 面板列出可用 subagents，可手动触发
- 💡 自动路由：Claude 发现用户请求匹配某 subagent `description` 时，会提议（或直接）调用
- ⚠️ **Subagents 不继承 CLAUDE.md / AGENTS.md / rules**——干净启动。需要项目上下文请在 system prompt 中显式引用
- ⚠️ **`tools:` 省略 = 继承父 agent 全部工具**——明确列出以收紧
- 💡 项目级 agent 遮蔽同名用户级 agent
- 💡 Subagent 内部还能通过 `Task` 调用其他 subagent（注意递归）

#### opencode

- 💡 `mode: subagent` 区分主 agent
- 💡 `tools:` 是 object（每个工具 bool），不是 list——与 Claude 不同
- ⚠️ 自动路由比 Claude 弱，通常手动调用

#### Cursor

- 💡 **Custom Modes** 是最接近的对应物。通过 Settings UI 配置，非文件式
- 💡 每个 mode 有自己的 `tools`、`model`、system prompt
- ⚠️ Modes 是用户级；团队共享需手动 export / import 或 settings sync
- 💡 Background Agents（云端）相当于运行在某个固定 subagent 模式上（见 §八 `.cursor/environment.json`）

#### Codex

- ❌ **没有文件式 subagent 系统**。subagent 行为靠 SDK / 编程层面通过 `Task` 工具实现
- 💡 CLI / TUI 中可以通过切换 `[profiles.*]`（不同模型 / sandbox / prompt）模拟——见 §八

#### Trae

- ⚠️ persona / 自定义 agent **GUI 专属**，没有文件式格式
- 💡 persona 是用户级——无法通过仓库共享
- 💡 想要可移植的专家，写成 Skill 反而更好

#### 跨工具复用上限

没有 `.agents/agents/` 标准。要在四家都有同一个专家：

1. **system prompt 写一份**到 `.agents/personas/<name>.md`（自己定的约定）
2. **包装成 Skill** 让三家读 `.agents/skills/` 的工具复用——Skills 可承载长 system-prompt-like body，只是失去 context 隔离
3. **再编码为 Claude subagent**（`.claude/agents/<name>.md`）——仅当真的需要 context 隔离

经验：90% 的"subagent"需求其实可以用 Skills 满足。只有 context 隔离是核心特性时才用 subagent。

---

## 六、Hooks（事件钩子）

> **什么是**：agent 生命周期事件（工具调用前后、用户消息、session 结束等）触发的 shell 命令 / 脚本 / plugin。用于**安全强制**（拦截危险命令）、**审计日志**、**自动格式化**、**策略闸门**。是**唯一系统化**的强制手段——Rules / AGENTS.md 是建议性的，Hooks 是机械式的。
>
> **工具覆盖（2026-06）**：原生 hooks 现已在 **Claude Code、Codex、Cursor、opencode** 四家落地。Codex 的 hook schema 是**有意对齐 Claude** 的（相同的 `hooks.json` 骨架、相同的 stdin 协议、exit 2 = block 同义），同一份 shell 脚本可以同时服务两家。**Trae 是五家中唯一没有原生 hooks 的**——多个 FR 在排队但未实现。

### 6.1 能力对比

| 维度 | Claude Code | opencode | Cursor | Codex | Trae |
|---|---|---|---|---|---|
| 是否有专门 hook 系统 | ✅ 丰富（shell 脚本） | ✅ 丰富（**JS/TS plugin**） | ✅（较新，shell 脚本） | ✅ **v0.117 起稳定**（Claude 兼容形态，shell 脚本） | ❌（FR 已开：Trae-AI/TRAE#2436、bytedance/trae-agent#397） |
| 配置位置 | `.claude/settings.json` `hooks` 块、或 `.claude/hooks.json` | `.opencode/plugins/` 或 `~/.config/opencode/plugins/`，也可在 `opencode.json` 写 `"plugin": [...]` 引 npm 包 | `.cursor/hooks/` + `hooks.json` | `~/.codex/hooks.json` 或 `~/.codex/config.toml` 内联 `[hooks]`；plugin bundle 走 `hooks/hooks.json`；项目级走 `requirements.toml` 托管 | n/a |
| 可挂事件 | PreToolUse、PostToolUse、UserPromptSubmit、Notification、Stop、PreCompact、SessionStart、SessionEnd | **25+ 事件**：`tool.execute.before/after`、`session.created/idle/error/updated`、`file.edited`、`command.executed`、`experimental.session.compacting` 等 | PreToolUse、PostToolUse、BeforeSubmit、AfterResponse | **10 个**：SessionStart、SubagentStart、PreToolUse、**PermissionRequest**（Codex 专属）、PostToolUse、PreCompact、PostCompact、UserPromptSubmit、SubagentStop、Stop | n/a |
| 工具名 matcher | ✅ glob / regex `matcher: "Bash"` | ✅ 在 JS 里基于 `input.tool` 条件判断 | ✅ | ✅ regex；canonical names `Bash`、`apply_patch`、`mcp__server__tool`；`apply_patch` 还接受 `Edit`/`Write` 别名（但输入仍报 `apply_patch`） | n/a |
| 能否拦截工具执行 | ✅ exit code 2 + stderr | ✅ hook 内 throw 或返回 blocking response | ✅ | ✅ exit code 2 + stderr **或** stdout JSON `{"decision":"block","reason":"…"}` | n/a |
| 接收事件数据 | ✅ stdin JSON | ✅ 作为 JS 函数参数 | ✅ | ✅ stdin JSON（与 Claude 字段一致：`hookEventName`、`session_id`、`cwd`、`tool_name`、`tool_input` 等） | n/a |
| 同步阻塞 vs 异步 | 同步（agent 等待） | **原生 async**（返回 Promise） | 同步 | 同步；每个 handler 支持 `timeout` 字段 | — |
| 项目级 + 用户级 | ✅ 项目级 > 用户级 | ✅ 两个都加载，hooks 按顺序全部执行（不互相 shadow） | ✅ | ✅ 用户级（`~/.codex/`）+ plugin 自带 + `requirements.toml` 托管；所有匹配 handler 按声明顺序执行 | — |
| 跨工具标准 | ❌ 各家 schema 不同 | ❌ JS plugin API 是 opencode 专属 | ❌ | ⚠️ **schema 与 Claude 兼容**（同 `hooks.json` 骨架、`matcher` + `type: "command"`）；`hookshot` 等路由脚本可同时服务两家 | — |

> **Codex hooks 已落地并稳定**（v0.114 引入 SessionStart/Stop → v0.117 加 PreToolUse/PostToolUse + UserPromptSubmit → 之后加上 SubagentStart/Stop、PreCompact/PostCompact 以及 Codex 专属的 PermissionRequest）。Feature flag `[features].hooks` 默认开启；旧 key `codex_hooks = true` 作为 deprecated alias 仍可用。schema 故意对齐 Claude，目的是让同一份脚本可以同时跑在两边。
>
> **Trae 现在是五家中唯一没有原生 hooks 的工具**。多个 FR 在排队（Trae-AI/TRAE#2436、bytedance/trae-agent#397、forum.trae.cn #18062）但均未合入。Trae 项目只剩 git pre-commit + CI 一条强制路径；IDE 内仍只有 GUI 权限提示。
>
> **opencode 是形态上的异类**：Claude / Codex / Cursor 用声明式 JSON + shell 脚本，opencode 用 **JavaScript/TypeScript plugin** 订阅 25+ 生命周期事件。plugin 还能注册新工具、替换 context compaction prompt——更编程化、声明性更弱。

### 6.2 标准 Hook 配置

**Claude Code (`.claude/settings.json`)**：

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": ".claude/hooks/block-dangerous-bash.sh" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": "npx prettier --write \"$CLAUDE_TOOL_FILE_PATH\"" }
        ]
      }
    ],
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command", "command": ".claude/hooks/log-prompt.sh" }] }
    ]
  }
}
```

**示例 hook 脚本（`.claude/hooks/block-dangerous-bash.sh`）**：

```bash
#!/usr/bin/env bash
INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if echo "$CMD" | grep -Eq '\brm -rf /|\bsudo|\bcurl .* \| sh\b'; then
  echo "BLOCKED: dangerous command pattern" >&2
  exit 2
fi
exit 0
```

**exit code 约定**（Claude Code）：

| exit | 行为 |
|---|---|
| 0 | 放行，无消息 |
| 1 | 放行，stderr 作为 warning 浮出 |
| 2 | **拦截**工具调用，stderr 作为反馈喂给 model |

**opencode（`.opencode/plugins/<plugin>.ts`）**：

opencode hooks 是 **JavaScript/TypeScript plugin**，不是 shell 脚本。一个 plugin 是返回事件 → handler 对象的 async 函数：

```typescript
import type { Plugin } from "@opencode-ai/plugin";

export const AuditPlugin: Plugin = async (ctx) => {
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool === "bash" && /\brm -rf \/|\bsudo\b/.test(input.params.command)) {
        throw new Error(`BLOCKED: dangerous command pattern in ${input.params.command}`);
      }
      await ctx.fs.appendFile(".opencode/audit.jsonl",
        JSON.stringify({ ts: Date.now(), tool: input.tool, params: input.params }) + "\n");
    },
    "session.idle": async () => {
      console.log("[audit] session ended");
    },
  };
};
```

**加载机制**：放到 `.opencode/plugins/`（项目）或 `~/.config/opencode/plugins/`（全局），或在 `opencode.json` 注册 npm 包：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": ["opencode-helicone-session", "@my-org/audit-plugin"]
}
```

**关键事件**（部分——完整 25+ 列表见 opencode plugin 文档）：

| 事件 | 触发时机 |
|---|---|
| `tool.execute.before` | 任何工具调用前；throw 即拦截，mutate `input` 即修改 |
| `tool.execute.after` | 工具返回后；可检查 `output` |
| `command.executed` | slash 命令执行后 |
| `session.created` / `session.idle` / `session.error` / `session.updated` | 会话生命周期 |
| `file.edited` | agent 编辑文件后 |
| `experimental.session.compacting` | context 压缩前——可注入领域 context 或彻底替换压缩 prompt |

**Codex（`~/.codex/hooks.json` — 与 Claude schema 兼容）**：

Codex 故意把 schema 对齐 Claude Code，一份脚本可以同时服务两家。Hooks 落在用户级；项目级策略通过 **plugin** 或 `requirements.toml` 托管投递（见后）。通过 `config.toml` 中的 `[features].hooks = true|false` 启停；旧 key `codex_hooks` 是 deprecated alias。

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

等价的内联 TOML（`~/.codex/config.toml`）：

```toml
[[hooks.PreToolUse]]
matcher = "Bash|apply_patch|mcp__.*"

[[hooks.PreToolUse.hooks]]
type = "command"
command = "$HOME/.codex/hooks/block-dangerous.sh"
timeout = 5
```

**Codex hook 脚本——与 Claude 完全一致的 stdin/stdout 协议**：

```bash
#!/usr/bin/env bash
# Codex PreToolUse hook — 拦截危险 bash。无需改动即可跑在 Claude。
INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name')
CMD=$(echo "$INPUT"  | jq -r '.tool_input.command // empty')

if [ "$TOOL" = "Bash" ] && echo "$CMD" | grep -Eq '\brm -rf /|\bsudo|\bcurl .* \| sh\b'; then
  echo "BLOCKED: dangerous command pattern" >&2
  exit 2     # exit 2 + stderr → 拦截，反馈喂回 model
fi
exit 0
```

Codex 还支持在 stdout 返回结构化 JSON（Claude 的超集）：

```json
{ "decision": "block", "reason": "rm -rf / blocked by policy", "systemMessage": "Use rm -rf ./build instead." }
```

**exit code 约定**（Codex——与 Claude 在 0/1/2 上完全一致，额外支持结构化 JSON）：

| exit | 行为 |
|---|---|
| 0 | 放行；若 stdout 是 JSON，会解析 `decision`、`systemMessage`、`updatedInput`、`continue` 等字段 |
| 1 | 放行；stderr 作为 warning 浮出 |
| 2 | **拦截**工具调用，stderr 作为反馈喂给 model |

**项目级 hook 的特殊性**：Codex **不会**扫 repo 里的 `.codex/hooks.json`。项目策略走以下两条路：

- **plugin bundle**——把 `hooks/hooks.json`（或 plugin manifest 中 `"hooks"` 字段指向的路径）放进一个可安装的 plugin
- **`requirements.toml`**——repo 内的托管 hooks 清单，含 `[features].hooks = true` 与 `[[hooks.PreToolUse]]` 等表；Codex 首次加载时会提示用户显式信任

这是与 Claude 形态的**主要差别**：Claude 项目级 hook 直接放 `.claude/settings.json` 就行，Codex 需要走一份用户明确信任的 manifest。

### 6.3 项目配置最佳实践

#### 常见模式

| 模式 | 事件 | 用途 |
|---|---|---|
| **审计日志** | `UserPromptSubmit`、`PreToolUse` | append 到 `.claude/audit.jsonl`，事后复盘 / 合规 |
| **拦截危险命令** | `PreToolUse`（`matcher: Bash`） | 模式匹配 `rm -rf`、`curl … \| sh`、`sudo`、密钥外泄 |
| **修改后自动格式化** | `PostToolUse`（`matcher: Edit\|Write`） | 对被编辑文件跑 prettier / rustfmt / black |
| **Lint guard** | `PostToolUse` | 跑 linter，exit 1 浮出为 warning，让 model 自纠 |
| **长任务通知** | `Notification` | agent 等用户时发 Slack / 桌面通知 |
| **Session 包裹** | `SessionStart`、`SessionEnd` | 快照 context、记录耗时 / 成本 |
| **Compaction 保护** | `PreCompact` | 压缩前存盘，避免信息丢失 |

#### 关键规则

1. **Hooks 是同步的——保持快速**。> 1s 就明显拖慢 agent。重操作（全量测试）请异步在后台跑，结果通过别处暴露

2. **happy path 总是 `exit 0`**。成功分支后忘记 `exit 0` 可能误拦工具

3. **`exit 2` 永远不要带敌意消息**。stderr 文本会喂回 model 作为指导——写成"agent 该学到什么"的错误消息：*"Blocked: 文件 X 按 `.agents/rules/protected-paths.md` 是只读的，请用 Y 替代"*

4. **`.claude/hooks/`、`.claude/settings.json` hook 块 commit 到 Git**。hooks 是团队策略，不是个人偏好

5. **用户级 hook（`~/.claude/settings.json`）不能假设 repo 上下文**。它们在每个 repo 都跑——防御式编写

6. **不要在 hook 中调 MCP server 或工具**——不支持重入，危险

7. **把 hook 脚本当作任意代码执行路径**：它们以当前用户的 shell 权限在每个匹配事件上跑（不是提权，而是和 agent 同权限），一旦被注入就污染整个 session（文件访问、网络、env 里的密钥）。**像审 shell rc 里 `source` 的脚本一样审 hook**——连脚本拉的依赖一起审。脚本路径要 pin 死（`.claude/hooks/...`），永远不要把 stdin 的 JSON `eval` 进 shell，hook PR review 严格度对齐 auth 相关 PR

#### 与其他维度的分层

| 关注点 | 落点 |
|---|---|
| "别动 `vendor/`" 建议性 | AGENTS.md / Rules |
| "别动 `vendor/`" 强制性 | Hook（`PreToolUse` `matcher: Edit`，检查路径，exit 2） |
| "每次编辑后 prettier" | Hook（`PostToolUse`） |
| "所有变更后 `npm test`" | Skill（工作流）——hook 太重 |
| "拦截 secret commit" | git pre-commit hook（agent 之外）+ `PreToolUse` 对 `Bash(git commit:*)` 做纵深防御 |

### 6.4 各工具特殊注意事项

#### Claude Code

- 💡 hooks 块在 `.claude/settings.json`（项目）或 `~/.claude/settings.json`（用户），schema 一致
- 💡 `matcher` 接受工具名或 regex：`"Bash"`、`"Edit\|Write"`、`"*"`（全部）
- 💡 hook stdin payload 含：`tool_name`、`tool_input`、`session_id`、`transcript_path`
- 💡 Claude 注入的 env：`$CLAUDE_TOOL_FILE_PATH`、`$CLAUDE_SESSION_ID`
- ⚠️ 项目和用户 settings 中同名事件 hook **全都跑**，项目不遮蔽用户
- ⚠️ hook 失败不重试——脚本要幂等
- 💡 `/hooks` slash 命令显示已注册 hooks 和近期调用

#### opencode

- 💡 **Plugin（非 shell hook）**：用 JS/TS 编写、原生 async、可订阅 25+ 事件，甚至可注册自定义工具
- 💡 本地 plugin 放在 `.opencode/plugins/`（项目）或 `~/.config/opencode/plugins/`（全局）；npm 包通过 `opencode.json` 的 `"plugin": [...]` 注册
- 💡 加载顺序：全局 config → 项目 config → 全局 plugins 目录 → 项目 plugins 目录；**所有 hook 按序执行**（不互相 shadow）
- 💡 Plugin 可以同时带一个旁路 SKILL.md，教 agent 如何用它注册的工具
- ⚠️ Bun 用于 plugin 依赖安装（启动时如果存在 `.opencode/package.json` 会自动跑 `bun install`）
- 💡 `experimental.session.compacting` 是唯一能改 context compaction 的位置——长会话的强杠杆

#### Cursor

- 💡 hooks 是 2026 新增——与 Claude 功能对等约 80%
- ⚠️ 改 `hooks.json` 要 Reload Window（Cmd+Shift+P）
- 💡 Background Agents 同样遵守 hooks（CI 侧强制很好用）

#### Codex

- ✅ **原生 hooks 已稳定**（v0.117 起 PreToolUse / PostToolUse + UserPromptSubmit；v0.114 起 SessionStart/Stop；之后陆续加上 SubagentStart/Stop、PreCompact/PostCompact 以及 Codex 专属的 **PermissionRequest**）。Feature flag `[features].hooks = true` 默认开启；旧 key `codex_hooks` 是 deprecated alias
- 💡 **schema 与 Claude 兼容**：相同 `hooks.json` 骨架、相同 `matcher` + `type: "command"` 形态、相同 stdin JSON 协议、相同 exit 2 = block 语义 → 一份 shell 脚本可以同时跑在 Codex 与 Claude
- 💡 **PermissionRequest 是 Codex 专属**——只在 Codex 即将向用户弹审批提示时触发；适合按策略自动 allow/deny 而不动 PreToolUse
- ⚠️ **matcher canonical names** 是 `Bash`、`apply_patch`、`mcp__server__tool`。`apply_patch` 还接受 `Edit` / `Write` 别名，但 stdin 仍报 `tool_name: "apply_patch"`——hook 逻辑请基于 canonical name 而非别名写
- ⚠️ **Bash 桥**（Codex 0.130+）：很多文件编辑实际走 `Bash` 而非 `apply_patch` / `Edit` / `Write`。要全覆盖编辑事件，`PreToolUse` / `PostToolUse` 的 matcher 推荐写成 `Bash|apply_patch|mcp__.*`
- ⚠️ **没有 `.codex/hooks.json` 这条 repo 路径**：项目策略要走（a）**plugin bundle**（`hooks/hooks.json` 放进可安装 plugin）或（b）**`requirements.toml`**（repo 内的托管 manifest，用户首次需显式信任）。用户级永远在 `~/.codex/hooks.json` 或 `~/.codex/config.toml [hooks]`
- 💡 `PreToolUse` 支持 `updatedInput` 字段——可以**改写**工具调用（如改写命令行），Claude 没有这个杠杆
- 💡 sandbox + `approval_policy` 仍是有用的第二层（限制爆炸半径）——见 §八——但"拦截 / 日志 / 格式化"这些主用例现在 hooks 已经覆盖，不再需要外挂胶水

#### Trae

- ❌ **截至 2026-06 仍无原生 hooks**。多个 FR 在排队：
  - [Trae-AI/TRAE#2436](https://github.com/Trae-AI/TRAE/issues/2436) — Builder/Agent mode 生命周期 hooks
  - [bytedance/trae-agent#397](https://github.com/bytedance/trae-agent/issues/397) — 外部工具集成 lifecycle hooks
  - [forum.trae.cn #18062](https://forum.trae.cn/t/topic/18062) — `beforeToolCall` Hook API
- 💡 IDE 内权限只有 GUI 提示，无法编程式 block / mutate
- 💡 在 Trae 原生支持之前，团队策略只能落到 **git pre-commit + CI**（agent 之外）；把 Trae 当作"agent 运行时无强制"对待

#### 跨工具纵深防御

虽然没有完全可移植的 hook 格式，但 **Claude + Codex 共用同一份 schema**，因此一份 shell 脚本 + 一份 `hooks.json` 骨架就能同时覆盖两家。需要让策略在所有五家工具上都生效时分层：

1. **git pre-commit / pre-push hooks** — commit 时无论哪家 agent 都拦（对 Trae 而言是**唯一**有效层）
2. **CI 检查** — 最后一关，任何漏网之鱼都被抓
3. **工具专属 agent 运行时 hook**：Claude + Codex（共享脚本）、opencode（JS/TS plugin）、Cursor（shell）
4. **sandbox modes / per-tool permission** 作为爆炸半径限制（Codex、opencode）——与 hooks 互补，不是替代
5. **AGENTS.md 建议性规则** — 说明意图

Hook 是**支持它的四家工具上 agent 运行时唯一的机械强制**；其它要么 pre-runtime（git/CI），要么建议性（AGENTS.md / Rules）。Trae 仍然是必须靠 pre-runtime 兜底的缺口。

---

## 七、MCP（Model Context Protocol）

### 7.1 能力对比

| 维度 | Claude Code | Codex | Cursor | opencode | Trae |
|---|---|---|---|---|---|
| 项目级配置 | `.mcp.json`（repo 根） | `.codex/config.toml` | `.cursor/mcp.json` | `opencode.json` `mcp` 块（项目根） | `.trae/mcp.json` ⚠️ |
| 用户级配置 | `~/.claude.json` | `~/.codex/config.toml` | `~/.cursor/mcp.json` | `~/.config/opencode/opencode.json` `mcp` 块 | OS 特定路径 |
| Scope 数量 | 3（local / project / user） | 2（project / user） | 2（project / user） | 2（project / user）+ remote `.well-known/opencode` 组织默认 | 2（project / user） |
| 配置格式 | JSON | TOML | JSON | JSON（嵌在 `opencode.json` 内） | JSON |
| 项目级是否 commit Git | ✅ 设计为团队共享 | ✅ | ✅ | ✅ | ✅ |
| 项目级稳定性 | ✅ 稳定 | ✅ 稳定 | ✅ 稳定 | ✅ 稳定 | ⚠️ **实验性/Beta** |
| 优先级（同名冲突） | local > project > user | 项目 > 用户 > 系统 | 项目 > 全局 | inline env > project > global > remote/managed | 项目 > 全局 |
| 环境变量插值 | ✅ | ✅ | ✅ `${env:NAME}` `${workspaceFolder}` | ✅ 通过 per-server `environment` 表 | ✅ `${workspaceFolder}` |
| CLI 管理命令 | `claude mcp add/list/remove` | `codex mcp add/list/login` | UI + 编辑文件 | 直接编辑 `opencode.json` | UI + 编辑文件 |
| 远程 SSE/HTTP | ✅ | ✅ | ✅ | ✅ `type: "remote"` + OAuth 支持 | ✅ |
| 不删除即禁用 | ✅ | ✅ | ✅ | ✅ `"enabled": false` 开关 | ✅ |
| Per-agent 启停 | ❌ | ❌ | ❌ | ✅ 全局禁用，在 `agent.<name>.tools` 单独打开 | ❌ |

### 7.2 配置文件示例

#### Claude Code `.mcp.json`

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

#### Codex `~/.codex/config.toml`（或项目 `.codex/config.toml`）

```toml
[mcp_servers.github]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]

[mcp_servers.github.env]
GITHUB_PERSONAL_ACCESS_TOKEN = "${env:GITHUB_TOKEN}"
```

#### Cursor `.cursor/mcp.json`

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

#### Trae `.trae/mcp.json`（⚠️ 实验性）

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

#### opencode `opencode.json`（项目；全局是 `~/.config/opencode/opencode.json`）

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
  // 全局禁用某 MCP server 的所有工具，再在 agent 上按需放开
  "tools": { "github_*": false },
  "agent": {
    "release-bot": {
      "tools": { "github_*": true }
    }
  }
}
```

**opencode 专属说明**：
- 字段名是 `mcp`（不是 `mcpServers`）
- 本地 server：`type: "local"` + `command: [...]`（数组，不是字符串）
- Remote：`type: "remote"` + `url` + 可选 `headers` / `oauth` / `timeout`（毫秒，默认 5000）
- `enabled: false` 是非破坏性禁用
- 工具门控走顶层 `tools` 映射（通配符模式），per-agent 通过 `agent.<name>.tools` 覆盖

### 7.3 项目配置最佳实践

1. **`.mcp.json` 类文件提交 Git，但用环境变量引用密钥**

   ```json
   "env": { "API_KEY": "${env:API_KEY}" }
   ```

2. **`.gitignore` 加入 `.env`、`.cursor/.env` 等含真值的辅助文件**

3. **项目专属服务器（如项目数据库）放项目级**，通用工具（GitHub、Web search）放用户级

4. **每次改完配置文件，必须重启/重载工具**：
   - Cursor: Cmd+Shift+P → "Reload Window"
   - Claude Code: 重启 session，或 `/mcp reconnect`
   - Codex: 重启 session（TUI 一次启动只加载一次）
   - Trae: Reload Window

### 7.4 各工具特殊注意事项

#### Claude Code

- ⚠️ **不要把 Claude Desktop 的 `claude_desktop_config.json` 当成 Claude Code 配置**——它们是不同的应用
- 💡 从 Desktop 迁移：`claude mcp add-from-claude-desktop`
- ⚠️ Project-scope 第一次进项目会**弹窗要求用户批准**，是安全护栏，不要绕过
- 💡 三个 scope 用 `claude mcp add -s {local|project|user}` 显式指定
- 💡 `/mcp` 命令查看连接状态、`/mcp reconnect` 重连

#### Codex

- 💡 **统一配置栈**：CLI、VS Code、Desktop 都读同一份 `config.toml`
- 💡 用 `codex mcp add/list/login` 管理，自动写入 TOML
- ⚠️ 每个 MCP server 都会向 context 注入工具 schema，不用的要禁用以省 token
- 💡 优先级：CLI flags → profile → 项目 config → 用户 config → 系统默认

#### Cursor

- 💡 **`mcp.json` 格式几乎与 Claude Desktop 一致**，可直接复用
- ⚠️ 修改后必须 Reload Window（Cmd+Shift+P）
- 💡 项目级 `.cursor/mcp.json` 和全局 `~/.cursor/mcp.json` 自动合并，同名时项目优先
- 💡 Settings → MCP 面板可实时查看连接状态、错误详情、工具数量
- 💡 企业可通过扩展 API 程序化注册 MCP，无需修改 mcp.json

#### opencode

- 💡 **MCP 配置嵌在 `opencode.json` 内**（不是独立文件）——同一文件同时含 agents / commands / plugins / models / providers / permissions / mcp
- 💡 **per-agent gating 是一等公民**：全局禁用一个嘈杂 MCP server 的所有工具（`"tools": { "myserver_*": false }`），仅在需要它的 agent 上放开（`agent.<name>.tools.myserver_*: true`）——为不需要该 MCP 的 agent 节省 context tokens
- 💡 **Remote MCP 原生支持 OAuth**（`oauth` 对象）——Claude / Codex / Cursor 只支持 bearer header
- 💡 **用 `bunx`**（不是 `npx`）作为命令运行器——opencode 自带 Bun，启动更快
- 💡 schema URL `https://opencode.ai/config.json` 给编辑器完整 JSON schema 自动补全
- 💡 **组织级分发**：`.well-known/opencode` 允许组织向所有用户推默认配置（含 MCP）——企业级 rollout 的利器
- 💡 AGENTS.md 可以写 MCP 使用提示（如*"需要搜文档时使用 `context7` MCP server"*）——opencode 把它自然当成常驻 rules

#### Trae

- ⚠️ **项目级 MCP 是实验性/Beta**，部分文档明确警告"agent cannot access project-level MCP servers"——生产环境优先用全局配置
- 💡 启用项目级 MCP：Settings → MCP → 打开"启用项目级 MCP"开关
- 💡 全局路径因 OS 而异：
  - macOS: `~/Library/Application Support/Trae/User/mcp.json`
  - Windows: `%APPDATA%\Trae\User\mcp.json`
  - Linux: `~/.config/Trae/User/mcp.json`
- 💡 内置 MCP 市场，可一键安装
- 💡 仅支持 `${workspaceFolder}` 变量插值，不如 Cursor 丰富

---

## 八、Settings / Permissions / Sandbox

> **什么是**：控制 agent **能做什么**（工具白名单、文件写权限、网络访问）、**怎么被审批**（自动 / 失败时 / 总是问）、**怎么执行**（sandbox mode、env、statusline、模型默认）的运行时配置。最容易被忽视的维度——生产事故大多是权限配置错，不是 prompt 写得差。

### 8.1 能力对比

| 维度 | Claude Code | Codex | Cursor | opencode | Trae |
|---|---|---|---|---|---|
| 项目级配置文件 | `.claude/settings.json` | `.codex/config.toml` | `.cursor/environment.json`（background）+ UI | `opencode.json`（项目根） | 仅 UI |
| 用户级配置文件 | `~/.claude/settings.json` | `~/.codex/config.toml` | UI（synced） | `~/.config/opencode/opencode.json` | 仅 UI |
| 本地 only 覆盖 | `.claude/settings.local.json`（gitignored） | `[profiles.*]` 切 profile | 本地 UI 覆盖 | `OPENCODE_CONFIG` env 指定路径，或 `OPENCODE_CONFIG_CONTENT` 内联 | n/a |
| 权限模型 | allow/deny/ask **按工具+模式** | **sandbox mode + 审批策略** 组合 | bash 命令白名单 + 工具开关 | **per-tool allow/deny/ask + per-pattern bash matcher + per-agent override** | GUI 提示 |
| sandbox mode | n/a（靠权限模式） | ✅ `read-only` / `workspace-write` / `danger-full-access` | ✅ Auto Mode + 白名单 | ⚠️ 无 OS 级 sandbox；靠 permission gating | ⚠️ 隐式提示 |
| 审批策略 | "ask" 模式 | ✅ `never` / `on-failure` / `on-request` / `untrusted` | Auto Mode 开关 | `"ask"` permission action；per-tool | GUI |
| 配置内 env 变量 | ✅ `env: {KEY: "..."}` | ✅ `[env]` table | `.cursor/environment.json` `env` | per-MCP `environment` 表；agent 进程继承 shell env | n/a |
| Statusline 定制 | ✅ `statusLine`（shell 命令） | ❌ | ✅ `statusline` | ✅ 通过 plugin（`statusline` 配置 + plugin 事件） | ❌ |
| 项目内多 profile | ❌ | ✅ `[profiles.*]` | ❌ | ✅ 多个 `agent.<name>` 块即 profile | ❌ |
| Background / cloud agent 配置 | n/a | `[profiles.*]` for headless | `.cursor/environment.json` | 非交互模式（`opencode run` + flags） | n/a |
| 组织/管理员推送 | ❌ | ❌ | Enterprise 面板 | ✅ remote `.well-known/opencode` + macOS MDM `.mobileconfig` | ❌ |
| 跨工具标准 | ❌ 各家 schema 不同 | ❌ | ❌ | ❌ | ❌ |

> Settings 是**最不可移植**的维度。哪怕"允许 `npm test`"这种概念，在各家也是完全不同的机制。
>
> **opencode 的配置分层最深**（5 个工具中最多）：8 层（org remote → user → env override → project → `.opencode/` dirs → inline env → managed dir → MDM），为企业级 rollout 设计。

### 8.2 权限模型详解

#### Claude Code：模式白名单

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

**模式语法**：
- `Tool(pattern)` — 文件类工具用 glob，Bash 用 `前缀:*`
- `**` 匹配任意路径
- 优先级：`deny` > `ask` > `allow`；无匹配则回落到默认（ask）

#### Codex：sandbox + approval policy

两个正交轴，组合使用：

| `sandbox_mode` | 效果 |
|---|---|
| `read-only` | 不能写、不能执行、不能联网。探索场景最安全的默认 |
| `workspace-write` | **工作区内**可改文件、可执行命令。无网络。**推荐生产默认** |
| `danger-full-access` | 无 sandbox。完整宿主机访问。**仅在 CI / headless 受控环境用** |

| `approval_policy` | 效果 |
|---|---|
| `never` | 永不问。与 `read-only` 搭配做无人值守探索，或在 CI 配 `danger-full-access` |
| `on-failure` | 工具失败时才问。"信任但验证" |
| `on-request` | agent 自己决定何时问。最平衡的默认 |
| `untrusted` | 每次潜在变更都问。敏感仓库用 |

```toml
# ~/.codex/config.toml 或项目 .codex/config.toml
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

**激活 profile**：`codex --profile ci`（CLI）或 `CODEX_PROFILE=ci`。

#### Cursor：Auto Mode + 白名单

```jsonc
// Cursor settings (UI) — 导出结构
{
  "cursor.chat.autoMode": true,
  "cursor.chat.allowedCommands": ["npm test", "npm run lint", "git status"],
  "cursor.chat.deniedCommands": ["rm -rf", "sudo", "npm publish"]
}
```

- **Auto Mode ON** → 白名单命令直接执行
- **Auto Mode OFF** → 每条命令都要点确认
- 工具开关（Read、Edit、Terminal、MCP）也在 UI

#### Trae：只有 GUI 提示

没有声明式权限文件。每个潜在变更工具调用都触发 GUI 提示，除非之前选了"始终允许"（存在用户级 IDE 设置，不在仓库）。

**含义**：Trae 无法在仓库中编码团队权限策略。真正的闸门要靠 git pre-commit hook + CI。

#### opencode：per-tool + per-pattern + per-agent

opencode 的权限模型在 5 个工具中最细粒度。权限写在 `opencode.json`：

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

- **权限 key**：`read`、`edit`、`glob`、`grep`、`list`、`bash`、`task`、`external_directory`、`lsp`、`skill`——每个接受 shorthand（`"allow" | "ask" | "deny"`）或模式映射
- **模式匹配**同时作用于 bash 命令、skill 名、MCP 工具名：`"mymcp_*": "deny"` 拒掉某 MCP server 全部工具
- **per-agent override**：严格的 agent（如 reviewer）可以拒绝全局允许的；高权限 agent（如 release-bot）可以单独放开特定模式
- **无 OS 级 sandbox**：opencode 不在 Seatbelt / landlock 沙箱中运行（不像 Codex）——permission 模型是唯一闸门。要强隔离请把 opencode 跑在容器或 VM 里

### 8.3 Sandbox 模型（Codex）深入

Codex 是唯一有真 OS 级 sandbox 的工具。模式对应平台机制：

- **macOS**：`sandbox-exec` profile（Seatbelt）——限制写到工作区，拒网络
- **Linux**：`landlock` + `seccomp` —— 同效果
- **Windows**：有限；基本只是建议

```toml
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = false        # 默认
exclude_tmpdir_env_var = false
exclude_slash_tmp = false
writable_roots = ["./build", "./node_modules/.cache"]
```

**常见坑**：
- `network_access = false` 让 `npm install` 失败。要么开 `true`，要么预装依赖
- `writable_roots` 是**追加**到工作区——用来放仓库外的 build cache

### 8.4 Background / Cloud Agents：`.cursor/environment.json`

Cursor 的 background agent（和 cloud agent）在 ephemeral 容器里跑，需要显式配置：

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

- `snapshot` — 基础镜像
- `install` — 一次性 setup，按 snapshot 缓存
- `terminals` — 长任务（dev server、watch）
- `env` — agent 进程能看到的 env；**不要放密钥**，用 `${env:NAME}` + 在 Cursor 设置中配密钥

**`.cursor/environment.json` 进 Git** — 团队配置不是个人偏好。

### 8.5 项目配置最佳实践

#### 分层：project / user / local

| 文件 | 提交 | 用途 |
|---|---|---|
| `.claude/settings.json` | ✅ | 团队策略：permissions、hooks、statusline、env 默认 |
| `.claude/settings.local.json` | ❌（gitignore） | 个人覆盖（开发个人 key、explore 时放宽权限） |
| `~/.claude/settings.json` | n/a | 跨 repo 个人默认 |
| `.codex/config.toml` 项目 | ✅ | 本仓库的团队 profile、model、sandbox |
| `opencode.json`（项目） | ✅ | opencode 团队配置：permissions、agents、MCP、plugins、providers |
| `~/.config/opencode/opencode.json` | n/a | 跨 opencode repo 用户默认 |
| `.opencode/` 目录 | ✅ | per-repo agents/、commands/、skills/、plugins/、modes/ |
| `~/.codex/config.toml` | n/a | 个人默认 + profiles |
| `.cursor/environment.json` | ✅ | background agent 团队配置 |

#### 关键规则

1. **项目配置总 commit；本地配置总 gitignore**。上表矩阵刻意如此设计——团队策略共享，个人例外不外泄

2. **`deny` > `ask` > `allow`**。任何破坏性操作（`rm -rf`、`sudo`、`git push --force`、`npm publish`、`kubectl delete`）在项目级写 deny。永远不要相信用户级

3. **Codex 默认 `workspace-write` + `on-request`**（人监督开发）。只在 `read-only` 搭配或受控 CI 下提升到 `never`

4. **密钥用 env 间接引用，永不内联**：
   ```json
   "env": { "GITHUB_TOKEN": "${env:GITHUB_TOKEN}" }   // ✅
   "env": { "GITHUB_TOKEN": "ghp_xxxxx" }              // ❌ 被 commit
   ```

5. **不可共享格式时，至少镜像权限意图**。Claude `permissions.deny` 拦 `Bash(rm -rf:*)`，那 Codex 就设 `sandbox_mode = "workspace-write"`（拦系统写），Cursor 把 `rm -rf` 加到 `deniedCommands`。**同一意图、三套配置**——这里没有 DRY

6. **AGENTS.md 中文档化策略**，即使是 settings 强制的。后来人要知道**为什么**这套权限是这样

7. **Background-agent setup 写在 `.cursor/environment.json`，不要在 prompt 里**。别让 agent 自己跑 `npm install`——通过 `install:` 预装

8. **定期测权限是否还在生效**。隔段时间在各家试一下 `Bash(sudo ls)` 或 `Edit(./.git/HEAD)`，验证 deny 没漂移

### 8.6 各工具特殊注意事项

#### Claude Code

- 💡 权限模式：文件路径用 **glob**，Bash 用 **`前缀:*`**，语法不一样
- 💡 `/permissions` 打开当前权限集编辑器
- ⚠️ skill / command frontmatter 中的 `allowed-tools` 和 settings 的 `permissions` 是不同概念——frontmatter 是**预批准列表**，settings 是**闸门**，取交集
- 💡 `statusLine` 每次渲染都跑 shell 命令——保持 < 100ms 否则明显卡顿
- 💡 `additionalDirectories` 让 agent 看到项目根之外的路径（慎用）
- ⚠️ local settings 浅合并到项目——嵌套数组**替换**而非追加，`permissions.allow` 容易踩坑

#### Codex

- 💡 **单一配置文件 `~/.codex/config.toml`，CLI、VS Code 扩展、Desktop 都读**——无 per-IDE drift
- 💡 `--profile <name>` 整块替换 `[profiles.<name>]`，CI vs 本地切换很干净
- ⚠️ `sandbox_mode` 改动**只对新 session 生效**——当前 TUI session 还是启动时加载的
- 💡 `[env]` 注入到每个工具调用；配 `${env:NAME}` 插值放密钥
- ⚠️ macOS 上 `workspace-write` 默认禁网络——`npm install` 静默失败，要么开 `network_access = true` 要么预装

#### Cursor

- 💡 多数设置在 UI / synced settings；极少文件式
- 💡 `.cursor/environment.json` 是**唯一可仓库化的运行时配置**（除 `.cursor/rules/`、`.cursor/mcp.json`）
- ⚠️ "Auto Mode" 是全局单一开关——没有"白名单内自动、其余 prompt"的中间档
- 💡 Background Agents 单独计费，以 `.cursor/environment.json` 为环境真源
- 💡 Settings → Privacy 控制遥测 / 训练 opt-out——企业可通过 MDM 在组织层面配

#### Trae

- ⚠️ **没有文件式权限系统**。所有闸门都是 GUI 提示，缓存在用户 IDE 存储
- 💡 团队策略只能靠 git pre-commit hook + CI
- 💡 国际版（`~/.trae/`）vs 中国版（`~/.trae-cn/`）设置不通用——别假设跨版本

#### opencode

- 💡 **8 级配置优先级**（从低到高，后者覆盖前者）：
  1. Remote `.well-known/opencode`（组织默认）
  2. 全局 `~/.config/opencode/opencode.json`
  3. `OPENCODE_CONFIG` env（自定义 config 路径）
  4. 项目 `opencode.json`
  5. `.opencode/` 目录（agents/、commands/、skills/、plugins/、modes/）
  6. `OPENCODE_CONFIG_CONTENT` env（内联 JSON）
  7. Managed `/Library/Application Support/opencode/`（macOS，admin 控制）
  8. macOS managed preferences via MDM `.mobileconfig`——**最高，用户不可覆盖**
- 💡 **单 JSON 文件**容纳 agents / commands / MCP / plugins / permissions / models / providers / themes——审计比其它工具的多文件分散更容易
- 💡 **plural 子目录约定为当前**：`agents/`、`commands/`、`skills/`、`plugins/`、`modes/`、`tools/`、`themes/`；singular 形式（`agent/`、`command/`…）作为向后兼容仍然加载
- 💡 **无 OS 级 sandbox**（不像 Codex）；生产环境靠 `permission` + 容器隔离
- 💡 **MDM 推送 settings** 在这 5 个工具中是 opencode 独有的——企业端点策略的利器
- 💡 **善用 schema**：`opencode.json` 顶部 `"$schema": "https://opencode.ai/config.json"` 开启编辑器完整补全 + 校验
- ⚠️ `.opencode/plugins/` 下的本地 plugin 可在 `.opencode/package.json` 声明 npm 依赖——opencode 启动时跑 `bun install`；像审 hook 脚本一样审依赖

#### 纵深防御推荐

没有任何工具的权限系统是可移植的，所以唯一持久的团队策略是**多层**：

1. **Agent 运行时闸门**（Claude permissions、Codex sandbox、Cursor allowlist、Trae GUI）——第一层，工具专属
2. **git pre-commit hook**——接住 agent 漏过的
3. **CI 质量门**——最后一关，无论谁 push
4. **AGENTS.md 文档化**——捕获意图，让后来人懂分层在防什么

单层策略（如"我们在 Claude settings 加了 deny"）一旦有人换 Codex 或 Trae 打开同一仓库就失效。

---

## 九、Monorepo 完整最佳实践

本章把 §1~§8 的 Monorepo 相关结论按 AGENTS.md / Rules / Skills / MCP 四维度统一整理（Commands / Subagents / Hooks / Settings 不分子模块，沿用各章方案即可），给出可直接落地的目录布局、配置脚本与验证清单。

### 9.1 嵌套能力原生支持差异（事实基础）

| 能力 | Claude Code | Codex | Cursor | opencode | Trae |
|---|:---:|:---:|:---:|:---:|:---:|
| 嵌套 AGENTS.md（自动加载） | ⚠️ 手动 `@import` | ✅ 自动 | ✅ 自动 | ✅ 自动（cwd 向上 walk） | ⚠️ 弱 |
| 嵌套 Rules（按文件 scope） | ✅ paths | — | ✅ globs | — （走嵌套 AGENTS.md） | ✅ globs |
| 嵌套 Skills（按目录 scope） | ✅ 递归 | ✅ 沿目录链 | ✅ 子目录 scope | ❌ 只扫顶层（同 Trae） | ❌ 只扫顶层 |
| 嵌套 MCP 配置 | ❌ 单一根级 | ❌ 单一根级 | ❌ 单一根级 | ❌ 单一根级 | ❌ 单一根级 |
| 子包 override 机制 | — | ✅ `AGENTS.override.md` | — | `opencode.json` `instructions` 数组 | — |

这张表是 §9.3~§9.6 策略选择的事实基础：

- **AGENTS.md / Rules / Skills 都有嵌套支持**，但 Claude/Trae 行为偏弱，需要靠根 AGENTS.md 路由兜底
- **MCP 完全无嵌套支持**，必须用根级单文件
- **生产项目不要依赖工具的"自动近端加载"**——靠根 AGENTS.md 显式路由保证五家行为最终一致

### 9.2 总体策略

| 维度 | 策略 | 跨工具一致性 |
|---|---|---|
| **AGENTS.md** | 两层 × 两块：L1 项目根（AGENTS.md + `.agents/`）+ L2 子模块（AGENTS.md + `.agents/`） | 5 家行为最终一致 |
| **Rules** | 绕开各家 rules 系统，内容分流到 AGENTS.md 正文（强约束）+ 根 `.agents/rules/`（项目级规则）+ 子模块 `packages/<n>/.agents/rules/`（子模块独占规则）+ Skills；仅工具特有交互保留 rules | 100%（除工具特有交互） |
| **Skills** | L1 项目根 skill 放根 `.agents/skills/`（5 家原生自动发现，Claude/Trae 通过 symlink 联通），L2 子模块 skill 放 `packages/<n>/.agents/skills/` 并在该子模块 AGENTS.md Workflows 表引用 | 5 家行为最终一致 |
| **MCP** | 各家维护各家根级配置文件，密钥用环境变量插值 | 协议标准，配置文件各异 |

详细方案见 §9.3~§9.6，一体化布局见 §9.7。

### 9.3 AGENTS.md：新增子模块的标准动作

两层 × 两块的核心矩阵、模板、决策树都在 §1.3。Monorepo 场景下唯一需要额外记住的是**新增一个子模块**应做哪几件事，让 5 家工具都能立刻发现它：

1. 在 `packages/<new>/AGENTS.md` 建 slim 路由文件（scope + stack + Rules Reference + Workflows）
2. 在 `packages/<new>/.agents/rules/` 下按主题分文件写规则，并在该子模块 AGENTS.md 的 Rules Reference 表内逐文件引用
3.（可选）在 `packages/<new>/.agents/skills/` 下新增子模块 skill，并在该子模块 AGENTS.md 的 Workflows 表内引用
4. 编辑根 `AGENTS.md` 的 Module Reference Map，加一行 `path pattern → file`
5. 提交 PR——code review 同一 diff 可见

`§1.3.3` 的 `0c. Tool-specific Loading` 段是 Monorepo 项目根 AGENTS.md 的**必有内容**——否则 Claude / Trae 无法判断哪些是自动加载、哪些需要主动 Read。

### 9.4 Rules：绕开各家 rules 系统

策略与迁移路线见 §2.3。Monorepo 场景下唯一要确认的是**保留各家 rules 的少数场景**：

- Trae `#Rule`：最高优先级触发，工具特有
- Cursor `@rule-name`：手动引用，工具特有
- Cursor Team Rules 仪表盘：企业管理需求

其余规则一律分流到根 / 子模块的 `.agents/rules/` 或 Skills。

### 9.5 Skills：按层处理

按 skill 所在层分两种处理（完整方案、`description` 写法、`paths` 用法、symlink 脚本与 git hooks 集成详见 §3.5）：

| Skill 类型 | 位置 | 发现机制 | 工具特殊配置 |
|---|---|---|---|
| **L1 项目根 skill** | 根 `.agents/skills/` | SKILL.md `description` 自动发现（**5 家原生**：Codex / Cursor 2.4+ / opencode / Copilot / Gemini） | 把 `.claude/skills/` / `.trae/skills/` 桥接到 `.agents/skills/`，方案根据团队 OS 组合自选（§3.5.2） |
| **L2 子模块 skill** | `packages/<n>/.agents/skills/` | 该子模块 AGENTS.md Workflows 表引用——**5 家都不会原生扫嵌套** | Claude 加 `paths` frontmatter 防污染；Trae / opencode 经 AGENTS.md 引用 Read SKILL.md 执行（无需 symlink） |

### 9.6 MCP：各家维护各家配置

详细方案见 §7.3。MCP 是协议标准但配置文件格式各异，且**完全无嵌套支持**：

- 项目级配置都提交 Git（团队共享），密钥用环境变量插值：`"API_KEY": "${env:API_KEY}"`
- `.env` 加入 `.gitignore`，存真实密钥
- 项目专属服务器放项目级（本项目数据库等），通用工具（GitHub、Web search）放用户级
- 改完配置必须 Reload Window / 重启 session
- Trae 项目级 MCP 是实验性，生产环境优先用用户级（详见 §9.10）

### 9.7 一体化目录结构

```
your-monorepo/
├── AGENTS.md                              # ★ L1 始终加载块：强约束 + Rules Reference + Module Reference Map
├── CLAUDE.md                              # 一行：@AGENTS.md
│
├── .agents/                               # ── L1 按需加载块（项目级） ───────────────────────
│   ├── rules/                             #    项目级规则
│   │   ├── coding-style.md
│   │   ├── typescript-strict.md
│   │   ├── rest-api-design.md
│   │   └── security-baseline.md
│   └── skills/                            #    项目级工作流（5 家原生）
│       ├── deploy-prod/SKILL.md
│       ├── security-audit/SKILL.md
│       └── scaffold/SKILL.md
│
├── .claude/skills/ → ../.agents/skills/   # symlink，Claude 共享根 skills
├── .trae/skills/   → ../.agents/skills/   # symlink，Trae 共享根 skills
│
├── .mcp.json                              # Claude MCP
├── .codex/config.toml                     # Codex MCP
├── .cursor/mcp.json                       # Cursor MCP
├── opencode.json                          # opencode 配置（含 mcp 块、agents、plugins、permission）
├── .trae/mcp.json                         # Trae MCP（实验性，如启用）
│
├── .cursor/rules/                         # 仅 Cursor @rule-name 交互场景才用（可省）
├── .trae/rules/                           # 仅 Trae #Rule 高优先级触发才用（可省）
│
└── packages/                              # ── L2：子模块 ──────────────────────────────────
    ├── frontend/
    │   ├── AGENTS.md                      # ★ L2 始终加载块（slim 路由：Rules Reference + Workflows）
    │   ├── .agents/                       # ★ L2 按需加载块
    │   │   ├── rules/                     #    一文件一主题
    │   │   │   ├── react-conventions.md
    │   │   │   └── state-management.md
    │   │   └── skills/                    #    仅前端用的子模块工作流
    │   │       └── update-design-tokens/
    │   │           ├── SKILL.md           #   paths: ["packages/frontend/**"]（Claude 防污染）
    │   │           └── scripts/sync.ts
    ├── backend/
    │   ├── AGENTS.md
    │   ├── AGENTS.override.md             # Codex 专属：完全替换上层（如需）
    │   └── .agents/
    │       ├── rules/
    │       │   └── api-design.md
    │       └── skills/
    │           └── run-migration/SKILL.md
    └── infra/
        ├── AGENTS.md
        └── .agents/
            ├── rules/
            │   └── terraform-style.md
            └── skills/
                └── plan-and-apply/SKILL.md
```

### 9.8 10 分钟最小配置

```bash
# 1. 根 AGENTS.md：强约束 + 两张路由表
cat > AGENTS.md <<'EOF'
# AGENTS.md

## 0a. Rules Reference
Read on demand when working in the matching domain. NOT auto-loaded by any
tool — use your file-read tool to Read them.

| Domain / Trigger                          | Reference File                       |
|-------------------------------------------|--------------------------------------|
| Writing or editing React components       | .agents/rules/react-conventions.md   |
| Using TypeScript strict-mode features     | .agents/rules/typescript-strict.md   |
| Designing or changing REST API endpoints  | .agents/rules/rest-api-design.md     |
| Touching auth, secrets, input validation  | .agents/rules/security-baseline.md   |

## 0b. Module Reference Map
This is a monorepo. Before editing files under a submodule, also read the
corresponding submodule AGENTS.md. Submodule-local rules override
conflicting root rules on overlapping topics.

| Path Pattern              | Submodule AGENTS.md           |
|---------------------------|-------------------------------|
| packages/frontend/**      | packages/frontend/AGENTS.md   |
| packages/backend/**       | packages/backend/AGENTS.md    |
| infra/**                  | infra/AGENTS.md               |

## 0c. Tool-specific Loading
- Codex / Cursor / opencode: nested AGENTS.md auto-loads — no manual read needed.
- Claude / Trae: MUST Read the submodule AGENTS.md before editing files
  in that subtree.
- L1 root .agents/rules/*.md: auto-loaded on Claude / Cursor / Trae via the
  bridges (`.claude/rules/` and `.trae/rules/` symlinks; `.cursor/rules/*.mdc`
  shims) — see §2.3.1. Codex / opencode reach them via the Rules Reference
  table above. L2 submodule .agents/rules/*.md: NEVER auto-loaded by any
  tool — Read on demand based on each submodule's Rules Reference table.
- All tools: submodule skills under packages/*/.agents/skills/ are NEVER auto-discovered — routed via each submodule AGENTS.md's Workflows table.

## 1. Stack
- pnpm@9, TypeScript strict

## 2. Commands
- Install: pnpm install
- Verify (lint + typecheck + test): pnpm verify

## 3. Do Not Touch
- prisma/migrations/**
- *.generated.ts
- .env*
EOF

# 2. 子模块 AGENTS.md（slim 路由文件，含 Rules Reference 表 + Workflows 段）
touch packages/frontend/AGENTS.md
touch packages/backend/AGENTS.md
touch infra/AGENTS.md

# 3. 子模块独占规则（按主题一文件，owner 就近维护）
mkdir -p packages/frontend/.agents/rules
touch packages/frontend/.agents/rules/{react-conventions,state-management}.md
mkdir -p packages/backend/.agents/rules
touch packages/backend/.agents/rules/api-design.md
mkdir -p infra/.agents/rules
touch infra/.agents/rules/terraform-style.md
# ⚠️ 别忘了在各子模块 AGENTS.md 的 Rules Reference 表内引用上述文件
#    （任何工具都不会自动加载子模块的 .agents/rules/*）

# 4. 项目级规则（多个子模块都会查阅的规则）
mkdir -p .agents/rules
touch .agents/rules/{coding-style,typescript-strict,rest-api-design,security-baseline}.md

# 5. Claude Code 桥接
echo "@AGENTS.md" > CLAUDE.md

# 6. Trae 桥接：打开 Settings → Rules & Skills → 勾选 "Include AGENTS.md in the context"
#    （无需建文件）

# 7. 项目根 skills 目录 + Claude/Trae 联通
mkdir -p .agents/skills
# 让 Claude (.claude/skills/) 和 Trae (.trae/skills/) 看到 .agents/skills/。
# 方案不在本手册规定范围——根据你团队的 OS 组合 / Git 行为 / 与全局安装的共存
# 关系自选 symlink / junction / 构建时生成 / npx skills add ...
# 详见 §3.5.2 的跨设备兼容性提示。
# 之后每次 checkout/pull/merge/rebase 都会自动刷新软链接

# 8. MCP 各家维护各家，密钥走 .env + 环境变量插值
echo ".env" >> .gitignore
```

### 9.9 Agent / Skill 配置验证清单

改完 AGENTS.md / Rules / Skills / Subagents / Hooks / MCP / Settings 后，**必须在每家工具里实际跑一次验证**——不要假定"文件写对了 = 工具读到了"。下面按通用三步法 + 维度 × 工具速查 + Skill 专项 + 整体回归四层组织。

#### 9.9.1 通用三步法（任何维度都先做这三步）

1. **Reload / Restart**：Cursor / Trae `Cmd+Shift+P → Reload Window`；Claude Code / opencode 重启 session；Codex 下一轮 prompt 自动重读。任何配置文件改完不重载，看到的还是旧上下文，"验证"等于零。
2. **直接问 agent**：在 5 家用同一句话问 _"List everything you know about this project from your loaded context: AGENTS.md, rules, skills, MCP servers."_——5 家答案能对得上才算配置一致；对不上即去对应维度排查。
3. **构造最小触发用例**：往禁区文件写一行、用 skill description 的 WHEN 关键词造句、要求执行 hook 拦截的命令——观察工具实际反应（拒绝 / 提示 / 自动激活），而不是看配置文件。

#### 9.9.2 维度 × 工具速查

| 维度 | Claude Code | Codex | Cursor | opencode | Trae |
|---|---|---|---|---|---|
| **AGENTS.md / CLAUDE.md** | `/memory` 看实际加载内容；不出现就检查 `CLAUDE.md` 里有没有 `@AGENTS.md` | `codex --ask-for-approval never "Summarize the current instructions."` 比对正文（注意 32 KiB 静默截断） | Chat: "List the AGENTS.md files in your context"；嵌套缺失就 `@AGENTS.md` 手动引 | `opencode run "Summarize your current AGENTS.md context"`；同级同时存在 `AGENTS.md` 和 `CLAUDE.md` 时前者胜出（另一个被忽略） | Settings → Rules & Skills → 确认 "Include AGENTS.md in the context" 已开；Chat: "复述你看到的 AGENTS.md 内容"，未开关时为空 |
| **Rules（声明性规则）** | `/memory` 列出 `.claude/rules/*.md`；`paths` 限定的规则要在对应路径下的文件被编辑时才生效 | 无独立 rules 系统——验 AGENTS.md 即可 | Settings → Rules 面板看到匹配文件；用 `@rule-name` 手动调，列表里没有就是没识别（无 frontmatter 的 `.md` 会被忽略） | 无独立 rules 系统——验 AGENTS.md + `opencode.json` 的 `instructions` 数组 | Settings → Rules & Skills 面板看条目；用 `#Rule <name>` 触发，提示找不到即未识别 |
| **Skills** | 应出现在 session 启动时的"skills loaded"横幅；用 SKILL.md `description` 的关键词触发会话，观察是否自动激活；`disable-model-invocation: true` 时必须显式 `/skill-name` | Codex 启动横幅；或 `codex --ask-for-approval never "List skills you can use here."` | Chat: "List available skills"；Cursor 2.4+ 自动扫 `.agents/skills/`，未识别则版本不够或目录拼错 | `opencode run "list your skills"`；opencode 把 5 个 skill 路径都加进 catalogue，缺一个就检查 `permission.skill` 黑名单和 `name` 合规性 | Settings → Rules & Skills 面板看 skill 列表；不在列表里就是 catalogue 没扫到——通常是没把 skill 同步到 `.trae/skills/`（symlink 或 `npx skills add --agent trae`） |
| **Subagents / Personas** | `/agents` 列出 `.claude/agents/*.md`；派一个 Task 给该 subagent，确认拿到 isolated context（CLAUDE.md / rules **不继承**） | 无文件式 subagent，仅 SDK `Task`——无可验证 | Custom Modes 下拉能选到；切换后看顶栏标记 | `opencode.json` `agent` 块 + `.opencode/agents/*.md`；调用时确认 prompt 真的隔离（subagent 干净启动，permission 单独配） | Settings → Persona 面板能选到；切换后看 GUI 标记 |
| **Hooks** | 故意触发对应 event（如让 agent 跑被 hook 拦的 `Bash` 命令），看是否真的被拦；查看 `~/.claude/log/`；`exit 2` 时 agent 应看到 stderr 反馈 | 同 Claude Code（schema 一致，同份 shell 脚本可两边跑）；额外查 `~/.codex/log/` | 故意触发；观察 `.cursor/hooks/` 下脚本的 stdout / stderr | 故意触发；opencode 用 JS/TS plugin，错误进 opencode log | ❌ 无原生 hooks——只能验 git pre-commit + CI 是否在底线兜住 |
| **MCP servers** | `/mcp` 看 connected / failed；project-scope MCP 首次需用户批准（CI 注意） | `/mcp` 看 connected / failed；`~/.codex/log/` 看握手 | Settings → MCP 面板看连接 + tool 数量；状态栏 MCP 指示灯 | `opencode run "list mcp servers"`；`opencode.json` 解析失败时启动报错 | Settings → MCP 面板；项目级实验性，生产用用户级 |
| **Settings / Permissions / Sandbox** | `/permissions` 列当前 allow/deny；故意试一条 deny 列表上的命令应被拒 | `codex --ask-for-approval never <op>` 看是否真的非交互执行；试一条沙箱外操作应失败 | Chat 调出 Auto Mode 状态；试白名单外命令应弹批准 | 直接问 agent：`opencode run "what permission policy is currently in effect for bash, edit, webfetch, and skills?"`；改完配置必须重启 session | GUI 提示窗口——人工观察 |

#### 9.9.3 Skill 专项：自动激活是否真的生效

Skill **写出来 ≠ 用起来**。`description` 不够具体时 5 家都会"看见 skill 但不自动调用"。验证流程：

1. 用 SKILL.md `description` 里的 WHEN 触发词造一句用户 prompt（如 description 写 _"Use when ... `dotfiles`, `config sync` ..."_，就发"帮我 backup 一下 dotfiles"）
2. 观察 agent 是否在回复前**声明**"I will use the `<skill-name>` skill"之类
3. **没有自动激活**的常见原因（按频率）：
   - `description` 缺 WHEN 子句——5 家都用 `description` 做激活信号，opencode 完全只看 `description`，没有其它 fallback
   - `name` 不合规：含 `_` / `.` / 大写 / `--` / 起止 `-` / `name ≠ 父目录名`——opencode 静默丢弃，其余 4 家也可能跳过
   - `disable-model-invocation: true` 误开（永远不要"为了保险"设这个，会杀掉自动激活）
   - SKILL.md 体超过 500 行 → catalogue 注册降级、激活权重降低
   - L2 子模块 skill 没在子模块 AGENTS.md 的 Workflows 表里挂引用——5 家都不扫嵌套 `.agents/skills/`
4. **L1 项目根 skill 在 Claude / Trae 没出现**：检查 `.claude/skills/` / `.trae/skills/` 是否真的指向（或包含） `.agents/skills/` 的内容——`ls -l .claude/skills .trae/skills`、Windows 上 `dir /AL` 看 reparse point 是否断链、copy 桥接的话看时间戳是否落后；按你团队选定的桥接方案重新刷新一次
5. **5 家都没自动激活但 catalogue 里能看到**：试着在 prompt 里手动点名（"use the `<skill-name>` skill"），如果手动能跑、自动不跑，几乎 100% 是 `description` 触发面太窄——重写 `description` 加更多 WHEN 关键词

#### 9.9.4 Agent 配置整体回归（每次合并 AGENTS.md / Rules / Skills 后跑一次）

在 5 家工具里粘贴以下 5 句 prompt，对比答案：

1. _"What files have you automatically loaded into context? List each path."_
2. _"Which rules currently apply to editing `<某个真实子模块下的文件路径>`?"_
3. _"List every skill you can invoke, with one-line descriptions."_
4. _"Which MCP servers are connected? List their tools."_
5. _"Run `sudo ls /` for me."_（**真发指令**而非问假设——验证 deny / hook / sandbox 是否真的机械拦截。期望结果：被拦或被要求批准。如果工具只是嘴上说"我不该这么做"但其实跑过去了，规则没生效）

5 家答案应**一致地**反映：根 AGENTS.md + 该子模块 AGENTS.md + 适用 rules + 期望 skills + MCP 列表 + 拒绝行为。任一条不一致即去对应维度的 §1.4 / §2.4 / §3.6 / §5.5 / §6.4 / §7.4 / §8.6 排查。

#### 9.9.5 何时跑哪一层验证

| 改动范围 | 跑哪些验证 |
|---|---|
| 仅改根 `AGENTS.md` 正文 | §9.9.1 三步法 + §9.9.2 AGENTS.md 行 |
| 新增 / 修改 `.agents/rules/*.md` | §9.9.2 Rules 行 + §9.9.4 Q1+Q2 |
| 新增 / 修改 SKILL.md | §9.9.2 Skills 行 + §9.9.3 Skill 专项**全跑** |
| 加 / 改 `.claude/agents/*.md` 或 `.opencode/agents/*.md` | §9.9.2 Subagents 行 + 派一个真实 Task 验隔离 |
| 改 hooks / permission / sandbox | §9.9.2 Hooks + Settings 行 + §9.9.4 Q5 |
| 加 / 删 MCP server | §9.9.2 MCP 行（每家都试） |
| 合并 PR 前的最后一次回归 | §9.9.1 + §9.9.4 在 5 家**都跑一遍** |

### 9.10 实施要点（按维度速查）

**AGENTS.md**

1. 根 AGENTS.md 的两张路由表（Rules Reference / Module Reference Map）必须维护——这是 Claude/Trae 找到嵌套规则的唯一线索
2. `0c. Tool-specific Loading` 段必须保留，告诉 agent 哪些自动加载、哪些需主动 Read
3. 新增子模块时同步在 Module Reference Map 加一行 `path pattern → file`
4. 不把所有规则都塞进根 AGENTS.md，按两层 × 两块结构（§1.3）分流
5. Codex 单文件 ≤ 32KB（会静默截断），分流到子模块也能避免单文件超限

**Rules**

1. 默认不写各家 rules，内容分流到 AGENTS.md / `.agents/rules/`（项目根 + 子模块）/ Skills
2. **子模块独占规则**放 `packages/<n>/.agents/rules/*.md`（按主题一文件），在该子模块 AGENTS.md 的 Rules Reference 引用；**项目级规则**（多个子模块都会查阅）放根 `.agents/rules/*.md`，在根 AGENTS.md 的 Rules Reference 引用
3. Cursor 一旦要用 rules，必须 `.mdc` 而不是 `.md`（无 frontmatter 的 `.md` 会被忽略）
4. Trae `#Rule` / Cursor `@rule-name` 这种工具特有交互才保留各家 rules
5. `.agents/rules/*.md` 无论项目根还是子模块，**任何工具都不会自动加载**——靠 AGENTS.md 路由表（根 AGENTS.md Rules Reference / 子模块 AGENTS.md Rules Reference）触发 Read

**Skills**

1. L1 项目根 skill 放根 `.agents/skills/`，写清 `description`——**5 家原生**通过 description 自动发现，无需 AGENTS.md 重复声明
2. L2 子模块 skill 放 `packages/<n>/.agents/skills/`，在该子模块 AGENTS.md Workflows 段引用——**5 家都不会原生扫嵌套**
3. Claude 的 L2 子模块 skill 必须加 `paths` frontmatter 防 scope 污染（全仓递归扫不限制范围会跨模块出现）
4. 项目根 skills 必须让 `.claude/skills/` 和 `.trae/skills/` 看到 `.agents/skills/` 的内容——具体用 symlink / junction / 递归 copy / 构建时生成 / `npx skills add --agent ...` 中的哪一种由你团队 OS 组合决定（§3.5.2 列出选型维度）；核心红线是**不要无差别 rm 已存在目录**，那里可能有 `npx skills add` 装的第三方 skill
5. L2 子模块 skill 在 Trae 下不走 symlink——靠子模块 AGENTS.md Workflows 引用 + agent 主动 Read SKILL.md 执行

**MCP**

1. 密钥永远不直接写配置文件，用环境变量插值 + `.env`（gitignored）
2. 项目专属服务器放项目级（团队共享 Git），通用工具放用户级
3. Trae 项目级 MCP 实验性，生产环境优先用用户级
4. 改完配置必须 Reload Window / 重启 session
5. MCP server 越多 context 消耗越大（每个 server 注入 tool schema），不用的及时禁用

---

## 十、每家工具关键坑点速查（生产环境必看）

### ⚠️ Claude Code 八大坑

1. **不原生读 AGENTS.md**：必须 `@AGENTS.md` 或 symlink
2. **subagent 不继承 CLAUDE.md/rules**：派发任务时显式贴入；`.claude/agents/*.md` 也是 clean context 启动（详见 §五）
3. **`allowed-tools` 不是限制字段，且 SDK 会忽略**：CLI 中只用于预批准列出的工具；SDK 通过主 `allowedTools` 控制权限
4. **`claude_desktop_config.json` ≠ Claude Code 配置**：是 Desktop 应用的
5. **Project-scope MCP 第一次需用户批准**：CI 环境注意
6. **`.claude/commands/` 是 legacy**：`/init` 仍会脚手架出来，但官方推荐 `.claude/skills/<name>/SKILL.md`（详见 §四）。同名 skill 会自动遮蔽同名 command，对迁移友好——直接放 SKILL.md 在旁边即可
7. **Subagent `tools:` 省略 = 继承父全部工具**：（详见 §5.5）想做只读 reviewer 必须明确列 `tools: [Read, Grep, ...]`，否则 Edit/Bash 全开
8. **Hook 项目级 + 用户级同名事件全都跑**：（详见 §6.4）不像 commands 那样项目遮蔽用户。脚本失败不重试，必须幂等

### ⚠️ Codex 七大坑

1. **AGENTS.md 32 KiB 静默截断，无任何警告**：调高 `project_doc_max_bytes`
2. **`AGENTS.override.md` 同级取代规则**：可能被高层目录 silently override
3. **MCP server 加 tool schema 消耗 context**：不用的关掉
4. **TUI session 启动时一次性加载 AGENTS.md**：改了要重启
5. **Hooks 已原生但项目级路径与 Claude 不同**：（详见 §六）Codex **不读** repo 里的 `.codex/hooks.json`；项目策略走 plugin bundle 或 `requirements.toml` 托管。matcher 别忘了带 `Bash|apply_patch|mcp__.*`——Codex 0.130+ 文件编辑桥到 `Bash`，只匹配 `apply_patch` 会漏。脚本本身与 Claude 兼容
6. **`workspace-write` 默认禁网络**：（详见 §8.3）`npm install` 会静默失败，要么开 `network_access = true` 要么预装
7. **`sandbox_mode` 改了不立刻生效**：当前 TUI session 还是启动时加载的——必须重启

### ⚠️ Cursor 七大坑

1. **`.cursor/rules/` 下纯 `.md`（无 frontmatter）被忽略**：必须 `.mdc`
2. **rules 路径写死**：不支持 `.agents/rules/`（Skills 才支持 `.agents/skills/`）
3. **`CLAUDE.md` 在 Cursor 中始终全量加载**：无视 alwaysApply
4. **嵌套 AGENTS.md 在某些版本不稳定**：必要时 `@AGENTS.md`
5. **修改 mcp.json 必须 Reload Window**：改 `hooks.json` 同样要 Reload
6. **Custom Modes 是用户级**：（详见 §5.5）团队共享只能手动 export/import 或靠 settings sync，没有仓库化方案
7. **"Auto Mode" 是单一全局开关**：（详见 §8.2）没有"白名单内自动、其余 prompt"的中间档；Background Agents 单独计费且以 `.cursor/environment.json` 为环境真源

### ⚠️ opencode 九大坑

1. **AGENTS.md 是主文件，CLAUDE.md 仅 fallback**：同级同时存在 AGENTS.md 和 CLAUDE.md 时 **AGENTS.md 胜出**（不合并，另一个被忽略）；想用 CLAUDE.md 必须删掉 AGENTS.md
2. **Skill name 校验最严**：1-64 字符全小写、单 hyphen（不允许 `--`）、不能首尾 `-`、必须与父目录名一致——任一违规 **静默跳过**，连警告都不报
3. **Skill 名跨 6 个搜索路径必须全局唯一**：（详见 §3.6）`.opencode/skills/` + `.claude/skills/` + `.agents/skills/` × 项目/全局 = 6 路径；重名时 opencode 任选其一，另一份被静默丢弃
4. **Hooks 不是 shell 脚本，是 JS/TS plugin**：（详见 §6.4）从 Claude 迁过来的 shell hook 不能直接用，要重写为 plugin；plugin 启动时 `bun install` 跑 `.opencode/package.json`——依赖要像审 hook 脚本一样审
5. **Plural 子目录是当前；singular 是 legacy compat**：（详见 §五 / §四）`.opencode/agents/`、`.opencode/commands/`、`.opencode/skills/`、`.opencode/plugins/` ——新项目用 plural，老项目 singular 仍工作但别新写
6. **MCP 字段名是 `mcp` 不是 `mcpServers`**：（详见 §7.4）Local server `command` 必须是数组（不是字符串）；与 Claude / Cursor 格式不同，复制粘贴不能直接用
7. **`/init` 是 opencode 自带的，不要和 Claude 的 `/init` 混淆**：opencode 的 `/init` 生成 AGENTS.md（不是 CLAUDE.md）
8. **无 OS 级 sandbox**：（详见 §8.6）不像 Codex 有 Seatbelt/landlock；强隔离请把 opencode 跑在容器/VM 内——permission gating 不是真沙箱
9. **配置层级 8 层**：（详见 §8.6）含 remote `.well-known/opencode` 和 MDM `.mobileconfig`——出现"我明明改了 opencode.json 却没生效"时，按优先级从高到低排查（MDM > managed > inline env > project dir > project file > env override > user > remote）

### ⚠️ Trae 十大坑

1. **AGENTS.md 默认不读**：要在 Settings → Rules & Skills 中开启 "Include AGENTS.md in the context" 开关；开启后直接复用根 AGENTS.md，不要再写 `project_rules.md` 薄壳
2. **Skills catalogue 只读 `.trae/skills/`**：不原生加载 `.agents/skills/` / `.claude/skills/`；根层公共 skills 需要桥接到 `.trae/skills/`，具体用 symlink / junction / 递归 copy / `npx skills add --agent trae` 由你团队 OS 组合自选——§3.5.2 列出选型维度
3. **Skills 不支持嵌套 catalogue**：项目根 skill 靠 symlink 联通 `.trae/skills/` → `.agents/skills/`；子模块 skill 不进 catalogue，靠子模块 AGENTS.md Workflows 段引用，agent 主动 Read SKILL.md 执行（详见 §9.5）
4. **项目级 MCP 是实验性**：可能 agent 访问不到，生产用全局
5. **中国版 vs 国际版路径不同**：`~/.trae-cn/` vs `~/.trae/`；settings 也不通用
6. **rules 激活模式存在 IDE 面板**：团队需统一约定
7. **`project_rules.md` 推荐 < 1000 字符**：详细规范拆到 Skills（如果确实需要 Trae 专属规则才创建）
8. **配置改完要 Reload Window**：包括 rules、skills、mcp
9. **没有原生 hooks、没有文件式 subagent**：（详见 §五 / §六）persona 和权限提示都是 GUI 专属，无法仓库化；五家中**仅 Trae 缺少 agent 运行时 hook**——多个 FR 在排队（Trae-AI/TRAE#2436、bytedance/trae-agent#397、forum.trae.cn #18062）但未实现
10. **没有文件式权限系统**：（详见 §8.2）所有闸门都是 GUI 提示，缓存在用户 IDE；团队策略只能靠 git pre-commit + CI

---

## 十一、TL;DR — 一图流总结

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  L1 项目根 ─────────────────────────────────────────────────────────────────  │
│  ┌─ AGENTS.md（始终加载块）─────────────────────────────────────────────┐    │
│  │  项目级强约束 + 两张路由表（Rules Reference + Module Reference Map）  │    │
│  │  Codex/Cursor/opencode 原生；Claude 需 @import；Trae 需开关           │    │
│  └─────────────────┬───────────────────────────┬───────────────────────┘    │
│                    ↓ (0a Rules Reference)      ↓ (0b Module Reference Map)   │
│  ┌─ .agents/（按需加载块）─────────────────┐   ┌─ packages/<m>/（→ L2） ──┐  │
│  │  项目级内容                            │   │（每个子模块一个，结构同 L1） │
│  │                                        │   │                            │  │
│  │  rules/  ← Rules Reference 引用         │   │ AGENTS.md (slim 路由)      │  │
│  │   coding-style / ts-strict /            │   │  ↓ Rules Ref / Workflows    │  │
│  │   rest-api / security-base             │   │ .agents/rules/             │  │
│  │                                        │   │   子模块独占规则             │  │
│  │  skills/ ← description 自动发现         │   │ .agents/skills/            │  │
│  │   deploy-prod / security-audit         │   │   子模块工作流               │  │
│  │                                        │   │                            │  │
│  │  （5 家原生读 skills；                  │   │（rules + skills 全部靠      │  │
│  │   rules 全靠 AGENTS.md 路由）           │   │   该子模块 AGENTS.md 路由） │  │
│  └────────────────────────────────────────┘   └────────────────────────────┘  │
│                                                                              │
│  ┌─ Rules（各家 native）─┐  Trae #Rule、Cursor @rule-name 等交互场景才用      │
│  └──────────────────────┘                                                    │
│                                                                              │
│  ┌─ MCP ─────────────────┐  Claude   : .mcp.json (JSON)                      │
│  │ 各家专属配置           │  Codex    : .codex/config.toml (TOML)             │
│  │ 协议标准、文件各异     │  Cursor   : .cursor/mcp.json (JSON)               │
│  │ 项目级共享             │  opencode : opencode.json (JSON, mcp 块)          │
│  │                       │  Trae     : .trae/mcp.json (JSON, 实验性)         │
│  └───────────────────────┘                                                   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 核心结论

- **AGENTS.md** 是项目说明的事实标准（5 家全覆盖：Codex / Cursor / opencode 原生 + Claude `@import` + Trae 开关）
- **Monorepo 双保险**：子模块 AGENTS.md 就近放（Codex / Cursor / opencode 自动加载）+ 根 AGENTS.md 的 **Module Reference Map** 路由表（Claude / Trae 兜底）—— 保证 5 家行为最终一致
- **两层 × 两块（对称结构）**：
  - **L1 项目根**
    - **AGENTS.md（始终加载块）**：项目级强约束 + Rules Reference（路由根 `.agents/rules/`）+ Module Reference Map（路由各子模块 AGENTS.md）
    - **`.agents/`（按需加载块）**
      - `rules/*.md` → 项目级规则（多个子模块都会查阅），由根 AGENTS.md 的 **Rules Reference** 路由
      - `skills/*/SKILL.md` → 项目级工作流，5 家原生通过 `description` 自动发现
  - **L2 子模块**（每个子模块同样两块）
    - **AGENTS.md（始终加载块）**：`packages/<n>/AGENTS.md`（slim：scope + stack + Rules Reference + Workflows），由根 Module Reference Map 路由进入
    - **`.agents/`（按需加载块）**
      - `rules/*.md` → 子模块独占规则（一文件一主题），由该子模块 AGENTS.md Rules Reference 路由
      - `skills/*/SKILL.md` → 子模块工作流，由该子模块 AGENTS.md Workflows 表路由（5 家都不扫嵌套）
  - **L1 ↔ L2 对称**：两层都是 `AGENTS.md（始终加载块）+ .agents/（按需加载块）` 的相同形态，仅在位置与作用范围上不同
- **`.agents/skills/`** 是 Skills 的事实标准——**5 个工具原生读取**（Codex/Cursor 2.4+/opencode/Copilot/Gemini），随 opencode 加入从 4 升至 5。Claude/Trae 需联通或主动 Read。装可触发的长 SOP / 工作流
- **Rules** 没有跨工具标准，且核心机制已定型未来不会统一 → **最佳实践是绕开 rules 系统**：声明性规则按两层走 AGENTS.md 正文（强约束）+ 项目根/子模块各自的 `.agents/rules/`（按需），工作流走 Skills，仅工具特有交互（`#Rule` / `@rule-name`）才保留各家 rules
- **Commands 全面退场，迁到 Skills**：Skills 是严格超集且是唯一跨工具方案。`.claude/commands/` 官方已 legacy；`.opencode/commands/` 虽仍是一等公民但 opencode 同样原生读 `.agents/skills/`——**本手册建议所有新工作流（包括 opencode）一律走 `.agents/skills/`**，只把旧 commands 库留作迁移目标，唯一例外是必须用 opencode `agent:` 字段路由到 sub-agent 隔离上下文的工作流
- **Subagents（`.claude/agents/`）只在 context 隔离是核心特性时用**：90% 的"specialist"需求其实是 Skills；没有跨工具标准（Cursor Custom Modes 是 GUI、Codex 仅 SDK、opencode `.opencode/agents/` 是文件式但格式 opencode 专属、Trae 是 persona），团队只能各家分别实现
- **Hooks 是 agent 运行时唯一的机械强制**：AGENTS.md / Rules 都是建议性。**Claude + Codex schema 一致**（同 `hooks.json` 骨架、同 stdin/exit 协议，一份脚本两边跑）、Cursor 用 shell 脚本（`.cursor/hooks.json`）、**opencode 用 JS/TS plugin**（`.opencode/plugins/`，从 Claude 迁过来需重写）；**Trae 仍是五家中唯一无原生 hooks 的**——多个 FR 在排队，落地前 Trae 项目只能靠 git pre-commit + CI 兜底
- **Settings / Permissions / Sandbox** 是最不可移植的维度：Claude allow/deny/ask 模式 vs Codex sandbox + approval_policy vs Cursor Auto Mode + 白名单 vs **opencode per-tool + per-pattern + per-agent（最细粒度）** vs Trae GUI——同一意图必须**写多套配置**，没有 DRY
- **MCP** 协议标准但配置文件各异：Claude `.mcp.json` / Codex `.codex/config.toml` / Cursor `.cursor/mcp.json` / **opencode `opencode.json` 的 `mcp` 块（与其它配置同文件）** / Trae `.trae/mcp.json`（实验性）
- **Codex 最干净**（一份 AGENTS.md 通吃 rules，真 OS sandbox）
- **Cursor 功能最强**（4 种 rule 激活模式 + UI 集成）
- **Claude 功能最深**（fork/!command/disallowed-tools）
- **opencode 兼容性最好**（原生读 `.agents/skills/` + `.claude/skills/`，AGENTS.md fallback CLAUDE.md，权限最细粒度，配置层级最深 8 级，企业 MDM 支持）
- **Trae 学习成本最低**（GUI 友好）

---

## 附：参考资料

- Claude Code 官方文档：<https://code.claude.com/docs/en/memory>、<https://code.claude.com/docs/en/skills>、<https://code.claude.com/docs/en/mcp>
- OpenAI Codex 官方文档：<https://developers.openai.com/codex/concepts/customization>、<https://developers.openai.com/codex/guides/agents-md>、<https://developers.openai.com/codex/skills>
- Cursor 官方文档：<https://cursor.com/docs/rules>、<https://cursor.com/docs/skills>、<https://cursor.com/docs/mcp>
- Trae 官方文档：<https://docs.trae.ai/ide/rules>、<https://www.volcengine.com/docs/86677/2137601>
- opencode 官方文档：<https://opencode.ai/docs/config/>、<https://opencode.ai/docs/agents/>、<https://opencode.ai/docs/plugins/>、<https://open-code.ai/en/docs/rules>、<https://open-code.ai/en/docs/skills>、<https://open-code.ai/en/docs/mcp-servers>
- AGENTS.md 开放标准：<https://agents.md/>
- AI Harness Engineering Compatibility Matrix：<https://codylindley.github.io/ai-harness-engineering-compatibility-matrix/>
