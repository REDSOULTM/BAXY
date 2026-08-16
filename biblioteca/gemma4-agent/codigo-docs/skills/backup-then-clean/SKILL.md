---
name: backup-then-clean
description: Create a ZIP backup of files/directories before any cleanup or large file operation. Verify backup integrity before proceeding to deletes. Use when user wants to "limpiar X pero por las dudas guardame copia", "antes de borrar respaldá".
priority: high
metadata:
  examples:
    - "hacé una copia de respaldo antes de borrar estos archivos"
    - "respaldá en un zip antes de limpiar y eliminar"
    - "antes de borrar guardame una copia de seguridad por las dudas"
    - "back up these files to a zip before deleting them"
    - "faça um backup em zip antes de apagar os arquivos"
---

# Backup then clean

Tools: `backup_sync`, `filesystem`, `verify`, `download` (hash). Honesty-critical: SÍ — NUNCA borrar antes de verificar el backup.

Paired con `safe-file-cleanup`. Diferencia: ese hace preview+delete reversible (papelera salvo "definitivo"); este copia explícita a .zip ANTES de tocar nada (útil para archivos pesados o garantía fuera del SO, movible a otro disco).

Usar cuando: "limpiá X pero backup primero", "antes de borrar Y guardame copia", "comprime X y después borralo", "archivá la carpeta Z". NO usar si pidió "borrá X sin copia" o cleanup inmediato → eso es `safe-file-cleanup`.

## Steps

1. **Identificar target.** `filesystem(action="list", path="<dir>")` o por pattern `filesystem(action="search", root="<root>", pattern="<pattern>", budget_s=5)`. Reportar: cantidad de archivos, tamaño total agregado, path absoluto.
2. **Confirmar destino.** Default `~/.gemma4/backups/<timestamp>_<source-name>.zip`. Si pide otro path: confirmar que el padre exista y que el archivo final NO exista (no sobrescribir backups).
3. **Crear backup.** `backup_sync(action="backup_create", source="<path>", destination="<zip path>", include_hidden=False)`. Su verifier (TODO): zip existe, size>0, opcional cuenta entries.
4. **Verificar integridad.** `download(action="hash", path="<zip path>", algorithm="SHA256")`. Reportar: "Backup creado: `<path>` (NN MB). SHA256: <hash>. Guardalo para validar a futuro que el zip no se corrompió."
5. **NO borrar hasta verificar.** Solo tras steps 3+4 con verifier `confirmed=True`. Si `confirmed=False`/`None`: "El backup no está verificado. NO voy a borrar nada hasta confirmar el zip. Revisá `<path>` y decime." Si OK: "Backup OK. ¿Procedo a borrar el original?" → esperar "sí".
6. **Cleanup tras confirmación.** Delegar a `safe-file-cleanup` (load si lazy) o directo: `filesystem(action="delete", path="<source path>", recursive=True)`. Cada delete verifica (`confirmed=True` si el path ya no existe).
7. **Reportar final.** "Operación completada: Backup `<zip path>` (NN MB, SHA256 <prefix>...); Borrado <N> archivos/carpetas, todos verificados ausentes; Rollback: extraé el zip si necesitás recuperar."

## Outcomes honestos

| Estado | Cómo reportar |
|---|---|
| Backup creado + verificado + delete OK | "Hecho. Backup en <path>, original borrado." |
| Backup creado pero zip vacío / falla verify | "El zip se creó pero parece corrupto. NO borré nada. Revisá `<path>`." |
| Backup OK pero usuario no confirmó delete | "Backup en <path>. Esperando tu OK para borrar el original." |
| Source no existe | "No encontré `<source>`. ¿Path correcto? No creé backup ni borré nada." |
| Disk full durante backup | "No hay espacio para crear el backup (size estimado: NN MB). NO borré nada." |
| Permission denied | "No tengo permisos para leer `<source>` o escribir `<destination>`. ¿Corro como admin?" |

## Anti-patterns

- ❌ Borrar el original ANTES de verificar el backup.
- ❌ Saltarse el SHA256 si el archivo es grande "porque tarda".
- ❌ Sobrescribir un backup existente (siempre nombre con timestamp).
- ❌ Reportar "backup hecho" si `backup_sync` retornó error.
- ❌ Borrar tras un backup que verifier marcó `confirmed=None` (unverifiable ≠ verified).
- ❌ Crear backups en la misma carpeta que se va a borrar (recursión).
