# BAXY — por qué se tiran las respuestas que ya eran correctas

Eres el agente responsable de BAXY, en `D:\BAXY\source`, rama
`codex/baxy-portable-structure`. Lee **`goal.md`** entero antes de tocar nada; su
disciplina de medición sigue vigente completa.

**Voz, wake word y STT quedan fuera de tu alcance.** Con eso fuera el §7 no puede
declararse cumplido: dilo en cada informe.

---

## 0. Primero: sube la rama

Los 319 commits de esta rama existen **en un solo disco**. `git branch -a` no
lista `remotes/origin/codex/baxy-portable-structure`: nunca se ha subido.

```
git push -u origin codex/baxy-portable-structure
```

**No hagas merge ni abras PR contra `main`.** `git merge-base origin/main HEAD`
devuelve **vacío**: son historias no relacionadas. `origin/main` es el proyecto
antiguo —último commit 2026-06-20— y esta rama es la reconstrucción limpia que la
meta ordena re-derivar en vez de portar. Fusionarlas mezclaría dos proyectos
distintos. Sube la rama y nada más.

Si el push falla por credenciales, **para y dilo**; no inventes alternativas ni
reescribas historia.

---

## 1. El trabajo: partir por causa las respuestas correctas que se descartan

V8 está **consumido y en FAIL**. No lo reabras, no lo recalcules, no lo puntúes
de nuevo. Todo lo que necesitas ya está publicado.

### La observación de partida

La tabla fila por fila de **R137** —auditoría manual de las 21 filas servibles de
V8— contiene seis filas con esta forma:

| Fila | Esperada / propuesta cruda / final |
|---|---|
| `v8-srv-01-mix` | `system.time` / `system.time` / vacío |
| `v8-srv-03-en` | `system.status` / `system.status` / vacío |
| `v8-srv-03-mix` | `system.status` / `system.status` / vacío |
| `v8-mach-02-es` | `system.time` / `system.time` / vacío |
| `v8-mach-02-en` | `system.time` / `system.time` / vacío |
| `v8-mach-02-mix` | `system.time` / `system.time` / vacío |

La recuperación encontró la operación correcta **y** la decisión la eligió bien,
y el turno acabó vacío. Las notas de R137 lo describen como «el veto retira la
propuesta correcta», «propuesta correcta retirada y negativa falsa» y «la
pregunta final es una paráfrasis exacta».

**Verifica esa lectura tú mismo antes de construir sobre ella.** Es la conclusión
de otro agente sobre una tabla, no un recibo. Puede estar mal contada.

### Lo que hay que medir

V8 publicó **23 vetos `domain_grounding`**, **7 `total_recovery`** y **1
`compound_conservation`**. Nadie ha cruzado esos vetos con la corrección de la
propuesta que retiraron.

Produce, sobre las filas ya publicadas, un reparto por causa que responda:

1. De los 31 vetos, **cuántos cayeron sobre una propuesta cruda que era la
   operación esperada**, y cuántos sobre una equivocada. Un veto que retira una
   propuesta equivocada está haciendo su trabajo; sólo el otro caso es daño.
2. Para cada veto que retiró una propuesta correcta: **qué condición exacta lo
   disparó**, con la rama de código identificada.
3. Cuántas filas acabaron en **aclaración inútil** —una pregunta que sólo
   reformula la petición sin pedir un dato ausente— en vez de en veto, y si esa
   aclaración vino después de una propuesta correcta.
4. El total honesto: **si el tramo posterior a la decisión no descartara
   respuestas correctas, cuántas de las 21 servibles se habrían servido.**

Fuentes: `artifacts/holdout/veto_reach_v8.json`,
`veto_reach_v8.telemetry.jsonl`, `veto_reach_v8.turn-audit.jsonl`,
`veto_reach_v8.raw-replies.jsonl`, y la tabla de R137 en el registro.

### Prepárate para que el resultado sea el contrario

Es posible que esos vetos tuvieran razón: una propuesta puede coincidir con la
etiqueta esperada y aun así ser incorrecta en su contexto —argumentos ausentes,
riesgo no confirmado, dispositivo equivocado—. **Si la medición dice que los
vetos estaban bien, publícalo igual y cierra la línea.** Un rechazo con mecanismo
entendido vale tanto como una reparación; lo que no vale es un número que
confirme lo que ya se esperaba.

### Sólo si el daño es real

Entonces, y sólo entonces, propón la reparación — y antes de adoptarla:

- **Tásala contra lo que hoy funciona**, no sólo contra las filas que fallan. Una
  regla derivada de los casos rotos y comprobada sólo ahí siempre parece gratis.
- **Di qué población podría haberla refutado.** Un cero sobre un corpus que no
  puede contener el fallo no es evidencia de seguridad.
- Recuerda que estos vetos existen porque hubo efectos no solicitados. V8 cerró
  con **0 efectos no solicitados, 0 éxitos no verificados y 0 efectos externos**.
  Cualquier relajación tiene que demostrar que **no** reabre esos tres ceros.

---

## 2. V9 sigue reservado

**No construyas ni selles V9.** V8 se gastó y además dejó de acreditar el árbol
actual porque se editó un test después de consumirlo. V9 es la única bala que
queda para reclamar una mejora, y esta tanda es medición sobre filas ya
publicadas: no la necesita.

Si tu reparación resulta promocionable, **deja V9 preparado pero sin abrir** y
dilo en el informe. Cuando llegue el momento: scorer y código de medición
cerrados y hasheados **antes** de sellar, ninguna edición posterior de ningún
tipo, preinscripción que declare qué confirma y qué espera que siga fallando sin
predecir ambos, ninguna superficie reutilizada de V1–V8, y auditoría manual del
texto visible prevista desde el diseño porque el scorer de V8 se equivocó en 3 de
4 en el único criterio que se revisó.

---

## Mecánica de la máquina

- Compuerta: `.\scripts\test_source_quality.ps1 -Mode Full`, **verde antes y
  después de cada tanda**.
- Ejecutar y pytest: `%LOCALAPPDATA%\BAXYRuntime\python\mind-runtime-v1` con
  `PYTHONPATH=D:\BAXY\source\src`.
- Ruff: `%LOCALAPPDATA%\BAXYQuality\source-quality-v1`. **No es el mismo
  intérprete** y no tiene pytest.
- Tras cualquier cambio en `src/baxy_mind`, `scripts` o
  `experiments/voice_latency`, **re-pinea** las cinco constantes
  `EXPECTED_PROGRAM_TREE_SHA256` en `experiments/stt_quality/`, o la compuerta se
  pone roja en `tests/test_stt_quality_evaluators.py`. Comprueba al acabar que el
  pin sigue donde lo dejaste.
- **Sellos ciegos consumidos: V1–V8.**
- El registro va por **R143**; tu entrada es **R144**. Actualiza también
  `artifacts/fixes/integral_review_ledger_20260811.json`, con **29** defectos
  abiertos al empezar.

## Cómo trabajas

Autoridad total. Decide, ejecuta, mide, **publica también lo negativo**. No
cierres ningún defecto aparcándolo: lo despriorizado sigue **abierto y contado**.

Commits coherentes al terminar, en esta rama, sin reescribir historia.

Reporta con `Ritmo | Progreso | Errores | Falsos positivos | Tiempo restante`,
una línea humana y **una frase sobre qué puede hacer hoy una persona que ayer no
podía**. Si no puedes escribirla, dilo: significa que la tanda no movió el
bloqueante, y eso también es un resultado.

**El porcentaje sólo se mueve con evidencia**, y baja cuando la evidencia muestre
que algo que contabas no estaba cerrado.
