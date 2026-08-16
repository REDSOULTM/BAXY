"""Replay each policy component's exact payload straight at llama-server.

The question this answers is narrow and specific: for the payloads P, G, L, V
and C actually send, does going through BAXY cost anything measurable over
posting the identical bytes to the same server?

Method: capture the real payloads from one traced session, then alternate BAXY
and direct arms in ABBA order against the same warm server, comparing
byte-identical request bodies. Nothing is executed and no asset changes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    public_runtime_identity,
    resolve_runtime,
)
from scripts.measure_mind_budget import write_json_atomic  # noqa: E402

DEFAULT_PAYLOADS = (
    REPO / "artifacts" / "fixes" / "policy_component_payloads_20260731.json"
)
DEFAULT_OUTPUT = (
    REPO / "artifacts" / "fixes" / "policy_direct_replay_20260731.json"
)
ROUNDS = 4


def _capture(output: Path) -> int:
    """Run the sidecar once, storing one exact payload per component."""

    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.llm import LlmRuntime, _RESPONSE_LANGUAGE_GRAMMAR

    captured: dict[str, dict[str, Any]] = {}
    original_post = LlmRuntime._post

    def capturing_post(
        self: LlmRuntime,
        payload: dict[str, Any],
        timeout: float | None = None,
        *,
        max_attempts: int = 2,
        cancellation: Any = None,
    ) -> dict[str, Any]:
        response_format = payload.get("response_format")
        name = None
        if isinstance(response_format, dict):
            envelope = response_format.get("json_schema")
            if isinstance(envelope, dict):
                name = envelope.get("name")
        if name is None and isinstance(payload.get("grammar"), str):
            name = (
                "language_grammar"
                if payload["grammar"] == _RESPONSE_LANGUAGE_GRAMMAR
                else "semantic_effect_guard"
            )
        key = str(name or "chat")
        if key not in captured:
            captured[key] = json.loads(json.dumps(payload))
            output.write_text(
                json.dumps(captured, ensure_ascii=False, indent=1),
                encoding="utf-8")
        return original_post(
            self, payload, timeout,
            max_attempts=max_attempts, cancellation=cancellation)

    LlmRuntime._post = capturing_post  # type: ignore[method-assign]
    try:
        return sidecar_module.main()
    finally:
        LlmRuntime._post = original_post  # type: ignore[method-assign]


def _canonical_body(payload: dict[str, Any]) -> bytes:
    """Serialize exactly as ``LlmRuntime._post`` does, so the bytes match.

    BAXY posts ``json.dumps(payload).encode("utf-8")`` with the stdlib
    defaults. Any other spelling (sort_keys, ensure_ascii=False) produces a
    different octet stream, and then the two arms are no longer comparable.
    """

    return json.dumps(payload).encode("utf-8")


def _post_direct(endpoint: str, body: bytes, timeout: float) -> dict[str, Any]:
    import urllib.request

    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _token_counts(response: Any) -> tuple[int | None, int | None]:
    """Prompt and completion tokens, when llama-server reports them.

    Decode time is proportional to generated tokens, so a delta is only
    attributable to transport once both arms are shown to generate the same
    amount of text.
    """

    usage = response.get("usage") if isinstance(response, dict) else None
    if not isinstance(usage, dict):
        return None, None
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    return (
        prompt if isinstance(prompt, int) else None,
        completion if isinstance(completion, int) else None,
    )


def run(payloads_path: Path, output: Path) -> dict[str, Any]:
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    payloads: dict[str, dict[str, Any]] = json.loads(
        payloads_path.read_text(encoding="utf-8"))

    from baxy_mind.llm import LlmRuntime

    llm = LlmRuntime()
    llm.start_warmup()
    if not llm.wait_warmup(180.0):
        raise RuntimeError("el modelo no quedó listo para el brazo directo")
    # El puerto lo elige el runtime al arrancar el servidor, así que el brazo
    # directo tiene que apuntar exactamente al mismo proceso, no a uno fijo.
    origin = getattr(llm, "_endpoint", None)
    if not origin:
        raise RuntimeError("el runtime no publicó su endpoint local")
    endpoint = f"{origin}/v1/chat/completions"

    samples: list[dict[str, Any]] = []
    try:
        # Calentamiento idéntico para ambos brazos.
        for component, payload in payloads.items():
            _post_direct(endpoint, _canonical_body(payload), 60.0)
            llm._post(dict(payload), 60.0)
            del component

        for round_index in range(ROUNDS):
            # ABBA: baxy, direct, direct, baxy.
            order = (
                ("baxy", "direct", "direct", "baxy")
                if round_index % 2 == 0
                else ("direct", "baxy", "baxy", "direct")
            )
            for component, payload in payloads.items():
                body = _canonical_body(payload)
                digest = hashlib.sha256(body).hexdigest()
                for arm in order:
                    started = time.perf_counter()
                    if arm == "baxy":
                        response = llm._post(dict(payload), 60.0)
                    else:
                        response = _post_direct(endpoint, body, 60.0)
                    elapsed = time.perf_counter() - started
                    prompt_tokens, completion_tokens = _token_counts(response)
                    samples.append({
                        "round": round_index,
                        "component": component,
                        "arm": arm,
                        "payload_sha256": digest,
                        "seconds": round(elapsed, 6),
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                    })
    finally:
        try:
            llm.close()
        except Exception:  # noqa: BLE001 - diagnostics only
            pass

    def summarize(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
        values = sorted(row["seconds"] for row in rows)
        if not values:
            return None
        generated = [
            row["completion_tokens"] for row in rows
            if isinstance(row.get("completion_tokens"), int)
        ]
        summary: dict[str, Any] = {
            "n": len(values),
            "min_s": round(values[0], 4),
            "p50_s": round(statistics.median(values), 4),
            "max_s": round(values[-1], 4),
            "mean_s": round(statistics.fmean(values), 4),
            "stdev_s": (
                round(statistics.stdev(values), 4) if len(values) > 1 else 0.0
            ),
        }
        if generated:
            summary["completion_tokens_p50"] = statistics.median(generated)
            summary["completion_tokens_min"] = min(generated)
            summary["completion_tokens_max"] = max(generated)
            per_token = [
                row["seconds"] / row["completion_tokens"]
                for row in rows
                if isinstance(row.get("completion_tokens"), int)
                and row["completion_tokens"] > 0
            ]
            if per_token:
                summary["s_per_generated_token_p50"] = round(
                    statistics.median(per_token), 6)
        return summary

    per_component = {}
    for component in payloads:
        rows = [s for s in samples if s["component"] == component]
        baxy = summarize([r for r in rows if r["arm"] == "baxy"])
        direct = summarize([r for r in rows if r["arm"] == "direct"])
        entry: dict[str, Any] = {"baxy": baxy, "direct": direct}
        if baxy and direct:
            entry["delta_p50_s"] = round(baxy["p50_s"] - direct["p50_s"], 4)
            entry["identical_payload_bytes"] = True
            left = baxy.get("completion_tokens_p50")
            right = direct.get("completion_tokens_p50")
            if left is not None and right is not None:
                entry["delta_completion_tokens_p50"] = left - right
                # Un delta de segundos sólo es atribuible al transporte si
                # ambos brazos generaron la misma cantidad de texto; si no,
                # lo que cambia es el trabajo, no el camino.
                entry["comparable_at_equal_work"] = left == right
                lps = baxy.get("s_per_generated_token_p50")
                rps = direct.get("s_per_generated_token_p50")
                if lps is not None and rps is not None:
                    entry["delta_s_per_generated_token_p50"] = round(
                        lps - rps, 6)
        per_component[component] = entry

    report = {
        "schema": "baxy.policy-direct-replay.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "effects_executed": 0,
        "question": (
            "for the exact payloads P, G, L, V and C send, does going through "
            "BAXY cost anything over posting the identical bytes to the same "
            "llama-server?"
        ),
        "method": (
            "payloads captured from a real traced session, then BAXY and "
            "direct arms alternated in ABBA order (baxy,direct,direct,baxy "
            "and the mirrored order) over 4 rounds against the same warm "
            "server. Both arms post the identical octet stream "
            "json.dumps(payload).encode('utf-8'), the same spelling "
            "LlmRuntime._post uses; the sha256 in each sample is of those "
            "exact bytes. Generated-token counts are recorded so a seconds "
            "delta is only read as transport cost when both arms did the "
            "same amount of decoding."
        ),
        "known_transport_difference": (
            "BAXY posts over its pooled keep-alive connection; the direct arm "
            "opens a fresh socket per request. On loopback that is the only "
            "remaining asymmetry and it favours BAXY."
        ),
        "runtime": public_runtime_identity(runtime),
        "endpoint": endpoint,
        "per_component": per_component,
        "samples": samples,
    }
    write_json_atomic(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, default=None)
    parser.add_argument("--payloads", type=Path, default=DEFAULT_PAYLOADS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.capture is not None:
        return _capture(args.capture)
    report = run(args.payloads, args.output)
    for component, entry in report["per_component"].items():
        baxy = entry.get("baxy")
        direct = entry.get("direct")
        print(f"{component:32} baxy_p50={baxy['p50_s'] if baxy else None} "
              f"direct_p50={direct['p50_s'] if direct else None} "
              f"delta={entry.get('delta_p50_s')} "
              f"tok={baxy.get('completion_tokens_p50') if baxy else None}"
              f"/{direct.get('completion_tokens_p50') if direct else None} "
              f"equal_work={entry.get('comparable_at_equal_work')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
