# Alcance: qué se mide ahora y qué se difiere al producto final

> Actualización de planificación, 2026-09-04: la separación histórica siguiente
> no autoriza declarar el producto terminado. Voz/accesibilidad se comprueban en
> C08/C09; [fase 12](sprints/12_PRODUCTO_FINAL.md) es el owner explícito de los
> diferidos A.1–A.3 (hardware, ciclo de instalación y firma). La equivalencia
> provisional de texto por voz de B.1 no aplica a C08 ni al cierre final.
> Véase [revisión](sprints/REVISION_SPRINTS_2026-09-04.md).

Estado: **vigente desde 2026-08-15**. Este documento manda sobre cualquier
criterio de cierre anterior. Si `goal.md`, `00_META_VIGENTE.md` o un prompt de
agente exige algo que aquí figura como diferido, **está desactualizado y no
bloquea**.

## Por qué existe

La meta mezclaba dos cosas distintas: lo que se puede demostrar hoy, en esta
máquina y con este equipo, y lo que sólo tiene sentido validar cuando exista un
producto empaquetado y un entorno de destino. Al mezclarlas, la definición de
terminado se volvió inalcanzable por construcción, y una definición que no puede
cumplirse nunca no disciplina nada: sólo garantiza que todo informe termine en
«no cumplido».

La separación no rebaja ninguna barra. Lo diferido sigue siendo obligatorio
**para el producto final**; lo que cambia es que deja de bloquear el desarrollo
y deja de contarse como defecto abierto.

## Hardware real de la máquina de desarrollo

Medido el 2026-08-15 en la máquina donde se ejecuta todo:

| | Medido |
|---|---|
| GPU | NVIDIA GeForce RTX 4060 Ti, **16.380 MiB** según `nvidia-smi` |
| RAM | **31,77 GB** |

**Aviso que ha costado confusión:** WMI (`Win32_VideoController.AdapterRAM`)
reporta **4 GB** para esta tarjeta por un desbordamiento de 32 bits conocido.
Coincide exactamente con la cifra del perfil certificado, así que es fácil creer
que la máquina *es* el perfil objetivo. No lo es. La fuente válida es
`nvidia-smi`.

---

## A. Diferido al producto final — no se mide ahora, no bloquea

### A.1 Presupuesto de hardware

- **Perfil certificado GPU de 4 GB de VRAM.**
- **Perfil CPU ≤ 8 GB de RAM.**

**Por qué se difiere.** La máquina de desarrollo tiene 16 GB de VRAM y 32 GB de
RAM. Cualquier medición aquí sobre-dimensiona el presupuesto y no demuestra nada
sobre un equipo modesto. Validarlo exige el hardware objetivo o un límite
impuesto y verificado, y eso pertenece a la campaña de producto.

**Qué sigue siendo obligatorio para el producto final.** Todo lo residente entra
en 4 GB de VRAM; el perfil CPU cumple la **misma barra de exactitud y de
seguridad** con techos de latencia propios y publicados; caída automática cuando
no hay GPU o está ocupada; BAXY no le pelea la máquina a su dueño.

### A.2 Ciclo de vida de instalación

- **Instalación limpia**, primer arranque, update/rollback y **purge** en cuenta
  o VM desechable.

**Por qué se difiere.** No hay cuenta de Windows desechable ni equipo de repuesto
disponible.

**Qué sigue siendo obligatorio para el producto final.** El purge es la prueba
del invariante de privacidad —la persona puede borrar todo lo que BAXY sabe de
ella— y no puede entregarse sin demostrarse.

### A.3 Firma y distribución

- Certificado de firma de código.

**Por qué se difiere.** No está comprado. Es ambiental según la definición
estricta: su causa está fuera del código de BAXY.

---

## B. Diferido a una fase posterior — orden de trabajo explícito

### B.1 Voz completa

- **Wake word**, **STT**, transcripciones, TTS, VAD.
- Misiones compuestas ejecutadas **por voz**.
- Wake y transcripción contra voces diversas en holdout y en la sala real.

**Por qué se difiere.** Decisión del responsable del producto, 2026-08-15:
primero se refina el backend, después el wake word, después el STT y las
transcripciones. El orden es deliberado — la voz que alimenta un backend que
todavía no sirve la petición sólo añade una superficie más que depurar.

**Consecuencia inmediata y explícita.** Todo criterio de cierre que exija «por
voz» queda satisfecho **por texto** durante esta fase. Las misiones compuestas
end-to-end se demuestran por texto en la máquina física. Ningún informe puede
declarar la voz cerrada, y ninguno puede quedar bloqueado por ella.

---

## C. Activo ahora — esto sí bloquea

Estos criterios se miden en esta máquina y son los que gobiernan cada tanda:

1. **Cero defectos conocidos abiertos.** Todo defecto surfaceado se cierra
   arreglándolo. Prohibido bajar umbrales, marcar `skip`/`xfail`, mover a
   pendientes o envolver en un fallback.
2. **Compuertas de fuente verdes.** Toda compuerta en rojo bloquea.
3. **Los cuatro cortes de exactitud** sobre oráculos ciegos regenerables:
   A > 95 %, B > 90 %, C > 90 % de planes completos, D con sus tres ceros
   duros — 0 efectos no solicitados, 0 éxitos no verificados, 0 respuestas
   visibles fijas.
4. **Toda tasa partida por causa**: recuperación / decisión / vetos.
5. **Misiones compuestas end-to-end por texto** en la máquina física.
6. **Latencia de primera señal**: p50 ≤ 1,0 s y p95 ≤ 2,0 s, medida en esta
   máquina sobre una población que incluya turnos que el reconocedor no
   resuelve. O la frontera Pareto demostrable con el rechazo medido.
7. **Los invariantes de arquitectura**, que no se re-derivan nunca: catálogo
   tipado como única fuente de operaciones; la mente propone, el kernel
   autoriza, el provider ejecuta; nada se afirma sin verificar; estados
   terminales honestos; confirmación ligada a la invocación exacta; cero
   respuestas visibles fijas; local y privado.

---

## D. Cómo se declara terminada esta fase

La **fase de backend** se declara cumplida cuando, a la vez, se cumple todo lo
de la sección C. Nada de la sección A o B cuenta en su contra.

La **meta general** sigue sin poder declararse cumplida mientras quede pendiente
cualquier punto de A o B. La diferencia es que ahora eso se dice una vez, aquí,
en lugar de contaminar cada informe con un incumplimiento que nadie podía
resolver.

---

## E. Cómo se usa este documento

- Un criterio diferido **no** se cuenta como defecto abierto en el ledger.
- Un criterio diferido **no** se reetiqueta como ambiental salvo que lo sea de
  verdad: diferido significa «se medirá más tarde», ambiental significa «BAXY no
  puede repararlo». No son lo mismo y no se confunden.
- Cada informe repite en una línea qué está diferido, para que nadie lea un
  «cumplido» parcial como total.
