"""Time budgets of the sidecar's requests: the turn's attempts and recovery inside the desktop transport's
cancellation, the catalog's startup window, the arguments request and a message composition.
"""

from __future__ import annotations

from typing import Any

from .router import DEFAULT_ENCODER_REQUEST_TIMEOUT_SECONDS


# The desktop transport cancels turn.decide after 22 seconds. Keep a fixed
# margin for JSONL scheduling while guaranteeing a separate, candidate-free
# recovery window after the bounded normal attempts.
TURN_DECIDE_NORMAL_BUDGET_SECONDS = 17.0
# Both side-effect-free attempts share the normal deadline. A per-attempt cap
# below that deadline stranded three seconds that cannot complete one CPU
# decode; an early contract failure still leaves its unused time to the retry.
TURN_DECIDE_ATTEMPT_BUDGET_SECONDS = TURN_DECIDE_NORMAL_BUDGET_SECONDS
TURN_DECIDE_RECOVERY_BUDGET_SECONDS = 2.5
TURN_DECIDE_TRANSPORT_SLA_SECONDS = 22.0
DEICTIC_CLARIFICATION_CPU_BUDGET_SECONDS = 15.0
# The shell owns one 120-second startup cancellation window. Keep the model
# warmup and the catalog request inside it, with explicit time left for JSONL
# delivery and authenticated catalog validation.
MIND_STARTUP_TRANSPORT_SLA_SECONDS = 120.0
CATALOG_LLM_WARMUP_SECONDS = 90.0
CATALOG_REQUEST_BUDGET_SECONDS = 105.0
ARGUMENT_REQUEST_BUDGET_SECONDS = 19.25
# GPU compositions keep their 5/10 s desktop budgets. The certified CPU
# profile needs the same visible-response contract. Isolated generations reach
# 14.51 s, accumulated history exceeds 20 s, and a verified three-step mission
# exceeds 45 s. Dense verified output can contain hundreds of literal tokens,
# so CPU realizes dense verified output through a short model-authored scaffold
# under one 120 s budget, then substitutes exact dynamic facts into its markers.
# The accelerated path retains its smaller explicit 5/10 s budget.
MESSAGE_COMPOSITION_MAX_BUDGET_SECONDS = 120.0
BACKGROUND_ENCODER_TIMEOUT_SECONDS = DEFAULT_ENCODER_REQUEST_TIMEOUT_SECONDS


def _message_composition_budget(value: Any) -> float:
    try:
        return max(
            1.0,
            min(MESSAGE_COMPOSITION_MAX_BUDGET_SECONDS, float(value)),
        )
    except (TypeError, ValueError):
        return 3.25
