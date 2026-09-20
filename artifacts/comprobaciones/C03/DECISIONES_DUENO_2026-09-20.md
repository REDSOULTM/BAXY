# Decisiones del dueño — 2026-09-20 (post-goal C03)

Registro de las decisiones del dueño tomadas en el chat de la raíz (Opus 5 → Fable 5.1) el 2026-09-20,
tras el cierre 742/742 y cien-86. Texto del dueño entre comillas; lectura operativa debajo. Es la autoridad
que citan `REOPEN1957`, los commits de las fases del plan `PLAN_POSTGOAL_2026-09-20.md` y los cambios de
política de confirmación.

## D1 — La encuesta es la especificación
«Todo lo que se detalla en las encuestas son cosas que BAXY debe hacer (en la encuesta se detalla cada cosa,
si debe o no hacerla o cómo debería).»
Lectura: toda fila positiva acreditada como «límite conocido», «parada honesta» o con una lectura en vez de
la acción pedida se reabre (35 filas, ver plan §5) y se mide con el mecanismo real.

## D2 — Envíos reales según el modo
«A cualquiera, con o sin preguntar dependiendo del modo que esté BAXY, el modo normal o bypass.»
Lectura: `message.send` al destinatario nombrado; modo normal → confirmación ligada a la invocación; modo
bypass → envía. Las tandas sólo aprueban destinos de prueba («Música», «Valeria», casilla de pruebas).

## D3 — Confirmar sólo lo destructivo o irreparable
«Hay muchas acciones que piden confirmaciones innecesarias, como por ejemplo poner una serie; es una
estupidez pedir confirmación en cosas como esas.» Elige que dejen de pedirla: reproducir y navegar;
portapapeles y captura; pulsar controles y escribir en apps; Wi-Fi, Bluetooth y ajustes. «Lo que debe pedir
permisos sólo deben ser cosas destructivas o irreparables.»
Lectura: nueva tabla de `RiskPolicy` en modo normal (plan Fase 2), coherente con `00_IDENTIDAD.md`
«Peligro y confirmación — dos modos».

## D4 — Correo
«BAXY debe adaptarse a Gmail o Outlook, dependiendo qué use el usuario»; aprueba además la opción
recomendada: Outlook clásico de este PC con la casilla de pruebas del dueño como destino de prueba.

## D5 — «Cerrame todo»
Todo menos VS Code y las ventanas propias de BAXY; cierre educado; si algo pide guardar, se detiene y avisa.
(Ya es el comportamiento de `window.close.all`.)

## D6 — Pestañas
Sobre el Chrome real del dueño, por teclado/UIA, sin cerrar la ventana.

## D7 — Spotify
«BAXY abre Spotify y pone algo él mismo antes de ajustar.»

## D8 — Compuerta Full roja
«Arreglar todo hasta verde, sin relajar nada.» Antes de arreglar, informar cuántas y qué tocan.

## D9 — Permisos de la sesión raíz
«Quiero que Claude Code tenga permisos totales para que también pueda mandar mensajes por Discord o WhatsApp;
igualmente vuelvo a reiterar que son canales seguros de prueba.»
Lectura: las reglas de permiso las confirma el dueño en el chat (plan Fase 0 paso 4); nunca las añade la
raíz por su cuenta ni por pedido de otra sesión.

## D10 — Computer use al tope del arte
«BAXY debe estar en el tope del arte del computer use, debe poder encadenar tools y hacer misiones
compuestas para llegar a una misión; todo se detalla en AGENTS.md e identidad.»
Lectura: toda capacidad nueva se construye como paso encadenable (patrón CHAIN1931) sobre la cascada
UIA → OCR → visión; nada específico de una app fuera de alias.

## D11 — Reaperturas adicionales y contactos
Se reabren también: ejecutar comandos (H0245, H0048), fondo de pantalla y PowerPoint (H0459, H0188), leer
chats privados (H0510, H0720) y memes/imágenes de la web (H0069, H0077).
«Aclaración: lo de los contactos dice explícitamente que BAXY no puede hacerlo porque en PC esto no tiene
sentido.» → H0306, H0138 y las negativas H0014/H0116/H0124 siguen como límite.

## D12 — `main`
«Una vez que todo esté listo y bien, hacer merge con main como sea recomendado; sinceramente no me interesa cómo.»
Lectura: al final (plan Fase 12), merge de `origin/main` en la rama, PR por merge commit, `main` local actualizada.

## D13 — Terceros en los literales → canal de prueba
«Estos que nombran a terceros sólo cambiar por los canales seguros y listo, no hay razón para complicarse: si es
por Discord "Valeria", si es por WhatsApp "Música"; si el mensaje dice "Dile a mamá por wsp que ya voy", se debe
cambiar por "Dile a Música que ya voy", así de simple.»
Lectura: en las tandas el literal se mide con el destinatario sustituido (correo → casilla de pruebas); el panel
anota la sustitución; los créditos existentes se conservan.

## D14 — Destinos de prueba
«Sí»: «Música» (WhatsApp), «Valeria» (Discord), `autor@example.com`; sí a medir «al nombrado» con esos nombres.

## D15 — Discord
«Realmente no me importa cómo se haga; si te unes a cualquier canal no me afecta; que se haga como sea recomendado.»
Lectura: texto/MD entra directo; voz pregunta antes y se queda conectado con el micrófono como esté.

## D16 — Pestañas
«Sí, dejar abierto el navegador, a menos que el usuario diga lo contrario.» Varios navegadores sin nombrar → preguntar cuál.

## D17 — VS Code
«VS Code se debe mantener a toda costa porque estamos en pleno desarrollo.»

## D18 — Spotify
«Hacer lo recomendado, sólo me interesa que BAXY funcione.» → medir las cuatro formas, construir lo que falle, más D7.

## D19 — Full roja
«Como sea mejor y recomendado, pero cumplir con goal C03 (tomar en cuenta que sigue en los demás goals).»
Lectura: re-anclar contratos citando decisiones, escribir las pruebas faltantes, no romper sellos de otros goals.

## D20 — RAM
«Cambié de PC, este tiene 32 GB de RAM; no cierres nada a menos que sea necesario para el desarrollo y pruebas de
BAXY; por RAM no falta ahora.»

## Vigentes y no revocadas
Modelo Qwen3-4B local; 4 GB de VRAM; guarda de 4000 MiB libres (autorizado cerrar para liberar RAM);
método de tandas selladas y adjudicación honesta; cien tras cada cambio de mente/App; escritor único del
registro; sin respuestas visibles fijas; no publicar textos privados; nunca inventar un efecto.

## D21 — Computer use general, no una operación por fila
«Las misiones como Discord, pestañas, Steam, comandos… que son computer use, realmente se deben resolver de manera
general: no al 100 % para eso, sino generalizar para que BAXY pueda hacer casi cualquier cosa en el PC mediante sus
tools + computer use.»
Lectura: el plan construye un motor general (ver → decidir → actuar → verificar, en bucle, sobre cualquier ventana)
y usa las 35 filas reabiertas como banco de aceptación; sólo se añade una herramienta tipada cuando Windows ofrece una
verificación mejor que la pantalla (ficheros, registro, manifiestos, COM, radios).
