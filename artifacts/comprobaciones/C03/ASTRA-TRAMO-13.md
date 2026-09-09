# C03 — tramo13: lectura personal y errores honestos

Estado EN_CURSO, rama Goal-c03, main y registro Granite intactos. Sin Full final,
sin cien frescos, sin promoción de modelo ni commit de esta tanda.

## Causas y cambios

Una pregunta como What is on my to do list? seleccionaba task.list correctamente.
Primero effect_intent convertía la pista sintáctica de definición what-is en veto
compound vacío. Se separó esa pista de restricciones explícitas (no tools, negación,
traducción, cómo hacer); el reconocedor conserva su abstención y las restricciones
reales conservan el veto. Después la captura personal-read descubrió otro owner:
MainWindowViewModel convertía la acción válida en conversación por la misma forma
interrogativa. Se retiró ese bloque duplicado y se usan los handlers tipados existentes.

RecoveryFailureCode conserva las tres causas de recuperación ya emitidas por sidecar;
shell publica error con operationAttempted=false/retryable y limpia aclaración, en
lugar de pedir una respuesta de conocimiento sin datos. Control de idioma contrario
de compose compartido con chat regular, usando evidencia existente del reader;
nombre neutral Lima sigue permitido. No certifica la ruta contextual temprana.

Se retiró Mention every step once del resumen: los precursores internos siguen como
evidencia ordenada sin exigir narrarlos. El modelo aún narra se resolvió en captura;
no se declara resuelta esa calidad. Pins actuales V8/STT reseñados en CHECKPOINT.

## Validación

- tests/test_turn_policy.py + tests/test_effect_intent.py:2337pass.
- C03/compose/goal06voice tras idioma y recovery:107pass.
- C03/compose/V8/STT último estado:113pass/1skip ambiental.
- .NET owner MindShellEndToEnd/C03facts/MindPlanSession:35pass/1fallo del fixture
  nuevo, que no devolvía argumentos de task.list. Reparación limitada al fixture;
  recheck lectura personal y continuidad después de error:2pass. Format exit0.
- Logs: scratchpad/c03-personal-shell-dotnet.log, c03-personal-shell-recheck.log,
  c03-personal-shell-python.log, c03-personal-shell-format.log.

## Modelo real

personal-shell: Qwen3-4B-Instruct-2507-Q4_K_M heredado,21publicados/21 en61.25s,
GPU3497.56MiB, RAM5490.62MiB. Registro sin cambios. t16 ahora ejecuta task.list real
y responde fielmente que la lista del perfil aislado está vacía. Cierre de ventana
propia confirmado y verificado PID2672/journalsequence28; continuidad posterior.
No cien frescos: se repitió el conjunto de desarrollo para contrastar el arreglo.

Persisten spanglish t5/t6/t15; t18 añade un estado pendiente del proceso no acreditado;
algunas explicaciones usan analogías confusas. Falta alias natural Calculadora,
contraste de incertidumbre/recuperación R07, candidato registrado sin overrides,
cien nuevos adjudicados, UI real y Full final. No bloqueo externo.
