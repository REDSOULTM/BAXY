# BAXY Field UI — origen congelado

Esta carpeta es una exportación literal de la GUI histórica mostrada por el
usuario. Los 39 archivos originales se recuperaron de Git sin reconstruirlos.

- commit: `4a83f2d082d6b0fec8297e801b96a0da620b059e`
- ruta original: `gui/ui_field`
- asunto: `BAXY 1.0 — reconstrucción limpia con todo lo útil del proyecto anterior`
- fecha del commit: `2026-07-02 06:09:01 -0400`

La composición y el estilo de esos 39 archivos siguen siendo la base visual. Se
agregaron `tsconfig.node.json` y `vite.config.ts`, recuperados literalmente del
commit `63843e4bd09bb121bcd37a575ceee565df754a1a`, porque el primer commit ya los
referenciaba pero no los había incluido.

## Reapertura visual de 2026-08-11

Una revisión física del MVP encontró textos de marca obsoletos en la barra de
título y en ajustes. El source React histórico se conservó intacto. La identidad
visible se corrige mediante una superposición acotada en el puente nativo de
`Baxy.App`. Esa superposición también limita ajustes a diagnósticos de solo
lectura con respaldo nativo; no cambia el contrato `baxy.field.v1`, la
navegación, las autoridades ni el acceso de red.

Como parte de la revisión se ejecutó deliberadamente el build con el grafo
fijado por `pnpm-lock.yaml`. Los bundles JS/CSS conservaron sus nombres y bytes;
Vite normalizó únicamente el formato del documento de entrada `dist/index.html`.
El árbol conjunto vigente queda sellado por `MainWindowShellContractTests` con
SHA-256
`0F6C38D1E3C377012BD7231372363334DB7ADD51845578074E59EFB1195E8122`.
La aplicación actual adapta el contrato HTTP/WS histórico mediante el puente
nativo separado en `Baxy.App`.

## Reapertura de recursos de 2026-08-31

Goal 10.2.5 sustituyó los dos RAF permanentes por schedulers que duermen sin
cambiar composición, estado, velocidades temporales, bridge ni acceso de red:
4 Hz en reposo, 30 Hz en conversación y 1 Hz sin render oculto (además de la
suspensión nativa). El build fue deliberado con el grafo
fijado por `pnpm-lock.yaml`.

- `dist/index.html`: `72C4FAC55D36BD9976755FBC4B1B480B1FDFF1E8D8863ACEDB6543EDC5C5DF86`
- `dist/assets/index-vrrSGhE0.js`: `240A887D548C2BA1DDB88B32183BC13986F8160F22E95BAB5B431D3696631743`
- `dist/assets/index-CjozYCnU.css`: `201D80C4A2F1FFD6E52367C0C130F6373F1A2C217C46C51789017F5F9327AAA2`
- sello conjunto source + payload: `0F6DCDA5DCF7DFA8A89C64763EF4E75067967977C5673121197825F8EB0E1C71`
