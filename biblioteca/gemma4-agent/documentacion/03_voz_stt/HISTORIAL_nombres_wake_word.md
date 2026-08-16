# Historial de nombres — wake-word / marca del asistente

> **Resultado final (2026-06): el nombre y la wake word son "Baxy".** El producto
> se llamó "Gemma 4 Agent" (original), luego brevemente "Carter", y finalmente
> **Baxy**. Este documento conserva el registro de los candidatos evaluados y
> **por qué se descartaron** (incluido "Carter", rechazado por recall 0.28 / /r/
> rótica). NO renombrar esos registros: son la evidencia histórica del proceso de
> elección. El **modelo** sigue siendo Gemma 4 (de Google), no confundir con la
> wake word.

Registro de nombres evaluados para renombrar el asistente (antes "Gemma 4 Agent").
Evita re-investigar candidatos ya descartados. Cada nombre se evalúa en **dos ejes**:

- **Disponibilidad comercial** (verificada con búsqueda web): 🔴 USADO · 🟡 VERIFICAR · 🟢 LIBRE.
- **Fonética como wake-word** (criterio MEDIDO en este proyecto): ✅ OK (sin /r/ rótica,
  termina en vocal → generaliza como "gemma" recall 0.74) · ⚠️ RIESGO (tiene /r/ →
  colapsa en idiomas no-ingleses como "carter" recall 0.28).

> Fuente del criterio fonético: `documentacion/03_voz_stt/PLAN_MAESTRO_wake_carter.md`.
> Última actualización: 2026-06-03.

---

## 🔴 USADOS — descartados (verificado con búsqueda web)

| Nombre | Por qué se descartó | Fonética |
|--------|---------------------|----------|
| **Gemma 4 Agent** | Nombre anterior; el modelo es Gemma 4 (Google) → confusión modelo/producto. | — |
| **Carter** | ENTRENADO y medido: recall held-out 0.28 (falla gate). La /r/ rótica colapsa en idiomas no-ingleses (en_US 1.00, it/fr/es 0.00). | ⚠️ /r/ |
| **Luna** | 9+ productos AI/voz: Universal Audio (DAW con asistente), Luna healthcare, livepro, Luna AI (GitHub OSS), etc. Demasiado común en AI. | ✅ |
| **Rey** | Varios AI: Rey de Reynolds&Reynolds (automotriz, NADA 2026), Re:plain, Realmo, RAY.ai. + monosílabo + /r/. | ⚠️ /r/ |
| **Vexa** | El PEOR: vexa.ai es un asistente de voz AI OSS privacy-first = IDÉNTICO a este proyecto. + vexaai.com, vexai.app, vexaiagent.com, VEXA EA Software. | ✅ |
| **Nova** | Muy usado en AI/asistentes. | ✅ |
| **Neo** | Muy usado. | ✅ |
| **Echo** | Es Amazon Echo. | ✅ |
| **Vox** | Marca registrada (Vox Media). | ✅ |
| **Sol / Leo** | Demasiado comunes. | ✅ |

---

## 🟢 LIBRES — disponibles para usar (verificado)

**NINGUNO de los 37 candidatos auditados resultó 100% libre.** El espacio de nombres
de asistentes/AI está saturado — hasta inventos raros (Zeva, Vixa, Wexa, Maxa…) ya son
productos AI. Lo más cercano a "libre" son los 3 amarillos de abajo.

---

## 🟡 VERIFICAR — sin colisión AI directa, pero riesgo en otro sector (lo mejor disponible)

| Nombre | Dónde aparece (riesgo) | Fonética |
|--------|------------------------|----------|
| **Loxa** | Sin AI/voz directo. Pero "Loxo" = plataforma AI de recruiting grande (confundible); + usos dispersos (insurtech loxacover, cosmética Loxa Beauty, herramientas). | ✅ |
| **Zeto** | Sin AI/SaaS directo. Pero "Zeto Inc." = medtech FDA (headset EEG con notif. "AI-enabled"), financiada. | ✅ |
| **Tavi** | Sin asistente de voz. Pero "TAVI" = acrónimo médico (válvula aórtica) MUY usado en AI médica (TAVIPILOT FDA, asistentes de voz post-TAVI). | ✅ |

---

## 🔴 USADOS — auditados y descartados (lote `wmgubieu2`, 2026-06-03)

Los 34 con colisión directa en AI/software/marca. Resumen (evidencia completa en el output del workflow):

| Nombre | Colisión | Nombre | Colisión |
|--------|----------|--------|----------|
| **Zeva** | zeva.ai chatbot/voz (PEOR caso, voz directa) | **Sela** | trysela.com AI voice agent (mortgage) |
| **Nila** | "Nila - AI Voice Assistant" | **Nuva** | Nuronics voz/chatbots multilingüe |
| **Niva** | Niva AI asistente de conocimiento | **Vixa** | vixa.ai agente de ventas tipo voz |
| **Vako** | vako.ai companion de salud (chatbot) | **Talo** | Talo AI voz (truncado) |
| **Quila** | quila.ai asistente AI de PM | **Luma** | Luma Labs (USD 967M) + apps de voz |
| **Wexa** | wexa.ai "AI coworkers" SaaS | **Maxa** | maxa.ai SaaS analytics (Series A $21M) |
| **Naxa** | naxa.io software geoespacial | **Zexa** | Zexa Technologies (software AI) |
| **Tixa** | Tixa AI employee + TIXAE voice agents | **Zyla** | Zyla Labs API Hub + Zyla healthcare AI |
| **Zylo** | zylo.com SaaS Management enterprise | **Zumi** | Robolink kit robótico AI |
| **Zalo** | super-app mensajería 77.6M usuarios (VNG) | **Zuna** | zuna.ai travel + Zuna SaaS |
| **Ziva** | Ziva Ai + Ziva Dynamics (Unity) | **Zino** | getzino.com GenAI low-code |
| **Nexo** | nexos.ai + Nexo crypto "AI Assistant" | **Nivo** | Nivo AI ops + nivo.rocks dataviz |
| **Quibo** | Quibo Tech software AI/ML | **Vimo** | (usado, ver output) |
| **Davo, Memo, Iko, Aiko, Umi, Beto, Ivo** | todos con colisión (ver output del workflow) | | |

---

## 🟢🟢 AUDITORÍA MASIVA (1040 nombres, lote `wzjma01ii`, 2026-06-03)

Tras no hallar libres en los nombres "obvios", se generaron **1040 nombres inventados de
3 sílabas sin /r/** y se auditaron TODOS con búsqueda web. Resultado:

- **712 LIBRES** · 228 VERIFICAR · 100 USADOS.
- **Lección clave:** los nombres inventados raros SÍ están libres (el espacio AI solo estaba
  saturado para nombres cortos/lindos/obvios como Luna/Vexa). Hay pool de sobra.
- **Caveat de calidad:** el generador se sesgó a iniciales "Va-"/"Na-" y muchos suenan
  parecidos entre sí. Son libres, pero hay que elegir uno que además suene bien como marca.

### ⭐ TOP curados — libres + pronunciables + suenan a marca (elegir de acá)
Cortos (5 letras, terminación vocal), los más "lindos" del pool de 712:

**Vaveo · Vatao · Vamao · Valao · Vabeo · Vakei · Vazai · Vamai · Vatoi · Vamoi**
**Vaxoa · Vayea · Vaquea · Vaquia · Vaveo · Nabeo · Natao · Nazao**

### Lista completa de los 137 curados (libres + filtro de pronunciabilidad)
```
Vaxoa, Vayea, Vaquea, Vaquia, Vaveo, Vatao, Vamao, Valao, Vabeo, Vaxao, Vayeo, Vaquao,
Vaqueo, Vaquio, Vavei, Vazai, Vamai, Vavoi, Vazoi, Vatoi, Vamoi, Vabei, Vakei, Vaxoi,
Vayei, Vaquai, Vaquei, Vaveia, Vataia, Vamaia, Valaia, Valoia, Vavoia, Vazoia, Vatoia,
Vasoia, Vamoia, Vabeia, Vakeia, Vaxeia, ... [+97 más, todos LIBRES]
Naquea, Nazao, Natao, Nazio, Nabeo, Naxao, Naquao, Naqueo, Naquio, Nazoi, Naquei, ...
```
(Las 712 libres completas + sus evidencias están en el output del workflow `wzjma01ii`.)

### 🟡 VERIFICAR de la masiva (muestra, sin AI directo pero con vecino/uso disperso)
Vavea, Vataa, Valea, Vania, Vazia, Vavoa, Vabea, Vadea, Vapea, Vakea, Valei, Vasoi…
(228 en total en el output.)

---

## 🧭 CONCLUSIÓN de la auditoría

**De 37 candidatos inventados: 0 libres, 3 amarillos (Loxa/Zeto/Tavi), 34 usados.** El mercado
de nombres AI está saturado. Caminos posibles desde acá:

1. **Tomar un amarillo** (Loxa / Zeto / Tavi) — sin colisión AI directa, asumiendo el riesgo del
   otro sector. Loxa y Zeto son los más limpios (fonética ✅, sin /r/).
2. **Inventar nombres MÁS raros** (3+ sílabas, combinaciones improbables) y auditar otra tanda.
3. **Nombre compuesto/propio** poco googleable (ej. una palabra inventada de 3 sílabas sin A";
   ej. "Tavela", "Quimba", "Noxela"…) — más chance de estar libre.
4. **Aceptar coexistencia**: para un proyecto OSS personal, un nombre con colisión menor en otro
   sector puede ser aceptable si no hay marca registrada AI fuerte (decisión del usuario).

---

## Notas / lecciones

- **Los nombres "buenos y obvios" en AI ya están todos tomados** (Luna, Rey, Vexa, Nova...).
  La fórmula "x + AI" es justo la que todos eligen ahora. Conviene ir a algo más raro/inventado.
- **Evitar /r/ rótica**: es la causa medida del fallo de Carter (la /r/ varía mucho entre
  idiomas y el TTS de training es inglés). Un nombre sin /r/ que termina en vocal generaliza.
- **Verificar SIEMPRE con búsqueda web** antes de comprometerse: Luna y Rey "parecían" libres
  y estaban muy ocupados.
- Ningún listado garantiza 100% sin búsqueda de marca registrada (USPTO/INPI) — esto cubre
  productos AI/software y marcas tech prominentes, no el registro legal formal.
