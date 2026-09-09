# Instrucción de cambio de idioma entre cláusulas — no adoptada

82.36 s, GPU 3497.56 MiB, RAM 5151.09 MiB; registro intacto.
12 turnos, 11 publicados. Mismos doce que mixed-segments, sin JSON dividido.

| Turnos | Veredicto |
|---|---|
| 1–4 lecturas ES/EN | Datos correctos; bienvenida atrasada ausente. |
| 5 hora mixed | Hora fiel, «please» e «if you're asking» copiados/torpes. No natural. |
| 6 hora/audio mixed | Hechos presentes, formulación repetitiva y mezclas telegráficas poco naturales. |
| 7 saludo mixed | Repite la pregunta en inglés y añade energía no solicitada; no mejora. |
| 8 cifrado | Fuga visible de JSON truncado: falla grave. |
| 9 copia de seguridad | composition_failed. |
| 10 gravedad | Analogía confusa del suelo pegado a la Tierra y gramática «a invisible». No plenamente útil/natural. |
| 11 no abras Paint | Correcto. |
| 12 Perú | Correcto. |

Máximo 6/12 plenamente satisfactorios. Se descarta; no se cambia la instrucción
productiva por esta variante ni se amplían listas para aprobar sus salidas.
La fuga de t8 revela un defecto independiente: chat intentaba json.loads, y si
fallaba mostraba el objeto parcial como prosa. Prueba roja con otro tema (caché)
y reparación en producto: rechazar envelope inválido o finish_reason=length.
El muestreo/schema diagnóstico no es aceptación ni promoción del GGUF.
