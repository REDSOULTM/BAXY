# 441 — 9B no mejora la atribución y cuesta más

Mismos ocho payloads438, sin cambios de prompt o muestreo. 5/8 útiles: las tres
lecturas españolas siguen atribuyendo Jordan/Marta/Ana María a BAXY. Los otros
cinco controles mantienen utilidad; todos stop. 48,36s, GPU3010,3125MiB,
RAM4007,27734375MiB; sin violaciones, registro intacto, cliente cerrado.
No promover ni repetir modelo9B para este fallo. La comparación con4B438 es
de composición nativa, no consumo/latencia del producto entero.

442 vuelve a4B y cambia una sola entrada de composición: omite la pregunta
original sólo ante lectura privada completada, conservando situation, contrato,
idioma y muestreo. Es el alcance de _compose_user_content(include_request=False)
ya heredado por acting, sin respuesta fija ni feedback/guardia. Hipótesis:
releer la pregunta personal en una fase que ya tiene un resultado puede hacer
que el modelo resuelva identidad en lugar de narrar los registros. Se contrasta,
no se presupone; la hermana y los múltiples registros son controles necesarios.
