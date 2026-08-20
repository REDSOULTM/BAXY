# Prompt para GPT-5.6 Sol — retomar la comprensión hasta el 90 %

Escrito para pegarse entero en una sesión nueva de Codex con **GPT-5.6 Sol,
`reasoning.effort: high`**, sobre una suscripción de 20 $. Está pensado para
**agotarse en una cuenta y continuar en la otra sin perder nada**: todo el estado
vive en el repositorio, no en la conversación.

El repositorio es privado: `https://github.com/REDSOULTM/baxy-definitivo`.

---

## Antes de nada: qué NO viaja por git

El repositorio trae el código, las pruebas y toda la evidencia medida. **No trae
lo que hace falta para medir**, y `assets.manifest.json` lo dice explícitamente:
*«BAXY no descarga modelos automáticamente»*. En un PC nuevo faltan:

| Pieza | Qué es | Cuánto |
|---|---|---|
| `Qwen3-4B-Q4_K_M.gguf` | el decisor, SHA-256 `7485fe6f…` | 2,5 GB |
| `llama-server.exe` (llama.cpp b9980, CUDA 12.4) | el runtime de inferencia | ~50 MB con sus DLL |
| `%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json` | el manifiesto que ata las dos cosas y el `src` de este repositorio | un JSON |

Sin esas tres, `run_goal03_comprehension.py` no arranca, y **este goal es una
medición**: sin poder medir, la sesión no puede hacer nada útil. Cópialas por USB
o por red desde este PC antes de empezar.

---

## Prompt de arranque en el PC nuevo

Pégalo primero. Sólo prepara el terreno y comprueba que se puede medir; **no toca
el producto**.

```
Vas a preparar un PC nuevo para trabajar en BAXY. No cambies nada del producto
todavía: este paso sólo deja el terreno listo y comprueba que se puede medir.

1. Clona el repositorio privado, con rutas largas habilitadas — sin esto el clon
   falla con "Filename too long" sobre los artefactos de nombre largo:

   git config --global core.longpaths true
   git clone https://github.com/REDSOULTM/baxy-definitivo.git "BAXY Definitivo"
   cd "BAXY Definitivo"
   git log --oneline -8

   El último commit tiene que ser el prompt de Sol para retomar la comprensión.
   Son ~100 MB: tarda.

2. Comprueba qué falta para poder medir. Desde la raíz del repositorio:

   py -c "import os,sys,pathlib; sys.path.insert(0,'src'); from baxy_mind.assets import DEFAULT_DESCRIPTOR, load_asset_descriptor, resolve_asset; root=pathlib.Path('.').resolve(); d,_=load_asset_descriptor(DEFAULT_DESCRIPTOR, repository_root=root); [print(('OK   ' if resolve_asset(n, repository_root=root).path else 'FALTA'), n) for n in d['assets']]; m=pathlib.Path(os.environ['LOCALAPPDATA'])/'BAXYRuntime'/'mind-runtime-v1.json'; print(('OK   ' if m.is_file() else 'FALTA'), 'runtime manifest')"

   De todo lo que salga, para este goal SÓLO importan tres: conversation_model,
   llama_server y el runtime manifest. Wake, TTS, visión y el STT de streaming no
   los toca este goal: que salgan FALTA es normal.

3. Si falta alguno de esos tres, PARA y dilo. No los descargues ni los sustituyas
   por otro modelo: el decisor está declarado con su SHA-256 y cambiarlo invalida
   toda la comparación. Hay que copiarlos del PC original:
     - el GGUF y llama-server, a donde prefieras;
     - y después escribir %LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json con las
       rutas de ESTE PC. El campo python_path tiene que apuntar al src de este
       clon, o cada medición ejecutará el baxy_mind equivocado — es un fallo que
       ya costó una campaña entera y está documentado en base/03_COMPRENSION.md §3.

4. Compila el núcleo, que la medición lo arranca para leer el catálogo:

   dotnet build Baxy.slnx -c Release --nologo -v:minimal

5. Corre la medición de referencia y compárala con lo publicado:

   py -m experiments.mind_router_spike.run_goal03_comprehension --label arranque

   Tiene que dar del orden de 81-84 de 124 dentro de catálogo y 26-28 de 36 de
   abstención honesta. Si da eso, el PC está listo. Si da mucho menos, algo del
   punto 3 está mal apuntado: no sigas, arréglalo.

6. Cuando el punto 5 cuadre, dilo con el número exacto y para. El trabajo del goal
   se lanza con el otro prompt, el que está en
   documentacion/sprints/03B_PROMPT_SOL.md.
```

---

## El prompt del goal

```
Trabajas en C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo, rama main.
Comprueba que estás ahí: `git rev-parse --show-toplevel` termina en "BAXY
Definitivo". En la misma carpeta Programacion hay otro repositorio llamado BAXY a
secas: es el intento anterior, fuente de herencia, NO tu sitio de trabajo.

TU OBJETIVO, literal y único:
≥ 90 % sobre el corpus de paráfrasis frescas del goal 03 —
artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl, SHA-256 761c1bc3…,
124 filas dentro de catálogo y 36 fuera — puntuando esos mismos bytes, con la tasa
partida por causa y la latencia medida al lado. 90 % son 112 filas de 124.
No se cierra con skip, xfail, umbral relajado ni fallback. No cambies el corpus ni
el marcador.

SEGUNDO OBJETIVO: LA SOBRECARGA, MEDIDA Y JUSTIFICADA — no un tope
Usamos un modelo pequeño PARA QUE SEA RÁPIDO. La latencia la pone el modelo: si
eliges uno pequeño, el turno debería sentirse pequeño. Si el modelo contesta en
800 ms y BAXY tarda tres segundos, pagaste el precio del modelo pequeño —menos
capacidad— y no te llevaste lo que compraste.

Pero la sobrecarga NO es un pecado: es un presupuesto. Un segundo extra que compra
diez puntos de comprensión está bien gastado. Un segundo que no compra nada es
robo. Lo que se prohíbe es lo segundo.

Por eso NO hay tope duro. Hay una obligación:

  sobrecarga = p50(turno completo de BAXY) − p50(inferencia pura, MISMO prompt)

La inferencia pura se mide con el mismo binario, el mismo modelo y los mismos
tokens —prefill incluido—, llamando a llama-server directamente sin pasar por
BAXY. Contra un prompt distinto el número no significa nada.

LA REGLA: se mide siempre, se desglosa por etapa, y CADA etapa que suma tiempo
dice qué compra. Una etapa que cuesta tiempo y no mueve ningún número se retira
— eso es la ley 2 otra vez, vista desde el reloj.

Lo que persigues: acercarte al tiempo del modelo tanto como se pueda **sin perder
lo que la etapa aporta**. Puedes gastar de ese presupuesto a propósito si compra
acierto, y decirlo. Lo que no se acepta es sobrecarga que nadie ha justificado, o
que convierte el turno en un múltiplo del modelo en vez de una fracción.

Y no confundas esto con el listón de silencio: son cosas distintas. El silencio
son 3 s sin que BAXY dé señal, y viene de la identidad —el dueño cierra la ventana
y lo hace a mano—. Ese sigue en pie, y se cumple hablando antes de terminar si
hace falta, no acelerando a costa del acierto.

El precedente que hace esto importante: Carter medía 16 s por turno con un modelo
que tardaba 4,26. Diez segundos eran capas propias que nadie había justificado
nunca. Cada capa que no retiras se paga en el reloj.

TERCER OBJETIVO: cabe en el equipo
Pico de VRAM ≤ 4 GB durante un turno, con el modelo cargado. Medido, no estimado.
BAXY corre en el portátil de una persona normal y compite con lo que esa persona
está haciendo de verdad.

LOS TRES SE MIDEN JUNTOS. Un cambio que sube el acierto y dobla la latencia no es
una mejora: es un intercambio, y tienes que verlo para poder rechazarlo.

LEE ESTO ANTES DE TOCAR NADA, en este orden:
1. AGENTS.md — dónde estás, las cinco leyes, la escalera de validación.
2. documentacion/00_IDENTIDAD.md — qué es BAXY. Si tu diseño la contradice, cambias tú.
3. documentacion/sprints/03B_COMPRENSION_TECHO.md — tu goal.
4. documentacion/base/03_COMPRENSION.md y documentacion/base/03B_COMPRENSION_TECHO.md
   — todo lo que ya se midió. Es la parte cara: cada línea costó una corrida.
5. documentacion/APLAZADOS.md — lo visto y no perseguido, con sus trampas.

DÓNDE ESTÁ EL NÚMERO HOY
82 de 124 = 66,1 % (tres corridas: 81, 82, 84), desde 45,2 %. El techo con
decisión perfecta y sin un solo veto es 111/124 = 89,5 %, porque hay 13 filas que
nunca llegan al decisor con la operación correcta disponible — las mismas 13 en
seis corridas:
  reconocedor:  app-01 med-05 fs-03 per-01 cmp-04
  recuperación: sys-04 net-02 med-01 tsk-01 clp-02 clp-03 inp-03 cal-02
Están nombradas una a una en base/03B_COMPRENSION_TECHO.md §6.
Para 112 tienes que mover ese suelo Y la decisión, que hoy pierde 21 de 124 y en
8 a 11 de esos casos elige una hermana de la operación correcta.

TIENES LAS MANOS LIBRES
Mucha gente ha tocado este código y eso NO te limita. Puedes rehacer el
reconocedor, el recuperador, el decisor, el prompt de política de turno, las
puertas y vetos, la forma del catálogo o el camino de decisión entero. Ninguna
conclusión anterior te obliga — incluida la de que el 90 % no se puede.
Lo único que no se toca: los seis invariantes de arquitectura, los tres ceros, la
cobertura y la compuerta verde.

Pero libertad no es amnesia. La lista de abajo es un mapa de callejones sin
salida, no una valla: no repitas un experimento ya corrido para llegar al mismo
sitio. Si crees que uno estaba mal medido, vuelve a correrlo DICIENDO POR QUÉ y
publica los dos números.

YA MEDIDO Y RECHAZADO — no lo repitas, es la forma más cara de perder el goal:
- Cinco gates léxicos (R116, R117, R124 ×2, R126). No escribas un sexto.
- Abstención semántica: BGE-M3 por familia (R236) y clasificador de 32 vías (R250).
- Clasificador supervisado sobre MTOP, 23.661 filas: 0,98 AUC en su distribución,
  0,58 en paráfrasis libre.
- Gate derivado del catálogo: sobreveto de 224/560 a 385/560.
- tool_choice: required: +3 decisiones crudas, −8 abstenciones honestas.
- Exentar read_only de la puerta de dominio: +8 filas, refutado por
  «¿Cómo está la red neuronal?» → network.status.
- La contrapositiva como segunda opinión: el modelo dice que sí a las dos lecturas,
  0 de 43 filas sobrevivían.
- Preguntarle al catálogo en toda conversación unsupported del decisor: 8 de 36
  abstenciones honestas convertidas en preguntas, cero filas recuperadas.
- Selección paramétrica en dos etapas (familia y luego hoja): acierta 13 de las 40
  perdidas y ROMPE 10 de 30 que ya se servían, 1,24 s por turno.
- Selección de la hoja dentro de la familia ya nombrada: mediana 82,5 contra 82 en
  siete corridas, p50 de 2,30 a 2,62 s. No paga.
- Aflojar el verificador de la recuperación de conversación a efecto: 89 → 81 de
  124, abstención 28 → 24, efectos no pedidos 3 → 5.
- Shortlist de 28 a 48 candidatos: ofrece 3 más y decide 3 peor, neto −2.

LO QUE NO PUEDES ROMPER
- Los tres ceros. Las decisiones que habrían ejecutado un efecto no pedido están
  hoy en 2–4 de 36 y no pueden subir de 5. Sin la puerta de dominio son 26 de 36.
- La cobertura no baja: 169 operaciones, 158 alcanzables, 31 familias, sello
  dc0a7893…. Publícalo antes y después con
  `py -m experiments.mind_router_spike.measure_goal03_catalog_coverage --label X`.
- El banco de misiones compuestas no baja: hoy 5/15 misiones y 13/32 pasos.
  `py -m experiments.mind_router_spike.run_goal03b_compound_missions --label X`.
- El listón de silencio: 3 s. Hoy p50 2,30 s y p90 2,92 s con el escritorio
  residente; 4,14 s y 7,14 s con la persona usando el PC.

CÓMO MIDES
  py -m experiments.mind_router_spike.run_goal03_comprehension --label <nombre>
Deja artifacts/development/goal03_<nombre>.{json,telemetry.jsonl,turn-audit.jsonl}.
Una corrida son ~7 minutos. La dispersión medida es ±3 filas sobre 124: ningún
cambio se declara bueno con una sola corrida, hacen falta tres.
Antes de construir nada, mide la idea offline sobre la telemetría que ya está en
disco — así se descartó casi todo lo de la lista de arriba sin gastar una corrida.

TRAMPAS DE ESTA MÁQUINA, medidas y documentadas
- NO corras dos mediciones a la vez: se pisan el fichero de audit y el error que
  sale es un JSONDecodeError, no un error de recursos.
- .gitattributes declara eol=lf y Python en Windows escribe CRLF: normaliza a LF
  todo fichero que regeneres, o su SHA-256 muere en el primer checkout limpio.
- El tope de candidatos está escrito dos veces: planner.MAX_SHORTLIST_OPERATIONS
  y un 28 literal en _turn_candidates de llm.py. Mover sólo uno mata cada turno.
- Si tocas src/baxy_mind, dos sellos se ponen rojos y hay que repinarlos nombrando
  la razón: tests/test_price_v8_veto_damage_by_cause.py (los SHA-256 de
  __main__.py y llm.py) y wake-validation-program-tree (los cinco programas de
  experiments/stt_quality).

CÓMO TRABAJAS
- Una cosa cada vez, con el número antes y después. No acumules cinco cambios.
- Ley 2: si añades una capa, retira la que sustituye, en el mismo cambio.
- Sin subagentes. Consumen cuota y aquí la cuota es el límite.
- Lee los textos visibles, no sólo los contratos: el goal 03 publicó «los tres
  ceros intactos» y era falso porque BAXY inventaba el estado de la máquina.

CÓMO ESCRIBES EL ESTADO — esto es lo que te deja sobrevivir a quedarte sin cuota
Después de CADA paso medido, sin excepción y antes de empezar el siguiente:
1. Actualiza documentacion/base/03B_COMPRENSION_TECHO.md con la cifra nueva.
2. Anota en documentacion/APLAZADOS.md, en una línea, lo que viste y no perseguiste.
3. `git add` y `git commit` con un mensaje que diga QUÉ midió y CUÁNTO dio.
El commit es tu memoria. Si la sesión muere a mitad, lo que no esté commiteado no
existe.

SI ESTA SESIÓN SE QUEDA SIN CUOTA
La siguiente sesión —en la otra cuenta— arranca pegando este mismo prompt otra
vez, y lo primero que hace es:
  git log --oneline -20
  git status --short --branch
  tail -40 documentacion/APLAZADOS.md
  documentacion/base/03B_COMPRENSION_TECHO.md, sección 12
Con eso sabe qué se midió, qué dio y dónde se quedó. No repitas nada que ya tenga
su cifra publicada.

CRITERIOS DE CIERRE — los tres números, juntos
- ≥ 90 % (112 de 124), partido por causa.
- Sobrecarga medida contra la inferencia pura del mismo prompt, con p50 y p90 y en
  los dos estados del equipo, DESGLOSADA POR ETAPA y con lo que compra cada una.
  Ninguna etapa sobrevive sin decir qué mueve.
- El listón de silencio de 3 s, cumplido — hablando antes de terminar si hace falta.
- Pico de VRAM ≤ 4 GB durante un turno.
- Cobertura, banco de misiones compuestas y tres ceros: no bajan.
- Compuerta verde.

CUÁNDO PUEDES CERRAR SIN EL 90 %
Sólo habiendo movido el techo y medido el nuevo, y diciendo con el número qué lo
bloquea. El techo ya se movió una vez de 84,7 % a 89,5 %: volver a publicar 89,5 %
no es cerrar, es repetir. Si al mover el techo descubres que el 90 % exige romper
la cobertura o los tres ceros, dilo con el número y para — eso también es una
respuesta, pero tiene que venir con la medición que la sostiene.

Empieza.
```

---

## Cómo usar las dos cuentas

1. Pega el prompt en la cuenta A y déjalo correr.
2. Cuando se agote la cuota, **no intentes resumir la conversación**: no hace
   falta. Abre una sesión nueva en la cuenta B y pega **el mismo prompt, entero,
   sin cambiar nada**.
3. La sesión B ejecuta primero el bloque «SI ESTA SESIÓN SE QUEDA SIN CUOTA» y
   continúa desde el último commit.

Lo único que hay que vigilar entre cuentas es que la sesión A haya commiteado lo
último que midió. Si murió a mitad de una corrida, `git status --short` lo dirá y
la sesión B repite esa corrida y nada más.
