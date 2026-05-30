---
name: schedule-recurring-task
description: Create a recurring routine (cron-like, on_phrase, or on_app_open trigger) and confirm with the user before activating. Use when user says "cada N hours/days do X", "cuando diga X haz Y", "todas las mañanas Y".
priority: medium
metadata:
  examples:
    - "programá una tarea para que se repita cada día"
    - "todas las mañanas hacé esto automáticamente"
    - "cuando diga tal frase ejecutá tal acción"
    - "creame una rutina que corra cada N horas"
    - "schedule a recurring task every morning"
    - "agende uma tarefa recorrente todos os dias"
---

# Schedule recurring task

**Tools used**: `routine`, `notification`, `verify`.
**Honesty-critical**: yes — never silently activate destructive routines.
Always confirm before enabling.

## Cuándo usar este skill

El usuario dice:
- "todas las mañanas a las 9 mostrame X"
- "cada hora chequeá Y"
- "cuando diga 'pomodoro' arrancá un timer de 25 min"
- "cuando abra Steam, mutea el sistema"
- "todos los lunes hacé Z"

Diferencia con `notification`:
- `notification`: one-shot timer/alarm/reminder (15 min, mañana 8am, etc).
- `routine`: **recurrente** o **disparada por evento** (phrase/app_open).

Si el usuario dice "recordame en 10 min algo", **usar `notification`**,
NO este skill. Este skill es para cosas que se repiten.

## Steps

### 1. Identificar el trigger

Tres tipos de trigger soportados:

#### 1a. Time-based (cron-like)

Si el usuario dice "todas las mañanas a las 9", "cada hora", "los lunes":

```python
trigger = {
    "type": "cron",
    "schedule": "0 9 * * *",   # 9 AM cada día
    # o "0 * * * *" cada hora, "0 9 * * 1" lunes 9 AM
}
```

Si no estás 100% seguro del cron expression, **decirle al usuario**
qué cron interpretaste antes de crear:

> "Voy a programarlo como `0 9 * * *` = todas las mañanas a las 9. ¿OK?"

#### 1b. Phrase-triggered

Si el usuario dice "cuando diga X haz Y":

```python
trigger = {
    "type": "on_phrase",
    "phrase": "<keyword>",  # case-insensitive, accent-folded
}
```

La phrase debe ser distintiva (≥3 chars). Confirmar con el usuario:

> "Vas a poder activarlo diciendo '<phrase>'. ¿Es OK o querés cambiar
> el keyword?"

#### 1c. Process-triggered

Si el usuario dice "cuando abra X, hacé Y":

```python
trigger = {
    "type": "on_app_open",   # o "on_app_close"
    "process": "<exe.exe>",
    "interval_minutes": 2,   # polling
}
```

### 2. Definir los steps

Cada step es una tool call. Ejemplo:

```python
steps = [
    {"tool": "audio", "args": {"action": "mute", "state": True}},
    {"tool": "notification", "args": {"action": "toast_now",
                                       "title": "Muted",
                                       "text": "System volume muted on Steam open"}},
]
```

**Validar** que las tools existen y los args son correctos antes de
crear la routine — si la tool falla en runtime el usuario no se entera
hasta el primer dispatch.

### 3. Detectar si es destructive

Si CUALQUIER step tiene una tool destructive (filesystem.delete,
registry.delete, terminal con comandos destructive), **NO crear sin
confirmación explícita del usuario**:

> "Esta routine incluye un paso destructivo: `<tool.action>`. ¿Confirmás
> que sí lo querés? Una vez activa, se ejecuta automáticamente sin
> nuevas preguntas. (sí/no)"

Esperar al próximo turn.

### 4. Crear

```
routine(action="create",
        label="<descriptive name>",
        trigger=<trigger dict>,
        steps=<steps list>,
        enabled=True)
```

Si trigger es `on_phrase` y algún step es destructive, **PASAR**
`confirmed_at_create=True` solo si el usuario explicitamente confirmó.

### 5. Verificar y reportar

```
routine(action="list")
```

Confirmar que la routine aparece con `enabled=True`. Reportar:

> "Creada la routine `<label>`:
> - Trigger: [descripción human-readable del trigger]
> - Steps: [N pasos, listar tools usadas]
> - Próxima ejecución estimada: [si time-based, el next fire time]
>
> Podés desactivarla con `routine(action="disable", id=<id>)`."

## Outcomes honestos

| Estado | Cómo reportar |
|---|---|
| Routine creada + listed con enabled=True | "Listo, la routine `<label>` está activa. [resumen]" |
| Routine creada pero destructive necesita confirm | "La routine incluye `<step>` que es destructivo. ¿Confirmás antes de activar?" |
| Trigger ambiguo / no parseo cron | "Tu pedido es ambiguo: '<original>'. Lo interpreté como `<cron>`. ¿Es lo que querés?" |
| Tool en step no existe | "El step `<tool>` no existe. ¿Querés que sugiera una alternativa o ajustás vos?" |
| Conflicto con routine existente con misma phrase | "Ya existe una routine para la phrase `<X>`. ¿La sobrescribo o usamos otra phrase?" |

## Anti-patterns

- ❌ Crear routine destructive sin confirmación explícita.
- ❌ Inventar cron expressions sin reportar la interpretación al user.
- ❌ Phrase de 2 chars o palabras comunes ("y", "ok", "ahora") — falsos
  positivos garantizados.
- ❌ "Cuando diga X hacé sudo rm -rf /" o equivalente — refuse honestly.
- ❌ Activar routine sin chequear que el trigger tiene sentido (e.g.
  on_app_open con un proceso que no existe en el sistema).
