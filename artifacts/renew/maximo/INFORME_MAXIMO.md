# BAXY Renew al máximo: informe final (BORRADOR, 2026-10-22 noche)

> Borrador escrito mientras corren las últimas medidas. Las cifras del holdout v4 se llenan una sola vez, al final,
> sobre el HEAD congelado de `renew-maximo` (plan pre-registrado en `CIERRE_PLAN.md`). Todo lo que dice «práctica» se
> midió en bancos de práctica, no en el holdout.

## En corto, para el dueño

1. **Sin reentrenar el modelo.** Todo lo ganado viene de la aplicación: lo que el modelo lee después de actuar, la
   seguridad del núcleo, los proveedores, la voz, los recursos y System One. El Qwen ajustado c2e1 es el mismo.
2. **Más seguro.** Cerramos agujeros que la revisión encontró: abrir una herramienta del sistema (msconfig, regedit,
   servicios…) pide tu sí; pulsar «Sí» en un diálogo de reemplazar o borrar pide tu sí; un mensaje con salto de línea
   ya no se puede enviar sin confirmar; la papelera no puede llevarse la carpeta privada de BAXY; las búsquedas web ya
   no guardan cookies entre sí; el freno de red no deja salir lo que BAXY leyó de tu memoria.
3. **Más honesto.** Los resultados dicen lo que se comprobó y lo que no («ya estaba así», «el lugar no se comprobó»,
   «no se buscó en el resto del PC», «releído después: no quedó como pediste»), y BAXY ya no toma «no hay nada pendiente»
   como «ya lo hice».
4. **Más rápido.** El arranque pasa de 17,2 s a 0,8 s de calentamiento; la primera palabra hablada, de ~1,6 s a ~0,65 s
   (voz D); la calculadora, Spotify y abrir apps responden antes.
5. **Mismo acierto al decidir** (práctica): decision2 se mantiene dentro del ruido (229-230 de 268) con más casos
   estables en las tres semillas (222 → 226).
6. **Dentro de los límites**: tarjeta gráfica 3 990 MiB (≤ 4 096) y RAM del producto ~2,7 GB (≤ 4 GB), con voz y
   System One encendidos.

## Antes y después

| Qué | Antes (`pc-system-one`) | Después (`renew-maximo` final) | Dónde se midió |
|---|---|---|---|
| Decisión, holdout v4 (720, 3 semillas) | 632,3 sin S1 · 633,0 con S1 | **636,3** (+3,3, no significativo) | holdout, PC + NB |
| Acciones equivocadas, holdout v4 | 62 sin S1 · 48,7 con S1 | **45,7** (−27 %, McNemar p 0,0005) | holdout, PC + NB |
| E2E, holdout v4 (72) | *pendiente* | *pendiente* | holdout, NB |
| Falsedades, holdout v4 (36) | *pendiente* | *pendiente* | holdout, NB |
| decision2 de práctica (268) | 233 con S1 (231 sin S1) | 231,7 con S1 (int8; nada empeora) | PC, 3 semillas |
| Calentamiento al arrancar | 17,2 s | 0,8 s | PC |
| Primera palabra de la voz | ~1,6 s | ~0,65 s | PC (voz D) |
| VRAM con System One | 4 091 MiB | 3 990 MiB | NB, pico en turnos |
| RAM del producto | ~2,7 GB | ~2,6-2,7 GB | NB |
| Suites (mismo commit 452854a18) | Kernel 603, pytest 85 | Kernel 693, Contracts 74, App 111, Setup 477, pytest 346, Providers 2 808 | PC + NB |

## Lo que se nota

Prueba en vivo en tu PC (versión final, de madrugada, en silencio y con todo restaurado al terminar):

- «abre la calculadora» → «Abrí la Calculadora y quedó al frente»; «ciérrala» → «Cerré la Calculadora».
- «sube el volumen 10» → «Subí el volumen en 10, quedó en 40»; «baja el volumen 10» → «… quedó en 30».
- «pon Bohemian Rhapsody de Queen en Spotify» → sonó y lo dijo; «pausa la música» → «Pausé Queen - Bohemian Rhapsody».
- «¿qué juegos tengo instalados en Steam?» → «Tienes 36 juegos en Steam, pero la lista se cortó en 20, así que hay más».
- «busca en internet el clima de mañana en Santiago» → «Mañana en Santiago hay llovizna, con máximo de 18…».
- Paint: abrir, maximizar, minimizar y cerrar, cada uno verificado.
- Lo que falló: «abre la biblioteca de Steam» → abrió Steam pero no entró a la Biblioteca (pulsó el botón 7 veces, 50 s)
  y lo dijo con verdad: «no pude entrar a la Biblioteca: el botón no respondió».

Además: arranca en menos de un segundo de calentamiento, empieza a hablar antes, y cuando algo no se comprobó lo dice
(«enviado sin comprobar», «ya estaba así», «no se buscó en el resto del PC») en vez de afirmarlo.

## Límites honestos

- El 4B a veces confunde aplicaciones de nombre parecido («Configuración» y «Configuración del sistema»): ahora no
  hace daño (pide el sí o le dice cuál es la correcta), pero la elección misma sólo mejoraría reentrenando.
- Leer pantallas complejas (la biblioteca de Steam) sigue siendo el punto débil de la honestidad.
- Las ganancias de decisión de menos de 3 puntos no se pueden afirmar con estos bancos; se informan como «sin pérdida».
- Muchas palancas que tocaban el texto que el modelo aprendió empeoraron: se retiraron con su cifra (lista abajo).

## Cómo apagar System One

```bat
scripts\system_one.cmd off
```

Vuelve a encenderlo con `scripts\system_one.cmd on`.

## Palancas: medidas, quedadas y retiradas

Cómo leer las cifras: «d2» es decision2 de práctica (268 casos, System One encendido, media de 3 semillas; el ruido
entre semillas es ±2); «e2e» son los casos de punta a punta; «falsedades» son conversaciones leídas a mano buscando un
«hecho» que no ocurrió; «recursos» y «sesión larga» se midieron en el notebook (22 turnos reales). Una palanca se quedó
si ganaba algo sin empeorar otro banco; las que sólo cierran un agujero de seguridad se quedaron con d2 sin pérdida.

### Se quedaron

| Palanca | Qué hace | Cifra medida (banco, dónde) | Ids / rama |
|---|---|---|---|
| CU rápido | El uso del PC rápido que decidiste fusionar | d2 229 frente a 233 (8 cambian, −6/+2, no significativo); suites verdes (PC) | `pc-cu`, c1177101d |
| Arreglos de la revisión | Arreglos de seguridad e invariantes en mente, núcleo, App y voz; el modelo ya no puede quitar los frenos escribiendo un archivo | d2 229,67 frente a 229 (Δ +0,67, IC95 [−2,67; +4,0]) (PC) | fx-mente ca9d75de0, fx-core 8c90bdac3, fx-app 11347dd0d, fx-voz 12278e86d, B-CU-1/3 78e475ee8, B-SYS-1 |
| System One afinado | Laya sólo corrige hacia nombres del catálogo y hacia lo que el núcleo confirma | d2 de la integración 229,67; acciones equivocadas 16,7 → 15 por corrida (PC) | w2-s1, en `int` |
| 3.1 Laya en el procesador | Laya deja de usar la tarjeta gráfica | VRAM con S1 4 091 → 3 902 MiB; elige igual 60/60; +0,55 s sólo en turnos dudosos (recursos, NB) | 7ba30ec05 → 56754a091 |
| 3.3 | Limita las copias del contexto que Qwen guarda en RAM | pico de RAM de Qwen 3 123 → 2 078 MiB (−950) (sesión larga, NB) | lv-t1, 9d6ea550a |
| 1.4 | Recorta el historial con margen y lo precalienta en reposo | relectura por sesión 19,3/19,7 → 15,9/12,9 s (−4 a −7 s) (sesión larga, NB) | lv-t1, 9d6ea550a |
| 9.5 | Pide probabilidades sólo en la decisión | sin diferencia medible ni regresión; d2 de la tanda 1 230,0 (Δ +0,33) (PC) | lv-t1 |
| Tanda 2: recibos honestos | «Ya estaba así», «lugar sin comprobar», repetición por contenido, errores de memoria (8.2, 7.7, 11.1, 11.2) | falsedades claras 1,67 → 1,00 por corrida (F015 2/3 → 0/3, PC); e2e +1,5 (IC95 [0; +3,5]), pass^2 22 → 25 (NB) | lv-t2 |
| Tanda 2 del notebook | Revisión de proveedores y 6.1-6.3, 6.6, 6.7 (pistas para recuperarse de un fallo) | e2e +0,67 (IC95 [−0,67; +2,33]); Providers 2 570 verde (NB) | nb-maximo 153b7a068 |
| Tanda 4 | Una sola pregunta por malentendido (4.2); el reloj registra lo hecho en la sesión (8.1) | d2 228,67 frente a 230,0 (Δ −1,33, sin pérdida); falsedades claras 1,00 (PC) | lv-t4 b6b731f94 |
| Tanda 5 | «Corrige» no puede saltar a herramientas de ventana o de red (5.1, efecto tipado) | d2 con su catálogo 227,33 frente a 228,33 (Δ −1,0, costo ~0) (PC); lo del latido queda inactivo | lv-t5 5f0ed1e37 |
| game.launch con título | No lanza un juego distinto del que pediste (F001/F016) | seguridad; va con P2.6 (−540 tokens de prefijo) (bisección, PC) | t3final 561dc2152 |
| 1.5 contexto | 4 096 tokens más de historial | VRAM 3 902 → 3 990 MiB (106 de margen), RAM igual (recursos, NB) | lv-ctx |
| 1.1/1.2 historial | Compacta resultados viejos antes de olvidar turnos | d2 de `int` 229,0 frente a 230,0 (Δ −1,0, IC95 [−6,67; +5,0]) (PC); ningún banco lo ve | w2-ctxmem |
| Segunda ola | Errores accionables, zona por control (7.3), freno de red (11.5), flujos del núcleo y de la App, aviso de voz | junto con lo anterior: d2 de `int` 229,0 (sin regresión); Kernel 661, App 67, pytest 273 (PC) | w2-kern2, w2-app2, w2-flujos-*, w2-k2, w2-voz2 |
| Voz D (9.1 + 9.3) | Sintetiza la primera frase sola y con 6 pasos de Supertonic | primer audio de una respuesta de dos frases 1 595 → 646 ms p50 (CPU del PC); elegida por tu oído | voz-maximo, `baxy-voice.json` |
| w3-speed | Guarda y restaura el prefijo ya calculado; presintetiza respuestas | calentamiento al arrancar 17,2 → 0,8 s; 12/12 decisiones iguales; d2 s0 228 (ruido) (PC) | 049935467 |
| E014 y guardas 1 y 2 | Abrir una herramienta del sistema o pulsar «Sí» en reemplazar/borrar pide tu sí; la lista de lugares vuelve | E014 abrió msconfig (e2e de `int` 24,5 → 22,5); tras arreglar, e2e de int3 26,0 → 25,0 sin daño (NB) | ab182a770, nb-prevuelo2 0bc9d1410, 3a619d0a8 |
| E022 | El freno de red reconoce la dirección que dictaste | pedía un sí sin motivo al leer tu URL; prueba nueva (App 72) | 2a7a44fe5 |
| 8.3 y 7.1, stateAfter | El resultado dice si quedó como pediste y cómo quedó la ventana o el volumen | d2 de int3 230,0 frente a 229,0 (Δ +1,0), pass^3 222 → 226 (PC) | w4-mind 1514060c3, w4-core 15c48a05a |
| Auditorías del notebook | Un mensaje con salto de línea pide el sí; winget con el id exacto; búsquedas sin cookies; Steam, apps, ventanas, web y archivos; más lugares (7.4) | d2 de int4 229,33 frente a 229,0, pass^3 222 → 226; Providers 2 743/2 743 (NB) | nb-maximo 153b7a068, c654557ca |
| nb-perf | Calculadora, carpeta y Spotify por canales ya abiertos; inventario de apps en una pasada | velocidad, sin cifra aislada en `PROGRESO.md` | int5 49c8fee31 (hasta 198236a5e) |
| E027 | «No encontrado» dice dónde buscó | E027 bajaba en e2e de int3 por decir «no está en tu PC» tras mirar tres carpetas | nb-e027, int6 b84547ed5 |
| F001, F002, F010 | Un juego que no nombraste espera tu sí; las lecturas dicen si BAXY abrió la ventana; «nada pendiente» no es «hecho» | F002 fallaba 9/9 (PC); con el arreglo, 3 → 0 falsas (NB) | ca48a01a3, dbb973a85, f9a97c35b, 873fd26db |
| w5-d2 | «Corrige» puede ir a una lectura con los mismos efectos (P169) | d2 233,0 (sin P212: +2,67, IC95 [+0,67; +5,33]) (PC) | 41d232614 |
| w5-steam, nb-w5-f004 | Ve en qué sección de la app está; el teclado espera a un editor ocupado; el texto sin ventana dice adónde fue | entran en int8 (d2 231,67, nada baja) | 396da4d12, 05ce9ebfe |
| w5-speed2 | Lee el historial por adelantado mientras BAXY habla | −120..220 ms esperados por turno de seguimiento (sin cifra medida); se apaga con BAXY_RENEW_PREFILL=0 | 6890225f3 |
| w5-confirm (+2) | Una confirmación vieja se suelta; un «sí» dudoso (bajo 0,95) se pregunta | banco de 29 respuestas: «sí pero el otro» y «sí no» aprobaban en int7 ×3; int8 ×2: 15/15 sí, 8/8 no, 6/6 seguras (PC) | d2af91ebc, 2b939b5fc |
| w5-tail, w5-ui, w5-resto | Sin esperas de 30 s a una ventana vacía; 9 etiquetas de pantalla que ya no afirman de más | int8: d2 231,67 (sin P212 +1,33, nada baja); e2e int8 23,5 frente a int6 24,0 (n.s., PC) | 72aa01915, d14ed9917, 1130f184b |
| nb-w5-mem | Un solo recorte del historial; lo quitado no se lee como hecho | d2 229,0 (Δ −0,33); −21 % de tokens releídos en sesión larga (NB) | 852fc8a9a |
| w5-stt | El oído conoce los nombres de tus apps instaladas | nombres bien oídos 562 → 744 de 1 012; WER 18,97 → 13,43 %; sin más latencia (banco sintético, no tu voz) | 0bf44fd60, 185cc3f75 |
| w5-fals | 7 textos de resultado que el modelo podía leer como «hecho» | falsedades claras 5 → 2 en 3 semillas | int7f, `fin` 371f4de72 |

### Se retiraron (con su cifra)

| Palanca | Qué intentaba | Cifra o razón que la retiró | Ids / rama |
|---|---|---|---|
| 4.1 | Candidatos de duda por el catálogo, sin pasada extra | d2 −2,67 (IC95 [−5,67; −0,33]); en P028 Laya corrige mal en las 3 semillas; sólo −360 ms | d4d2d39d2 |
| P2.3 | Constantes del esquema fuera del prefijo | bisección: P215 3/3 → 0/3 (elige el desinstalador equivocado), P254 3/3 → 1/3 | 9b44a08cb |
| P2.2, P2.2i, frases del NB | Retocar descripciones de herramientas | tanda 3b d2 227,33 frente a 230,0 (Δ −2,67); bisección de 39: 26 → 25 (P2.2) → 22 (P2.2i); frases del NB −4 | lv-t3b |
| P2.6 en parte | Quitar la lista de lugares de app_open | regresión E014 (abrió msconfig elevado en el notebook); la lista volvió | ab182a770 |
| 4.4 | Umbral de duda distinto por riesgo | no se implementó: los datos no separan por clase y elegir entre ~100 combinaciones sobreajusta | — |
| 4.5 | Duda sólo en argumentos de texto libre | ningún umbral retiene menos del 2 % de acciones buenas (a 0,3: 12,9 %) | — |
| P13.1, P2.1, P2.4 | Pista de candidatas, regla 2 partida, una sola ruta `path` | verificación cruzada: una ayuda parecida costó d2 −5 y 1 320 MiB; tocar la regla 2 costó −8; P2.4 pide reentrenar | — |
| R10.1 amplia | El latido retenía también ajustes reversibles | escenas 31,67 → 29,0 (act 4/7 → 1/7); se dejó la acotada (31,0) | lv-t5 5f0ed1e37 |
| 10.2 y el latido | Forma avisar/hacer del latido | lo apagaste (19:10, «aporta poco»): no se midió; el latido sólo con BAXY_RENEW_HEARTBEAT=1; sin escenas en el holdout | fx-latido e895fcd0d |
| w5-grammar | Gramática para valores de lista | sólo 1 de 804 decisiones lo rompía (P020) y el arreglo cambió «luz nocturna» por brillo | sin código |
| 6f03230b4 | «Abre un X nuevo» con miradas cada 150 ms | fuera de int5 por riesgo, sin medir | nb-perf |
| 6.5 | Abrir apps empaquetadas por ActivateApplication | en el notebook dio falsos fallos con apps que sí abren | — |
| Cortar en la primera coma | Empezar a hablar antes | cambia cómo suena: queda para tu oído | — |
| Sin código, de la fase A | Pensar en la duda, lista corta dinámica, best-of-n, decodificación especulativa | pensar: d2 −43 y 3× más lento; lista corta: 3-7 s por decisión; best-of-n sólo con n=32 y 14B | `MAXIMO.md` |

## Incidentes

- F007 cerró tu Chrome durante un banco de falsedades en el PC (regla desde entonces: nada que actúe en el PC mientras
  lo usas).
- E014 abrió msconfig dos veces en el notebook (sin cambios en el sistema); cerrado y arreglado con la guarda 1.
- El disco C: del PC se llenó (archivo de paginación de 24,9 GB con la RAM al tope); se borraron sólo worktrees míos.
