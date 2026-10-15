# Estabilidad de BAXY (misión de estabilización, 2026-10-10 → 14)

Resumen final de `ESTABILIDAD.json`. Los logs, jueces e informes citados están en `%LOCALAPPDATA%\BAXY\cu-v3\`; los
informes de arreglos, en `cu-v3\estab\`. Todas las corridas del banco son en modo bypass sobre blancos seguros. Los casos
de voz de Discord (s11, s13, c7) y s14 corren en Normal para comprobar la pregunta. Lo que aún espera a la última
integración ya está medido: banco reducido zu/zw y tandas z7–z10.

## Banco B (72 casos ×3)

| Etapa | Código | Logrados 3/3 | Límites honestos 3/3 | Varían | Falsos éxitos | p50 total / misión |
|---|---|---|---|---|---|---|
| Fase 1, línea base | ronda 30, `ce6beebaf` | 62 | 1 (s06) | 8, más n5 0/3 con causa falsa | 2 (u1, y8) | 6,26 / 6,72 s (e1 / e2) |
| Fase 2, estabilizar | `4d9c38ac1` (h1–h3) | 64 | 2 (n5, s06) | 6, todos con causa y arreglo | 1 (h1 c6, cerrado por F3) | 5,15 / 4,91 / 4,46 s; misión 4,56 / 4,34 / 4,04 s |
| Fase 3, refactor | `40534dee6` (rf1, ×1) | 66 firmas iguales a las juzgadas, más c6 n7 u9 y1 logrados | — | g1 (sin L3), v1 (a remedir) | 0 | 4,91 s; misión 4,30 s |
| Definitivo | `0f2468bb1` (def1–def3) | 67 | 3 (g1, n5, s06) | 2: c2 y x8, 2/3 (foco tras traer la Calculadora → K) | 0 | 4,57 / 4,57 / 4,81 s; misión 3,96 / 3,87 / 3,92 s |
| fx, con K | `b61edf336` | 69 | 3 | 0 | 0 | 4,63 / 4,79 / 4,49 s; misión 3,97 / 4,14 / 3,90 s |
| fv | `3961b3737` (`banco_fv1..3.txt`) | 69 | 3 | 0 | 0 | 3,46 / 3,43 / 3,53 s; misión 2,95 / 2,91 / 2,87 s |
| **Final, zf** | **main `8d90cc2d0`** (`banco_zf1..3.txt`) | **69** | **3 (g1, n5, s06)** | **0** | **0** | **4,05 / 4,17 / 4,03 s; misión 3,63 / 3,63 / 3,62 s** |

- **zf.** Jueces `bancoB_zf1..3_juez.json`. Los 7 casos con firma nueva (s11 c7 n4 s13 v10 v11 y9) se juzgaron:
  21/21 logrados, con finales honestos. Los otros 65 tienen en las 3 corridas la misma firma que en fv (juzgado 72/72).
- **zf frente a fv: +0,33 s de mediana por caso.** Se debe al estado de partida: en fv la app ya estaba abierta (s03,
  Configuración, 0,4 s) y en zf se abre en frío (2,6 s). La decisión del modelo es igual o más rápida (s03: 0,10 s
  frente a 0,37 s).

### Bancos reducidos tras los arreglos TZ

Orden del dueño: tras un arreglo se repiten ×3 sólo los casos que el arreglo puede mover; el resto hereda zf.

| Bancos | Código | Casos | Resultado ×3 | Falsos éxitos | p50 total / misión (sumbench, sólo esos casos) |
|---|---|---|---|---|---|
| zs1–zs3 (`banco_zs1..3.txt`) | `a99fa5bea` | 22 | 22/22 iguales o logrados. u9 y x7 cambian de final a «estoy en «search»»: logrados por captura | 0 | 3,66 / 3,53 / 3,50 s; misión 3,10 / 2,96 / 3,04 s |
| zt1–zt3 (`banco_zt1..3.txt`) | `e9266d59b` | 41 (37 del banco + 4 imprescindibles) | 38 con firma igual ×3: 34 logrados, g1 y n5 límite, imp-dc-leer e imp-wa-leer. imp-wa-enviar 3/3 (4 pasos en zt1, 3 en zt2/zt3). c6 2/3 e imp-wa-abrir 2/3 (abajo) | 0 | 4,34 / 4,08 / 4,52 s; misión 3,88 / 3,72 / 4,02 s |
| zu1–zu3 (`banco_zu1..3.txt`) | `e61a9ed41` (+TZ-DC3, TZ-HOLD) | 17 | 13 con firma igual o logrados ×3 (c6 3/3, u9 «search» logrado). WhatsApp: abrir 2/3, enviar 1/3, leer 0/3: el chat ya no estaba arriba y la búsqueda pulsaba «Nuevo chat» y dejaba el filtro «No leídos» → TZ-WA2 | 0 | — |
| **zw1–zw3 (`banco_zw1..3.txt`), final** | **`da9a8bb78`** (+TZ-WA2, TZ-OSC2, saneo) | 15 | **15/15 ×3**: 11 con firma juzgada (Calculadora, Configuración, Spotify, c6) + imp-wa-abrir, imp-wa-enviar, imp-wa-leer, imp-dc-leer 3/3 | **0** | — |

- **c6, zt1.** Falló por entorno: Discord tenía el frente y recibió las 28 teclas, pero no las puso en su compositor.
  En redpc, el mismo paso dio 42/42. El final dice «antes de parar escribí «prueba BAXY C6»», que la mirada no mostró;
  se corrige en TZ-DC3 (en curso).
- **imp-wa-abrir, zt3.** El chat se dibujó tarde. La caja propia del lugar ya estaba en la mirada anterior al último
  clic, así que la comprobación no daba la llegada, y el final negó lo logrado. Arreglado en TZ-DC3 (`e2dc2114d`).

## Tandas de uso real (t1–t4, 123 turnos)

Fase 1 y fin1–fin6 en redpc; z1–z6 en el notebook. Totales de z: suma de `bien_estricto` y `bien_flexible` de
`tandas_z<N>_notebook\juicio_t1..t4.json`.

| Corridas | Código | Estricto | Flexible | Turnos que cambian de ruta |
|---|---|---|---|---|
| Fase 1, estab1/estab2 | `ce6beebaf` | 70 / 74 | 94 / 89 | 21 (entorno 10, estado 4, redactor 3, carrera 3, empate 1) |
| fin1 / fin2 | `0650deac3` | 80 / 76 (65 / 62 %) | 100 / 97 (81 / 79 %) | 3: t1-c07, t2-c01 t1 y t2 (música sin confirmar; arreglo SP) |
| fin3 / fin4 | `adf871f05` | sin juicio completo (88 veredictos sin heredar) | | 3 |
| fin5 / fin6 | `db89105ef` (sin K) | sin juzgar | | |
| **z1 / z2** | `8d90cc2d0` | **94 / 87** (76,4 / 70,7 %) | **108 / 104** (87,8 / 84,6 %) | 6 |
| **z3 / z4** | `a99fa5bea` | **90 / 83** (73,2 / 67,5 %) | **106 / 105** (86,2 / 85,4 %) | 2 |
| **z5 / z6** | `e9266d59b` | **92 / 97** (74,8 / 78,9 %) | **108 / 109** (87,8 / 88,6 %) | **0** |
| **z7 / z8** | `e61a9ed41` | **96 / 92** | **110 / 109** | **0** |
| **z9 / z10 (final)** | **`da9a8bb78`** | **93 / 97** (75,6 / 78,9 %) | **107 / 110** (87,0 / 89,4 %) | **0** |

Finales falsos sobre efectos en el PC (juez independiente): z7 1 dudoso («elegí el modo Oscuro» con el modo ya puesto → TZ-OSC2), z8 0, **z9 0, z10 0**. Datos de memoria del modelo (límite declarado): 4 / 4 / 4 / 3.

Las tandas de cierre son z1–z10: sustituyen a las fin7/fin8 que se anunciaban aquí.

**Finales falsos por corrida.** Tipo a: efecto en el PC. Tipo b: dato de conocimiento de memoria, un límite declarado en
`LIMITES_DE_BAXY.md` § datos de memoria. Fuentes: `finales_falsos` y `final_falso` de los juicios; z3–z6 traen además
`tipo_final_falso`.

| Corrida | a | b | Turnos |
|---|---|---|---|
| z1 | 0 | 4 | b: t2-c01 t4 (cuenta de uno sin fuente, vía búsqueda → TZ-VETO), t2-c09 t1, t3-c17 t1 y t2 |
| z2 | 0 | 3 | b: t2-c09 t1, t3-c17 t1 y t2 |
| z3 | 1 | 4 | a: t4-c04 t3 (niega el modo oscuro y pulsa colores → TZ-OSC); b: t2-c09 t1, t3-c17 t1–t3 |
| z4 | 1 | 5 | a: t4-c04 t3 (→ TZ-OSC); b: t1-c03 t3, t2-c09 t1, t3-c17 t1–t3 |
| z5 | 0 | 4 | b: t2-c09 t1, t3-c17 t1–t3 |
| z6 | 1 | 3 | a: t4-c01 t4 (niega que Spotify suena → TZ-HOLD); b: t2-c09 t1, t3-c17 t3, t4-c02 t3 |

## Arreglos después del banco zf

Ramas fusionadas en `fable/estab-fase3`; un informe por rama en `cu-v3\estab\`.

| Arreglo | Causa medida | Qué cambia | Reglas |
|---|---|---|---|
| TZ-DC (`TZ_DC.md`) | z1 t4-c03 t2: `message_body` no leía texto entre «», así que el cuerpo lo ponía el modelo, que se abstuvo en z1 | El texto entre «» se lee sin modelo; desaparece esa llamada | 0 |
| TZ-CAL (`TZ_CAL.md`) | t3-c18 t3: la Calculadora ya estaba en Programador. En z1 el chequeo cerró en `page:` y no quedó retenido (el motor pulsó otro modo); en z2 el redactor inventó | Una corrección sobre un lugar ya alcanzado se dice desde datos («Ya está en «…»»), sin redactor | 0 |
| TZ-VETO (`TZ_VETO.md`) | z1 t2-c01 t4: la pista del veto quitó «al menos» y «al menos un disco» pasó a «un disco»; nadie juzgaba cuentas de uno | `answer_unstated` juzga las cuentas de uno sin fuente y se comprueba antes que el veto de palabras | +1 |
| TZ-SP (`TZ_SP.md`) | z2: Spotify (Chromium) no dibuja la búsqueda mientras una ventana encima lo tapa entero (redpc: no llega en 22–25 s, 3/3). Causa de entorno | Dos campos de diagnóstico que dicen que estaba tapado; código muerto quitado | 0 |
| WA-LEER (`WA_LEER.md`) | La mente recibía sólo las 20 primeras líneas del chat (6/6) y el OCR descartaba líneas repetidas (45/66), así que la última burbuja de la otra persona se perdía | El chat llega entero y las burbujas se separan por sitio: 14/14 sobre vistas congeladas (antes 7/14) | +1 (+2 −1) |
| TZ-OSC (`TZ_OSC.md`) | z3/z4 t4-c04 t3: la misión eligió «Oscuro», la comprobación no lo tomó como llegada y pulsó tres colores de énfasis; el final negó lo hecho | Un valor elegido en una lista prueba la llegada; no se pulsan resultados que sólo contienen el nombre | +2 |
| TZ-DC2 (`TZ_DC2.md`) | z3 t1-c09 t1: la sonda de mensajería arrancaba su propio worker de UIA con la primera búsqueda del Core y buscaba a ciegas (7,46 s, identidad no verificada) | Un único worker de UIA por Core, compartido; ≈ −1 s en la primera búsqueda | 0 |
| TZ-DC3 (`TZ_DC3.md`) | zt3 imp-wa-abrir: llegada tardía al chat que `FocusedIntoThePlace` no tomaba. zt1 c6: entorno | La caja propia nueva desde el primer clic del subobjetivo prueba la llegada (`e2dc2114d`). Un texto que la mirada siguiente no muestra no se dice escrito (`e9d597e2e`) | 0 |
| TZ-HOLD (`TZ_HOLD.md`) | z6 t4-c01 t4: el veto `effect_claim` mató «Ya está reproduciendo…» y su pista pidió decir que no se hizo | Todo efecto retenido se dice con su frase de datos, sin redactor | −2 |
| TZ-OSC2 (`TZ_OSC2.md`) | z5–z8 t4-c04 t3: «elegí el modo Oscuro» con el modo ya puesto y sin clic sobre él | Escribir en la búsqueda no elige nada; un valor ya elegido se dice «ya estaba elegido» | +1 |
| TZ-WA2 (`TZ_WA2.md`) | zu: el chat ya no estaba arriba; la búsqueda pulsaba la fila con vista previa, el eco del buscador o «Nuevo chat» y dejaba «No leídos» | El chat se abre por su entrada, por «Todos» una vez o por el buscador con el resultado exacto; nunca «Nuevo chat» (datos `chatSearch`) | +4 −1 |

## Imprescindibles en vivo

Detalle en `documentacion/LIMITES_DE_BAXY.md`.

- **Steam.** Lanzar Cuphead e instalar y desinstalar Super Meat Boy: 3/3 (imp1, imp2, stm3 del 14-10). En Normal, al
  instalar pregunta y con «no» no instala: 3/3. Biblioteca, tienda y comunidad: 3/3 en el banco. Buscar en la
  biblioteca es un límite (g1).
- **Discord.**
  - Enviar (c6): 3/3 en el banco hasta zf y 3/3 en msg1–3; 2/3 en zt, por entorno.
  - Leer lo último (imp-dc-leer): 3/3 en msg1–3 y 3/3 en zt.
  - Entrar a voz con «sí» y salir: 5/5 con una sola pregunta tras VZ. Con «no» no entra: s11, s13 y c7, 3/3.
  - Salir sin llamada activa: lo dice y no pulsa nada, 2/2.
- **WhatsApp**, con el contacto individual «Abuela».
  - Abrir: 3/3 (wac1–3) y 2/3 en zt; el fallo de zt3 lo arregla TZ-DC3.
  - Enviar: 6/6, y 3/3 en zt. En Normal pregunta y con «sí» envía: 3/3.
  - Leer lo último: la respuesta es correcta, porque el chat «Abuela» no tiene mensajes de ella («En lo que muestra el
    chat no hay mensajes de Abuela.», 3/3 en zt). WA-LEER deja la lectura lista. **Falta la prueba en vivo con un
    mensaje de ella.**

**Identidad** comprobada en vivo en los dos PC: notebook el 11-10 y el 12-10 a las 01:47; redpc el 12-10 entre las
09:58 y las 10:41. Los defectos de redacción que salieron se corrigieron en M2 e I2. Detalle en `LIMITES_DE_BAXY.md`
§ Identidad.

## Full verde

| Código | pytest |
|---|---|
| main `8d90cc2d0` | 26 405 pasan / 3 omitidas |
| `255136708` | 26 459 / 3 |
| `602fde7a1` | 26 464 / 3 |

Skip y xfail de `58f8b37c1` a `8d90cc2d0`: marcadores de pytest 53 → 53, xfail 0 → 0, C# 113 → 110. En ejecución, pytest
omite 3 al inicio y 3 al final.

## Latencia

Cada turno se mide como total = tiempo de modelo + sobrecarga de BAXY.

- **Fase 1** (informe de la fase en `PROGRESO_V3.md`):
  - Mediana por caso del tiempo de modelo: ≈ 1,0 s.
  - Sobrecarga: 5,34 s (r30) → 5,60 s (e1) → 5,65 s (e2).
- **Banco definitivo.** Total p50 4,57–4,81 s; misión p50 3,87–3,96 s.
- **Sobrecarga estimada del banco definitivo: ≈ 3,6–3,8 s.** Es el total menos el ≈ 1,0 s de modelo de la fase 1,
  porque en el definitivo el tiempo de modelo no se volvió a medir por separado. Es una estimación, no una medida.
  Contra la fase 1 son ≈ 1,7–2 s menos de sobrecarga.
- **Banco final.** fv: p50 3,43–3,53 s (misión 2,87–2,95 s). zf: p50 4,03–4,17 s (misión 3,62–3,63 s); los +0,33 s
  frente a fv son de estado de partida (apps abiertas en frío), no del modelo.
- **p90.** Bajó de 13,5 s a ≈ 9,5–11,6 s entre la fase 1 y la fase 2/refactor; en zf, 9,67–11,51 s.
- **Tandas.** t1-c01 t1 (YouTube) suena y se verifica en las 6 corridas z, pero tarda 20–29 s: estricto «mal» por lento.

## Saldo de reglas

Fuente: `cu-v3/estab/saldo_reglas.md`. Cubre desde la ronda 30 (`51cf45154`) hasta `fable/estab-fase3` `0650deac3`.

**Neto ≈ −19:** ≈ 84 añadidas y ≈ 103 quitadas. Por clases:

| Clase | Reglas |
|---|---|
| (a) Retiradas por limpieza | ≈ −63 |
| (b) Añadidas por estabilidad y honestidad | ≈ +65 |
| (c) Añadidas por imprescindibles pedidos por el dueño (IMP steam 3, IMP mensajería 4, IMP2 6, IMP3 3, IMP4 3) | +19 |
| Quitadas al sustituir dentro de ramas de arreglo | −40 |

Cuadre: +65 + 19 − 63 − 40 = −19.

Desglose de (a):

| Retirada | Reglas |
|---|---|
| Procedimientos aprendidos, 1 mecanismo | ≈ −25 |
| R motor | ≈ −14 |
| L1, arrastre y guardado por contenido | ≈ −11 |
| Vetos del redactor fundidos o retirados en F | −7 |
| R bajo riesgo | ≈ −6 |

En (b), la identidad pedida en vivo pesa +11 (M, M2, U). Las ramas de (c) quitaron 7, así que su neto es +12.

Hay revisiones adversariales que cambiaron reglas sin actualizar su saldo (V, C, B2, M, U). Pueden mover el total unas
pocas reglas, no el signo.

Ramas fusionadas después de `0650deac3`, según sus informes: W2/W3 revertidas −2, SP +1, H1 +2, H2 +1, I2 −2, U1 +2,
V1 0, K +2 y YT 0. Suman **+4**, así que el saldo en la cabeza de `fable/estab-fase3` quedó en **≈ −15**.

**Arreglos TZ**, según sus informes: TZ-DC 0, TZ-CAL 0 (+1 −1), TZ-VETO +1, TZ-SP 0, WA-LEER +1 (+2 −1), TZ-OSC +2,
TZ-DC2 0 y TZ-DC3 0. Suman **+4**, así que el saldo queda en **≈ −11**: sigue negativo. No incluye TZ-HOLD (en curso)
ni las ramas fusionadas entre YT y la ronda TZ (C7Y5, E5…), cuyo saldo no se sumó aquí.

## Qué quedó sin 3/3, y por qué

| Qué | Resultado | Causa medida | Estado |
|---|---|---|---|
| c2, x8 (Calculadora con tecleo) | 2/3 en el definitivo; 3/3 en fx, fv y zf | La primera tecla se perdía mientras el marco UWP pasaba el foco a su contenido | Cerrado por K |
| c6 (Discord enviar) | 2/3 en zt | zt1: Discord recibió las teclas con el frente y no las escribió (entorno; 42/42 en redpc) | Entorno; el final ya no dice «escribí» lo no visto (TZ-DC3). c6 3/3 en zu y zw |
| imp-wa-abrir / enviar / leer | 2/3 en zt; 2/3, 1/3, 0/3 en zu | zt3: llegada tardía (TZ-DC3); zu: chat fuera de la parte alta de la lista (TZ-WA2) | **3/3 los tres en zw** |
| WhatsApp leer lo último | Correcto, 3/3 | El chat «Abuela» no tiene mensajes de ella | Falta la prueba en vivo con un mensaje de ella |
| Tandas: Spotify sonando negado (z6 t4-c01 t4) | Final falso a, 1 de 6 corridas | Corrección ya cumplida que se niega | Cerrado por TZ-HOLD: z7–z10 «Ya está sonando «…» en Spotify.» 4/4 |
| Tandas: «elegí el modo Oscuro» con el modo ya puesto (t4-c04 t3) | Dudoso en z7 | Escribir en la búsqueda contaba como elegir | Cerrado por TZ-OSC2: z9 y z10 «Abrí «Configuración» y «Oscuro» ya estaba elegido.» |
| Tandas: datos de memoria (t2-c09 t1, t3-c17, t1-c03 t3, t4-c02 t3) | Final falso b en las 6 corridas (3–5 por corrida) | El modelo responde de memoria sin fuente | Límite declarado en `LIMITES_DE_BAXY.md` § datos de memoria |
| Tandas: YouTube en frío (t1-c01 t1) | Suena y se verifica 6/6; 20–29 s | Arranque en frío del reproductor | Lento, no falso |
| Tandas: pegar en un Bloc de notas nuevo (t4-c14 t1) | Falla en las 6 corridas, honesto | No crea el documento nuevo | Fuera del banco, para la fase de escalado |
| t-scroll-4 | No dice su límite | Tras Ctrl+L la misión adopta una ventana emergente propia (`KeepsBorn`) | Sin cambio desde el 12-10 (W2 revertida) |

## Cómo se llegó aquí (piezas)

**Fase 2** (`fable/estab-fase2`). Cada pieza pasó una revisión adversarial independiente:
- procedimientos apagados;
- decisor determinista (|Δlogprob| 0,283 → 0);
- la voz siempre confirma;
- Spotify por su botón propio;
- lo no verificado lo dice el suelo;
- portapapeles que reintenta;
- cerrar sin pregunta inventada.

**Fase 3** (`fable/estab-fase3`, integración final):
- **Refactor:**
  - `llm.py` pasó de 32 627 a 1 252 líneas, repartidas en 49 módulos;
  - `computer_use.py` quedó en 33 módulos `cu_*`;
  - `ComputerUseMission` quedó en 24 parciales;
  - `__main__` quedó en 21 módulos.
- **Arreglos:** D2, Y5, N1, F3, L3, L4, M2, IMP (Steam, mensajería, 2–4), E, H1, H2, I2, SP, U1, V1, K, YT, E5, C7Y5,
  VZ, WA-LEER y la ronda TZ (DC, CAL, VETO, SP, OSC, DC2, DC3, HOLD).
- **Saneo** de datos privados ×2, más el de la vista congelada del modo oscuro (`d6736ee37`).
