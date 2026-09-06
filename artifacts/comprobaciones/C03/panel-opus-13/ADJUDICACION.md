# C03 — panel de regresión, ronda 13 (2026-09-05)

Misma población que `panel-opus-12` (78 turnos), después de la reparación del
seguimiento elíptico. Granite 4.2 3B Q4_K_M registrado.

**75 publicados, 2 `composition_failed` (056, 062), 1 `filtered` (010).**

**No es una aceptación.** Población de reparación; los cien turnos frescos del
tramo D siguen pendientes.

## Reparado y verificado desde la ronda 12

| Clase | Antes | Ahora |
|---|---|---|
| Persona en la negativa | 015 «No abres la Calculadora» | «No abriré la Calculadora ahora.» |
| Seguimiento con tema | 020/022/034 en abstracto | nombran latencia, DNS caching y proxy |
| Encargo del mundo | — | 023, 024, 025, 059, 060, 075, 076, 078 nombran el límite |
| Reloj parafraseado | — | 053, 054, 067, 068, 077 en ventana |

## Regresión encontrada y reparada después de esta captura

`051` «what are your limits on this PC» se contestó con la definición de máscara
de subred del turno 050. La causa es mía: la lectura de la elipsis tomaba
«this» por anáfora, así que la pregunta heredaba el tema anterior. Un
determinante va seguido de su sustantivo y un sustantivo nunca es armazón; con
eso, y exigiendo además un interrogativo, «what are your limits on this PC»,
«close that» y «ábreme eso» dejan de ser seguimientos. Fijado en
`tests/test_request_reading.py`.

Sin esa comprobación la reparación del seguimiento habría entrado en el tramo D
llevándose por delante las preguntas de límites.

## Defectos que quedan, por clase

1. **Saludo mal formado** (001, 003, 004): «Hello hi!».
2. **Seguimiento en tema que repite la definición** (020, 022): nombra la
   latencia y vuelve a definirla en vez de decir por qué importa. Prohibirlo
   desde el prompt se midió y empeoró (`seguimiento-12`); es generación
   conversacional, C05/C06.
3. **Capacidades o límites infieles** (038 contesta con el nombre del equipo,
   046 rechaza una pregunta que sabe contestar, 052 pregunta por los campos de
   un recordatorio, 058 «No hay nada que niegarse aquí»).
4. **Fugas del contrato interno** (040 «Continue the conversation calmly…»,
   044 «(Note: I'm responding in English as per the internal language
   policy.)»).
5. **Persona impersonal** (029 «se puede abrir…» en vez de «puedo»).
6. **Dos agotamientos y un silencio** (056, 062, 010).

Las clases 2, 3 y 4 viven en la generación conversacional de la mente y tocan
C05/C06; se dejan trazadas con su evidencia.

## Tasa

Contadas una a una: unas 58 de 78 útiles y fieles (~75 %), la misma cifra que
la ronda 12 con el seguimiento reparado y una regresión propia encontrada y
corregida. No procede congelar la población fresca todavía.
