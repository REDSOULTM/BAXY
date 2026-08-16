# Text Core Soak Test Report (RC3)

_Generated: 2026-05-02T17:07:53Z_

## Verdict: **SOAK_PASSED**

- Turns simulated: 200
- Wall: 0.9 ms (0.005 ms/turn)
- Latency p50 / p95 / max: 0.003 / 0.006 / 0.017 ms

## Invariants

- fake_success:                0
- action_failed_controlable:   0
- placeholders:                0
- memory_contamination:        0 (expected writes=12, actual=12)
- prompt growth chars:         40 (bound=128)
- latency drift (p95-p50):     0.003 ms
- tracemalloc leak:            142732 B

## Blockers

- (none)

## Notes

Deterministic scaffold soak. Live-LLM soak evidence lives in audit/results/FULL_LIVE_LLM_VALIDATION_LIVE_SAFE.json + SKIPPED_LIVE_VALIDATION_*.json. This soak guards the synchronous Python paths against drift across 200 turns.