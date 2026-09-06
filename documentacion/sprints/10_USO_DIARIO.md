# Goal 10 — Certificación autónoma para uso diario

> Revisión 2026-09-04: requiere C09 cumplido y el
> [protocolo único](00_PROTOCOLO_EJECUCION.md). Una meta se divide en tramos
> reanudables, con contexto objetivo 60–100K y corte a 150K; 500K es capacidad.
> El cierre de desarrollo no sustituye la [fase 12](12_PRODUCTO_FINAL.md).

> **Mapa: no se lanza entero.** 10.0–10.2.5 conservan su estado histórico;
> 10.3–10.6 están retirados. Tras C09, ejecuta 10.7–10.18 con Grok 4.6 High.
> Una meta puede reanudarse en sesiones limpias conservando objetivo y cursor.

## Por qué existe

Los Goals 01–09 construyeron, en este orden, herencia, reproducibilidad,
comprensión y alcance, honestidad, ejecución verificada, voz del producto,
misiones compuestas, primera señal y voz física. El siguiente paso lógico no es
otra capacidad aislada: es demostrar que todas ellas forman un compañero que se
usa normalmente y no decepciona.

El Goal 09.5 reconcilia antes todas las versiones de Carter, schemas y BAXY que
existan en la máquina, trasplanta las mejores piezas y revalida 01–09. 09.5.12
publicó el mapa: herencia previa, delta nuevo, piezas trasplantadas (cero lotes)
y rechazos. Por eso el 10 consume `documentacion/herencia/00_MAPA.md` y el ledger
09.5 ya actualizados: no vuelve a inventar una misión que algún intento anterior
resolvió. El delta 09.5 va a checkpoints internos de `10.0`–`10.18`; no hay
prompts 10.x nuevos.

El Goal 10 conserva la cobertura de sus versiones anteriores, pero cambia quién
produce la evidencia y cuándo se produce. La decisión del dueño del 2026-09-01
está en `10_REPLANIFICACION_AUTONOMA.md`:

1. **Capacidades antes de aceptación:** conversación, hechos locales, web,
   aplicaciones, audio, media, sistema, productividad, comunicación y misiones
   compuestas cierran primero sus particiones y holdouts.
2. **Aceptación integral autónoma:** los 1.947 turnos y 808 misiones ya conocidos son mínimos
   de no-regresión. 09.5 añade cualquier mensaje/misión de las fuentes nuevas y
   10.1 congela los totales `N10/M10`; todos reciben resultado individual, sin confundir
   corpus, fixture ni simulación con efecto físico.
3. **Dosis transversal:** después de 10.7–10.17, agentes conducen cuatro bloques
   frescos de 50 turnos por la misma entrada pública de usuario. El dueño no aporta
   prompts ni veredictos. El oráculo independiente verifica salida, plan, efecto,
   postcondición y terminal.

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
| 10.0 | Restaurar la base verde | Goal 09.5 | contrato estructurado y pruebas coherentes; Full verde |
| 10.1 | Congelar corpus, alcance y cola | 10.0 | `N10/M10` reproducibles, ≥1.947/808, y partición sin solapes |
| 10.2 | Presencia y recursos | 10.1 | bandeja, arranque, readiness e idle corto medidos |
| 10.2.5 | Recursos en reposo | 10.2 | árbol completo bajo presupuesto sin perder disponibilidad |
| 10.3–10.6 | **Retirados; no se lanzan** | — | el preflight 10.3 queda histórico; `0/50` no es deuda |
| 10.7 | Conversación y no-efecto | 10.2.5 | su partición de `N10` verde por la entrada pública |
| 10.8 | Hechos locales | 10.7 | hechos dinámicos locales contemporáneos |
| 10.9 | Web y actualidad | 10.8 | búsqueda pertinente sin salida de datos del usuario |
| 10.10 | Apps, ventanas y visión | 10.9 | efectos y postcondiciones físicos de esa familia |
| 10.11 | Audio | 10.10 | volumen, mute y estado verificados |
| 10.12 | Media, streaming y juegos | 10.11 | reproducción/navegación sin éxitos de fixture |
| 10.13 | Sistema y conectividad | 10.12 | estado, ajustes, wifi, Bluetooth y periféricos |
| 10.14 | Productividad y memoria | 10.13 | notas, agenda, recordatorios, memoria y CRUD |
| 10.15 | Comunicación y navegación | 10.14 | navegador, mensajería, portapapeles y Office |
| 10.16 | Misiones compuestas | 10.15 | `C10` candidatas (mínimo 74) encadenadas, sin pasos huérfanos |
| 10.17 | Identidad viva | 10.16 | cada decisión de Identidad con evidencia de producto |
| 10.18 | Certificación autónoma e integración | 10.17 | cuatro bloques ×50 + `N10/M10/C10` sobre el mismo árbol |

Las filas de corpus se asignan una sola vez. Una misión compuesta se diagnostica
en 10.16, pero su `message_id` no se suma dos veces a `N10/M10`. La cola
congelada del 10.1 es la autoridad de pertenencia.

## Criterios agregados

- [ ] 200 turnos autónomos y frescos en cuatro bloques, conducidos por agentes a
      través de la entrada pública del producto después de 10.7–10.17; cero bypass
      directo a componentes internos y cero fallo de honestidad sin corregir y
      repetir.
- [ ] `N10/N10` turnos observados (mínimo 1.947 + delta 09.5) contabilizados exactamente una vez, con
      respuesta, contrato, hechos del turno, evidencia y `pass`/`fail` razonado.
- [ ] `M10/M10` misiones (mínimo 808 + delta 09.5) atraviesan la tubería; fixture
      y simulación se publican como tales y nunca cuentan como efecto real.
- [ ] Cero petición in-scope omitida por ambiente. Si falta una app, cuenta,
      contenido, permiso o dispositivo, la meta se pausa en `FALLO_DE_AMBIENTE`,
      publica cómo preparar el PC y reanuda desde el cursor antes de avanzar.
- [ ] La ausencia del dueño nunca es `FALLO_DE_AMBIENTE`: ningún cierre depende
      de que proporcione entradas, observe una salida o juzgue un resultado.
- [ ] Cada fichero 10.x se lanzó una vez; fallos corregibles y regresiones se
      resolvieron dentro de su meta, sin volver a un goal anterior.
- [ ] Cada decisión de `00_IDENTIDAD.md` tiene evidencia viva en el mismo árbol.
- [ ] Cada defecto/capacidad consulta primero la decisión 09.5; si existe una pieza
      heredable se reutiliza o adapta antes de construir.
- [ ] Sólo español, inglés y spanglish son alcance; nombres ingleses de apps dentro
      de una frase española cuentan como spanglish.
- [ ] Arranque, reinicio, repetición e idle corto sustituyen cualquier soak; se
      publican latencia y recursos sin esperar 24 horas.
- [ ] Los tres ceros siguen intactos: efecto no pedido, éxito no verificado y
      respuesta visible fija.
- [ ] Full verde y todo el Goal 10 publicado antes de abrir el 11.

El cierre significa cero fallos reproducibles conocidos dentro del alcance sobre
el commit y ambiente certificados. No formula la promesa imposible de que ningún
software fallará jamás; hace que cualquier fallo observado en campaña bloquee,
se corrija en su owner y se revalide antes del uso cotidiano.

La evidencia que explica el corte está en
[`10_APRENDIZAJES.md`](10_APRENDIZAJES.md). El protocolo de ejecución está en
[`10_PROTOCOLO_GROK46.md`](10_PROTOCOLO_GROK46.md).
