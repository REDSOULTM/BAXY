# Idioma y límite — desarrollo, 2026-09-06

**4/8 correctos, 7/8 publicados; 1 fallo de composición.** Sesión 97207 terminó
exit 0. PREREG.json conserva candidato y turnos; Granite registrado.

| # | Veredicto | Motivo |
|---|---|---|
| 1 | Pasa | Conserva el límite del catálogo al recomponer, sin afirmar lectura ni intento. |
| 2 | Falla | Afirma inexistencia o instalación incompleta sin observación. |
| 3 | Falla | Explicación pertinente, totalmente inglesa. |
| 4 | Pasa | Saludo breve en spanglish. |
| 5 | Falla | Repite un fragmento del pedido y no da la hora. |
| 6 | Falla | Agotamiento de composición; no hay respuesta útil. |
| 7 | Pasa | Lima, en inglés. |
| 8 | Pasa | 96, en español. |

El subtipo unsupported ahora llega al shell. Dos tests antes rojos reproducen
la pérdida en ambos extremos; después Python 834 pass y C# 73 pass/0 skips.
El guard mixed funciona cuando recibe mixed, pero _decisive_request_language
trataba la mezcla como falta de evidencia y permitía que otro detector la
reemplazara por inglés. Tres contrastes rojos confirman ese traspaso; se corrige
después de esta corrida. La lectura explícita de spanglish también está cubierta.

La hora con modificador de idioma no coincide con el parser heredado anclado:
Dime la hora, please, en spanglish queda como conversación en vez de lectura.
Siguiente contraste: separar ese modificador al reconocer el pedido de hora,
preservando el texto completo para redactar. No inventar hora ni traducirla a mano.

La auditoría muestra retrieval=semantic en turnos posteriores: E5 sí se carga.
No concluir que falta el modelo por un snapshot inicial lexical; la promoción
es asíncrona. Los fallos de acción de archivo y prosa global siguen abiertos.
No Full nuevo, aceptación fresca, UI física ni cierre C03. Sin fixture pendiente.
