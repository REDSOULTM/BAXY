# C04 — Lo pedido ocurre, se verifica y se autoriza correctamente

**Ejecutable: Grok 4.6 High; un goal con tramos reanudables.**
Predecesor: C03 cumplido. Incorpora [contrato](01_CONTRATO_DE_CAMPANA.md) y
[protocolo vigente](../00_PROTOCOLO_EJECUCION.md).

## Objetivo

Cumple el Goal 05 y los modos/confirmaciones del 04. Cada capacidad comprometida
debe tener una petición pública, un efecto comprobado o un terminal honesto y
la respuesta correspondiente. Repara la verificación de app.open sin rebajarla.

## Lecturas y owners

Filas G05, modos de G04 e Identidad. Casos R02/R03/R08/R09/R12/R15.
ProductCatalog, RiskPolicy, handlers Core, providers Windows y autoridad de
confirmación. Lee la matriz histórica del 05 y la revalidación 09.5.11B como
inventario; su contador ClassifyCatalog no es evidencia de efectos físicos.

## Tramos de ejecución

A: inventario/preflight y regresión Calculadora. B: una familia de providers
por ventana, hasta 20 escenarios nuevos sin cortar secuencias. C: confirmación,
efecto incierto y recuperación. D: unión de todo el catálogo y cierre.
Conserva todos los IDs; un terminal honesto de fracaso no acredita que una
operación realizable funcione. La matriz distingue ambas cosas.

## Trabajo

1. Extrae el catálogo público real y cobertura actual. Congela un escenario de
   aceptación por operación, con variantes necesarias de argumentos, política y
   error. Usa frases naturales; el conductor no puede enviar operationId.
   Mantén separados: operaciones existentes, representadas por casos, intentadas,
   ejecutadas físicamente, verificadas, fallidas e intrínsecamente no verificables.
2. Reproduce Calculadora desde C01 con el runtime real. Lee estado independiente
   antes/después y localiza por qué el efecto visible terminó verification_failed.
   Repara el mecanismo genérico; no añadas una excepción de texto/app para pasar.
3. Recorre operaciones de lecturas y efectos con recursos propios del test.
   Comprueba también argumentos, destino e identidad del recurso. Ver el proceso
   arrancar no prueba que se abrió la ventana correcta; un exit code no certifica
   el efecto. El mensaje público debe coincidir con esa postlectura.
4. Provoca un ejecutor que afirma éxito sin efecto y un efecto incierto tras
   timeout. La petición entra por el canal común; la inyección se identifica.
   pending sólo significa reintento seguro. Conserva la identidad del efecto
   incierto y evita ejecutarlo dos veces. C05 verifica luego continuidad extensa.
5. Corrige la discrepancia de RecoverableDelete con Identidad: borrar confirma
   en modo normal aunque use papelera. Prueba crear, tirar y restaurar sólo
   recursos de la campaña. Comprueba la invocación exacta, argumentos cambiados,
   confirmación caducada, cancelación y replay. Revisa también sobrescritura y
   pérdida de trabajo. Bypass no permite efectos no pedidos ni éxitos inventados.
6. Separa falta de ambiente de imposibilidad intrínseca de verificación.
   Reúne el ambiente de prueba necesario; no conviertas operaciones sin probar
   en observadas por categoría. Una operación no verificable requiere razón,
   comportamiento honesto comprobado y cobertura explícita en la matriz.
7. Publica la ejecución completa, incluidos fallos. No uses un allowlist de
   verification_failed para declarar exitosa una capacidad que el usuario pidió.

## Cierre obligatorio

- [ ] Todas las operaciones del catálogo tienen escenario, resultado y evidencia;
      no hay filas desconocidas ni exclusiones que oculten falta de ambiente.
- [ ] R02/R03/R08/R09/R12/R15 y todos los casos físicos aplicables pasan.
- [ ] Los efectos se observan independientemente y la prosa final coincide;
      provider mentiroso y efecto incierto producen terminales honestos.
- [ ] Modos normal/bypass, confirmación exacta y no duplicación cumplen Identidad.
- [ ] Las filas intrínsecamente no verificables conservan razón y prueba de su
      terminal; no se cuentan como ejecución verificada ni como dispositivo probado.
- [ ] Se conservan cobertura y cuenta; no hay adaptadores específicos añadidos
      para el examen ni un nuevo marco genérico de verificación.
- [ ] Filas propias cumplidas, Full verde, artefactos y cambios propios publicados.

Evidencia: artifacts/comprobaciones/C04/. Siguiente: C05.
