# RUNTIME TOOL PROTOCOL WIRING AUDIT

> Mission Opus 4.7 — wire `model_compatibility` (declarative protocols)
> into the actual Carter runtime so non-native tool models (`phi4`,
> `gemma3:12b`, `deepseek-r1:8b`, `phi3.5`) can execute tools end-to-end,
> while `qwen3:8b` stays bit-exact identical to the pre-mission baseline.
>
> Read-only audit phase **R0**. No code edits in this document. Plan
> R1–R9 at the end.

---

## 1. Veredicto brutal

The harness was fixed in mission `MODEL_COMPATIBILITY_BIAS_AUDIT`, but
the **Carter runtime itself still defaults to OpenAI-native tool calling
exclusively** unless the operator opts in.

What's already in the tree (post fair-rebench mission):

| Piece                                    | Path                                                                      | State |
|------------------------------------------|---------------------------------------------------------------------------|-------|
| Universal parser (4 wire formats)        | [src/carter_v2/adapters/tool_call_parser.py](src/carter_v2/adapters/tool_call_parser.py) | shipped |
| Declarative compat package (6 protocols) | [src/carter_v2/model_compatibility/](src/carter_v2/model_compatibility)   | shipped |
| Registry `tool_protocol` per `ModelEntry`| [src/carter_v2/model_selection/model_registry.py](src/carter_v2/model_selection/model_registry.py) | shipped |
| Backend opt-in router                    | [`_chat_via_compat_router`](src/carter_v2/turn/backends.py#L442)          | shipped |
| Registry-aware `supports_tools`          | [`OpenAICompatAgentBackend.supports_tools`](src/carter_v2/turn/backends.py#L117) | shipped |
| Probe runner (7 protocols × `--fast`)    | [audit/runners/tool_call_compatibility.py](audit/runners/tool_call_compatibility.py) | shipped |

What is **missing** to claim end-to-end runtime wiring:

1. The opt-in fork in [chat_with_tools()](src/carter_v2/turn/backends.py#L352-L378)
   only fires when `CARTER_TOOL_PROTOCOL=auto`. **No automatic fallback
   today** when Ollama returns HTTP 400 ``"... does not support tools"``
   — the call simply raises `RuntimeError` and the conversation dies.
2. **No live runtime probe** that exercises the compat router against
   Carter's real tool catalogue (`websearch_search`, `time_now`,
   `system_open_app`, etc.) for non-native models.
3. The registry still tags `gemma3:12b` as `fenced_json` and `phi3.5` as
   `fenced_json`, but the fair re-bench shows `gemma3:12b` reaches 1.00
   on `json_direct` and `phi3.5` peaks at 0.80 on `fenced_json`. Two
   protocol fields are stale.
4. No closure JSON specifically asserting `non_native_models_runtime_tool_pass`.

That's it. The plumbing is built — these last four items finish the
mission.

---

## 2. Flujo actual

```text
user_text
   │
   ▼
AgentEngine.run()                                    src/carter_v2/turn/agent.py
   │  builds messages + tool_catalog (top-K)
   ▼
_backend_chat_with_tools(backend, messages, tools)   agent.py:2484
   │  thin wrapper; forwards to backend
   ▼
OpenAICompatAgentBackend.chat_with_tools()           backends.py:352
   ├── if env CARTER_TOOL_PROTOCOL=="auto" AND profile.preferred != openai_tools
   │      └── _chat_via_compat_router(...)           backends.py:442  [opt-in]
   │            └── compat_build → _post → parse_tool_call → AgentResponse
   │
   └── else (DEFAULT — bit-exact legacy):
         payload = {model, messages, tools=[...], tool_choice="auto", ...}
         body    = self._post(payload)
              ├── HTTP 400 from Ollama → raise RuntimeError    ← **dead end today**
              └── ok → msg.tool_calls → ToolCall[]
   ▼
AgentEngine fallback recovery:
   ├── _textual_tool_calls(text, available)  ← legacy regex-based recovery
   │     (Python-call style, JSON heuristics — not the universal parser)
   └── normalize_tool_calls(...)             adapters/tool_normalizer.py
   ▼
risk/policy/confirmation gate                        turn/policy/*.py
   │
   ▼
tool dispatch                                        adapters/tools.py
```

Key observation: the universal parser **is not yet used** by the legacy
path. It is only invoked through the new `_chat_via_compat_router`. The
runtime falls back to the older regex-based `_textual_tool_calls` when
the native channel comes back empty.

---

## 3. Diseño nuevo

```text
model_id
   │
   ▼
get_model_compatibility(model_id)                   model_compatibility/profiles.py
   │  → ModelCapabilityProfile{
   │       role, supports_tools, preferred_tool_protocol, …
   │     }
   ▼
OpenAICompatAgentBackend.chat_with_tools()
   │
   ├── A. preferred == "openai_tools"        → legacy native path
   │       (qwen, gpt-oss, mistral-small, llama3.x, hermes3, …)
   │
   ├── B. preferred ∈ {json_direct, tagged, fenced_json,
   │                    final_json_only, reasoning_then_json}
   │       AND env CARTER_TOOL_PROTOCOL == "auto"
   │       → _chat_via_compat_router(profile)
   │
   └── C. legacy native path raises HTTPError(400, "does not support tools")
           AND profile.preferred ≠ openai_tools
           AND env CARTER_TOOL_PROTOCOL != "off"
           → automatic one-shot fallback to compat router using
             profile.preferred_tool_protocol
           → trace event: backend_tool_channel_unsupported = true
```

The router itself is unchanged: it builds the prompt via
`build_payload()` (which renders the tool catalogue inline with the
protocol-specific system prompt template), POSTs without `tools=`, and
parses the content channel via the universal parser with
`allowed_tools={t["function"]["name"] for t in tools}`. **Unknown tool
names cannot pass** — they are rejected by the parser before any
dispatch happens (see
[`test_unknown_tool_in_native_is_rejected`](tests/integration/test_tool_call_parser.py)).

---

## 4. Riesgos

| # | Risk                                          | Mitigation                                                                                                  |
|---|-----------------------------------------------|-------------------------------------------------------------------------------------------------------------|
| 1 | JSON parser too permissive (e.g. quoted prose)| Universal parser already gates by `allowed_tools` (4 reject-tests in `test_tool_call_parser.py`).           |
| 2 | Tool hallucination (model invents a tool)     | Parser drops calls whose name ∉ `allowed_tools`; compat router only forwards calls that survive the gate.   |
| 3 | Missing/invalid args                          | Tool dispatcher already validates against `ToolDefinition.parameters` (existing risk/policy gate).          |
| 4 | Security bypass (compat path skipping policy) | `_chat_via_compat_router` returns a normal `AgentResponse` — same risk/policy/confirmation pipeline applies.|
| 5 | Qwen regression                               | Default `CARTER_TOOL_PROTOCOL=openai_native` keeps qwen path bit-exact. R6 test enforces.                   |
| 6 | Auto-fallback masking real backend errors     | Only triggers on HTTP 400 with body containing the literal Ollama "does not support tools" marker.          |
| 7 | Double LLM load during probe                  | Probe runner reuses `_unload(model)` from `tool_call_compatibility.py` to enforce single-load discipline.   |

---

## 5. Plan R1–R9

| Phase | Deliverable | Status |
|-------|-------------|--------|
| **R0** | This audit doc | ✅ done |
| **R1** | Protocol enum / types — already in [model_compatibility/protocols.py](src/carter_v2/model_compatibility/protocols.py) | ✅ done in prior mission |
| **R2** | Backend request adapter — already in [_chat_via_compat_router](src/carter_v2/turn/backends.py#L442) | ✅ done in prior mission |
| **R3** | Universal prompt builder — already in [model_compatibility/router.py](src/carter_v2/model_compatibility/router.py) | ✅ done in prior mission |
| **R4** | Parse + validate via universal parser with `allowed_tools` | ✅ done (router already passes `allowed_tools`) |
| **R5** | **NEW** Auto-fallback when native HTTP 400 + reconcile registry protocols against fair-rebench | ⏳ this mission |
| **R6** | Runtime tests covering 10 cases (already 5 passing in `test_backends_compat_optin.py`); add 4 more | ⏳ this mission |
| **R7** | **NEW** `audit/runners/runtime_tool_protocol_probe.py` — live test of compat path with 5 models × Carter tools | ⏳ this mission |
| **R8** | Update Model Lab artifacts: registry protocol fields, MODEL_TOURNAMENT_REPORT.md, MODEL_STACK_BY_VRAM.md | ⏳ this mission |
| **R9** | `audit/results/RUNTIME_TOOL_PROTOCOL_FINAL_GATE.json` + final gates | ⏳ this mission |

End of R0.
