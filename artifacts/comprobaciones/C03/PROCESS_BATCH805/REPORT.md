# Procesos805 — 37 de 50 válidos; categoría abierta

La raíz leyó los 50 finales contra sus observaciones nuevas y los criterios congelados del panel795. Se completaron los 50 en una sola corrida, con 37 válidos y 13 fallidos. No se adopta todavía la fuente800/802/804: mejora las listas y recupera casos, pero pierde cuatro respuestas válidas frente801. Los veredictos anteriores quedan intactos.

| Grupo | Válidos | Fallidos |
|---|---:|---:|
| Listas | 10 | 1 |
| Conteos | 12 | 0 |
| CPU | 8 | 3 |
| Memoria de procesos | 5 | 6 |
| Recurso no especificado | 2 | 2 |
| Memoria de aplicaciones | 0 | 1 |

La diferencia804 reutiliza el selector C# existente de inventarios densos para procesos. Conserva los presupuestos existentes, Python802, modelo, perfil y límites. Respecto803 hay 12 ganancias y 3 pérdidas; respecto801, 6 ganancias y 4 pérdidas. No se interpreta una cifra neta como ausencia de regresiones.

| Medición de turno | 805 | 803 (9+41) |
|---|---:|---:|
| Mediana, todos | 4,394 s | 7,675 s |
| Mediana de listas | 5,119 s | 30,817 s |
| Mediana de conteos | 2,991 s | 4,627 s |
| Percentil95, todos | 7,118 s | 31,084 s |
| Máximo | 29,626 s | 31,552 s |

Intervalo entre primer y último evento de cada turno; no latencia acústica.803 excluye su intento interrumpido.805 duró265,078s; VRAM3497,56MiB y RAMresidente2392,75MiB, separadas; cero infracciones de recursos. Conductor sin UI visible ni voz: no acredita pico conjunto ni experiencia de escritorio.

## Fallos conservados

- **H0364**: CPU por intervalo, cinco PIDs y porcentajes mostrados correctos, pero la lista omite cinco de las diez filas devueltas y afirma que se devolvieron10 sin explicar el recorte visible.

- **H0650**: Top5, cinco instancias y valoresMB correctos, con límite5de158; distingue dosChatGPT pero omite todos losPIDs, exigidos por el criterio de identidad de memoria sellado.

- **H0669**: Declara memoria y los tres valores/PIDs visibles son correctos, pero muestra3de10filas mientras afirma que se devolvieron10. No explica ese recorte; no es la lista devuelta completa.

- **H0675**: Afirma una app ganadora a partir del working set de un proceso sin membresía ni agregación. Además llama-server744,39MB ni siquiera encabeza la lectura individual: python883,82MB está antes.

- **process795-list-04**: Los diez nombres/PIDs son correctos y declara158observados accesibles, pero no identifica el límite de la lista devuelta ni explica que sólo presenta una muestra. Falta el alcance parcial exigido por el criterio sellado.

- **process795-memory_rank-02**: Ganador individual y883,92MB correctos, pero faltaPID16132 requerido por el criterio de identidad de memoria sellado.

- **process795-memory_rank-03**: Cinco filas/valoresMB correctos y dosChatGPT separados, pero no muestra ninguno de losPIDs exigidos, aunque dice que son distintos.

- **process795-memory_rank-04**: Conserva diezPIDs y valores, pero ordenaChatGPT397,09MB antes de codex481,81MB, contradiciendo el orden por consumo solicitado.

- **process795-memory_rank-05**: Dos procesos y883,92/747,47MB correctos con alcance; faltan ambosPIDs exigidos por el criterio de memoria.

- **process795-memory_rank-08**: Termina composition_failed/no_response tras seis vetos internal_code. Hay datos y borrador factual, pero accessible_processes reaparece y no llega respuesta útil al usuario.

- **process795-cpu_rank-05**: Muestra tresprocesos conPIDs y porcentajes correctos pero afirma que se mostraron10. Siete filas observadas quedan fuera sin explicación.

- **process795-cpu_rank-06**: Tresinstancias y porcentajes correctos, pero afirma que10se devuelven en la lista aunque sólo nombra3. No conserva la lista observada.

- **process795-unspecified_rank-01**: Declara memoria y la frase final da el ganador y siguientes correctos, pero sólo presenta3de10filas sin identificar ese recorte al afirmar10devueltas. El límite visible queda ambiguo.

El caso memory_rank-08 conserva seis vetos por copiar el código interno del alcance, hasta quedar sin respuesta. La siguiente reparación proyectará ese dato mediante la pieza existente antes de entregarlo al modelo. La fidelidad de filas/PIDs/orden se prepara aparte; cada propuesta se medirá por separado. No se añade el checker de identidad descartado ni se relaja el criterio sellado.

## Evidencia y límites

ROOT_ADJUDICATION.json conserva los 50 juicios raíz, comparaciones y hashes de evidencia. VERIFICATION_STATUS.json mantiene los nueve requisitos históricos abiertos y cero crédito nuevo. Literales, payloads y razonamientos completos: C:/Users/usuario/AppData/Local/BAXY/C03-process-batch805-private/RESPUESTAS_ADJUDICADAS.md. EXIT.json es éxito de ejecución, no adjudicación; el juicio está separado.

Full804 repetición1 exit0: Python12714pass/3skips/466subtests/603,40s; .NET4642pass/1omisión agregada, con16omisiones optativas impresas (no se suman como categorías disjuntas). Release4,58s,0advertencias/errores;28pins intactos. Primer Full rojo y reparación exacta de saltos de línea conservados. Ninguna omisión cuenta como pass.

Encuesta28cubiertos/714abiertos/0noaplican; matriz3cumplidas/5contradichas/3pendientes. C03 EN_CURSO: faltan demás categorías, ocho rutas, aceptación100, recuperación, UI/audio y Full final. BAXY permanece cerrado para uso manual.
