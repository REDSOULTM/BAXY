# Carter v5 Skills

> **Anthropic Agent Skills** format. Skills are markdown recipes that the LLM
> loads on demand via `skill_load(name)` — they are NOT keyword-triggered.

## How skill selection works (NO HARDCODE)

When the user writes `"instala doom eternal"`:

1. At session boot, Carter injects into system_prompt a **menu** with each
   skill's `name` + `description` (~30 tokens each).
2. The **LLM (Gemma 4)** reads the user's message + the menu.
3. The LLM decides — **semantically, via its language understanding** —
   whether to emit `skill_load(name="install-game")`.
4. The `skill_load` tool returns the full SKILL.md body as a tool result.
5. The LLM proceeds with the recipe using normal tools (`gui_deeplink`, `gui`, etc.).

**There is no keyword matching, no regex, no trigger list.** The selection is
100% semantic via the LLM. If Carter ever uses keywords to pick skills, it's
a bug.

## Frontmatter schema (Anthropic spec + 1 Carter extension)

Carter follows the **official Anthropic Agent Skills spec**
(<https://code.claude.com/docs/en/custom-skills.md>) with ONE extension:
`priority`. Other Carter-specific metadata lives in the markdown body, not
the frontmatter.

```markdown
---
name: install-game                                 # required, lowercase + hyphens, ≤64 chars
description: One-line description used by the LLM  # required
priority: high                                     # Carter extension: critical|high|medium|low
---

# Recipe body here...

**Tools used**: gui_deeplink, gui, web.
**Honesty-critical**: yes — never click "Buy" without explicit "sí".
```

### Why kebab-case names (NOT snake_case)

The Anthropic spec says: *"Lowercase letters, numbers, and hyphens only
(max 64 characters)."* — `install-game`, not `install_game`. The Claude
Code linter enforces this.

### Why `priority` is a Carter extension (not in official spec)

The official spec is **lazy-load only** — every skill is on-demand. But
Gemma 4 benefits from having universal rules (e.g. "never spend money
without explicit 'sí'") **eager-loaded** into system_prompt at session
boot. Lazy loading is too late: by the time the LLM realizes it needs the
rule, it may have already emitted the wrong action.

So Carter adds `priority`:

| Value | Behavior |
|---|---|
| `critical` | **Eager-load**: full body injected into system_prompt at boot. Reserved for safety/honesty universals. |
| `high` / `medium` / `low` | **Lazy**: only the menu entry (name+description) is in system_prompt. LLM calls `skill_load()` when needed. |

Skills are sorted in the menu by priority (critical first, then alphabetical).

### Other Carter conventions

Put in the **markdown body**, NOT frontmatter:

- **Tools used**: a bullet list at the top of the body documenting which tools the recipe expects.
- **Honesty-critical**: explicit section if the skill has hard honesty rules.
- **When to use / Examples**: anywhere in the body.

This keeps the frontmatter minimal and spec-compliant.

## Per-tier load cap

The LLM can call `skill_load()` multiple times per turn, but is capped by
VRAM tier:

| Tier | Max `skill_load()` calls per turn |
|---|---|
| tier_6gb | 1 |
| tier_8gb | 2 |
| tier_10gb | 3 |
| tier_12gb | 4 |
| tier_16gb | 5 |

Past the cap, `skill_load` returns an honest error explaining the limit.

## Folder structure

```
skills/
├── README.md          (this file)
├── registry.py        (scanner + parser)
├── __init__.py        (public API)
└── <skill-name>/      (kebab-case, mirrors `name` field)
    └── SKILL.md       (the recipe with YAML frontmatter)
```

## Built-in skills

| Skill | Priority | Use case |
|---|---|---|
| `purchase-guard` | **critical** (eager) | Universal: never spend money without explicit "sí" |
| `install-game` | high (lazy) | Install/buy Steam game with honest pause before Buy |
| `steam-library-check` | high (lazy) | Read-only library inspection, no launch |
| `gui-visual-action` | high (lazy) | Click/type/select with conditional "if visible" semantics |
| `filesystem-workflow` | high (lazy) | Multi-step filesystem flows (create+write+open, backup+edit) |

## Adding a new skill

1. Create folder `skills/<your-skill-name>/` (kebab-case).
2. Create `SKILL.md` with the 3-field frontmatter (`name`, `description`, `priority`).
3. Use the markdown body for the recipe + tools-used + honesty rules.
4. Restart Carter — registry rescans on boot.
5. The skill appears in the menu automatically.

No code changes needed.

## References

- [Anthropic Agent Skills (announcement)](https://www.anthropic.com/news/agent-skills)
- [Claude Code Custom Skills spec](https://code.claude.com/docs/en/custom-skills.md)
- Doc 15: `La razon de carter/15_skills_para_bench_540.md`
