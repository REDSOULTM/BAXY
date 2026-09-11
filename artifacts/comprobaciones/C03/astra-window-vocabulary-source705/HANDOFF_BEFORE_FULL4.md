# Prioridad705: Full2 terminal; corregir límite y diagnosticar arranque

Full2/16657 fue detenido intencionadamente por candidato con defecto demostrado y fallos de inicio; terminal exit1 confirmado. FULL2.log/EXIT/INTERRUPTION conservan evidencia, no es Full completo. Observados3fallos (CoreNotes y2MindShell). El fixtureMindShell usa Pythonstdlib independiente: no importa llm.py ni el helper nuevo; ModuleNotFound descartado como explicación de esos tests. Causa de arranque aún no demostrada. Baseline de nuevos límitesPython5fallos/69pass; no se retiró ningún test. Fuente705 sigue sin adoptar; encuesta26/716/0.

# Prioridad de revisión705: defecto de límite pendiente

Full2/16657 sigue vivo con CANDIDATE3 (timeout de Core ya registrado). No cambiar fuente hasta su final. TOKEN_BOUNDARY_DEFECT.json demuestra3aceptaciones incorrectas: nombre conocido enmascara prefijo de identificador compuesto (.route/.schema/-extra). Reparar límites en ambos helpers, añadir controles de puntuación y compuestos, ejecutar dueñas y nuevoFull antes de producto/adopción. No basta un rerun sin cambios. Fuente705 sigue sin adoptar.

# Estado prioritario: Full2 aún activo con un fallo observado

Sesión16657. Timeout de10s al arrancar Core en CoreNotesEndToEndTests.LargeNotesListIsBoundedPaginatedAndLeavesProtocolResponsive, antes de paginación. No reiniciar el Full activo; esperar final, reproducir test concreto y resolver sin cambiar límite. Opera cerró normalmente para liberar RAM; no hay inferencia. Producto706 ya preparado (scratchpad/c03-status-batch706.py yhook706), no iniciado. Su guard exige Full2verde; si el Full verde posterior es otro intento, actualizar sólo esa referencia de evidencia antes de ejecutar. CANDIDATE3 manda. Fuente705no adoptada. REPORT.md yprivadoREPLAY.md describen evidencia ylímites.

# Actualización Full705: segunda ejecución16657

61066 terminóexit1 antesde suites por5espaciosen fixture;copiasFULL1 ytestoriginal preservadas. Sóloformato corregido,tokensidénticos. Fuentesproductivasno cambiaron. AhoraFull2vivo16657;logsTEMP/c03-window-vocabulary705-full2.log yfull2-exit.json. CANDIDATE3.json manda sobreCANDIDATE2.167App/691Pythondueñaspass. Noadopción.

# Estado actual705 — candidato sin adoptar; Full en curso

Objetivo íntegro activo; dueño no tiene decisiones pendientes. El turno previo sólo aclaró metodología (no_progress); éste implementa y valida el bloqueo. No marcar goal completo. Mantener742/rev1248:26cubiertos/716abiertos/0NA, mainintacto yBAXYcerrado.

Fuente705: nuevoshelpers src/Baxy.App/ObservedResponseLiterals.cs ysrc/baxy_mind/observed_response_literals.py, usados porUserMessagePolicy/llm.py únicamente en vocabulario/códigos/minúscula inicial. Reconocen segmentos exactos title/processName bajo kindoperation,window.*,verified/succeededtrue,polaritysuccess; misión conserva sobres de steps. Hechos y texto público originales no se reescriben. Límite4096 se comprueba antes de enmascarar. No cambia prompt/sampler/modelo/kernel. Casos con títulos alterados, estados no verificados, jerga extra, foco invertido, nombre en minúscula ymisión están probados.

Dueñas:691Python/167App,0skip. Full vivo61066; logTEMP/c03-window-vocabulary705-full.log, salidaJSONfull-exit.json. Recoger esehandle, no repetir ni reiniciar por timeout. Artefactos astra-window-vocabulary-source705/{PREREG,CANDIDATE2,FULL_RUNNING,REPLAY}. CANDIDATE2sha fuentes vigentes; PREREG recoge revisión anterior. DeclaracionesSTT ytest_price_v8 actualizadas;407Python,árbolf137c37bdfff68369b233748b5e2a963c999c0d4ee4f0eced4e20281c408368e. Baselines/testerrores preservados. Noadopción aún; última fuente publicada703/commitc11007b0,estado83fef92c.

Replay privado LOCALAPPDATA/BAXY/C03-window-vocabulary705-private/REPLAY.json: borradores reales694H0104(18ocurrencias,2únicos) pasan12sin editar;6grammar siguenmal.704ventanal(18,1único) siguefallando. Sonfixturesdevalidación con trazas reales, no inferencias nuevas ni aceptación. Falta producto completo706(campaña aún no preparada) yadopción/publicación. No rerun de scriptsone-shot705; conservarresultados.

Siguiente: conFullverde, evidencia de producto y revisión/adopción705. Luego reparación de lectura/frescura: H0023 pierdewindow.resolve válida en__main__.py1537–1564,6210–6285;H0359 cae antesdedecisión;H0532 ya esknowledgesin lectura. No confundir las3causas ni aplicarproto695. RestoC03 completo másabajo. APLAZADOS/ghostsK2/prototype695 ajenossepreservan.

---

# Handoff C03 — continuidad703 adoptada;50/73 en producto704

Goal íntegro C03 activo. Leer el adjunto goal-objective.md SHA621020a31266e98d043b07f214e8a8c6c3cb48f1287d27e411bf805402dadb86. RamaGoal-c03, mainintacto. Encuesta742/rev1248:26cubiertos/716abiertos/0NA, ninguna decisión pendiente del dueño. BAXY cerrado; no inferencia, test o build activo. Estado anterior del goal turn:progress, con implementación, validación y32respuestas recuperadas.

## Fuente actual703

MainWindowViewModel reutiliza la decisión ordinaria para distinguir una petición nueva de una respuesta a confirmación, sin clasificarla dos veces. MindPlanSession comparte la transición de cancelación segura: resolver outbox y luego limpiar el plan; sólo cuando hay confirmación sin reconciliación ni efecto incierto. Fragmentos conservan identidad, nuevas acciones obtienen nuevosIDs, efectos inciertos no se abandonan. Sin cambio de modelo,Python,catálogo niRiskPolicy. No permitirSensitive/External en bloque; varias operaciones escriben/envían datos.

Fuente703 en astra-continuity-source703/{PREREG,VALIDATED,RESULT,PINS}. DosC#productivos y dosficheros de pruebas. Python sigue6a01540ccabb4121cb90e6d8f3dea527e0feefde0cd6868e8b3a38e03e028fe4/406archivos; fuente702 intacta. 18focales iniciales; dueñas192seleccionadas:188pass/4fallosdefixture/0skip. Las4fixtures usaban token no canónico yfecha sinO exacto. Sólo esos valores se corrigieron; validación enfocada final11pass/0skip incluye4arregladas+7controles repetidos. No sumar199tests únicos. Fuentes productivas idénticas entre ejecuciones. Fast0,0warnings/errors,Release25,21s. NoFull703:Full693 es línea base anterior; Full cuando se adopte C#+Python productivos juntos y Full final.

## Producto704 completado y sellado

Mismos73textos/orden/criterios689/694/702.50correctos/23fallos;32ganancias/0pérdidas respecto702. La misma selección equivocada de tabs en t6 genera confirmación, pero los39pedidos siguientes ya no quedan atrapados:35hacen lectura y32terminan correctamente. No aprobar la tanda entera ni dar cobertura automática. Leídos todos los finales y todas las etapascompose; segundo revisor confirmó índices45–72.

Público astra-status-batch704/{MANUAL_REVIEW,RESULT,PINS}; privadoLOCALAPPDATA/BAXY/C03-status-batch704-private/{review.json,verdicts.json,adjudication.json,RESULT.md,http-posts.jsonl,decision-boundary.jsonl}. No reejecutar adjudicadores/selladores. EXIT0/manifiesto intacto,3499,5586MiBGPU/2444,0742MiBRAM,272,687s. SinUI/voz, no consumo total certificado. No presentar tiempo global como aceleración: ahora sí ejecuta35lecturas antes bloqueadas.

## Publicación

703adoptada de forma delimitada y publicada enc11007b0; push origin/Goal-c03 confirmado. Auditoría scratchpad/c03-audit-continuity703-704.py comprueba disco/índice,privados,6fuentes,árbol,plan/observador,encuesta/runtime/main y sellos702. Predecesores:7ceeef70fuente702,4d55b449estado,10f16319fuente693,a8eaf976comparación. Preservar APLAZADOS/prototype695 y ghosts de índiceK2; no restaurarlos ni incluirlos de paso.

## Bloqueos siguientes

704falla:4enumeraciones de ventanas→aclaración;windows-all-en→browser.tabs.list/confirmación;windows-focus-mixed→18rechazosmissing_fact de borrador correcto con ventanal;3datos históricos sin lectura(disk-used-es,H0532,H0675);RAMH0539/H0508confunde utilizable/instalada/disponible;7lecturas soportadas no seleccionadas(H0359,cpu-order-es,H0450,H0499,H0602,clock-date-en,audio-order-es);3alcancesredfalsos;2rankingsCPUacumulados/conmiembrosalterados.

Identidades: window_prose_facts107–267 reconoce títulos/procesos pero omite estructuras naturales. UserMessagePolicy156–275 yModelMessageComposer56–62/127–208 vetan términos internos incluso dentro de títulos observados; Pythonllm9587–9645también. Corregir la frontera de identidad verificada en ambos extremos, no permitir jerga globalmente ni añadir excepciones por títuloQwen. H0104funciona704porque ahora el título esChatGPT, no porque se reparó el veto. Requiere Full si se adoptaC#+Python.

Frescura: prototype695rechazado por activar lecturas para conocimiento/otra persona/discoD. No aplicarlo ni repetir sus50literales. Los valores históricos no sustituyen lectura nueva; conservar contexto de referencias. HerenciaREGISTRO_DE_MANTENIBILIDAD1109–1128,1582–1600,2678–2703. Correlacionar selector por texto exacto,pid,time dentro de decision-boundary; HTTPid/request_id/turnoid son contadores distintos. Una exploración por ordinal confundiót5cont6 y fue rechazada; no es defecto probado del producto.

H0732sigueFAIL: NetworkInformationStatusProbe sólo cuenta interfacesUp, no verificaInternet. Wifi.status.connected:false no demuestra ausencia deEthernet. Procesos requieren revisar compose posterior alprogreso; totalProcessorSeconds es acumulado, no CPUactual. H0655 se acepta bajo el mismo criterio contextual694 por sus cantidadesfree/used/installed explícitas; el término disponibleentotal sigue mejorable. No modificar sellos históricos por estas notas.

## Comparación de modelos terminada

InformeK2_HORIZON_SELECTOR700/INFORME_PARA_DUENO.md, publicadoa8eaf976; open_in_codex devolvióqueued,no afirmar que se vio.300respuestas independientes699:6perfiles×50mismas preguntas,sinBAXY/system/tools/schema. PrácticosQwen40/50,1,352s;K2high38/50,8,8285s. Sólo servidorQwen3165,55MiBGPU/715,38RAM,K2high3444,23/787,56. K2gana6,pierde8;no superioridad universal. ReferenciasQwen40,K2BF16pequeño33,K2grande39. Sinpromoción.

700quitauna instrucción en20selectores/modelo:Qwen7→5,K2high10→8;efecto mixto, recupera una horaK2. Historial/catálogo conservados,no prueba todas lascapas. Mantenerseparados fallosdelmodelo ydelproducto. RuntimeQwen4B2507Q4/b9980,manifest13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed. K2backendexterno35999d1/tokenizer285/285,no paridadlogitsHF completa. No reabrir campaña sincausa.

## Cierre íntegro pendiente

Generalización742,ocho rutas,reserva100,averías/restauración,UIreal/voz/loopback/AEC,recursosconjuntos,matriz yFullfinal. MantenerC03EN_CURSO. Continuarautónomamente con causas compartidas; no preguntar otra vez por históricos/autorización ya concedidos.
