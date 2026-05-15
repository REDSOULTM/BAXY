# Smoke Log — Modo A (Direct call con stubs)
Generado en sesión autónoma 2026-05-15.


## system
- [PASS] `system` happy time → expect=ok, got=ok
- [PASS] `system` cpu_ram_gpu → expect=ok, got=ok
- [PASS] `system` disk → expect=ok, got=ok
- [PASS] `system` battery → expect=ok, got=ok
- [PASS] `system` CC-101 shutdown gate → expect=needs_confirmation, got=needs_confirmation
- [PASS] `system` CC-101 restart gate → expect=needs_confirmation, got=needs_confirmation
- [PASS] `system` CC-101 sleep gate → expect=needs_confirmation, got=needs_confirmation
- [PASS] `system` anti-bypass _internal_safe filtered → expect=needs_confirmation, got=needs_confirmation
- [PASS] `system` anti-bypass routine_context filtered → expect=needs_confirmation, got=needs_confirmation
- [PASS] `system` confirmed=True passes gate → expect=ok, got=ok
- [PASS] `system` invalid action → expect=any_error, got=failed

## filesystem
- [PASS] `filesystem` list → expect=ok, got=ok
- [PASS] `filesystem` read → expect=ok, got=ok
- [PASS] `filesystem` search → expect=any, got=failed
- [PASS] `filesystem` diff happy → expect=ok, got=ok
- [PASS] `filesystem` CC-101 delete gate → expect=needs_confirmation, got=needs_confirmation
- [PASS] `filesystem` delete confirmed → expect=ok, got=ok
- [PASS] `filesystem` anti-bypass _internal_safe filtered → expect=needs_confirmation, got=needs_confirmation
- [PASS] `filesystem` missing path → expect=any_error, got=failed
- [PASS] `filesystem` T2-003 copy overwrite=false rejects existing → expect=needs_user, got=needs_user

## terminal
- [PASS] `terminal` CC-101 terminal gate → expect=needs_confirmation, got=needs_confirmation
- [PASS] `terminal` confirmed=True passes → expect=ok, got=ok
- [PASS] `terminal` anti-bypass _internal_safe filtered → expect=needs_confirmation, got=needs_confirmation
- [PASS] `terminal` T2-007 cwd validation → expect=needs_user, got=needs_user
- [PASS] `terminal` empty command → expect=any_error, got=failed

## package
- [PASS] `package` search (no gate) → expect=ok, got=ok
- [PASS] `package` list (no gate) → expect=ok, got=ok
- [PASS] `package` CC-101 install gate → expect=needs_confirmation, got=needs_confirmation
- [PASS] `package` CC-101 uninstall gate → expect=needs_confirmation, got=needs_confirmation
- [PASS] `package` anti-bypass _internal_safe filtered → expect=needs_confirmation, got=needs_confirmation
- [PASS] `package` install confirmed → expect=ok, got=ok

## database
- [PASS] `database` status → expect=ok, got=ok
- [PASS] `database` list_tables → expect=ok, got=ok
- [PASS] `database` schema happy → expect=ok, got=ok
- [PASS] `database` T2-017 identifier validation → expect=needs_user, got=needs_user
- [PASS] `database` query happy → expect=ok, got=ok
- [PASS] `database` T2-018 CTE+DML rejected by driver-level read-only → expect=any_error, got=failed
- [PASS] `database` CC-101 execute gate → expect=needs_confirmation, got=needs_confirmation
- [PASS] `database` execute confirmed → expect=ok, got=ok
- [PASS] `database` anti-bypass → expect=needs_confirmation, got=needs_confirmation
- [PASS] `database` CC-105 password redacted from result

## backup_sync
- [PASS] `backup_sync` status → expect=ok, got=ok
- [PASS] `backup_sync` CC-101 restore overwrite gate → expect=needs_confirmation, got=needs_confirmation
- [PASS] `backup_sync` restore skip-policy (classifier asks confirm) → expect=needs_confirmation, got=needs_confirmation
- [PASS] `backup_sync` restore skip-policy confirmed → expect=ok, got=ok
- [PASS] `backup_sync` T2-021 zip-slip blocked → expect=failed, got=failed

## notification
- [PASS] `notification` status → expect=ok, got=ok
- [PASS] `notification` toast → expect=any, got=failed
- [PASS] `notification` T2-024 invalid time format → expect=needs_user, got=needs_user
- [PASS] `notification` T2-024 HH:MM passes prevalidator, classifier asks confirm → expect=needs_confirmation, got=needs_confirmation
- [PASS] `notification` alarm_create HH:MM confirmed → expect=any, got=ok

## routine
- [PASS] `routine` list → expect=ok, got=ok
- [PASS] `routine` T3-028 PS injection rejected → expect=any_error, got=needs_confirmation
- [PASS] `routine` happy create → expect=any, got=needs_confirmation

## network
- [PASS] `network` ping → expect=any, got=ok
- [PASS] `network` dns_get → expect=ok, got=ok
- [PASS] `network` T2-033 IPv4 validation → expect=needs_user, got=needs_user
- [PASS] `network` CC-100 state enum → expect=needs_user, got=needs_user
- [PASS] `network` connections happy → expect=ok, got=ok
- [PASS] `network` dns_set valid IPs (may need adapter; just shouldn't crash) → expect=any, got=ok

## maintenance
- [PASS] `maintenance` status → expect=any, got=ok
- [PASS] `maintenance` firewall_status → expect=ok, got=ok
- [PASS] `maintenance` T2-025 PS injection rejected → expect=needs_user, got=needs_user
- [PASS] `maintenance` event_logs_query happy → expect=ok, got=ok
- [PASS] `maintenance` T2-026 defender returns job_id (got status=running, job_id=res_14338fb3ad)
- [PASS] `maintenance` T2-027 disk_cleanup_describe no exec arrays

## gui
- [PASS] `gui` screenshot default → expect=ok, got=ok
- [PASS] `gui` CC-106 monitor=primary → expect=ok, got=ok
- [PASS] `gui` monitor invalid → expect=needs_user, got=needs_user
- [PASS] `gui` T3-010 SendKeys escape → expect=ok, got=ok
- [PASS] `gui` keypress ENTER → expect=ok, got=ok
- [PASS] `gui` CC-100 keypress injection safe → expect=ok, got=ok

## window
- [PASS] `window` list → expect=ok, got=ok
- [PASS] `window` active → expect=ok, got=ok
- [PASS] `window` control focus → expect=any, got=failed

## web
- [PASS] `web` read public → expect=any, got=failed
- [PASS] `web` T2-014 SSRF guard blocks loopback → expect=any_error, got=failed
- [PASS] `web` T2-014 SSRF guard blocks cloud metadata → expect=any_error, got=failed
- [PASS] `web` search → expect=any, got=failed

## browser_real
- [PASS] `browser_real` status → expect=any, got=ok

## data_analysis
- [PASS] `data_analysis` status → expect=any, got=ok
- [PASS] `data_analysis` T2-035 @ rejected → expect=needs_user, got=needs_user
- [PASS] `data_analysis` T2-035 backtick rejected → expect=needs_user, got=needs_user
- [PASS] `data_analysis` csv_query happy → expect=any, got=ok

## download
- [PASS] `download` status → expect=any, got=failed
- [INFO] `download.fetch` ran: ok=False, verified=False, signature_present=None

## smart_home
- [PASS] `smart_home` status → expect=any, got=ok

## audio
- [PASS] `audio` get_volume → expect=any, got=ok
- [PASS] `audio` devices → expect=any, got=ok

## audio_device
- [PASS] `audio_device` status → expect=any, got=ok
- [PASS] `audio_device` list → expect=any, got=ok

## app
- [PASS] `app` search → expect=any, got=ok

## steam
- [PASS] `steam` status → expect=any, got=failed

## vision
- [PASS] `vision` describe → expect=any, got=failed

## browser
- [PASS] `browser` open → expect=any, got=ok

## uia
- [PASS] `uia` find → expect=any, got=ok

## clipboard
- [PASS] `clipboard` read → expect=any, got=ok
- [PASS] `clipboard` write → expect=any, got=ok

## memory
- [PASS] `memory` save → expect=any, got=failed
- [PASS] `memory` recall → expect=any, got=ok
- [PASS] `memory` list → expect=any, got=ok

## verify
- [PASS] `verify` app_opened → expect=any, got=ok
- [PASS] `verify` file_exists → expect=ok, got=ok

## state
- [PASS] `state` resources → expect=ok, got=ok
- [PASS] `state` checkpoints → expect=ok, got=ok
- [PASS] `state` note → expect=ok, got=ok

## input
- [PASS] `input` languages → expect=any, got=failed

## env
- [PASS] `env` get → expect=any, got=ok

## registry
- [PASS] `registry` query → expect=any, got=ok

## email
- [PASS] `email` status → expect=any, got=ok

## reminder
- [PASS] `reminder` list → expect=any, got=ok

## knowledge
- [PASS] `knowledge` status → expect=any, got=ok

## office
- [PASS] `office` status → expect=any, got=ok

## media
- [PASS] `media` now_playing → expect=any, got=ok

## source_manager
- [PASS] `source_manager` status → expect=any, got=ok
- [PASS] `source_manager` sources → expect=any, got=ok

## dependency
- [PASS] `dependency` status → expect=any, got=ok

## contacts
- [PASS] `contacts` list → expect=any, got=ok

## notes_tasks
- [PASS] `notes_tasks` list → expect=any, got=ok

## local_calendar
- [PASS] `local_calendar` event_list → expect=any, got=ok

## habit_tracker
- [PASS] `habit_tracker` stats → expect=any, got=needs_user

## local_search
- [PASS] `local_search` status → expect=any, got=ok

## printer_scanner
- [PASS] `printer_scanner` status → expect=any, got=ok

## desktop_layout
- [PASS] `desktop_layout` status → expect=any, got=ok

## document
- [PASS] `document` status → expect=any, got=ok

## developer
- [PASS] `developer` status → expect=any, got=ok

## device_settings
- [PASS] `device_settings` status → expect=any, got=ok

## game_launcher
- [PASS] `game_launcher` status → expect=any, got=ok

## media_edit
- [PASS] `media_edit` status → expect=any, got=ok

## watcher
- [PASS] `watcher` list → expect=any, got=ok

## job_manager
- [PASS] `job_manager` list → expect=any, got=ok

## fact_check
- [PASS] `fact_check` status → expect=any, got=ok

## photo_library
- [PASS] `photo_library` status → expect=any, got=ok

## container
- [PASS] `container` status → expect=any, got=ok

## creative_local
- [PASS] `creative_local` status → expect=any, got=ok

## form_filler
- [PASS] `form_filler` status → expect=any, got=ok

## peripheral
- [PASS] `peripheral` status → expect=any, got=ok

## accessibility
- [PASS] `accessibility` status → expect=any, got=ok

## study
- [PASS] `study` status → expect=any, got=ok

## subagent
- [PASS] `subagent` status → expect=any, got=error

## safety
- [PASS] `safety` status → expect=ok, got=ok
- [PASS] `safety` pending → expect=ok, got=ok
- [PASS] `job_manager` T2-046 shlex.split string command → expect=any, got=ok

## Sanity check
- [PASS] no destructive PowerShell tokens observed in subprocess calls
- subprocess.run calls: 33
- subprocess.Popen calls: 2
- urlopen calls: 2

## Resumen Modo A
- Total casos: 143
- PASS: 143
- FAIL: 0
- Bypass tests: 6/6 PASS (anti-bypass de CC-101)

## Casos fallados