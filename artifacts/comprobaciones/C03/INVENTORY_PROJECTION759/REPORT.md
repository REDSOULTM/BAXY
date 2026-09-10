# Modelo, integración y sobrecarga: qué está demostrado

La preocupación del dueño es correcta: una regla sin nombre de modelo también puede favorecer las formulaciones que se usaron para ajustarla. Una comparación integrada no basta para juzgar al modelo original. No afirmamos que todo BAXY esté ajustado para Qwen; sí hay pérdidas de integración demostradas que deben corregirse y separarse de sus errores nativos.

La primera comparación696–698 conservaba instrucciones de BAXY y sus860 respuestas no constituían aislamiento nativo. La corrección699 ejecutó las mismas50 tareas completas en cada uno de seis perfiles:300 respuestas sin system, herramientas ni schema de BAXY. No se dividió el panel en dos mitades. Se usaron recetas y plantillas específicas, con diferencias locales de backend, cuantización, contexto y presupuesto declaradas. Es una comparación de perfiles locales, no una equivalencia demostrada con los modelos originales BF16 ni un ranking universal. Véase [la referencia nativa699](../K2_HORIZON_NATIVE699/REPORTE699.md).

737 mantuvo hechos, backend, plantilla y sampler de K2 en57 pares, cambiando sólo pregunta directa frente a prompt de redacción BAXY. Hubo25 aciertos compartidos,14 sólo con BAXY,3 sólo directos y15 pares sin respuesta acreditable. Demuestra ganancias y pérdidas del prompt; no prueba neutralidad del resto de las capas ni variabilidad entre semillas. [Comparación737](../FACTS_PROMPT737/REPORT.md).

752B fue una regresión de producto con73 turnos y Qwen, no una nueva comparación de modelos. Dio49 acreditados,22 fallos sustantivos y2 sensibles a precisión sin acreditar. Entre los defectos: una respuesta de foco correcta fue rechazada18 veces por la gramática de BAXY; son repeticiones de un caso. [Informe752B](../STATUS_BATCH752B/REPORT.md).

## Primera pérdida localizada en el inventario

753 observó la frontera real del producto, sin alterar argumentos, resultados ni excepciones. La primera petición contenía1533 tokens de entrada; generó256, terminó por límite y tardó3,922s. El redactor gastó salida en coordenadas, tamaños y estados no pedidos antes de completar20 identidades de una página de24 ventanas observadas. Su reintento ya no disponía del presupuesto de cuatro segundos. No fue desbordamiento del contexto4096:1789 tokens totales. La ejecución terminó filtered/null. [Diagnóstico753](../COMPOSE_BOUNDARY753/DIAGNOSIS.json).

Los siguientes pares conservaron la misma observación congelada, el modelo, el backend y los ajustes. Son diagnósticos de una causa concreta, no cobertura de encuesta ni benchmarks de modelos.

| Prueba | Única intervención del par | Resultado |
|---|---|---|
|754|Añadir instrucción de concisión y alcance|Ambos brazos agotan4s; respuesta final no observada.|
|755|Repite el par con OMP/MKL4 y TOKENIZERSfalse como producto|Ambos agotan4s. Igualar esos valores no explica la diferencia de velocidad.|
|756|Observa ambos finales hasta15s, sin cambiar max256 ni referencia4s|6,484/6,828s; ambos cortados. La instrucción sola no completa la lista.|
|757|Sólo retirar detalles por ventana no pedidos; conservar20 identidades y metadatos|6,547s/corte frente a3,750s/final completo. El segundo aún omite que la lista es parcial.|
|758|Ambos con proyección de identidades; añadir la misma instrucción754 al segundo|3,453/3,422s, ambos completos. El segundo aún confunde20 encontradas con24 observadas; alcance insuficiente.|
|759|Ambos con proyección de identidades y prompt original; añadir significado factual de página|3,578/3,953s. El segundo indica lista parcial20/24 pero inventa que son las más recientes. Rechazado.|

La proyección757 reduce1533 a678 tokens de entrada y256 cortados a153 completos de salida. Se mantienen todas las entradas, repeticiones, títulos/procesos y metadatos; no se reduce el número de ventanas para mejorar el resultado. Es una mejora parcial demostrada, todavía no una reparación aceptada.759 expone además un hueco del validador si éste permite la recencia no observada; la adjudicación humana sigue rechazándola.

El servidor aislado decodificó aproximadamente44–50tokens/s frente a unos76 en753. El cwd difiere: el producto hereda el directorio del intérprete y los pares usan el directorio del backend. No se ha demostrado que sea la causa; tampoco la explican los ajustes OMP/MKL ensayados. Los tiempos dentro de cada par permiten observar esa intervención; no atribuir diferencias entre entornos sin medir sus condiciones efectivas.

El pico del servidor en757 fue3495,56MiB de VRAM y717,98MiB de RAM residente. No equivale al consumo de BAXY con UI, voz y el resto del árbol. Muestras cada250ms pueden omitir picos breves. Todos los servidores de estos diagnósticos terminaron; sesiones32057,90883 y63743 recogidas con exit0. El primer lanzamiento758 con `py` no llegó a abrir servidor: faltaba psutil en ese intérprete. Se ejecutó después con el Python registrado, sin instalar ni cambiar dependencias.

## Decisión y continuación

No se adopta ningún parche, modelo, prompt ni nuevo presupuesto por estos pares. No se concede cobertura:26 cubiertos,716 abiertos,0 no aplicables. No hay una decisión pendiente del dueño.

La siguiente reparación debe hacer explícito el significado de los datos que BAXY entrega al narrador y conservar sólo lo pertinente a la petición, manteniendo el snapshot canónico, todas las identidades y la validación de veracidad. No añadir otra formulación de concisión:754–756 no resolvieron el defecto. No aceptar recencia, orden ni otra propiedad que el proveedor no observe. Aplicar las mismas exigencias semánticas a todos los modelos, con sus plantillas y recetas propias, y verificar la primera transformación incorrecta. Después de una fuente validada, repetir la categoría completa73 y las variantes necesarias; una prueba de esta observación no cierra su familia.

Sin fuente productiva editada no corresponde otra suite ni Full. Siguen pendientes cobertura generalizada, reserva, UI real, loopback/AEC, recursos conjuntos, matriz, continuidad y Full de cierre. C03 permanece activo. Las entradas, hechos del escritorio y respuestas completas se conservan sólo en los directorios privados locales C03-compose753-private y C03-inventory-*; los artefactos públicos contienen causas, métricas y huellas.
