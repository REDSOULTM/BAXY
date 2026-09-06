# BAXY — sprints de producto y comprobación

**Ruta vigente desde 2026-09-04: C03 → C09 → 10.7–10.18 → 11.1–11.16 → 12.1–12.3.**
C01/C02 están cerrados en el estado inspeccionado; C03 sigue en curso.
Comprueba el [estado actual](Sprints%20comprobación/05_ESTADO_Y_CONTINUACION.md)
antes de continuar. No reinicies sprints por haber cambiado de sesión.

- [Lanzador con todos los pendientes](00_LANZAR_DESDE_10_7.md).
- [Replanteamiento para el Grok que ejecuta C03](Sprints%20comprobación/07_REPLANTEAR_C03.md).
- [Protocolo único Grok 4.6 High](00_PROTOCOLO_EJECUCION.md).
- [Diagnóstico y fuentes oficiales](REVISION_SPRINTS_2026-09-04.md).

## Qué manda y cómo se ejecuta

Identidad, la petición actual del dueño y el prompt vigente con su protocolo.
Los cierres anteriores prueban lo que midieron en su fecha, no que hoy el producto
cumpla. Los relevos son evidencia/estado; sus copias de instrucciones no sustituyen
el archivo vigente. AGENTS ubica repositorio, owners y validación.

Cada sprint conserva su alcance completo. Trabaja una causa/frontera por tramo,
con lecturas y salida pequeñas; estado durable y continuación entre ventanas.
500K es capacidad de Grok, no objetivo de consumo. La política actual busca
60–100K activos y corta a 150K; no es un umbral oficial de calidad.
Una sesión agotada no cierra ni invalida un sprint. No se exige una sesión única.

## Compromisos originales y trazabilidad

01–09, 03B/03C y la recuperación 09.5 son historia de implementación que los
Cxx contrastan con el producto. No se borran esos prompts ni sus umbrales.
La [matriz](Sprints%20comprobación/03_MATRIZ_DE_CRITERIOS.md) conserva sus 97
criterios originales y owners. Los números históricos no son conteos actuales.

| # | Goal | Cumplido cuando |
|---|---|---|
| 01 | **La herencia** | Sabes qué hay construido ya, qué funciona de verdad y qué se trae |
| 02 | La base reproducible | La compuerta pasa entera, también en un clon limpio |
| 03 | **La comprensión** | La petición llega a la operación correcta, o a una pregunta útil |
| 03B | **Romper el techo** | El 90 % que el 03 midió inalcanzable — cambiando la arquitectura que lo limita |
| 03C | **Cerrar el alcance** | ≤5/36 fuera de catálogo `acted` sin bajar de 112/124; las 12 in-catalog restantes no se aplazan al 04 |
| 04 | La honestidad | Cero efectos no pedidos, cero éxitos falsos, cero frases fijas |
| 05 | La ejecución verificada | Lo que dice que pasó, pasó — y algo independiente lo comprueba |
| 06 | La voz del producto | Todo lo que la persona lee lo formula el modelo, y está bien escrito |
| 07 | Las misiones compuestas | Lo que ninguna operación sola logra, encadenando |
| 08 | La primera señal | Nunca hay silencio muerto |
| 09 | La voz y el oído | Oye su nombre, entiende y contesta hablando |
| 09.5 | **Herencia total** ([mapa](09.5_HERENCIA_TOTAL.md)) | Todas las versiones presentes conciliadas, mejores piezas trasplantadas y 01–09 revalidados; se pegan los `09.5.x` |
| 10 | **Certificación para uso diario** ([mapa](10_USO_DIARIO.md)) | Familias 10.7–10.17 primero; después 200 turnos autónomos por la entrada pública, `N10/M10` (mínimos 1.947/808 + delta 09.5) e Identidad |
| 11 | **Validación y cierre** ([mapa](11_VALIDACION.md)) | `K11` contratos (mínimo 2.036 + delta 09.5), deuda, errores, regresión e higiene |


La campaña [C01–C09](Sprints%20comprobación/00_INDICE.md) recupera la conducta
integrada. C09 habilita el 10; no lo certifica. El 10 prueba familias y 200 turnos;
el 11 resuelve deuda y regresión. [Fase 12](12_PRODUCTO_FINAL.md) cubre el producto
instalado y el hardware objetivo que el alcance había dejado diferidos.

Conserva lo ya demostrado con hashes/procedencia; revalida lo afectado por cambios.
Un caso de aceptación usado para reparar deja de ser reservado. Un
composition_failed espontáneo es fallo de respuesta aunque sea honesto.
Full verde solo no acredita prosa, ejecución física, UI, voz ni instalación.
Un límite medido mantiene incumplimiento, no permiso para avanzar.

## Cinco leyes

1. **Hereda primero, estado del arte después, construye al final.** Biblioteca por
   índice/título/rango; contrasta la pieza viva. No re-derives rechazos medidos.
2. **Nada de sobreingeniería.** Si añades una capa, retira la que sustituye.
3. **Sólo se arregla lo que bloquea (01–10).** Deuda restante a APLAZADOS;
   el 11 la resuelve. Un fallo de tu aceptación no se difiere para aprobar.
4. **Lo más ligero que cumpla.** 4 GB VRAM es techo, no objetivo; cuentan árbol
   completo, RAM, CPU, voz y latencia. No reducir cobertura ni exactitud.
5. **Arquitectura modular.** Una responsabilidad por pieza, dependencias hacia
   dentro y cero código muerto. Costuras medidas para sustituciones reales.

## Seis invariantes

Catálogo tipado único: mente propone, kernel autoriza, provider ejecuta.
Nada se afirma sin verificar. Terminales honestos. Confirmación ligada a la
invocación exacta. Cero respuestas visibles fijas. Modelo local y privado:
puede entrar información web, no salir contenido privado del usuario.

Identidad exige compañero con voz, accesibilidad, memoria controlable,
operaciones genéricas del PC, presencia y ausencia de silencio mayor de 3 s.
No se sustituye respuesta útil por silencio ni por una lista de frases permitidas.

## Qué significa terminado

Una tanda de implementación cierra con conducta demostrada, Full verde,
validación física cuando corresponda y trabajo propio publicado conforme a AGENTS.
Los skips se informan aparte y no acreditan criterios. Conserva WIP ajeno y usa
un checkout aislado para certificar si es necesario.

11.16 entrega candidato de desarrollo validado. **Sólo 12.3 declara
BAXY_DEFINITIVO_VALIDADO**, con instalación, hardware objetivo y distribución
acreditados. Los diferidos de producto tienen ahora dueño en 12: no desaparecen
ni se presentan como hechos. Un bloqueo ambiental mantiene NO_LISTO.

Historia de orden: [09.5 y siguientes](00_ORDEN_DESDE_09_5.md).
Prompts Sol antiguos en `sol/`: archivo, no se lanzan.
