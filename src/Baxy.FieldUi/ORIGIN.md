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

## Reapertura de progreso de 2026-09-07

C03 UI102 localiza una etiqueta de progreso oculta por el borrador del input.
FieldCenter usa una región role=status existente antes de recibir la etiqueta;
retira su uso como placeholder y conserva el lector y su borrado terminal.
Bridge, autoridades y grafo de dependencias conservados. Build deliberado
pnpm build; evidencia antes/después en C03/PRUEBAS_UI102.md y ASTRA-TRAMO-103.md.

- `dist/assets/index-BdsTtBhL.js`: `775C33943717459934D9CE5E55CC0DE5735F30BD6907914FA24CE31F4FAFC5BC`
- `dist/assets/index-Bvtbe9rc.css`: `D681CF835B0FC96C38A9F3E53F7E3BF31DCA80D1D0FB4A1DFF8117E9B8E85DF9`
- `dist/index.html`: `86272A3E53398F2C061659D7CE0ACAA5F8A3C902CE9E334E096C8B0D8B63F742`
- sello conjunto source + payload: `5396C5B4C33FAA3603CED416017EED5D44E0B03949A8C82D920C43F25BAF3687`

## Reapertura de error de composición de 2026-09-07

C03 UI107 muestra composition_failed con Idle tras avería real. Fuente108
añade error al estado consumido por el lector existente: grafo Error y
etiqueta Response error en una región alert persistente, sin prosa de
respuesta ni movimiento de foco. La App conserva diagnóstico tipado y
proyecta la cola pendiente como thinking. ADR-0008 reabierto; pnpm build
deliberado con las mismas dependencias. Pruebas en ASTRA-TRAMO-108.md.

- `dist/assets/index-B7EBy9jN.css`: `A5262CAD74EC68E7C2836B2ADA0DD53A06DD016F58F89793657A88B1887561C1`
- `dist/assets/index-Dh8gdcnz.js`: `3526427606D8FD7395A0B55B1C2AB270C3282D65AB124568205570E50CBC9D0F`
- `dist/index.html`: `01D05090C87B6100703765F2A80051EBE6747CA260B0F6362B25826CD6A9320A`
- sello conjunto source + payload: `99FF9838C07CE32F25F329AACF830F62D8DD70C5931E26C2EC483B710B2CA657`
