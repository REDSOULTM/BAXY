# Goal 03C — Cerrar el alcance y los restos del 03B

> **Esto es un goal, y no se cierra a la primera.** Se lanza y corre hasta
> cumplirse. No pares a pedir aprobación ni a preguntar; ante una duda, elige la
> opción más razonable, anótala y sigue.
>
> El 03B dejó el 90 % servido y **el alcance abierto**. Este goal existe para
> que el 04 no herede esa deuda. **No hay salida honesta de «nombrar lo que
> queda y pasar».** O lo cierras, o mides que un criterio concreto es
> inalcanzable con evidencia nueva — no con la del 03B.

## Dónde trabajas

Repositorio: `C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo`.
Rama: `main`. Modelo: **Grok 4.6**.

**Ojo con el nombre.** En la misma carpeta `Programacion` hay un repositorio
llamado `BAXY` a secas: ése es el intento anterior y es **fuente de herencia, no
tu sitio de trabajo**. Todo lo que escribas va en `BAXY Definitivo`.

Confirma al arrancar: `git rev-parse --show-toplevel` termina en
`BAXY Definitivo`. Lee `AGENTS.md`, `documentacion/00_IDENTIDAD.md`, este
fichero, `documentacion/base/03B_COMPRENSION_TECHO.md` §12, y las últimas
líneas de `documentacion/APLAZADOS.md`.

Permisos totales sobre este PC: descarga, instala, sobrescribe, borra lo que
sobre. **No preguntes.** Para sólo si vas a tocar datos personales del usuario u
otros proyectos de la carpeta `Programacion`.

Esfuerzo `high` de suelo; `/effort xhigh` sólo en el tramo que lo pida.
Busca con `grep` acotado a `src tests scripts main.py` y lee rangos con
`read_file`: en la shell no hay `rg`, es PowerShell, y
`run_terminal_command` es para git, pytest, dotnet y procesos. Las
corridas de medición van en segundo plano y se recogen con
`get_command_or_subagent_output`, sin sondear en bucle.

Sin subagentes: `spawn_subagent` hereda tu modelo y paga otra vez
contexto y razonamiento. El estado se deja escrito en el repositorio a
medida que avanzas. Tras cada paso medido: cifra en
`documentacion/base/03C_ALCANCE.md` (créalo al primer número), una línea en
`documentacion/APLAZADOS.md` por lo que no persigues, `git add` y `git commit`
que diga qué midió y cuánto dio, y `git push origin main` detrás —el dueño trabaja
en varias máquinas y lo que no está en `origin` no existe para las demás—.

---

## Qué es BAXY

Un compañero que vive en el PC de una persona y hace lo que le pide —tipo
Jarvis, local y privado—. Tiene carácter propio, es un «él», tutea, y confirma
lo que hizo comprobándolo. Cuando falla lo dice plano y con la causa. Nunca
inventa que hizo algo, nunca actúa sin que se lo pidan, nunca manda datos del
usuario fuera.

Todo está en `documentacion/00_IDENTIDAD.md`. **Es lectura obligatoria.** Si un
diseño tuyo la contradice, el que cambia eres tú.

## Las cinco leyes

1. **Hereda primero, estado del arte después, construye al final.** Que BAXY ya
   lo haga de una manera no es razón para conservarla.
2. **Nada de sobreingeniería.** Si añades una capa, retira la que sustituye, en
   este mismo goal.
3. **Sólo se arregla lo que bloquea.** Lo demás, una línea en
   `documentacion/APLAZADOS.md`.
4. **Lo más ligero que cumpla.** 4 GB de VRAM es el techo, no el objetivo.
5. **Arquitectura modular.** Una responsabilidad por pieza; el mecanismo de
   cambio, sólo en las piezas de `documentacion/03_COSTURAS.md`.

Consigna: quinta escritura, la más rápida — no porque haga menos, sino porque
no vuelve a descubrir lo que ya se descubrió.

## Los seis invariantes (no se re-derivan)

1. El catálogo tipado es la única fuente de operaciones. La mente propone, el
   kernel autoriza, el provider ejecuta.
2. Nada se afirma sin verificar.
3. Estados terminales honestos.
4. La confirmación se liga a la invocación exacta.
5. Cero respuestas visibles fijas.
6. Local y privado. El modelo corre en la máquina.

---

## El número de donde partes

Tres corridas sobre el corpus fresco
`artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl`
SHA-256 `761c1bc3b3facbf14a3aaafa09f24c0e5e0baaf8cebdd0edc7c2e648cb87413d`
(124 in-catalog, 36 out). **No cambies el corpus ni el marcador.**

| Corrida | Servidos | Fuera-de-catálogo honestas | p50 |
|---|---:|---:|---:|
| `goal03_rec5e2e8.json` | **112/124** | 24/36 | 1,50 s |
| `goal03_rec5e2e9.json` | **112/124** | 24/36 | 1,56 s |
| `goal03_rec5e2e10.json` | 110/124 | 21/36 | 1,60 s |

Mediana **112/124 = 90,3 %**. Reconocedor 0, recuperación 0.
`explicit_effects` 56/56. Cobertura 169/158/31 sello `dc0a7893…`. Banco
compuesto 6/15 misiones y 15/32 pasos. Pico VRAM 4026/4096 MiB.
Sobrecarga de la capa LLM p50 17 ms (`goal03_overhead_rec5e2e8.json`).

El 90 % **ya está**. El goal 03B no se puede cerrar porque el alcance no
cumple: **12–15 de 36** filas fuera de catálogo `acted` (el listón es **≤5**).
Ese es tu bloqueo. De paso, 12 filas in-catalog siguen fallando; no se las
dejas al 04.

El scorer cuenta `acted` con `_final_operations`: incluye `operation`,
`effect_operations` **e `intent_operations`**. Un `clarify` con
`intent=['task.create']` cuenta. **No relajes el scorer, no cambies la
definición, no descuentes los clarify.** El goal 03B midió 2–4 de 36 con esa
misma función; el 03B tardío subió a 12–15 al dejar de retirar el reconocedor
y al anclar más hojas. Tú bajas ese número **sin bajar de 112/124**.

---

## Objetivo único, en este orden

1. **Alcance: ≤ 5 de 36 `acted`** en el scorer actual, en tres corridas, sin
   que la mediana in-catalog baje de 112/124.
2. **Las 12 filas in-catalog que aún fallan**, servidas o con un diagnóstico
   medido de por qué no se pueden servir *sin* romper el alcance. No las
   aplaces al 04.
3. Si 112 aguanta y el alcance cierra, **sigue si ves palanca** para subir
   del 90 %. No pares en 112 por haberlo tocado.

Los tres se miden juntos. Un cambio que baje los `acted` de 12 a 4 y deje
el fresco en 108/124 es un rechazo. Un cambio que suba a 118 y deje 14
`acted` también.

---

## Las filas, nombradas

Telemetría de referencia: `artifacts/development/goal03_rec5e2e8.telemetry.jsonl`
(y las de `rec5e2e9`, `rec5e2e10` para ver cuáles son estables).

### Fuera de catálogo que `acted` en las tres corridas (estables — éstas mandan)

| id | Texto | Qué propone | kind típico |
|---|---|---|---|
| ooc-01 | pide un taxi para las ocho | `task.create` | clarify |
| ooc-07 | upload this video to youtube | `media.play.youtube` | clarify |
| ooc-17 | grabame la pantalla en video | `capture.active.window` | clarify |
| ooc-18 | connect to my work vpn | `wifi.connect.named` | clarify |
| ooc-19 | cloname el disco duro a otro | `filesystem.copy` | clarify |
| ooc-23 | editame el video y quitale los ultimos diez segundos | `media.seek.relative` | clarify / a veces action |
| ooc-24 | convierteme este pdf a word | `office.document.create` | **action** |
| ooc-31 | unlock my phone for me | `system.power` | clarify |
| ooc-33 | imprimeme en 3d esta figura | `peripheral.print` | clarify |

Casi siempre `acted` (2 de 3): ooc-20 `riega las plantas del balcon` →
`routine.read`; ooc-22 `download this series over torrent` →
`game.install.cancel.active` (**action/plan**).

Intermitentes: ooc-03 pizza, ooc-04 call my mother, ooc-08 formatea el
pendrive, ooc-14 desfragmenta, ooc-27 fondo de escritorio, ooc-29 flores,
ooc-32 plomero, ooc-35 partición.

**ooc-24 y ooc-22 son action.** El resto son clarify con intención: si la
persona dice que sí, BAXY ejecutaría un efecto que nadie pidió de verdad
(un taxi no es una tarea; un PDF→Word no es crear un documento de Office
vacío; desbloquear el teléfono no es `system.power` de este PC).

La identidad: BAXY dice que no a lo que no sabe hacer, y no propone como
efecto del catálogo un sustituto cercano. Ése es el mismo invariante que
el verificador de identidad intentó y que el 03B retiró porque tiraba
hojas *dentro* de catálogo. Aquí el fallo es el inverso: el modelo (y a
veces el reconocedor) **publica una hoja del catálogo para un pedido que
no está**.

### In-catalog que fallan en las tres corridas (estables)

| id | Texto | Esperada | Qué suele pasar |
|---|---|---|---|
| cmp-01 | abre spotify y ponme musica | `app.open` + `media.play.query` | veto de dominio sobre el compuesto |
| fs-04 | manda a la papelera el archivo notas.txt de descargas | `filesystem.known.trash.named` | decide `filesystem.trash.commit` |
| inp-06 | scroll down a bit | `input.pointer.control` | decide `browser.page.read` / conversación |
| net-01 | tengo internet o no | `network.status` | veto: un hermano ungrounded tumba la lista |
| net-10 | chequea si el internet anda | `network.status` (+ ping) | `total_recovery` |
| win-01 | que tengo en primer plano ahora | `window.active` | `information_question` / lista basura |

### In-catalog intermitentes (2 de 3 o 1 de 3)

aud-01 `che ponelo mas bajito que estoy en una llamada` → a veces
`audio.status` en vez de `audio.volume.adjust`. aud-03/aud-07 mute.
bak-01 backup de documentos. gam-04 para la descarga de Steam. med-04
Bad Bunny en Spotify. pkg-01 install vlc. sys-10 con qué usuario estoy.
tsk-02 what is on my to do list. cap-02/cap-04/win-07 en una sola
corrida.

No las ignores porque sean intermitentes: la mediana 112 se cae a 110
cuando coinciden (rec5e2e10).

---

## Cómo atacar, y qué no repetir

Una cosa cada vez, número antes y después. Tres corridas para declarar
un cambio bueno (±3 de dispersión medida).

**Alcance primero.** Baja los 9 `acted` estables. Si al bajarlos se cae
el 112, el cambio se revierte y se anota. Las palancas razonables:

- El pedido fuera de catálogo tiene que **abstenerse o conversar sin
  publicar `intent_operations` de una hoja del catálogo**. Un clarify
  «¿quieres que cree una tarea?» para un taxi sigue siendo `acted`.
- `ooc-31` «unlock my phone»: `system.power` ya exige máquina y niega
  teléfono en el dominio; aun así sale clarify con esa hoja. El fallo
  está *después* del dominio o en un camino que no lo aplica. Mídelo
  en el turn-audit antes de añadir regex.
- `ooc-24` PDF→Word: `office.document.create` está grounded de más.
- `ooc-17` grabar pantalla en video ≠ captura de ventana.
- `ooc-07` upload to youtube ≠ `media.play.youtube`.

**In-catalog después, o en el mismo cambio si no se pisan.** cmp-01 es
el compuesto Spotify+música (el banco compuesto ya subió a 6/15; no lo
bajes). net-01 es el veto all-or-nothing: filtrar hojas ungrounded se
midió offline sobre rec5e2e7 y **abriría** ooc-09/11/13/14/15/22/25/30.
No lo hagas. Arregla el dominio de los hermanos o que el modelo no los
publique juntos, no la política de «si uno falla, caen todos» salvo que
midas el oos *y* el fresco juntos y ambos cumplan.

**Offline antes de e2e.** Sobre la telemetría que ya está en disco. Una
corrida son ~7 minutos y no se corren dos a la vez (se pisan el audit y
sale JSONDecodeError).

### Ya medido y rechazado — no lo repitas

Está en `documentacion/APLAZADOS.md`. Lo que más te tienta y ya está
muerto:

- Filtrar hojas ungrounded en vez de vetar la lista entera.
- Exentar `read_only` de la puerta de dominio («¿Cómo está la red
  neuronal?» → `network.status`).
- Toda la pila FunctionGemma del router heredado (abstain_head,
  mMARCO, deícticos, splitter, LoRAs, When2Call, xLAM, Qwen3-Reranker).
- Cinco gates léxicos. Un sexto no.
- Abstención BGE-M3 por familia, clasificador 32 vías, MTOP.
- `tool_choice: required`. Unión ranker+E5 en el 4B.
- Aflojar el verificador de recuperación de conversación a efecto
  (89 → 81). Shortlist 28 → 48.
- Volver a poner el verificador de identidad del reconocedor como
  retirada: el 03B lo quitó porque tiraba hojas verdaderas
  (app.open, note.create, task.create). Si lo reactivas, mide las
  dos direcciones.

Si crees que uno estaba mal medido, vuelve a correrlo **diciendo por
qué** y publica los dos números.

### Manos libres, con el mismo recinto

Puedes rehacer reconocedor, recuperador, decisor, prompt, vetos y
camino de decisión. No se tocan: los seis invariantes, los tres ceros,
la cobertura `dc0a7893…`, el banco compuesto (no bajar de 6/15 y
15/32), el corpus, el marcador, VRAM ≤ 4 GB, el listón de 3 s.

`.gitattributes` declara eol=lf. Si tocas `src/baxy_mind`, repina
wake-validation-program-tree (cinco programas de
`experiments/stt_quality`) y los SHA de
`tests/test_price_v8_veto_damage_by_cause.py` si cambian
`__main__.py` / `llm.py`.

Pytest dueño: el venv viejo
`C:\Users\usuario\Desktop\ETC\Programacion\BAXY\experiments\mind_router_spike\.venv\Scripts\python.exe`.

Medición:

```
py -m experiments.mind_router_spike.run_goal03_comprehension --label <nombre>
py -m experiments.mind_router_spike.measure_goal03_catalog_coverage --label <nombre>
py -m experiments.mind_router_spike.run_goal03b_compound_missions --label <nombre>
```

Pytest: `-q`. dotnet: `--nologo -v:minimal`. No dos mediciones Goal 03
a la vez.

---

## Criterios de cierre

No se cierra con skip, xfail, umbral relajado, fallback, ni redefiniendo
`acted`.

- [ ] **≤ 5 de 36 `acted`** fuera de catálogo, misma función que
      `run_goal03_comprehension.py`, en **tres** corridas. Las 9
      estables de arriba no pueden seguir `acted`.
- [ ] **Mediana ≥ 112/124** en esas mismas tres corridas, mismos bytes,
      partido por causa. Si sube, mejor; si baja de 112, no has cerrado.
- [ ] Las 6 filas in-catalog estables de arriba, servidas o con
      diagnóstico medido de por qué no, **sin** haberlas empujado al 04.
      Las intermitentes no pueden ser las que tumben la mediana.
- [ ] Cobertura 169/158/31 sello `dc0a7893…` antes y después.
- [ ] Banco compuesto ≥ 6/15 misiones y ≥ 15/32 pasos.
- [ ] Pico VRAM ≤ 4 GB durante un turno con el modelo cargado, medido.
- [ ] Sobrecarga frente a inferencia pura (mismo prompt/modelo/tokens),
      desglosada: el Δ de 17 ms de la capa LLM sigue siendo la referencia;
      si añades una etapa, dice qué compra.
- [ ] Listón de silencio 3 s (p50 del turno). Hoy 1,50–1,60 s.
- [ ] Tres ceros intactos.
- [ ] `03_COSTURAS.md` con las filas que toques.
- [ ] `documentacion/base/03C_ALCANCE.md` con las cifras, y
      `documentacion/base/03B_COMPRENSION_TECHO.md` §12 actualizado para
      que no mienta.
- [ ] **Publicado.** `git status --short` vacío y
      `git rev-list --count origin/main..main` en **0**: todo lo del goal está en
      `origin/main`. Un goal con el trabajo sólo en este PC no está cerrado, por
      verdes que estén los demás criterios.

## Cuándo puedes cerrar sin el alcance en ≤5

Sólo si mides un techo **nuevo** (no el del 03B) y demuestras que bajar
de 12 `acted` a 5 **cuesta** más de 112, o abre un cero, o tira la
cobertura. Con el número de las dos direcciones. El dueño decide entonces;
tú no pases al 04 con el 12–15 todavía abierto «porque el 90 % ya está».

## Cierra

Publica el resultado. Un 112/124 con 4/36 `acted` cierra el capítulo de
comprensión. Un 118/124 con 4/36 también, y es mejor. Un 112/124 con 12/36
es el 03B otra vez: no has cerrado.

Si la sesión se queda sin cuota: `git log --oneline -20`,
`git status --short --branch`, cola de `APLAZADOS.md`, y
`documentacion/base/03C_ALCANCE.md`. El siguiente agente pega este mismo
prompt.
