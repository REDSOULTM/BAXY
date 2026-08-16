# Session 20 - Runner Resource Context

## Scope

This step connects evidence-based resource resolution to universal plan execution without changing public tool names, capability interfaces, or product behavior.

## Changes

| Area | Change | Reason |
| --- | --- | --- |
| Plan node results | Added `resolved_resources` to each node result. | Keeps resource evidence inspectable for LLM summaries, checkpoints, and resume. |
| Checkpoints | Bumped checkpoint schema to `3` and persists node-level resource evidence. | Makes resumed runs aware of what resources were grounded during execution. |
| Runner base dirs | `PlanGraphRunner` accepts `resource_base_dirs`. | Lets a task workspace/sandbox become the safe resolution base for relative files. |
| Prior artifacts | Later nodes can resolve resources from artifacts produced by earlier nodes. | Enables multi-step workflows without guessing paths from language. |

## Guardrails

- The resolver does not execute tools.
- Tool arguments are not rewritten by this layer.
- No product/app dictionaries.
- No language-specific branching.
- No filesystem crawling.

## Validation

- `python -m pytest Carter_v2/tests/test_universal_agent_kernel.py::test_plan_graph_runner_records_workspace_resource_evidence Carter_v2/tests/test_universal_agent_kernel.py::test_plan_graph_runner_resolves_later_nodes_from_prior_artifacts -q`
- `python -m pytest Carter_v2/tests/test_universal_agent_kernel.py Carter_v2/tests/test_resource_resolver.py Carter_v2/tests/test_assistant_engine.py -q`
