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

Tools: `routine`, `notification`, `verify`. Honesty-critical: SÍ — nunca activar routines destructivas en silencio. Confirmar siempre antes de habilitar.

Usar cuando: "todas las mañanas a las 9 mostrame X", "cada hora chequeá Y", "cuando diga 'pomodoro' arrancá timer 25 min", "cuando abra Steam mutea", "todos los lunes hacé Z". Diferencia con `notification`: esa es one-shot (timer/alarm/reminder); `routine` es **recurrente** o **disparada por evento** (phrase/app_open). Si dice "recordame en 10 min algo" → usar `notification`, NO este skill.

## Steps

1. **Identificar el trigger** (3 tipos):
   - 1a. **Time-based (cron)** — "todas las mañanas a las 9", "cada hora", "los lunes": `trigger={"type":"cron","schedule":"0 9 * * *"}` (`0 * * * *`=cada hora, `0 9 * * 1`=lunes 9 AM). Si no estás 100% seguro del cron, decirle al usuario qué interpretaste antes de crear: "Voy a programarlo como `0 9 * * *` = todas las mañanas a las 9. ¿OK?"
   - 1b. **Phrase-triggered** — "cuando diga X haz Y": `trigger={"type":"on_phrase","phrase":"<keyword>"}` (case-insensitive, accent-folded). La phrase debe ser distintiva (≥3 chars). Confirmar: "Vas a poder activarlo diciendo '<phrase>'. ¿OK o querés cambiar el keyword?"
   - 1c. **Process-triggered** — "cuando abra X hacé Y": `trigger={"type":"on_app_open","process":"<exe.exe>","interval_minutes":2}` (o `on_app_close`; interval=polling).
2. **Definir los steps** (cada step = una tool call), ej. `steps=[{"tool":"audio","args":{"action":"mute","state":True}}, {"tool":"notification","args":{"action":"toast_now","title":"Muted","text":"..."}}]`. **Validar** que las tools existen y los args son correctos antes de crear — si la tool falla en runtime el usuario no se entera hasta el primer dispatch.
3. **Detectar si es destructive.** Si CUALQUIER step usa una tool destructive (filesystem.delete, registry.delete, terminal con comandos destructive), **NO crear sin confirmación explícita**: "Esta routine incluye un paso destructivo: `<tool.action>`. ¿Confirmás? Una vez activa se ejecuta automáticamente sin nuevas preguntas. (sí/no)". Esperar al próximo turn.
4. **Crear.** `routine(action="create", label="<descriptive name>", trigger=<dict>, steps=<list>, enabled=True)`. Si trigger es `on_phrase` y algún step es destructive, **pasar** `confirmed_at_create=True` solo si el usuario explícitamente confirmó.
5. **Verificar y reportar.** `routine(action="list")` → confirmar que aparece con `enabled=True`. Reportar: "Creada la routine `<label>`: Trigger [human-readable]; Steps [N pasos, tools usadas]; Próxima ejecución [si time-based, next fire time]. Podés desactivarla con `routine(action="disable", id=<id>)`."

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
- ❌ Phrase de 2 chars o palabras comunes ("y", "ok", "ahora") — falsos positivos garantizados.
- ❌ "Cuando diga X hacé sudo rm -rf /" o equivalente — refuse honestly.
- ❌ Activar routine sin chequear que el trigger tiene sentido (ej. on_app_open con un proceso que no existe).
