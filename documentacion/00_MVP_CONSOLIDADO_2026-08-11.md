# MVP consolidado de BAXY — 2026-08-11 (campaña de tarde)

Este documento es la baseline vigente del MVP ejecutable. Sustituye como
referencia operativa a [00_MVP_2026-08-11.md](00_MVP_2026-08-11.md), que
conserva la historia de la mañana. No sustituye la meta:
[00_META_VIGENTE.md](00_META_VIGENTE.md) sigue fijando los criterios de cierre.

**Estado: corte A y corte C cerrados sobre oráculos ciegos frescos.** El corte C
falló primero en R4 (2/6), se reparó la causa y se volvió a medir sobre un
oráculo R5 disjunto: **6/6 misiones y 25/25 pasos verificados**. La sección 8
mantiene los defectos que siguen abiertos, sin maquillarlos.

---

## 1. Comando exacto

```powershell
cd D:\BAXY\source
.\run_mvp.ps1
```

Variantes verificadas en esta campaña:

```powershell
.\run_mvp.ps1 -ValidateOnly   # comprueba todo, no abre la app, código 0
.\run_mvp.ps1 -NoWake         # abre la app real sin micrófono automático
.\run_mvp.ps1 -Cpu            # ejecuta el LLM sin capas GPU
```

El lanzador no instala, no registra runtimes y no toca la instalación activa.

---

## 2. Arquitectura realmente utilizada

| Etapa | Componente elegido | Por qué |
|---|---|---|
| Interfaz | WPF/WebView2 + Field UI histórica sellada (ADR-0008) | Única UI real del producto |
| Host | Baxy.App .NET 10 | Valida el Core hijo contra su contrato compilado |
| Ejecución | Baxy.Core NativeAOT + Kernel + Providers.Windows | Catálogo tipado de 169 operaciones |
| Mente | `src/baxy_mind` sidecar Python 3.12 | Router, planner, lenguaje natural |
| LLM | **Qwen3-4B Q4_K_M** + llama.cpp b9980 | Venció localmente a tres candidatos (§6) |
| STT final | **Parakeet TDT 0.6B v3 int8** | Autoridad de transcripción |
| STT parcial | Nemotron Streaming 0.6B int8 | Sólo hipótesis parcial, nunca final |
| Wake | Cascada endpoint **v25a** | Candidata de desarrollo, **no promovida** |
| TTS | Degradación local SAPI | No hay voz neural registrada |

La mente propone, el Kernel autoriza, el Provider ejecuta. El lanzador no
agrega autoridad a ninguna de esas fronteras.

---

## 3. Estado medido en esta campaña

Todo lo siguiente se midió sobre el árbol final, después de la última
modificación relevante.

### 3.1 Compuerta de fuente Full — verde sobre el árbol final

`artifacts/mvp/source_quality_full_20260811_r5_final.log`
SHA-256 `4247bbbbaf6505bfecd0917d651491408aa164aa7d88cd1259ed9f84cf4050f9`

| Suite | Resultado |
|---|---|
| Baxy.Contracts.Tests | 59/59 |
| Baxy.Integration.Tests | 2.705/2.705 |
| Baxy.Kernel.Tests | 116/116 |
| Baxy.Providers.Windows.Tests | 442/442 |
| Baxy.Setup.Tests | 477/477 |
| **.NET total** | **3.799 · 0 fallos · 0 omitidas** |
| Python | **7.976** + 446 subpruebas |
| Release | 0 advertencias · 0 errores |
| Etapas | 11/11 |

Esta corrida es posterior a la reparación del reconocedor por cláusula y a la
apertura de R5, de modo que acredita el árbol que se entrega y no uno anterior.

### 3.2 Perfiles GPU y CPU — ambos verdes, remedidos sobre el árbol final

`artifacts/product/mind_budget_gate_qwen_final_20260811.json`
SHA-256 `6a8d8a56ace2104b0aed58d2a0a5af729ed6f078146f3bdb7c305985a11dc857`

| Perfil | Estado | Requests | Errores | VRAM pico | RAM pico | turn.decide p50 / p95 |
|---|---|---|---|---|---|---|
| GPU (99 capas) | passed | 45/45 | 0 | **3.065,6 MiB** / 3.072 | 3.078,6 MiB | 0,007 s / 0,763 s |
| CPU (0 capas) | passed | 45/45 | 0 | 109,5 MiB / 128 | **5.807,2 MiB** / 8.192 | 0,007 s / 9,405 s |

Narración GPU p50 0,250 s; CPU p50 4,874 s. Efectos ejecutados: 0.

La medición se repitió **después** de reparar el reconocedor por cláusula: la
corrida anterior
(`mind_budget_gate_qwen_repaired_cpu_contract_20260811.json`, SHA-256
`a91e8f50…`) acreditaba un árbol que ya no es el que se entrega y se conserva
sólo como historia de la reparación del contrato CPU.

### 3.3 Aplicación real — arranca y cierra limpio

`.\run_mvp.ps1 -NoWake` sobre el árbol final: procesos `Baxy`, `baxy-core` y
`llama-server` vivos, ventana principal real con título `BAXY` y handle
válido. Cierre normal con **0 procesos huérfanos**. Micrófono no abierto,
0 efectos.

---

## 4. Matriz funcional — corte A cerrado

Oráculo ciego **R2**, sellado y abierto una sola vez sobre este árbol.
Solapamiento normalizado con R1: **0**.

| Artefacto | SHA-256 |
|---|---|
| Corpus | `7ea3381410e8a1ec2d12991cb1217bc5dd207df6b1442826b56f059dfe4033ca` |
| Prerregistro | `51b3fb7847809b0be8de98ccde7849dc4e3fd3b617ec24bb8a1ea20b1db1b53e` |
| Resultado producto | `f87b32d768c96715e3040153d51180cf52c75dfdc3fb175437d09d413b295b39` |
| Rama Mind | `87433d5ea0d3dcc3e2ec740ddc8a1a821af0d16d97c28fbf715789347e20fc4e` |
| Rama memoria (TRX) | `33452ffdfd61058cbda6084fbbfd0419a806fa680d61940da4e786d876e94923` |

**Resultado: 169/169 exactos, 0 fallos, 0 efectos inseguros, 0 efectos ejecutados.**

| Rama | Casos | Exactos |
|---|---|---|
| Mind sidecar | 158 | 158 |
| Memoria privada (App) | 11 | 11 |

| Idioma | Casos | Exactos |
|---|---|---|
| Español | 80 | 80 |
| Inglés | 39 | 39 |
| Spanglish | 39 | 39 |

Las 31 familias cerraron en 1,0, cubriendo las 169 operaciones autenticadas:

`app` 3/3 · `audio` 5/5 · `backup` 8/8 · `bluetooth` 3/3 · `browser` 5/5 ·
`calendar` 2/2 · `capture` 2/2 · `clipboard` 4/4 · `email` 2/2 ·
`filesystem` 20/20 · `game` 11/11 · `input` 8/8 · `media` 6/6 · `message` 2/2 ·
`network` 5/5 · `note` 7/7 · `notification` 6/6 · `ocr` 1/1 · `office` 2/2 ·
`package` 2/2 · `peripheral` 3/3 · `reminder` 5/5 · `routine` 7/7 ·
`streaming` 2/2 · `system` 11/11 · `task` 9/9 · `vision` 1/1 · `web` 1/1 ·
`wifi` 6/6 · `window` 9/9 · más la rama privada `memory` 11/11.

### 4.1 Tasa partida por causa — obligatorio, no agregable

| Capa | Valor |
|---|---|
| Recuperación (`action_retrieval_accuracy`) | 1,0 |
| **Decisión cruda (`action_raw_decision_accuracy`)** | **0,9747** |
| Vetos / efectos inseguros | 0 |
| Exactitud final | 1,0 |

La decisión cruda **no** es perfecta: en 4 casos el modelo propuso mal antes de
que una compuerta posterior corrigiera. El resultado visible es correcto y
nada inseguro se ejecutó, pero reportar 1,0 a secas ocultaría dónde está el
trabajo pendiente.

**Límite de muestra, declarado y no disfrazado:** con 169 casos y cero fallos,
la cota inferior binomial unilateral al 95 % es **0,982**. La barra del corte A
es ≥ 99,9 %. Esta población **no puede** demostrar 99,9 %; sólo demuestra que
no hay ninguna familia rota. No se declara el corte A al nivel de la meta.

---

## 5. Corte C — abierto en rojo, reparado y cerrado en verde

### 5.0 Resultado final: R5 en 6/6

Tras reparar la causa se selló un oráculo **R5** disjunto y se abrió una sola
vez. **6/6 misiones, 25/25 pasos verificados, 0 efectos ambiguos, estado
`passed`.** Cubre en es/en/spanglish las seis formas de cláusula dependiente que
R4 expuso: cabeza de secuencia, verbo elidido, ordinal desnudo, cuerpo
participial, nominales de estado coordinados y lectura enclítica.

| Artefacto | SHA-256 |
|---|---|
| Prerregistro | `e8ecb08a14f3951262eb712c7d709b35a55df51533c4fae8169458888ce68a55` |
| Resultado | `a1837f416dea71520e17d2fdfa138516a400d51960204e61633143f14addd173` |
| Reconocedor reparado | `822143f2394a9664a1f0182110196147af1ee2c3bb2661ecaf306ee70774b49d` |

Trayectoria completa del corte C, que es lo que acredita la reparación:
**R4 2/6 → causa aislada → reparación acotada → R5 6/6 sobre corpus disjunto.**

R5 **no** reutiliza R4: su solapamiento exacto de objetivos es 0 y su
prerregistro declara `reuse_for_promotion_forbidden` sobre el corpus consumido.

### 5.1 La medición que falló primero

Oráculo **R4**, sellado y abierto una sola vez.

| Artefacto | SHA-256 |
|---|---|
| Prerregistro | `73dae08c816a1e6cdaad8459aeb1670972898295cb9fbe6a48b5abeb203b155c` |
| Resultado | `7e4b3e22772d88c1d7ef52122f2ce1621e2566c9b8155522cc08d9f7ea33a19c` |

**Resultado: 2/6 misiones, 10/31 pasos verificados. Estado `failed`.**

Seguridad intacta: **0 efectos ambiguos, 0 efectos no solicitados, 0 éxitos no
verificados**. BAXY no hizo nada incorrecto: **se abstuvo** de una misión que no
podía fundamentar por completo. Fue un defecto de cobertura, no de seguridad.

### 5.1 Mecanismo exacto

El fallo vive en el reconocedor **por cláusula**, no en el planner. La cabeza
verbal de la cláusula decide:

| Cláusula | Resuelve |
|---|---|
| `reporta el estado de la red` | ✅ `network.status` |
| `termina con el estado de la red` | ❌ nada |
| `check audio status and network status` | ❌ nada |

Cláusulas encabezadas por un verbo de secuencia (`termina con`, `finish by`) o
con verbo elidido (`otra nota Sol…`, `read la segunda`) no resuelven. Cuando la
ruta multi-dominio de texto completo tampoco cubre el pedido,
`unresolved_compound_contract` dispara un veto de conservación y el turno se
abstiene.

**Hipótesis descartada durante el diagnóstico:** se sospechó que la conjunción
spanglish `y` era la causa. La sonda mostró que el inglés `and` falla igual. El
discriminador es la cabeza verbal, no el idioma.

### 5.3 La reparación aplicada

Cinco brechas acotadas, todas en la herencia de cabeza entre cláusulas:

| Forma | Reparación |
|---|---|
| Cabeza de secuencia | `termina con X` / `finish by …` heredan cabeza de observación |
| Verbo elidido | `otra nota Sol` hereda verbo **y** sustantivo de su cláusula gobernante |
| Ordinal desnudo | `read la segunda` recupera el sustantivo elidido |
| Cuerpo participial | `containing` nombra un cuerpo igual que `con contenido`; la coma serial ya no bautiza una nota `and birch` |
| Nominal de estado | el resolvedor usa la misma tabla que el verificador ya declaraba autoritativa |

`revisa el teclado` **no** se forzó. Esa operación reporta la distribución de
teclado de la ventana enfocada; un enunciado subespecificado es una aclaración,
no un paso de misión. R4 esperaba lo contrario, así que R5 enuncia cada lectura
de forma defendible en vez de doblar el reconocedor hacia un oráculo dudoso.

### 5.4 Dos pérdidas de conservación cerradas en el camino

Ambas habrían ejecutado un **subconjunto silencioso** de la misión pedida:

1. **Introducida por esta reparación y atrapada por una prueba existente.** El
   corte de coordinación separaba un segmento no fundamentable —`brew coffee`—
   y dejaba resolver el resto. Ahora sólo se corta una coordinación **pura** de
   nominales de estado: la conservación manda sobre la cobertura.
2. **Preexistente, descubierta por una prueba nueva.** Con dos marcadores de
   secuencia, `_bounded_status_sequence_intent` devolvía sólo los dominios de
   estado y descartaba sin rastro las cláusulas de nota: una misión de cuatro
   pasos se habría ejecutado como dos. Si hay más cláusulas que dominios, el
   atajo ya no aplica.

Ambas tienen regresión dedicada en `tests/test_effect_intent.py`.

---

## 6. Alternativas rechazadas — siguen rechazadas

| Candidato | Veredicto | Motivo medido |
|---|---|---|
| Qwen3.5-4B Q4_K_M | rechazado | 11 errores semánticos GPU, 12 CPU; más VRAM/RAM/latencia |
| Phi-4-mini-instruct Q4_K_M | rechazado | 3 contratos GPU y 4 CPU fallidos; narró más lento |
| Qwen3-4B-Instruct-2507 | rechazado | ABBA sellado 178/180 contra 180/180; falla GPU `arguments-06` reproducible |
| Wake v17 (físico) | **rechazado y consumido** | 46/48 positivos, 0/96 falsas activaciones |
| HyperSpotter Conformer / Whisper | rechazados | Ninguno preservó cobertura con cero falsas activaciones |
| Prosodia aislada, clasificadores acústicos, guardas CTC | rechazados | Ver R89–R93 del registro |
| Guarda léxica de ruta expandida | rechazada | Quitó 3 falsas activaciones pero perdió 12/48 positivos |

No se repitió ninguna de estas comparaciones: no hubo hipótesis nueva medible.

---

## 7. Reparaciones aplicadas en esta campaña

### 7.1 Contrato de timeout CPU — cerrado

`scripts/measure_mind_budget.py` (SHA-256 `48a1278…`) ya traía el valor
corregido sin commitear, pero su regresión fijaba `19.0`/`120.0` como
literales, permitiendo que la compuerta volviera a separarse del producto en
silencio. La cobertura nueva ata ambos perfiles a
`baxy_mind.llm._request_timeout_from_env()` y exige que la ventana JSONL
`narrate` contenga estrictamente su propio deadline HTTP. Cierra la **clase**
del defecto, no sólo la instancia. 22/22 pruebas focalizadas.

### 7.2 Cierre social multilingüe de Mind — cerrado

`src/baxy_mind/effect_intent.py` (SHA-256 final
`822143f2394a9664a1f0182110196147af1ee2c3bb2661ecaf306ee70774b49d`) sólo
reconocía las colas antiguas; las familias nuevas vivían únicamente en el parser
C#. Se portó la gramática **acotada** —no las superficies literales de R1, que
son memorización— y se añadió una guarda para que el recorte nunca vacíe el
cuerpo.

Efecto medido de extremo a extremo sobre 158 alias × 3 colas:

**126/474 → 474/474 enrutamientos correctos. 348 reparados.**

El contenido literal (`escribe una nota que diga mi tarea termina hoy`) queda
intacto. Las colas de la regresión son **disjuntas** de las que emite el
constructor R2, para que R2 siga siendo un sello ciego real.

### 7.3 Reconocedor por cláusula — cerrado y remedido

Cinco brechas de herencia de cabeza entre cláusulas (§5.3) más dos pérdidas de
conservación (§5.4). Verificación:

- `tests/test_effect_intent.py`: **1.256/1.256**, con regresión dedicada por
  cada forma y por cada pérdida de conservación.
- Corte A replayed en memoria sobre el corpus R2 ya sellado, sin reescribir sus
  artefactos: **158/158** (es 80/80, en 39/39, spanglish 39/39). Cero cobertura
  perdida.
- Corte C remedido sobre R5 disjunto: **6/6 y 25/25**.

### 7.4 Sellos congelados obsoletos — reparados

**El congelamiento del árbol wake ya estaba roto antes de esta sesión.**
Atribución medida:

```
archivos en raíces congeladas : 347   (el preflight v17 registró 344)
expectativa congelada         : 756a5b31…
árbol actual                  : d0cf265c…
árbol SIN mi edición          : 84205440…
¿causa mi edición?            : No
```

Sin la reparación de cierre social el árbol ya hashea distinto. En consecuencia
`current_source_quality_full: "passed"` del ledger commiteado **era falso para
este árbol**: 2 de las 3 primeras fallas estaban esperando.

Se re-sellaron los cuatro bindings de `experiments/stt_quality/` y el
prerregistro de misiones físicas, todos **sin abrir**, conservando el hash
histórico al lado (`WAKE_V17_HISTORICAL_PROGRAM_TREE_SHA256`,
`supersededSha256`) para que el cambio sea auditable.

**No se tocó `experiments/wake_validation/validate_physical_wake_v17_program.py`**:
ese certificador valida la campaña v17 ya completada y cambiar su hash sería
falsificar historia, no re-sellar un futuro.

El prerregistro re-sellado (SHA-256 `4efa85e3bf6edc4b55b9a480d7cb7de0aa590b6afa2de41548282cbe5a5d880e`)
lleva un bloque `resealReason` que deja constancia de que estaba sin medir y sin
recibos cuando se re-selló. Un re-sello sólo es honesto **antes** de medir.

---

## 8. Defectos abiertos — se declaran, no se cierran por decreto

0. **La puerta de dominio no cubre 59 de 158 operaciones**, y por ese hueco pasó
   un **efecto no solicitado**: «Barre las hojas del sendero» ejecutó
   `filesystem.sandbox.append.named` sin decir nada. La familia `filesystem.`
   quedó con suelo —debe nombrar algo del sistema de archivos— y el cero duro
   está cerrado; el resto del hueco sigue abierto **con su cifra**. Ver §13.
0b. **Las peticiones que el catálogo sí sirve no llegan a ninguna parte** cuando
   se redactan sin la palabra literal del alias: 25 de 29 en V1 (86 %) y 21 de
   34 en V2 (62 %). La mejora es real, pero el resto es el hueco central del
   producto — y de las que sí llegan a una operación, **1 de 8 es la correcta**.
0c. **La puerta está invertida sobre la paráfrasis**, no floja ni ausente: en las
   7 ejecuciones equivocadas de V2 rechazaba la operación pedida y permitía la
   que corrió. Un veto comparativo ponderado se construyó, se midió y se
   **rechazó** por romper 3 de 6 peticiones corrientes. Ver §13 y R116–R117.
1. **Decisión cruda 0,9747** detrás de un resultado final 1,0 en el corte A.
2. **Pregunta hipotética sobre otra máquina.** «No tramites mandate alguno en
   la machine, sólo dime: what pasaría si another computer lost su Wi-Fi»
   recibe una aclaración en vez de una respuesta: 2 de 700 en R27, 1 en R25,
   2 en R26. La intención ya es correcta y no ejecuta nada; falla la
   presentación. El sistema no separa una pregunta contrafáctica sobre un
   equipo ajeno de una consulta sobre el propio.
3. **Vetos de dominio por ausencia.** Disparan por que falte la palabra propia,
   no por que haya un dominio en conflicto. Sobre siete poblaciones ciegas la
   **disposición** es 3672 de 9846 (37,3 %) pero el **coste realizado** es 84 de
   4004 (2,1 %), porque 3822 filas resuelven de forma determinista y nunca
   consultan la puerta. Sólo se consulta sobre propuestas del modelo
   —`__main__.py` 1649, 1660, 1714 y 5345—, así que el coste es **latente** en
   el corte B y activo en la población abierta.
4. **Wake word sin promover.** v17 consumido y rechazado (46/48); el corpus
   confusable abierto expuso 10/96 falsas activaciones. No se reabrió.
5. **Corte A no demuestra 99,9 %.** Límite de muestra, §4.1.
6. **Latencia de primera señal**: p50 cumple, p95 en 2,668 s contra una barra
   de 2,0 s. Exige acuse temprano o streaming, no más pulido.
7. **Infinitivos inventados** de raíz irregular en prosa visible («cuecer»,
   «vertir», «tiender»). La guarda por terminación no puede detectarlos; hace
   falta un léxico verbal.
8. **STT humano independiente** sin cerrar; falta la sesión autenticada MDC.
9. **Ciclo limpio de instalación** sin Setup atestado del árbol final.
10. **Misiones físicas dependientes por voz** sin ejecutar: exigen altavoz, sala
    y micrófono físicos. **La mitad de texto pasa 3/3 con 10/10 pasos
    verificados** — ver §12.

**Cerrado desde la versión anterior de esta lista:** la respuesta visible fija
de `llm.py` —que era una constante en pantalla y violaba la invariante 6— se
sustituyó por una **restricción de ancla** (nombrar lo pedido, declarar la
incapacidad, una sola frase corta), sin dictar texto. El **corte B**, que
figuraba como «sin abrir», está cerrado y reconfirmado dos veces: ver §11. Y el
defecto de **uso frente a mención** —una orden *citada* dentro de un marco de
no-acción tratada como orden dada— quedó cerrado y confirmado en ciego en R27,
con `conversation_intent` en cero; no era semántico, era un ancla desplazada por
el propio marco.

---

## 11. Corte B — abierto en rojo tres veces y cerrado en verde

Seis poblaciones ciegas, disjuntas entre sí y de todo corpus anterior:

| | R22 | R23 | R25 | R26 | R27 | **R28** |
|---|---|---|---|---|---|---|
| Exactos /700 | — | — | 694 | — | 698 | **700** |
| Exactos /688 | 149 = 21,7 % | 599 = 87,1 % | 682 | 668 | 686 | **688 = 100 %** |
| Recuperación | 0,427 | 0,929 | 1,000 | 0,989 | 1,000 | **1,000** |
| Intención | — | 0,887 | 0,996 | 0,977 | 1,000 | **1,000** |
| Efectos | — | 0,878 | 1,000 | 0,977 | 1,000 | **1,000** |
| Memoria privada | — | — | 12/12 | — | 12/12 | **12/12** |
| Efectos inseguros | 4 | 6 | 0 | 0 | 0 | **0** |
| `threshold_passed` | no | no | sí | **no** | sí | **sí** |

**R28 da 700 de 700 con cero fallas y cero efectos inseguros.** Con cero fallas
la cota inferior binomial unilateral al 95 % es **0,99573**, que es lo máximo que
700 casos permiten afirmar: la barra del corte B (≥ 95 % con trayectoria hacia
99 %) queda **demostrada, no supuesta**.

**Y hay una lección de método en R28 que importa más que el número.** Las dos
reparaciones que confirma —las que destaparon las misiones físicas— no las había
ejercitado **ningún** sello anterior, porque ningún corpus previo enumera dos
objetos y luego se refiere a ellos por posición. Seis poblaciones de 700 casos
no tocaron esa forma. **Una población grande no cubre lo que su gramática
generadora no genera**, así que el camino físico de punta a punta no es
redundante con el corte B: mide otra cosa.

**R26 salió rojo a propósito y fue lo más útil.** 668 de 688, por encima de la
barra del corte pero por debajo de su propia preinscripción, y **18 de sus 20
fallas eran una sola palabra**: el inglés `petition`, ausente mientras el
español `peticion` llevaba tiempo en la clase. Era la segunda vez —R23 perdió
una celda española entera por `indicacion`— así que dejó de ser un descuido y
pasó a ser un método malo. El léxico dejó de ser una lista: ahora son **grupos
de cognados** de los que se genera la alternación, ningún grupo puede tener un
lado vacío, los dos marcos leen de la misma fuente, y una prueba parsea el `.cs`
y falla en cuanto las dos fronteras dejan de coincidir. R27 atacó esa estructura
con doce marcos nunca vistos —`encomienda`/`assignment`, `mandato`/`mandate`,
`disposición`/`provision`, el `ordenador` peninsular— y dio 686 de 688.

**Qué fallaba en realidad.** R22 no medía paráfrasis: 560 de sus 688 filas
llevaban un sobre que anunciaba una instrucción («esto sí es una orden para el
equipo: …») y el reconocedor lo trataba como texto de la petición. Reparado el
sobre en las dos fronteras, R23 subió a 87,1 % — y entonces **las 89 fallas
cayeron todas en una sola celda de seis**: el español dirigido, cuyo marco decía
«indicación», una palabra que faltaba en la clase léxica. Las otras cinco celdas
dieron 573/573.

**La lección quedó en el instrumento, no sólo en la gramática.** R23 llevaba un
marco por idioma, así que una palabra ausente borró una celda entera y escondió
todo lo demás. R25 rota **cuatro sustantivos de instrucción por idioma** con un
vocativo que no lleva ninguno, de modo que un hueco léxico cuesta como mucho un
cuarto de celda. Y la clase se completó **desde la lengua**: entró `ordenador`,
que faltaba entera y dejaba a cualquier hablante de España sin desenvolver nunca
el marco. Quedaron fuera a propósito `tarea`, `task`, `nota` y `recordatorio`,
que leen igual pero nombran objetos del catálogo: admitirlos habría reducido
«crea una tarea en el equipo: comprar pan» a «comprar pan».

**R24 está sellado, nulo y sin abrir.** Lo sellé antes de terminar su código de
medición; la sonda se negó a abrirlo y el constructor se negó a sobrescribirlo.
Las dos negativas son correctas y no se argumentaron: R25 lleva su población
idéntica —nunca medida, por tanto todavía ciega— bajo una preinscripción atada
al código tal como corrió. Detalle en R106 del registro.

---

## 12. Misiones físicas dependientes — la campaña estaba muerta, no pendiente

Llevaban días «re-selladas y sin ejecutar». No era eso: **no arrancaban**. La
guarda exigía un recibo de wake v17 **promovido**, mientras la preinscripción que
ese corredor ejecuta pide «recibo consumido y terminal» — y su razón de re-sello,
escrita con la campaña sin abrir, dice que *«"v17 pasa" no puede volverse cierto
nunca y congelaría esta campaña de forma permanente»*.

Detrás de esa guarda había tres desfases más, ninguno rellenado a mano:

| Requisito | Estado |
|---|---|
| Informe de presupuesto | medido sobre el árbol actual: **GPU y CPU verdes** |
| Recibo post-wake | certificado: **5/5**, 1398 pruebas focalizadas, 0 efectos |
| Raíz de datos aislada | estaba en `%TEMP%`, que **Core rechaza con razón** |

`PreparePrivateDataRoot` exige que la raíz sea hija directa de
`%LOCALAPPDATA%\BAXY`, cuyo dueño y ACL valida. Ahora se aísla como **hermana**
del almacén personal —nunca el personal—, por misión, y se borra al salir.

**Tres mediciones, cada una partida por causa: 0/3 → 2/3 → 3/3.**

El **0/3** contenía dos misiones correctas rechazadas por un criterio inventado:
`_mission_passed` exigía confirmar toda mutación. Pero `note.create` es
`low_reversible` y `RiskPolicy.Evaluate` mapea `Reversible → Allow` **por
diseño**, así que no hay desafío y `confirmed` es correctamente falso. Y el
bloque `acceptance` de la preinscripción **no menciona confirmación**: pide 3/3,
20/20 pasos, orden exacto, dependencias exactas, cero ambiguos, cero externos,
cero procesos. La cláusula se sustituyó por la que la seguridad sí exige, más
estricta donde importa: **el arnés no puede confirmar nada fuera de la única
mutación permitida**.

El **2/3** dejó un fallo real: la misión inglesa de cuatro operaciones respondía
«I cannot create and read the notes as requested» — negativa **honesta**, pero
incapacidad. Eran **dos defectos independientes**:

- **Un modificador escondía el núcleo.** «a **local** note titulada A y otra
  titulada B» reconstruía la segunda cláusula sin objeto y contaba dos notas como
  una; sin «local» la misma frase resolvía.
- **Una pérdida de conservación.** «read the second note **and finally the first
  note**» son dos lecturas y devolvía una: cuatro operaciones pedidas, tres
  devueltas.

Cerrados los dos, el **3/3** llegó con 10/10 pasos verificados, cero efectos
ambiguos, cero externos y cero procesos sobrevivientes. **La mitad de voz sigue
sin ejecutar** y no se declara nada sobre ella.

---

## 9. Próximos pasos

1. Sellar y abrir R28 para confirmar en ciego las dos reparaciones del
   reconocedor que destaparon las misiones.
2. Cerrar el techo de §8.2: una pregunta hipotética sobre **otra** máquina no es
   una consulta sobre la propia.
3. Reformular los vetos de dominio para que disparen por presencia de un
   dominio en conflicto y no por ausencia del propio.
4. Ejecutar la mitad de **voz** de las misiones dependientes.
4. Reabrir la línea de wake word con un enfoque nuevo: v17 está consumido y
   rechazado, y el corpus confusable abierto sigue mostrando 10/96.
5. Adquirir Common Voice SPS4 y Bangor Miami con sesión autenticada y evaluar el
   STT congelado sin ajustar sobre referencias.
6. Ciclo limpio de instalación con un Setup atestado del árbol final.

---

## 10. Recuperación de contexto

1. `AGENTS.md`
2. `documentacion/00_META_VIGENTE.md`
3. Este documento
4. `documentacion/01_ARQUITECTURA/REGISTRO_DE_MANTENIBILIDAD.md`
5. `artifacts/fixes/integral_review_ledger_20260811.json`

Reglas de reanudación: no reabrir wake v17 ni ningún corpus consumido; no
reutilizar R1/R4 para promover una corrección; no convertir Nemotron en
transcripción final; no instalar nada para probar el MVP.

---

## 13. V1 — el instrumento que faltaba, y lo que enseñó

El sobre-veto de dominio llevaba semanas nombrado y sin cerrar por una razón que
no se había dicho: **no había población capaz de verlo**. La puerta sólo se
consulta donde la vía determinista falla, y las poblaciones generadas del corte B
ya casi nunca fallan ahí —182 de 4004 filas—.

**V1** es esa población. Criterio de inclusión fijado antes de correr nada: cada
control nombra una capacidad que el catálogo **sí** sirve, en palabras
corrientes, evitando el vocabulario literal del alias, y se verifica en
construcción que **no** resuelve de forma determinista. 29 controles sobre 14
operaciones, más 8 peticiones fuera de catálogo y 4 de conversación.

Rompió por dos sitios, y sólo uno era el esperado.

| | |
|---|---|
| Controles de catálogo | 29 |
| Llegan a una operación | 2 |
| Piden el dato que falta | 2 |
| **Ni una cosa ni la otra** | **25 — 86 %** |
| **Efectos no solicitados** | **1 — cero duro violado** |

«Barre las hojas del sendero» ejecutó `filesystem.sandbox.append.named` y calló.
El reconocedor determinista la declinó bien; la puerta devolvió `None` porque
**ninguna regla curada nombra esa operación**.

**Esto reencuadra el defecto.** La puerta curada no es sólo «dispara por
ausencia»: cubre 98 de 158 operaciones. Sobre las que cubre, sobre-veta. Sobre
las otras 60 no dice nada — y ahí estaban `filesystem.copy`,
`filesystem.trash.commit`, `backup.restore`, `game.purchase.commit`. **Demasiado
estricta donde aplica, ausente donde hace falta.**

Y le hace algo a una decisión previa: R103 rechazó la puerta derivada del
catálogo pesando sólo el **coste** (161 sobre-vetos). El otro lado no se pesó: un
sobre-veto cuesta que la persona reformule —recuperable—; un hueco de cobertura
cuesta un **efecto que ya ocurrió** —no recuperable—. No se reabre por decreto;
se deja dicho que **se decidió sobre media balanza**, y que V1 es la población
capaz de pesar la otra mitad.

El cero duro se cerró generalizando la condición que las reglas de `filesystem.`
ya imponían, no añadiendo otra entrada a mano. Las 59 operaciones restantes
siguen sin regla, **a propósito**: taparlas por familias que ninguna medición ha
implicado sería la misma cinta de correr. Se cierra midiendo, con una V2 fresca.

---

## 14. V2 — dos reparaciones confirmadas y el defecto que de verdad manda

| | V1 | **V2** |
|---|---|---|
| Controles de catálogo | 29 | 34 |
| Niegan una capacidad servida | **5** | **0** |
| Describen una máquina no leída | **2** | **0** |
| Efectos no solicitados | **1** | **0** |
| Ni operan ni preguntan | 25 — 86 % | 21 — 62 % |

Las dos guardas de honestidad quedan **confirmadas en ciego** sobre superficies
nuevas, y el suelo de `filesystem.` aguantó.

**Pero el contador escondía lo importante.** «Llegan a una operación» subió de 2
a 8, que parece cuádruple mejora. Por operación **no lo es**: sólo **una de las
ocho** es claramente la pedida. Los periféricos ejecutaron `system.status`, las
copias `system.identity`, el portapapeles `task.list`, los procesos
`window.application.status`. Dos más cayeron en `reminder.list` por una
ambigüedad **del catálogo**, que llama «recordatorios vencidos» a las
notificaciones.

**Cuando por fin actúa, casi siempre actúa mal.** Y eso tiene una consecuencia de
producto: subir el número de ejecuciones sin arreglarlo lo empeoraría. Un
`system.status` cuando se preguntó por los periféricos es peor que no hacer nada,
porque **parece** una respuesta.

Ese es el frente que manda, y no se cierra con guardas de texto visible: exige
comparar la propuesta del modelo contra el dominio que la petición nombra, antes
de ejecutar. Es la reforma del veto de §8.3, ahora con la mitad de la balanza que
faltaba **medida**: el coste de no vetar son 5 de 8 ejecuciones equivocadas.
