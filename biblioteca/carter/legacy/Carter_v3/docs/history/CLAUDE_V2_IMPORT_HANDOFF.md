# Claude handoff: Carter v2 -> v3 import work

Date: 2026-05-03

This file is the short handoff. The full audit is in:

- `Carter_v3/V2_TO_V3_IMPORT_AUDIT.md`

Read that report first. This handoff only distills the operational conclusions so you can execute without re-deriving the whole analysis.

## Non-negotiable alignment

Use `ContextoCarter.md` as the binding source of truth.

The import goal is not:

- recover the biggest number of v2 tool names
- make the catalog large again
- port branded capabilities
- expose provider-specific internals

The import goal is:

- recover the strongest universal primitives from v2
- improve v3 execution + verification quality
- keep v3 small, fast, local, and honest
- avoid overengineering and app-specific hacks

## Core conclusion

Do **not** import Carter v2 as a public tool catalog.

Why:

- v2 has `244` public tools across `31` capability families
- `95` tools are `_NO_VERIFY`
- `148` have a verifier
- but `75` of those `148` use `_verify_synchronous_ok`
- that means a large portion of the catalog is not verified strongly enough for the v3 standard

The correct extraction strategy is:

`v2 backend/primitives -> v3 internal executor/provider -> smaller universal public tool surface`

## Best export candidates from v2

These are the highest-value sources to mine next:

1. `legacy/Carter_v2/src/carter_v2/capabilities/media.py`
2. `legacy/Carter_v2/src/carter_v2/capabilities/process.py`
3. `legacy/Carter_v2/src/carter_v2/capabilities/app_resolver.py`
4. `legacy/Carter_v2/src/carter_v2/capabilities/probe.py`
5. `legacy/Carter_v2/src/carter_v2/capabilities/window.py`
6. `legacy/Carter_v2/src/carter_v2/capabilities/ui.py`
7. `legacy/Carter_v2/src/carter_v2/capabilities/filesystem.py`
8. selective parts of `legacy/Carter_v2/src/carter_v2/capabilities/terminal.py`
9. later, selective parts of `legacy/Carter_v2/src/carter_v2/capabilities/web.py`

## Do not import these raw into v3 core

- `steam_*`
- `office_*`
- `gui_do`
- `web_profile_*`
- `web_extension_relay_*`
- `web_connect_cdp`
- `web_tabs`
- `web_use_tab`
- `meta_*` as a coping mechanism for catalog overload

Reason:

- too provider-specific
- too brand-specific
- too weakly verified
- too much public surface
- not aligned with `ContextoCarter.md`

## The v3 target shape

The v3 core should keep moving toward:

- fewer public tools
- stronger universal executors
- stronger readback
- deterministic cheap layers before GUI/vision
- provider-specific code hidden behind adapters/providers

Examples:

- not `office_powerpoint_add_slide`
- yes `presentation_create` with Office COM as one possible backend later

- not `steam_install`
- yes generic package/install mission building blocks later

- not `gui_do`
- yes lower-level `window` + `ui` + screenshot/OCR layers orchestrated by the mission loop

## Best immediate implementation order

Phase 1 should focus on universal ROI:

1. real audio/system controls from `media.py`
2. stronger app open/close from `process.py`
3. stronger app/process/window discovery from `app_resolver.py` + `probe.py`
4. richer window primitives from `window.py`
5. deterministic UIA tier from `ui.py`
6. stronger filesystem helpers from `filesystem.py`
7. safer terminal execution from `terminal.py`

Then:

8. redesign browser using selective extraction from `web.py`

## Current v3 context you must preserve

- `Carter_v3` already has a landed baseline and audit closure
- public `mission_status` contract is fixed
- `VerifiedOutcome.status` contract is fixed
- `compute_mission_status()` must remain structural
- post-tool replies must continue to come from evidence, not LLM draft text
- no fake success
- no app-specific hacks
- no `if model_name == ...`
- no catalog explosion
- no overengineering

## Success criterion for this import work

A v2 export is only good if it does at least one of these:

- increases real execution coverage for non-dangerous cases
- strengthens verification/readback
- reduces reliance on GUI/vision for tasks that can be solved cheaper
- removes a current v3 stub or weak implementation
- improves universality without adding brand hacks

If it only adds surface area, complexity, or optional domain sprawl, reject it.

## Operational instruction

Before writing code:

1. re-read `ContextoCarter.md`
2. re-read `Carter_v3/V2_TO_V3_IMPORT_AUDIT.md`
3. verify current v3 invariants and tests
4. import only the minimum slice that materially improves v3

Do not optimize for "ported more". Optimize for:

- universal value
- real verification
- low overhead
- maintainable v3 shape
