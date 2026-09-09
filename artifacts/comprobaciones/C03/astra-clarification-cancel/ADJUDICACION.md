# Cancelación de aclaración — desarrollo, 2026-09-06

**3/6 plenamente correctos; 6/6 publicados.** Sesión 86568 terminó exit 0.
Runtime Granite registrado. Casos conocidos de desarrollo, no aceptación fresca.

| # | Veredicto | Motivo |
|---|---|---|
| 1 | Falla | Pregunta pertinente, pero «Qué específico deseas» no es español natural. |
| 2 | Falla | Limpia el pendiente sin otra decisión, pero «Cancelar la acción» no comunica el resultado. |
| 3 | Pasa | Capital de Perú: Lima, en inglés. |
| 4 | Pasa | Aclaración breve y pertinente en inglés para open that. |
| 5 | Falla | cancel that reanuda la petición anterior y pregunta en español. |
| 6 | Pasa | 14 por 6: 84, en inglés. |

El control español funciona: no hay otra decisión en t2 y el estado queda
disponible. Su proyección entrega sólo cause=clarification cancelled, perdiendo
que la transición ya ocurrió. El parser de cancelación no reconoce cancel that;
t5 vuelve a llamar a la decisión dos veces. Son causas concretas pendientes.
No se acredita UI física, voz, R07 ni cierre C03. Sin fixture ni proceso activo.
