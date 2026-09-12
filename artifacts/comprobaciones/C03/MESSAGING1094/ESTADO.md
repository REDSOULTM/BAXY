# MESSAGING1094 — reparación candidata

«Escribile» y «respondele» no entraban en la aclaración de mensajería con canal ausente. Tres literales de MESSAGING1085 quedaron abiertos: dos terminaron en fallo de interpretación/composición y otro publicó sólo el cuerpo del mensaje. Los comparadores que sí entraron en esa ruta preguntaron por el canal.

Se comparte la familia verbal entre las tres comprobaciones existentes de forma, destinatario y contenido. Incluye la alternancia escribele/escribile y respondele; conserva las exclusiones, el catálogo y la pregunta nativa por el dato faltante. No hay respuestas fijas ni proveedor nuevo. El defecto secundario que rechaza infinitivos con pronombre en una negativa queda separado: corregirlo no resolvería esta aclaración.

Fuente única: `src/baxy_mind/effect_intent.py`, SHA256 `14cea4af55dd936d79d2e2a83bb3dd9c5311aeeb1ed0d2d3b5a5abf3fdd9a625`. Base `32b3becbdf9b18c459e228b8e4464830cf270aa85e7ba0f2c550c42329a641b5`. Diff revisado por raíz: 7 líneas añadidas y 3 retiradas. El resto del candidato permanece igual.

La reparación aún no tiene resultado dinámico. No se ejecutaron suites, Fast ni Full por instrucción expresa del dueño. BUILD1079 sigue siendo la compilación .NET vigente; se comprobará su fingerprint efectivo al preparar el candidato Python nuevo.

MESSAGING1095 preparará los 24 objetos restantes exactos de MESSAGING1085: 9 literales aún abiertos, 10 variantes y 5 límites. Tres literales fallidos requieren esta reparación; las variantes y el límite ya pasados se vuelven a medir por el cambio en su ruta. El literal H0019 ya acreditado se excluye. No se repite la tanda anterior entera.

Estado: 191/742 cubiertos, 551 abiertos, 0 no aplican; al menos 65 primeras altas en 24 h; 0/35 categorías cerradas y 3/11 filas C03 cumplidas. C03 continúa activo.

En MESSAGING1085, el índice 4 alcanzó el ancla de perfil y se detuvo antes de crear el perfil, el directorio de ejecución o lanzar el producto. El diagnóstico posterior detectó WhatsApp.Root PID 29456, que reapareció tras la observación previa. El índice 5 sólo observó ese cliente presente. Ambos son casos sin ejecutar, con recibos conservados; no son fallos del producto ni créditos. No se atribuye una causa exacta al error silencioso anterior sin recibo de stderr.
