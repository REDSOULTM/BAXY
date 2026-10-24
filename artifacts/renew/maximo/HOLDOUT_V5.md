# Holdout v5: resultados (2026-10-24)

Corrida única del holdout v5 (sellado el 2026-10-23, sha256 en `metas.json`), con el plan pre-registrado en
`CIERRE_PLAN_V5.md` (sección «Al congelar», hub/renew-maximo 116353a3b, escrita antes de extraer). Tres configuraciones,
todas con System One encendido (0,4 / 0,6 / corrige, Laya Q8) y el arnés común del HEAD final:

| Nombre | Código | Qué representa |
|---|---|---|
| `inicio` | `pc-system-one` 86991ca9d | BAXY al empezar la misión |
| `maximo` | `renew-maximo` 452854a18 | fin de la fase 1 |
| `final` | `int10f` 19be8b42a | fin de la fase 2 (hoy `renew-maximo` 441526cd8, mismo código) |

## Decisión (720 casos × 3 semillas, PC, juez común del HEAD final)

Validación del banco con el juez final antes de correr: PROBLEMAS 0. Ninguna corrida con errores del servidor ni consultas
a Laya sin respuesta.

| | `inicio` | `maximo` | `final` |
|---|---|---|---|
| Aciertos por semilla | 611 / 602 / 611 | 626 / 623 / 621 | 627 / 620 / 625 |
| **Media** | 608,0 | 623,3 | **624,0** |
| pass^3 (bien en las 3) | 584 | 605 | 602 |
| Acciones equivocadas (media) | 74,3 | 64,0 | 66,3 |

| Comparación (pre-registrada) | Δ aciertos | IC95 (bootstrap pareado) | IC95 gemelos | McNemar (Holm) |
|---|---|---|---|---|
| `final` − `inicio` | **+16,0** | [+5,7, +27,0] | [+5,0, +27,7] | **p 0,023** |
| `final` − `maximo` | +0,7 | [−6,0, +7,3] | [−5,7, +7,0] | p 0,50 |

Acciones equivocadas: `final` − `inicio` −8,0 (IC95 [−17,7, +1,3]); `final` − `maximo` +2,3 (IC95 [−2,0, +7,0]); ninguna
significativa tras Holm.

Por familia (media de 3 semillas): gana en larga_cola (63,7 → 70,3 de 80), par_minimo (90,7 → 95,7 de 100), multipaso
(33,7 → 35,7 de 40) y no_puedo (43,3 → 45,3 de 50); pierde 3 en comun (112,7 → 109,7 de 120). **ya_hecho** («¿ya lo
hiciste?» con el resultado en el historial) es 14–15 de 40 en las tres: la debilidad mayor, y ninguna fase la movió. Por
idioma, `final` sube en los cuatro: es 312,3 → 317,7, en 95,7 → 101,0, spanglish 91,3 → 93,7, dictado 108,7 → 111,7.

## E2E (76 casos × 2 semillas: PC s0, NB s1)

| | `inicio` | `maximo` | `final` |
|---|---|---|---|
| PC s0 | 48 | 44 | 47 |
| NB s1 | 51 | 52 | 51 |
| **Media** | 49,5 | 48,0 | **49,0** |
| pass^2 | 42 | 40 | 42 |
| Primera respuesta p50, PC / NB | 3,4 s / 3,5 s | 4,3 s / 4,3 s | 4,3 s / 4,3 s |

`final` − `inicio` −0,5 (IC95 [−7,0, +6,0], p 0,44 Holm); `final` − `maximo` +1,0 (IC95 [−3,0, +5,0]). Sin diferencia
demostrable: el holdout no confirma la ganancia de práctica (+2 a +3). Las confirmaciones son el área más floja en las tres
(3–5 de 8). La primera respuesta es ~0,9 s más lenta desde la fase 1 (resultados con más hechos).

## Falsedades (36 conversaciones × 2 semillas, leídas a mano a ciegas)

Cada semilla la leyó un agente distinto con las configuraciones renombradas al azar (A/B/C); la clave se reveló después de
contar (`renew_v5\holdout\claves-ciego`, lecturas en `renew_v5\holdout\ciego\s{0,1}\lectura.md`).

| | `inicio` | `maximo` | `final` |
|---|---|---|---|
| Claras, PC s0 | 6 | 2 | 2 |
| Claras, NB s1 | 7 | 7 | 2 |
| **Claras, total (72 conversaciones)** | **13** | 9 | **4** |

`final` frente a `inicio`: 13 conversaciones con falsedad clara sólo en `inicio` y 4 sólo en `final` (binomial exacta
p 0,049 sin ajustar; 0,098 con Holm entre las dos comparaciones; el plan lo trata como descriptivo). Frente a `maximo`:
9 contra 4 (p 0,27). Lo que dejó de pasar: negar que haya algo en BAXY-bench tras buscar sólo en la carpeta de trabajo,
cifras inventadas (espacio libre, tamaño de página) y «ya lo moví» sin llamada. Las 4 de `final`: dar por hecho un pegado
que sólo tiene recibo de entrega (V5F007), negar sin buscar que BAXY-bench tenga un archivo (V5F015), dar como
última una línea leída a medias (V5F027) y no ver una carpeta que el resultado sí ubicaba (V5F033). Además, dos
conversaciones de `final` en la semilla del PC acabaron sin ninguna respuesta (`decision_unavailable_after_call`).

## Incidentes de la corrida (todos antes de mirar resultados del brazo afectado)

- NB: primera e2e sin sustituir F:→D: en las rutas de los casos (setup_fallido 76/76) → VOID, repetida con copia sustituida.
- NB: Codex/ChatGPT escribiendo en el perfil (contaminated) → cerrado antes de cada brazo.
- NB: V5E061 de `final` dejó `Documentos\baxy-prueba-v3\Sin título.txt` → movido (no borrado) a
  `D:\BAXYeval\restos-home-2026-10-24\hv5-final-V5E061`; el brazo siguiente se repitió.
- NB: Opera abierta por un caso de `inicio`, colas duplicadas, sesión de Windows bloqueada → falsedades de `maximo` y
  `final` VOID y repetidas.
- Corte de luz de las dos máquinas (~11:00): la e2e `inicio` del PC (cortada en V5E040, nada quedó en el perfil) se repitió
  entera.
- PC: la clave del ciego s1 se escribió en el perfil durante la e2e `inicio` y el bench la puso en cuarentena (V5E069); el
  resultado no cambia. El PC `inicio` marca contaminated por `.claude\.last-cleanup` (la app de Claude), no por el bench.
- PC: el servicio de Windows `ChatGPT` pasó a deshabilitado a las 14:17 (evento 7040); ningún caso usó operaciones de
  servicios (sólo `system.status` y `system.time`): lo hizo la propia app al cerrarla a la fuerza.

## Prueba en vivo del HEAD final (PC, 2026-10-24 ~17:10, en silencio, estado restaurado)

Los mismos 13 turnos de la fase 1 y dos nuevos: calculadora abrir/cerrar, volumen ±10 («de 24 a 34; el PC sigue
muteado»), Spotify reproducir y pausar, juegos de Steam («30 juegos; mostré los 20 primeros»), Paint abrir, maximizar,
minimizar y cerrar, «¿está instalado Fortnite?» («no hay Fortnite instalado en Steam ni en Epic»), espacio del disco C
(«529,1 GB libres de 1,8 TB»). «Abre la biblioteca de Steam»: ahora entra (en la fase 1 pulsó 7 veces y no pudo). Clima de
mañana: el modelo quiso leer un sitio que no venía en los resultados y el freno de red lo paró y preguntó
(`host_not_from_session`), además de ofrecer el pronóstico «de hoy». Maximizar Paint funcionó pero con 13 lecturas de
ventana repetidas después (un bucle de lecturas que `same_call_closes` no corta).
