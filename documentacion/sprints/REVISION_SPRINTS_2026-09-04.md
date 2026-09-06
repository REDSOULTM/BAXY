# Revisión de sprints — 2026-09-04

Encargo: revisar C03 en curso y todo lo pendiente para llegar a BAXY funcional
con Grok 4.6, considerando Granite 4.2 3B. Auditoría documental y de fronteras
de código; no ejecuta ni certifica C03. Base observada: `main`, `5f572ee`,
con WIP de Grok. No se modifica ese código, su matriz ni su checkpoint.

## Diagnóstico demostrado

1. **La aceptación histórica no acreditaba el producto integrado.** La
   [auditoría anterior](../AUDITORIA_GOALS_01_10_2026-09-03.md) reprodujo por UI
   seis entradas insatisfactorias: hora correcta en Core pero respuesta falsa;
   apertura incierta que capturaba chiste/red y sobrevivía a Nueva sesión.
   Sus cifras de voz y hardware también distinguían pruebas parciales de físicas.
   C01/C02 aportan ahora entrada compartida y base; no hay que reconstruirlas.
2. **C03 sí reparó causas reales.** [HERENCIA](../../artifacts/comprobaciones/C03/HERENCIA.md)
   identifica `utc`+offset frente a `localTime` artificial. El código observado
   `ModelMessageComposer.cs:104–157` reintenta los mismos hechos. Los informes
   R01/R07 acreditan muestras concretas de hora y agotamiento observable.
3. **Honestidad se confundió con utilidad.** El relevo C03, líneas 175–185 y
   390–400, excluye `composition_failed` de los huecos. CIEN registra Qwen
   cien-29: 70 finales/30 agotamientos; Granite cien-30: 86/14; cien-31: 88/12,
   además de finales incorrectos. Esas cifras NO son tasas de acierto.
4. **La reserva se contaminó.** El relevo, líneas 401–403, permite reutilizar
   v16 como fresca al cambiar GGUF/prompt. CIEN documenta v16 en cien-27…31.
   Es válida para comparación/desarrollo, nunca vuelve a estar reservada.
5. **La reparación se está convirtiendo en vocabulario del examen.**
   En el primer corte de código de esta auditoría:
   `UserMessagePolicy.cs:406–480` acumula rechazos; 484–498 enumera palabras;
   856–866 incluye planetas; 1473–1487 exige `hola` en **cualquier traducción al español**, no sólo
   `hello`. Por inspección, rechaza «buenas noches» para `good night`: no es
   necesario atribuir ese rechazo a la calidad del modelo.
   `llm.py:228–267` mezcla hechos con órdenes como «Welcome: Hola», red y
   comienzos prescritos. Esto es evidencia de reglas específicas; su daño
   cuantitativo necesita ablación controlada, no se supone. Un bloqueo de una
   respuesta falsa no prueba que pueda producirse una verdadera.
6. **El plan combate el contexto demasiado tarde.** Cxx permitía 350K antes
   de compactar; 10/11 imponían simultáneamente compactar y cerrar en una sola
   sesión. 10.7 concentra 1.083 filas/321 textos. Los contratos repetidos eran
   mayores que varios objetivos. Un relevo C03 tenía 426 líneas y copiaba su
   propio prompt: el siguiente agente heredaba instrucción y cronología mezcladas.
7. **El final dejaba producto pendiente.** El alcance difiere instalación,
   purge, hardware objetivo y firma; 11.16 terminaba en «listo para uso diario».
   Se añade fase 12 explícita para esos compromisos, sin ejecutarlos ahora.
8. **La matriz no es un certificado actual.** Hay CUMPLIDO de tres ceros
   basado en cien-11/16, aunque cien-31 informa reserva ficticia en Deimos y
   `Sigo con` en progreso. El agente C03 debe reconciliar las filas afectadas;
   esta auditoría no pisa la matriz que está editando.

Actualización de lectura durante la revisión: el checkpoint de Grok ya informa
cien-32, 88 publicados/12 agotamientos y NO SELLO; prepara cien-33. No se cancela
esa corrida desde aquí. El mensaje de replanteamiento exige reconciliar cualquier
resultado posterior antes de retomar. No se trata cien-31 como último estado vivo.

Segunda actualización, al cerrar la revisión el 2026-09-05: se leyeron también
`tramo-a-runtime.txt`, `tramo-a-traces.txt` y `disc-compare.md` completos. El
checkpoint informa A+B1–B15, disc-29/30 en vuelo, C03 EN_CURSO, sin Tramo C.
Los nuevos informes confirman reparaciones de rutas/vetos, pero `What will you
refuse` va pasando de rechazo invertido a RAM inventada, metadiscurso e identidad.
Eliminar cada expresión sin responder correctamente no demuestra mejora general.
Se exige contraste causal con casos nuevos antes de seguir sumando condiciones.
No hay que reiniciar A si la evidencia sigue vigente. Granite continúa por override;
la producción registrada sigue siendo Qwen según ese checkpoint.

## Documentación de agentes C03 leída

Se leyeron completos los diez documentos localizados por nombres versionados
y no versionados: `artifacts/comprobaciones/C03/`:
`HERENCIA.md`, `R01-R02.md`, `R06-R10.md`, `R07.md`, `RUTAS.md`, `CIEN.md`,
`baseline-c02/LAUNCH.md`, `ab-voice/COMPARE.md`, `ab-voice/COMPARE-NATIVE.md`;
y `Sprints comprobación/RELEVO_C03_2026-09-04.md`.
También contrato, protocolo, estado, relevo común, matriz original y prompts Cxx.
Se revisaron los objetivos/criterios de todos los pendientes 10.7–11.16, sus
mapas y la identidad. No se afirma haber leído los chats privados ni cada JSONL.
Los informes históricos son evidencia fechada; no se ejecutaron sus órdenes.

La lección ya estaba en
[Carter, secciones 3.1–3.4](../../biblioteca/carter/la-razon-de-carter/11_lecciones_v1_a_v4.md):
acumulación de routers/reescrituras y pruebas estructurales verdes con mala conducta.
Se hereda esa advertencia; no los samplers de otros modelos.

## Grok: fuentes y decisiones

Consulta oficial 2026-09-04 y `grok --version` local:
`grok 1.0.13 (5e9a58528b76)`; `--help` confirma `--reasoning-effort`,
`--resume`, `--restore-code` y modo single-turn.

- [Grok 4.6](https://docs.x.ai/developers/grok-4-6): contexto 500.000 y High
  disponible. La ficha no certifica que llenar esa ventana mantenga igual calidad.
- [Comandos](https://docs.x.ai/build/modes-and-commands): `/context`, `/compact`
  y `/new`. La herramienta de shell no equivale al cliente interactivo.
- [Compactación](https://docs.x.ai/developers/advanced-api-usage/context-compaction):
  debe ocurrir antes de exceder el contexto; se elige umbral según la carga.
- [CLI](https://docs.x.ai/build/cli/reference): configuración y reanudación.

No se encontró una receta oficial de programación «Grok 4.6 = prompt mágico».
No se usa la guía Realtime de voz como guía de código. Objetivo observable,
restricciones concretas, una causa por tramo, lectura acotada, prueba externa y
checkpoint son decisiones de ingeniería basadas en este historial. El objetivo
60–100K, corte a 150K y lotes pequeños son política conservadora, no benchmark
ni umbral científico de degradación. Se evalúan por criterios cerrados/contexto
consumido y fallos que reaparecen; no por cantidad de tokens gastados.

## Granite: conservar el candidato y verificar la integración

[Ficha IBM](https://huggingface.co/ibm-granite/granite-4.2-3b): recomienda
temperature 1.0, top_p 0.95 y muestreo; distingue thinking/non-thinking.
[GGUF oficial](https://huggingface.co/ibm-granite/granite-4.2-3b-GGUF):
Q4_K_M ronda 2,24 GB de archivo; eso no mide VRAM total con caché y voz.

La comparación nativa local informó 10/15 finales fieles de Granite frente
a 4/15 de Qwen, con defectos en ambos. Es indicio favorable al candidato pedido,
no prueba de superioridad general ni pase de C03. El checkpoint dice Qwen
registrado y Granite por override: verificar el manifiesto/proceso actual antes
de afirmar qué corre en la UI. No sustituir la elección del usuario por Qwen.

Auditar todas las llamadas del mismo GGUF, no sólo compose: `llm.py` conserva
temperature 0.0 en decisión/guardas/reintentos. No cambiar todos los valores a
ciegas: medir cada rol con su esquema, template, tokens, finish_reason y latencia;
cualquier desviación del perfil oficial se documenta con su prueba. No entrenar
con holdout, subir a 8B ni añadir otra mente para evitar reparar la integración.

## Cambio operativo

- [Contrato único](00_PROTOCOLO_EJECUCION.md): sustituye instrucciones duplicadas.
- C03 se trabaja en tramos A–D; los otros Cxx y 10/11 tienen cortes explícitos.
- Misma exigencia de producto, distinta unidad de trabajo. No se reinician C01/C02.
- [Mensaje para el Grok que está en C03](Sprints%20comprobación/07_REPLANTEAR_C03.md).
- [Lanzador vigente](00_LANZAR_DESDE_10_7.md): C03 → C09 → 10 → 11 → 12.

## Validación de esta revisión

- Pruebas dueñas: `test_goal095_09512_integrate.py`,
  `test_goal10_autonomous_campaign_docs.py` y `test_goal_launch_contracts.py`,
  con el Python 3.12 del manifiesto: **17 passed**. El launcher `py` apuntaba a Python
  3.13 sin pytest; se corrigió la selección del intérprete, sin instalar paquetes.
- 56 documentos propios: enlaces locales comprobados, **0 rotos**.
- 38 prompts pendientes: contrato común y tramos presentes; ninguna obligación
  de cerrar en una sesión ni presupuesto de trabajo de 350K. 97 filas originales
  conservadas; no se editó su matriz en curso.
- `git diff --check -- documentacion`: sin errores de whitespace.
- El primer Full detectó ocho contratos documentales obsoletos: contrato entero
  repetido, sesión única y cierre definitivo en 11.16. Se actualizaron las pruebas
  para comprobar la incorporación del contrato común, leyes/invariantes, cadena
  completa y aceptación instalada. El prompt vigente continúa de 11.16 a 12.1.
  No se cambiaron tests de conducta del producto ni se omitieron los fallidos.
- Un segundo Full aprobó .NET y los contratos nuevos, pero detectó dos fallos
  `wake_program_tree_changed`: una modificación accesoria del generador histórico
  alteraba el hash global que incluye todos los scripts. Se retiró esa modificación,
  conservando el generador cerrado de 09.5.12 y sus sellos; el linaje antiguo queda
  expresamente sustituido en 11.16. No se actualizan hashes de voz para aparentar
  una revalidación, ni se modifica el WIP ajeno de los evaluadores STT.
- Tras retirar el cambio accesorio: documentación + evaluadores STT en el
  checkout aislado, **29 passed / 0 failed / 1 skip**, y diff vacío en
  `src scripts main.py assets.manifest.json`. En el árbol vivo de Grok la misma
  comprobación devuelve **27 passed / 2 failed / 1 skip** por huellas STT.
  Ese estado ajeno queda para C03: reconciliar las dependencias del candidato y
  revalidar, sin reetiquetar evidencia histórica como si acabara de medirse.
- **Full verde, exit 0**, sobre checkout aislado de `5f572ee` + documentación y
  sus dos tests revisados, sin el WIP de C03. Estática y build Release verdes,
  0 warnings/0 errores de build.
  Comando: `./scripts/test_source_quality.ps1 -Mode Full`.
  Se usó `PYTEST_ADDOPTS=-rs` sólo para informar motivos de skips, sin filtros.
  Entorno: `%TEMP%/baxy-sprints-review-20260904/BAXY Definitivo`.
- .NET: **4.033 passed / 0 failed / 1 skip**. Desglose: Contracts 60,
  Integration 2.907, Kernel 138, Providers 451, Setup 477.
- Python: **8.790 passed / 0 failed / 11 skips ambientales**; además,
  433 subtests passed y 3 warnings de cálculo. Los skips corresponden a datos
  privados/ledgers, repositorio histórico, entradas blind y árbol WPF ausentes
  del checkout aislado. No acreditan esos criterios.
- [Log definitivo](../../artifacts/audit/sprints_20260904/full-final.log),
  [registro de validación y hashes](../../artifacts/audit/sprints_20260904/validation.json)
  y [relevo](../../artifacts/audit/sprints_20260904/HANDOFF.md).
  Se conservan también los dos logs diagnósticos. Los 57 archivos de entrada
  de prompts/contratos/tests coinciden con la copia validada; este informe y el
  relevo son metadatos de resultados completados después del gate.

Este Full valida la compatibilidad de la revisión documental con la base
publicada; **no certifica el código de C03 que Grok sigue modificando**. La UI,
la voz física y las campañas de aceptación no se ejecutaron en esta revisión.
Cambios guardados en el árbol compartido, sin commit/push de esta auditoría;
el WIP ajeno se conserva. La revisión de sprints queda terminada; C03 sigue abierto.
