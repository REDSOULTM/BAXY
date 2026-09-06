# Grok 4.6 High — protocolo vigente

Desde 2026-09-04 este nombre histórico remite a
[00_PROTOCOLO_EJECUCION.md](../00_PROTOCOLO_EJECUCION.md), parte de cada Cxx.
No se requiere pegar ambos: el agente lee el contrato referenciado.

500K es capacidad del modelo, no presupuesto de lectura. Se sustituye el reparto
50K+250K+150K+50K por contexto objetivo 60–100K, checkpoint a 100K y corte a 150K.
Es una decisión conservadora para BAXY, no un umbral de calidad publicado por xAI.

Se mantienen High, objetivo completo, persistencia tras corte de cuota,
conservación del WIP, logs/procesos/efectos reconciliados y un único agente escritor.
Reanudar el mismo Cxx en sesión limpia está permitido. Cambiar de sesión no
significa abrir otro sprint, perder criterios ni repetir lo ya acreditado.

El [relevo](06_RELEVO_ENTRE_AGENTES.md) conserva la mecánica de recuperación.
Para el C03 actualmente en marcha usa el
[mensaje de replanteamiento](07_REPLANTEAR_C03.md).
