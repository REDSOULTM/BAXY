# Handoff — Goal 10.2.5 — 2026-09-01 — cierre en `main`

## Objetivo
BAXY permanece disponible por texto y voz con el mínimo trabajo en reposo; el árbol completo cumple ≤5 % visible y ≤2 % minimizado sin bloquear turnos.

## Estado
Hecho: diagnóstico, implementación, pruebas dueñas dobles, build/sello Field UI, turno físico, 60 s visible (1,8538 %), minimizado (0,7228 %), soak 15 min (media 0,7537 %, sin crecimiento monotónico) y Full final verde. En curso: commit/push. Sin empezar: ninguno.

## Decisiones tomadas
- ONNX continuo usa un hilo, ejecución secuencial y `allow_spinning=0`: el mismo score bajó de 28,4989 % a 0,65325 % de CPU máquina.
- Field UI duerme entre ticks: 4 Hz sólo en reposo, 30 Hz activa y suspensión nativa oculta; el árbol visible final dio 1,8538 %.
- Keep-warm, wake hop/score, modelos y sidecars permanecen: descargarlos habría cambiado latencia/capacidad y contradicho 09.5.9.
- Una narración no bloquea entrada; una composición fallida se liquida tras tres intentos; readiness caída recrea el sidecar en el siguiente turno.

## Archivos tocados
- `src/baxy_mind/onnx_runtime.py` — configuración ONNX común y restaurable.
- `src/Baxy.App/PresenceIdleSampler.cs` — CPU normalizada del árbol estable completo.
- `src/Baxy.App/MainWindow.xaml.cs` — suspensión/reanudación WebView2 según visibilidad.
- `src/Baxy.App/PendingModelMessageQueue.cs` — cola acotada y terminal.
- `src/Baxy.FieldUi/src/App.tsx` y `components/NeuralGraph.tsx` — scheduler 4/30 Hz.
- `artifacts/goal1025/resource-baseline-after.v1.json` — evidencia cuantitativa.

## Archivos relevantes aún sin tocar
- Ninguno.

## Hipótesis
Confirmadas: pools nativos ONNX giraban en espera; dos RAF WebView2 seguían repintando; la regla 10.2 medía sólo `Baxy.exe`; una confirmación/composición pendiente podía dejar “Thinking”. Evidencia: A/B, `py-spy`, medición por árbol y traza física.
Descartadas: el shell .NET era el consumidor principal (0,20 % baseline); descargar llama-server era necesario (0–0,10 % idle).

## Comandos ejecutados y resultado
- Owner Python dos veces → `221 passed, 101 subtests`, 0 fallos por corrida.
- Owner .NET dos veces → `107 passed`, 0 skips por corrida.
- `pnpm lint; pnpm exec tsc -b; pnpm build` → PASS; bundle `index-vrrSGhE0.js`.
- `./scripts/test_source_quality.ps1 -Mode Full` final → EXIT 0; .NET Integration 2853 pass/1 skip ambiental, Kernel 137/0, Providers 451/0, Setup 477/0, Contracts 60/0; Python 8775 pass/10 skips ambientales/446 subtests.

## Problemas pendientes
- Ninguno de producto conocido. Las omisiones Full son gates físicos/opt-in ambientales preexistentes y no se cuentan como aprobados.

## Siguiente acción recomendada
Tras cerrar y empujar este goal, abrir `documentacion/sprints/10.3_USO_REAL_A.md`.
