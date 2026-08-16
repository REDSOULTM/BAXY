# Session 18 - Universal Cleanup Notes

## Scope

This cleanup keeps the existing Carter tools/capabilities as the execution surface and removes fragile routing behavior from the main path.

## Consolidated changes

| Area | Change | Reason |
| --- | --- | --- |
| Tool normalizer | Removed app/brand dictionaries and language intent rewrites from tool-call normalization. | Avoid app hacks and language-specific routing. Tool rewrites now require structured resource evidence or explicit URL evidence. |
| Brain router | Replaced regex high-risk detection with shell-token structural checks. | Keep the router from becoming a language classifier while still flagging clearly dangerous shell command shapes. |
| Capability registry | Converts unexpected capability exceptions into `CapabilityResult` errors. | Prevent one crashing capability from breaking the agent loop without context. |
| Tests | Updated normalizer and registry coverage for evidence-based behavior. | Guard against reintroducing brand/app hardcodes or uncaught capability crashes. |

## Deliberately not included

Generated probe outputs, binary probe assets, personal notes, archives, and untracked research files are left untouched. They are not part of this cleanup and should be handled in a separate artifact pass if needed.

## Validation

- `python -m pytest Carter_v2/tests/test_tool_normalizer.py Carter_v2/tests/test_registry_errors.py Carter_v2/tests/test_brain_router_fase7.py -q`
- `python -m pytest Carter_v2/tests/test_assistant_engine.py -q`
