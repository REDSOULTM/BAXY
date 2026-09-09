# Pedido conservado — desarrollo, no aceptación

Termina exit 0, 235.05 s; 3337.57 MiB VRAM y 6935.07 MiB RAM. Registro
Granite intacto. Mismos seis controles y límites que sentences.

| Turno | Respuesta | Veredicto |
|---|---|---|
| 1 | Hello! | Útil. |
| 2 | Noventa y seis. | Cálculo correcto. |
| 3 | Eighty-four. | Cálculo correcto. |
| 4 | composition_failed | Explicación mixed ausente: falla. |
| 5 | composition_failed | Spanglish explícito ausente: falla. |
| 6 | The capital of Peru is Lima. | Hecho correcto. |

4/6 útiles. No mejoran las dos explicaciones; no seguir cambiando el prompt
para perseguir esta muestra. El audit temporal sí permite cambiar de hipótesis:
request 9 gasta 4.609 s en una composición; después política, idioma y guard
agotan el tiempo que les queda (5.781 s, llamadas solapadas, no sumarlas).
El progreso EN «I'm calculating fourteen times six.» aún se rechaza por no
contener still/working, y se vuelve a componer antes de decidir.

Fuente: sampling.jsonl (inicio/fin por llamada y requestId), compose-audit,
turn-audit, paired y RESULT. La causalidad histórica y el siguiente contraste
de planificación se documentan en ASTRA-TRAMO-7.md. No promoción de Qwen8.
