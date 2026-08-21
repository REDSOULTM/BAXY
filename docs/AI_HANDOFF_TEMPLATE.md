# Plantilla de handoff entre sesiones

Para **continuar** una sesión en otra: lo que la sesión siguiente no puede deducir del
código ni de `git log`. No es un informe de entrega — el informe de entrega está en
`documentacion/01_ARQUITECTURA/GUIA_AGENTES_IA/05_VALIDACION_SEGURIDAD_Y_HANDOFF.md`.

Reglas: **una página como mucho**. Rutas concretas, no descripciones. Comandos con su
resultado exacto, no «funcionó». Nada de narrar la conversación. Si algo se deduce
leyendo el diff, no se escribe aquí.

Dónde dejarlo: en el artefacto de la tanda (`artifacts/<goal>/HANDOFF.md`) o pegado en
el mensaje de arranque de la sesión siguiente. **Escríbelo a medida que avanzas**, no
al final: una compactación no debe borrar horas de trabajo pensado.

---

```markdown
# Handoff — <goal / tarea> — <fecha> — <commit>

## Objetivo
Una frase. El criterio de cierre, literal.

## Estado
Hecho: …
En curso: …
Sin empezar: …

## Decisiones tomadas
- <decisión> — porque <razón medida>. No reabrir sin dato nuevo.

## Archivos tocados
- ruta:línea — qué cambió y por qué

## Archivos relevantes aún sin tocar
- ruta — por qué va a hacer falta

## Hipótesis
Confirmadas: <hipótesis> → <evidencia: comando, artefacto o test>
Descartadas: <hipótesis> → <por qué murió>   ← lo más valioso del handoff

## Comandos ejecutados y resultado
- `comando` → resultado exacto (N pass / M fail / M skips ambientales)
- No ejecutado: <gate> — razón concreta

## Problemas pendientes
- <bloqueo> — con owner o condición. Deuda real, no ideas vagas.

## Siguiente acción recomendada
Una sola, concreta, con el fichero por el que se empieza.
```
