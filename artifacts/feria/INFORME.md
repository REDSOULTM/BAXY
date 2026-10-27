# Informe de la noche de la feria — 2026-10-27 (00:00 a 04:30)

Equipo de la feria: **el notebook**. BAXY instalada 1.1.1, mente desplegada desde la rama `nb-arr-feria`
(commit 6203d774f, en hub) en `D:\BAXYeval\entrega\BAXY-1.1.1-arr-9537b5f8b`. Sin cambios en .NET ni en la interfaz.

## Qué se probó

| Prueba | Antes (nb-arr-junto, lo de anoche) | Ahora (J, desplegado) |
|---|---|---|
| Preguntas con año, de memoria tras «conversación nueva» (NB, en vivo) | 3 de 5 falsas («Francia», «Chile», «Mbappé») | 9 de 9 buscadas y correctas |
| Sondas con año del PC (12, x2) | 2,5 de 12 | 11 de 12 |
| Curiosidades («cuéntame un dato curioso…», PC 8 x2) | 0 de 8 (inventadas) | 8 de 8 |
| Bloc de notas cerrado sin pedirlo (NB, secuencia de la feria) | 3 de 4 pasadas | 0 de 3 |
| «Abre la calculadora» pulsando cosas | 1 de 2 | 0 de 3 |
| Decisión v11 del PC (240, x2) | 198,5 | 198,5 (Δ 0,0, ningún caso distinto) |
| Acciones equivocadas v11 / v6 | 30 / 77 | 29 / 74 |
| v6 abierto (720, una semilla) | 625 | 624 (Δ −1, ruido ±4) |
| Batería de la feria y del público (59 pedidos) | — | 0 sin respuesta, 0 errores, mediana 8 s, p90 20 s |
| Resistencia H (20 min, 118 turnos) | — | 0 sin respuesta, 0 errores, sin fuga de RAM |
| Resistencia J (40 min) | — | ver abajo |
| Suite Python completa | — | 957 pass, 1 skip, 2 xfail (preexistentes) |

## Qué se arregló (commits en `nb-arr-feria`)

- ced466b6d, 1dec600b2, 54a4f702b, 5c71624e7, 6203d774f — ayuda «dated_search» en la mente: si la pregunta tiene
  un solo número y es un año, o pide una curiosidad, y el modelo iba a contestar de memoria sin mirar nada, el propio
  modelo escribe la búsqueda web (`fill_call`, como la capa «corrige» de System One) y la duda no la retiene.
  Lo estable (capitales, planetas, la Mona Lisa) sigue saliendo de memoria en 3-7 s; lo fechado tarda 8-20 s.
- 3e320d49a, 19b6b441b — ayuda «close_unsaid»: un clic en «Cerrar/Close/Salir/Minimizar» no se hace si la persona
  no dijo nada de cerrar, salir o minimizar. Los cierres pedidos («cierra el bloc de notas») funcionan igual (6 de 6).
- Tres intentos sólo con frases en el prompt (a489c28e1, 9f7587350, 9e14c2d1d, 1f47d6121) se midieron y se
  descartaron: no aguantaban o empeoraban; la regla 5 quedó como la de anoche.

## Límites que quedan (declarados, sin arreglo esta noche)

- Lo tecleado mientras la mente carga (≈30-40 s tras abrir BAXY) se queda en la caja hasta que esté lista; el aviso
  dice «Escribe o di» en vez de «Cargando». No se pierde: hay que pulsar Enter otra vez.
- «¿Quién te creó?»: dice que no lo sabe, porque la memoria de este perfil no lo tiene. Si quieres que lo diga,
  díselo una vez («recuerda que te creó …») antes de la feria.
- «¿Qué modelo usas?» a veces devuelve la pregunta (V11D237, por la regla de persona de anoche).
- Spotify: si alguien toca el teclado o el ratón mientras BAXY busca la canción, se corta y BAXY dice que no pudo
  comprobarlo aunque suene.
- Una pregunta con año y otro número («el récord de 100 m en 2009») no activa la ayuda.
- Falsedades en el PC: VOID (había un Chrome tuyo con un documento abierto y no se cerró).
- ruff no ejecutado (no está instalado en el runtime).

## Estado del PC

- La «visión» que preparó la sesión del PC (23:16-23:33, sin commit, en la rama vieja `baxy-renew` de tu checkout)
  son los commits de visión que **ya están** en la entrega desde el 21-10 (293357a9a, proyector en CPU): no había nada
  nuevo que meter. Tu checkout no se tocó.
- Una sesión `claude -p` sin interfaz midió los bancos hasta las 04:15 y lo dejó en el buzón; sus ventanas y la tarea
  programada de falsedades se borraron (7040 = 0).

## Cómo volver atrás

- Toda la noche: `git -C D:\BAXYeval\entrega\BAXY-1.1.1-arr-9537b5f8b checkout --detach 5017917f9` y reiniciar BAXY.
- Sólo una ayuda, sin tocar código: variable de entorno `BAXY_AYUDAS` con la lista de ayudas sin `dated_search` o sin
  `close_unsaid`.
