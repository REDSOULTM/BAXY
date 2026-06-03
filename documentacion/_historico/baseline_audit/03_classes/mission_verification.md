# 03.04 — Mission Outcome + Verification (clases UML)

> **Container:** Mission Outcome + Verification.
> **Archivos:** `mission_goal.py`, `mission_outcome.py`, `verify_core.py`, `verifiers.py`.

## Fig 3.04 — Mission/Verification classes

```mermaid
classDiagram
    class OutcomeStatus {
        <<enumeration str>>
        COMPLETED
        PARTIAL
        FAILED
        UNVERIFIED
        NEEDS_USER
        NEEDS_PERMISSION
        BLOCKED_BY_POLICY
        TOOL_OK_VERIFIER_INCONCLUSIVE
        INTENT_NOT_FULFILLED
    }

    class ExpectedOutcome {
        kind: str
        target: str
        matched_by: str|None
        confirmed: bool|None
    }
    note for ExpectedOutcome "@dataclass(frozen=True)\nSub-goal estructural derivado del prompt"

    class MissionOutcome {
        status: OutcomeStatus
        summary: str
        confirmed_count: int
        failed_count: int
        unverified_count: int
        expected_total: int
        expected_satisfied: int
        detail: dict
    }
    note for MissionOutcome "@dataclass(frozen=True)\nResultado final del turn — alimenta footer + telemetry"

    class MissionGoal {
        goal_text: str
        expected: list[ExpectedOutcome]
        raw_lang: str
        from_user_text(user_text) MissionGoal
        update_with_tool(tool_name, args, ok)
        is_fulfilled() bool
        progress() tuple~int,int~
        missing_kinds() list[str]
        summary() str
    }
    note for MissionGoal "@dataclass · 6 métodos\nRegex multilingüe ES/EN/PT/FR/IT en _VERB_KIND_PATTERNS"

    class _ToolCallRecord {
        name: str
        args: dict
        ok: bool
        verifier: VerifierOutcome|None
    }
    note for _ToolCallRecord "@dataclass(frozen=True)\nLocal mirror — agent.py usa tipos distintos"

    class VerifierOutcome {
        tool: str
        confirmed: bool|None
        method: str
        evidence: dict
        note: str
    }
    note for VerifierOutcome "@dataclass\nUna entrada por tool ejecutada — null=inconclusive"

    OutcomeStatus <-- MissionOutcome : status
    MissionGoal o-- "many" ExpectedOutcome : expected
    _ToolCallRecord o-- VerifierOutcome : verifier
    MissionOutcome <-- compute_mission_outcome : produce

    note "compute_mission_outcome(goal, tool_records, reply)\nfunción top-level en mission_outcome.py · NO es método"
```

## Funciones top-level (no clases pero pertenecen al subsistema)

| Función | Archivo | Rol |
|---|---|---|
| `compute_mission_outcome(goal, tool_records, reply)` | `mission_outcome.py` | Pipeline: combina MissionGoal + verifiers per-tool → MissionOutcome |
| `_enabled()` | `mission_outcome.py` | `GEMMA4_MISSION_OFF` |
| `register_verifier(tool_name)` decorator | `verify_core.py` | Pueblo el `VERIFIER_REGISTRY` |
| `verify(tool_name, args, result) → VerifierOutcome` | `verify_core.py` | Dispatch al registry |
| `summarize_verifiers(outcomes) → str` | `verify_core.py` | Footer del reply |
| `collect_evidence_keys(outcomes) → list[str]` | `verify_core.py` | Para telemetry |
| `registered_tool_names() → list[str]` | `verify_core.py` | introspección |
| `_clear_registry_for_tests()` | `verify_core.py` | Test helper |
| 19 verifiers concretos `@register_verifier("X")` | `verifiers.py` | Implementaciones específicas |

## Veredictos

| Clase | LOC | Métodos | Marca | Veredicto |
|---|--:|--:|---|---|
| `OutcomeStatus` (enum) | ~10 | 9 valores | — | mantener. Si en producción solo se usan 4-5, considerar reducir (Fase 8). |
| `ExpectedOutcome` | <20 | dataclass | — | mantener. |
| `MissionOutcome` | <20 | dataclass | — | mantener. |
| `MissionGoal` | ~80 | 6 + cls | — | mantener. `_VERB_KIND_PATTERNS` multilingüe ya en findings. |
| `_ToolCallRecord` | <20 | dataclass | `[1-USER]` (solo `compute_mission_outcome`) | considerar inline. |
| `VerifierOutcome` | <20 | dataclass | — | mantener. |

## Hallazgos a `_findings_seed.md`

- **`OutcomeStatus` 9 valores** — Fase 8 verificar distribución real.
- **`_ToolCallRecord` 1-user** — inline en `compute_mission_outcome` posible.
- **2 funciones top-level (`compute_mission_outcome`, `verify`)** son las APIs públicas — buen patrón (no es indirección).
- **`VERIFIER_REGISTRY` global mutable poblado por decoradores** — ya en findings.
