# Handoff — arreglos de los fallos de la feria — 2026-10-27 — f5d3bd162

## Objetivo

Corregir con arreglos generales los 22 fallos de la feria (seis raíces, R1 a R6) antes de los finetunes, sin bajar
ninguna cifra de los bancos. El informe completo, con cifras por caso, se queda fuera del repo porque contiene frases
de la feria: `F:\BAXYeval\fallos\INFORME.md` en el PC.

## Estado

- El código final de `pc-arr-fallos` (hub) es **f5d3bd162**: base 5677d108a más R1 a R6 y las ramas del notebook
  NB-W1, NB-W3, NB-W5 y NB-W6. En el notebook está desplegado f74f0d0eb desde las 20:47. f5d3bd162 sólo añade un
  cambio de mente (la búsqueda de «qué/quién es X» no la retiene la duda): para llevarlo basta `checkout --detach` en
  la entrega. Paquete en `F:\BAXYeval\deploy\f5d3bd162\` (sólo cambian `Baxy.exe` y `core\baxy-core.exe`).
- Medido frente a la base. El juez del banco de decisión es por reglas; el arnés y el catálogo son los volcados de
  cada kernel.

  | Banco | Base | Candidato | Δ |
  |---|---|---|---|
  | Decisión v11 ×3 | 198,67 | 198,67 | 0 [−4, +4] |
  | v6 abierto s0 | 617 | 622 | +5 [−4, +14] |
  | Acciones equivocadas v6 | 78 | 74 | −4 |
  | Batería parafraseada de la feria ×2 (f5d3bd162) | 33,67 | 39,5 | +5,8 [+1,3, +10,8], p 0,03 |
  | Batería held-out del NB (286) (f5d3bd162) | 195 | 216 | +21 [+8, +34] |
  | En vivo en el PC (f5d3bd162) | 13/20 + 0/4 al escribir | 20/22 | |
  | En vivo en el NB | 19/31 | 25/31 | |
  | Falsedades v11 en el NB, lectura a ciegas | 4 claras | 3 claras | |

- Pruebas de f74f0d0eb:
  - build Release: 0 errores y 0 avisos;
  - dotnet: 5427 de 5428 (la que falla, `VisibleClickWatchesTheWindowItsLookRead`, falla igual en la base desde las
    20:20; depende del escritorio);
  - pytest: 1080 pasan, más el fallo previo de `test_voice_vad` (falta silero_vad en el Python del PC).

## Decisiones tomadas

- **`named_fact`** sólo juzga las preguntas por qué o quién es lo nombrado, cuando lo nombrado cierra la pregunta.
  La primera versión mandaba a la web capitales, siglas y autores, y bajaba v11 y v6.
- **Guarda `unopened_app`**: una app es el destino del texto sólo si se dice como lugar («en/in/on…»). Con el nombre a
  secas confundía «el cursor» con la app Cursor.
- **Tope de la decisión: 768 tokens.** Se midió ~36 tokens/s en el notebook; con 1536, un documento largo pasaría de
  los 30 s que la App da a una decisión y la mente se relanzaría.
- **Fuera:**
  - la regla 6 nueva y la vuelta a decidir «sólo con palabras»: la primera no tuvo efecto medido; la segunda
    convertía acciones correctas en pregunta-eco;
  - los trozos de voz: tiraban «sí», «no» y los números;
  - el arrastre de NB-W2: 0 de 2 en vivo.
- Falsedades las mide el notebook con lectura a ciegas por Claude: en el PC dan VOID con las ventanas del dueño y el
  juez 35B no cabía. Por orden del dueño, desde las 19:10 las rondas de medición duran ≤ 5 min y el juez es Claude.

## Archivos tocados

- `src/baxy_mind/mind.py`: `named_fact`, `calculate`, `unopened_app`, `ask_once`, `DECISION_TOKENS` y el aviso.
- `answer_check.py`, `arithmetic.py` y `data/tool_descriptions.en.v1.json`.
- `src/Baxy.App`: `TurnClosing`, `NetworkEgress` (consulta y canal no dichos), relanzamientos y aviso.
- `src/Baxy.Providers.Windows`: escritura, Calculadora, Steam, Word, apps web por su AUMID y YouTube con navegador.
- Las pruebas de cada uno.

## Archivos relevantes aún sin tocar

- `src/Baxy.Providers.Windows/External/YouTubeMpvAdapter.cs`: está entero muerto; borrarlo con la skill
  `limpiar-muerto`.

## Hipótesis

- El caso de «saluda a X» (canal no dicho) y el de la repetición que no se ejecuta sólo se ven en vivo: el banco de
  decisión no pasa por la App.

## Comandos ejecutados y resultado

Colas y scripts en `F:\BAXYeval\fallos\cola\`:
- `medir.sh` lleva un cerrojo de GPU;
- `volcar_catalogo.sh` y `con_grupo.py` arman el catálogo de cada brazo;
- `pruebas.sh` corre build, dotnet y pytest.

El corredor en vivo es `F:\BAXYeval\fallos\vivo\vivo.py`, con `--senuelo`: los casos de escribir llevan una ventana
señuelo propia delante. Las corridas quedan en `F:\BAXYeval\renew_v1\runs\fe-*`.

## Problemas pendientes

- Casos que siguen igual:
  - pedir que repita: 0/10;
  - «saluda a X» en decisión: 0/10;
  - un saludo mal oído con seguridad;
  - una frase sin sentido («no puedo ayudarte»).
- Cuentas: a veces el 4B no usa `calculate` y contesta de memoria. «Una operación cualquiera en la Calculadora» la
  resuelve por dentro (held-out: base 4/10, candidato 1/10).
- Steam: una cuenta recién iniciada, con la caché vacía, diría «no lo tienes».
- Pruebas intermitentes que ya existían:
  - `GlobalAndPagedNativeReadsPreserveLiteralTitleAndProcessSelectors`;
  - `Only_the_exact_token_grants_not_a_truncated_or_altered_one`: si el token acaba en «B», la prueba lo altera sólo
    en bits de relleno de base64;
  - `VisibleClickWatchesTheWindowItsLookRead`: depende del escritorio.

## Siguiente acción recomendada

1. Tras el despliegue en el notebook: los pedidos de comprobación del informe, incluido un Word de ~300 palabras con
   su tiempo.
2. Una ayuda que obligue a usar `calculate` cuando lo dicho es una cuenta y el modelo contesta de palabra, medida con
   la held-out.
3. Borrar `YouTubeMpvAdapter`.
