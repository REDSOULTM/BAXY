"""baxy-mind: el sidecar de inteligencia de BAXY 1.0 (ADR-0005).

Segundo proceso local sobre la frontera JSONL UTF-8 + Job Object del cuerpo
determinista. Aloja el router de intención por embeddings, el LLM de
conversación/tools (llama-server como subproceso propio) y el STT. El core
.NET no incorpora IA; este paquete no ejecuta efectos: propone operaciones
tipadas que el core valida con su schema, riesgo y confirmaciones.
"""

__version__ = "1.0.0"
