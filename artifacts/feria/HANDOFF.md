# Handoff — feria científica 2026-10-27 (pruebas hasta 04:30) — nb-arr-feria

## Objetivo
BAXY instalada en el notebook funcionando end to end para la feria; cada error con arreglo verificado o declarado
como límite; estado del PC claro; informe corto con cifras y vuelta atrás.

## Estado (se actualiza a medida que avanza)
- 00:12 instalada del NB lanzada con DevTools (puerto 9333, perfil `dev-mente-v2`), mente de la entrega
  `D:\BAXYeval\entrega\BAXY-1.1.1-arr-9537b5f8b\src` = 5017917f9 (src igual a nb-arr-junto 915203bba). Visión
  encendida (`--mmproj ... --no-mmproj-offload`), VRAM 3.982 MiB.
- PC: `claude -p` sin interfaz desde 00:12 (PID 33916) mide decisión v11 de final8 4530e077c frente a nb-arr-junto
  915203bba (worktree `F:\BAXYeval\wt\pc-feria`). Falsedades no: su banco maneja el escritorio y el PC va por SSH.
- Visión: ya estaba en la entrega (293357a9a, 21-10). Lo que el PC dejó preparado sin commit en `baxy-renew`
  (sesión e14ecb06, 23:16-23:33) son esos mismos commits traídos a una rama vieja + el límite de RAM a 5 GB en la
  documentación de esa rama. No entra nada nuevo a la feria.

## Hallazgos
- Batería feria (14 de 20 antes de caerse DevTools): 6-25 s por turno, sin repeticiones ni bucles.
  - FALSO de memoria: «¿Quién ganó el mundial de fútbol 2022?» → «Francia» (p_call 0,05; también 20:49 de ayer).
  - «¿Cuánto es 345 por 12?» abre la Calculadora y calcula ahí (aid calculator_next): 18 s, resultado correcto y
    visible. Se deja así (verificado por la app; cambiarlo mueve decisiones).
  - «Pon una canción de Queen»: `input_user_interrupted` porque el dueño abrió la tapa en ese momento (dicho por él);
    no es fallo. Sonó Queen; BAXY dijo «no pude comprobar que sonara» (límite conocido de anoche).

- Datos de sucesos de memoria (00:20-00:50, base 5017917f9): tras «conversación nueva» no busca nunca; 3 de 5 falsos
  (mundial 2022 «Francia», Copa América 2021 «Chile», Balón de Oro 2023 «Mbappé»). Con historial de búsquedas sí busca.
  Trivia estable (capitales, Luna, planetas): 18/18 bien de memoria.
  - C a489c28e1 (frase sin ejemplo): peor, no busca y pregunta «¿quieres que busque?». Descartado.
  - C2 9f7587350 (con ejemplo «mundial 2022»): 7/7 sucesos buscados y bien; «dato curioso» cae en la duda (p_call 0,31)
    y pregunta, 2/2. Causa: la palabra «datos» de la frase.
  - C3 9e14c2d1d (sin «datos»): 6/6 sucesos bien; datos curiosos de memoria falsos 2/3; al final vuelve a contestar de
    memoria un suceso con un detalle falso.
  - C4 1f47d6121 (+ «una curiosidad que te pidan»): en medida.
- Arranque: lo tecleado antes de que la mente esté lista (≈30-40 s) se queda en la caja (`data-ready=false`), no se
  pierde; el aviso dice «Escribe o di» en vez de «Cargando». Límite menor, sin arreglo.
- Clics no pedidos tras cumplir (base, 1 de 2 pasadas): «Abre la calculadora» pulsó «Es igual a» y «Borrar» ×3;
  «Abre el bloc de notas y escribe…» escribió y pulsó «Cerrar» (ventana cerrada). Sin arreglo aún.
- PC decisión v11 x3: A final8 194,33 → B nb-arr-junto 197,67 (Δ +3,33, IC95 [−0,33, +7,67]); equivocadas 32,3 → 30,0.
  v6 abierto s0 B = 625 (ref. final8 616,6). Baja V11D237 («qué modelo usas» → pregunta-eco por la regla de persona).

## Vuelta atrás
- Mente: `git -C D:\BAXYeval\entrega\BAXY-1.1.1-arr-9537b5f8b checkout --detach 5017917f9` y reiniciar BAXY.
- Más atrás: `python_path` del registro `%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json` a
  `...BAXY-1.1.1-final7-4530e077c\src` (copia en `entrega\respaldo-registro\`).

## Herramientas
Scratchpad de esta sesión: `cdp.py`, `probar_texto.py`, `probar2.py` (con reconexión), `ver.py`, `lanzar_debug.ps1`;
Python con `websocket`: `C:\Users\usuario\AppData\Local\Programs\Python\Python312\python.exe`.
