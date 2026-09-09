# C03 — preservar disposición e idioma, 2026-09-06

La recuperación descartaba dos decisiones útiles ya tomadas por la mente:
unsupported no cruzaba turn.result y mixed se trataba como falta de evidencia.
Se conserva conversationKind como metadato cerrado de presentación en Python y
C#. No concede operaciones ni efectos; el shell lo usa para mantener out_of_catalog
al recomponer un borrador rechazado. Antes: Python 1 fail; C# 1 fail, que mostraba
conversation/success en vez del límite. Después: 834 pruebas Python y 73 C# verdes.

El compositor comprobaba idioma sólo para ES/EN y chat no comprobaba mixed.
Ambos usan ahora la evidencia del reader existente: una respuesta sustantiva
en un solo idioma pierde la mezcla; cifras y nombres neutros siguen admitidos.
Se reintenta conservando el pedido; un nuevo fallo se declara, no se publica.
También se reconoce spanglish como idioma explícitamente pedido, reutilizando
la precedencia de traducción/idioma que existía para español e inglés.

astra-language-boundary: 4/8 correctos, 7/8 publicados, 1 fallo de composición;
preregistro y adjudicación conservados. El límite español y el saludo mixto
mejoran. Quedan la afirmación inglesa de inexistencia sin observación, la
explicación inglesa y la hora sin lectura. No se cuenta publicación como calidad.

La corrida explica el siguiente arreglo: el reader decía mixed y
_decisive_request_language devolvía None, permitiendo otra decisión monolingüe.
Tres contrastes fallan antes; se conserva ahora esa lectura positiva de mezcla.
Después: 1217 pass/101 subtests en cinco owners Python. Ruff verde; pins V8/STT
se actualizan sin cambiar sus corpus ni adjudicaciones (17 pass/1 skip ambiental).

La promoción E5 sí se observa en turn-audit (retrieval=semantic); un primer
snapshot lexical no demuestra falta de modelo. No descargarlo ni reconstruir
el corpus por ese dato. El pedido de hora con idioma al final no coincide con
el parser anclado: cuatro positivos fallan antes y tres negativos pasan. Se
separa únicamente el modificador final de idioma dentro del reconocedor, sin
alterar el pedido que se envía al compositor. Después: 190 pruebas C# verdes,
0 skips (parser de estado, hechos C03, conformance reader y planner boundary).
astra-language-preserved compara los mismos ocho controles, con preregistro.

Terminó exit 0: **3/8 plenamente correctos, 8 publicados**. La hora ya se lee,
pero sólo se publica tras recortar un borrador que copia instrucciones; no cuenta
como formulación natural. El cifrado explícitamente mixto toma la vía followup:
request_id 29 lo confirma en turn-audit. Esa vía devolvía directamente la respuesta
contextual y omitía el guard común. Una regresión nueva falla antes; ahora pasa por
redacción validada si pierde la mezcla. El reintento monolingüe tampoco puede salir:
se comprueba audit_reason, conservando el mensaje estable de la excepción.
Después: **1219 pass/101 subtests**, ruff y diff-check verdes. No hay procesos activos;
falta medir la última reparación contextual en el producto. Adjudicaciones intactas.

Full reservado para el candidato final. Sin promoción de modelo, publicación,
UI física, 100 frescos o cierre. Los fallos globales continúan EN_CURSO.
