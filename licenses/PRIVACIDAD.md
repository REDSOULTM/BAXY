# BAXY: política de privacidad / Privacy policy

Última actualización: 11 de noviembre de 2026 · Last updated: November 11, 2026

Las dos versiones dicen lo mismo. *Both versions say the same; English below.*

## Español

**Quién la escribe.** Emmanuel Antonio Villacura Arancibia, desarrollador de BAXY (Chile). Contacto: un *issue* en
<https://github.com/REDSOULTM/BAXY> o la web <https://baxy.app>.

**Lo esencial.** BAXY corre en tu computador: el modelo de lenguaje, el reconocimiento de voz, la voz, la palabra de
activación y lo que BAXY recuerda. **El desarrollador no recibe nada tuyo:** BAXY no tiene servidor propio, no manda
estadísticas de uso, ni informes de fallos, ni lo que dices o escribes. Lo que dices, tus archivos, tu pantalla y tus
recuerdos no salen de tu computador, salvo en los casos de abajo. Casi todos empiezan porque **tú pides algo** que
necesita un servicio de internet, y entonces sólo sale lo necesario para ese pedido; los que BAXY hace sin que se lo
pidas están en «Sin que lo pidas», más abajo.

**Qué sale y a quién**, cuando le pides algo a BAXY o, donde la fila lo dice, sin pedirlo:

| Cuando pides | Servicio | Qué recibe | Sus condiciones |
|---|---|---|---|
| El tiempo | MET Norway (Instituto Meteorológico de Noruega, Oslo) | Las coordenadas del lugar (4 decimales), tu dirección IP y el nombre y la versión de BAXY | <https://api.met.no/doc/TermsOfService> (sus registros guardan la IP y las coordenadas; aceptados por el desarrollador el 2026-11-08) |
| El tiempo «aquí», o algo «cerca de mí» | ipwho.is | Tu dirección IP, para saber tu ciudad aproximada | <https://ipwhois.io/terms> |
| Una búsqueda en la web | DuckDuckGo | Lo que pides buscar (y tu ciudad y su país si pides «cerca de mí»), con el país que tienes puesto en Windows si el buscador lo ofrece en el idioma de la búsqueda, desde tu IP, por un navegador WebView2 oculto que usa un perfil propio de BAXY. Como cualquier navegador, la página que carga puede pedir por su cuenta recursos de otros sitios (imágenes, scripts, anuncios o analítica), que reciben tu IP y la dirección de esa página | <https://duckduckgo.com/privacy> |
| Una página web concreta, o un fichero que pides descargar de una dirección | El sitio de esa página o de ese fichero | Tu IP y la dirección, en una petición que lleva el nombre de BAXY; si la página sólo muestra su texto con scripts, la carga el navegador WebView2 oculto de la fila de arriba, y puede pedir recursos de otros sitios como dice esa fila | Las de ese sitio |
| Un artículo de enciclopedia | Wikipedia (Fundación Wikimedia) | Lo que pides buscar (y tu ciudad y su país si pides «cerca de mí») y el idioma | <https://foundation.wikimedia.org/wiki/Policy:Privacy_policy> |
| Sitios de un lugar («farmacias en…») | Photon (komoot), con datos de OpenStreetMap | El lugar y la clase de sitio (y tu ciudad y su país si pides «cerca de mí») | <https://photon.komoot.io/> |
| Un cambio de moneda | Frankfurter | Los códigos de las dos monedas | <https://frankfurter.dev/> (dice no guardar IP) |
| Un vídeo de YouTube | YouTube (Google) | Lo que pides ver | <https://policies.google.com/privacy> |
| Instalar un juego de Steam por su nombre, o ver su página en la tienda (sólo si no está entre tus juegos instalados) | La tienda de Steam (Valve) | El título que pides y tu IP; al instalar, si la tienda no tiene un juego con ese título, también trozos del título (el título sin una de sus palabras, o una palabra sola) | <https://store.steampowered.com/privacy_agreement/> |
| Abrir un sitio, una búsqueda o un título en tu navegador o en una aplicación (por ejemplo YouTube, Netflix o Steam) | Ese sitio, que carga el navegador o la aplicación | Lo que pides abrir o buscar, y lo que ese navegador o esa aplicación mande por su cuenta; al abrir una dirección en tu navegador, BAXY pregunta además a ese sitio, con una petición propia desde tu IP, si la página responde | Las de ese sitio |
| Comprobar si una máquina o un sitio responde (ping) | La máquina o el sitio que nombras | Un paquete de prueba (ICMP), desde tu IP | Las de ese sitio |
| Ejecutar un comando en la terminal | Lo que ese comando contacte | Lo que el comando mande | Las de ese sitio |
| Enviar un mensaje (por Discord o WhatsApp) o un correo, o crear una cita (por Outlook) | Esa aplicación tuya, con tu cuenta, y su servicio | El texto y el destinatario que dices, o la cita; los envía esa aplicación, no BAXY | Las de ese servicio |
| Instalar un programa, o desinstalarlo, con winget (el gestor de paquetes de Windows) | Las fuentes de winget de tu Windows (de serie, el catálogo de winget y el de la Microsoft Store, los dos de Microsoft) y, al instalar, el sitio del que winget baja el instalador | El nombre o el identificador del programa que pides, y tu IP; lo envía winget, no BAXY | Las de Microsoft para winget (<https://learn.microsoft.com/windows/package-manager/winget/source> nombra sus fuentes) y las de ese sitio. BAXY llama a winget con las opciones que aceptan por ti los acuerdos de la fuente y, al instalar, los del paquete (`--accept-source-agreements`, `--accept-package-agreements`): winget no te pregunta por ellos |
| Descargar el modelo ajustado opcional (sólo si lo eliges en Ajustes) | Hugging Face | Tu IP y el fichero que se baja | <https://huggingface.co/privacy> |
| Buscar un modelo local (sólo si lo haces en Ajustes → Modelo → Local) | Hugging Face | El nombre que escribes y tu IP; BAXY pide además a Hugging Face los datos de los modelos que aparecen y el principio de algunos de sus ficheros | <https://huggingface.co/privacy> |
| Instalar Ollama (sólo si lo eliges en Ajustes → Modelo → Local) | GitHub | Tu IP y el fichero que se baja | <https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement> |
| Instalar un modelo local (sólo si lo eliges en Ajustes → Modelo → Local) | Hugging Face; lo pide BAXY y, si eliges su visión, Ollama | Tu IP y el modelo que se baja (y su visión, si la eliges) | <https://huggingface.co/privacy> |
| Buscar una versión nueva (sólo en la copia de GitHub: una vez en cada arranque, salvo que apagues «Avisar de versiones nuevas» en Ajustes → General → Versión, y cuando buscas actualizaciones o se lo pides a BAXY) | GitHub (api.github.com) | Tu IP y la versión de BAXY instalada; pide la última versión publicada de REDSOULTM/BAXY y, si es más nueva, baja su fichero release.json y su firma para comprobarla | <https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement> |
| Actualizar BAXY (sólo en la copia de GitHub, y sólo si eliges actualizar) | GitHub | Tu IP y la versión de BAXY; se baja el instalador nuevo, que se comprueba con su SHA-256 antes de abrirlo | <https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement> |
| Usar tu propia clave de una empresa de IA (sólo si la conectas en Ajustes) | Esa empresa (Anthropic, OpenAI o Google), o el servidor que escribas en «Otra» si no está en tu computador | Lo que dices y lo que BAXY lee para ti, incluidos textos e imágenes de tu pantalla, archivos y páginas. Al conectarla, o al abrir con ella una conversación guardada, se envía también esa conversación entera, incluido lo que hiciste antes con el modelo local | Las de esa empresa, con tu cuenta |

**Cómo se presenta BAXY.** Las peticiones que BAXY hace él mismo a MET Norway, ipwho.is, Wikipedia, Photon, Frankfurter,
YouTube, Hugging Face y GitHub, y las de leer una página o descargar un fichero, dicen que vienen de BAXY: llevan su
nombre y, algunas, su versión y una dirección del proyecto en GitHub. Lo que carga el navegador WebView2 oculto (la
búsqueda en DuckDuckGo y las páginas que sólo muestran su texto con scripts) se presenta como ese navegador, sin el
nombre de BAXY.

**Sin que lo pidas.** En la copia de GitHub, BAXY busca una versión nueva una vez en cada arranque (la fila «Buscar una
versión nueva» de la tabla), y deja de hacerlo si apagas «Avisar de versiones nuevas» en Ajustes → General → Versión. Y,
en cualquier copia, si a Windows le falta WebView2 de Microsoft, que BAXY necesita para su ventana, BAXY lo descarga de
Microsoft al arrancar: Microsoft recibe tu IP.
Además, mientras BAXY está abierto, el componente WebView2 de Microsoft que dibuja su ventana, y el navegador WebView2
oculto cuando lee páginas, contactan por su cuenta con Microsoft desde tu IP: al arrancar, de vez en cuando, con su
servicio de experimentos y configuración (config.edge.skype.com), al que mandan la versión de WebView2 y de Windows, la
arquitectura, fechas de instalación y un identificador de WebView2 en este computador; y, cada pocos minutos, con su
servicio de actualización de componentes (edge.microsoft.com), al que mandan la lista de sus piezas con sus versiones, el
idioma, datos del equipo (Windows, procesador, memoria y si está unido a un dominio) e identificadores de esa consulta.
No llevan nada de lo que dices, escribes o lees, ni de tu pantalla. Microsoft describe los dos en
<https://learn.microsoft.com/deployedge/microsoft-edge-security-endpoints>. WebView2 no da a las aplicaciones ninguna
opción documentada para apagarlos, y BAXY no cambia las directivas de tu Windows ni bloquea direcciones. El primero lo
corta la directiva de WebView2 «ExperimentationAndConfigurationServiceControl» en modo restringido, que puede poner quien
administra el computador y que Microsoft no recomienda (<https://learn.microsoft.com/deployedge/microsoft-edge-webview-policies>).
SmartScreen, el filtro de Microsoft que recibiría la dirección de las páginas que se abren, está apagado en la ventana
de BAXY y en el navegador oculto.

**Lo que no sale.** Los nombres de lugares del tiempo y de la hora se buscan en los datos de GeoNames que BAXY lleva
dentro: GeoNames no recibe nada. Abrir programas, leer ventanas, tus notas, recordatorios y recuerdos se hacen en tu computador. El nombre de cada conversación lo pone un modelo de este computador (el de BAXY u Ollama); si usas una empresa de IA u «Otra», la conversación se queda con sus primeras palabras y su nombre no se le pide. Buscar una versión nueva no manda nada de lo que dices ni de tus archivos: sólo la versión de BAXY, desde tu IP. Las copias de Steam y de itch.io no preguntan a GitHub. La de Steam la actualiza Steam, y la de itch.io, la app de itch.io si la instalaste con ella: «Abrir en Steam» o «Abrir en itch.io» (o pedirle a BAXY que se actualice) abre la biblioteca de Steam o la página de BAXY en itch.io. Una copia bajada de la página de itch.io sin su app no se actualiza sola: la versión nueva se baja de esa misma página.

**«Búsqueda web».** Ese interruptor (Ajustes → Privacidad → Salidas a internet) cubre sólo lo que BAXY pide a internet por su cuenta: buscar en la web, leer una página, descargar un fichero, buscar un vídeo en YouTube y consultar la tienda de Steam por un juego que pides ver o instalar. Apagado, BAXY no hace nada de eso. Lo que pides abrir por su nombre en tu navegador u otro programa tuyo (un sitio, un vídeo, una serie o un juego) no pasa por ese interruptor: es tu orden y sale por ese programa; y al abrir una dirección en tu navegador, la petición propia con la que BAXY pregunta a ese sitio si responde tampoco pasa por él (la fila «Abrir un sitio, una búsqueda o un título» de la tabla).

**El modelo ajustado opcional.** El ajuste se entrenó con conversaciones sintéticas con recibos de trazas reales; no se usó texto privado de ninguna persona. Esas conversaciones se escribieron con un servicio de IA de terceros; la autorización de ese servicio para entrenar un modelo con ellas se pidió el 2026-11-07 y, al 2026-11-10, sigue sin respuesta.

**Microsoft y la tienda.** El instalador de la copia de GitHub baja de GitHub las piezas de BAXY, y de Microsoft, si faltan, WebView2 y el runtime de Visual C++: GitHub y Microsoft reciben tu IP. Las copias de Steam y de itch.io no tienen instalador: las baja su tienda, y si a Windows le falta WebView2, BAXY lo descarga de Microsoft al arrancar. WebView2
envía datos de diagnóstico a Microsoft según el ajuste de Windows «Privacidad y seguridad > Diagnóstico y comentarios»
(<https://learn.microsoft.com/microsoft-edge/webview2/concepts/data-privacy>). Si compras BAXY en Steam o en itch.io, la
compra y tu cuenta las rigen las políticas de esa tienda.

**Dónde se guarda lo tuyo.** En tu computador, en la carpeta de datos de BAXY (`%LOCALAPPDATA%\BAXY`). Puedes ver,
editar y borrar lo que BAXY recuerda, y el desinstalador de la copia de GitHub quita esa carpeta si eliges borrar tus datos. Las copias de Steam y de itch.io no tienen desinstalador propio: desinstalarlas (desde Steam, con la app de itch.io o borrando su carpeta) no borra esa carpeta de datos, que puedes borrar a mano. Ahí queda también el modelo ajustado opcional, si lo bajaste. Las últimas 50 conversaciones, con su nombre, se guardan ahí cifradas para tu usuario de Windows, y puedes borrarlas. BAXY deja además, en su carpeta de datos (%LOCALAPPDATA%\BAXY), registros técnicos sin cifrar. Los dos que anotan cada turno (renew\turns.jsonl, hasta unos 100 MB, y 1\conversation\conversation.v1.jsonl, hasta 8 MB) guardan la hora, cuánto tardó y qué operaciones se usaron, no lo que dices ni lo que BAXY responde, salvo que tú lo actives en tu computador para diagnosticar un fallo (variable BAXY_TRACE_WORDS=1); un registro de errores puede citar un fragmento de lo que el modelo escribía cuando falló. Lo que una versión anterior de BAXY hubiera anotado en ellos con lo que dijiste se borra la primera vez que arranca esta versión (si otro programa lo tiene abierto en ese momento, en el arranque siguiente), salvo que tengas activada esa variable: entonces sigue ahí hasta que uses «Olvidar todo». Cuando BAXY mira tu pantalla guarda la captura, sin cifrar, en 1\captures sólo mientras atiende ese pedido: la borra al terminarlo y al cerrarse. «Olvidar todo» borra esos registros y las capturas junto con las conversaciones. Lo que dejan las páginas que lee el navegador WebView2 oculto queda en un perfil aparte dentro de esa carpeta: BAXY borra su caché, su historial y lo que cada sitio guarda al terminar de leer cada página, lo vacía antes de usarlo otra vez si pasa de 100 MB, y «Olvidar todo» lo vacía también. Los servicios de la tabla
guardan lo que reciben según sus propias políticas; el desarrollador no tiene acceso a eso.

**Cambios.** Si BAXY empieza a enviar algo nuevo, esta política cambiará antes, con su fecha.

Esta política la escribió el desarrollador con ayuda de una IA y no la ha revisado un abogado.

## English

**Who writes it.** Emmanuel Antonio Villacura Arancibia, BAXY's developer (Chile). Contact: an issue at
<https://github.com/REDSOULTM/BAXY> or the website <https://baxy.app>.

**The essentials.** BAXY runs on your computer: the language model, speech recognition, the voice, the wake word and
what BAXY remembers. **The developer receives nothing of yours:** BAXY has no server of its own and sends no usage
statistics, no crash reports, and nothing you say or type. What you say, your files, your screen and your memories do
not leave your computer, except in the cases below. Almost all of them start because **you ask for something** that
needs an internet service, and then only what that request needs is sent; those BAXY does without being asked are under
«Without being asked», further down.

**What is sent, and to whom**, when you ask BAXY for something or, where the row says so, without asking:

| When you ask for | Service | What it receives | Its terms |
|---|---|---|---|
| The weather | MET Norway (Norwegian Meteorological Institute, Oslo) | The place's coordinates (4 decimals), your IP address and BAXY's name and version | <https://api.met.no/doc/TermsOfService> (its logs keep the IP and coordinates; accepted by the developer on 2026-11-08) |
| The weather "here", or something "near me" | ipwho.is | Your IP address, to find your approximate city | <https://ipwhois.io/terms> |
| A web search | DuckDuckGo | What you ask to search for (and your city and its country if you ask "near me"), with the country set in Windows if the search engine offers it in the language of the search, from your IP, through a hidden WebView2 browser with a profile of BAXY's own. Like any browser, the page it loads may ask other sites on its own for resources (images, scripts, ads or analytics), which receive your IP and that page's address | <https://duckduckgo.com/privacy> |
| A given web page, or a file you ask to download from an address | That page's or that file's site | Your IP and the address, in a request that carries BAXY's name; if the page only shows its text through scripts, the hidden WebView2 browser of the row above loads it, and it may ask other sites for resources as that row says | That site's |
| An encyclopedia article | Wikipedia (Wikimedia Foundation) | What you ask to search for (and your city and its country if you ask "near me") and the language | <https://foundation.wikimedia.org/wiki/Policy:Privacy_policy> |
| Places in an area ("pharmacies in…") | Photon (komoot), with OpenStreetMap data | The place and the kind of place (and your city and its country if you ask "near me") | <https://photon.komoot.io/> |
| A currency conversion | Frankfurter | The two currency codes | <https://frankfurter.dev/> (says it keeps no IP) |
| A YouTube video | YouTube (Google) | What you ask to watch | <https://policies.google.com/privacy> |
| Installing a Steam game by its name, or seeing its page in the store (only if it is not among your installed games) | The Steam store (Valve) | The title you ask for and your IP; when installing, if the store has no game with that title, also pieces of the title (the title without one of its words, or one word alone) | <https://store.steampowered.com/privacy_agreement/> |
| Opening a site, a search or a title in your browser or in an app (for example YouTube, Netflix or Steam) | That site, loaded by the browser or the app | What you ask to open or search for, and whatever that browser or app sends on its own; when opening an address in your browser, BAXY also asks that site, with a request of its own from your IP, whether the page answers | That site's |
| Checking whether a machine or a site answers (ping) | The machine or the site you name | A test packet (ICMP), from your IP | That site's |
| Running a command in the terminal | Whatever that command contacts | Whatever the command sends | That site's |
| Sending a message (through Discord or WhatsApp) or an email, or creating an appointment (through Outlook) | That app of yours, with your account, and its service | The text and the recipient you say, or the appointment; that app sends them, not BAXY | That service's |
| Installing a program, or uninstalling it, with winget (Windows' package manager) | The winget sources of your Windows (by default winget's catalog and the Microsoft Store's, both Microsoft's) and, when installing, the site winget downloads the installer from | The name or the identifier of the program you ask for, and your IP; winget sends it, not BAXY | Microsoft's for winget (<https://learn.microsoft.com/windows/package-manager/winget/source> names its sources) and that site's. BAXY calls winget with the options that accept for you the source's agreements and, when installing, the package's (`--accept-source-agreements`, `--accept-package-agreements`): winget does not ask you about them |
| Downloading the optional fine-tuned model (only if you choose it in Settings) | Hugging Face | Your IP and the file downloaded | <https://huggingface.co/privacy> |
| Searching for a local model (only if you do it in Settings → Model → Local) | Hugging Face | The name you type and your IP; BAXY also asks Hugging Face for the details of the models that come up and for the beginning of some of their files | <https://huggingface.co/privacy> |
| Installing Ollama (only if you choose it in Settings → Model → Local) | GitHub | Your IP and the file downloaded | <https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement> |
| Installing a local model (only if you choose it in Settings → Model → Local) | Hugging Face; asked by BAXY and, if you choose its vision, by Ollama | Your IP and the model downloaded (and its vision, if you choose it) | <https://huggingface.co/privacy> |
| Looking for a new version (only in the copy from GitHub: once at each start, unless you switch off «Tell me about new versions» in Settings → General → Version, and when you check for updates or ask BAXY) | GitHub (api.github.com) | Your IP and the installed version of BAXY; it asks for the latest published version of REDSOULTM/BAXY and, if it is newer, downloads its release.json file and its signature to check it | <https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement> |
| Updating BAXY (only in the copy from GitHub, and only if you choose to update) | GitHub | Your IP and BAXY's version; the new installer is downloaded and checked against its SHA-256 before it is opened | <https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement> |
| Using your own key from an AI company (only if you connect it in Settings) | That company (Anthropic, OpenAI or Google), or the server you enter under «Other» if it is not on your computer | What you say and what BAXY reads for you, including text and images from your screen, files and pages. When you connect it, or open a saved conversation with it, that whole conversation is sent too, including what you did earlier with the local model | That company's, under your account |

**How BAXY introduces itself.** The requests BAXY makes itself to MET Norway, ipwho.is, Wikipedia, Photon, Frankfurter,
YouTube, Hugging Face and GitHub, and those to read a page or download a file, say they come from BAXY: they carry its
name and, some of them, its version and an address of the project on GitHub. What the hidden WebView2 browser loads
(the search on DuckDuckGo and the pages that only show their text through scripts) introduces itself as that browser,
without BAXY's name.

**Without being asked.** In the copy from GitHub, BAXY looks for a new version once at each start (the row «Looking for
a new version» in the table), and stops doing so if you switch off «Tell me about new versions» in Settings → General →
Version. And, in any copy, if Windows lacks Microsoft's WebView2, which BAXY needs for its window, BAXY downloads it from
Microsoft when it starts: Microsoft receives your IP.
Also, while BAXY is open, Microsoft's WebView2 component that draws its window, and the hidden WebView2 browser when it
reads pages, contact Microsoft on their own from your IP: when they start, now and then, its experimentation and
configuration service (config.edge.skype.com), to which they send the version of WebView2 and of Windows, the
architecture, installation dates and an identifier of WebView2 on this computer; and, every few minutes, its component
update service (edge.microsoft.com), to which they send the list of their parts with their versions, the language, data
about the machine (Windows, processor, memory and whether it is joined to a domain) and identifiers of that request.
They carry nothing you say, type or read, nor anything of your screen. Microsoft describes both at
<https://learn.microsoft.com/deployedge/microsoft-edge-security-endpoints>. WebView2 gives apps no documented option to
switch them off, and BAXY does not change your Windows policies nor block addresses. The first one is stopped by the
WebView2 policy "ExperimentationAndConfigurationServiceControl" in restricted mode, which whoever manages the computer can
set and which Microsoft does not recommend (<https://learn.microsoft.com/deployedge/microsoft-edge-webview-policies>).
SmartScreen, Microsoft's filter that would receive the address of the pages that are opened, is off in BAXY's window and
in the hidden browser.

**What is not sent.** Place names for the weather and the time are looked up in the GeoNames data BAXY carries inside:
GeoNames receives nothing. Opening programs, reading windows, your notes, reminders and memories happen on your computer. Each conversation is named by a model on this computer (BAXY's or Ollama's); if you use an AI company or «Other», the conversation keeps its first words and its name is not asked of it. Looking for a new version sends nothing you say and none of your files: only BAXY's version, from your IP. The copies from Steam and itch.io do not ask GitHub. Steam updates the one from Steam, and the itch app updates the one from itch.io if you installed it with that app: «Open in Steam» or «Open in itch.io» (or asking BAXY to update) opens Steam's library or BAXY's page on itch.io. A copy downloaded from the itch.io page without its app is not updated by itself: you download the new version from that same page.

**"Web search".** That switch (Settings → Privacy → Going online) covers only what BAXY asks the internet for on its own: searching the web, reading a page, downloading a file, searching for a video on YouTube and looking up in the Steam store a game you ask to see or install. With it off, BAXY does none of that. What you ask to open by its name in your browser or another program of yours (a site, a video, a series or a game) does not go through that switch: it is your order and leaves through that program; and when you open an address in your browser, the request of its own with which BAXY asks that site whether it answers does not go through it either (the row "Opening a site, a search or a title" of the table).

**The optional fine-tuned model.** The fine-tune was trained on synthetic conversations whose tool receipts are taken from real traces; no person's private text was used. Those conversations were written with a third-party AI service; that service's permission to train a model on them was requested on 2026-11-07 and, as of 2026-11-10, has had no answer.

**Microsoft and the store.** The installer of the copy from GitHub downloads BAXY's parts from GitHub and, if they are missing, WebView2 and the Visual C++ runtime from Microsoft: GitHub and Microsoft receive your IP. The copies from Steam and itch.io have no installer: their store downloads them, and if Windows lacks WebView2, BAXY downloads it from Microsoft when it starts. WebView2 sends diagnostic data to Microsoft according to the Windows setting "Privacy & security > Diagnostics
& feedback" (<https://learn.microsoft.com/microsoft-edge/webview2/concepts/data-privacy>). If you buy BAXY on Steam or
itch.io, your purchase and account are governed by that store's policies.

**Where your data is kept.** On your computer, in BAXY's data folder (`%LOCALAPPDATA%\BAXY`). You can view, edit and
delete what BAXY remembers, and the uninstaller of the copy from GitHub removes that folder if you choose to delete your data. The copies from Steam and itch.io have no uninstaller of their own: uninstalling them (from Steam, with the itch.io app or by deleting their folder) does not delete that data folder, which you can delete by hand. The optional fine-tuned model, if you downloaded it, is kept there too. Your last 50 conversations, with their names, are kept there encrypted for your Windows user, and you can delete them. BAXY also leaves unencrypted technical logs in its data folder (%LOCALAPPDATA%\BAXY). The two that note each turn (renew\turns.jsonl, up to about 100 MB, and 1\conversation\conversation.v1.jsonl, up to 8 MB) keep the time, how long it took and which operations were used, not what you say nor what BAXY answers, unless you turn that on in your computer to diagnose a fault (the BAXY_TRACE_WORDS=1 variable); an error log may quote a fragment of what the model was writing when it failed. What an earlier version of BAXY had noted in them with what you said is deleted the first time this version starts (if another program has it open at that moment, at the next start), unless you have that variable turned on: then it stays there until you use «Forget everything». When BAXY looks at your screen it keeps the capture, unencrypted, in 1\captures only while it handles that request: it deletes it when the request ends and when BAXY closes. «Forget everything» deletes those logs and the captures along with the conversations. What the pages read by the hidden WebView2 browser leave stays in a separate profile inside that folder: BAXY deletes its cache, its history and what each site stores when it finishes reading each page, empties it before using it again if it exceeds 100 MB, and «Forget everything» empties it too. The services in the table keep what
they receive under their own policies; the developer has no access to it.

**Changes.** If BAXY starts sending anything new, this policy will change first, with its date.

This policy was written by the developer with the help of an AI and has not been reviewed by a lawyer.
