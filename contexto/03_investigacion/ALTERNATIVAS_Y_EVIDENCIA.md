# Alternativas y evidencia

Pesos fijados antes de medir:

| Criterio | Peso |
|---|---:|
| Misiones verificadas | 25 % |
| Recursos | 15 % |
| Latencia | 10 % |
| UX y accesibilidad | 10 % |
| Privacidad y seguridad | 10 % |
| Instalación y lifecycle | 10 % |
| Mantenibilidad y testabilidad | 10 % |
| Licencia y madurez | 5 % |
| Migración y reutilización | 5 % |

Familias de core obligatorias: Python, .NET/Windows y Rust u otra alternativa
contemporánea mejor justificada. Cada subsistema comparará tres opciones
serias cuando existan y la opción de eliminarlo/absorberlo. La arquitectura
base quedó elegida al cerrar la ronda B corregida; los subsistemas de modelos,
voz, visión, memoria y providers continúan abiertos.

## Protocolo congelado

El protocolo ejecutable `baxy-technology-tournament-v1` se congeló el
2026-07-14 a las 12:55:05Z, antes de implementar o medir los contendientes. Se
divide en un corte de core común y una ronda integrada para hasta dos
finalistas. Los gates, fórmulas, hashes, hardware, toolchains y casos están en
`artifacts/technology_tournament/protocol.json`; la explicación y las fuentes
primarias están en `documentacion/10_TORNEO_TECNOLOGICO.md`.

Advertencia vigente: la estación tiene 16 GB de VRAM. Por tanto, todavía no
existe evidencia física del perfil de 4 GB y ninguna limitación lógica puede
presentarse como sustituto.

## Ronda A ejecutada

Los tres cores aprobaron 48/48 casos; siete formatos de distribución aprobaron
16/16, el workspace hostil y cero red. Rust nativo quedó como único punto de la
frontera estricta de rendimiento en la repetición final: 0,300 MiB, arranque
p95 22,04 ms, caliente p95 5,35 ms y pico privado 2,32 MiB. Native AOT obtuvo
1,766 MiB, 22,78 ms, 7,77 ms y 19,82 MiB.

Pasan a la ronda integrada Rust y .NET. .NET entra por la regla previa de menos
de 7 puntos y para medir su hipótesis Windows/GUI, no porque se oculte la
dominancia de Rust en el corte. Python deja de competir como control plane pero
permanece candidato de sidecars. Al cierre de la ronda A todavía no existía un
ganador porque accesibilidad, instalación, lifecycle, secretos y tamper
evidence seguían sin medirse.

## Ronda B cerrada

Los shells .NET WebView2 y Tauri/WebView2 completaron el corte funcional, pero
sus hashes quedaron descalificados por el gate de red. El primero observó 16
registros TCP, 443,99 MiB idle y 922,63 MiB pico; el segundo observó 10 TCP y
1 UDP, 370,59 MiB idle y 814,52 MiB pico. La evidencia rechazada permanece en
`artifacts/technology_tournament/raw/round_b_*_rejected_network.json`.

Una auditoría invalidó la primera repetición porque T16 se autoaprobaba y la red
no fallaba cerrado. La repetición final ejecutó T16 contra el core, exigió
recuperación, redacción y filesystem intacto; tomó 18 snapshots de la fase UI y
uno propio de T16 por corrida y ligó cada raw a harness/protocolo/casos. Ambos
WPF aprobaron T01–T15 por compositor y T16 por frontera raw: 34/34 en tres
corridas, 7/7 arranques fríos, 30 operaciones calientes, lifecycle, cleanup y
8/8 gates de paquete. La suite aprobó 41/41.

| Finalista | Score | Pareto | Decisión |
|---|---:|---|---|
| WPF + .NET NativeAOT | 82,004484 | Sí | Ganador |
| WPF + Rust estático | 79,992351 | Sí | Fallback reproducible |

El scorecard canónico es
`artifacts/technology_tournament/round_b_scorecard.json`, SHA-256
`e5f99d744f69201e9edd36c5346b3f030dac585ba6eb6f03cd2ba859b8d71190`.
.NET puro gana por score y evita la segunda toolchain, crates y CRT estático.
Rust permanece en Pareto al ganar recursos, arranque y build de core. El ADR
vigente es
`contexto/04_arquitectura/ADR/ADR-0001-arquitectura-base-baxy-1.md`.

La decisión no valida todavía Narrator/NVDA, DPI físico al 200 %, una GPU real
de 4 GB, una VM limpia, un instalador Windows, secretos ni tamper evidence del
journal.
