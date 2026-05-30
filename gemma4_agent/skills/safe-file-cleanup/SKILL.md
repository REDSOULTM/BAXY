---
name: safe-file-cleanup
description: Safely delete files or directories. Always preview before deleting; refuse without explicit confirmation; never bulk delete user data without naming each target.
priority: high
metadata:
  examples:
    - "borrá estos archivos pero con cuidado"
    - "eliminá esta carpeta de forma segura"
    - "limpiá estos archivos mostrándome antes qué vas a borrar"
    - "quiero borrar archivos pero confirmame primero"
    - "safely delete these files with a preview first"
    - "apague estes arquivos com cuidado"
  when_to_use:
    - "el usuario quiere borrar archivos o carpetas del disco con cuidado"
    - "eliminar archivos mostrando antes qué se va a borrar"
  limitations:
    - "quitar el primer elemento mostrado de una lista"
    - "borrar un elemento de una lista que se mostró antes en la respuesta"
    - "not for picking or removing an item from a shown list"
requires:
  os: [windows, linux, darwin]
---

# Safe file cleanup

**Tools used**: `filesystem`, `verify`, `safety`.
**Honesty-critical**: yes — borrar es irreversible (papelera ayuda pero no
siempre, y networks shares no la usan).

## Cuándo usar este skill

El usuario dice algo como:
- "borrá este archivo"
- "limpiá la carpeta X"
- "tirá la basura"
- "borrá todos los .tmp"

## Reglas duras

1. **Nunca borrar sin previa enumeración explícita** de qué se va a borrar.
2. **Nunca borrar carpetas del sistema** sin confirmación:
   - `C:\Windows\*`, `C:\Program Files\*`, `C:\Program Files (x86)\*`
   - `~/.config`, `~/.ssh`, `~/AppData/*`
   - Cualquier path bajo `%PROGRAMDATA%`
3. **Nunca usar `filesystem(action="delete", recursive=True)`** sobre paths
   con `*` o wildcards expandidos sin enumerar.
4. **Bulk delete >10 archivos** requiere confirmación explícita del usuario.

## Steps

### 1. Resolve y preview

```
filesystem(action="list", path="<dir>")
```

O si es búsqueda por pattern:

```
filesystem(action="search", root="<dir>", pattern="*<filter>*", budget_s=5)
```

Reportar al usuario **la lista completa** de qué se borraría (paths absolutos
+ tamaño total). Ejemplo:

> "Voy a borrar estos 7 archivos (3.2 MB total):
>   - C:/Users/user/temp/log1.txt (200 KB)
>   - C:/Users/user/temp/log2.txt (180 KB)
>   - ...
> ¿Confirmás? (sí/no)"

### 2. Esperar confirmación

NO borrar todavía. Esperar al próximo turn.

### 3. Borrar individualmente

Si el usuario dijo "sí":

```
filesystem(action="delete", path="<path1>")
filesystem(action="delete", path="<path2>")
...
```

Cada delete crea un **checkpoint** que permite rollback via `state` tool.

### 4. Verificar

El verifier de `filesystem` chequea estructuralmente que el path ya no
existe (`absent_after_delete`). Si algún path **sigue existiendo** tras el
delete, reportar UNVERIFIED para ese path.

## Outcomes honestos

| Estado | Cómo reportar |
|---|---|
| Lista enumerada, esperando confirmación | "Voy a borrar N archivos. ¿Confirmás? (sí/no)" |
| Borrado verificado, todos absent | "Borré los N archivos." |
| Algún path quedó | "Borré N-1; el archivo X sigue existiendo (¿permisos?)." |
| Permission denied en algún path | "No pude borrar X: permission denied. Probá con permisos elevados." |
| Bulk request sin enumerar | "Necesito enumerar primero qué hay ahí. ¿Te lo listo?" |

## Anti-patterns

- ❌ `filesystem(action="delete", path="C:/Users/<user>/Documents", recursive=True)`
   sin enumerar primero. **Destructivo masivo sin opt-in.**
- ❌ Asumir "sí" porque el usuario dijo "borrá X" — eso fue INTENT, no
   autorización para wildcards.
- ❌ Mentir post-delete: si verify dice path sigue ahí, reportar UNVERIFIED.
- ❌ Borrar `.git`, `node_modules`, `__pycache__` sin pedir confirmación —
   son recoverable pero el usuario puede no querer perder estado.

## Casos especiales

- **Papelera/Trash**: en Windows, `filesystem.delete` por default va a la
  papelera (recoverable). Si el usuario pide "borrá definitivo" / "sin
  papelera" / "shift+delete", documentarlo explícito.
- **Symlinks**: borrar el symlink, NO el target. La tool ya lo maneja, pero
  reportarlo si el path es un symlink.
- **OneDrive / Cloud-synced folders**: avisar que el borrado puede sync
  a cloud y afectar otros devices.
