# Diagnóstico causal acotado — process795-count-07 / t25, batch813

El primer veto determinable de la prosa publicada por la mente es **léxico en Baxy.App**, no un rechazo factual del Core: `UserMessagePolicy.ContainsInternalCode` devuelve true por el substring **`current context`** (`src/Baxy.App/UserMessagePolicy.cs:1518`). `ModelResponseRejectionReason` lo convierte en `internal_code` en las líneas 287–295. Es un **falso positivo de código interno**: aquí la expresión describe el alcance de una observación, no identifica protocolo ni una instrucción interna. Esto no declara correcta la respuesta completa ni cambia la adjudicación de la categoría.

## Evidencia del turno y primera frontera

- Evidencia exacta: `C:/Users/usuario/AppData/Local/BAXY/C03-process-batch813-private/review.json`, caso en línea 5433; terminal en 5440–5446; primera composición en 5575–5603. Petición: `Count the running processes.` Operación: `system.process.list`.
- Primera prosa (línea 5603): “146 running processes were observed within the accessible scope during this observation. The list includes all processes visible in the current context, and no additional processes were found beyond the observation scope.” SHA256 registrado: `dfbc7341a5cc390f5fafdb50972af70789bd815c4f0393e263eff8e80d2b0ff3`.
- `stage=first`, `published=true`, `reason=""`, `finish_reason=stop`: la mente entregó esa prosa. Hay seis composiciones de operación con el mismo hash; se intercala una composición de estado de trabajo. El flag de la mente no acredita aceptación por la App.
- `ModelMessageComposer.cs:147–170` recibe el texto y llama a `AcceptPublishedConversation`; esta llama a `AcceptModelAuthoredResponse` (211–224), que consulta `ModelResponseRejectionReason` (`UserMessagePolicy.cs:472–481`).
- La copia léxica elimina sólo nombres observados (`UserMessagePolicy.cs:276`, `ObservedResponseLiterals.cs:9–25,51–76`). Ningún nombre de proceso de t25 coincide con `current context`, por lo que no desaparece. Los predicados anteriores del grupo de líneas 287–291 no coinciden: no hay pregunta/petición de campo, frase de definición, palabra consecutiva duplicada ni atribución de petición a tercera persona (988–1003,1152–1174,1197–1211,1616–1625).
- `ContainsInternalCode` pliega el texto y aplica `.Contains("current context", StringComparison.Ordinal)` (1442–1518). Es incondicional respecto de los hechos y no usa la completitud del PC. Las exenciones de identificadores del usuario sólo afectan a formas de código, no a este literal (1447–1454). No se ve una reescritura de la prosa que origine el defecto: el literal ya está en el primer draft.

## Por qué termina composition_failed

`ModelMessageComposer.cs:179–208` repite la composición con los mismos hechos y concatena los dos rechazos como `internal_code;recovery:internal_code`. `PendingModelMessageQueue.cs:15,168–178` tiene un máximo de tres intentos; con texto nulo añade `;retry_exhausted`. Los seis drafts de operación idénticos y el terminal registrado son coherentes con tres pares original/recovery. No hay indicio de timeout: el terminal registra `timedOut=false`, admisión 200. No se atribuye al Core el ownership del veto por aparecer dentro de la trayectoria del producto.

## Distinción factual que impide dar por buena la respuesta completa

La primera frase conserva el conteo de **146 instancias accesibles observadas**. El snapshot contiene **10 filas devueltas** y `observationScope=accessible_processes`; no establece completitud del PC. El payload de composición declara expresamente que dicha completitud no está establecida.

La afirmación “no additional processes were found beyond the observation scope” excede esa evidencia: no se observó fuera del alcance. “The list includes all processes visible…” tampoco está sustentada como descripción de las diez filas devueltas. Por tanto, **falso veto internal_code no equivale a respuesta íntegramente válida**. El código causal localizado no está comprobando esas afirmaciones. Este diagnóstico no añade ni recomienda una nueva capa/checker y no regradúa el panel ni la raíz.

## Relación con la proyección812 y límite de la conclusión

`measurement_prose_projection.py:79–108` convierte el enum de alcance en prosa y, ante `Count the running processes.`, conserva sólo `observedProcessCount` y `observationScope`. Eso coincide con el payload registrado. La divergencia demostrada es que la mente acepta la prosa y la App mantiene el veto literal `current context`. No se demuestra que812 introdujera ese veto ni que un contrato obligatorio antiguo de filas/PID cause t25. De hecho, `RequiredStructuredLiterals` (`UserMessagePolicy.cs:2540–2613`) no exige esos datos para esta operación, y los vetos de hechos posteriores (372–378) ni siquiera se alcanzan después del `internal_code`.

Lectura en dos pasadas: localizar primera frontera; verificar precedencia, repetición y sellos. SHA256 actuales de `UserMessagePolicy.cs`, `ModelMessageComposer.cs`, `PendingModelMessageQueue.cs`, `measurement_prose_projection.py` y `llm.py` coinciden con `PROCESS_BATCH813/PREREG.json.sources` (prerregistro con HEAD `2bb04ef4a3951f4862f2ba41697da0c6b28a1919`). No se ejecutó runtime, inferencia, pruebas, build ni Full; no se modificó fuente canónica. La evidencia consultada basta para este mecanismo determinista; no se recorrieron logs privados ni otras corridas.