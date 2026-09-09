# Desarrollo: prosa de referente

68.33 s; 3497.56 MiB GPU atribuida; 4793.25 MiB RAM; registro intacto.
No aceptación C03. 5/6 útiles; no Full ni promoción.

| Turno | Veredicto |
|---|---|
| t1 cierra aquello | Útil: pide identificar ventana, aplicación o documento, sin efectos. |
| t2 cancelar | Útil y fiel: cancela la aclaración pendiente. |
| t3 hora ES | Fallo visible: composition_failed. El borrador «Son las 07 horas y 13 minutos» coincide con clock=07:13, pero se rechaza como missing_name en todos los reintentos. También aparece la versión escrita con palabras. |
| t4 close that | Útil: «Close what?» mantiene acción e idioma. |
| t5 cancel that | Útil y fiel: cancela la aclaración. |
| t6 cálculo | Útil y correcto: 84. |

La corrección del requisito léxico resuelve ambas aclaraciones. El nuevo fallo
de hora procede del comprobador de equivalencia, limitado a la notación HH:MM.
No se atribuye el fallo a la exactitud del dato del modelo ni se marca como pass.
