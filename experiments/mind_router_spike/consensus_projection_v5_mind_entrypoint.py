"""Development-only memory-bounded consensus without the full-catalog encoder.

Set ``BAXY_EXPERIMENT_DISABLE_FULL_CONSENSUS=1`` before import.  The specialist
provides top-three candidates, the frozen lexical ranker may repair a sibling
only when the native selector agrees, v16 vetoes incompatible nominations, and
v12 owns disposition.  This replaces one FP32 encoder instead of adding one.
"""

from __future__ import annotations

import os
from typing import Any

from experiments.mind_router_spike import consensus_projection_v4_mind_entrypoint as v4


base = v4.base
if os.environ.get(base.DISABLE_FULL_ENV, "").strip() != "1":
    raise RuntimeError("v5 requires the full consensus encoder to be disabled")
if base._FULL is not None:
    raise RuntimeError("the full consensus encoder was loaded before v5")


def _closed_memory_consensus(
    runtime: base._REAL_LLM_RUNTIME,
    text: str,
    candidates: list[dict[str, Any]],
) -> tuple[str | None, str]:
    """Nominate from specialist top-three without loading a second encoder."""

    specialist = base._SPECIALIST.predict(text)
    baseline = specialist.operations[0]
    if baseline == base.NO_ACTION:
        return None, "specialist-no-action"
    top3 = tuple(
        operation
        for operation in specialist.operations[:3]
        if operation != base.NO_ACTION
    )
    if (
        base._family(baseline) == "notification"
        and "notification.cancel.latest" in top3
        and base._notification_cancel_contract(text)
    ):
        return "notification.cancel.latest", "notification-contract"

    lexical = base._LEXICAL.predict(text)
    selected = baseline
    gate = "specialist"
    if (
        lexical.operations[0] in top3
        and lexical.operations[0] != baseline
        and base._family(lexical.operations[0]) == base._family(baseline)
    ):
        by_name = {
            str(candidate.get("name", "")): candidate for candidate in candidates
        }
        shortlist = [by_name[name] for name in top3 if name in by_name]
        if lexical.operations[0] in by_name and len(shortlist) >= 2:
            native, no_match = base._select(
                runtime,
                text,
                shortlist,
                no_match_mode="sentinel",
                tool_choice="required",
            )
            if not no_match and native == (lexical.operations[0],):
                selected = lexical.operations[0]
                gate = "native+lexical"
    return selected, gate


v4._select_consensus = _closed_memory_consensus


if __name__ == "__main__":
    raise SystemExit(v4.main())
