# AGENTS.md Project Description File

> This file is the full survey of the **AGENTS.md** dimension for [SKILL.md](../SKILL.md).

## 1.1 Capability Comparison

| Dimension | Claude Code | Codex | Cursor | opencode | Trae |
|---|---|---|---|---|---|
| Native AGENTS.md support | ❌ (Claude's native file is `CLAUDE.md`) | ✅ primary file | ✅ native | ✅ primary file | ⚠️ compat (off by default) |
| Bridging | `CLAUDE.md` uses `@AGENTS.md` | — | — | Falls back to `CLAUDE.md` if no `AGENTS.md`; also reads `~/.claude/CLAUDE.md` as global fallback | Settings toggle |
| Root-level file | `CLAUDE.md` | `AGENTS.md` | `AGENTS.md` | `AGENTS.md` (or `CLAUDE.md` as fallback) | `AGENTS.md` (once toggle is on) |
| Global / user-level file | `~/.claude/CLAUDE.md` | — | — | `~/.config/opencode/AGENTS.md` | — |
| Subdirectory nesting | ⚠️ requires explicit Read | ✅ one per layer along the path | ✅ subdir overrides parent | ✅ walks up from cwd (similar to Codex) | ⚠️ weak support |
| Override mechanism | — | ✅ `AGENTS.override.md` | — | `instructions` field in `opencode.json` can point to additional files | — |
| Size limit | main file ≤ 200 lines / 25 KB | **32 KiB silent truncation** | no public limit | no public limit | recommended < 1000 chars |
| Priority rule | lower layers complement higher | nearer to cwd = later = wins | subdir wins | local file > global file; AGENTS.md > CLAUDE.md when both exist | project > user > default |
| `/init` command | ✅ generates `CLAUDE.md` | ✅ | ✅ | ✅ generates `AGENTS.md` | ❌ (manual) |

## 1.2 Monorepo Support

| Tool | Monorepo nesting behavior |
|---|---|
| **Codex** | Walks Git root → cwd along the path, concatenating each layer's `AGENTS.md` / `AGENTS.override.md` (at most one per layer). Later wins. **Strongest Monorepo support**. |
| **Cursor** | Nested `AGENTS.md` is auto-scoped by location ("file at `subproject_A/x/AGENTS.md` is treated as a rule with implicit glob `subproject_A/x/**`"). Subdir wins. **Second-best support**. |
| **opencode** | Walks UP from the current directory (similar to Codex), reading **every** layer's `AGENTS.md` and concatenating them; at any layer where `AGENTS.md` is missing it falls back to `CLAUDE.md` at that same layer. Submodule layers are additive on top of root, not replacements. Also reads `~/.config/opencode/AGENTS.md` and `~/.claude/CLAUDE.md` as global fallbacks. **Strong Monorepo support, on par with Codex**. |
| **Claude Code** | Does **not** auto-load nested `CLAUDE.md` / `AGENTS.md`. The root AGENTS.md must explicitly declare submodule paths, and the agent must actively Read them. |
| **Trae** | When the toggle is on, reads root-level `AGENTS.md`; nested support is weak. Also relies on root AGENTS.md to direct active Reads. |

> **Conclusion**: native behaviors diverge greatly. The best practice is to **embed AGENTS.md next to each submodule + use the root AGENTS.md as a routing entry** — keep Codex / Cursor / opencode's auto-loading, while using references to direct Claude / Trae to actively Read. See §1.3.

## 1.3 Project Config Best Practices

### 1.3.1 Core Idea: Two Tiers × Two Slots

The repository has exactly **two tiers** — the project root and each submodule. Each tier has the same **two slots**:

- **AGENTS.md** — source of truth + routing entry (always loaded inside that tier's scope)
- **`.agents/`** — on-demand content split into `rules/` (declarative knowledge) and `skills/` (operational workflows)

The whole chapter collapses to this matrix:

| | AGENTS.md (always-loaded slot) | `.agents/rules/` (on-demand rules) | `.agents/skills/` (on-demand workflows) |
|---|---|---|---|
| **L1 — Project root** | Root `AGENTS.md`: hard constraints + routing to L1 `.agents/` and to each L2 submodule | Root `.agents/rules/*.md`: project-level rules that multiple submodules may consult | Root `.agents/skills/<name>/SKILL.md`: project-level workflows (5 native readers auto-discover via `description`; Claude / Trae via symlink) |
| **L2 — Submodule** | `packages/<m>/AGENTS.md`: scope + stack + routing to its own `.agents/rules/` and `.agents/skills/` | `packages/<m>/.agents/rules/*.md`: rules that only this submodule needs | `packages/<m>/.agents/skills/<n>/SKILL.md`: workflows that only this submodule needs (must be routed for portable behavior, especially on Claude / Trae / opencode) |

To decide where a piece of content goes, you only ever ask two questions:

1. **Is it project-level or submodule-level?** → picks the tier (L1 vs L2).
2. **Is it a rule or a workflow?** → picks the slot inside `.agents/` (`rules/` vs `skills/`).

Hard project-wide constraints that every session must obey are not "rules in a file" — they live in the **body of the root AGENTS.md** itself (the always-loaded slot at L1).

**Discovery summary** (who reaches what, how):

| Resource | Native auto-load | Route-driven active Read |
|---|---|---|
| L1 root `AGENTS.md` | Codex / Cursor / opencode (and Trae once toggle is on) | Claude via `@AGENTS.md` from `CLAUDE.md` |
| L1 root `.agents/rules/*` | Claude / Trae auto-load when the canonical files are bridged into `.claude/rules/` and `.trae/rules/` (directory symlinks); Cursor when each rule has a corresponding `.mdc` shim in `.cursor/rules/`. See [`rules.md`](rules.md) §2.3.1 | Codex / opencode — via the root AGENTS.md's **Rules Reference** table (no native rules system to bridge into) |
| L1 root `.agents/skills/*` | **5 native readers** via SKILL.md `description` (Codex / Cursor 2.4+ / opencode / Copilot / Gemini) | Claude / Trae — via a bridge to `.claude/skills/` and `.trae/skills/` (see `skills.md` §3.5.2 for cross-device considerations) |
| L2 submodule `AGENTS.md` | Codex / Cursor / opencode (nearest-layer auto-load) | Claude / Trae — via the root AGENTS.md's **Module Reference Map** |
| L2 submodule `.agents/rules/*` | **None** | All tools — via the L2 AGENTS.md's **Rules Reference** table |
| L2 submodule `.agents/skills/*` | Codex / Cursor can discover nested skill roots from the matching subtree; Claude / Trae / opencode do not | All tools — via the L2 AGENTS.md's **Workflows** table |

§1.3.7 lists why this design works in detail; §1.3.8 lists the practical rules to follow.

### 1.3.2 Recommended Directory Layout

```
your-repo/
├── AGENTS.md                          # ★ L1 always-loaded: hard constraints + routing
├── CLAUDE.md                          # one line: @AGENTS.md
│
├── .agents/                           # ── L1 on-demand slot (project-level) ──────────────
│   ├── rules/                         # project-level rules (routed from root AGENTS.md)
│   │   ├── coding-style.md
│   │   ├── typescript-strict.md
│   │   ├── rest-api-design.md
│   │   └── security-baseline.md
│   └── skills/                        # project-level workflows (5 native readers auto-discover)
│       ├── deploy-prod/SKILL.md
│       └── security-audit/SKILL.md
│
├── packages/                          # ── L2: submodules ─────────────────────────────────
│   ├── frontend/
│   │   ├── AGENTS.md                  # L2 always-loaded slot for this submodule
│   │   └── .agents/                   # L2 on-demand slot for this submodule
│   │       ├── rules/                 #   one file per topic
│   │       │   ├── react-conventions.md
│   │       │   └── state-management.md
│   │       └── skills/                #   submodule-scoped workflows (must be routed)
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
└── infra/                             # L2 (another submodule, outside packages/)
    ├── AGENTS.md
    └── .agents/
        ├── rules/
        │   └── terraform-style.md
        └── skills/
            └── plan-and-apply/SKILL.md
```

**Symmetry**: each submodule (L2) mirrors the project root (L1) — same two slots (`AGENTS.md` always-loaded + `.agents/rules/` + `.agents/skills/` on-demand), same routing pattern. The only difference is location and scope.

> Trae needs no extra file — just toggle Settings → Rules & Skills → "Include AGENTS.md in the context" to read the root AGENTS.md directly.

### 1.3.3 Root AGENTS.md Template

**Section skeleton**:

```markdown
## 0a. Rules Reference        — routes to root .agents/rules/*.md
## 0b. Module Reference Map   — routes to each submodule AGENTS.md
## 0c. Tool-specific Loading  — tells Claude/Trae they must actively Read
## 1. Project Overview        — business positioning, tech stack, key directories
## 2. Setup & Run             — package manager, install/build/run commands
## 3. Test & Lint             — required verification commands
## 4. Code Style              — language/framework/naming/import order
## 5. Architecture Rules      — module boundaries, cross-package call constraints
## 6. Do Not Touch            — list of forbidden files
## 7. Commit & PR             — commit conventions, PR size constraints
```

**Full paste-ready example**:

```markdown
# AGENTS.md

## 0a. Rules Reference

The following project-level rules live under `.agents/rules/`. On Claude /
Cursor / Trae they auto-load through the bridges in `.claude/rules/`,
`.cursor/rules/*.mdc`, and `.trae/rules/` (see [`rules.md`](rules.md)
§2.3.1). Codex and opencode reach them through this table — **Read on
demand** when working in the matching domain.

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
- **L1 root `.agents/rules/*.md`**: auto-loaded on Claude / Cursor / Trae
  through the bridges configured per [`rules.md`](rules.md) §2.3.1
  (`.claude/rules/` and `.trae/rules/` symlinks; `.cursor/rules/*.mdc`
  shims). Codex / opencode have no native rules system — they reach the
  same files by following the Rules Reference table above. **L2 submodule
  `.agents/rules/*.md`**: never auto-loaded by any tool; Read on demand
  based on the submodule's Rules Reference table.
- **All tools except Codex/Cursor 2.4+/opencode/Copilot/Gemini**: root
  `.agents/skills/` is not auto-discovered — Claude reads them via
  `.claude/skills/` symlinks, Trae via `.trae/skills/` mirror.
- **Portable rule**: submodule skills under `packages/*/.agents/skills/`
  MUST still be routed via each submodule AGENTS.md's Workflows table.
  Codex / Cursor can discover nested skill roots from the matching subtree,
  but Claude / Trae / opencode cannot, so the Workflows route is the only
  behavior that works consistently across all tools.

## 1. Project Overview
...
```

### 1.3.4 Submodule AGENTS.md Example (routing only)

The submodule AGENTS.md is slim: scope, stack, Rules Reference table, Workflows table. It does NOT contain rule content — that lives in sibling `.agents/rules/*.md` — nor skill content — that lives under sibling `.agents/skills/<name>/SKILL.md`.

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

The following skills are scoped to this submodule and are not portably
auto-loaded across all tools. When the trigger matches, Read the SKILL.md
first, then follow its steps. See §1.3.4c for why this routing is required.

| Trigger                                | Skill                                                            |
|----------------------------------------|------------------------------------------------------------------|
| Update design tokens from Figma export | `packages/frontend/.agents/skills/update-design-tokens/SKILL.md` |
| Generate a new React component         | `packages/frontend/.agents/skills/new-component/SKILL.md`        |

## Do Not Touch
- packages/frontend/src/legacy/**
```

### 1.3.4b Submodule Rule File Example

```markdown
# React Conventions (Frontend Module)

Scope: `packages/frontend/**/*.{ts,tsx}`

## Component Style
- Function components + hooks only
- Props must be explicitly typed; `any` is forbidden

## State
- State management uses zustand; do not introduce redux
- Cross-component state through context or zustand only

## API
- All API calls go through `packages/api-client`
```

### 1.3.4c Submodule Skills Routed via Workflows Section

The submodule AGENTS.md's `Workflows` section in §1.3.4 routes to a sibling `.agents/skills/` directory. Here is why and how.

**The portability problem**: nested skill discovery is inconsistent across tools.

| Tool | Scans for skills at … | Nested submodule `.agents/skills/` support |
|---|---|---|
| Codex | `.agents/skills/` from cwd up to repo root | ✅ |
| Cursor 2.4+ | `.cursor/skills/` / `.agents/skills/` roots, including nested subproject skill roots | ✅ |
| opencode | `.opencode/skills/` + `.claude/skills/` + `.agents/skills/` (root & global) | ❌ |
| Claude Code | `.claude/skills/` (root) | ❌ |
| Trae | `.trae/skills/` (root) | ❌ |

A skill placed at `packages/frontend/.agents/skills/render/SKILL.md` is therefore **not portable by default**: Codex / Cursor may discover it from that subtree, but Claude / Trae / opencode still need the AGENTS.md routing chain.

**The solution**: route through the submodule AGENTS.md, the same way submodule rules are routed through its Rules Reference. Skills go through the `Workflows` table.

**Per-tool discovery path**:

| Tool | How a submodule skill becomes reachable |
|---|---|
| **Codex / Cursor** | Auto-loads `packages/frontend/AGENTS.md` (nested AGENTS.md is native) → sees the `Workflows` table; nested skill roots may also be discovered directly from the same subtree |
| **opencode** | Auto-loads `packages/frontend/AGENTS.md` (nested AGENTS.md is native) → reads the `Workflows` table → on a matching trigger, Reads the SKILL.md |
| **Claude Code / Trae** | Root AGENTS.md Module Reference Map points to `packages/frontend/AGENTS.md` → agent Reads that file → reads the `Workflows` table → Reads the SKILL.md on matching trigger |

All five tools **can** converge on the same behavior when discovery goes through the AGENTS.md chain. The skill content lives next to the submodule code, while the route keeps behavior consistent even where nested skill scanning is missing.

> ⚠️ **Model-capability caveat**: unlike Codex / Cursor / opencode's nested AGENTS.md auto-load (which is mechanical), the Claude / Trae routing path is **model-driven** — it relies on the agent reading the root AGENTS.md, recognizing the routing table as a directive, and *proactively* Reading the linked file. Weaker models (or aggressive context-trimming sessions) sometimes skip the chain and end up not seeing the submodule's rules / skills. Mitigations: keep the routing tables prominent (top of root AGENTS.md, not buried); explicitly write something like *"You MUST Read the matching submodule AGENTS.md before editing files in that subtree"* in §0c (Tool-specific Loading); and verify with §9.9.2 (AGENTS.md row) after any change.

> **Why `Workflows` and not `Rules Reference`?** Skills are operational steps (SOPs / playbooks); rules are declarative knowledge. Keeping them in different sections preserves the mental model — anything in `Workflows` is "do these steps when X happens", anything in `Rules Reference` is "consult this knowledge when working in Y area".

### 1.3.5 `.agents/rules/` vs `.agents/skills/` — Division of Labor

This applies identically in both tiers (root and submodule). The two directories differ in **shape** (declarative knowledge vs. operational steps) and in **discovery**:

| Dimension | `.agents/rules/*.md` | `.agents/skills/<name>/SKILL.md` |
|---|---|---|
| **Nature** | Spec library (declarative knowledge) | Workflow (operational steps the agent should run) |
| **Trigger** | L1: native auto-load through bridges on Claude / Cursor / Trae (see [`rules.md`](rules.md) §2.3.1); Codex / opencode go through the AGENTS.md `Rules Reference` table. L2: AGENTS.md route → agent actively Reads (no bridge by design) | Auto-load via `description` (root only, 5 native readers) or Workflows route (submodule) |
| **Cross-tool native discovery** | L1: ✅ all 5 tools — bridges cover Claude / Cursor / Trae, AGENTS.md routing covers Codex / opencode. L2: ❌ no native support — always route-driven | ✅ at root: **5 native readers** (Codex / Cursor 2.4+ / opencode / Copilot / Gemini). At submodule level, native discovery is inconsistent, so portable setups stay route-driven |
| **Typical content** | "React conventions", "REST API design" | "Release to prod", "Security audit", "Regenerate Prisma client" |
| **Load granularity** | File-level (Read on demand) | Whole skill folder (per frontmatter metadata) |
| **When to choose** | Knowledge the agent should consult | Steps the agent should execute |

### 1.3.6 Decision Guide: Where Does a Piece of Content Live?

Two questions, in order:

```
You want to write a rule / piece of knowledge / workflow
        ↓
Q1: Is it a project-wide hard constraint that every session must obey?
    (naming, commit format, do-not-touch, architecture boundary)
    ├── Yes → write into root AGENTS.md body — done.
    └── No ↓
        Q2a: Does it apply across the whole project (multiple submodules
             may consult it), or is it specific to one submodule?
            ├── Whole project → tier = L1 (project root)
            └── One submodule → tier = L2 (that submodule)
        Q2b: Is it declarative knowledge (a rule), or an operational
             workflow (a skill)?
            ├── Declarative → goes into <tier>/.agents/rules/<topic>.md
            │     + add a row to that tier's AGENTS.md Rules Reference
            └── Operational → goes into <tier>/.agents/skills/<name>/SKILL.md
                  + if tier = L2: add a row to that submodule AGENTS.md
                    Workflows table (see §1.3.4c)
                  + if the submodule AGENTS.md does not yet exist, also
                    add a row to root AGENTS.md Module Reference Map
```

Cross-repo sharing is an org distribution concern, not a tier concern: if you want to share a `.agents/rules/` or `.agents/skills/` directory across repos, version it as a git submodule.

### 1.3.7 Strengths of This Approach

| Strength | Explanation |
|---|---|
| **Two questions, no more** | Pick a tier (project / submodule) and a shape (rule / workflow). That is the entire decision surface |
| **Symmetric L1 ↔ L2 layout** | Both tiers carry the same two slots (`AGENTS.md` + `.agents/rules/` + `.agents/skills/`); the layout you learn at L1 you already know at L2 |
| **Always-loaded vs on-demand is a slot property** | In each tier, AGENTS.md is the always-loaded slot, `.agents/` is the on-demand slot — uniform across tiers |
| **Fully leverages native capability** | L1 AGENTS.md + L2 AGENTS.md auto-load on Codex / Cursor / opencode; L1 skills auto-discover on 5 native readers — common case costs little glue |
| **CR-friendly** | L2 changes (AGENTS.md + rules + skills) all live next to the submodule code and show up in the same PR diff |
| **Eventual behavior consistency** | Routing tables in root AGENTS.md let Claude / Trae / opencode catch up to what Codex / Cursor can reach natively in deeper trees — all five tools converge on the same content |
| **Not bound by Codex 32 KiB limit** | Each AGENTS.md has its own quota; rule and skill content is split out into separate files, so no AGENTS.md ever hits the limit |
| **One file, one topic** | Rule files are focused — easy to grep, easy to evolve |
| **New-tool friendly** | Routing tables + standard locations — any agent that can Read files keeps up |

### 1.3.8 Implementation Notes

**Both tiers (general)**:
1. **AGENTS.md is the always-loaded slot, `.agents/` is the on-demand slot** — never inline rule or skill bodies into AGENTS.md beyond the §0a/§0b routing tables (and the §1–§7 hard-constraint sections at L1)
2. **Section 0c (Tool-specific Loading)** in root AGENTS.md is mandatory — tells the agent what auto-loads vs. what needs an active Read, avoiding silent omissions
3. **Avoid duplication between rules and skills**: keep one copy per piece of content; choose using §1.3.5

**L1 (project root)**:
4. **Maintain both routing tables in root AGENTS.md** — the Rules Reference (root `.agents/rules/`) is the only discovery path for Codex / opencode (no native rules system) and the canonical human-facing index; the Module Reference Map (each submodule AGENTS.md) is the only clue Claude / Trae have to find submodule-level content beyond the always-loaded slot. Both stay required even when L1 rules are bridged into Claude / Cursor / Trae
5. **L1 rule file naming**: choose a name that matches what the rule covers (`react-conventions.md`, `typescript-strict.md`, `rest-api-design.md`); put a `Scope:` section at the top of each file
6. **L1 skill `description` is the only signal** native readers use to auto-discover the skill — include both WHAT and WHEN
7. **L1 skills must not assume a submodule context** — if ambiguous, move to the submodule or parameterize via prompt
8. **Claude / Trae bridges for L1 skills**: bridge `.claude/skills/` and `.trae/skills/` to `.agents/skills/` using a strategy that fits your team's OS mix (see `skills.md` §3.5.2 for trade-offs; the handbook does not prescribe a single recipe)

**L2 (submodule)**:
9. **When adding a submodule**: first create `<module>/AGENTS.md` (slim — scope + stack + Rules Reference + Workflows), then add a row to the Module Reference Map in root AGENTS.md
10. **Keep submodule AGENTS.md slim**: a routing entry, not a rule container — push rule content into `<module>/.agents/rules/*.md` and skill content into `<module>/.agents/skills/`
11. **Put `Scope: <glob>` at the top** of the submodule AGENTS.md and at the top of each rule file, matching or narrowing the submodule scope
12. **One file per topic** under `<module>/.agents/rules/` — easier to grep, easier to evolve
13. **Every submodule rule file MUST be referenced** from the submodule AGENTS.md Rules Reference, otherwise no tool will Read it
14. **Every submodule skill MUST appear in the Workflows table** (see §1.3.4c) — even where Codex / Cursor can discover nested skill roots, the Workflows route is what makes the skill consistently reachable across Claude / Trae / opencode too
15. **Add the Workflows / Rules Reference row in the same commit** as the rule / skill itself — otherwise it ships invisible
16. **Deeper nesting is supported**: e.g. `packages/frontend/components/AGENTS.md`; Codex / Cursor / opencode nearest-layer-load again; to make Claude / Trae read it too, add a second-level route in the parent AGENTS.md

## 1.4 Per-tool Notes

### Claude Code

- ❌ **Does not natively read AGENTS.md** — must bridge via `@AGENTS.md` or symlink `CLAUDE.md -> AGENTS.md`
- ⚠️ **Subagents do not inherit**: agents spawned by `Task` do not load CLAUDE.md/AGENTS.md — paste relevant content into the prompt explicitly
- 💡 The `/init` command auto-merges `AGENTS.md` + `.cursorrules` + `.windsurfrules` into the generated `CLAUDE.md`

### Codex

- ⚠️ **32 KiB silent truncation** (no warning). Raise it via `project_doc_max_bytes = 65536` in `~/.codex/config.toml`
- 💡 `AGENTS.override.md` at the same level replaces `AGENTS.md` — useful for "full replacement"
- 💡 `project_doc_fallback_filenames` can include legacy filenames like `TEAM_GUIDE.md`
- Verify: `codex --ask-for-approval never "Summarize the current instructions."`

### Cursor

- 💡 Nested `AGENTS.md` is auto-scoped — **root AGENTS.md should only contain cross-subsystem common content**
- ⚠️ Nested loading has bugs in some versions; manually reference via `@AGENTS.md` when needed
- 💡 Coexists with `.cursor/rules/*.mdc`; AGENTS.md is lower priority than `.mdc`

### opencode

- ✅ **Native primary file**: `AGENTS.md` is the recommended rules file (opencode was an early backer of the AGENTS.md standard)
- 💡 **Falls back to `CLAUDE.md`** when no `AGENTS.md` exists at the same level — useful for projects already on Claude
- 💡 **Global rules**: `~/.config/opencode/AGENTS.md` is auto-loaded across all opencode sessions
- 💡 **Global Claude fallback**: also reads `~/.claude/CLAUDE.md` if no global opencode AGENTS.md (can be disabled)
- 💡 `/init` scans the repo and creates/updates `AGENTS.md`, asking targeted questions when needed
- 💡 **External rule files**: the `instructions` field in `opencode.json` can point to additional files, so teams can reuse a shared rules file without duplicating it into AGENTS.md
- ⚠️ Lookup order matters: when both `AGENTS.md` and `CLAUDE.md` exist at the same level, **AGENTS.md wins** (the other is ignored, not merged)

### Trae

- ⚠️ **Does not read AGENTS.md by default** — toggle Settings → Rules & Skills → "Include AGENTS.md in the context"
- 💡 **Recommended approach**: once toggled on, reuse root `AGENTS.md` directly; do not write a thin shell `.trae/rules/project_rules.md` — avoid rule fragmentation
- 💡 Only create files under `.trae/rules/` when you need Trae-specific rules (e.g. `#Rule` trigger, specific activation mode)
- ⚠️ After editing `AGENTS.md`, you must Reload Window for it to take effect
- 💡 China edition (trae.cn) and International edition (trae.ai) have different paths: `~/.trae-cn/` vs `~/.trae/`
