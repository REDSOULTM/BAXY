# Carter v2 -> v3 import audit

Date: 2026-05-03
Scope: audit of `legacy/Carter_v2/` to extract only what helps Carter v3 become the universal local PC companion defined in `ContextoCarter.md`.

This report is intentionally opinionated. The question is not "what code exists in v2?" The question is "what from v2 helps v3 become a fast, honest, universal, verifiable Jarvis for Windows without hardcodes or app hacks?"

## Executive verdict

Do not import the Carter v2 catalog into v3 as-is.

Why:

1. v2 exposed `244` public tools across `31` capability families, but the surface is much larger than its verification quality.
2. `95` tools in v2 are `_NO_VERIFY`.
3. `148` tools have a verifier, but `75` of those `148` resolve to `_verify_synchronous_ok`, which means "the tool said ok" rather than "the world changed and we observed it".
4. The large catalog forced routing workarounds. v2 had to introduce per-turn top-K selection because the full `~242-tool` catalog was too large to send to the LLM every turn.
5. A meaningful part of the catalog is app-specific, environment-specific, or domain-specific in ways that contradict the v3 north star from `ContextoCarter.md`.

The correct strategy for v3 is:

- import universal primitives and OS backends from v2;
- do not import app-specific public tool names into the v3 core;
- redesign weakly-verified surfaces before exposing them again;
- keep the v3 public catalog small, universal, and evidence-driven;
- hide environment-specific and provider-specific logic behind adapters/providers, not brand-named tools.

## The criteria: what ContextoCarter requires

This audit uses `ContextoCarter.md` as the binding criteria. The most relevant values are:

- Value 1: local-first and privacy-first
- Value 2: low pre-LLM overhead and real speed
- Value 3: no fake success
- Value 4: verification is mandatory
- Value 5: recover once, do not loop blindly
- Value 6: universal, not hardcoded
- Value 7: no hacks by app/brand
- Value 10: text core first
- Value 12: no contamination from active window
- Value 13: cheap layers first, GUI/vision only when needed
- Value 15: safe by default, with safer alternatives
- Value 16: real multi-step missions
- Value 18: traceability
- Value 22: protect RAM/VRAM/CPU
- Value 23: rollback
- Value 28: modular in values, not bloated in architecture
- Value 29: real PC companion, always with verification

That leads to one hard rule:

The v3 target is not "recover the biggest possible number of tool names from v2".
The v3 target is "recover the strongest universal behavior from v2 and expose it through a smaller, cleaner, more honest public surface".

## Quantitative inventory

### Raw surface size

- Carter v2 public tool catalog: `244` tools
- Carter v2 capability families: `31`
- Carter v3 current public tool catalog: `32` tools

### v2 tool count by capability

| Capability | Tools |
| --- | ---: |
| system | 24 |
| office | 23 |
| web | 22 |
| filesystem | 14 |
| window | 13 |
| network | 10 |
| code | 10 |
| media | 9 |
| steam | 9 |
| media_files | 9 |
| memory | 8 |
| skills | 8 |
| power | 7 |
| vision | 7 |
| process | 6 |
| terminal | 6 |
| input | 6 |
| scheduler | 5 |
| desktop | 5 |
| pdf | 5 |
| email | 5 |
| database | 5 |
| heartbeat | 4 |
| ui | 4 |
| taskman | 4 |
| gui | 4 |
| calendar | 4 |
| notifications | 3 |
| download | 2 |
| meta | 2 |
| clock | 1 |

### Verification shape in v2

- `_NO_VERIFY`: `95`
- `_VERIFIABLE_TOOLS`: `148`
- tools with no verifier and not in `_NO_VERIFY`: `1` (`web_close_tab`)

### Verifier usage count in v2

| Verifier | Count |
| --- | ---: |
| `_verify_synchronous_ok` | 75 |
| `_verify_filesystem_write` | 24 |
| `_verify_gui_action` | 12 |
| `_verify_window_action` | 8 |
| `_verify_office_open` | 6 |
| `_verify_terminal` | 5 |
| `_verify_app_open` | 4 |
| `_verify_app_close` | 3 |
| `_verify_web_open` | 3 |
| `_verify_app_uninstall` | 2 |
| `_verify_clipboard` | 1 |
| `_verify_folder_open` | 1 |
| `_verify_download` | 1 |
| `_verify_mute` | 1 |
| `_verify_volume` | 1 |
| `_verify_network` | 1 |

Interpretation:

- The v2 catalog is not mostly "strongly verified".
- It is a mix of:
  - real universal backends,
  - honest read-only probes,
  - useful but optional domain automation,
  - and a large tail of weakly verified or app/provider-specific surfaces.

## Critical findings

### 1. Importing the full catalog would reintroduce catalog bloat and routing hacks

`legacy/Carter_v2/src/carter_v2/turn/tool_catalog_selection.py:3` says the quiet part out loud: v2 had to stop sending the full `~242-tool` registry to the LLM every turn.

`legacy/Carter_v2/src/carter_v2/turn/tool_catalog_selection.py:28` defines an `ALWAYS_ON_CORE` because the catalog had grown to the point where the agent needed manual rescue rails just to keep essential tools visible.

That is the opposite of the v3 direction.

v3 should solve more cases by improving:

- resolver quality,
- verification quality,
- universal executors,
- and mission/recovery behavior,

not by restoring a 244-tool public surface.

### 2. Large parts of v2 are not strong enough to claim "Jarvis did it"

`legacy/Carter_v2/src/carter_v2/turn/verification.py:365` defines `_verify_synchronous_ok`.

That verifier powers `75` tools. It confirms because the tool returned `ok=True`, not because the environment changed and Carter read it back. That is not acceptable as a default shape for v3.

Examples:

- `steam_install` -> `_verify_synchronous_ok`
- `office_powerpoint_save` -> `_verify_synchronous_ok`
- `office_powerpoint_add_slide` -> `_verify_synchronous_ok`

Those names sound powerful, but the verification contract is weaker than the user requirement for v3.

### 3. GUI high-level automation in v2 is useful as research, not importable as a core public tool

`legacy/Carter_v2/src/carter_v2/capabilities/gui_agent.py` is a serious attempt at high-level GUI action planning. It is also exactly the kind of large, expensive, fragile layer that `ContextoCarter.md` warns against using too early or too broadly.

The tool `gui_do` is verified by `_verify_gui_action` at `legacy/Carter_v2/src/carter_v2/turn/verification.py:392`, which does not provide the level of universal readback needed for v3.

Conclusion:

- salvage patterns and fallbacks from `gui_agent.py`;
- do not import `gui_do` as a first-class v3 public tool.

### 4. Browser/web in v2 mixes good ideas with too much public surface

`legacy/Carter_v2/src/carter_v2/capabilities/web.py:39` exposes a broad browser stack:

- open URL
- text search
- Playwright navigation
- download
- click/fill
- screenshot
- extract
- eval
- CDP session
- tab selection
- profiles
- extension relay

This is too much public surface for the current v3 stage.

Worse, `web_search_in_browser` is verified by `_verify_web_open` at `legacy/Carter_v2/src/carter_v2/turn/verification.py:466`, which mostly looks for browser processes, not strong final-tab readback.

Conclusion:

- import only the universal browser pieces;
- redesign verification before re-exposing richer browser control.

### 5. Steam and Office are not "universal core", even if parts of them are useful

`legacy/Carter_v2/src/carter_v2/capabilities/steam.py` is a good capability module for its narrow problem, but it is explicitly provider-specific:

- registry lookup for Steam `InstallPath` (`steam.py:48`)
- common Steam install paths (`steam.py:59`)
- alias table for store edge cases like `fall guys` (`steam.py:175`)

This directly conflicts with the v3 principle of avoiding app-specific logic in the core.

`legacy/Carter_v2/src/carter_v2/capabilities/office.py:72` shows another issue: Office automation is useful, but availability depends on `pywin32`. That makes it a backend/provider concern, not a core-v3 public truth.

Conclusion:

- do not import `steam_*` or `office_*` as core public tool families;
- extract reusable backend ideas only;
- surface future document/package flows through generic abstractions.

## Capability family verdicts

This is the central decision table for v3.

| Capability | Tools | Verification profile | Verdict for v3 | Reason |
| --- | ---: | --- | --- | --- |
| process | 6 | 2 app_open, 2 app_close, 1 uninstall, 1 no_verify | Import now | Core universal app/process layer |
| window | 13 | 8 window-action, 5 no_verify | Import now | Core universal window layer |
| ui | 4 | 2 gui-action, 2 no_verify | Import now as internal primitive | Deterministic UIA layer is valuable; keep behind generic UI surface |
| filesystem | 14 | 8 fs-write, 6 no_verify | Import now | Core universal filesystem layer |
| media | 9 | 1 volume, 1 mute, 3 sync-ok, 4 no_verify | Import now selectively | Real OS controls with readback are high-value v3 gaps |
| system | 24 | 8 sync-ok, 16 no_verify | Import now selectively | Strong source for probes and system read tools |
| terminal | 6 | 5 terminal, 1 no_verify | Import now selectively | Useful universal executor if policy stays strict |
| network | 10 | 1 network, 1 sync-ok, 8 no_verify | Import now selectively | Read-only probes are good; write actions need careful gating |
| desktop | 5 | clipboard/folder/fs-write/no_verify mix | Import now selectively | Screenshot, clipboard, folder open are universal |
| web | 22 | 3 web-open, 11 sync-ok, 7 no_verify, 1 missing | Redesign then import selectively | Good backend ideas, bad public surface size |
| input | 6 | 6 gui-action | Internal only | Useful executor, too low-level for public core |
| vision | 7 | 5 no_verify, 1 gui-action, 1 fs-write | Keep for later | Expensive, not baseline-first |
| office | 23 | 6 office-open, 12 sync-ok, 1 fs-write, 4 no_verify | Backend only | Generic document providers later, not public Office-named tools |
| pdf | 5 | 4 fs-write, 1 no_verify | Backend only | Useful document export/import provider |
| email | 5 | 2 sync-ok, 3 no_verify | Later optional domain | Not core PC control baseline |
| calendar | 4 | 3 sync-ok, 1 no_verify | Later optional domain | Not core PC control baseline |
| database | 5 | 2 fs-write, 1 sync-ok, 2 no_verify | Later optional domain | Useful for projects, not core baseline |
| code | 10 | 6 sync-ok, 4 no_verify | Later optional domain | Useful as dev surface, not core Jarvis baseline |
| media_files | 9 | 7 fs-write, 1 sync-ok, 1 no_verify | Later optional domain | Good batch media backend, not top v3 priority |
| scheduler | 5 | 4 sync-ok, 1 no_verify | Later optional domain | Useful but not critical to baseline |
| download | 2 | 1 download, 1 no_verify | Later optional backend | Better folded into generic web/filesystem pipeline |
| memory | 8 | 4 sync-ok, 4 no_verify | Already partially replaced | Keep v3 memory model, only salvage ideas |
| notifications | 3 | 3 sync-ok | Import selectively | `notify_toast` fits v3; speak/sound need policy and environment gates |
| power | 7 | 7 sync-ok | Dangerous layer only | Keep behind strict policy; do not widen early |
| steam | 9 | mixed app-open/app-close/uninstall/sync/no_verify | Do not import to core | Provider-specific and hardcoded |
| gui | 4 | 3 gui-action, 1 no_verify | Do not import raw | Too high-level and weakly verified |
| heartbeat | 4 | 2 sync-ok, 2 no_verify | Already solved differently | Keep v3 watcher architecture |
| taskman | 4 | 2 sync-ok, 2 no_verify | Fold into task runtime | Do not expose separately yet |
| skills | 8 | 3 sync-ok, 5 no_verify | Out of core scope | Not part of PC companion baseline |
| meta | 2 | 2 no_verify | Do not import | v3 should not need catalog self-description to survive |
| clock | 1 | 1 no_verify | Already present | Keep current v3 contract |

## What is directly exportable from v2

These are the v2 modules with the best export value for v3.

### A. High-value universal modules to mine now

1. `legacy/Carter_v2/src/carter_v2/capabilities/app_resolver.py`
   - Why it matters:
     - runtime app discovery via `Get-StartApps`
     - localized names
     - typo tolerance through normalization + fuzzy fallback
   - Why it fits v3:
     - universal
     - brand-agnostic
     - cheap
   - Best landing zone in v3:
     - `src/carter_v3/resolvers/resource_resolver.py`
     - `src/carter_v3/perception/probe.py`

2. `legacy/Carter_v2/src/carter_v2/capabilities/probe.py`
   - Why it matters:
     - installed apps
     - running processes
     - hardware snapshot
     - explicit cleanup of active-window contamination in context injection
   - Why it fits v3:
     - enables universal resolution and readback
     - aligns with Values 12, 13, 18, 22
   - Best landing zone in v3:
     - `src/carter_v3/perception/probe.py`
     - `src/carter_v3/resolvers/resource_resolver.py`

3. `legacy/Carter_v2/src/carter_v2/capabilities/process.py`
   - Why it matters:
     - launch ladder
     - runtime resolver integration
     - graceful close ladder instead of immediate kill
   - Why it fits v3:
     - universal app open/close is baseline Jarvis behavior
   - Best landing zone in v3:
     - `src/carter_v3/tools/dispatch.py`
     - new helper module such as `src/carter_v3/tools/process_actions.py`

4. `legacy/Carter_v2/src/carter_v2/capabilities/window.py`
   - Why it matters:
     - real window focus, wait, state change, inspect
   - Why it fits v3:
     - window management is universal and cheaper than vision
   - Best landing zone in v3:
     - `src/carter_v3/perception/probe.py`
     - new `src/carter_v3/tools/window_actions.py`

5. `legacy/Carter_v2/src/carter_v2/capabilities/ui.py`
   - Why it matters:
     - deterministic UIA actions on elements
   - Why it fits v3:
     - gives v3 a universal middle tier between windows and vision
   - Best landing zone in v3:
     - new `src/carter_v3/perception/uia_adapter.py`
     - new `src/carter_v3/tools/ui_actions.py`
   - Important constraint:
     - keep it as a lower-level primitive; do not expose `gui_do` semantics again.

6. `legacy/Carter_v2/src/carter_v2/capabilities/filesystem.py`
   - Why it matters:
     - safe path gating
     - rich file ops
     - zip/unzip and stat helpers
   - Why it fits v3:
     - universal, deterministic, cheap to verify
   - Best landing zone in v3:
     - `src/carter_v3/tools/dispatch.py`
     - new `src/carter_v3/tools/filesystem_actions.py`

7. `legacy/Carter_v2/src/carter_v2/capabilities/media.py`
   - Why it matters:
     - real `system_set_volume`
     - real `system_get_volume`
     - real `system_mute`
     - brightness/dark mode/device selection
   - Why it fits v3:
     - v3 still has stubbed audio controls; this is one of the cleanest high-value imports available
   - Best landing zone in v3:
     - new `src/carter_v3/tools/system_controls.py`
     - `src/carter_v3/tools/verifier.py`

8. `legacy/Carter_v2/src/carter_v2/capabilities/terminal.py`
   - Why it matters:
     - safer typed subprocess entrypoints
     - allowlist
     - timeout policy
     - truncated output
   - Why it fits v3:
     - preserves universal power without turning terminal into raw shell freedom
   - Best landing zone in v3:
     - `src/carter_v3/tools/dispatch.py`
     - `src/carter_v3/security/policy.py`

### B. Good backends, but not as current public tools

1. `legacy/Carter_v2/src/carter_v2/capabilities/web.py`
   - Keep:
     - URL normalization
     - fetch/extract helpers
     - browser session management ideas
   - Do not keep as raw public surface:
     - `web_connect_cdp`
     - `web_tabs`
     - `web_use_tab`
     - `web_profile_*`
     - `web_extension_relay_*`
   - Correct v3 shape:
     - keep public tools generic and few
     - hide provider/session complexity behind internal browser providers

2. `legacy/Carter_v2/src/carter_v2/capabilities/office.py`
   - Keep:
     - COM backend patterns
     - read/write/export mechanics
   - Do not keep as public Office-named surface:
     - `office_word_*`
     - `office_excel_*`
     - `office_powerpoint_*`
   - Correct v3 shape:
     - future generic tools like `document_create`, `spreadsheet_update`, `presentation_create`
     - Office becomes one provider, not the public ontology

3. `legacy/Carter_v2/src/carter_v2/capabilities/pdf.py`
   - Keep:
     - read/merge/split/export mechanics
   - Correct v3 shape:
     - document provider or export backend

4. `legacy/Carter_v2/src/carter_v2/capabilities/download.py`
   - Keep:
     - reliable download mechanics and status tracking
   - Correct v3 shape:
     - folded into generic web/filesystem pipeline, not separate public domain explosion

### C. Do not import into the v3 core as public capability families

1. `legacy/Carter_v2/src/carter_v2/capabilities/steam.py`
   - Not because it is bad code.
   - Because it is store-specific public surface.
   - What can still be mined:
     - protocol URL orchestration
     - manifest scanning patterns
     - generic provider idea for package/game catalogs

2. `legacy/Carter_v2/src/carter_v2/capabilities/gui_agent.py`
   - Useful research artifact
   - Wrong shape for current v3 core
   - Too expensive, too mission-heavy, too verification-weak to import raw

3. `legacy/Carter_v2/src/carter_v2/session/skills.py` plus `skill_*`
   - Outside the core PC-companion baseline

4. `meta_*`
   - Catalog self-description is a workaround for catalog overload, not a capability v3 should need

## The import pattern v3 should use

The right import pattern is not:

`v2 public tool -> same public tool in v3`

The right import pattern is:

`v2 backend/primitives -> v3 internal executor/provider -> smaller universal public tool`

Examples:

### Example 1: Office

Wrong:

- `office_powerpoint_new`
- `office_powerpoint_add_slide`
- `office_powerpoint_save`

Right:

- `presentation_create`
- `presentation_add_slide`
- `document_export`

With provider selection behind the scenes:

- COM provider if Office exists
- alternate provider later if needed
- same public contract regardless of backend

### Example 2: Steam

Wrong:

- `steam_install`
- `steam_run`
- `steam_search`

Right:

- generic install/open/search mission composed from:
  - `app_open`
  - `package_install`
  - `package_search`
  - `ui_observe`
  - `ui_act`

If Steam support exists later, it should live as a provider/adapter, not as core brand ontology.

### Example 3: GUI

Wrong:

- `gui_do`

Right:

- `window_list`
- `window_focus`
- `ui_find_element`
- `ui_invoke`
- `ui_set_value`
- `desktop_screenshot`
- `screen_read_text`

Then the mission loop orchestrates those primitives with verification, instead of exposing one giant opaque tool.

## Recommended v3 public surface after import

The v3 public surface should stay universal and relatively small.

Recommended direction:

### Core observe

- `clock_now`
- `system_get_time`
- `system_get_volume`
- `system_get_battery`
- `system_get_cpu_info`
- `system_get_ram_info`
- `system_get_gpu_info`
- `network_get_ip`
- `process_list`
- `window_list`
- `ui_observe`
- `filesystem_read_text`
- `filesystem_list_directory`
- `filesystem_search_files`
- `web_extract`
- `desktop_screenshot`
- `screen_read_text`

### Core act

- `app_open`
- `app_close`
- `window_focus`
- `window_close`
- `system_set_volume`
- `system_mute`
- `notify_toast`
- `filesystem_write_text`
- `filesystem_delete`
- `web_open_url`
- `web_search`
- `memory_save`
- `memory_recall`
- `memory_delete`
- `terminal_run_command`

### Generic workflow layer

- `document_create`
- `document_update`
- `spreadsheet_update`
- `presentation_create`
- `document_export`
- `package_search`
- `package_install`
- `package_uninstall`
- `download_file`

### Internal-only layers

- UIA actions
- raw input synthesis
- browser session/CDP
- provider-specific document backends
- provider-specific package store backends
- vision/VLM routers

## Recommended import phases

### Phase 1: import the strongest universal backends

Goal: raise real PC capability without bloating the public surface.

Import first:

- `app_resolver.py`
- `probe.py`
- `process.py`
- `window.py`
- `ui.py`
- `filesystem.py`
- `media.py`
- selective `terminal.py`

Why first:

- highest universal value
- lowest brand coupling
- strongest alignment with current v3 gaps
- directly improves "open app / close app / control system / manage windows / work with files"

### Phase 2: fix the current universal holes in v3

Use v2 as source material to close these concrete v3 deficits:

1. real volume/mute controls
2. stronger app open/close ladders
3. richer window actions
4. deterministic UIA tier before vision
5. stronger filesystem operations
6. safer terminal executor

### Phase 3: redesign browser around a smaller truth

Mine `web.py`, but only after defining a tighter v3 browser contract:

- open
- search
- extract
- maybe navigate session later

Do not begin by re-importing:

- profiles
- tabs
- CDP public knobs
- extension relay public knobs

### Phase 4: optional providers behind generic tools

Once the universal core is stable:

- document providers
- PDF providers
- database helpers
- email/calendar providers
- package-store providers

But only behind generic tool names.

## Concrete landing map for v3

| v2 source | v3 target | Import style |
| --- | --- | --- |
| `capabilities/app_resolver.py` | `src/carter_v3/resolvers/resource_resolver.py` | direct logic port, trimmed |
| `capabilities/probe.py` | `src/carter_v3/perception/probe.py` | merge and simplify |
| `capabilities/process.py` | `src/carter_v3/tools/dispatch.py` + helper module | direct logic port, keep launch/close ladder |
| `capabilities/window.py` | new `src/carter_v3/tools/window_actions.py` | direct logic port, adapt contracts |
| `capabilities/ui.py` | new `src/carter_v3/tools/ui_actions.py` | internal primitive, not giant public mission tool |
| `capabilities/filesystem.py` | `src/carter_v3/tools/dispatch.py` + helper module | direct logic port with v3 policy |
| `capabilities/media.py` | new `src/carter_v3/tools/system_controls.py` | direct logic port with verifier updates |
| `capabilities/terminal.py` | `src/carter_v3/tools/dispatch.py` / `security/policy.py` | selective import only |
| `capabilities/web.py` | new browser provider modules | selective extraction, not raw port |
| `capabilities/office.py` | future document providers | backend-only, no direct public port |
| `capabilities/pdf.py` | future document providers | backend-only |
| `capabilities/steam.py` | future package-store provider research | ideas only, not public port |
| `capabilities/gui_agent.py` | mission/recovery research only | do not port as runtime public tool |

## Priority recommendation

If the goal is to move v3 from "baseline landed" toward "real Jarvis for all non-dangerous cases", the best next import order is:

1. `media.py`
2. `process.py`
3. `app_resolver.py`
4. `probe.py`
5. `window.py`
6. `ui.py`
7. `filesystem.py`
8. selective `terminal.py`
9. selective `web.py`

Why `media.py` first:

- v3 already exposes `system_set_volume` and `system_mute`
- today they are precisely the kind of capability the user expects from a real PC companion
- v2 already contains a real universal implementation for that layer
- the verification story is stronger than many other families

## Anti-goals

These are the moves this audit explicitly rejects:

- re-adding `244` public tools to v3
- importing `steam_*` into the v3 core
- importing `office_*` into the v3 core as the user-facing ontology
- restoring `gui_do` as the "do everything in GUI" tool
- restoring catalog-overload plus top-K rescue logic as the main coping strategy
- accepting `_verify_synchronous_ok` as good enough for powerful actions

## Final conclusion

Carter v2 is not a catalog to be copied.

It is a mine of useful primitives, adapters, and lessons.

The parts worth exporting to Carter v3 are the ones that:

- are universal,
- are cheap before vision,
- admit real readback,
- avoid app-specific hardcodes,
- fit a smaller public contract,
- and help Carter act as a real Windows companion.

That means:

- yes to process/window/ui/filesystem/media/system/probe/resolver internals;
- yes to selective terminal and selective browser backends;
- no to importing the v2 public surface whole;
- no to brand-named tools in the v3 core;
- no to weak verification being treated as enough.

If v3 follows this import strategy, it can grow toward the user standard:

"all non-dangerous cases should really work and be verified"

without betraying the architectural values in `ContextoCarter.md`.

## Appendix A: full v2 capability inventory

### clock (1)

`system_get_time`

### process (6)

`app_open`, `app_close`, `app_uninstall`, `process_start_app`, `process_stop_app`, `process_list`

### window (13)

`window_list`, `window_inspect_active`, `window_focus`, `window_wait_for`, `window_minimize`, `window_maximize`, `window_restore`, `window_close`, `window_resize`, `window_move`, `window_get_text`, `window_screenshot`, `window_pin_on_top`

### ui (4)

`ui_find_element`, `ui_invoke`, `ui_set_value`, `ui_get_value`

### filesystem (14)

`filesystem_write_text`, `filesystem_read_text`, `filesystem_list_directory`, `filesystem_search_files`, `filesystem_move`, `filesystem_copy`, `filesystem_delete`, `filesystem_get_stat`, `filesystem_append_text`, `filesystem_rename`, `filesystem_zip`, `filesystem_unzip`, `filesystem_read_lines`, `filesystem_get_size`

### media (9)

`system_set_volume`, `system_get_volume`, `system_mute`, `system_set_brightness`, `system_get_brightness`, `system_set_dark_mode`, `system_get_dark_mode`, `system_list_audio_devices`, `system_set_default_audio_device`

### system (24)

`system_get_gpu_info`, `system_get_ram_info`, `system_get_disk_info`, `system_get_cpu_info`, `system_list_display_modes`, `system_get_refresh_rate`, `system_set_refresh_rate`, `system_get_keyboard_layout`, `system_list_keyboard_layouts`, `system_set_keyboard_layout`, `system_get_audio_device`, `system_get_battery`, `system_get_uptime`, `system_get_locale`, `system_get_default_browser`, `system_list_monitors`, `system_list_installed_apps`, `system_get_startup_apps`, `system_env_get`, `system_env_set`, `system_registry_read`, `system_registry_write`, `system_get_running_services`, `system_clipboard_history`

### network (10)

`network_wifi_list`, `network_wifi_connect`, `network_wifi_disconnect`, `network_get_ip`, `network_ping`, `network_get_public_ip`, `network_port_check`, `network_dns_lookup`, `network_speed_test`, `network_traceroute`

### terminal (6)

`terminal_run_command`, `terminal_run_powershell`, `terminal_winget_install`, `terminal_winget_search`, `terminal_pip_install`, `terminal_git_run`

### desktop (5)

`desktop_clipboard_set`, `desktop_clipboard_get`, `desktop_open_folder`, `desktop_screenshot`, `desktop_get_process_info`

### web (22)

`web_open_url`, `web_search_in_browser`, `web_search`, `web_navigate`, `web_click`, `web_fill`, `web_screenshot`, `web_extract`, `web_eval`, `web_close_session`, `web_close_tab`, `web_connect_cdp`, `web_tabs`, `web_use_tab`, `web_profile_list`, `web_profile_use`, `web_profile_status`, `web_profile_delete`, `web_extension_relay_start`, `web_extension_relay_status`, `web_extension_relay_eval`, `web_extension_relay_extract`

### input (6)

`input_mouse_click`, `input_mouse_move`, `input_mouse_scroll`, `input_key_press`, `input_hotkey`, `input_type_text`

### vision (7)

`vision_read_text_visual`, `vision_find_element_visual`, `vision_click_visual`, `vision_describe_screen`, `vision_omniparse_screen`, `vision_som_select`, `screen_capture_to_file`

### office (23)

`office_word_open`, `office_word_new`, `office_word_read`, `office_word_write`, `office_word_save`, `office_word_close`, `office_excel_open`, `office_excel_new`, `office_excel_read_cell`, `office_excel_write_cell`, `office_excel_read_range`, `office_excel_save`, `office_excel_close`, `office_powerpoint_open`, `office_powerpoint_new`, `office_powerpoint_add_slide`, `office_powerpoint_read_slide`, `office_powerpoint_save`, `office_powerpoint_close`, `office_word_find_replace`, `office_excel_create_chart`, `office_pdf_export`, `office_excel_run_macro`

### pdf (5)

`pdf_read_text`, `pdf_merge`, `pdf_split`, `pdf_from_docx`, `pdf_to_images`

### email (5)

`email_send`, `email_read_inbox`, `email_read_message`, `email_reply`, `email_list_folders`

### calendar (4)

`calendar_list_events`, `calendar_create_event`, `calendar_delete_event`, `calendar_update_event`

### database (5)

`db_sqlite_query`, `db_sqlite_execute`, `db_sqlite_create`, `db_csv_query`, `db_csv_to_excel`

### code (10)

`code_run_python`, `code_run_node`, `code_lint_python`, `code_format_python`, `code_git_status`, `code_git_diff`, `code_git_log`, `code_git_clone`, `code_git_push`, `code_git_pull`

### media_files (9)

`media_audio_play`, `media_audio_record`, `media_audio_transcribe`, `media_video_convert`, `media_video_extract_audio`, `media_video_trim`, `media_image_resize`, `media_image_convert`, `media_audio_tts_file`

### download (2)

`download_file`, `download_status`

### memory (8)

`memory_save`, `memory_recall`, `memory_search`, `memory_remember`, `memory_promote`, `memory_dream`, `memory_dream_preview`, `memory_context`

### notifications (3)

`notify_toast`, `notify_speak`, `notify_sound`

### power (7)

`power_shutdown`, `power_restart`, `power_lock`, `power_sleep`, `power_hibernate`, `power_signout`, `power_screen_off`

### steam (9)

`steam_open_client`, `steam_install`, `steam_uninstall`, `steam_run`, `steam_stop`, `steam_list_installed`, `steam_is_installed`, `steam_search`, `steam_open_page`

### heartbeat (4)

`heartbeat_status`, `heartbeat_read`, `heartbeat_write`, `heartbeat_append_task`

### taskman (4)

`taskman_task_status`, `taskman_task_list`, `taskman_task_cancel`, `taskman_task_wait`

### skills (8)

`skill_list`, `skill_read`, `skill_load`, `skill_run`, `skill_write`, `skill_refresh`, `skill_validate`, `skill_recipes`

### meta (2)

`meta_list_capabilities`, `meta_describe_tool`
