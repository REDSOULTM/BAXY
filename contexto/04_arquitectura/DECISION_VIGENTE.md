# Decisión de arquitectura vigente

Estado de la arquitectura base: **aceptada el 2026-07-14**. Las decisiones de
entrega reproducible se aceptaron el 2026-07-15.

ADR canónico:
`ADR/ADR-0001-arquitectura-base-baxy-1.md`.

Decisión de subsistema aceptada:
`ADR/ADR-0002-estado-gpu-local.md` — identidad GPU por DXGI y uso puntual por
PDH, sin subprocess ni inclusión implícita en `summary`.

Decisiones de entrega aceptadas:

- `ADR/ADR-0003-paquete-release-reproducible.md` — producto y paquete
  reproducibles same-host.
- `ADR/ADR-0004-setup-embebido-transaccional.md` — Setup NativeAOT
  autocontenido, verificación embebida y foundation transaccional por usuario.

La arquitectura base conserva un host .NET 10 WPF y un core .NET 10 NativeAOT
en proceso separado, con JSONL UTF-8 por stdin/stdout, instancia única y
ownership mediante Job Object. Por decisión explícita del usuario, ADR-0008
sustituye únicamente su presentación WPF pura: el host sirve dentro de WebView2
el `dist/` React histórico de `4a83f2d` y lo conecta mediante mensajes nativos,
sin servidor HTTP ni autoridad adicional. Core, planner, stores y voz no cambian.
La decisión anterior ganó 82,004484/100 frente a 79,992351/100 del híbrido
WPF + Rust; esa medición sigue siendo evidencia histórica, no un veto contra la
restauración visual solicitada.

WPF + Rust 1.97 estático es el fallback reproducible. Python permanece como
candidato de sidecar especializado si gana un subsistema.

Permanecen abiertas las elecciones de modelos y runtimes de inferencia,
router/planner productivos, VAD/STT/TTS, visión, integración general de memoria,
computer-use, providers restantes y el lifecycle final del Setup con integración
Windows. El provider GPU local
queda decidido solo para los scopes finitos del ADR-0002. El corte del torneo
tampoco aprueba todavía
el perfil físico de 4 GB, Narrator/NVDA, DPI físico al 200 %, firma,
autenticidad ni instalación en VM limpia.
