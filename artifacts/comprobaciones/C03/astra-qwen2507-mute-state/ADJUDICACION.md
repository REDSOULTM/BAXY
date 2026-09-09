# Desarrollo: estado categórico de silencio — DESCARTADO

Sesión67417 terminó0;60,05s,GPU3497,56MiB,RAM5267,71MiB;registro intacto.
21/21publicados, **no21aciertos**. Mismos21mensajes que completed-request.
Se reemplazó sólo muted=true/false por muteState=muted/unmuted en la proyección
del narrador. El booleano original seguía en la verificación. No cambió sampler,
modelo, instrucciones ni filtros. **No mejora t6 y se retiró el cambio.**

| Turno | Evaluación individual |
|---|---|
| t1 | Hora correcta, 12:01 expresada oralmente. |
| t2 | Hora y volumen fieles; audio activo compatible con no silenciado, aunque no acredita reproducción. |
| t3 | Hora correcta en inglés. |
| t4 | Hechos correctos, prosa técnica «The mute state is unmuted». |
| t5 | Hora correcta, mezcla mínima con «man» añadido sin función. |
| t6 | **Incorrecto**: audio desactivado contradice muteState=unmuted y muted=false original. Respuesta sólo española a pedido mixto. |
| t7 | Mezcla idiomas, pero inventa una fiesta y usa bro/emoji; no voz breve y apropiada de BAXY. |
| t8 | Explicación básica útil del cifrado; mezcla reducida al sustantivo inglés. |
| t9 | Recuperación mediante copia correcta al inicio; analogía de una copia que se queda sin luz confusa. |
| t10 | Explicación gravitatoria superficial; «hambre de estar juntos» figurado y «soltas» impropio del español neutro. Mezcla mínima. |
| t11 | Respeta negación, no abre Paint. |
| t12 | Capital correcta en inglés. |
| t13 | Fotosíntesis correcta, inglés y dos frases. |
| t14 | Menor densidad y estructura más espaciosa correctas; «más ligera» requiere comparación de volúmenes iguales. |
| t15 | **Falla idioma**: sólo español pese a Spanglish explícito; definición circular de archivo, contraste con carpeta parcialmente útil. |
| t16 | Lista vacía fiel en inglés. |
| t17 | Confirma título exacto y opciones pertinentes. |
| t18 | Cancelación fiel, repetitiva y con detalle interno innecesario. |
| t19 | Nueva confirmación correcta. |
| t20 | Cierre verificado; misma coletilla técnica que antes. |
| t21 | Hora correcta en inglés. |

Fixture propiaPID17576 ausente al terminar, sin limpieza externa. El resultado de
app.close en t20 conserva windowClosed=true. No acredita pantalla/audio físico.
Antes de la captura:129tests Python pass, Ruff0. Esos tests verificaban transporte
del estado y conservación de la evidencia, no calidad del modelo. Se retiraron
la proyección experimental y sus tests al fallar el criterio visible.
PREREG.json conserva hashes del candidato ensayado; no describe la fuente tras retirarlo.
