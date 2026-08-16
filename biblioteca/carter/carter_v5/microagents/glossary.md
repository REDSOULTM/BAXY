---
name: glossary
triggers: ["que significa", "qué significa", "que es ", "qué es ", "vocabulario", "jerga", "glossary"]
priority: low
---

# Glossary (Carter v5 internal terms)

- **archetype**: clasificación del turn (TRIVIAL | KNOWLEDGE | TOOL_SIMPLE | TOOL_VERIFY | MISSION | MISSION_LONG | DESTRUCTIVE).
- **composite tool**: tool agrupadora (`gui`, `filesystem`, `app`) que rutea a tools individuales internas. 16 totales.
- **deeplink**: URI scheme registrado en HKCR de Windows (`steam://`, `spotify:`, `vscode://`). Ver `tools/deeplinks.py`.
- **HKCR**: `HKEY_CLASSES_ROOT` — registry de Windows para tipos de archivo + URI schemes.
- **mmproj**: multimodal projector file (`mmproj-F16.gguf`) que conecta vision encoder + LLM en llama.cpp.
- **mission_goal**: verifier por intención del prompt (Voyager pattern). Vive en `mission/goal.py`.
- **OUTCOME**: estado final del turn — COMPLETED, PARTIAL, FAILED, UNVERIFIED, NEEDS_USER, NEEDS_PERMISSION, BLOCKED_BY_POLICY, TOOL_OK_VERIFIER_INCONCLUSIVE, INTENT_NOT_FULFILLED.
- **tier**: perfil de hardware (tier_6gb | tier_8gb | tier_10gb | tier_12gb | tier_16gb).
- **UNVERIFIED**: tool ejecutó pero no podemos medir efecto. Honesto, NO es falla.
- **causal focus**: enfocar la ventana que cambió causalmente por la acción reciente. Ver `tools/gui.py:_focus_window_changed_by_last_action`.
- **god mode**: bypass de safety gate (env `CARTER_V4_GOD_MODE=1`). Solo para owner trusted.
