# Fuente333 — dueñas y Fast verdes; producto334 pendiente

`pytest tests/test_turn_policy.py tests/test_compose_contract.py -q -x --tb=short`:
**1009 pass, 0 fail, 0 skips, 5,82 s**. `test_source_quality.ps1 -Mode Fast`:
verde, build Release2,18s, cero errores/advertencias.

Baseline11fail2pass: nueve pruebas llaman a la nueva función todavía inexistente;
dos pruebas de integración reproducen el rechazo de respuestas correctas.
No presentar los nueve AttributeError como defectos independientes del producto.
Primer focal2fail11pass: la respuesta ya pasó; la aserción nueva consultaba `text`
en vez de `reply`. Corregida según el retorno real del protocolo; sin relajación.

`visible_reply_is_only_questions` sustituye las tres aproximaciones de puntuación
en llm.py/__main__.py. Reconoce contenido fuera de interrogaciones delimitadas;
emojis y puntuación no cuentan como respuesta. Sin nombres ni frases del usuario
en fuente productiva. No certifica relevancia/verdad por tener un prefijo; siguen
vigentes los validadores semánticos y de hechos. El comportamiento sin «¿» conserva
la regla anterior de fin de oración.

Producto334 repite la secuencia exacta331 sin override, con los mismos runtime y
perfiles de muestreo. No aceptar la integración sólo por estos verdes.
