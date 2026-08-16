# Session 19 - Evidence-Based Resource Resolution

## Scope

This step expands Carter's universal resource resolver without adding product-specific app mappings, language branches, or app hacks.

## Changes

| Area | Change | Reason |
| --- | --- | --- |
| URLs | Keep explicit URL/domain-like resolution. | A URL is grounded by structure, not by product name. |
| Files | Resolve absolute paths, existing relative paths under configured base directories, and path-shaped targets. | Lets task runners resolve sandbox/workspace artifacts without scanning personal folders. |
| Snapshot artifacts | Resolve paths from structured snapshot fields such as `artifacts`, `recent_files`, or `recent_paths`. | Allows future runs/checkpoints to expose resources as evidence. |
| Apps | Continue resolving only from installed-app snapshot metadata. | Avoids brand dictionaries and assumptions. |
| Processes/windows | Resolve running processes and visible window titles from snapshot metadata. | Supports PC-control workflows using observed runtime state. |

## Guardrails

- No app/product dictionaries.
- No language-specific branching.
- No filesystem crawling.
- No URL guessing from plain service names.
- Skills/tools still remain the execution surface; this layer only supplies evidence for selecting resources.

## Validation

- `python -m pytest Carter_v2/tests/test_resource_resolver.py Carter_v2/tests/test_tool_normalizer.py Carter_v2/tests/test_assistant_engine.py -q`
- `python -m pytest Carter_v2/tests/test_universal_agent_kernel.py Carter_v2/tests/test_assistant_engine.py Carter_v2/tests/test_resource_resolver.py -q`
