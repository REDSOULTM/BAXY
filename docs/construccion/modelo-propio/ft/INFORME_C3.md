# Informe final del ajuste c3 (2026-10-31)

Escrito por un ayudante de la sesión principal del PC el sábado 31-10 por la mañana, con lo que había en disco. Todo está
cerrado salvo el **banco ciego c3** (§11), que corre en el portátil desde las 08:35 y termina hacia las 22:30. Lo que no se
hizo dice «**no hecho**». No hay textos de la encuesta, de pedidos reales ni de casos del banco: sólo ids y cifras.

Nombres: **c2e1** = el modelo que estaba en producción; **base** = c2e1 medido con el prefijo c3; **A** y **B** = las dos
semillas de `c3r9b_1` (el adaptador que quedó); **Laya** = System One. «Banco amplio» = `reales_todo` (todos los pedidos
reales del autor, la encuesta y 1.663 textos de desarrollo pegados; `<evaluacion>\ft_v1\c3\reales_todo\informe.md`).

## 1. Resumen

1. **En producción desde el 31-10 a las 06:25, en el portátil y en el PC: la semilla A** (`c3r9b_1-sA`, sha `485595f7…`) con la
   App de `ft-c3-final` **f778d5d35** (`Baxy.exe` `d38419da…`) y **Laya apagada**. Hay respaldo y vuelta atrás en las dos (§7).
2. **B ganó el banco amplio, pero no se quedó:** en «Guardar como» ×3 dijo haber guardado en el Escritorio sin hacerlo en
   2 de 3 pasadas. A dijo la verdad 3 de 3 (y 1 de 1 en el PC), aunque sólo guardó bien una vez (§2).
3. **El modelo mejora en los pedidos del autor** (+23,5 casos de 1.538, IC +9,5/+39,2; frente a la producción con Laya,
   +21,5, IC +3,5/+40,0) **y casi no pierde en no actuar ante texto pegado** (−6,5 de 1.663, IC −13,2/+0,2).
4. **El 65 % de los fallos del e2e eran de la App** (70 de 108 en corridas válidas), no del modelo. Se arreglaron uno por
   uno ocho problemas (§6); el que más se notó: borrar una carpeta por nombre pasó de 110 s a 11 s.
5. **La mente de producción no recibía la lista de apps instaladas**: un nombre con un espacio no separable hacía que el
   contrato rechazara la lista entera. Con la lista: 75/75 nombres de app correctos; sin ella, entre 15 y 30 de 75.
6. **Laya no aporta nada medible** (−3,0 casos, IC −14,5/+9,0) y quedó apagada.
7. **No pasa todas las puertas del plan**: en el e2e del portátil bajan E017 y E021, y varias puertas no se midieron (§3). Se
   desplegó por el visto bueno de diseño para desplegar al ganador; el banco ciego dirá si se queda.
8. **Gasto en RunPod: US$237,71** (el plan presupuestaba US$80). Todos los pods están parados y se terminan el domingo.

| Medida | Antes | Después (A + f778d5d35, Laya apagada) |
|---|---|---|
| Banco amplio, pedidos + encuesta (1.538 casos; pod 2, 4 corridas) | base 83,7 %; producción con Laya 83,8 % | **85,2 %**: +23,5 casos frente a la base (IC +9,5/+39,2), +21,5 frente a la producción (IC +3,5/+40,0) |
| Banco amplio, dev: no actuar ante texto de desarrollo (1.663) | 98,2 % | 97,8 %: −6,5 casos (IC −13,2/+0,2) |
| Feria ×6 (pod 2) | 254/300 | **262/300** |
| decision2 s0 (pod 2, una corrida) | 202/270 | 198/270 |
| e2e de práctica en el PC (30 casos × 3, mismo código 80684a524) | 83/90, pass^3 25/30 | **88/90**, pass^3 28/30 |
| e2e de práctica en el portátil (30 × 3, código anterior a los arreglos) | 86/90, pass^3 26/30 | 86/90, pass^3 28/30; **bajan E017 (3→1) y E021 (3→1)** |
| Nombre correcto al abrir una app (75 pedidos, catálogo del portátil) | c2e1 sin lista: 15/75 | **75/75** con la lista (A sin lista: 30/75) |
| Lista de apps que ve la mente (humo del 31-10) | 0 nombres, `verified false` | portátil 285 nombres; PC 580 nombres y 30 juegos |
| «bórrala» de una carpeta del escritorio (humo en el PC) | 110 s hasta preguntar, 92 s tras el «sí» | **11,2 s y 3,1 s** |
| «Guardar como» con nombre, en el escritorio (humo) | sobrescribía el archivo de origen y decía otra cosa (3df619e01) | A: honesto 3 de 3 en el portátil y 1 de 1 en el PC; guardado bien 1 de 3 |
| Laya | encendida | apagada |
| Banco ciego c3 (160 misiones, oficial frente a A × 3) | — | **se completa al terminar (§11)** |

## 2. Qué quedó en producción y por qué la semilla A

| | Producción anterior (29-10) | Producción desde el 31-10 06:25 |
|---|---|---|
| Modelo | c2e1, sha `8a4b6ce3…affc8` | **c3r9b_1-sA**, sha `485595f734f9…e499f0e`, 2.740.937.440 bytes |
| App y mente | PC: App e8cfed24c (`Baxy.exe` `80bdd726…`) + mente 4530e077c; portátil: 52f8e2a18 | **`ft-c3-final` f778d5d35** en las dos: `Baxy.exe` `d38419da…`, `baxy-core.exe` `dc99878b…`, mente `mind-src\f778d5d35efb` |
| Laya | encendida | **apagada** (`%LOCALAPPDATA%\BAXY\renew\system_one.off`) |
| Prefijo | el de siempre | c3 (`confirm_pending` con «yes, no or unclear», catálogo neutro) |

Por qué A y no B (detalle en `DESPLIEGUE_C3.md` §13–§16, rama `ft-c3-despliegue`, commit 49fae37b8):

- En el banco amplio **B era igual o mejor que A**: B − A = +2,2 casos en pedidos (IC −7,0/+11,5) y +3,5 en dev (IC
  −1,0/+8,8). Por eso fue el primer intento, tres veces (§13, §14, §15).
- **B pide `appId` «Settings»** y, sin la lista de apps, la App no lo resolvía en un Windows en español: «configuración de
  sonido» fallaba con B y abría con A. Arreglado en la App (f298e6b20) y con la lista de apps (c0c1a0409, 01c5849d9).
- **En «Guardar como», con la App ya arreglada (f778d5d35), B mintió 2 de 3 veces**: guardó en la carpeta de origen y
  dijo «en el escritorio». A, con la misma App, dijo la verdad las 3 veces en el portátil (una vez guardó bien; dos veces no
  guardó y lo dijo) y en la pasada del PC (guardó en el escritorio con el nombre recortado «prueba c3.txt» y lo dijo tal
  cual). Por la regla «nunca decir algo falso» se revirtió B (06:09) y se desplegó A (portátil 06:12, PC 06:20).

Receta de A (y de B, con otra semilla): LoRA sobre el adaptador de c2e1, módulos M1, rango 32, α 32, LR 1e-5, una época
(361 pasos, lote 16, calentamiento 5 %), datos `c3r9b` (5.727 muestras, §5), A100 del pod 2, 62 min cada semilla.
Semilla A 20261030, B 20261031.

## 3. Puertas del plan (§5 de `research_notes/ft/00_PLAN_FT_C3.md`), una por una, para A

| Puerta | Qué pedía | Resultado de A | ¿Pasa? |
|---|---|---|---|
| **Banco ciego c3** | logrado / límite honesto / éxito falso / fallo por mayoría de 3; meta: más logradas que el oficial, éxitos falsos ≤ oficial + 1, pass^3 ≥ | corriendo | **§11** |
| e2e duras (E003, E011, E017, E021, E022, E023, E029; mayoría de 3; ningún caso baja) | — | PC: todas por mayoría (E021 2/3, igual que la base); sólo baja E010 3→2, que no es puerta. portátil: **E017 3→1 y E021 3→1** | **no** (en el portátil) |
| e2e Δ ≥ 0 y pass^3 ≥ | — | PC +5 y +3; portátil 0 y +2 | sí |
| e2e con Laya como en producción (PC, umbrales 0,4/0,6/1) | informativo | base 87/90, A 88/90; E017 1/3 frente a 2/3 de la base | baja E017 |
| Confirmaciones 15/15 «sí» y 8/8 «no», mayoría de 3 | — | **no hecho con A** (sólo la base y 6 brazos del 29-10, una corrida, §A.4). En los humos, «no sé» nunca borró (todas las pasadas del 31-10, con A y con B) | sin medir |
| «Hace siempre» de `LIMITES` | — | **no hecho** | sin medir |
| v11 directo / riesgo / no_puedo / texto | — | **no hecho** | sin medir |
| decision2 ×3 | ≥ base menos el ruido | una corrida en el pod 2: 198 frente a 202 | incompleta |
| Feria ×6 | ≥ base menos el ruido (±6/300) | 262 frente a 254 (+8) | sí |
| Falsedades juzgadas por Opus ×6 (≤ base) | — | **no hecho** (la base corrió s0 y s1 en el portátil sin juez) | sin medir |
| Held-out ×2 y v11 ×2 | confirmación | **no hecho**. Lo reemplazó en la práctica el banco amplio (3.201 casos), que no es ciego | sin medir |
| 10 familias, de ≤ 1/6 a ≥ 4/6 en ≥ 6 | — | «antes» medido (pass@4 de la base, §A.6); **«después» no hecho** | sin medir |
| Recursos: VRAM ≤ 4 GB, RAM ≤ 5 GB, p50 ≤ 1 s | — | en el pod 2, VRAM del llama-server 4.367 MiB (base 4.371); p50 del pod no comparable (pod cargado). En el PC **no medido** con A | sin medir en el PC |
| Personalidad a ciegas | — | **no hecho** | sin medir |
| Tres pruebas de la identidad por texto ×3 | — | dentro del banco ciego (misiones de juego con Luanti, con Minetest Game instalado con el sí del autor); aparte, **no hecho**; por voz el domingo, **no hecho** | §11 |
| «En las manos» del usuario | baja o igual | lo cuentan los jueces del banco ciego | §11 |
| Regla de selección (ganar al oficial en la diferencia pareada decision2 + feria y pasar todas las puertas) | — | suma en el pod 2: 460 frente a 456 (+4), sin IC; la elección real se hizo con el banco amplio y los humos | no se aplicó tal cual |

Lo que bajó en el portátil: E017 es «guardar en el Bloc de notas», un fallo de la App (B1 de la auditoría, §6) arreglado
después de esas corridas; E021 es del modelo (tras el «sí» y la salida de la consola, vuelve a pedir el mismo comando y
termina preguntando). Ninguna corrida e2e de práctica se repitió con la App de f778d5d35: **no hecho**.

## 4. Cómo se llegó a c3r9b

| Ronda | Qué se probó | Resultado |
|---|---|---|
| 1 (29-10) | 27 adaptadores y un control: desde el modelo base (M1, M2), continuando c2e1 con LR 5e-5 a 5e-6, RPO, mezclas de pesos, checkpoints parciales | Ninguno ganó a la base en la selección del PC (decision2 + feria, /568): el mejor −11. Todos suben en decision2 (+1 a +14) y bajan en la feria (−13 a −50). La LR manda, no la duración. Tablas en el anexo A |
| 2 (30-10 madrugada) | banco amplio con los 4 mejores de LR baja (c2c1, c2c05, c2cr05, c2cr-sB) y luego c2cr2, c3r3, c3r4 | pedidos +7 a +17 casos, todos dentro del ruido; dev −10 a −20, salvo c3r3_1-sB (+2). c3r4 (todas las familias juntas) −39,5 y dev −76 |
| 3 (30–31-10) | c3r6 … c3r10 y mezclas (tabla de abajo) | c3r9 y c3r9b, los primeros fuera del ruido en pedidos |

Ronda 3, banco amplio en el pod 2 contra su base (Δ en casos; IC 95 % por remuestreo de casos):

| Candidato | Pedidos + encuesta | Δ (IC) | Dev | Δ dev (IC) |
|---|---|---|---|---|
| c3r6_1-sA | 82,3 % | −26,0 (−47,5/−3,0) | 95,6 % | −40,0 (−55,0/−26,0) |
| c3r6_05-sA | 82,0 % | −30,0 (−51,5/−8,0) | 96,2 % | −29,0 (−43,0/−15,0) |
| c3r6t_05-sA | 83,0 % | −15,5 (−31,0/+0,5) | 97,3 % | −15,5 (−24,5/−7,5) |
| c3r7t_05-sA | 83,5 % | −7,5 (−23,5/+9,0) | 96,9 % | −21,0 (−30,0/−12,0) |
| c3r8m_1-sA | 84,0 % | +1,5 (−16,0/+19,0) | 97,4 % | −14,0 (−21,5/−7,0) |
| w6_05-sA-l0.5 | 84,1 % | +2,0 (−13,0/+18,5) | 97,2 % | −16,0 (−24,5/−8,0) |
| w6_03-sA-l0.3 | 84,2 % | +4,5 (−9,5/+18,0) | 97,7 % | −9,0 (−16,0/−2,0) |
| w7t_05-sA-l0.5 | 83,5 % | −7,0 (−20,5/+6,5) | 97,1 % | −17,5 (−26,0/−9,5) |
| c3r10_1-sA (c3r9b + F29) | 84,6 % | +9,0 (−6,0/+25,0) | 97,5 % | −11,5 (−19,5/−3,5) |
| c3r9_1-sA | 85,1 % | +22,8 (+8,8/+37,5) | 97,5 % | −11,5 (−19,2/−4,2) |
| **c3r9b_1-sA** (4 contra 4) | 85,2 % | **+23,5 (+9,5/+39,2)** | 97,8 % | **−6,5 (−13,2/+0,2)** |
| **c3r9b_1-sB** (4 contra 4) | 85,3 % | **+25,8 (+10,2/+41,8)** | 98,0 % | **−3,0 (−9,0/+2,5)** |
| producción (base + Laya) | 83,8 % | −3,0 (−14,5/+9,0) | 98,2 % | +0,5 (−4,0/+5,5) |

(Pedidos + encuesta de las filas c3r6–c3r10 = media ponderada de las dos partes de la tabla original; las de c3r9 y c3r9b
son las del informe.) Ruido: la base cambia 43 casos de pedidos y 16 de dev entre dos corridas suyas. Las pérdidas de dev
de c3r9b son pocas e inestables (A 26 casos, 4 firmes; B 22, 2 firmes): consola y archivos ante ítems cortos de lista,
encargos con contexto de IDE y especificaciones; ninguna familia se rompe.

Lección de la ronda 3: **más familias juntas fue peor** (c3r5–c3r7, de 7.000 a 13.212 muestras, todas negativas). Ganó la
receta pequeña: c3r3 + lo on-policy de c2e1 (F27) + tres familias acotadas (F25, F26, F28).

## 5. Datos: familias y recetas

Notas de integración: `<evaluacion>\ft_v1\c3\familias\NOTAS_INTEGRACION.md` (39 puntos); recetas c3r4–c3r10:
`<evaluacion>\ft_v1\c3\c3r4\informe.md`. Todas las familias pasaron la fuga contra bancos, canarios y los 742 literales de la
encuesta; las de juez sólo dejan lo que jueces Claude a ciegas dieron por «correcto».

| Familia | Qué enseña | Muestras | ¿En c3r9b? |
|---|---|---|---|
| F01_F02 | «no pude comprobarlo»; responder hablando a una confirmación | 736 | no (c3r5–c3r7) |
| F03_F04 | mensajes; cerrar o reiniciar sin apagar | 421 | no |
| F05_F06 | instalar y desinstalar; juegos | 352 | no |
| F07_F08 | idioma y variedades; la Calculadora por tres caminos | 1.293 | no |
| F09 | vía genérica de la pantalla (mirar → pulsar → escribir → comprobar), con el motor arreglado | 337 | no |
| F10_F20 (C10–C20) | misiones, Discord/WhatsApp, hilos, sinsentido y saludo, anotar en una app, rutas dictadas, BAXY mismo, relativo sin cantidad, ventanas, Office, cola | 1.320 | no |
| F_e2e | pasos dentro de una tarea («guardar como», hora del contexto) | 357 | no |
| F21_F24 | preguntar si falta el dato, texto pegado, límite honesto, negación y condición | 750 | sólo 5 demostraciones («déjalo en N» sin referente) |
| F25 | saber de una entidad → `web.search` con el nombre pelado o las palabras dichas | 306 | **sí** |
| F26 | una respuesta ambigua a una confirmación nunca aprueba | 184 limpias de 265 | **sí** |
| F27 | F21–F24 on-policy de c2e1 (su propia salida buena, juzgada) | 882 | **sí** |
| F28 | volumen o brillo relativo sin cantidad → preguntar cuánto | 70 | **sí** |
| F29 | no ejecutar las órdenes de un texto de desarrollo pegado | 191 (167 tras recortar) | no (c3r10 no ganó) |
| F11–F15 de c3r (dentro de c3r3) | saludar 19, sin sentido 12, anotar en app 89, erratas de voz 145, «sube/baja… a N» 85 | 350 | sí, vía c3r3 |

| Receta | Qué lleva | Muestras | Resultado |
|---|---|---|---|
| c3r3 | c3r2 limpio: sin 61 incorrectas de la revisión ciega ni la familia dev, con el texto juzgado | 4.190 | +13,5 / +11,5 (ruido); dev −5 / +2 |
| c3r5 / c3r6 / c3r7 | c3r3 + todas las familias F01–F26 (y sus recortes a 7.000) | 7.000–13.212 | todas peores en pedidos y en dev |
| c3r8m | c3r3 + F25 + F26 | 4.889 | +1,5; dev −14 |
| c3r9 | c3r3 − 146 muestras con consultas reformuladas + F25 nueva + F26 + F27 + 5 demos | 5.661 | +22,8; dev −11,5 |
| **c3r9b** | c3r9 + F28 − 4 contradicciones («déjalo en N» sin historial) | **5.727**, sha `1b5300c7…`, prefijo `3b42ddb1…` | **+23,5 / +25,8; dev −6,5 / −3,0** |
| c3r10 | c3r9b + F29 recortada | — | +9,0; dev −11,5 |

Render de c3r9 y c3r9b en el pod 2, CPU, zona horaria America/Santiago (el pod en UTC daba mal la hora del prompt: punto
16 de las notas). Los datos de la primera ronda (c2rep, c3, c3s, c3gs, c3r, c3r2) están en el anexo A.6.

## 6. La App

Auditoría de todos los fallos e2e del 29 y 30-10 (`<evaluacion>\ft_v1\c3\AUDITORIA_FALLOS_APP.md`; regla de diseño: si el
modelo eligió bien y la App falló, es de la App y se arregla para todos):

| | Eligió mal (modelo) | Eligió bien, falló la App | Entorno del banco |
|---|---|---|---|
| PC | 18 | 32 | 71 |
| portátil | 20 | 38 | 12 |
| **Total** | **38** | **70 (65 % de los 108 de corridas válidas)** | 83 (todos en corridas anuladas) |

La VM de Azure dio 853 fallos en 168 corridas, sin detalle por caso (VM apagadas o sin SSH): no se pudieron repartir.

Arreglos, uno por cada problema (informe completo en `INFORME_FALLOS_APP_C3.md` de `ft-c3-final`, ocho vueltas; ninguno
nombra una app ni un idioma, y cada uno tiene su prueba roja antes y verde después):

| Problema | Causa | Arreglo | Efecto medido |
|---|---|---|---|
| **M6b Discord** | el primer Escape sólo vaciaba el buscador rápido y lo dejaba abierto | 840853a74, 3e48e4bf7, 81ce9e4dd | visto en vivo en el PC: buscador cerrado y foco en Discord |
| **app.open por ejecutable** («calc.exe», «mspaint») | `app_not_found` con candidatos sin la Calculadora (15 fallos, E010/E003/E011) | 3db37d8a7 + 7d155b409 | el ejecutable abre la app instalada que lo lanza |
| **Calculadora** con paréntesis en el teclado Estándar | se negaba (`calculator_needs_scientific_mode`, 7 fallos de E011) | ade6a43fe + 3df619e01 | se pulsa en un orden que da el mismo valor («(250+175)*2» → 850) |
| **Diálogo de archivos de Windows, en cualquier app** | el motor no sabía qué es un diálogo de archivos: «Guardar» contaba como hecho aunque el archivo fuera a otra carpeta (40 fallos, E017, la primera causa) | 367031bd9, 7cf26e904 | en vivo en el portátil: Bloc de notas, Paint, Chrome, Edge y Word guardan y abren; los fallos se dicen (`file_dialog_*`) |
| **Papelera por nombre con plazo de 8 s** | recorría escritorio, documentos y descargas enteros, dos veces, sin plazo | e43e08c8b | «bórrala»: 110 s → 11 s; «sí»: 92 s → 2–3 s |
| **Índices ligados a la mirada** | tras un clic la vista se renumeraba y el texto por el índice viejo iba a otro control | 8a7d9cd6a | se actúa sobre el control que el modelo vio (`indexAsked`/`indexNow`) o sobre nada |
| **La visión no pulsa rótulos inexistentes** | un punto de la visión en blanco o en un icono se pulsaba y salía `completed` | 015aef031 (fusionado en f778d5d35) | `visible_button_not_found` con los controles más parecidos; nada pulsado |
| **Lista de apps guardada y enviada aunque llegue tarde** | un espacio no separable en un nombre hacía que el contrato rechazara la lista; si la lectura no cabía en los 6 s del saludo, la mente se quedaba sin apps toda la sesión | c0c1a0409, 01c5849d9 | 285 nombres en el portátil y 580 en el PC; 75/75 nombres correctos frente a 15–30 de 75 |

Otros arreglos de la App en el ajuste: sigla dicha por la persona en una búsqueda («ONU», 0d062d9cd); «Settings» en Windows
en inglés (00df7ffb1) y «Settings» por «Configuración» en Windows en español (f298e6b20); búsqueda en un paso y relectura
de texto en Chromium y apps empaquetadas (M1, M1b, M2); clics que el post-read negaba (M3); controles repetidos con un
solo índice (M5).

Verificación de f778d5d35 (`<evaluacion>\ft_v1\c3\verde_final_pc.log`): `Baxy.slnx` Release 0 advertencias y 0 errores;
Providers.Windows 3664/3664, App 469/469, Kernel 991/991, Contracts 74/74.

## 7. Despliegue

Del 30-10 a las 23:40 al 31-10 a las 06:25 hubo cinco pasos (`DESPLIEGUE_C3.md` §11–§16):

| Paso | Modelo + App | Resultado |
|---|---|---|
| §11, 31-10 00:02 PC, 00:41 portátil | A + 3df619e01 | desplegado; «bórrala» 110 s en el PC |
| §12, 01:30–01:47 | A + e43e08c8b | desplegado; «bórrala» 11 s; «Guardar como» a medias |
| §13, 02:53–03:15 | B + 7cf26e904 | revertido en el portátil (Configuración no abría con «Settings»); PC sin tocar |
| §14, 03:15–03:23 | B + e43e08c8b | revertido en el portátil (misma causa, del modelo) |
| §15, 04:58–05:22 | B + 6f6600ace | revertido en el portátil («Guardar como» afirmó un nombre que no guardó) |
| **§16, 05:50–06:25** | **B y luego A + f778d5d35** | B revertido (mintió 2 de 3); **A desplegado en el portátil (06:12) y en el PC (06:20)** |

Humo final de A + f778d5d35: presentación, cuenta, búsqueda de una entidad y volumen pasan; Configuración › Sonido abre
(7,1 s portátil, 6,9 s PC); «bórrala» / «sí» 11,4 / 2,2 s (portátil) y 11,2 / 3,1 s (PC); «no sé» no borra; la Calculadora abre; un
solo llama-server con A y ninguno de Laya. Lo que abrieron las pruebas se cerró por PID; los restos se movieron.

Respaldos y vuelta atrás (con BAXY cerrado):

```powershell
# portátil, desde <evaluacion>\wt\ft-c3-despliegue
powershell -ExecutionPolicy Bypass -File scripts\renew\ft\revertir_c3.ps1 -Maquina nb -Respaldo <evaluacion>\entrega\respaldo-c3-20261031-061203
# PC, desde <evaluacion>\wt\c3-despliegue
powershell -ExecutionPolicy Bypass -File scripts\renew\ft\revertir_c3.ps1 -Maquina pc -Respaldo <evaluacion>\deploy\respaldos-c3\respaldo-c3-20261031-062047
```

Eso devuelve A + e43e08c8b. La producción original (c2e1 con e8cfed24c en el PC y 52f8e2a18 en el portátil) sigue en los
respaldos de §11: `<evaluacion>\deploy\respaldos-c3\respaldo-c3-20261030-235951\` (PC, con el `BAXY.lnk` original) y
`<evaluacion>\entrega\respaldo-c3-20261031-003927\` (portátil).

Cosas del despliegue que quedan así:

- En el PC la App es una copia en caliente en `versions\1.1.1` y `BAXY.lnk` apunta a `Baxy.exe`. El Setup 1.1.2 se
  construyó pero salió con código 30 al instalar (causa sin encontrar); mientras siga la copia en caliente, ningún Setup
  puede actualizar, volver atrás ni desinstalar sin correr antes `revertir_c3`.
- Ramas en hub **sin fusionar** en `baxy-renew`: `ft-c3-final` (f778d5d35) y `ft-c3-despliegue` (49fae37b8). Esperan el
  «adelante» del autor.
- El catálogo de apps de prueba del PC se renombró a `application-catalog.v1.json.prueba-0429`; no hace falta devolverlo.

## 8. Laya (System One)

| Medida | Sin Laya | Con Laya |
|---|---|---|
| Banco amplio, pedidos + encuesta (base) | 83,7 % | 83,8 %: −3,0 casos (IC −14,5/+9,0) |
| Banco amplio, dev (base) | 98,2 % | +0,5 casos (IC −4,0/+5,5) |
| e2e de práctica en el PC, A | 88/90 | 88/90 |
| e2e de práctica en el PC, base (días distintos) | 83/90 (29-10) | 87/90 (30-10) |

En el banco amplio vale la diferencia pareada por caso (−3,0 y +0,5, las dos dentro del ruido); los porcentajes salen de
corridas distintas (base a 4 corridas, producción a 2). En el e2e la base sube con Laya, pero son días distintos y A queda
igual. No aporta nada medible con A y ocupa un segundo llama-server. Quedó apagada en las dos máquinas con el interruptor del
usuario (`system_one.off`; se enciende borrándolo). Ese interruptor también apaga Laya en los bancos que se lancen con
`scripts\run_renew.cmd` en esa máquina. Regenerar Laya: **no hecho** (el plan lo pedía sólo si ganaba).

## 9. Costo

**US$237,71 en RunPod** en total; el plan presupuestaba US$80. Todos los pods están parados (sólo cobran el disco) y se
terminan el domingo, después de comprobar con el sha que cada GGUF está en `<evaluacion>\ft_v1\out`. Lista de pods en
`<evaluacion>\ft_v1\pods_parados_para_terminar.txt`. Lo que encareció: 5090 que daban NaN (se perdieron tres brazos), un
pod parado que pierde su GPU y no vuelve, el vigía que apagó pods con trabajo a medias, y A100 a US$1,79/h desde el
mediodía del 29-10 (anexo A.9).

## 10. Pendiente o abierto

### No hecho

- Confirmaciones ×3, `LIMITES`, v11, falsedades juzgadas, held-out ×2, personalidad, las 10 familias «después» y las
  tres pruebas de la identidad por texto aparte y por voz (§3).
- **Ayudas retiradas: ninguna.** Lista cerrada de 21 en `research_notes/ft/prep/AYUDAS_A_RETIRAR.md` §4; sólo se hizo la
  fila 0.6b (`calculator_next` partido, `ft-c3-ayudas` b5c6fb57d y 0c2035f70).
- **`LIMITES_DE_BAXY.md` sin actualizar.** Se sabe que está desfasado en tres puntos: instalar y desinstalar piden el sí,
  el clic derecho no es un límite y comprar o reservar se confirman.
- e2e de práctica de A con la App final, en el PC y en el portátil.
- Recursos de A en el PC (VRAM, RAM, p50).

### Datos para el próximo ajuste (lo que el modelo hace mal hoy)

- **«Guardar como» con nombre**: escribir el nombre en el campo después de navegar a la carpeta, con la mirada al día, y
  sólo entonces «Guardar».
- **No seguir tras un fallo de escritura**: si escribir el nombre falla, no pulsar «Guardar» ni confirmar nada.
- **El nombre entero**: «prueba c3 guardado.txt» y no «prueba c3»; lo dictado se escribe tal cual.
- **No decir más de lo que leyó el recibo** (lo que hizo caer a B): el final cuenta la carpeta y el nombre del recibo.
- Tras la salida de un comando de consola, contestar con ella y no repetir el comando (E021).
- Completar sólo la tarea nombrada (E023).
- Contratos que cambiaron y hay que regenerar en los datos: el recibo de la Calculadora con paréntesis (ahora `completed`
  con `pressedInOrder`), la vista y los recibos del diálogo de archivos, `indexAsked`/`indexNow` y
  `visible_control_identity_stale`, y el «no encontrado» de la visión con los controles más parecidos.
- Volumen o brillo sin cantidad: el autor dio por buenas las dos respuestas (preguntar cuánto o subir 10; 31-10); F28
  enseña a preguntar y el prefijo c3 dice «10 si no dijo número». Conviene que los datos no contradigan al prefijo.
- F29 (texto de desarrollo pegado, sobre todo encargos con contexto de IDE): c2e1 casi nunca acierta (8 %); hace falta
  demostración escrita, no on-policy.

### La App, abierto

- Texto por teclado que pierde las primeras teclas en un Bloc de notas recién abierto (1 caso) y una respuesta que no
  sonó (1 caso): sin prueba que falle.
- Epic leído sólo por OCR, sin índices (M4) y su doble «sí» al desinstalar (M7, decisión de producto).
- `input.key.press` no tiene `ctrl_<letra>`: un atajo de otro idioma (Ctrl+G) no se puede pulsar; va por el menú.
  Ampliarlo es decisión del líder.
- Un foco que no es Win32 (XAML, Chromium) y no toma texto no se detecta; una subcarpeta de un lugar conocido sin ruta.
- La App sale con código 1 al cerrarse (`conductor_failed`, anterior al ajuste).
- Selectores de archivos sin árbol accesible (GTK, Java): no hay ninguno instalado para medir.

### Operación

- Terminar los pods el domingo (§9).
- Fusionar `ft-c3-final` y `ft-c3-despliegue` con el «adelante» del autor.
- Si el banco ciego da que A no cumple, decidir con el autor si se vuelve a c2e1 (respaldos de §7).

## 11. Banco ciego c3 — resultado: se completa al terminar (ETA 22:30)

Sellado el 29-10 a las 00:37, antes de tocar datos: `holdout_c3.7z` sha256 `e07d5acf…f400a1`, 160 misiones, canario
C3-020, sobre 15 apps gratuitas que BAXY nunca vio, instaladas sólo en el portátil. Abierto **una vez, por el script**, el 31-10
a las 08:31 (`BANCO_CIEGO_LISTO.md` §0b); tres arranques fallidos antes de la primera misión no cuentan como apertura.

| Brazo | Código | Modelo | Laya |
|---|---|---|---|
| oficial | 52f8e2a18 | c2e1 (`8a4b6ce3…`) | encendida |
| candidato | f778d5d35 (`ft-c3-final`) | A (`485595f7…`) | apagada |

Orden: oficial s0, candidato s0, oficial s1, candidato s1, oficial s2, candidato s2; empezó a las 08:35. Después,
`puntuar_c3.ps1`: tres jueces Claude a ciegas por misión y corrida con `CRITERIO_C3.md`, y `tabla_c3.py`. Meta del plan:
el candidato logra más que el oficial, sus éxitos falsos no pasan de los del oficial + 1 y su pass^3 no baja.

| Métrica | oficial | candidato |
|---|---|---|
| misiones comparadas | | |
| logrado (mayoría de 3) | | |
| límite honesto (mayoría de 3) | | |
| éxito falso (mayoría de 3) | | |
| fallo (mayoría de 3) | | |
|   de ellas sin mayoría (cuentan como fallo) | | |
| pass^3 (logrado en las 3) | | |
| misiones con algún éxito falso (alguna corrida) | | |
| «en las manos» (mayoría) | | |
| oráculo solo: ok por mayoría | | |
| oráculo solo: pass^3 | | |
| logrados por corrida | | |
| primera señal p95 (todos los turnos) | | |
| primera señal p95 (turnos que sonaron) | | |
| primera señal p50 | | |
| turnos con primera señal ≤ 3 s | | |
| turnos sin ningún sonido | | |
| primera respuesta p95 | | |
| duración de BAXY por misión, media (s) | | |
| duración de BAXY por misión, mediana (s) | | |
| duración del caso con setup y oráculos, media (s) | | |
| robos de foco (pasos; meta 0) | | |
| misiones con robo de foco | | |
| frente movido y devuelto (pasos, informativo) | | |
| pasos con teclado/ratón físicos (informativo) | | |

**McNemar** (oficial → candidato, logrado por mayoría): —.
**Meta del plan**: más logradas —; éxitos falsos ≤ oficial + 1 —; pass^3 ≥ oficial —. **—**.
Misiones que gana el candidato: —. Que pierde: —.

Límites de esta medida (de `BANCO_CIEGO_LISTO.md` §6): los robos de foco sólo se ven en los recibos; «en las manos» sólo
lo dicen los jueces; la primera señal es el primer sonido; los jueces no están calibrados con ≥ 100 casos por clase.

---

## Anexo A. Primera ronda (29-10): tablas de la selección

Del borrador del 29-10 a las 22:50; se conservan las cifras y se cierran sus pendientes.

### A.1 Selección en el PC (decision2 /268 + feria 50 × 6 = /300)

Fuente: `<evaluacion>\renew_v1\runs\c3-<brazo>-d2-s0.jsonl` y `c3-<brazo>-feria-s<N>.jsonl`.

| Brazo | Qué es | decision2 | Δ | feria ×6 | Δ | por corrida | selección /568 | Δ |
|---|---|---|---|---|---|---|---|---|
| **base del día** | c2e1 + prefijo c3 | 227 (226, 226) | — | 254 | — | 40–44 | **481** | — |
| oficial (c2e1, prefijo viejo) | — | 232–234 (canal de mensajes) | — | 251 (28-10, canal de mensajes) | — | — | — | — |
| mc2c-sA-l0 (control) | c2e1 pasado por la receta del pod | 228 | +1 | 248 | −6 | 40–42 | 476 | −5 |
| c2c-sB | continúa c2e1, LR 2e-5, c3gs | 232 | +5 | 238 | −16 | 38–41 | 470 | −11 |
| mc2c-sA-l0.5 | WiSE-FT λ 0,5 de c2c con c2e1 | 229 | +2 | 241 | −13 | 39–41 | 470 | −11 |
| c2c-sA | continúa c2e1, LR 2e-5 | 230 | +3 | 238 | −16 | 39–41 | 468 | −13 |
| mrpo-sA-l0.5 | WiSE-FT λ 0,5 de rpo-sB | 231 | +4 | 237 | −17 | 39–41 | 468 | −13 |
| rpo-sB | RPO sobre m1-sB | 234 | +7 | 233 | −21 | 38–40 | 467 | −14 |
| m1-sB | desde base, módulos M1, c3 | 231 | +4 | 234 | −20 | 38–40 | 465 | −16 |
| c2c5-sA | continúa c2e1, LR 5e-5 | 235 | +8 | 229 | −25 | 37–39 | 464 | −17 |
| m1s-sB | M1 + semilla 10 % (c3s) | 230 | +3 | 232 | −22 | 38–39 | 462 | −19 |
| m2-sA | desde base, módulos M2, c3 | 239 | +12 | 222 | −32 | 35–39 | 461 | −20 |
| c2rep-sB | réplica de c2 sin semilla | 239 (240, 240) | +12 | 219 | −35 | 36–37 | 458 | −23 |
| c2c5-sB | continúa c2e1, LR 5e-5 | 232 | +5 | 223 | −31 | 36–38 | 455 | −26 |
| m2-sB | M2, c3 | 234 | +7 | 217 | −37 | 35–37 | 451 | −30 |
| m1s-sA | M1 + semilla 10 % | 231 | +4 | 215 | −39 | 35–37 | 446 | −35 |
| m2gs-sA | M2 con c3gs | 241 | +14 | 205 | −49 | 33–35 | 446 | −35 |
| c2rep-sA | réplica de c2 sin semilla | 230 (229, 229) | +3 | 212 | −42 | 33–36 | 442 | −39 |
| rpo2-sA | RPO sobre m2-sA | 238 | +11 | 204 | −50 | 33–35 | 442 | −39 |
| m1-sA | M1, c3 | 228 | +1 | 213 | −41 | 35–36 | 441 | −40 |

- Ruido: el control es el mismo c2e1 (405 de 426 tensores idénticos) y da −6 en la feria; la base va de 40 a 44 por
  corrida. ±6/300 no distingue.
- Recursos: p50 de decision2 0,83–0,84 s la base y 0,78–0,91 s los brazos; VRAM 4.001 MiB la base y 4.011–4.016 MiB los
  brazos.
- La criba en el PC de los finalistas de LR baja (c2c1, c2c05, c2cr, c2cr05…): **no hecha**; pasaron directamente al
  banco amplio (§4).

### A.2 En los pods (Linux, cada pod contra su base; decision2 /270)

| Pod | Brazo | Qué es | feria ×6 | Δ | decision2 | Δ |
|---|---|---|---|---|---|---|
| 2 | base | — | 254 | — | 202 | — |
| 2 | c2c05-sA | continúa c2e1, LR 5e-6, c3gs | 246 | −8 | 199 | −3 |
| 2 | c2c1-sA | continúa c2e1, LR 1e-5, c3gs | 244 | −10 | 201 | −1 |
| 2 | c2cr05-sA | continúa c2e1, LR 5e-6, c3r | 244 | −10 | 200 | −2 |
| 2 | c2cq-sA = q50 | c2c a ¼ de época | 244 | −10 | 202 | 0 |
| 2 | q203-sA | c2c a época completa | 243 | −11 | 200 | −2 |
| 2 | q150-sA | ¾ de época | 242 | −12 | 202 | 0 |
| 2 | q100-sA | ½ época | 240 | −14 | 200 | −2 |
| 2 | c2c-sA | LR 2e-5 | 237 | −17 | 202 | 0 |
| 2 | c2c5-sA | LR 5e-5 | 230 | −24 | 201 | −1 |
| 2 | rpo3-sA | RPO sobre c2c-sB | 224 | −30 | 199 | −3 |
| 2 | rpo2-sA | RPO sobre m2-sA | 213 | −41 | 207 | +5 |
| 2 | c3r9_1-sA (30-10) | ronda 3 | 272 | +18 | 199 | −3 |
| 2 | **c3r9b_1-sA** (31-10) | ronda 3 | **262** | +8 | 198 | −4 |
| 2 | c3r9b_1-sB (31-10) | ronda 3 | 258 | +4 | 200 | −2 |
| 2 | c3r10_1-sA | ronda 3 | 264 | +10 | 193 | −9 |
| 3 | base | — | 245 (×10: 408/500) | — | 199 | — |
| 3 | c2cr05-sA | LR 5e-6, c3r | 249 | +4 | 198 | −1 |
| 3 | c2cr-sB | LR 1e-5, c3r | 247 | +2 | 199 | 0 |
| 3 | c2c05-sA | LR 5e-6 | 246 (×10: 410/500) | +1 (+2) | 198 | −1 |
| 3 | c2c1-sA | LR 1e-5 | 242 (×10: 404/500) | −3 (−4) | 204 | +5 |
| 3 | r100-sA | c2c1 a ½ época | 235 | −10 | 200 | +1 |
| 3 | rpo-sB | RPO sobre m1-sB | 232 | −13 | 201 | +2 |
| 3 | c2c-sB | LR 2e-5 | 230 | −15 | 197 | −2 |
| 3 | m2-sA | M2 desde base | 225 | −20 | 204 | +5 |
| 3 | m2gs-sA | M2 con c3gs | 211 | −34 | 206 | +7 |

Fuente: `<evaluacion>\ft_v1\c3\bancos_pod\pod2|pod3\pod-<brazo>-<banco>-s<N>.out` (última línea). PC y pod coinciden en la
feria para los brazos medidos en los dos. Con LR 2e-5 la feria apenas cambia entre ¼ y 1 época. 6 de los ~10 puntos que
perdían los de LR baja eran FER024 («baja … a N»), lo que llevó a F15 y luego a F28.

### A.3 e2e de práctica (30 casos × 3; las corridas `*.void*` no cuentan)

Puertas duras: E003, E011, E017, E021, E022, E023, E029. «Bajan» = menos aciertos que la base de la misma máquina.

Notebook, código ft-c3:

| Brazo | por corrida | total | pass^3 | puertas duras no 3/3 | bajan | suben |
|---|---|---|---|---|---|---|
| base | 28, 29, 29 | 86/90 | 26/30 | E011 2/3, E023 2/3 | — | — |
| c2c-sB | 30, 29, 30 | 89/90 | 29/30 | ninguna | ninguno | E011, E014, E023 |
| c2c1-sA | 30, 29, 30 | 89/90 | 29/30 | E023 2/3 | ninguno | E008, E011, E014 |
| c2cr05-sA | 30, 29, 30 | 89/90 | 29/30 | ninguna | E006 3→2 | E008, E011, E014, E023 |
| m2-sA | 28, 29, 30 | 87/90 | 27/30 | E011 2/3, E029 2/3 | E029 3→2 | E014, E023 |
| m1-sB | 26, 26, 28 | 80/90 | 24/30 | E017 0/3, E011 2/3, E029 2/3 | E017 3→0, E014 2→0, E006, E029 | E023 |
| **c3r9b_1-sA** | 29, 28, 29 | 86/90 | 28/30 | **E017 1/3, E021 1/3** | **E017 3→1, E021 3→1** | E008, E011, E014, E023 |

Notebook con los arreglos E008/E011 (`c3app-*`): base 29, 28, 28 = 85/90 (E021 1/3); c2c-sB 30, 30, 29 = 89/90 (E029
3→2). Qué binario corrió: `console.txt` dice 7ee83b524 y la segunda vuelta del informe de fallos dice fe0c80d68; E008 no
falla en ninguna de las 6, lo que apoya fe0c80d68. **No comprobado del todo.** `c3base-s0b-codigo-viejo`: 26/30.

PC (`c3pc-<brazo>-s*-e2e`, todas en 80684a524):

| Brazo | por corrida | total | pass^3 | puertas duras no 3/3 | bajan | suben |
|---|---|---|---|---|---|---|
| base | 27, 27, 29 | 83/90 | 25/30 | E017 0/3, E011 2/3, E021 2/3, E023 2/3 | — | — |
| c2c1-sA | 30, 28, 30 | 88/90 | 28/30 | E021 2/3 | E010 3→2 | E008, E011, E017, E023 |
| c2c-sB | 29, 28, 29 | 86/90 | 27/30 | E021 1/3, E011 2/3 | E021 2→1 | E017, E023 |
| c2c05-sA | 28, 30, 28 | 86/90 | 27/30 | E017 1/3, E011 2/3 | E012 3→2 | E008, E017, E021, E023 |
| rpo3-sA | 27, 27, 28 | 82/90 | 25/30 | E021 0/3, E017 2/3, E029 2/3 | E021, E020, E010, E029 | E008, E011, E017, E023 |
| c2cr05-sA | 29, 29 (s2 **no hecha**) | 58/60 | — | E011 | — | — |
| c3r9_1-sA | 30, 29, 30 | 89/90 | 29/30 | E021 2/3 | ninguno | E008, E011, E017, E023 |
| **c3r9b_1-sA** | 30, 29, 29 | **88/90** | 28/30 | E021 2/3 | E010 3→2 | E008, E011, E017, E023 |
| c3r9b_1-sB | 29, 29, 29 | 87/90 | 29/30 | **E017 0/3** | ninguno | E008, E011, E021, E023 |
| c3r3_1-sB | 29, 30, 30 | 89/90 | — | — | — | — |
| c3r8m_1-sB | 30, 30, 29 | 89/90 | — | — | — | — |
| c3r10_1-sA | 29, 29, 29 | 87/90 | — | — | — | — |
| base con Laya (`c3pcs1`) | 29, 28, 30 | 87/90 | 27/30 | E017 2/3, E029 2/3 | — | — |
| A con Laya (`c3pcs1`) | 30, 29, 29 | 88/90 | 29/30 | E017 1/3 | — | — |

Las corridas `c3pc-*` llevan el servidor de Laya con umbrales 0 (sin efecto); las `c3pcs1-*`, los de producción
(0,4/0,6/1). VM Azure: sin detalle por caso (§6); no comparable (B 23/29 en la VM frente a 29/30 en el PC).

### A.4 Confirmación (una corrida; `conf_bench.py`)

| Brazo | sí | no | otras |
|---|---|---|---|
| base | 15/15 | 8/8 | 6/6 |
| c2c-sB, rpo-sB, m1-sB, m1s-sB | 15/15 | 8/8 | 6/6 |
| m2-sA | 15/15 | 8/8 | 5/6 |
| c2c1-sA (pod 3; canal de mensajes) | 15/15 | 8/8 | 6/6 |

Las dos corridas más que pide la puerta y la medida con A: **no hechas**.

### A.5 Qué se descartó en la primera ronda

| Qué | Por qué (cifra) |
|---|---|
| c2rep (réplica de c2 sin semilla) | gana decision2 (+3/+13) pero pierde la feria: 212 y 219 frente a 254 |
| Entrenar desde el base (m1, m2, m1s, m2gs) | feria −20 a −49; e2e de m1-sB 80/90 con E017 0/3 |
| Semilla al 10 % | no mueve la feria (215 frente a 213; 232 frente a 234) |
| m1p (prefijos del PC y del portátil) | parado por decisión de diseño («universal para casi cualquier PC») |
| m1g (catálogos grandes desde el base) | perdido dos veces (NaN en la 5090; vigía); los catálogos grandes siguieron en c2c |
| M2 frente a M1 | m2-sA, mejor e2e del grupo desde base (87/90), pero feria 222 |
| LR 5e-5 (c2c5) | selección 464 y 455; feria pod 2 230 |
| RPO (rpo2, rpo3) | feria pod 2 213 y 224; rpo3 E021 0/3 en el PC |
| WiSE-FT λ 0,5 (mc2c, mrpo) | no recupera la feria: 241 y 237 |
| Menos época con LR 2e-5 | la feria casi no depende de la duración: 240–244 |
| c2cr2 (c3r2, F15) | banco amplio −1 a +17, dev −10 a −20; no superó a c3r3 |
| Escenas | fuera de las puertas por decisión de diseño (latido fuera) |

### A.6 Datos de la primera ronda

| Conjunto | Muestras | Qué lleva | Brazos |
|---|---|---|---|
| c2rep | 2.255 | v2 re-renderizada al formato c3, sin semilla ni latido | c2rep-sA/sB |
| c3 | 2.607 | regeneración on-policy de c2e1; 0 canarios | m1, m2 |
| pares RPO | 766 | 383 on-policy + 383 de regresión | rpo-sB, rpo2, rpo3 |
| c3s | 2.894 | c3 + semilla anonimizada al 9,9 % | m1s |
| c3p | 2.896 | c3s con prefijos del PC y del portátil | fuera por decisión de diseño |
| c3g | 2.890 | c3s con 8 catálogos neutros grandes | m1g (perdido) |
| c3gs | 3.203 | c3 + toda la semilla sin datos personales (604) + 8 catálogos grandes | c2c, c2c5, c2cq, c2c1, c2c05, m2gs |
| c3r | 4.219 | c3gs + F11–F14 + replay de c2e1 (17,9 %); fuga 0 | c2cr, c2cr05 |
| c3r2 | 4.304 | c3r + F15 «sube/baja … a N» (85) | c2cr2 |

Pass@4 de la base por familia (antes; 384 pedidos de plantilla, T 0,8): F01 45/46, F02 20/36, F03 15/30, F04 27/30, F05
25/36, F06 46/46, F07 47/52, F08 27/30, F09 35/42, F10 35/36. Lista disjunta firmada: 314 pedidos, sha256 `e062d953…374c`.
El «después»: **no hecho**.

Hallazgos que afectan a otros datos (`<evaluacion>\ft_v1\c3\c3r_informe.md`): `regen.sh` no variaba la semilla;
`verificar.py` daba INVENTA a un nombre instalado con número; la plantilla F03 esperaba la Calculadora y no `calculate`.

### A.7 Decisiones de diseño durante el ajuste

Latido y escenas fuera (29-10 00:42); semilla anonimizada ≤ 10 % (11:50); ningún catálogo real en los datos, «universal
para casi cualquier PC» (12:55); continuar desde c2e1 con toda la semilla sin datos personales (13:45); visto bueno para
desplegar al ganador sin más confirmaciones (noche del 30 al 31-10); instalar Minetest Game para el banco ciego (31-10 08:29); volumen
sin cantidad: preguntar o subir 10, las dos valen (31-10).

### A.8 Incidencias y lecciones

| Cuándo | Qué pasó | Qué se hizo |
|---|---|---|
| 29-10 01:12 | `crear_pods.ps1` (REST v1) dio 400 | pod creado con el MCP de RunPod |
| 29-10 02:31 | sin memoria en la 5090 | `--grad-ckpt` y `expandable_segments` |
| 29-10 03:12 | portátil: lo lanzado por SSH nace en la sesión 0, sin escritorio | tarea programada interactiva en la sesión 1 |
| 29-10 04:29 | Windows Update reinició el PC | colas retomadas a las 08:58 |
| 29-10 10:47 | 5090 agotadas; un pod parado pierde su GPU | A100 SXM 80 GB (US$1,79/h) |
| 29-10 13:47 | 5090 con loss NaN desde el paso 3 | sólo A100/A6000; tres brazos perdidos |
| 29-10 13:47 | **fallo propio:** el vigía apagó el pod 2 con brazos a medias | vigía y recolector cuentan los brazos en marcha |
| 29-10 15:53 y 18:41 | e2e anulados por una ventana de Configuración | el corredor la cierra por PID al empezar |
| 29-10 16:27 | F: lleno por 99 GB de ranuras | ranuras a E: |
| 29-10 18:50 | `sort -t- -k2 -n` tomaba el ckpt-50 por el final | `sort -V` |
| 29-10 19:41 | el PC se reinició a la fuerza (VRAM llena) | un llama-server por GPU |
| 30-10 | pod 4 dejó de responder; cuota del volumen del pod 2 llena dos veces | tandas repetidas en el pod 2 |
| 30-10 | render en UTC: la hora del prompt no era la del objetivo | render con TZ America/Santiago |
| 31-10 00:0x | el humo cerró por PID procesos ajenos con PID reutilizado | filtro por hora de creación |
| 31-10 04:31 | una prueba en vivo se cruzó con la de otro agente en el portátil | cerrada por PID y repetida con el portátil libre |
| 31-10 08:31–08:34 | tres arranques fallidos del banco ciego antes de la primera misión (lista, BOM, ventana) | arreglados en el script; la apertura sigue siendo única |
