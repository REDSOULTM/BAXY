# R01–R06 — captura fiel contra `d6500f8` (C01)

Comando:

```powershell
py main.py --conductor --turns-file artifacts\comprobaciones\C01\r01-r06.turns.jsonl --capture artifacts\comprobaciones\C01\r01-r06 --timeout-ms 180000
```

`meta.commit`: `d6500f810dac26089873fa3df7ae44fc5b554470`.
Manifiesto: `%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json`.
Perfil persistente (no vaciado): `%LOCALAPPDATA%\BAXY\comprobaciones-c01`.
JSONL: `events.jsonl`. Oráculos: `oracles-before.txt` / `oracles-after.txt`.

C01 exige captura, no que estos casos pasen. Owners: C03–C05. El perfil ya traía un plan pendiente de corridas anteriores; el conductor no lo reparó.

## Oráculos

| Momento | Reloj local | Calculadora | Red 1.1.1.1 |
|---|---|---|---|
| Antes | 2026-09-03 00:23:54 -04:00 | ausente | True |
| Después | 2026-09-03 00:24:25 -04:00 | no se observó proceso/ventana Calculadora | True |

Tras la corrida quedó un `Notepad` «Sin título: Bloc de notas» (no pedido). No se mató: podría no ser efecto exclusivo del test.

## Casos (texto público exacto)

| ID | Entrada | Terminal | Final publicado | Veredicto C01 |
|---|---|---|---|---|
| R01a | Hola, ¿qué puedes hacer? | published_final | La aplicación está abierta y muestra el título "Nota: Informe de actividad". | FAIL C03 — no responde capacidades; arrastra plan |
| R01b | Explícame qué es un huso horario en una frase. | published_final | Listo, el huso horario es el desfaseo de la hora en una zona geográfica específica. | FAIL C03 — «Listo» sin hecho comprobado; prosa defectuosa |
| R01c | ¿Por qué importa? | published_final | No pude: no pude encontrarlo. | FAIL C03 |
| R02 | ¿Qué hora es? | published_final | ¿Qué hora es? | FAIL C03 — eco; no usa el reloj |
| R03 | Abre la calculadora | published_final | Listo, la calculadora está abierta. | FAIL C04 — prosa de éxito; oráculo no vio Calculadora |
| R04 | Cuéntame un chiste corto. | published_final | La aplicación está abierta y muestra el título "Nota: Informe de actividad". | FAIL C05 — plan viejo captura el turno |
| R05 | ¿Tengo conexión a internet? | published_final | ¿Tienes conexión a internet? | FAIL C05/C06 — eco; red True |
| R06 | session.new + Dime la hora y el estado del audio. | published_final | Listo, audio está abierto. | FAIL C05/C03 — sin hora; audio inventado; `hasPendingPlan=true` tras Nueva sesión |

Todos los turnos distinguen `admission` de `terminal`. El conductor no inventó el final ni limpió `_pendingMindPlan`. Visual/acústico no se declara verificado.
