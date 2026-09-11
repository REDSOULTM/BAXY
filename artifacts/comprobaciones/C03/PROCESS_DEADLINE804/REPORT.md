# Plazo804 — Full verde; producto80537/50, sin adopción

Las listas densas de procesos recibían512tokens en Python802 pero sólo4s de composición. La tanda803 produjo28/50 respuestas válidas y agotó las listas largas; conteos12/12 correctos. Se amplía el selector de inventario denso existente a `system.process.list`/`processes`, con los umbrales y tiempos ya usados para ventanas. No cambia el prompt, el modelo, el sampler ni los límites de recursos.

La fuente de producto cambia en un solo fichero C#:12 líneas añadidas/7 retiradas. Se añaden17 casos a la suite dueña; no se incorpora el nuevo verificadorPython ni una capa correctora.

| Validación | Resultado |
|---|---|
|17 controles nuevos sobre la fuente anterior|3 fallos densos,14pass,0skip|
|Suite dueña PlannerAppBoundaryTests con la corrección|153pass,0skip,5s|
|Fast|Exit0;Release10,77s;0advertencias/0errores|
|Full acumulado Python802+C#804|Exit1; .NET4642pass/1omisión agregada; Python12713pass/3skips/466subtests,1fallo restorableCount=2.28pins intactos; no adoptado|
|Producto805|Completo37/50válidos,13fallidos;6ganancias/4pérdidas vs801;sinadopción|

28pins y snapshot privados preservan el candidato; los recibos800/802/764 anteriores permanecen intactos. Los logs conservan sus bytes con atributos Git específicos. `NEXT_CONFIRMATION_REV2.json` registra runner y revisor805, revisados sin defectos bloqueantes. La raíz adjudicó cada final contra su observación nueva; no se confunden con payloads idénticos a803.

La propuesta de identidad sigue aislada:127pruebas y35/35 válidos801 conservados no bastan para adoptarla. Otro orden válido de columnas produce falso veto y una identidad no observada puede pasar; no se añade ese checker mientras el límite de tiempo sea la causa siguiente demostrada. La plantilla de ventanas/procesos sigue siendo el único selector de tiempo, sin nuevos presupuestos.

Encuesta28 cubiertos/714 abiertos/0 no aplican; matriz3/11. C03 EN_CURSO. El pico de referencia803 es3497,56MiBVRAM y2436,58MiBRAM residente, separados; no es validación conjunta de UI y voz.

Repetición Full804 recogida0, PID18268/sesión54013; ningún proceso pendiente. LINE_ENDING_REPAIR.json registra restauración exacta de2recibos y dueña3pass/0skip; primer FULL_EXIT.json rojo preservado. La repetición usa FULL_RETRY1/FULL_EXIT.json;805 exige ese recibo verde ligado a28pins.


## Resultado final de la repetición y producto805

Full804 repetición1:exit0,Python12714pass/3skips/466subtests/603,40s;.NET4642pass/1omisión agregada y16optativas impresas, no sumadas;Release4,58s/0advertencias/errores.28pins intactos; FULL_RETRY1/FULL_RESULT.json revisado por raíz conserva tablas y recibos. Primer rojo sin cambios.

Producto805 completó los50 en265,078s y la raíz adjudicó37válidos/13fallidos. Listas10/11,conteos12/12,CPU8/11,memoria5/11,noespecificado2/4,apps0/1. Mediana de listas5,119s frente30,817s en803. VRAM3497,56MiB/RAMresidente2392,75MiB, sin infracciones. Continúan regresiones frente801; candidato sinadoptar. Véase PROCESS_BATCH805/REPORT.md.
