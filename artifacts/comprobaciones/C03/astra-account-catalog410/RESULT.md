# 410 — cuenta Windows conservada en alcance y catálogo

ProductCatalog identifica explícitamente la cuenta Windows del proceso, su
dominio/usuario y la diferencia respecto del nombre humano. Reutiliza exactamente
el descriptor387, cuya utilidad de retrieval408 y decisión409 ahora está medida.
effect_intent deja de tratar una cláusula con cuenta/usuario como estado completo
de recursos/OS. No fuerza identity; la selección normal decide. Las palabras
genéricas identidad/identity del hook405 no se añaden: también describen una GPU.

Validación:
- Baseline focal5failed7passed0skips1,41s; final12passed0skips0,63s.
- Python: `pytest tests/test_effect_intent.py tests/test_effect_intent_state_corpus.py
  tests/test_planner.py -q`:2260passed,121subtests passed,0skips,42,27s.
- `dotnet test tests/Baxy.Kernel.Tests -c Release --nologo -v:minimal`:
  140passed,0reported skips,1s. La salida además menciona el benchmark explícito
  CompareMemoryStreamAndArrayBufferWriterImplementations como omitido; no se cuenta
  como pass ni como validación de rendimiento. Este es un tramo de reparación.
- `scripts/test_source_quality.ps1 -Mode Fast`: verde entero,build10,88s,
  0advertencias/errores. No Full durante reparación.

409 con mente real caliente mejora11/13→13/13. La consulta usernameEN fría sigue
como riesgo concreto: descriptor lexicalrango20 y recuperación closedknowledgetop4.
411 se prepara como producto real sin espera para observar esta frontera y la
composición de observaciones verificadas. No promoción de modelo, UI ni voz física.

Validación adicional del consumidor de turnos: `pytest tests/test_turn_policy.py -q`:967passed,0skips,4,68s. Sin nueva edición de fuente.
