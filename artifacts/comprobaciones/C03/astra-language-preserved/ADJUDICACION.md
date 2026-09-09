# Idioma conservado — desarrollo, 2026-09-06

**3/8 plenamente correctos, 8/8 publicados.** Sesión 44819 terminó exit 0.
Mismos ocho controles que astra-language-boundary; PREREG.json y paired.txt.

| # | Veredicto | Motivo |
|---|---|---|
| 1 | Pasa | Límite del catálogo, sin efecto inventado. |
| 2 | Falla | I saw afirma observación inexistente y altera el nombre solicitado. |
| 3 | Falla | Pregunta si se desea una explicación simple, ya pedido; no explica. |
| 4 | Pasa | Saludo breve en spanglish. |
| 5 | Falla de formulación | 05:01 es la lectura real, pero proviene de recortar un borrador que copia instrucciones; no acredita formulación natural. |
| 6 | Falla | Explicación correcta sólo en español, pese a petición explícita de spanglish. |
| 7 | Pasa | Lima, en inglés. |
| 8 | Falla | Devuelve el cálculo como pregunta en vez de dar 96. |

Revisión del borrador de t5: el modelo emitió «En español y inglés, di: [...]»;
el recorte publicó sólo la cifra. Inicialmente se contaron cuatro respuestas
útiles por ser la hora verdadera; al exigir también formulación de C03 quedan
tres plenamente correctas. El recorte no acredita calidad del modelo. La ruta
sí lee system.time con utc y offset reales: el reconocimiento ya está reparado.

La auditoría t6, request_id 29, clasifica followup. LlmRuntime.chat retorna
_resolve_contextual_answer antes de la validación común; esa salida explica que
mixed llegue al modelo y aun así escape una respuesta española. Contraste nuevo
rojo; se cierra después de esta corrida con la vía habitual de recomposición.
No basta poner otro filtro al final del shell. t3/t8 son aclaraciones improcedentes.

No Full, aceptación fresca, UI física ni promoción de modelo. Sin fixture ni
procesos de esta corrida pendientes. Este resultado sigue dejando C03 EN_CURSO.
