# Fix Notes — Carter Agent
Observaciones fuera de scope (no se arreglan; quedan para próxima auditoría).

---

## Pendientes para próxima auditoría

- **T3-smart_home-rollback-incomplete-032**: requiere snapshotear el `state` HA completo (atributos brightness/hs_color/color_temp/etc.) y construir el rollback con esos atributos. Diseño: añadir helper `_hass_snapshot_entity(host, token, entity_id)` que use `/api/states/<entity_id>` y guarde el dict completo en checkpoint metadata; el rollback step debe invocar `call_service` con el shape inverso.
- **T2-backup_sync-no-checkpoint-022 (PARTIAL)**: el dst-tree snapshot antes del primer overwrite implica copiar todo el árbol del destino a una sibling backup dir (potencialmente decenas de GB). Quizás registrar solo la lista de paths que serán sobrescritos y ofrecer rollback como "extract from backup zip" en lugar de "restore from snapshot".
- **Schema descriptions en vision/gui**: tras CC-106 los matches OCR exponen `screen_x/screen_y`, pero la description del schema `vision`/`gui` aún no menciona `coord_space` ni la diferencia entre image-local y screen-local. Worth a doc-only follow-up.
- **CC-105 false-positives**: la redacción matchea `primary_key`, `column_key`, `keyboard_*`, etc. Si causa ruido en logs, considerar allowlist explícita (`{"password", "token", "secret", "api_key", "auth_token", ...}`) en vez de regex.
- **`_ps_quote` legacy**: solo se mantiene para escapar identifiers ya validados (task_name registrado por el agente, no por LLM). Worth a doc note o removal en pasada futura.

