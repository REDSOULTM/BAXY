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

## Reapertura de identidad (bypass y modo accesible) de 2026-10-11

Estabilización U: la comprobación en vivo de la identidad (`I_identidad_notebook.md` §4) halló el ajuste de
confirmaciones escondido en una pestaña oculta y los modos de accesibilidad bloqueados y sin efecto. El panel
izquierdo muestra ahora `confirmaciones` (bypass sólo tras la pregunta propia de la vista, apagado con un toque,
y un indicador permanente en la barra de título) y el `perfil` normal/accesible sin candados. El modo accesible
vive en el perfil (`presentation-mode`), cambia sólo la presentación —zoom del host, contraste, foco visible, sin
movimiento— y se lee del host, sin copia en `localStorage`. El título del documento es `BAXY` (`lang="es"`).
Build deliberado `pnpm build` con el grafo fijado (reproducible byte a byte antes del cambio).

- `dist/index.html`: `9CDBE4F642A97472FFAB2CC47FA7420B792F3D7E88DC95A0CAA695311B469BCA`
- `dist/assets/index-DivO9-Mf.css`: `4770C047AD8CDAF2C40BE5392F6002C21E1375D3FABF9AFF7A69A1A8EC5D50DC`
- `dist/assets/index-Ln-pnDgH.js`: `164222722B5EDCE3255EF49716F3988765CC8A7B28F878948F2BCD501C077FF0`
- sello conjunto source + payload: `12E633C9AF4742B656DD14C5865A8355CA7904313234789B0204D8B9FDA06036`

Revisión U (H1): la vista lee y escribe bypass por su propia ruta (`/confirmation`); el panel histórico ya no lo
lleva. Build deliberado con el mismo grafo.

- `dist/index.html`: `00475538CE2BFB5B90CF81FC10A26379FCF109761DDE9A240E4BFD9958A102E6`
- `dist/assets/index-DivO9-Mf.css`: sin cambios
- `dist/assets/index-C1M38p-E.js`: `B2A4985772C1641058F68E7FBBEB5F58D30D256020F3DC6328B8F17AF1B3CC9C`
- sello conjunto source + payload: `E0E7B6DBD0E46CC07E2B238B831362F898D2387A0C0DF1DB8ADCEA2AADD96B20`

## Reapertura de honestidad (notebook, ronda A) de 2026-10-16

La vista dice lo que el producto hace. El aviso de bypass nombra todo lo que deja de confirmar; la voz es la
palabra «Baxy» y el clic derecho (el modo «ptt» era el mismo bucle de palabra de activación y se fue); fuera el
modo `?debug`, el estado `standby` que el host nunca manda, el proxy de dev a un backend que Renew no tiene y los
fallbacks sin `field-native-bridge.js`; comentarios corregidos. `prototype.css` pierde 28 variables sin lector, la
copia del prototipo que el rediseño redefine y las reglas que ningún elemento casa (`.bar*`, `.metric*`,
`.left-header .dots`, `.hot`, `@keyframes recPulse` y `pulseDot`): el estilo computado de cada elemento, comparado en Edge headless antes
y después (vista por defecto, cada panel, ventana estrecha y modo accesible), no cambia. Build deliberado
`pnpm build` con el grafo fijado (reproducible byte a byte antes del cambio).

- `dist/index.html`: `AE7473B0D5DDD11C6AC4D4701DB705E5D2C28A777B735BF03063E29E42F20732`
- `dist/assets/index-COQjHLMx.css`: `8DE4457A681B697B4B51D7F1794EA110C090BB50DC36AF05F2F269AD331380F6`
- `dist/assets/index-QIqCwDlN.js`: `ADF10A563BB172CF40E31357B03E5D4EE8077DCC99F0D2010A8329CF1BA74578`

## Reapertura de honestidad (notebook, ronda B) de 2026-10-16

El aviso de bypass y su etiqueta accesible dicen hasta dónde llega: deja de confirmar lo que la persona pide; lo que
BAXY propone por su cuenta (el latido) sigue esperando su sí, y borrar en el panel de memoria sigue en dos pasos
(«borrar», «confirmar borrado»). Build deliberado `pnpm build` con el grafo fijado.

- `dist/index.html`: `548E75C082BE6AAA80253EC96F69111C037BD277B3CA7136870596D2B7F12AFF`
- `dist/assets/index-COQjHLMx.css`: sin cambios
- `dist/assets/index-DiHBS7rP.js`: `05C457592758E4EA44ACAF14A184ED40DFF48F86C4DC72F3D26B85AE20BDD241`

## Ronda final de auditoría (PC) de 2026-10-16

La etiqueta de la barra de título en bypass dice «bypass · sin confirmar lo que pides» (antes «sin confirmaciones»,
que decía de más: el latido sigue esperando el sí y el panel de memoria sigue en dos pasos). Build deliberado
`pnpm build` con el grafo fijado.

- `dist/index.html`: `B4505CD551AF50D301CE2F3B0C6E357F520B6959A6C7F2DF963FCCB7FD76EA3A` (ronda final 25 de BAXY Renew: apunta al bundle nuevo)
- `dist/assets/index-COQjHLMx.css`: sin cambios
- `dist/assets/index-CyCfzHRV.js`: `8B8C4C720A8237DDEDAA7FFBE21E50E1FFF0161F83EDABFFF2AAD3BD2F6A55F3` (reconstruido en las rondas finales 21 a 25 de BAXY Renew: el panel de memoria, su pie y el contador dicen «desactivada» o «—» sin leer, mientras carga o tras una lectura fallida; un cambio hecho con su lista sin releer se dice hecho; y, en la 25, los botones Sí/No van bajo la pregunta más nueva)

## Ronda final 40 de BAXY Renew (PC) de 2026-10-17

El panel de actividad guarda las 80 líneas más nuevas y su cabecera decía «80 entries» como si fuera el total: ahora
cuenta las recibidas en la sesión y, pasado el tope, dice «80 of N entries». Build deliberado `pnpm build` con el grafo
fijado.

- `dist/index.html`: `949D417241189CFB53542206E1CB8DF2C8663E99685A546D13D772B2C1FCA3D6` (apunta al bundle nuevo)
- `dist/assets/index-COQjHLMx.css`: sin cambios
- `dist/assets/index-CaampMEG.js`: `E4ABA773D9C51DA4C94D1DDFC1FE283E671F0AB83D93F6290583AEA27D66D0DF` (sustituye a `index-CyCfzHRV.js`)
