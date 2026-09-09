# Baseline Astra — 16 turnos, 2026-09-06

Lectura individual de `paired.json` y `paired.txt`. Fuente Python y shell de
`2bf3d4c` congelados durante la corrida. Granite registrado `e0406663`, b9980,
misma selección de turnos que usará el candidato. No es aceptación reservada.

**10/16 útiles y fieles; 15/16 publicados.** El agotamiento cuenta como fallo.
No se exige una redacción exacta ni que la respuesta de utilidad evite definir:
si además explica la utilidad, pasa (t8). Un saludo breve genérico pasa (t3/t4).

| Turno | Veredicto | Motivo |
|---|---|---|
| 1 | Pasa con defecto de puntuación | Devuelve saludo y oferta social; la pregunta termina con punto. |
| 2 | Pasa | Explica resolución de nombres a direcciones IP. |
| 3 | Pasa | Devuelve el saludo en inglés. |
| 4 | Pasa | Devuelve el saludo en inglés. |
| 5 | Pasa | Define correctamente latencia. |
| 6 | Falla | Repite la definición; no dice por qué importa. |
| 7 | Pasa | Explica almacenamiento de consultas DNS y su finalidad. |
| 8 | Pasa | Responde la importancia: menor tiempo de consulta y mejor rendimiento. |
| 9 | Pasa | Explica el túnel cifrado de VPN sobre red pública sin afirmar anonimato total. |
| 10 | Falla | Respuesta abstracta sobre tomar decisiones; pierde VPN. |
| 11 | Pasa | Define proxy como intermediario. |
| 12 | Falla | No explica la finalidad solicitada y añade una «ruta interna» sin fundamento. |
| 13 | Falla | «Enruta el enlace» no explica el encaminamiento de tráfico entre redes. |
| 14 | Falla | Agotamiento: no hay respuesta a la utilidad del router. |
| 15 | Falla | Resultado aritmético correcto (12 × 8 = 96), pero responde en inglés a petición española y omite el operador en la frase. |
| 16 | Pasa | Lima es la capital de Perú. |

La traza de esta baseline conserva motivos, huellas y finish_reason, pero no
borradores brutos: no se activó el opt-in de contenido. Las respuestas finales
sí están completas. La corrida del candidato debe activar ese opt-in con las
mismas entradas sintéticas para diagnosticar sus rechazos. No reconstruir
borradores ausentes ni atribuirlos a partir de los finales.

`astra-before` es un intento interrumpido y no controlado: la fuente se editó
mientras el sidecar podía reiniciarse. Se conserva, pero no aporta un antes
válido. Esta corrida aislada lo sustituye para comparar, sin borrar evidencia.
