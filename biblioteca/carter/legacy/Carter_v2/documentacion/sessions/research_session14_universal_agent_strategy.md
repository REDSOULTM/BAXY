# Carter v2 - Session 14 Research: Universal Agent Strategy

Date: 2026-04-21
Scope: research-only strategy for making Carter behave like a real Windows Jarvis without visible user modes.

Hard constraints from owner:

- 0 regex for cognitive routing, intent recognition, safety decisions, or app-specific recovery.
- 0 hardcoded language/locale logic.
- 0 app hacks.
- No voice/camera scope.
- Goal: universal task execution by text, with Carter improvising outwardly but executing with disciplined internal structure.

## Bottom Line

Carter should not expose "modes" to the user. The user should just ask for anything.

Internally, Carter still needs execution strategies. The correct design is not "mode selector". The correct design is a single universal agent kernel:

1. Understand the request into a structured `TaskFrame`.
2. Select tools from metadata and live environment, not keyword rules.
3. Build a `PlanGraph` with dependencies, risks, success criteria, rollback notes, and verification steps.
4. Execute with a ReAct-style observe-act-verify loop.
5. Reflect on failures and successes.
6. Promote verified successful workflows into reusable skills.
7. Store durable user/project preferences with a memory policy, not by blindly saving every phrase.

This gives the feeling of improvisation while avoiding random tool use.

## External Research Takeaways

### ReAct

ReAct shows that reasoning and acting should be interleaved. Reasoning helps track and update plans, while actions gather external information. For Carter, this means long tasks should not be planned once and blindly executed. Carter should repeatedly observe state, act, and update the plan.

Source: https://arxiv.org/abs/2210.03629

### Reflexion

Reflexion shows value in feeding back task results and errors as language-level learning signals. For Carter, failed tool runs should become structured reflections that improve the next attempt, and verified successes should become candidates for memory/skills.

Source: https://arxiv.org/abs/2303.11366

### Voyager

Voyager is the closest conceptual match: it uses an automatic curriculum, a growing skill library, iterative prompting with environment feedback, execution errors, and self-verification. For Carter, the most important idea is verified skill acquisition: only workflows that completed and passed verification should become reusable.

Source: https://arxiv.org/abs/2305.16291

### LATS

Language Agent Tree Search combines reasoning, acting, planning, environment feedback, and self-reflection. Carter does not need full Monte Carlo tree search for every task, but it should use branching/search for expensive or ambiguous tasks: code debugging, UI automation, app building, and high-risk operations.

Source: https://arxiv.org/abs/2310.04406

### LLMCompiler

LLMCompiler separates planning from task fetching and execution, enabling parallel function calls when dependencies allow. Carter should eventually represent plans as a DAG rather than a simple list so independent read-only checks can run in parallel.

Source: https://arxiv.org/abs/2312.04511

### OpenAI Agents SDK

Relevant primitives: agents, tools, guardrails, sessions, human in the loop, and tracing. The important lesson is not to copy the SDK, but to copy the boundaries:

- guardrails at tool boundaries
- persistent run/session context
- tracing for every agent/tool/guardrail event
- human approval as part of the runtime, not a prompt convention

Source: https://openai.github.io/openai-agents-python/
Guardrails: https://openai.github.io/openai-agents-python/guardrails/
Tracing: https://openai.github.io/openai-agents-python/tracing/

### Anthropic Computer Use

Computer use documentation emphasizes an agent loop where the model requests actions, the app executes them in an environment, captures screenshots/results, and returns observations. It also emphasizes sandboxing/isolation. Carter runs on the real PC, not a Docker desktop, so the same loop must exist with stronger per-tool policy and verification.

Source: https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool

### Anthropic Tool Design

Tools are a contract between deterministic systems and nondeterministic agents. The recommendation is to prototype tools, run real evaluations, and improve ergonomics based on agent failures. This directly supports Carter's probe strategy.

Source: https://www.anthropic.com/engineering/writing-tools-for-agents

### MCP

MCP reinforces that tools should be model-discoverable with schema and metadata, and that deterministic ordering helps caching/prompt stability. Carter should move toward a richer internal tool metadata layer, even if it does not become an MCP host immediately.

Source: https://modelcontextprotocol.io/specification/draft/server/tools

## Current Carter Architecture Read

Current flow:

1. `AssistantEngine.turn()`
2. `BrainRouter.decide()`
3. If LLM backend exists, everything goes to `AgentEngine`
4. `AgentEngine` exposes tool schemas
5. LLM returns tool calls
6. policy/event bus runs
7. `dispatch_tool_call()` maps to `CapabilityRequest`
8. `CapabilityRegistry.execute()` invokes capability
9. `VerificationManager` annotates result
10. reply guard shapes final answer

This is a good base.

The pieces that conflict with universal behavior are:

- `intents/*` and `planner/*` contain language and regex-based deterministic parsing.
- `BrainRouter` currently has regex high-risk detection.
- `tool_normalizer.py` has hardcoded web targets and Steam client names.
- `agent.py` system prompt has app-specific fallback examples and language-specific hints.
- `plan_validator.py` uses regex for code/injection detection.
- Some recovery/error classifiers use regex.

Important nuance: deterministic parser is mostly fallback now because LLM lane owns turns when backend is available. That means S14 does not need to delete old deterministic parsing immediately. It should isolate it as an offline fallback and stop building new intelligence there.

## Core Design: One Universal Agent Kernel

### User Experience

User says:

- "haz una app con login y dashboard"
- "ordena mi carpeta de descargas"
- "investiga y dame un informe"
- "abre X y configura Y"
- "arregla este error"
- "recuerda que prefiero X"

Carter should not ask the user to choose a mode.

### Internal Runtime

Internally every request becomes:

```text
UserRequest
  -> TaskFrame
  -> ToolContext
  -> PlanGraph
  -> ExecutionRun
  -> VerificationReport
  -> MemorySkillUpdate
```

These are not user-visible modes. They are execution objects.

## TaskFrame

`TaskFrame` is the universal structured understanding of the request.

It should be generated by the LLM using structured JSON output and validated locally. No regex. No locale parser. No language-specific keyword lists.

Proposed fields:

```json
{
  "goal": "string",
  "user_language": "BCP47 or unknown",
  "needs_tools": true,
  "needs_clarification": false,
  "clarification_question": "",
  "expected_work_units": "single_step | short_workflow | long_workflow",
  "risk": "low | medium | high | critical",
  "mutation_scope": "none | app_state | files | system | external_account | session_power",
  "environment_targets": [
    {"kind": "file | app | window | web | repo | database | email | calendar | system", "description": "..."}
  ],
  "constraints": [
    "no destructive action without approval"
  ],
  "success_criteria": [
    {"criterion": "...", "verification": "tool | observation | test | user_confirm"}
  ],
  "candidate_tool_names": [],
  "memory_candidates": [
    {"kind": "preference | project_fact | safety_rule | temporary_context", "text": "...", "durability": "temporary | durable"}
  ]
}
```

The enum values are not user modes. They are operational dimensions. They should be stable, small, and language-independent.

## ToolContext And Dynamic Tool Retrieval

Carter has too many tools to expose naively forever. The next architecture should build a `ToolIndex` from `ToolDefinition` metadata:

- name
- namespace
- action
- full description
- compact description
- input schema
- output schema if known
- risk
- side effects
- preconditions
- failure hints
- verification support
- examples

Then the agent retrieves relevant tools dynamically:

1. Create TaskFrame.
2. Query ToolIndex semantically.
3. Include only likely tools plus always-available meta/memory/policy tools.
4. If the first tool set is insufficient, allow a `tool_search` or `meta_list_capabilities` style expansion.

This avoids app/language hacks and reduces confusion for Qwen3-8B.

Implementation note: for a local-first system, start with:

- SQLite table for tool metadata
- optional embeddings when available
- LLM rerank over a small candidate set
- deterministic validation that returned tool names exist

Do not use regex or keyword language maps for retrieval.

## PlanGraph

Current Carter can do sequential tool-calling. For "haz X app con X cosas", it needs persistent graph execution.

`PlanGraph` should be a DAG:

```json
{
  "goal": "...",
  "nodes": [
    {
      "id": "n1",
      "purpose": "inspect repo",
      "tool": "filesystem_list_directory",
      "arguments": {},
      "depends_on": [],
      "risk": "low",
      "expected_observation": "...",
      "success_criteria": [],
      "on_failure": "retry | replan | ask_user | abort",
      "rollback": null
    }
  ]
}
```

Why DAG:

- read-only inspection can run before mutations
- independent checks can run in parallel
- long tasks can resume after interruption
- failure can replan a subtree instead of restarting everything

This is the local equivalent of LLMCompiler's planner/fetch/executor split.

## Execution Loop

For every node:

1. Precondition guard
2. Policy guard
3. Execute tool
4. Capture result
5. Verify effect
6. Update working memory
7. Decide next node or replan

Pseudo-flow:

```text
while run.not_done:
  observe current state
  select ready node
  check policy
  call tool
  verify
  if verified: mark done
  elif recoverable: reflect and replan
  else: ask user or abort honestly
```

This is ReAct with stronger local contracts.

## Verification Strategy

Every plan node should declare how success is verified.

Examples:

- file write: read file and compare content/hash
- app open: process/window exists
- web navigation: browser/tab URL or page title
- code change: tests/build pass
- git operation: git status/log/remote state
- scheduler task: task exists
- registry write: read same key back, but only if allowed
- email/calendar: either backend confirms message/event ID, or mark as provider-reported, not externally verified

Do not let "tool returned ok" mean the same as "world state verified".

## Memory Strategy

Carter should learn from the user, but only with judgment.

Use a `MemoryPolicy` that classifies candidates:

- durable preference
- safety rule
- project fact
- workflow fact
- temporary context
- rejected/noise

Rules:

- Safety preferences such as "do not log off" are durable.
- Project roots, preferred stack, naming style, and command preferences are durable if repeated or explicit.
- One-off task details are temporary.
- Tool errors become reflections, not user facts.
- Verified successful workflows become skill candidates.

No regex. Use structured extraction by the LLM plus local validation.

## Skill Strategy

Current skills are promising. They should become the main path for Carter's "learning".

Only promote a skill if:

1. The task completed.
2. Verification passed.
3. The workflow is reusable.
4. The skill is not app/language-specific unless it describes an external integration with metadata.
5. The skill has preconditions, risk, inputs, and expected outputs.

Skill format should include:

```yaml
name: ...
description: ...
inputs:
  - name: ...
preconditions:
  - ...
risk: low|medium|high
verification:
  - ...
rollback:
  - ...
```

The body can remain natural language, but metadata should be structured.

This is the Voyager lesson adapted to Windows: acquire verified composable skills, not random memories.

## Universal App And Web Handling Without App Hacks

Current hardcoded web targets and Steam client handling should be replaced by a generic resolver.

Proposed `ResourceResolver`:

Inputs:

- natural target description
- current system app index
- Start Menu entries
- registry app entries
- PATH executables
- AppUserModel IDs when available
- browser bookmarks/history if explicitly enabled
- URL parser for explicit URLs
- web search for ambiguous public services if allowed

Output:

```json
{
  "candidates": [
    {
      "kind": "app | url | file | protocol | store_item",
      "name": "...",
      "launch": "...",
      "confidence": 0.0,
      "evidence": "where this candidate came from"
    }
  ]
}
```

Then the LLM chooses based on evidence. No hardcoded "youtube", "steam", "chrome" correction list.

If ambiguity remains, ask one short question.

## Language Universality

Do not use locale-specific deterministic interpreters for primary routing.

Use:

- multilingual LLM structured output
- schema validation
- final response in detected user language
- memory of user's preferred language

Language can be a field in TaskFrame, but no code path should depend on "if Spanish do X, if English do Y" for task execution.

The existing `intents/locales/*.py` can remain as no-LLM fallback, but S14 should declare it legacy and stop expanding it.

## Safety Without Regex

The current high-risk regex guards are understandable but not universal. Replace them gradually with layered non-regex controls:

1. Prefer semantic tools over raw terminal.
2. For terminal tools, parse command using shell-aware tokenization or AST libraries where available.
3. Use structured policy checks over tool name, risk metadata, path scope, target hive, mutation scope, network/external scope, and approval state.
4. Require explicit user approval for destructive/high-risk actions.
5. Require an operation-specific guard for session/power.
6. Reject commands that cannot be parsed safely.

For PowerShell specifically, investigate using PowerShell's own parser from PowerShell rather than regex matching strings.

## Current Code Migration Map

### Keep

- `AgentEngine` tool-calling loop
- `CapabilityRegistry`
- `CapabilityResult`
- `VerificationManager`
- `ActionLedger`
- `PersistentMemory`
- `SkillLibrary`
- `probe_all_tools.py`
- S12 readiness and sandbox assets

### Isolate As Legacy/Fallback

- `intents/parser.py`
- `intents/locales/es.py`
- `intents/locales/en.py`
- `planner/simple.py`
- `planner/compound.py`
- deterministic lanes in `AssistantEngine` when no LLM is available

Do not expand these for universal Jarvis behavior.

### Replace Or Redesign

- `BrainRouter`: replace regex signal with TaskFrame generation.
- `tool_normalizer.py`: replace hardcoded target rewrites with ResourceResolver evidence.
- `plan_validator.py`: replace regex code pattern blocking with schema and parser-based policy.
- system prompt app-specific fallback hints: replace with generic resolver/tool-search strategy.
- recovery regex classifier: replace with structured error codes from capabilities.

## Proposed Implementation Phases After Research

### S14A - Zero-Regex Foundation Gate

Purpose: prepare the repo so future agent cognition does not depend on regex/hardcoded language/app logic.

Work:

- Add tests that prevent new regex use in routing/planning/policy modules.
- Add architecture docs marking deterministic language parsers as fallback-only.
- Complete S13 hardening fixes first if not done.
- Add all missing compact descriptions.

### S14B - TaskFrame Prototype

Work:

- Add `TaskFrame` dataclass/Pydantic model.
- Add `TaskFrameBuilder` using LLM structured JSON.
- Validate with schema.
- Store TaskFrame in traces/results.
- Do not yet change execution behavior globally.

Acceptance:

- Given multilingual prompts, TaskFrame is valid and language-independent.
- No regex.
- Tests cover Spanish, English, mixed language, and non-English prompts without language branches.

### S14C - ToolIndex And Dynamic Tool Context

Work:

- Build metadata index from ToolDefinition.
- Add tool retrieval/reranking.
- Expose smaller tool sets per TaskFrame.
- Keep meta/tool expansion path when uncertain.

Acceptance:

- Qwen sees fewer tools.
- Probe routing does not regress.
- Missing compact descriptions fail tests.

### S14D - PlanGraph Runner

Work:

- Add persistent `PlanRun` records.
- Represent nodes, dependencies, status, result, verification, retry count.
- Execute ready nodes.
- Support resume.
- Start with sequential execution; parallel read-only execution can wait.

Acceptance:

- "haz X app con X cosas" can become inspect -> implement -> test -> run -> verify.
- Failure replans or asks user instead of silently stopping.

### S14E - ResourceResolver

Work:

- Build generic resolver from live system indices.
- Remove web/app hardcoded normalization.
- Add evidence-based candidate selection.

Acceptance:

- "abre X" works from installed apps, URL, file, protocol, or search evidence.
- No app-specific correction table.

### S14F - MemoryPolicy And Skill Promotion

Work:

- Add structured memory candidate extractor.
- Add durable vs temporary classification.
- Add verified workflow to skill candidate pipeline.
- Require verification before skill promotion.

Acceptance:

- Carter learns user safety/preferences.
- Carter does not memorize transient task noise.
- Carter can reuse verified workflows.

## Non-Negotiable Engineering Rules

1. No cognitive regex.
2. No locale-specific routing.
3. No app-specific hacks.
4. Every tool call has policy metadata.
5. Every mutation has verification or honest unverifiable status.
6. Every long task has resumable state.
7. Every learned skill has verification evidence.
8. Every fallback should be generic and evidence-based.
9. Every prompt rule that grows beyond a few lines should become metadata or a validator.
10. If the model is uncertain, Carter asks a short question rather than guessing.

## What Not To Build

- Do not add a visible mode selector.
- Do not keep adding if/else app fixes.
- Do not add more language-specific parsers.
- Do not expand keyword lists.
- Do not make all tasks use GUI automation. Prefer semantic APIs/tools first, then UI.
- Do not let memory become a dumping ground.
- Do not call a workflow successful unless verification supports it.

## Best Final Architecture

```text
User text
  -> TaskFrameBuilder
  -> MemoryContext + SystemContext + ToolIndex
  -> PlanGraphBuilder
  -> PolicyGuard
  -> PlanGraphRunner
      -> Tool call
      -> Result
      -> Verifier
      -> Reflection/Replan
  -> Final response
  -> MemoryPolicy
  -> SkillPromotion
```

This architecture lets Carter behave like a single universal assistant while internally using the right strategy for each task.

## Practical Next Step

The first implementation session after this research should not try to build the whole architecture. It should implement the foundation:

1. Finish S13 hardening fixes.
2. Add `TaskFrame` and `TaskFrameBuilder` behind a feature flag.
3. Add tests proving TaskFrame works across languages without regex or locale branches.
4. Add a tool metadata completeness test.
5. Keep existing behavior as fallback until TaskFrame routing is proven by probes.

That is the safest bridge from today's Carter to universal Jarvis behavior.

