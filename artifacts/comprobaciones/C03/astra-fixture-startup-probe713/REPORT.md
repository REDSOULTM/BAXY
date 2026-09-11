# Arranque tras una sola enumeración del catálogo

Los50 arranques del fixture real terminaron listos, sin timeout del Core, error de inicio ni captura diagnóstica. La sonda anterior había terminado en su sexto arranque con5listos/1fallido. Se conservó el mismo montaje, observador y límite de10s del saludo del Core, con nuevos datos privados por arranque.

NUnit: **1pass,0fail,0skips**. Las50inicializaciones están dentro de esa prueba; no se presentan como50pruebas NUnit ni50requisitos de encuesta. InitializeAsync completo midió mínimo5.850s, mediana6.746s y máximo11.855s. Ese reloj también incluye trabajo posterior al saludo y no comparte su límite10s.

El fixture quedó restaurado byteporbyte y el helper temporal retirado. Todas las fuentes del candidato712 permanecen idénticas a su sello. El siguiente Full debe recompilar los tests porque el binario utilizado todavía contenía la instrumentación.

El ejecutor terminó con exit1 por OSError22 al restaurar el fixture después de terminar las pruebas. El código de salida del proceso de tests no llegó a guardarse; su log conserva NUnit1pass. Se comprobó que el archivo instrumentado no estaba truncado, se retiró el bloque temporal con apply_patch y su hash volvió a coincidir exactamente con el respaldo. EXIT.json preserva el fallo operativo; no se transforma en un exit0 del comando original.

Este resultado apoya la reparación del arranque en este host; no garantiza ausencia de fallos raros ni cierraC03. Las respuestas del modelo, UI, voz y recursos conjuntos no se midieron. La encuesta sigue26cubiertos/716abiertos/0noaplicables. Fuente705+712 sin adoptar hasta completar Full y regresión de producto.
