# C03 — tramo15: cancelación y datos mínimos para narrar

EN_CURSO,Goal-c03,main/registro/stash intactos. Sin100frescos,Fullfinal,promoción,
commit ni push. Tramo anterior cuenta como progreso:código y evidencia cambiaron.

La captura spoken-clock expuso dos causas:outcome=completed junto a estado cancelado,
y fuga de un windowId en el primer borrador antes de un retry que inventó cierre.
Se reparó la proyección Python:remaining_steps_cancelled→outcome=cancelled;
se conservan efectos anteriores ordenados. _compose_action_facts retira windowId
del objeto de argumentos sólo para narración;lo mismo en observaciones de ventanas.
No cambia prepared operation ni token,catálogo,providers,autorización o ejecución.
Propósito,proceso y demás argumentos conservados. No se añade instrucción ni veto.

Pruebas cubren cancelación después de efecto anterior,lectura previa,confirmación,
no mutación del input e incertidumbre distinta de cancelación. C03/compose109pass;
voice/V8/STT28pass/1skip ambiental;Ruff0. Ningún cambio.NET en este tramo.
Logs scratchpad/c03-cancel-outcome-python.log,c03-cancel-outcome-regression.log.
llmSHA cf307d3c3ee0d73d30f136517d6d1bf717789bf38f98fd243bb2db682ebcd790
STTSHA d254b4df302d1ed6a9c52a689d50ed2da3bac9bfced5cf0ef610ac395416c027

Captura cancel-outcome/session6180 terminada78.33s,21/21publicados,GPU3499.56MiB,
RAM4663.94MiB. t18 explica cancelación sin cierre falso ni ID;prosa extensa sigue
sin satisfacer naturalidad final. t20 cierre real PID38092/journalsequence28.
Audio muted=false comprobado en esta captura;no acusar inversión por compararlo
con estado true de capturas anteriores. t2 dice desactivado de mutación:fallo de prosa.
21adjudicados individualmente. No panel verde ni aceptación reservada.

Consulta histórica acotada adicional a logs nativos gemma/ministral:no justifica
otro barrido. Gemma actual fallaba12*8,17+26,14*6;Ministral aritmética/gramática.
Evidencia scratchpad/c03-native-gemma.log,c03-native-ministral.log. No se lanzaron
nuevos modelos ni se tocó el sampler. Confirmado baseline inicial10/16útiles y
15/16publicados en astra-baseline/ADJUDICACION.md;no usar población actual21 para
fabricar porcentaje de mejora contra aquellos16.

Siguiente:consistencia de spanglish/calidad conceptual y narración breve;resolver
alias natural de ventana y representación de fallo de composición en UI según
rutas del tramo14. Cerrar sólo con desarrolloverde,100nuevos,R07final,UI,runtime
registrado,Fullfinal y publicación propia. Todos los procesos de esta tanda recogidos.
