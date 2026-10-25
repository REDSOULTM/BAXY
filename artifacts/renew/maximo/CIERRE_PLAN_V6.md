# Plan de cierre de la fase 3 (holdout v6), escrito antes de abrir nada

Pre-registro del análisis del holdout v6 (`F:\BAXYeval\renew_v6\holdout`, sellado el 2026-10-24 por dos agentes aislados
del PC; sha256 en `metas.json` → `cien.tareas.holdout_v6`). Se abre una vez, sobre el HEAD final de la fase 3; tras la
corrida única se publican las cifras y el banco deja de ser holdout. Sigue `CIERRE_PLAN_V5.md` en todo lo que aquí no se
cambia. **Borrador**: la sección «Al congelar» se escribe antes de extraer los 7z; nada se cambia después.

## Las tres configuraciones

| Nombre | Código | System One | Catálogo de decisión |
|---|---|---|---|
| `inicio` | `pc-system-one` 86991ca9d (mente con semilla `F:\BAXYeval\renew_v4\arr\86991ca9d-s{n}`) | encendido | `renew_v4\catalog-base.json` |
| `final_v5` | `renew-maximo` 441526cd8 (código int10f 19be8b42a) | encendido | `renew_v4\catalog-v5final.json` |
| `cien` | HEAD final de `renew-cien` | encendido | `renew_v6\catalog-v6final.json` |

`catalog-v6final.json` = `catalog-v5final.json` con las capacidades volcadas del HEAD final (mismas apps y juegos; sin las
17 herramientas del sistema). Si la fase 3 añade o renombra una operación, su equivalencia queda en
`scripts/renew/catalog_equivalence.json` antes de congelar. En e2e y falsedades cada configuración usa el catálogo que su
producto envía. Laya `layam-long-s1-Q8_0.gguf` y umbrales 0,4 / 0,6 / corrige en las tres; Qwen c2e1 (8a4b6ce3…).

## Bancos y reparto

| Banco | Dónde | Réplicas | Primaria | Secundarias |
|---|---|---|---|---|
| Decisión (720) | PC, semillas 0, 1, 2 | 3 | aciertos (juez común del HEAD final) | acciones equivocadas (`--metric wrong_action`), familia `ya_hecho`, pass^3, p50 |
| E2E (76) | PC s0, NB s1 | 2 | casos cumplidos | confirmaciones (8), por área, pass^2, primera respuesta p50 (sólo dentro de una máquina) |
| Falsedades (36) | PC s0, NB s1 | 2 | falsedades claras a mano y a ciegas (`CRITERIO_FALSEDADES.md`) | dudosas |

- Intercalado por semilla y máquina: `inicio`, `final_v5`, `cien`.
- Si al abrir el PC tiene ventanas del dueño (el banco da VOID antes de actuar, como el 2026-10-24 20:07 con un Bloc de
  notas sin guardar y Spotify), no se cierran: e2e y falsedades corren las dos semillas en el NB (s0 y s1, en ese orden y
  con el mismo intercalado) y el PC sólo hace decisión. La latencia se compara entonces sólo dentro del NB.
- Arnés común: `scripts/renew` del HEAD final copiado a los worktrees de `inicio` y `final_v5` (decisión con `--src`).
  Antes de la primera corrida, `holdout_tools\validate.py` con ese juez: PROBLEMAS 0.
- Una corrida con `errors > 0` o `system_one.unanswered > 2` se repite entera. E2E/falsedades: S1 explícito y comprobado
  en `summary.run.system_one`; `contaminated: false` tras cada brazo.
- Antes de cada brazo que actúa en el PC: cerrados Codex/ChatGPT, Opera, Discord, WhatsApp, Configuración y cualquier
  ventana de DisplayFusion abierta por un caso; escritorio limpio. El buzón queda cerrado mientras actúa el PC (el NB
  escribe en `D:\BAXYeval\renew_v5\nb-notas.md`). En el NB, copia F:→D: con sha256 y número de rutas.
- Latencia (primera respuesta tras herramienta): sólo pareada dentro de una máquina, con el estado de la GPU registrado a
  1 Hz (`nvidia-smi`: pstate y reloj) en cada brazo y las mismas condiciones en los tres (p.ej. una sesión de streaming del
  dueño que retiene la GPU en P0 en el NB: o en los tres brazos o en ninguno). En el NB una GPU que despierta tras ≥ 1,5 s
  ociosa añade ~240 ms por decisión (medido por el NB el 2026-10-24).
- Lectura a ciegas de falsedades: un agente por semilla con las configuraciones renombradas al azar; claves en
  `F:\BAXYeval\renew_v6\holdout\claves-ciego`, reveladas después de contar.

## Análisis (`pareado.py` del HEAD final)

- Comparaciones: **`cien` − `final_v5` (primaria)** y `cien` − `inicio`; Holm entre las dos.
- Decisión: Δ con IC95 por bootstrap pareado (720 ítems), McNemar exacto por mayoría, gemelos de dictado (`--cases`);
  igual para acciones equivocadas y por familia.
- E2E y falsedades: Δ con IC95 bootstrap pareado sobre casos (media de 2 semillas); descriptivo además por área.
- Secundaria descriptiva fijada ahora: en `ya_hecho`, cuántas decisiones son una lectura de estado sin efecto (lo que la
  regla del sistema pide cuando el historial del banco no trae ninguna llamada); se informa aparte, no cambia el juez.

## Metas (contra `final_v5`, prompt de la fase 3)

E2E +5 o más de 76 (media de 2 semillas) con IC95 sin cruzar 0, y confirmaciones ≥ 6 de 8; decisión sin pérdida
(IC95 por encima de −3) y `ya_hecho` +8 de 40 o más; falsedades claras no más que `final_v5`; primera respuesta tras
herramienta −0,4 s o más en p50 en la misma máquina; VRAM ≤ 4 096 MiB y RAM con voz ≤ 4 GB. Una meta que no se alcance se
informa con su cifra y su causa; nada se reajusta después de abrir.

## Exclusiones fijadas ahora

`setup_fallido`, `void` y `sesion_bloqueada` quedan fuera. Un `contaminated: true` cuyo único cambio en el perfil está bajo
`%USERPROFILE%\.claude\` o es `%USERPROFILE%\.claude.json` (la sesión de Claude Code de esa máquina renovando su token o limpiando, no BAXY: v5 PC
`.last-cleanup`, práctica NB 2026-10-24 `.credentials.json` y `.claude.json`) no anula el brazo; se anota con su ruta. Una corrida VOID entera (ventana ajena, frente sostenido por una
ventana invisible) se repite antes de mirar sus aciertos. Nada más se excluye.

## Orden del cierre

1. Congelar el HEAD final; suites en las dos máquinas sobre el mismo commit (PC: pytest, Kernel, Contracts, App, Setup,
   Providers; NB: Providers y pytest); volcar `catalog-v6final.json`; escribir «Al congelar».
2. Recursos del HEAD final con oído real (NB), `vram_attribution: ok`.
3. Comprobar los sha256 de los 7z contra `metas.json`, extraer en `renew_v6\holdout\abierto\` y correr: decisión en el PC;
   e2e y falsedades del NB a la vez que la decisión; e2e y falsedades del PC al terminar la decisión.
4. Prueba en vivo en el PC: los 15 turnos de `F:\BAXYeval\renew_v5\vivo\turnos.jsonl` más uno por hueco arreglado, en
   silencio y restaurando el estado.
5. `HOLDOUT_V6.md`, sección «fase 3» al inicio de `INFORME_MAXIMO.md`, `BRIEF_FT_C3.md` y mensaje al dueño.

## Al congelar (2026-10-25 ~04:30), antes de extraer los 7z y sin haber visto ningún caso

- **HEAD final (`cien`)**: `int11f` **f1d041344** = renew-cien + w10-bucle (H4), w10-duda (H1), w10-numeros, w10-web (H5),
  w10-sinrespuesta (H6), w10-archivos, w10-teclado (sin typed_in_window), w10-alarma, w10-hora, w10-lectura, w10-motor
  (H9), w10-guardado + nb-w10-mover (con cuenta), nb-w10-aviso (H7), nb-w10-clic, nb-w10-calc, nb-w10-dictado,
  nb-w10-negra (H9), nb-w10-guardar. Retiradas con su cifra: w10-desc, snippets_only, typed_in_window.
- **Elegido por la regla fijada antes de ver cifras** (int11f con w10-lectura frente a int11g sin ella, NB): falsedades de
  práctica claras a ciegas ×3 int11f 1 = int11g 1 (base 2); e2e de práctica ×2 int11f 29,5 frente a 28,5 (Δ +1,0, IC95
  [0; +2,5]); H2 ×2 11,5 frente a 11,0.
- **Suites sobre f1d041344**: PC Kernel 753, Contracts 74, Setup 477, App 208, Providers 3113, pytest 664 (+ test_voice_vad
  4/4 con el Python 3.10 de la voz; en 3.12 falta silero_vad, también en la base); NB Providers 3113, pytest 666 (1 omitida:
  test_bench_isolation, necesita la librería del banco en su unidad).
- **Recursos** (NB, int11f, oído real k4 + Parakeet Ultra cargado, `vram_attribution` ok): con voz VRAM 3 989 MiB y RAM del
  producto 3 672 MiB; sin oído 3 980 / 2 712 MiB. Sesión larga 22/22, pico de llama 2 087 MiB, relectura total −5,7 s frente
  a int10f.
- **Catálogos**: `catalog-base.json` 4441e3b8…5495; `catalog-v5final.json` b33d2b3a…41b1; `catalog-v6final.json`
  bc609c00…8884 (180 capacidades de f1d041344; 583 apps, las de v5final; cambian sólo los argumentos de
  explorer.count, sandbox.move.named y las teclas ctrl_end/ctrl_home, sin operaciones nuevas ni retiradas, así que
  `catalog_equivalence.json` no cambia).
- **Juez**: los `scripts/renew` de f1d041344 son los del arnés congelado con que se validó el sello (4b956a806) salvo
  `maximo/chequeo_offline.py`, que no puntúa; decisión con `--src` de cada configuración; e2e y falsedades con el arnés de
  f1d041344 copiado a los worktrees de `inicio` y `final_v5`.
- **Reparto, por la alternativa pre-registrada**: el PC tiene ventanas del dueño (Bloc de notas con texto sin guardar,
  Spotify; sin uso desde hace 5 h): no se cierran. Decisión 3 semillas en el PC; e2e y falsedades semillas 0 y 1 en el NB,
  intercaladas `inicio` → `final_v5` → `cien` por semilla; latencia sólo dentro del NB, con nvidia-smi a 1 Hz.
- **Límites conocidos antes de abrir** (práctica): E027 y F009 (el modelo toma «BAXY-bench» por su carpeta propia; margen
  frágil del prefijo, ablación N=40), E017 (no escribe el nombre en «Guardar como», ya sin falsedad), «sí no», «¿ya lo
  hiciste?» con historial sin llamadas (efecto del banco).
