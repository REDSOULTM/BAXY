# Skills de BAXY — arqueología y contraste actual

Fecha: 2026-07-16.

## Qué se conservó y qué se corrigió

Carter y los BAXY anteriores ya tenían reglas por dominio en prompts, módulos
`domain_tools`, archivos `tool_rules/*.md` y providers dedicados. Eran valiosas
porque enseñaban particularidades que un LLM no debe adivinar: Discord usa
selector de destino, Steam separa catálogo/propiedad/instalación/compra, Spotify
necesita now-playing, Office valida Open XML y WhatsApp no comparte atajos con
Discord. El problema era que esas reglas se cargaban de forma amplia, podían
quedar desincronizadas del registro real y a veces mezclaban consejo con
autoridad de ejecución.

BAXY conserva ese conocimiento como skills versionadas junto al producto, pero
con una frontera estricta:

- la skill sólo orienta el planner; no ejecuta ni registra operaciones;
- toda operación nombrada debe existir en el catálogo público de ese arranque;
- ninguna skill puede ver o introducir `memory.*`;
- una misión carga como máximo tres skills y 12.000 caracteres;
- la selección exige solapamiento con la shortlist de tools, además de similitud
  semántica;
- el validador rechaza nombres, carpetas, metadata o tamaños fuera del contrato;
- schemas, riesgo, confirmación y postcondición siguen perteneciendo a .NET.

## Contraste con 2026

La [especificación Agent Skills](https://agentskills.io/specification) y las
implementaciones documentadas por [Microsoft Agent
Framework](https://learn.microsoft.com/en-us/agent-framework/agents/skills),
[VS Code](https://code.visualstudio.com/docs/agent-customization/agent-skills),
[OpenAI](https://openai.com/academy/skills/) y el repositorio de referencia de
[Anthropic](https://github.com/anthropics/skills) convergen en tres ideas:
directorio con `SKILL.md`, descripción que decide el trigger y divulgación
progresiva de metadata → instrucciones → recursos. También distinguen skills
de workflows: para efectos no idempotentes, checkpoints y aprobaciones deben
estar en un workflow durable, no sólo en instrucciones del modelo.

BAXY adopta esas ideas, con una extensión interna deliberada. Su frontmatter
incluye `operations` y `priority`, campos que no pretenden ser portables: son el
allowlist cerrado que vincula consejo y catálogo del producto. No se habilitan
scripts dentro de estas skills porque permitir que texto recuperado ejecute
código ampliaría la autoridad del planner. Si más adelante se exportan como
Agent Skills portables, esos campos deberán moverse a metadata con namespace y
pasar el validador oficial; el runtime interno seguirá verificando el allowlist.

## Catálogo implementado

Hay 16 skills: Discord, WhatsApp, Spotify, dos flujos Steam, captura/OCR,
calendario, Office, Bluetooth, impresión/escaneo, navegador/investigación,
archivos/backups, tareas/recordatorios/rutinas, notas, paquetes y control de
Windows. Cada una documenta las secuencias frágiles y los falsos éxitos que ya
aparecieron entre Carter y BAXY, sin repetir conocimiento general.

## Gates

1. Parseo UTF-8 y frontmatter cerrado.
2. Nombre igual a la carpeta, máximo 64 caracteres; descripción máxima 1.024.
3. Cuerpo máximo 500 líneas y archivo máximo 32 KiB.
4. Cero operaciones desconocidas o privadas.
5. Selección acotada por tools visibles y prompt máximo.
6. Pruebas de recuperación por dominio y de hard negatives.
7. La ejecución siempre vuelve a validar el plan en .NET; una skill nunca es
   evidencia de que una app, cuenta o hardware estén disponibles.
