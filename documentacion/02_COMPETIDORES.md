# Contra qué compite BAXY

Estado: agosto de 2026. Este documento existe para que ningún goal reinvente lo
que el mercado ya resolvió, y para que nadie confunda lo que BAXY hace distinto
con lo que simplemente hace igual que los demás.

Revísalo cuando decidas una pieza de tecnología. Y si al medir descubres que algo
de aquí ya no es cierto, corrígelo — este campo se mueve rápido.

## El panorama, en tres grupos

### 1. Los asistentes de plataforma

**Microsoft Copilot** es el competidor natural: viene con el sistema operativo.
En Build 2026 Microsoft giró de los Copilot+ PC hacia una plataforma que corre
agentes y modelos locales sobre CPU, GPU y NPU en cualquier hardware Windows, con
un panel de agentes que da control granular sobre a qué datos accede cada uno y
registro local de su actividad.

Ese giro **valida la tesis de BAXY** —el asistente pertenece a la máquina, no a
la nube— y a la vez sube el listón: lo que antes era el diferenciador de BAXY
ahora viene de fábrica.

Dónde sigue flojo: Copilot está atado a la pila M365, se paga por asiento, y
fuera del mundo Microsoft su alcance es limitado.

### 2. Los asistentes locales de propósito general

**Jan.ai** — sustituto de ChatGPT que corre offline, con modelos descargables de
Hugging Face. Muy bueno como interfaz de chat local. No controla el ordenador.

**OpenHuman** — asistente personal de escritorio con memoria persistente,
búsqueda web, acceso a ficheros, voz y enrutado de modelos. Es el que más se
parece a BAXY en ambición.

**Agentic AI Desktop Suite** — offline-first para Windows 11 + WSL2: voz, visión,
OCR, RAG y control de terminal, sobre Ollama con Qwen 7B, Whisper y Piper TTS.

**NEXUS AI**, **LM Studio** — privacidad y ejecución local, más plataforma que
asistente.

### 3. La pila que todo el mundo monta

El montaje estándar de un asistente de voz local en 2026 es **whisper.cpp + un
LLM local vía Ollama + Piper TTS**. Con una RTX 3060 de 12 GB y Llama 3.3 8B, la
latencia extremo a extremo va de 1 a 2 segundos.

Ese número es la vara con la que se te va a medir. Y ojo al hardware: 12 GB de
VRAM y un modelo de 8B. BAXY apunta a 4 GB como techo — si llega a una latencia
comparable con una cuarta parte de la memoria, eso es un resultado, no un empate.

## En qué se diferencia BAXY

Casi nadie compite en las tres cosas a la vez. La mayoría hace una bien.

**1. No miente, y lo demuestra.** Es la diferencia grande y la más difícil de
copiar. Los asistentes del mercado ejecutan y reportan lo que el ejecutor
devolvió; BAXY exige que un verificador independiente confirme el estado
observable antes de afirmar nada, y tiene estados terminales honestos para cuando
no puede. «Se envió el comando» no es «se completó la misión».

Un agente que dice haber hecho algo que no hizo se desinstala el primer día. Ahí
es donde BAXY se gana quedarse.

**2. El catálogo tipado como única fuente de autoridad.** La mente propone, el
kernel autoriza, el provider ejecuta. Ni el prompt, ni el corpus, ni el modelo
pueden inventar una operación o elevar su autoridad. La mayoría de asistentes
agénticos le dan al modelo una terminal y confían en el prompt — eso escala en
capacidad y no escala en seguridad.

**3. Los tres idiomas de verdad.** Español, inglés y **spanglish**, con cambio de
idioma a media frase. Casi todo el mercado está afinado en inglés; el spanglish
real, con acentos reales, es terreno casi vacío.

**4. Presupuesto de recursos como criterio de diseño.** El mercado asume 8B y
12 GB de VRAM. BAXY pone el techo en 4 GB y busca activamente bajar de ahí,
porque un asistente que compite con el trabajo de su dueño acaba desinstalado.

## Lo que no vale la pena diferenciar

Estas están resueltas. Copiar el estándar y seguir:

- **Chat local con modelo descargable** — Jan.ai y LM Studio ya lo hacen bien.
- **La pila de voz** — whisper.cpp / Piper / Ollama es un estándar de facto que
  funciona. El goal 09 hereda antes de inventar.
- **RAG sobre ficheros locales** — resuelto en todas partes.
- **Cifrado local de conversaciones** — es higiene, no ventaja.

## Cómo se usa esto al elegir tecnología

Antes de adoptar una pieza, pregunta si el mercado ya la resolvió. Si la
respuesta es sí, cópiala y gasta el tiempo en lo que sí diferencia.

Los cuatro diferenciadores de arriba son donde el trabajo tiene sentido, y son
justo lo que los goals 03 a 08 atacan. El resto es infraestructura: que
funcione, que pese poco, y a otra cosa.
