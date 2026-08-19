# Prompt para GPT-5.6 Sol — retomar la comprensión hasta el 90 %

Escrito para pegarse entero en una sesión nueva de Codex con **GPT-5.6 Sol,
`reasoning.effort: high`**, sobre una suscripción de 20 $. Está pensado para
**agotarse en una cuenta y continuar en la otra sin perder nada**: todo el estado
vive en el repositorio, no en la conversación.

---

## El prompt

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
