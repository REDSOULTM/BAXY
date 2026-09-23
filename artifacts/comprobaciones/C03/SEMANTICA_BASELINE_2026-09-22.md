# Fase 3.5 — baseline antes de tocar `src` (2026-09-22, HEAD b5c9fe72 = tag `opus55-inicio`)

Harness: `scripts/semantic_replay.py` (conversaciones enteras por el conductor, un perfil por guion, efectos reales
con preset/restore de volumen, micrófono y brillo; 742 literales sólo-decisión por `turn.decide`). Revisiones a mano
de los turnos `manual` en `contexto/semantic_reviews.json`, atadas al texto exacto del final.

```
python -X utf8 scripts/semantic_replay.py conv --out <S>/base --label sem-base --idle 30 \
    artifacts/comprobaciones/C03/contexto/dueno-2026-09-21.turns.jsonl \
    artifacts/comprobaciones/C03/contexto/heldout-2026-09-22.turns.jsonl
python -X utf8 scripts/semantic_replay.py rescore --out <S>/base --reviews artifacts/comprobaciones/C03/contexto/semantic_reviews.json
```

## Cifras

| Guion | Bien | contexto | guarda | paráfrasis | familia | efecto inventado | fuera de alcance | `-` (salió bien el 21) |
|---|---|---|---|---|---|---|---|---|
| dueño 2026-09-21 | **33/60** | 0/12 | 0/8 | 0/5 | 1/1 | 1/1 | 6/8 | 25/25 |
| held-out 2026-09-22 | **15/30** | 1/9 | 3/6 | 0/1 | 2/4 | 1/1 | 2/2 | 6/7 |
| 35 bancos contextuales (`contexto/<categoría>.turns.jsonl`) | **398/525** | — | — | — | — | — | — | — |

742 literales del registro privado, sólo decisión (`semantic_replay.py literals`, un `turn.decide` aislado por
literal, 0,58 s de media): 0 errores; action 404, conversation 118, clarify 116, plan 104. Es la referencia del
`diff` de cada clase (las decisiones que cambien se revisan una a una). Bancos: 398/525 (el notebook midió 396/525
sobre HEADs anteriores).

Igual que ctx-dueno-08 del notebook (33/60 sobre 4dd98219). Efectos afirmados sin operación fuera de la clase
«efecto inventado»: **dos** — dueño 56 «ahora súbelo a 100» → «El volumen se subió a 100.» y held-out 5 «y ahora
redúcelo a 45» → «Reducí el brillo de la pantalla a 45.», ambos en ruta conversación y con cero operaciones.

Corrección del held-out antes de su commit: el turno 29 prohibía la subcadena «la llamé» y así penalizaba la respuesta
verdadera «No, no la llamé»; se sustituyó por «ya la llamé», «sí, la llamé»… y se marcó `manual` (revisado: bien).

## Turnos malos del 21 (guion del dueño), clasificados

| n | clase | dueño (forma) | BAXY en baseline | causa medida |
|---|---|---|---|---|
| 3 | guarda | «Me gusta crear cosas , como tu» | «El mensaje me llegó cortado en «, como tu»» | `cut_request`: «tu» sin tilde al final leído como posesivo cortado |
| 4 | guarda | «me gusta crear cosas como tu» | «En eso no encuentro un pedido…» | ídem; la pregunta anterior deja objetivo pendiente |
| 5 | guarda | «Bueno no era un pedido…» | «no encuentro un pedido» | el shell concatena la charla al objetivo pendiente («Aclaración confiable…») y el texto combinado (≥15 palabras sin verbo de orden) cae en `overheard_speech` |
| 15 | paráfrasis | «…hablando de amor, pon una canción de amor en youtube» | pregunta qué canción | la vía del modelo pregunta; el patrón calla por el prefijo de charla |
| 16 | contexto | «Quiero una canción de amor» | «¿en Spotify?» | no hereda YouTube de 15 |
| 17 | contexto | «No, en youtube» | «No puedo colocar… en YouTube» | el re-armado del shell («pedido + Aclaración: No, en youtube») se lee como negación/límite |
| 22 | paráfrasis | «¿Sabes qué peli estoy viendo en potplayer?» | «no pude entender» | la lectura de ventana no se propone |
| 23 | paráfrasis | «Estoy viendo colony… investigala, quiero saber qué piensa la gente» | «no encuentro un pedido» | `overheard_speech` (≥15 palabras; «investigala» no está entre los verbos de orden) |
| 24 | contexto | «INvestigala» | «no encuentro un pedido» | cascada del objetivo pendiente |
| 25 | contexto | «…te dije que investigues algo…» | «no encuentro un pedido» | `overheard_speech` |
| 26 | guarda | «Por dios, odio estos fallos» | «no encuentro un pedido» | cascada del objetivo pendiente |
| 27 | guarda | «Esto es para el agente que lea…» | «No pude entender» | recuperación fallida |
| 28 | guarda | «Obvio que no lo entendiste…» | «no encuentro un pedido» | `overheard_speech` |
| 35 | paráfrasis | «¿cuál fue el 1er libro de zombies?» | contesta de memoria | hecho datado sin búsqueda |
| 38 | fuera de alcance | «en steam apretá en counter strike 2» | lectura de biblioteca | motor (Fase 4/5) |
| 40 | contexto | «No lo hiciste mentiroso…» | «No pude entender» | recuperación fallida |
| 41 | contexto | «Dímelo tú, te mandé la misión a ti» | «No pude entender» | recuperación fallida |
| 42 | fuera de alcance | «En steam ve a crash bandicoot» | fallo honesto en 35 s | motor; latencia |
| 46 | contexto | «activalo» | «No puedo activar tu micrófono» | sin inverso del último efecto |
| 49 | guarda | «Deberías poder pero está bien…» | «no encuentro un pedido» | `overheard_speech` |
| 53 | contexto | «20» (tras «¿cuánto?») | «¿Quieres que ajuste el volumen?» | «20» sola = `noise`; el re-armado «baja el volumen + Aclaración: 20» no completa el ajuste relativo |
| 54 | contexto | «si» | «No puedo reducir el volumen…» | límite falso sobre el objetivo pendiente |
| 56 | contexto | «ahora súbelo a 100» | «El volumen se subió a 100.» **sin operación** | sin antecedente para «lo»; efecto inventado |
| 57 | contexto | «al volumen» | «No puedo ajustar el volumen» | límite falso |
| 58 | paráfrasis | «¿La nueva peli de resident evil es buena?» | «No tengo información» | opinión sobre estreno sin búsqueda |
| 59 | contexto | «pues investigala, dime si tiene buenas o malas reseñas» | «¿Sobre qué producto…?» | sin tema anterior |
| 60 | guarda | «dios mío, te dije hace 2 mensajes…» | «no encuentro un pedido» | cascada del objetivo pendiente |

Salen bien hoy de los malos del 21: 19, 20, 39, 44 («mutea mi microfono»), 47, 48, 50, 51 (arreglos del notebook).

## Held-out (congelado desde su commit), malos en baseline

contexto: 2 «quince» (re-pregunta), 5 «y ahora reducilo a 45» (efecto inventado), 7 «volvé a prenderlo», 9 «devolvele
el sonido», 12 «sí, dale» (no cierra la confirmación), 14 «averiguá qué dijo la crítica» (busca «la crítica»), 16
«fijate cuándo sale la próxima temporada», 18 «en YouTube mejor». guarda: 3 y 20 (charla con pregunta pendiente →
re-pregunta), 13 (charla → «¿confirmar o cancelar?»). paráfrasis: 15. familia: 25 «poné en mute el micro», 27
«subile al volumen hasta 50». `-`: 10 «abrí el bloc de notas» falló en el adaptador («falló el inventario»; máquina).
