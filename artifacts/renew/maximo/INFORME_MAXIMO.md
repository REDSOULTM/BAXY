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

*(tabla final desde `PROGRESO.md` y `MAXIMO.md`)*

## Incidentes

- F007 cerró tu Chrome durante un banco de falsedades en el PC (regla desde entonces: nada que actúe en el PC mientras
  lo usas).
- E014 abrió msconfig dos veces en el notebook (sin cambios en el sistema); cerrado y arreglado con la guarda 1.
- El disco C: del PC se llenó (archivo de paginación de 24,9 GB con la RAM al tope); se borraron sólo worktrees míos.
