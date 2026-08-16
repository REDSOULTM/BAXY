# Overnight Audit Report

Generated: 2026-06-26T09:59:09

## Summary

Total: 1
Passed: 0
Failed: 1
Blocked by policy: 0
Critical hangs: 0

Hardness: live-all. No expected policy gate is counted as PASS; missing apps, accounts, local APIs, or OS capabilities are reported as FAIL with evidence.

## Modified Files

- `nightly_e2e_suite.py`: new E2E audit harness.
- `OVERNIGHT_AUDIT_REPORT.md`: generated report.
- `overnight_audit_results.json`: generated machine-readable results.

## Results

| ID | Module | Status | ms | Verifier | Evidence |
|---|---|---:|---:|---|---|
| W01 | WhatsApp | FAIL | 30969 | Gemma4Agent.tools.execute('whatsapp', args) child process + visible message verifier | {"ok": true, "action": "send_message", "provider": "whatsapp_desktop_gui_search", "recipient_contact": "Música", "recipient_source": "gui_search", "text": "hola", "opened": true, " |
