# C03 — serialización del prefijo system — tramo77

75 localiza nueve HTTP400: template Qwen3.5 requiere system sólo en índice0.
Todos los paquetes fallidos contienen dos o tres system consecutivos al inicio.
Herencia: los builders de conversación, idioma, aclaración y recuperación ya
aportan la información adecuada. Se conserva; el owner LlmRuntime._post agrupa
exclusivamente ese prefijo antes del transporte. No mueve el diálogo ni altera
el payload conservado por el caller para los reintentos. No capa de clasificación,
instrucción nueva ni normalización del texto humano.

Contraste primario y medición previa: PRUEBAS_TEMPLATE75_76.md.76 elimina9/9
errores de template y conserva los principales resultados del2507. No acredita
producto ni modelo completo. El modelo permanece como override aislado.

Test de frontera HTTP:2 fail/1 pass/41 deselected/0,61s antes del arreglo.
Después cuatro suites dueñas:1149 pass/0 skips/5,62s. Fast31677exit0,
Release1,51s,0 avisos/errores. No Full durante reparación.

files77-template terminó57828exit0, misma secuencia10/fixtures/modelo de74/75.
Hook77 observa post_chat_completion después de serializar, no el payload previo
de LlmRuntime._post. Criterio: recuperar porqué/definición/aclaración sin HTTP400
ni efectos no pedidos, conservando UTF8 y todo lo ya útil. Registrar t9 aunque
siga fallando; la ausencia de hechos no se arregla relajando extra_claim.

Resultado7/10 útiles,125,11s,GPU3177,56MiB,RAM6765,18MiB,registro intacto.
Ningún HTTPError y todos los paquetes con como máximo un system. Checksum
recuperado. Causa UTF8 y nivel de volumen se perdían después en vetos de rol:
el tramo78 los recupera y llega9/10. PRUEBAS_TEMPLATE77.md/TRAMO77_PINS.json.
