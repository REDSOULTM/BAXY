# C03 — lecciones para continuar, 2026-09-05

Documento de evidencia y orientación, no otro goal. Resume los informes
persistidos desde el inicio de C03, los checkpoints publicados y la continuación
de Opus. No afirma acceso exhaustivo a chats privados ni a cada JSONL histórico.
Los resultados pertenecen a sus candidatos; comprueba evidencia posterior antes
de aplicar una conclusión al código actual.

| Evidencia | Aprendizaje operativo |
|---|---|
| [HERENCIA](../../../artifacts/comprobaciones/C03/HERENCIA.md), 2026-09-03 | El reloj se leía bien y el recovery cambiaba éxito por fallo. Reparar la primera pérdida de hechos, no culpar al GGUF. Conservar utc+offset y reintentar los mismos hechos. |
| Primer checkpoint publicado, commit c1ebb79; CIEN de ese commit | Había Full verde y aclaraciones inútiles. Los tests estructurales no acreditan utilidad; aplazar un bloqueo a C06 no cierra C03. |
| [CIEN](../../../artifacts/comprobaciones/C03/CIEN.md), cien-17; commit e7a8ba0 | El plan sobrevivía a Nueva sesión. Una prueba debe incluir estado previo y posterior, no sólo frases aisladas. |
| [RUTAS](../../../artifacts/comprobaciones/C03/RUTAS.md) | Hay bienvenida, conversación, aclaración, confirmación, progreso, resultado, error y resumen. Un reloj correcto no cubre la voz del producto. |
| [A/B](../../../artifacts/comprobaciones/C03/ab-voice/COMPARE.md) y [A/B nativo](../../../artifacts/comprobaciones/C03/ab-voice/COMPARE-NATIVE.md) | Granite rindió mejor en ese panel pequeño. Perfiles y parámetros efectivos importan; no extrapolar a aceptación ni repetir la comparación sin razón nueva. |
| [Discriminantes](../../../artifacts/comprobaciones/C03/disc-compare.md) | Instrucciones de otras rutas contaminaban la actual. Exigir la marca BAXY en capacidades causaba falsos rechazos. Un filtro necesita contraejemplos válidos. |
| CIEN, cien-34 y cien-35 | 88/100 y 93/100 publicados no eran aciertos. Leer lo publicado y contar ausencia, irrelevancia, hechos inventados e idioma. v16–v18 ya son desarrollo. |
| [Diagnóstico de transferencia](../../../artifacts/audit/c03_opus_20260905/DIAGNOSTICO.md) | Contradicción Python/C# de idioma, saludo que borra pedido y payload que inventa estado: hipótesis reproducidas sin Granite. No repetir las pruebas antiguas como si las funciones no hubieran cambiado. |
| [Estado Opus](05_ESTADO_Y_CONTINUACION.md) | Lectura unificada y datos de idioma cruzando la frontera: preservar la reparación demostrada, no volver a listas independientes. |
| [R07 Opus](../../../artifacts/comprobaciones/C03/r07-opus-1/R07.md) | Recuperación exige mismo proceso/perfil/sesión. La captura acredita recuperación; algunas frases se corrigieron después y requieren su propia evidencia. |
| [UI Opus](../../../artifacts/comprobaciones/C03/ui-opus-2/UI.md) | El conductor no detectaba la bienvenida defectuosa de arranque. Enviar y leer en la ventana real importa; título y servidor listo no bastan. |
| [Seguimientos](../../../artifacts/comprobaciones/C03/SEGUIMIENTOS.md) | La causa inicial atribuida al router era falsa: el compositor perdía contexto. La traza efectiva decide. Compilar Debug no afectaba al Release usado por el conductor. |
| Seguimientos 11/12 y [checkpoint](../../../artifacts/comprobaciones/C03/CHECKPOINT.md) | Prohibir redefinir empeoró de 9/9 a 6/9 en tema. Retirar la variante mala; mantener el tema no equivale a responder la pregunta. |
| [Panel 12](../../../artifacts/comprobaciones/C03/panel-opus-12/ADJUDICACION.md) y [panel 13](../../../artifacts/comprobaciones/C03/panel-opus-13/ADJUDICACION.md) | Aproximadamente 75 % útiles en ambos. Mejoras por clase pueden coexistir con regresiones; comparar mismos casos y medir ambos lados. |
| Panel 13 y seguimientos | «this PC» heredó tema indebidamente. Los contrastes deben distinguir seguimiento, pregunta nueva y orden; no sólo variantes positivas del fallo. |

Conservar: lectura verificada del reloj, reintentos con hechos intactos,
limpieza de sesión, separación de idioma/intención, trazas de borrador y las
pruebas reales de UI/recuperación cuando sus dependencias sigan vigentes.
Investigar: primera etapa que falsea intención, contexto, capacidad, idioma,
contenido o publicación. No convertir esta lista en más validadores del producto.

El prompt anterior ya pedía una causa y dos variantes; faltaba volver esa regla
operativa con comparación emparejada, contraejemplos válidos y evidencia antes
de repetir. La revisión también elimina el arranque obsoleto por Good afternoon
y la obligación implícita de volver a investigar lo ya reparado. No modifica
criterios de aceptación ni promete éxito por cambiar las instrucciones.

Fuentes de metodología consultadas el 2026-09-05:
[guía de Opus 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5)
y [trabajo entre ventanas de contexto](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents).
La guía recomienda alcance explícito, concisión y limitar verificaciones
redundantes y delegación. Aquí se conservan los gates obligatorios de BAXY.
Las decisiones de paneles, criterios y parada vienen de la evidencia del repo.

