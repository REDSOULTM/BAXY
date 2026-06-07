# Contribuir a Baxy

¡Gracias por tu interés! Este proyecto es un asistente de voz local con un fuerte
énfasis en **honestidad, reproducibilidad y privacidad**. Estas pautas mantienen
esa calidad.

## Entorno de desarrollo

```bash
# 1. Clonar + venv (Python 3.10 — es el runtime objetivo)
git clone <repo-url>
cd gemma4_agent
py -3.10 -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 2. (opcional) UI web — necesitás Node + pnpm
cd gemma4_agent/ui_field && pnpm install && pnpm run build
```

Mirá el [README](README.md) para los pasos completos (modelo GGUF, llama.cpp, etc.).

## Correr los tests

La suite vive bajo `gemma4_agent/tests/`:

```bash
python -m pytest gemma4_agent -q
```

Antes de abrir un PR: **la suite debe quedar verde**. No rompas tests que pasan;
si un test queda obsoleto por tu cambio, actualizalo (no lo borres a la ligera).

## Principios no negociables

Estos vienen del corazón del proyecto y los revisamos en cada PR:

1. **Medí, no celebres.** No afirmes que algo "funciona" sin un número contra un
   criterio definido de antemano. Reportá resultados crudos aunque sean malos —
   la honestidad sobre fallos es lo que mantiene sano al proyecto.
2. **Honestidad estructural.** El agente nunca debe afirmar que hizo algo que no
   verificó. Si una acción no se pudo confirmar, el reply lo dice. No agregues
   "éxitos" fabricados ni respuestas enlatadas.
3. **El LLM responde, no los hardcodes.** Nada de tablas de respuestas fijas ni
   listas de keywords por idioma para decidir qué hacer. Lo determinista permitido
   es: clasificación por embeddings multilingües, guardas estructurales (miden la
   forma, no el contenido) y resolución por estado del SO.
4. **Universalidad.** El proyecto es multi-idioma y multi-acento. No optimices
   sobre una sola voz/idioma; evaluá contra un conjunto diverso.
5. **Todo OSS y gratis.** Sin APIs de pago obligatorias ni dependencias cloud
   propietarias. Si la única solución buena es paga, proponela y dejá que se
   decida — no la impongas por default.
6. **Reproducibilidad.** Todo dataset/artefacto debe poder regenerarse desde
   scripts versionados. Si bajás algo, dejá el script de descarga, no solo el
   archivo.
7. **Confirmá lo irreversible.** Las operaciones destructivas (borrar, sobrescribir,
   matar procesos del usuario) van gateadas con confirmación.

## Reportar bugs

Incluí: qué esperabas, qué pasó, el comando/fraseo exacto, y (si aplica) el log.
Para bugs del agente, el fraseo importa: el modelo es no-determinista y el mismo
pedido puede rutearse distinto.
