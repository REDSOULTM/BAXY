# Frontera Codex → Fable — Goal de la base determinista (v3)

Estado: **contrato vigente; cuerpo determinista cerrado**. Fecha: 2026-07-15.

Este documento define hasta dónde llega Codex (el **cuerpo** determinista de BAXY 1.0)
y qué queda para Fable (la **mente**: IA, tools, voz). Codex debe tratarlo como
directiva de alcance: qué cerrar, qué no empezar, qué dejar preparado y cuándo
detenerse.

## Misión

Entregar el **cuerpo** de BAXY 1.0 — producto local Windows, instalable, utilizable,
confiable y terminado en todo lo **determinista y verificable** — conforme a
`BAXY_GPT56_ULTRA_PROMPT.md` y al corpus histórico congelado. Solo español /
inglés / espanglish. **Detenerse justo antes de la IA.** Resolver **solo
bloqueantes reales**, con la solución **más simple** que cierre el gate.

## Regla de entorno (equipo limpio del usuario)

Las pruebas que requieren un **equipo/perfil limpio** — instalación desde cero,
**purga destructiva** de datos, y `app.open` sin procesos preexistentes — quedan
**APLAZADAS**. El usuario las correrá más tarde con un equipo limpio al lado.

- **No bloquear el avance por ellas.** Marcarlas `pendiente-por-entorno
  (esperando equipo limpio del usuario)` y **seguir con lo que sí se puede cerrar
  en la máquina actual.**
- **Prohibido reintentarlas en bucle**, inventar rodeos, o tocar/borrar datos
  BAXY preexistentes para forzarlas.
- Dejar cada una **lista para ejecutarse en un solo paso** (script/checklist
  preparado) cuando llegue el equipo limpio, y avisar que quedó a la espera.

## Regla de proporcionalidad

1. La solución más simple que cierra el gate, gana. Primitiva de Windows
   (`MoveFileEx`, `RunOnce`, DPAPI, ZIP Stored) antes que un subsistema propio
   con coordinator/worker/journal.
2. Un gate verde está **TERMINADO**. Prohibido reabrirlo para "endurecerlo más".
   Se pasa al siguiente gate pendiente.
3. Nada de robustez especulativa. Un modo de fallo se maneja solo si (a) lo exige
   un mensaje del corpus congelado o (b) lo encontró una regresión/auditoría real.
   No se inventan casos límite hipotéticos.
4. Ningún subsistema nuevo sin un test rojo que venga de un requisito real.
5. Techo de complejidad: si una pieza determinista supera ~1.500 líneas, es alarma
   de sobre-ingeniería — se detiene y se simplifica antes de seguir. Anti-patrón
   exacto a NO repetir: el desinstalador de ~9.800 líneas en 18 archivos.

**Bloqueante real** = algo que falla un gate Must o un P0/P1 documentado. Un
"¿y si...?" sin mensaje del corpus ni regresión detrás **no es bloqueante** — es
sobre-ingeniería y está prohibido.

## Codex DEBE cerrar AHORA (no depende de equipo limpio)

1. **GUI fiel (gate 11):** diagnosticar y cerrar el **rojo actual** de la captura
   de nota (operación vs proyección de respuesta vs observación UIA) y la
   fidelidad integral. Corre con raíz de datos aislada — no necesita equipo limpio.
2. **Memoria (gate 10, techo determinista):** cerrar el endurecimiento que el
   corpus exija (HMAC del journal ya está). Nada más.
3. **Artefacto + checksum del gate 14** reconstruido desde el HEAD limpio actual
   (la parte reproducible, **sin** la instalación física).

## Catálogo CONGELADO — no más operaciones nuevas

El catálogo queda **congelado en las ~22 operaciones actuales** (notas, apps,
estado de sistema, GPU, audio, memoria). **Codex NO agrega familias de operación
nuevas.** Las 22 ya prueban el patrón del cuerpo; no hace falta más para la base.

- La cobertura del resto del ledger (gate 4, "cero casos solucionables omitidos")
  es de **Fable**, vía el cerebro de embeddings — **no** de Codex vía más cortes
  de regex. El gate 4 completo necesita entender intención de verdad y queda
  abierto como frontera Codex→Fable.
- Motivo doble: (a) Codex nunca cierra el gate 4 sumando operaciones de a una —
  solo llega a un techo difuso; (b) cada operación nueva son más frases de regex
  = más deuda contra la ley de no-keywords que Fable después tiene que limpiar.
- "Agotar el ledger determinista" = **las 22 que existen, congeladas.** No es un
  número a expandir.

## Codex DEJA LISTO PERO NO EJECUTA (aplazado a equipo limpio)

- **Gate 14:** instalación desde cero + **purga** keep/purge en cuenta/VM
  desechable. El tramo keep-data same-host ya pasó; falta solo lo destructivo.
- **Gate 13 / `app.open`:** correr con un entorno sin procesos preexistentes.
- Preparar script/checklist de un paso para ambos.

## Codex NO debe empezar (es de Fable)

- Embeddings / detección de intención por forma.
- Conversación general.
- Tool-calling inteligente o planner que componga misiones.
- Runtimes de modelos y motores STT/TTS reales.

## Cuatro costuras a dejar limpias (protegidas por test de arquitectura)

1. **Entrada de intención:** `texto → operación tipada`. El router regex es
   relleno **interino declarado**; ninguna frase de idioma fuera de la capa de
   parser. Fable lo reemplaza por embeddings multilingües.
2. **Salida de respuesta:** `resultado tipado → lenguaje natural` en una capa
   aparte; ningún texto de respuesta hardcodeado en los handlers.
3. **Catálogo = superficie de tools:** el `OperationRegistry` se mantiene como
   registro limpio (nombre + schema + riesgo + verificador).
4. **Frontera de sidecar:** JSONL local + Job Object lista para un **segundo
   sidecar** (runtime de modelos en Python), no solo el core.

## Voz

Puerta única de entrada de misión para texto y voz — ya construida como
`MissionInput` con fuente `VoiceTranscript`. **No cablear STT/TTS.** Fable conecta
el motor a esa puerta.

## Límite honesto

La base topa en **~10/15 Must**. Los gates **7 (voz al cerebro), 9 (conversación
general) y 12 (medición 4 GB VRAM)** son de Fable y quedan abiertos a propósito,
marcados como frontera Codex→Fable. Los aplazados por entorno (partes de 13/14)
**no se fingen cerrados** — se marcan `pendiente-por-entorno`. No fingir cobertura.

## Cierre ejecutado por Codex

El corte funcional `78169ad` congeló exactamente 22 operaciones de producto y
21 tools públicas; `app.status` permanece interno. El saludo publica, en orden,
nombre, schema cerrado, riesgo, contrato verificador y descripción, y la GUI
rechaza cualquier diferencia.

Las cuatro costuras quedan protegidas por prueba:

1. `MissionInput` lleva `Text` y `VoiceTranscript` por una sola ruta; un
   centinela impide que las regex de idioma salgan de la capa interina declarada.
2. `OperationOutcome` es tipado y no contiene el mensaje público; handlers y
   replay delegan la verbalización a un narrador separado.
3. `OperationRegistry` expone 22 definiciones internas y 21 descriptores de tool
   completos, sin exportar `app.status`.
4. El core usa un host JSONL configurable y reutilizable, con UTF-8 estricto y
   Job Object kill-on-close por sidecar; dos procesos independientes acreditan
   la frontera prevista para un futuro runtime Python.

La solución completa pasó 1.787 pruebas .NET estándar, con cero fallos y cero
P0/P1. La evidencia reproducible está en
`artifacts/product/architecture_seams_gate.json`. No se añadió STT, TTS,
embeddings, planner, conversación general ni runtime de modelos.

El HEAD limpio `455243c` produjo además el release 1.0.1 A/B reproducible y el
predecesor 1.0.0. La evidencia `artifacts/setup/final_release_gate.json` liga
producto, ZIP, Setup, checksums y smoke NativeAOT. No ejecuta ni sustituye los
dos recorridos aplazados de perfil limpio.

## Regla de parada

Cuando esté cerrado todo lo que **no depende de equipo limpio** (gates 10, 11, y
las partes no-físicas de 13/14/15), con el **catálogo congelado en las 22
operaciones** (sin agregar familias nuevas): **detenerse.** No profundizar nada
que ya pase, no agregar operaciones. Reportar qué quedó `pendiente-por-entorno`
esperando el equipo limpio del usuario, y ceder a Fable.
