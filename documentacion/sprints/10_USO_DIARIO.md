# Goal 10 — Uso diario y aceptación del producto

> **Mapa: no se lanza entero.** El Goal 10 se ejecuta en orden mediante
> `10.1`–`10.18`. Cada fichero es un goal autónomo para **Grok 4.6 High** y cabe
> en una ventana operativa máxima de **500k tokens**. No se juntan dos sesiones
> aunque una termine pronto.

## Por qué existe

Los Goals 01–09 construyeron, en este orden, herencia, reproducibilidad,
comprensión y alcance, honestidad, ejecución verificada, voz del producto,
misiones compuestas, primera señal y voz física. El siguiente paso lógico no es
otra capacidad aislada: es demostrar que todas ellas forman un compañero que se
usa normalmente y no decepciona.

El Goal 10 conserva las dos obligaciones de sus versiones anteriores:

1. **Uso diario real:** 200 turnos del dueño en cuatro sesiones, con las cinco
   familias más frecuentes repetidas 20 veces cada una; modos, narración, memoria,
   privacidad y presencia se prueban usándolos.
2. **Aceptación integral:** los 1.947 turnos reales observados y sus 808 misiones
   accionables reciben un resultado y un veredicto individual, sin confundir
   corpus, fixture ni simulación con efecto físico.

La decisión posterior del dueño sigue vigente: **no hay soak, espera de 24 horas
ni prueba que bloquee por calendario**. La estabilidad que esa espera pretendía
comprar se prueba con arranque en frío, reinicios acotados, repetición concentrada
y medición de recursos en reposo.

## La frontera con el Goal 11

El 10 valida el uso y los mensajes reales del producto. El 11 conserva la función
original de cierre: contratos históricos adicionales, deuda aplazada, caminos de
error, regresión cruzada, higiene y publicación final. No se vacía
`APLAZADOS.md` ni se persiguen fallos hipotéticos en el 10 salvo que bloqueen su
propia aceptación.

## Orden de sesiones

| Goal | Misión acotada | Dependencia | Cierra con |
|---|---|---|---|
| 10.1 | Congelar corpus, alcance y cola | Goal 09 | 1.947/808 reproducibles y partición sin solapes |
| 10.2 | Presencia y recursos | 10.1 | bandeja, arranque, readiness e idle corto medidos |
| 10.3 | Uso real A | 10.2 | 50 turnos: 25 espontáneos + 25 repetidos |
| 10.4 | Uso real B | 10.3 | segundo bloque de 50 |
| 10.5 | Uso real C | 10.4 | tercer bloque de 50 |
| 10.6 | Uso real D | 10.5 | 200 totales y cinco familias ×20 |
| 10.7 | Conversación y no-efecto | 10.6 | su partición de 1.947 verde |
| 10.8 | Hechos locales | 10.7 | hechos dinámicos locales contemporáneos |
| 10.9 | Web y actualidad | 10.8 | búsqueda pertinente sin salida de datos del usuario |
| 10.10 | Apps, ventanas y visión | 10.9 | efectos y postcondiciones físicos de esa familia |
| 10.11 | Audio | 10.10 | volumen, mute y estado verificados |
| 10.12 | Media, streaming y juegos | 10.11 | reproducción/navegación sin éxitos de fixture |
| 10.13 | Sistema y conectividad | 10.12 | estado, ajustes, wifi, Bluetooth y periféricos |
| 10.14 | Productividad y memoria | 10.13 | notas, agenda, recordatorios, memoria y CRUD |
| 10.15 | Comunicación y navegación | 10.14 | navegador, mensajería, portapapeles y Office |
| 10.16 | Misiones compuestas | 10.15 | las 74 candidatas encadenadas, sin pasos huérfanos |
| 10.17 | Identidad viva | 10.16 | cada decisión de Identidad con evidencia de producto |
| 10.18 | Integración del 10 | 10.17 | 200 + 1.947 + 808 cerrados sobre el mismo árbol |

Las filas de corpus se asignan una sola vez. Una misión compuesta se diagnostica
en 10.16, pero su `message_id` no se suma dos veces al total de 1.947/808. La cola
congelada del 10.1 es la autoridad de pertenencia.

## Criterios agregados

- [ ] 200 turnos reales en cuatro sesiones; 100 espontáneos y 100 de repetición,
      con cinco familias ×20, y cero fallo de honestidad sin corregir y repetir.
- [ ] 1.947/1.947 turnos observados contabilizados exactamente una vez, con
      respuesta, contrato, hechos del turno, evidencia y `pass`/`fail` razonado.
- [ ] 808/808 misiones accionables atraviesan la tubería que corresponda; fixture
      y simulación se publican como tales y nunca cuentan como efecto real.
- [ ] Cero petición in-scope omitida por ambiente. Si falta una app, cuenta,
      contenido, permiso o dispositivo, su sesión termina en `FALLO_DE_AMBIENTE`,
      publica cómo preparar el PC y se repite antes de avanzar.
- [ ] Cada decisión de `00_IDENTIDAD.md` tiene evidencia viva en el mismo árbol.
- [ ] Arranque, reinicio, repetición e idle corto sustituyen cualquier soak; se
      publican latencia y recursos sin esperar 24 horas.
- [ ] Los tres ceros siguen intactos: efecto no pedido, éxito no verificado y
      respuesta visible fija.
- [ ] Full verde y todo el Goal 10 publicado antes de abrir el 11.

La evidencia que explica el corte está en
[`10_APRENDIZAJES.md`](10_APRENDIZAJES.md). El protocolo de ejecución está en
[`10_PROTOCOLO_GROK46.md`](10_PROTOCOLO_GROK46.md).
