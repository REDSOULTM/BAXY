# Diff C01 revisado antes de publicar

Ámbito: producto, tests, scripts, evidencia C01, sellos mínimos Full, docs de la tanda.

| Pieza | Qué hace | Riesgo rechazado |
|---|---|---|
| `FieldProductChannel` | Admisión/turno/proyección compartida | No es API HTTP |
| `FieldUiBridge` | Adaptador origen WebView → canal | `HistoricalFieldOriginPolicy` se queda aquí |
| `ProductConductor` + `Host` | Entrada sin ventana, terminales honestos | WinExe espera con `WaitForExit` |
| `main.py --conductor` + `run_baxy_conductor.ps1` | Comando documentado | Sin flag de modo agente |
| Tests FieldProduct | Paridad e inyección de publicación | No prosa fija del modelo |
| Sellos STT + `test_wakeword_runtime_resources.py` | Full-blockers; C02 revalida | No se bajó umbral ni se ocultó skip |

`FieldUiBridge.cs` pierde ~850 líneas porque las rutas HTTP viven en el canal. Las sobrecargas `SubmitAsync` siguen: la pública exige `CanSend`; la interna despacha texto ya validado. El canal valida y publica la guía de rechazo en ambos adaptadores.

No se publica `HttpListener` / `MapGet`. Visual y acústica no se declaran verificadas.
