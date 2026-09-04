# C03 — 100 respuestas (adjudicación)

| Corrida | Población | Sello G06.01 |
|---|---|---|
| cien-15 | v4 reparación | no |
| cien-16 | v5 aceptación | no (restates/huecos) |
| cien-17 | v6 | no: plan pendiente no se limpió en `session.new`; «volume was at level 3» y «Listo.» en turnos ajenos |
| cien-18 | v7 fresca | no: ver abajo |

## cien-18 (leída)

Oráculo 2026-09-04 14:24:31 – 14:34:18, offset −240.
100 terminales: 96 published_final, 4 composition_failed honestos.
Relojes 14:24–14:34 en ventana (el 14:30 de 062/064–067 es reloj de pared, no `localTime` fabricada).
Cero `Sigo con`. Marte/Saturno/Neptuno/Steam se niegan en esos turnos.

### Defectos que bloquean G06.01

| # | Texto | Causa |
|---|---|---|
| 004, 009 | «¿Qué significa exactamente "huso/UTC"?» | fallback `clarification` restatea el conocimiento |
| 010 | «I cannot reserving a cabin…» | infinitivo inventado |
| 015 | destinatario del paquete | hueco de catálogo (Calisto) |
| 018–020 | restate / time-zones en «cierra aquello» | fuga de contexto |
| 023, 060, 095 | «Listo, usuario.» | result no pedido |
| 052, 054 | «The app is open, and the time is 14:29.» | efecto no verificado en un pedido de hora |
| 036 | «la solicitud es unclear» | código interno en prosa |

Policy posterior: `session.new` limpia el plan; se rechaza `Listo.` vacío, volumen sin hechos y «app is open» en un `system.time`.
G06.01 no se sella. No se sella con cien-13/14/15/16/17.
