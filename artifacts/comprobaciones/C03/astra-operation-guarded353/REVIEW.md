# 353 — alcance preservado también durante recuperación

Se reprodujo el compositor Python real; cada primera petición baseline coincide
con el HTTP capturado. Se mantuvieron guardas, prompts, sampling y reintentos.
Qwen3.5: baseline7/9 útiles, operation-scope9/9 útiles. Su primer Hola Emmanuel
se rechaza por no explicar el fallo. El retry baseline dice no poder saludar por
memoria desactivada; con operation conserva el ámbito: no pudo guardar la
información porque la memoria estaba deshabilitada. Enable ya no inventa vista.

2507 también mejora la explicación de activación y acota el fallo. No corrige su
atribución de Emmanuel/Lina al asistente ni su prosa de replay durante save.
No presentar el resultado como solución completa ni promover otro modelo.

Decisión354: adoptar únicamente la preservación de operation en la proyección,
que procede de la situación tipada y no del texto del usuario. La App ya valida
esa identidad. No nuevo prompt, blacklist, campo inventado o bypass de guardas.
Los tests deben cubrir primera petición y retry, y el producto repetirse.
No App/GUI/voz/fresh acceptance en esta medición; procesos cerrados.
