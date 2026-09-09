# C03 — 416 validado; producto417 8/9; 418 validado;419 cortado por RAM;420 preparado — EN_CURSO

Goal completo activo. Goal-c03 / HEAD 2bf3d4c. Preservar WIP, main y evidencia.
Sin agentes, commit/push ni Full durante reparación. BAXY manual cerrado; sólo
la encuesta permanece (PID 101140, padre 29800). No hay modelo/producto activo.
Mensajes directos 16 y encuesta 742/rev1248 consolidados; automáticos excluidos.

Fuente última adoptada 410: alcance cuenta/recursos y descripción del catálogo.
12 focales, 2260 Python +121 subtests, Kernel 140; Fast verde; turn_policy 967
pass/0 skips (4,68 s). Benchmark explícito omitido por Kernel no cuenta como pass.
Memoria fuente 402/404 conservada. Evidencia en astra-account-catalog410.

Producto411: 4/6 útiles; cuenta EN fría sí funciona. T3 vuelve a pedir permiso
para leer cuenta; T5 confunde Windows 11 con Windows 10. Modelos cerrados.
412 no reproduce por omitir bienvenida. 413 sí reproduce (payload por PID):
recuperar lectura antes de guardas mejora 13/15→14/15, pero recita cuenta en warm.
414 filtra read_only antes del top4: 14/15→14/15, corrige warm y rompe cold.
Ambos rechazados para adopción; no duplicar pases ni combinar por frío/caliente.
Ver astra-read-recovery413 y astra-read-candidates414/RESULT.md. Historia para
reproducir siempre desde HTTP nativo: activity omite bienvenida automática.

415 composición iguala payload real411. Sólo observed.os.caption mejora 1/4→4/4
casos útiles (Windows 11 ES/EN, Windows 10, Server 2022). RESULT/PINS completos.
GPU 3171,56 MiB/RAM 3623,17 MiB, sólo composición; no acredita voz conjunta.
416 sustituye Rtl por CIM local con runner existente (5 s y cancelación);
Caption obligatorio hasta resultado verificado. 36 proveedor/193 integración,
0 skips; Fast verde/build18,76 s/0 warnings/errors. Pruebas de cancelación,
fallo parcial y dato inválido. CIM real 0,354–0,415 s; no modelo/voz medidos.
RESULT/PINS en astra-os-provider416. Producto417 cerrado y documentado: 8/9
útiles, mismos seis411 4/6→5/6 más tres controles correctos. Windows 11 ES/EN,
RAM y CPU bien. Account T3 sigue aclarando innecesariamente. 9 finales/admisiones
200, sin timeout/silencio. No UI/voz ni VRAM medida; RAM libre T8 sólo206 MiB,
comprobar memoria disponible antes del próximo modelo. Manifiesto intacto.
418 corrige MainWindowViewModel: una ruta/contrato privado reconocido limpia
la aclaración pública anterior; NoRoute/AskToSave siguen por mente. Seis pruebas
focales pasan, 0 skips/26 s, incluidos faltar nombre→cancelar sin escribir.
Baseline reprodujo dos llamadas mentales extra y ausencia de lectura; también
hubo defectos de fixture (journal compartido/outbox inexistente), ya corregidos.
Owners 2007 pass/0 skips reportados/6m51, más gate runtime explícito omitido
(no cuenta). Fast verde/build18,01 s/0 warnings/errors. RESULT/PINS418 completos. Producto419 se detuvo por RAM libre<768 MiB durante arranque, cero turnos,
GPU3167,56 MiB/RAMárbol3543,67 MiB/61,157s. No resultado semántico. RESULT/PINS419.
Modelo/producto cerrados; cuatro workers AOT restantes cerrados por ambos SDK.
RAM libre después5485224 KiB. Encuesta intacta.420 preparado, aún no ejecutado:
runtime Python -X utf8 scratchpad/c03-private-product420.py. Misma fuente418,
ocho casos419 y mismos límites; Core ya publicado, sin nueva compilación esperada.
Si vuelve a cortarse sin build, investigar RAM del runtime; no bajar el margen.
No nueva fuente420. La hipótesis de actor/first-person impuesto a memory.recall
se refutó leyendo RequiredBaxyActions: los hechos estructurados devuelven [].
Provenance349 ya añadió source=explicit user y no corrigió sujeto; no repetirlo.
NaturalMemoryRequestParser conserva brazos literales junto a patrones genéricos;
verificar alcance/reachability antes de atribuirles un fallo o retirarlos.


Pendiente: account T3, memoria ES/redactada, falsa persistencia al presentarse,
precedencia aclaración MainWindow671, ocho rutas y encuesta/fallos264. Cero
requisitos finales certificados y 0/100 frescos de aceptación. Quedan averías,
UI real/voz física/ASR/wake/≤4 GB conjunto, runtime/instalación/contratos C04–C09,
Full final verde y publicación. Sin bloqueo externo; no porcentaje ni ETA.
