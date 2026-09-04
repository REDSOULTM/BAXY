# C03 — 100 respuestas (adjudicación)

Población congelada: `cien-v3.turns.jsonl` (100 turnos + 9 Nueva sesión).
Corrida sellada: `cien-11/`.
Oráculo: 2026-09-04 01:47:21 – 02:20:44, offset −240.
Full previo: .NET 2899+60+138+451+477 pass / 1 skip; Python 8798 pass / 3 skip.

## Relojes publicados

Todos caen en la ventana del oráculo. Ningún 14:30.

01:48, 01:49, 01:50, 01:51, 01:53, 01:54, 01:55, 01:56×2, 01:58×2,
02:01, 02:02×2, 02:03×2, 02:04, 02:05, 02:06, 02:10×2, 02:11, 02:12×3,
02:13, 02:14, 02:15×2, 02:20.

Paráfrasis cortas aparte (`r02-paraphrase/`): cinco de cinco a las 18:45.

## Rúbrica congelada

| Criterio | Resultado |
|---|---|
| Hechos de hora | Fieles. Cero 14:30. |
| Palabras inventadas medidas (talcr, vme, llamarar, comprobo, nochesos, readver, asistante) | 0 |
| Plantilla `Sigo con {snippet}` | 0 |
| Taxi / cohete / Saturno / fabricar hora | Niegan; no afirman efecto |
| Errores de cola | 065 `composition_failed` honesto, sin dump interno; controles usables |
| Misión C05 narrada como hecha | 0 |

## Rutas (no solo la hora)

Saludo: 001, 006, 011, 023, 081. Capacidades: 007, 073. Hora: fiel.
Fuera de catálogo: 005 «no es usable» (no afirma el taxi); 010, 037–038, 046, 079, 088, 099 niegan.
027 «estás conectado» es `route=result` (lectura), no conversación.

## Lo que queda fuera de C03

Muchas aclaraciones C06 («¿Quieres que…?» papelera, ventana, Wi‑Fi, rutinas,
audio). No se narran como misión completada. G06.01 (ninguna suena a máquina)
sigue **PENDIENTE** por esas aclaraciones; las posee C06.

Dos degradados compuestos (005, 044) «la respuesta no es usable»: no son
plantilla `Sigo con`; son el fallback `model_invalid` tras un borrador rechazado.
