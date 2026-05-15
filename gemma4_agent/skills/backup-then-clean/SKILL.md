---
name: backup-then-clean
description: Create a ZIP backup of files/directories before any cleanup or large file operation. Verify backup integrity before proceeding to deletes. Use when user wants to "limpiar X pero por las dudas guardame copia", "antes de borrar respaldá".
priority: high
---

# Backup then clean

**Tools used**: `backup_sync`, `filesystem`, `verify`, `download` (for hash).
**Honesty-critical**: yes — NUNCA borrar antes de que el backup esté
verificado.

Es **paired** con `safe-file-cleanup`. Diferencia:
- `safe-file-cleanup`: preview + delete con checkpoint reversible (en
  papelera, salvo si el usuario pide "definitivo").
- `backup-then-clean`: copia explícita a un .zip ANTES de tocar nada.
  Útil cuando los archivos pesan mucho o el usuario quiere garantía
  fuera del SO (puede mover el .zip a otro disco).

## Cuándo usar este skill

El usuario dice:
- "limpiá X pero hacé backup primero"
- "antes de borrar Y guardame copia"
- "comprime X y después borralo"
- "archivá la carpeta Z"

NO usar si el usuario ya dijo "borrá X sin copia" o pidió cleanup
inmediato — eso es `safe-file-cleanup` directo.

## Steps

### 1. Identificar el target

```
filesystem(action="list", path="<dir>")
```

O si es búsqueda por pattern:

```
filesystem(action="search", root="<root>", pattern="<pattern>", budget_s=5)
```

Reportar al usuario:
- Cantidad de archivos.
- Tamaño total agregado.
- Path absoluto.

### 2. Confirmar destino del backup

Por default: `~/.gemma4/backups/<timestamp>_<source-name>.zip`.

Si el usuario quiere otro path:
- Confirmar que el padre exista.
- Confirmar que el archivo final NO exista (no sobrescribir backups).

### 3. Crear el backup

```
backup_sync(action="backup_create",
            source="<path>",
            destination="<zip path>",
            include_hidden=False)
```

El verifier de `backup_sync` (cuando lo implemente — TODO):
- Confirma que el .zip existe.
- Lee el size > 0.
- Opcionalmente: cuenta entries del zip.

### 4. Verificar integridad

```
download(action="hash", path="<zip path>", algorithm="SHA256")
```

Esto produce un SHA256 del .zip. Reportar al usuario:

> "Backup creado: `<path>` (NN MB). SHA256: <hash>. Guardá este hash
> si querés validar en el futuro que el zip no se corrompió."

### 5. NO borrar hasta que el backup esté verificado

Solo después de que **steps 3+4 hayan terminado con verifier confirmed**,
proceder al cleanup. Si el verifier dijo `confirmed=False` o `None`:

> "El backup no está verificado. NO voy a borrar nada hasta que pueda
> confirmar el zip. Revisá `<path>` manualmente y decime."

Si verifier OK:

> "Backup OK. ¿Procedo a borrar el original?" → esperar "sí"

### 6. Cleanup tras confirmación

Esta parte la delega el LLM al `safe-file-cleanup` skill (load it
explícitamente si fue lazy), o ejecuta directo:

```
filesystem(action="delete", path="<source path>", recursive=True)
```

Cada delete tiene su verifier (`confirmed=True` si el path ya no existe).

### 7. Reportar final

> "Operación completada:
> - Backup: `<zip path>` (NN MB, SHA256: <prefix>...)
> - Borrado: <N> archivos/carpetas, todos verificados ausentes.
> - Rollback disponible: extraé el zip si necesitás recuperar."

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
- ❌ Borrar después de un backup que verifier marcó `confirmed=None`
  (unverifiable ≠ verified).
- ❌ Crear backups en la misma carpeta que se va a borrar (recursión).
