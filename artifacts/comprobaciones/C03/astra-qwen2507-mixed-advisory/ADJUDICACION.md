# Desarrollo: mezcla léxica como aviso

90.38 s; 3497.56 MiB GPU atribuida; 4962.72 MiB RAM; registro intacto.
12/12 publicados, cero agotamientos. Esto NO equivale a doce respuestas aptas.

| Turno | Adjudicación |
|---|---|
| 1, 3, 4 | Hora y audio fieles; inglés del resumen algo telegráfico. |
| 2 | Hechos fieles; «mutado» es una elección léxica defectuosa para silenciado. |
| 5 | «It's 7:30, amigos.»: hora fiel y mezcla natural mínima. |
| 6 | Hechos fieles, pero respuesta sólo española y otra vez «mutado»: calidad de idioma pendiente. |
| 7 | Saludo torpe, cambia el trato con «meterse» y añade relleno. |
| 8 | Explicación útil y fiel en mezcla mínima «Encryption es…». Se preserva el primer borrador en vez de agotar retries. |
| 9 | Explicación útil, pero ignora la solicitud explícita de spanglish. Falla el idioma. |
| 10 | Analogía vaga y afirmación «cuando caes, no vuelves a subir»: explicación insuficientemente fiel. |
| 11, 12 | Negación Paint y capital Lima correctas. |

Máximo 8/12 útiles; no desarrollo verde ni aceptación. La intervención mejora la
disponibilidad y evita daño probado del veto, pero la calidad sigue adjudicándose
manualmente. Se adopta sólo el cambio del veto a aviso en las trazas opt-in:
mixed_language_needs_review. Se conservan prompts de idioma, controles ES/EN,
hechos, polaridad, autoridad, eco y JSON. No se añaden palabras a un diccionario.
