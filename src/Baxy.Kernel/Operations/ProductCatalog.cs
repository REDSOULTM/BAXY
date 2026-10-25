using System.Diagnostics.CodeAnalysis;
using System.Text.Json;
using Baxy.Contracts;

namespace Baxy.Kernel.Operations;

public static class ProductCatalog
{
    private const OperationJsonType NullableString = OperationJsonType.Null | OperationJsonType.String;
    private const OperationJsonType NullableInteger = OperationJsonType.Null | OperationJsonType.Integer;
    private const OperationJsonType NullableBoolean = OperationJsonType.Null | OperationJsonType.Boolean;
    private const OperationJsonType Scalar = OperationJsonType.Null
        | OperationJsonType.Boolean
        | OperationJsonType.Number
        | OperationJsonType.String;

    // The session media.control's YouTube tab publishes (WindowsExternalCapabilityProvider.YouTubeTabMediaSource).
    private const string YouTubeTabMediaSource = "BAXY YouTube (Edge)";

    private static readonly ProductOperationDescriptor[] Catalog =
    [
        Descriptor(
            "app.close",
            // Auditoría de los pedidos reales (2026-10-17): o una ventana resuelta (windowId) o la aplicación por su
            // nombre (appId), exactamente uno de los dos (AppCloseHandler).
            Schema(
                [
                    String("appId", maximumUtf8Bytes: 512, nonWhitespace: true),
                    String("windowId", maximumLength: 36, nonWhitespace: true),
                ],
                []),
            OperationRisks.WorkLoss,
            "app.close.identity.window.absence.v1",
            "Solicita el cierre de una ventana resuelta (windowId) o de todas las ventanas de una aplicación por su nombre (appId) y verifica su ausencia sin forzar la terminacion del proceso; si una ventana responde con un diálogo propio (guardar) se detiene y lo dice; el windowId caduca a los 5 minutos."),
        Descriptor(
            "app.installed",
            Schema([String("name", maximumUtf8Bytes: 256, nonWhitespace: true)], ["name"]),
            OperationRisks.ReadOnly,
            "app.installed.windows.catalog.snapshot.v1",
            "Busca una aplicación por su nombre en el catálogo Inicio de Windows, sin abrirla; si el catálogo no la lista dice inStartCatalog false (lo que no está en Inicio no se ve) y los nombres más cercanos del catálogo."),
        Descriptor(
            "app.open",
            Schema(
                [
                    String("appId", maximumUtf8Bytes: 512, nonWhitespace: true),
                    Boolean("forControl"),
                    Boolean("foreground"),
                    Boolean("newDocument"),
                    // Estabilización, encargo C: a place of the application with an address of its own, by its name in
                    // the data (src/baxy_mind/data/app_places.v1.json, ApplicationPlaces), and the value of its one slot
                    // (what is searched, a game's number). The address is composed by ApplicationPlaces alone.
                    String("place", NullableString, values: ApplicationPlaces.PlaceNames),
                    String("placeValue", NullableString, maximumUtf8Bytes: 128, nonWhitespace: true),
                ],
                ["appId"]),
            OperationRisks.LowReversible,
            "app.open.process.window.focus.v1",
            "Abre por nombre exacto una aplicación del catálogo Inicio del usuario y verifica su proceso y su ventana visible, y dice si quedó al frente; sin ese nombre exacto no abre nada y dice los nombres instalados más cercanos.",
            // It reuses the window of an application that already runs and raises it (foreground), presses Ctrl+N in it
            // (newDocument) or hands it a place's address, which the application opens in its window and raises
            // (ApplicationPlaceOpener); without those three the window that runs is left as it is, or a new process
            // starts and the front goes back where it was.
            effects:
            [
                WindowInput(
                    EffectCondition.IsTrue("foreground"),
                    EffectCondition.IsTrue("newDocument"),
                    EffectCondition.Named("place")),
            ]),
        // Auditoría de los pedidos reales (2026-10-17): reiniciar una aplicación no tenía operación propia y la única que
        // decía «restart» era system.power, que va sin el sí de la persona.
        Descriptor(
            "app.restart",
            Schema([String("appId", maximumUtf8Bytes: 512, nonWhitespace: true)], ["appId"]),
            OperationRisks.WorkLoss,
            "app.restart.window.close.process.exit.app.open.v1",
            "Reinicia una aplicación abierta: cierra con gracia sus ventanas como app.close (nunca fuerza; si una ventana responde con un diálogo propio, como guardar, se detiene y lo dice), espera hasta 10 segundos a que sus procesos terminen (si sigue corriendo oculta lo dice y no la mata), la abre otra vez como app.open y sólo da por reiniciada una aplicación con un proceso nuevo."),
        Descriptor(
            "audio.app.volume.adjust",
            Schema(
                [
                    Integer("amount", 1, 100),
                    String("app", maximumUtf8Bytes: 256, nonWhitespace: true),
                    String("direction", values: ["down", "up"]),
                ],
                ["amount", "app", "direction"]),
            OperationRisks.LowReversible,
            "audio.app.volume.adjust.session.postread.v1",
            "Sube o baja el volumen propio de una aplicación (sus sesiones de audio en la salida predeterminada, el control por aplicación del mezclador) una cantidad acotada desde su nivel observado y verifica la postlectura; no toca el volumen del sistema."),
        Descriptor(
            "audio.app.volume.set",
            Schema(
                [
                    String("app", maximumUtf8Bytes: 256, nonWhitespace: true),
                    Integer("level", 0, 100),
                ],
                ["app", "level"]),
            OperationRisks.LowReversible,
            "audio.app.volume.set.session.postread.v1",
            "Fija el volumen propio de una aplicación (sus sesiones de audio en la salida predeterminada, el control por aplicación del mezclador) en un nivel absoluto de 0 a 100, aunque esté en pausa, y verifica la postlectura; no toca el volumen del sistema."),
        Descriptor(
            "audio.microphone.mute",
            Schema([Boolean("state")], ["state"]),
            OperationRisks.LowReversible,
            "audio.microphone.mute.capture.endpoint.postread.v1",
            "Silencia o reactiva el micrófono predeterminado de Windows y corrobora la postlectura del endpoint de captura."),
        Descriptor(
            "audio.mute",
            Schema([Boolean("state")], ["state"]),
            OperationRisks.LowReversible,
            "audio.mute.endpoint.postread.v1",
            "Silencia o reactiva la salida predeterminada y corrobora la postlectura."),
        Descriptor(
            "audio.status",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "audio.status.endpoint.read.v1",
            "Identifica por nombre la salida de audio predeterminada actual y lee su volumen y silencio, sin modificarla."),
        Descriptor(
            "audio.volume",
            Schema([Integer("level", 0, 100)], ["level"]),
            OperationRisks.LowReversible,
            "audio.volume.endpoint.postread.v1",
            "Fija el volumen absoluto de la salida predeterminada y corrobora la postlectura."),
        Descriptor(
            "audio.volume.adjust",
            Schema(
                [
                    Integer("amount", 1, 100),
                    String("direction", values: ["down", "up"]),
                ],
                ["amount", "direction"]),
            OperationRisks.LowReversible,
            "audio.volume.adjust.endpoint.postread.v1",
            "Sube o baja el volumen de salida una cantidad acotada desde su valor observado y verifica la postlectura."),
        Descriptor(
            "backup.create",
            Schema(
                [
                    String("expectedSha256", maximumLength: 64, nonWhitespace: true),
                    String("resourceId", maximumLength: 35, nonWhitespace: true),
                ],
                ["expectedSha256", "resourceId"]),
            OperationRisks.LowReversible,
            "backup.create.sandbox.hash.postread.v1",
            "Crea una copia privada de un archivo identificado, verifica que su SHA-256 es el del original y lo registra para verificarla después."),
        Descriptor(
            "backup.known.create",
            Schema(
                [String("folder", values: ["all_known", "desktop", "documents", "pictures", "projects"])],
                ["folder"]),
            OperationRisks.LowReversible,
            "backup.known.create.windows.zip.hash.postread.v1",
            "Crea un ZIP privado de una carpeta conocida de Windows y verifica su manifiesto y SHA-256; no incluye vínculos ni marcadores de OneDrive, archivos que no puede abrir, carpetas que no puede abrir ni lo que pase de 32 niveles; cuenta los vínculos y marcadores y los archivos ilegibles, no las carpetas ni lo que pasa de 32 niveles."),
        Descriptor(
            "backup.known.list",
            Schema([Integer("limit", 1, 50)], []),
            OperationRisks.ReadOnly,
            "backup.known.list.windows.manifest.hash.snapshot.v1",
            "Lista los backups ZIP de carpetas conocidas (20 por defecto, 50 como mucho) y vuelve a verificar sus hashes; una vista muestra 20 como mucho (lo marca y no alcanza lo que pasa de ahí)."),
        Descriptor(
            "backup.known.restore.latest",
            Schema(
                [String("folder", values: ["all_known", "desktop", "documents", "pictures", "projects"])],
                ["folder"]),
            OperationRisks.LowReversible,
            "backup.known.restore.latest.windows.extract.hash.postread.v1",
            "Restaura el backup ZIP más reciente en un directorio privado nuevo y verifica archivos y bytes extraídos."),
        Descriptor(
            "backup.known.verify.latest",
            Schema(
                [String("folder", values: ["all_known", "desktop", "documents", "pictures", "projects"])],
                ["folder"]),
            OperationRisks.ReadOnly,
            "backup.known.verify.latest.windows.hash.postread.v1",
            "Verifica el SHA-256 del backup ZIP más reciente de la carpeta indicada."),
        Descriptor(
            "backup.list",
            Schema([Integer("limit", 1, 50)], []),
            OperationRisks.ReadOnly,
            "backup.list.sandbox.hash.snapshot.v1",
            "Lista las copias privadas, desde la más reciente, y dice de cada una si su SHA-256 sigue siendo el registrado al crearla, sin exponer rutas internas; 20 por defecto (totalCount dice cuántos hay); una vista muestra 20 como mucho (lo marca y no alcanza lo que pasa de ahí)."),
        Descriptor(
            "backup.restore",
            Schema(
                [
                    String("backupId", maximumLength: 39, nonWhitespace: true),
                    String("destinationRelativePath", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                ],
                ["backupId", "destinationRelativePath"]),
            OperationRisks.LowReversible,
            "backup.restore.sandbox.hash.postread.v1",
            "Restaura en un destino libre del sandbox una copia privada cuyo SHA-256 sigue siendo el registrado al crearla; una copia cambiada o sin ese registro no se restaura."),
        Descriptor(
            "backup.verify",
            Schema([String("backupId", maximumLength: 39, nonWhitespace: true)], ["backupId"]),
            OperationRisks.ReadOnly,
            "backup.verify.sandbox.hash.v1",
            "Reabre una copia privada y compara su SHA-256 con el registrado al crearla; una copia cambiada o sin ese registro no está verificada."),
        Descriptor(
            "bluetooth.device.list",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "bluetooth.device.list.hardware.snapshot.v1",
            "Enumera dispositivos Bluetooth mediante un adapter oficial y un gate físico de hardware; una vista muestra 20 como mucho (lo marca y no alcanza lo que pasa de ahí)."),
        Descriptor(
            "bluetooth.device.pair",
            Schema([String("deviceId", maximumUtf8Bytes: 256, nonWhitespace: true)], ["deviceId"]),
            OperationRisks.PrivacySensitive,
            "bluetooth.device.pair.hardware.postread.v1",
            "Empareja un dispositivo resuelto mediante el diálogo y permisos oficiales del sistema.",
            effects: [SystemChange()]),
        Descriptor(
            "bluetooth.radio.set",
            Schema([Boolean("state")], ["state"]),
            OperationRisks.LowReversible,
            "bluetooth.radio.set.windows.radio.postread.v1",
            "Enciende o apaga las radios Bluetooth mediante la API oficial de Windows y verifica su estado final.",
            effects: [SystemChange()]),
        Descriptor(
            "bluetooth.radio.status",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "bluetooth.radio.status.windows.radio.read.v1",
            "Lee si las radios Bluetooth están encendidas o apagadas mediante la API oficial de Windows; sin efecto."),
        Descriptor(
            "browser.control",
            Schema([String("action", values:
                ["back", "close", "close_all", "exit_fullscreen", "fullscreen_video", "new_tab", "reload", "scroll_down",
                    "scroll_up"])], ["action"]),
            OperationRisks.LowReversible,
            "browser.control.cdp.postread.v1",
            "Actúa sobre la pestaña activa de la ventana de delante del navegador predeterminado de la persona (atrás, recargar, desplazar, pestaña nueva, pantalla completa del vídeo, cerrar una o todas salvo la última, que se deja porque cerrarla cerraría la ventana) por mensajes de ventana o UI Automation, y verifica el efecto releyendo el marco del navegador; sólo si no hay navegador predeterminado, o con BAXY_BROWSER=product, actúa en el navegador propio del producto por CDP; cerrar todas para a las 50 pestañas o a los 40 segundos y dice cuántas cerró (closedTabs).",
            effects: [WindowInput()]),
        Descriptor(
            "browser.navigate",
            Schema([String("url", maximumUtf8Bytes: 2_048, nonWhitespace: true)], ["url"]),
            OperationRisks.ExternalCommunication,
            "browser.navigate.cdp.url.postread.v1",
            "Abre una URL exacta en el navegador predeterminado de la persona, con su perfil y sus sesiones, y verifica la llegada leyendo su barra de direcciones o el título de su ventana; sólo si no hay navegador predeterminado o no se puede lanzar, la abre en el navegador propio del producto por CDP y verifica la URL final.",
            // Al máximo 11.5: the URL BAXY opens leaves the PC (NetworkEgress reads this fact; the heartbeat held it by
            // its risk already).
            effects: [Network()]),
        Descriptor(
            "browser.navigate.named",
            Schema(
                [
                    String("browser", values: ["brave", "chrome", "edge", "opera", "opera_gx"]),
                    String("url", maximumUtf8Bytes: 2_048, nonWhitespace: true),
                ],
                ["browser", "url"]),
            OperationRisks.ExternalCommunication,
            "browser.navigate.named.cdp.url.postread.v1",
            "Navega el navegador Chromium indicado (Opera, Opera GX, Chrome, Edge o Brave) mediante un perfil CDP privado y verifica ejecutable y URL final.",
            effects: [Network()]),
        Descriptor(
            "browser.page.read",
            Schema([Integer("maximumCharacters", 256, 6_000)], []),
            OperationRisks.PrivacySensitive,
            "browser.page.read.cdp.dom.snapshot.v1",
            "Lee el título, la URL y el texto visible de la página de delante del navegador predeterminado de la persona por UI Automation, sin modificarla y con el contenido acotado; si BAXY abrió la última página en otro navegador (uno nombrado), lee ésa por CDP; 6.000 caracteres como mucho (truncated).",
            // WEB1541: a read observes no effect; the receipt says so truthfully.
            requiresObservedEffect: false,
            // Ronda final 15: it reads BAXY's own browser when its session is the one in use, and starts it in front when it
            // is not running.
            effects: [WindowInput()]),
        Descriptor(
            "browser.tabs.list",
            Schema([Integer("limit", 1, 50)], []),
            OperationRisks.PrivacySensitive,
            "browser.tabs.list.cdp.targets.snapshot.v1",
            "Enumera las pestañas de la ventana de delante del navegador predeterminado de la persona (20 por defecto, 50 como mucho), con su título y cuál está activa, leídas de su tira de pestañas por UI Automation; sin navegador predeterminado, las del navegador propio del producto por CDP; una vista muestra 20 como mucho (lo marca y no alcanza lo que pasa de ahí).",
            requiresObservedEffect: false,
            // Ronda final 15: as browser.page.read.
            effects: [WindowInput()]),
        Descriptor(
            "calculator.expression.evaluate",
            Schema([String("expression", maximumLength: 64, nonWhitespace: true)], ["expression"]),
            OperationRisks.LowReversible,
            "calculator.expression.evaluate.windows.calculator.uia.display.v1",
            "Pulsa una expresión aritmética simple (números y + - * /; ^ y paréntesis en el modo científico) en los botones de la Calculadora de Windows abierta, sin traerla al frente ni enviar teclas, y lee el resultado que muestra su pantalla mediante UI Automation; empezada por un operador, sigue desde el número que muestra; sin efecto fuera de la Calculadora.",
            effects: [WindowInput()]),
        Descriptor(
            "calendar.event.create",
            Schema(
                [
                    String("endUtc", maximumLength: 64, nonWhitespace: true),
                    String("startUtc", maximumLength: 64, nonWhitespace: true),
                    String("title", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                ],
                ["endUtc", "startUtc", "title"]),
            OperationRisks.ExternalCommunication,
            "calendar.event.create.account.postread.v1",
            "Crea un evento en el calendario predeterminado del Outlook clásico de la persona, que lo sincroniza con su cuenta si la cuenta sincroniza (se relee en este PC): sale de la máquina, así que pide su confirmación antes; verifica la identidad del evento creado."),
        Descriptor(
            "calendar.event.list",
            Schema(
                [
                    String("endUtc", maximumLength: 64, nonWhitespace: true),
                    String("startUtc", maximumLength: 64, nonWhitespace: true),
                ],
                ["endUtc", "startUtc"]),
            OperationRisks.ReadOnly,
            "calendar.event.list.account.snapshot.v1",
            "Lista los eventos del calendario predeterminado de Outlook entre dos fechas separadas por 366 días como mucho (un rango mayor se rechaza), como mucho 200 leídos (pasado el tope lo dice) y una vista muestra los 20 primeros, sin modificarlos."),
        // Ronda 22 (uso real r18 t2-c16, t3-c11, t4-c09 «…y guárdala en el escritorio»): a capture the person asks to
        // keep is also saved as a PNG in the known folder named («folder»; pictures: its screenshots subfolder), with
        // a dated name that never overwrites, read back against its hash. Without «folder» it stays private only.
        Descriptor(
            "capture.active.window",
            CaptureSchema(),
            OperationRisks.PrivacySensitive,
            "capture.active.window.gdi.foreground.bounds.bmp.hash.v1",
            "Captura solo los límites visibles de la ventana activa en un BMP privado y devuelve metadatos verificados; con folder guarda además una copia PNG verificada en esa carpeta conocida."),
        Descriptor(
            "capture.screenshot",
            CaptureSchema(),
            OperationRisks.PrivacySensitive,
            "capture.screenshot.gdi.bmp.hash.v1",
            "Captura el escritorio virtual en un BMP privado y devuelve solo identidad, dimensiones y hash; con folder guarda además una copia PNG verificada en esa carpeta conocida."),
        Descriptor(
            "client.channel.locate",
            Schema(
                [
                    String("client", values: ["discord"]),
                    String("name", maximumUtf8Bytes: 256, nonWhitespace: true),
                ],
                ["client", "name"]),
            OperationRisks.LowReversible,
            "client.channel.locate.quick.switcher.uia.postread.v1",
            "Busca un canal o chat por nombre en el buscador rápido del cliente de escritorio (Discord: Ctrl+K), lee las coincidencias por UI Automation y cierra el buscador si Discord sigue al frente, sin unirse ni abrir nada; si el buscador queda o puede haber quedado abierto, o Discord queda a la vista, el resultado dice que hubo efecto.",
            // The locate is a post-read: it joins and opens nothing, so it verifies by its result
            // (the matches read from the switcher), not by an observed external mutation.
            requiresObservedEffect: false,
            effects: [WindowInput()]),
        // BAXY Renew cu (C14): the person's own microphone inside the chat client, by its own mute button (Discord's
        // «Silenciar»), read back by UI Automation; Windows' microphone is audio.microphone.mute.
        Descriptor(
            "client.microphone.set",
            Schema(
                [
                    String("client", values: ["discord"]),
                    Boolean("muted"),
                ],
                ["client", "muted"]),
            OperationRisks.LowReversible,
            "client.microphone.set.discord.uia.toggle.postread.v1",
            "Silencia o activa el micrófono propio de la persona dentro del cliente de escritorio (Discord: su botón «Silenciar») por UI Automation y relee su estado; no toca el micrófono de Windows ni une a ninguna llamada.",
            effects: [WindowInput()]),
        Descriptor(
            "clipboard.copy",
            EmptySchema(),
            OperationRisks.PrivacySensitive,
            "clipboard.copy.win32.foreground.sendinput.sequence.postread.v1",
            "Copia la selección del control enfocado y verifica foco estable, aceptación completa de Ctrl+C y un cambio real del portapapeles.",
            effects: [WindowInput()]),
        Descriptor(
            "clipboard.paste",
            EmptySchema(),
            OperationRisks.PrivacySensitive,
            "clipboard.paste.win32.clipboard.foreground.sendinput.accepted.v1",
            "Pega el contenido actual del portapapeles en el control enfocado y verifica que el portapapeles no esté vacío, que el foco no cambie y que Windows acepte todos los eventos Ctrl+V.",
            effects: [WindowInput()]),
        // BAXY Renew cu (C18): the clipboard pasted into a new document of the application named, opened first.
        Descriptor(
            "clipboard.paste.into",
            Schema([String("appId", maximumUtf8Bytes: 512, nonWhitespace: true)], ["appId"]),
            OperationRisks.PrivacySensitive,
            "clipboard.paste.into.app.open.document.paste.v1",
            "Abre un documento nuevo de la aplicación nombrada (app.open al frente, con documento nuevo) y pega en él el contenido del portapapeles (clipboard.paste); si la aplicación no se abre no pega nada.",
            effects: [WindowInput()]),
        Descriptor(
            "clipboard.read.text",
            Schema([Integer("maxCharacters", 1, 6_000)], []),
            OperationRisks.PrivacySensitive,
            "clipboard.read.text.sequence.secondread.v1",
            "Lee texto privado acotado del portapapeles y exige dos snapshots idénticos; 6.000 caracteres como mucho; truncated dice si se cortó."),
        Descriptor(
            "clipboard.write.text",
            Schema([String("text", maximumLength: 65_536)], ["text"]),
            OperationRisks.PrivacySensitive,
            "clipboard.write.text.sequence.postread.v1",
            "Reemplaza texto del portapapeles y verifica contenido y secuencia mediante postlectura."),
        // Auditoría semántica 2026-09-20 (REOPEN1957 H0459 «cambiá el fondo de
        // pantalla a azul», D11): un color liso o una imagen de una carpeta conocida
        // como fondo de escritorio, verificado por la postlectura del sistema; el
        // recibo guarda el fondo anterior para restaurarlo.
        Descriptor(
            "desktop.wallpaper.set",
            Schema(
                [
                    String("color", types: NullableString, maximumUtf8Bytes: 32),
                    String("folder", types: NullableString, values: ["desktop", "documents", "downloads", "pictures"]),
                    String("name", types: NullableString, maximumUtf8Bytes: 200),
                ],
                []),
            OperationRisks.LowReversible,
            "desktop.wallpaper.set.spi.registry.postread.v1",
            "Cambia el fondo de escritorio a un color liso (#RRGGBB) o a una imagen de una carpeta conocida y verifica la postlectura del sistema; devuelve el fondo anterior; sólo una imagen directa de la carpeta."),
        // Auditoría de los pedidos reales (2026-10-17): cambiar la frecuencia o la resolución del monitor principal.
        Descriptor(
            "display.mode.set",
            Schema(
                [
                    Integer("height", 200, 16_384),
                    Integer("refreshHz", 1, 1_000),
                    Integer("width", 320, 16_384),
                ],
                []),
            OperationRisks.LowReversible,
            "display.mode.set.win32.test.apply.readback.v1",
            "Cambia el modo del monitor principal (resolución, frecuencia de refresco o ambas) a uno que su controlador lista: lo prueba con CDS_TEST, lo aplica, relee el modo y, si no es el pedido, vuelve al anterior y lo relee; con sólo la resolución mantiene la frecuencia si ese modo la lista, si no toma la más alta listada.",
            effects: [SystemChange()]),
        Descriptor(
            "display.status",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "display.status.windows.display.devices.read.v1",
            "Lee los monitores conectados (cantidad, resolución y frecuencia de refresco) mediante la API de pantalla de Windows; sin efecto."),
        // Auditoría semántica 2026-09-20 (REOPEN1957 H0188 «Haz un powerpoint hablando
        // de amor de 6 diapositivas», D11): la presentación se escribe como paquete
        // Open XML, una diapositiva por entrada («Título\nviñeta\nviñeta»), en una
        // carpeta conocida; la postlectura cuenta las diapositivas del paquete.
        Descriptor(
            "document.presentation.create",
            Schema(
                [
                    String("folder", types: NullableString, values: ["desktop", "documents", "downloads"]),
                    new OperationArgumentProperty(
                        "slides",
                        OperationJsonType.Array,
                        itemTypes: OperationJsonType.String,
                        maximumItems: 12,
                        itemMaximumUtf8Bytes: 1_024,
                        itemNonWhitespace: true),
                    String("title", maximumUtf8Bytes: 200, nonWhitespace: true),
                ],
                ["slides", "title"]),
            OperationRisks.LowReversible,
            "document.presentation.create.openxml.slidecount.postread.v1",
            "Crea una presentación .pptx con el título dado y de 1 a 12 diapositivas, una por entrada (primera línea título, hasta 8 viñetas; las demás líneas se omiten y el resultado las cuenta) en una carpeta conocida y verifica cuántas diapositivas tiene el paquete escrito."),
        Descriptor(
            "email.latest.read",
            EmptySchema(),
            OperationRisks.PrivacySensitive,
            "email.latest.read.outlook.mapi.snapshot.v1",
            "Lee el mensaje mas reciente del buzon Outlook autenticado y verifica su identidad MAPI; sólo mira los 100 elementos más nuevos de la Bandeja de entrada predeterminada; un cuerpo de más de 6.000 caracteres se corta (bodyTruncated)."),
        Descriptor(
            "email.latest.reply",
            // Renew al máximo (w8): expectedMessageId (the messageId email.latest.read gave) binds the reply, and the
            // person's yes, to one mail; one that is no longer the newest sends nothing (MicrosoftAccountAdapter).
            Schema(
                [
                    String("expectedMessageId", types: NullableString, maximumUtf8Bytes: 64),
                    String("text", maximumUtf8Bytes: 16_384, nonWhitespace: true),
                ],
                ["text"]),
            OperationRisks.ExternalCommunication,
            "email.latest.reply.outlook.sent.postread.v1",
            "Responde al mensaje mas reciente de Outlook (el de expectedMessageId, el messageId que dio email.latest.read; si ya no es el más nuevo no envía nada y dice cuál lo es) y verifica la copia enviada por contenido y hora; sólo mira los 100 elementos más nuevos de la Bandeja de entrada predeterminada; el resultado trae el cuerpo del correo respondido, cortado a 6.000 caracteres (bodyTruncated)."),
        // Fase 7 (D4, 2026-09-20): correo a una dirección libre desde el perfil clásico de
        // Outlook del dueño, confirmado en modo normal; la copia en Elementos enviados
        // (destinatario, texto, hora) es la prueba. Sin Outlook clásico se dice el límite.
        Descriptor(
            "email.send",
            Schema(
                [
                    String("subject", types: NullableString, maximumUtf8Bytes: 200),
                    String("text", maximumUtf8Bytes: 16_384, nonWhitespace: true),
                    String("to", maximumUtf8Bytes: 254, nonWhitespace: true),
                ],
                ["text", "to"]),
            OperationRisks.ExternalCommunication,
            "email.send.outlook.sent.postread.v1",
            "Envía un correo a la dirección indicada (asunto opcional; sin asunto, el comienzo del texto) desde el perfil clásico de Outlook del dueño y verifica la copia en Elementos enviados por destinatario, texto y hora; sin asunto usa la primera línea (de más de 78 caracteres, se corta a 75 y «…»)."),
        // Auditoría semántica 2026-09-20 (REOPEN1957 H0542 «… comprímela y luego abre
        // el zip», D11): comprimir un archivo o carpeta de una carpeta conocida a un
        // zip al lado, verificado abriendo el zip; y abrir por nombre un archivo seguro
        // de una carpeta conocida, verificado por la ventana o el proceso que aparece.
        Descriptor(
            "file.compress",
            Schema(
                [
                    String("folder", values: ["desktop", "documents", "downloads", "pictures"]),
                    String("name", maximumUtf8Bytes: 200, nonWhitespace: true),
                ],
                ["folder", "name"]),
            OperationRisks.LowReversible,
            "file.compress.zip.archive.postread.v1",
            "Comprime un archivo o una carpeta de una carpeta conocida en un zip con el mismo nombre al lado y verifica que el zip existe y tiene entradas; sólo un elemento directo de la carpeta."),
        // BAXY Renew, herramientas de agente (2026-10-15): editar, buscar, leer y escribir archivos como las
        // herramientas edit/find/read/write de los agentes (OpenCode, OpenClaw, Claude Code). file.find sustituye a
        // filesystem.known.list y .search; file.read a document.text.read y document.pdf.read; file.write a
        // filesystem.write.text y filesystem.sandbox.append.named. Lo que reemplazan file.write y file.edit va antes
        // a la Papelera de reciclaje: el cambio queda recuperable y no pide confirmación (decisión 8 del dueño).
        Descriptor(
            "file.edit",
            Schema(
                [
                    String("fileName", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                    String("folder", values: ["all_known", "desktop", "documents", "downloads", "home"]),
                    String("newText", maximumUtf8Bytes: 65_536),
                    String("oldText", maximumUtf8Bytes: 65_536),
                    Boolean("replaceAll"),
                    String("subdirectory", maximumUtf8Bytes: 512, nonWhitespace: true),
                ],
                ["fileName", "folder", "newText", "oldText"]),
            OperationRisks.LowReversible,
            "file.edit.windows.known.exact.replace.recycle.postread.v1",
            "Reemplaza un texto exacto en un archivo de texto de hasta 4 MiB nombrado de forma única en una carpeta conocida (una vez, o todas si se pide; si aparece más de una vez sin pedirlo no cambia nada y dice cuántas), conserva su codificación, envía la versión anterior a la Papelera de reciclaje y verifica releyendo el archivo; con un nombre que no aparece o aparece varias veces da hasta 5 candidatos (candidatesTruncated); busca el nombre hasta 12 niveles y 8 segundos, y si el plazo corta la búsqueda no cambia nada y dice el archivo que vio (known_file_search_incomplete), que se edita nombrando su ruta."),
        Descriptor(
            "file.find",
            Schema(
                [
                    String("content", maximumUtf8Bytes: 512, nonWhitespace: true),
                    String("folder", values: ["all_known", "desktop", "documents", "downloads", "home"]),
                    Integer("limit", 1, 100),
                    String("order", values: ["name", "recent", "size"]),
                    String("query", maximumUtf8Bytes: 512, nonWhitespace: true),
                    String("subdirectory", maximumUtf8Bytes: 512, nonWhitespace: true),
                ],
                ["folder"]),
            OperationRisks.ReadOnly,
            "file.find.windows.known.name.content.bounded.v1",
            "Lista el primer nivel de una carpeta conocida de Windows, o busca bajo ella archivos por nombre (parte del nombre o patrón con * y ?) o por un texto dentro de sus archivos de texto, de forma acotada (20 resultados por defecto, 50 en el listado del primer nivel (sin ocultos ni de sistema), y 100 como mucho; hasta 12 niveles y 8 segundos, y una búsqueda cortada por el plazo lo dice; por contenido, mira hasta 2000 archivos de cualquier tipo y sólo lee los de texto de hasta 1 MiB, y para en el límite de aciertos y sólo ordena esos) y sin seguir puntos de reanálisis; devuelve cada archivo con su ruta relativa a la carpeta, nunca la absoluta; sin efecto; una vista muestra 20 como mucho (lo marca y no alcanza lo que pasa de ahí)."),
        Descriptor(
            "file.open",
            Schema(
                [
                    // cu-v3-abrir-archivo: the installed application to open it with (as app.open's appId); without it,
                    // the default one.
                    String("application", maximumUtf8Bytes: 512, nonWhitespace: true),
                    String("folder", values: ["desktop", "documents", "downloads", "home", "pictures"]),
                    // The person asked to see it (the model sets it, as app.open's): the opened application keeps the
                    // front; without it the file opens behind the person's window.
                    Boolean("foreground"),
                    String("name", maximumUtf8Bytes: 200, nonWhitespace: true),
                ],
                ["folder", "name"]),
            OperationRisks.LowReversible,
            "file.open.shell.window.process.postread.v1",
            "Abre por nombre un archivo seguro de una carpeta conocida con su aplicación predeterminada, o con la aplicación instalada que se nombre, y verifica la ventana o el proceso que aparece. Un archivo que no está en esa carpeta no se abre: el recibo dice dónde se vio uno con ese nombre exacto; dónde se vio busca 4 niveles en escritorio, documentos, descargas e imágenes, 5 lugares y 3 segundos como mucho (searchComplete); sólo abre documentos, imágenes, audio, vídeo y zip o 7z.",
            // Ronda final 8: with an application named or foreground it raises a window, and without them the default
            // application may be one that already runs and takes the file in the person's window, or a packaged app Windows
            // activates by itself.
            effects: [WindowInput()]),
        Descriptor(
            "file.read",
            Schema(
                [
                    String("fileName", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                    String("folder", values: ["all_known", "desktop", "documents", "downloads", "home"]),
                    Integer("maximumCharacters", 200, 200_000),
                    Integer("offset", 0, 100_000_000),
                    String("subdirectory", maximumUtf8Bytes: 512, nonWhitespace: true),
                ],
                ["fileName", "folder"]),
            OperationRisks.ReadOnly,
            "file.read.windows.known.text.pdf.paged.v1",
            "Localiza un archivo nombrado de forma única (por su nombre o su ruta relativa) en una carpeta conocida de Windows y devuelve una página de su texto desde offset: un archivo de texto en su codificación, o el texto que ya contiene un PDF (pypdf, sin OCR), hasta 4 MiB de texto o 64 MiB de PDF; dice qué tipo leyó, el largo total y si queda más; sin efecto; con un nombre que no aparece o aparece varias veces da hasta 5 candidatos (candidatesTruncated); busca el nombre hasta 12 niveles y 8 segundos, y una búsqueda cortada por el plazo lo dice; la extracción de un PDF para a los 90 segundos.",
            // Al máximo, flujos: PdfExtractionTimeout: a PDF's text is extracted for up to 90 s.
            budget: TimeSpan.FromSeconds(90)),
        Descriptor(
            "file.write",
            Schema(
                [
                    Boolean("append"),
                    String("expectedSha256", types: NullableString, maximumLength: 64),
                    // Owner decision 2026-09-13 (DECISIONES_DUENO, point 2): a known
                    // folder may be the root instead of the sandbox; an existing file
                    // there is never overwritten without its current hash.
                    String("folder", values: ["desktop", "documents", "downloads", "home"]),
                    String("relativePath", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                    String("text", maximumUtf8Bytes: 1_048_576),
                ],
                ["relativePath", "text"]),
            OperationRisks.LowReversible,
            "file.write.sandbox.known.cas.recycle.hash.v1",
            "Escribe UTF-8 atómicamente en el sandbox o en una carpeta conocida; reemplazar exige el SHA-256 exacto observado antes y envía la versión anterior a la Papelera de reciclaje; append añade al final conservando lo que había; verifica el hash releído; append rechaza un archivo de más de 10 MiB; el texto, 1 MiB como mucho."),
        Descriptor(
            "filesystem.copy",
            FilesystemTransferSchema(),
            OperationRisks.LowReversible,
            "filesystem.copy.sandbox.hash.postread.v1",
            "Copia un archivo identificado dentro del sandbox y verifica su hash en destino."),
        Descriptor(
            "filesystem.create.directory",
            Schema(
                [
                    // Owner decision 2026-09-13 (DECISIONES_DUENO, point 2): a known
                    // folder may be the root instead of the sandbox.
                    String("folder", values: ["desktop", "documents", "downloads", "home"]),
                    String("relativePath", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                ],
                ["relativePath"]),
            OperationRisks.LowReversible,
            "filesystem.create.directory.sandbox.postread.v1",
            "Crea un directorio relativo confinado al sandbox o a una carpeta conocida (escritorio, documentos, descargas, la carpeta del usuario) y verifica su identidad; una ruta absoluta dentro de esa carpeta vale como su ruta relativa."),
        // Auditoría semántica 2026-09-20 (REOPEN1957 H0701 «Dime cuantos archivos .py
        // hay en el directorio actual», D24): el directorio actual es la carpeta del
        // Explorador en primer plano; sin Explorador delante falla (no_explorer_in_front).
        // Holdout v6 V6E027: sin ninguno delante, el único abierto («la carpeta que tengo abierta en el explorer»).
        Descriptor(
            "filesystem.explorer.count",
            Schema(
                [
                    String("extension", maximumUtf8Bytes: 16, nonWhitespace: true),
                    String("folder", values: ["desktop", "documents", "downloads", "home", "pictures"]),
                    // Holdout v5 V5E034/V5E044: «¿cuántos pdf hay en BAXY-bench\facturas?» had no call.
                    String("subdirectory", maximumUtf8Bytes: 512, nonWhitespace: true),
                ],
                ["extension"]),
            OperationRisks.ReadOnly,
            "filesystem.explorer.count.foreground.folder.toplevel.v1",
            "Cuenta los archivos de primer nivel con la extensión dada en la carpeta conocida que se nombra (o en una subcarpeta suya) o, sin ella, en la que muestra la ventana del Explorador en primer plano o, sin ninguna delante, la única abierta (si no, falla), y nombra esa carpeta sin revelar su ruta; no cuenta los archivos ocultos ni los de sistema."),
        Descriptor(
            "filesystem.file.open.latest",
            Schema([String("folder", values: ["desktop", "documents", "downloads", "pictures"])], ["folder"]),
            OperationRisks.LowReversible,
            "filesystem.file.open.latest.windows.shell.process.postread.v1",
            "Abre el archivo seguro modificado mas recientemente de una carpeta conocida y lo da por abierto sólo con una ventana nueva (o del proceso lanzado) cuyo título lo nombra; si no, dice que no se pudo verificar; sólo mira el primer nivel de la carpeta, sin ocultos ni de sistema.",
            // It opens as file.open does.
            effects: [WindowInput()]),
        Descriptor(
            "filesystem.folder.open",
            Schema(
                [
                    String("folder", values: ["desktop", "documents", "downloads", "home", "pictures"]),
                    String("subdirectory", maximumUtf8Bytes: 512, nonWhitespace: true),
                ],
                ["folder"]),
            OperationRisks.LowReversible,
            "filesystem.folder.open.windows.shell.postread.v1",
            "Abre una carpeta conocida de Windows, o una subcarpeta suya, y verifica la ventana de Explorer observada.",
            // Ronda final 14: it starts or raises an Explorer window in front.
            effects: [WindowInput()]),
        Descriptor(
            "filesystem.known.duplicates",
            Schema(
                [
                    String("folder", values: ["downloads"]),
                    Integer("limit", 1, 100),
                ],
                ["folder"]),
            OperationRisks.ReadOnly,
            "filesystem.known.duplicates.windows.size.hash.snapshot.v1",
            "Busca grupos de archivos duplicados en Descargas mediante tamaño y SHA-256 sin modificarlos (20 grupos por defecto; calcula el hash de 10.000 archivos candidatos como mucho y lo dice si corta); busca hasta 12 niveles; una vista muestra 20 como mucho (lo marca y no alcanza lo que pasa de ahí)."),
        Descriptor(
            "filesystem.known.trash.named",
            Schema(
                [
                    String("fileName", maximumUtf8Bytes: 512, nonWhitespace: true),
                    String("folder", values: ["all_known", "desktop", "documents", "downloads", "home"]),
                    String("subdirectory", maximumUtf8Bytes: 512, nonWhitespace: true),
                ],
                ["fileName", "folder"]),
            OperationRisks.RecoverableDelete,
            "filesystem.known.trash.named.windows.absence.v1",
            "Resuelve un archivo nombrado de forma única y lo envía a la Papelera de reciclaje de Windows, de donde la persona lo recupera, y verifica que ya no está en su carpeta; con un nombre repetido da hasta 5 candidatos (candidatesTruncated); busca el nombre hasta 12 niveles."),
        Descriptor(
            "filesystem.list",
            Schema(
                [
                    Integer("limit", 1, 100),
                    String("relativeDirectory", maximumUtf8Bytes: 1_024),
                ],
                []),
            OperationRisks.ReadOnly,
            "filesystem.list.sandbox.identities.v1",
            "Lista entradas acotadas del sandbox y emite identificadores opacos de corta vida; 50 por defecto (totalCount); los ids duran 5 minutos; una vista muestra 20 como mucho (lo marca y no alcanza lo que pasa de ahí)."),
        Descriptor(
            "filesystem.move",
            FilesystemTransferSchema(),
            OperationRisks.LowReversible,
            "filesystem.move.sandbox.hash.absence.v1",
            "Mueve un archivo identificado y verifica hash de destino y ausencia de origen."),
        Descriptor(
            "filesystem.read.text",
            Schema(
                [
                    Integer("maximumBytes", 1, 1_048_576),
                    String("resourceId", maximumLength: 35, nonWhitespace: true),
                ],
                ["resourceId"]),
            OperationRisks.ReadOnly,
            "filesystem.read.text.sandbox.hash.v1",
            "Lee UTF-8 acotado desde una identidad revalidada y devuelve su hash."),
        Descriptor(
            "filesystem.sandbox.diff.named",
            Schema(
                [
                    String("leftFileName", maximumUtf8Bytes: 512, nonWhitespace: true),
                    String("rightFileName", maximumUtf8Bytes: 512, nonWhitespace: true),
                ],
                ["leftFileName", "rightFileName"]),
            OperationRisks.ReadOnly,
            "filesystem.sandbox.diff.named.hash.snapshot.v1",
            "Compara dos archivos de texto del sandbox nombrados por su nombre de archivo exacto (único en el sandbox) y devuelve hashes y líneas diferentes; archivos de hasta 2 MiB; una vista muestra 20 números de línea cambiados (changedLineCount es el total); compara las líneas por posición."),
        Descriptor(
            "filesystem.sandbox.move.named",
            Schema(
                [
                    // Holdout v5 V5E032/V5E040: a file of the person's (folder, subdirectory) moved or copied by name.
                    Boolean("copy"),
                    String("destinationRelativePath", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                    String("folder", values: ["desktop", "documents", "downloads", "home"]),
                    String("sourceFileName", maximumUtf8Bytes: 512, nonWhitespace: true),
                    String("subdirectory", maximumUtf8Bytes: 512, nonWhitespace: true),
                ],
                ["destinationRelativePath", "sourceFileName"]),
            OperationRisks.LowReversible,
            "filesystem.sandbox.move.named.hash.absence.v1",
            "Mueve (o copia, con copy) un archivo de nombre único dentro del sandbox o, con folder, en esa carpeta conocida (o en su subcarpeta), sin sobrescribir, y verifica hash y ausencia (o permanencia) del origen."),
        Descriptor(
            "filesystem.search",
            Schema(
                [
                    Integer("limit", 1, 100),
                    String("query", maximumUtf8Bytes: 512, nonWhitespace: true),
                ],
                ["query"]),
            OperationRisks.ReadOnly,
            "filesystem.search.sandbox.identities.v1",
            "Busca nombres dentro del sandbox sin seguir puntos de reanálisis; 50 por defecto (totalCount); una vista muestra 20 como mucho (lo marca y no alcanza lo que pasa de ahí)."),
        Descriptor(
            "game.catalog.list",
            Schema(
                [
                    Integer("limit", 1, 100),
                    String("query", maximumUtf8Bytes: 512),
                ],
                []),
            OperationRisks.ReadOnly,
            "game.catalog.list.steam.snapshot.v1",
            "Lista el catálogo local de Steam mediante una sesión resuelta y acotada; 50 por defecto, una vista muestra 20; totalCount dice cuántos hay."),
        Descriptor(
            "game.entitlement.named",
            Schema(
                [
                    // H0578 «Descarga Fall guys en epic games»: the Epic Games launcher
                    // keeps the same two facts locally (installed manifests, the
                    // authenticated catalog cache); the store the person names picks
                    // the library that is read. Absent, it is Steam as before.
                    String("store", values: ["epic", "steam"]),
                    String("title", maximumUtf8Bytes: 256, nonWhitespace: true),
                ],
                ["title"]),
            OperationRisks.ReadOnly,
            "game.entitlement.named.steam.librarycache.manifest.postread.v1",
            "Comprueba por título si un juego de Steam o de Epic Games figura en la biblioteca autenticada local y si está instalado; no descarga, no compra ni abre diálogos; con Steam sólo resuelve un título idéntico a un único juego (sin contar mayúsculas ni tildes); con Epic toma la primera entrada con ese título."),
            // Whether a game is owned is read on the PC alone (Renew al máximo, B-APP-6): no network effect.
        Descriptor(
            "game.install.cancel",
            Schema([String("appId", maximumLength: 16, nonWhitespace: true)], ["appId"]),
            OperationRisks.WorkLoss,
            "game.install.cancel.steam.postread.v1",
            "Cancela una descarga parcial exacta desde el administrador autenticado de Steam y verifica que dejó de progresar."),
        Descriptor(
            "game.install.cancel.active",
            EmptySchema(),
            OperationRisks.WorkLoss,
            "game.install.cancel.active.steam.all.postread.v1",
            "Cancela las descargas ya empezadas de juegos aún no instalados en Steam y verifica que ninguna siga progresando; una actualización de un juego instalado o una instalación encolada sin bytes no se cancela (steam_downloads_not_covered)."),
        Descriptor(
            "game.install.named",
            // REOPEN1993 grupo S: la tienda nombrada tras el título (Steam o Epic).
            Schema(
                [
                    String("store", types: NullableString, values: ["epic", "steam"]),
                    String("title", maximumUtf8Bytes: 256, nonWhitespace: true),
                ],
                ["title"]),
            OperationRisks.Installation,
            "game.install.named.steam.manifest.postread.v1",
            "Resuelve el título de un juego de Steam (sus manifiestos locales o la búsqueda pública de la tienda; o de Epic Games) a su identidad, abre la instalación por su dirección, confirma el diálogo propio de Steam y verifica la transición del manifiesto local; con Steam sólo resuelve un título idéntico a un único juego (sin contar mayúsculas ni tildes); con Epic toma la primera entrada con ese título."),
        Descriptor(
            "game.install.status",
            Schema([String("appId", maximumLength: 16, nonWhitespace: true)], ["appId"]),
            OperationRisks.ReadOnly,
            "game.install.status.steam.snapshot.v1",
            "Mide el estado y progreso local de una instalación Steam por AppID exacto."),
        Descriptor(
            "game.installed.named",
            Schema(
                [
                    String("provider", values: ["any", "epic", "steam"]),
                    String("title", maximumUtf8Bytes: 256, nonWhitespace: true),
                ],
                ["provider", "title"]),
            OperationRisks.ReadOnly,
            "game.installed.named.steam.epic.manifest.directory.postread.v1",
            "Comprueba por nombre si un juego esta instalado mediante manifiestos de Steam y Epic y verifica que exista su directorio local."),
        Descriptor(
            "game.launch",
            // Renew al máximo (falsedades F001 y F016 del NB, 2026-10-22): el modelo lanzó el único juego instalado
            // por «Doom Eternal» y por «Fortnite». El título que pidió la persona va con el AppID y el proveedor lo
            // compara con el nombre del manifiesto antes de lanzar (game_title_required, game_title_mismatch).
            Schema(
                [
                    String("appId", maximumLength: 16, nonWhitespace: true),
                    String("title", maximumUtf8Bytes: 256, nonWhitespace: true),
                ],
                ["appId", "title"]),
            OperationRisks.LowReversible,
            "game.launch.steam.process.postread.v1",
            "Inicia un AppID instalado en este PC cuyo nombre es el juego que pidió la persona y verifica la identidad del proceso lanzado.",
            // It clicks «Jugar» in the dialog Steam opens for the game's address (SteamLocalAdapter.LaunchAsync); what Steam
            // publishes by itself (its «playing») is not the person's data leaving through BAXY (owner, 2026-10-16).
            effects: [WindowInput()]),
        // BAXY Renew cu (C04 variante, C05): los lugares propios de la tienda de juegos como operaciones con nombre: su
        // búsqueda con lo que se busca y la página de un juego por su título. Son app.open con ese lugar, al frente.
        Descriptor(
            "game.store.page",
            Schema([String("title", maximumUtf8Bytes: 128, nonWhitespace: true)], ["title"]),
            OperationRisks.LowReversible,
            "game.store.page.app.open.place.v1",
            "Abre en Steam, al frente, la página de la tienda del juego que lleva ese título (lo resuelve su búsqueda pública) y dice qué juego es; mirar la ventana dice si llegó.",
            // Auditoría del núcleo 2026-10-23: el título sale a la búsqueda pública de la tienda.
            effects: [WindowInput(), Network()]),
        Descriptor(
            "game.store.search",
            Schema([String("query", maximumUtf8Bytes: 128, nonWhitespace: true)], ["query"]),
            OperationRisks.LowReversible,
            "game.store.search.app.open.place.v1",
            "Abre en Steam, al frente, la búsqueda de su tienda con lo que se busca (un título, un tema o un tipo de juego); mirar la ventana dice qué resultados muestra.",
            // Auditoría del núcleo 2026-10-23: lo que se busca sale a la tienda de Steam.
            effects: [WindowInput(), Network()]),
        // Auditoría semántica 2026-09-20 (REOPEN1993, grupo S): «Desinstala Worms
        // Rumble en Steam» es una desinstalación real (encargo imp-steam: por la
        // dirección del dato y el diálogo propio de Steam, ya no por su consola),
        // verificada por el manifiesto local; pierde lo instalado, así que confirma.
        Descriptor(
            "game.uninstall.named",
            Schema(
                [
                    String("store", types: NullableString, values: ["epic", "steam"]),
                    String("title", maximumUtf8Bytes: 256, nonWhitespace: true),
                ],
                ["title"]),
            OperationRisks.WorkLoss,
            "game.uninstall.named.steam.manifest.absence.postread.v1",
            "Resuelve un título instalado de Steam a su AppID, abre su desinstalación por su dirección, confirma el diálogo propio de Steam y verifica que el manifiesto local ya no lo declare instalado; sólo resuelve un título idéntico a un único juego (sin contar mayúsculas ni tildes)."),
        Descriptor(
            "input.key.press",
            Schema([
                // Goal v3 punto 2: Enter o Espacio sobre el «Sí» enfocado de un aviso de
                // sobrescritura pisa el archivo igual que el clic; el modelo lo declara desde
                // la vista (su significado va en el argumento, tool_descriptions.en) y
                // RiskPolicy lo confirma.
                String("consequence", types: NullableString, values: ["overwrite"]),
                String("key", values:
                [
                    "alt_tab", "arrow_down", "arrow_left", "arrow_right", "arrow_up",
                    // ctrl_l enfoca la barra de direcciones de cualquier navegador.
                    // Hace falta para el vídeo: el árbol de accesibilidad de Chrome
                    // devuelve un solo nodo y el OCR sólo ve la URL escrita, de modo
                    // que no hay etiqueta que pulsar. Con ella, ir a una dirección es
                    // encadenar lo que ya existe —enfocar, escribir, Enter— en vez de
                    // añadir una herramienta.
                    // Motor de computer use (CONTRATO_VISTA_ACCION.md §2): los atajos
                    // que una persona usa en cualquier aplicación —seleccionar todo,
                    // copiar, buscar, paleta de comandos, pestaña nueva, cerrar
                    // pestaña, deshacer, recargar—. Ctrl+W cierra la pestaña, pero en el
                    // Explorador, en muchas aplicaciones y en la última pestaña de un
                    // navegador cierra la ventana: RiskPolicy lo confirma (auditoría
                    // final 2, fila 9).
                    // Goal v3 punto 2: guardar, guardar como, abrir, reemplazar,
                    // cortar, la barra de menús (F10) y el menú contextual del
                    // control enfocado (Shift+F10); ninguno cierra nada.
                    // Holdout v5 V5E023: Ctrl+End and Ctrl+Home move the caret to the end or start of the whole text
                    // («agrega al final» in a Notepad just opened, its caret at 0); they only move it, so never ask.
                    "backspace", "context_menu", "control", "ctrl_a", "ctrl_c", "ctrl_end", "ctrl_f", "ctrl_h",
                    "ctrl_home", "ctrl_k", "ctrl_l", "ctrl_o", "ctrl_s", "ctrl_shift_escape", "ctrl_shift_s", "ctrl_t",
                    "ctrl_v", "ctrl_w", "ctrl_x", "ctrl_z", "delete", "end", "enter", "escape", "f10", "f5", "home",
                    "page_down", "page_up", "shift", "shift_f10", "space", "tab", "win",
                ]),
                // Revisión de V (H1): lo que Enter o Espacio pulsan según la vista del paso (el control
                // enfocado o, desde un campo, el resultado elegido de su lista): lo declara el modelo y
                // RiskPolicy lo juzga como la etiqueta de un clic.
                String("onto", types: NullableString, maximumUtf8Bytes: 256),
                // El modelo declara cuándo Enter cae sobre un compositor de
                // mensajes con texto: esa pulsación llega a una persona y el
                // Kernel la confirma en modo normal (§2.1). Suprimir pregunta
                // salvo que el paso declare que el teclado está en un campo de
                // texto (text_field): fuera de uno borra lo seleccionado. Revisión
                // 2026-10-22 (K-2): Enter o Espacio sin target ni onto no declaran
                // dónde caen y preguntan, salvo que el prevuelo del Core lea que la
                // ventana destino no es de mensajería ni consola (K-2 refinada);
                // sobre text_field van directos.
                String("target", types: NullableString, values: ["message_composer", "text_field"]),
                // La ventana mirada (el número que dio la vista): la tecla va sólo
                // a ella; si no está delante y no se la puede traer, nada se envía.
                Integer("window", 1, uint.MaxValue, types: NullableInteger),
            ], ["key"]),
            OperationRisks.LowReversible,
            "input.key.press.win32.sendinput.accepted.v1",
            "Presiona una tecla o una combinación (Ctrl+A/C/F/H/K/L/O/S/T/V/W/X/Z, Ctrl+Inicio/Fin, Ctrl+Shift+S, Ctrl+Shift+Escape, F5, F10, Shift+F10) en la ventana enfocada y verifica que Windows aceptó todos los eventos SendInput; Ctrl+W, que puede cerrar una ventana, pide confirmación, y con target message_composer la pulsación de Enter se trata como un envío.",
            effects: [WindowInput()]),
        Descriptor(
            "input.keyboard.layout",
            Schema([String("language", values: ["spanish"])], ["language"]),
            OperationRisks.LowReversible,
            "input.keyboard.layout.win32.foreground.postread.v1",
            "Activa el teclado español en la ventana enfocada y verifica el idioma de entrada de su hilo mediante Win32.",
            // Audit 2026-10-15, App H1: it posts WM_INPUTLANGCHANGEREQUEST to the focused window.
            effects: [WindowInput()]),
        Descriptor(
            "input.keyboard.open",
            EmptySchema(),
            OperationRisks.LowReversible,
            "input.keyboard.open.window.visible.postread.v1",
            "Abre el teclado en pantalla de Windows y verifica su proceso y ventana visible sin quitar el foco al control de destino."),
        Descriptor(
            "input.keyboard.status",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "input.keyboard.status.win32.foreground.read.v1",
            "Lee y verifica el idioma de entrada del hilo de la ventana enfocada mediante Win32."),
        Descriptor(
            "input.pointer.control",
            Schema([String("action", values: ["click", "move_center", "scroll_down"])], ["action"]),
            OperationRisks.LowReversible,
            "input.pointer.control.win32.postread.v1",
            "Mueve el puntero al centro, hace clic en su posición actual o desplaza hacia abajo y verifica el recibo Win32.",
            effects: [WindowInput()]),
        // Motor de computer use (CONTRATO_VISTA_ACCION.md §2): desplaza la ventana
        // en primer plano por pasos de rueda y sólo cuenta el desplazamiento si la
        // superficie cambió; un panel ya al fondo no cambia y se dice.
        Descriptor(
            "input.scroll",
            Schema(
                [
                    Integer("amount", 1, 10),
                    String("direction", values: ["down", "up"]),
                    // Un panel concreto de la última vista (una lista, una conversación):
                    // se desplaza ese control y no el centro de la ventana.
                    Integer("index", 0, VisibleViewNumbering.HighestIndex, types: NullableInteger),
                    // Goal v3 punto 2 (revelar): el elemento con este nombre que la
                    // ventana mirada tiene fuera de vista se trae a la vista por
                    // UI Automation, sin rueda ni puntero; la prueba es verlo.
                    String("label", types: NullableString, maximumUtf8Bytes: 256),
                    // La ventana mirada (el número que dio la vista sobre la que se
                    // decidió): la vista ya no la trae al frente, así que la rueda
                    // la trae ella; si Windows no se la da, no se mueve nada.
                    Integer("window", 1, uint.MaxValue, types: NullableInteger),
                ],
                ["amount", "direction"]),
            OperationRisks.LowReversible,
            "input.scroll.win32.wheel.surface.postread.v1",
            "Desplaza la ventana en primer plano, o el control de la última vista que nombra su índice, hacia arriba o hacia abajo la cantidad de pasos de rueda pedida y verifica que la superficie visible cambió; con label trae a la vista ese elemento de la ventana nombrada sin rueda ni puntero y verifica que se ve.",
            effects: [WindowInput()]),
        Descriptor(
            "input.select.all",
            EmptySchema(),
            OperationRisks.LowReversible,
            "input.select.all.focused.uia.postread.v1",
            "Selecciona todo en el control enfocado de la ventana activa y verifica la seleccion mediante UI Automation.",
            effects: [WindowInput()]),
        Descriptor(
            "input.text.type",
            Schema(
                [
                    // Revisión de combos-galerías (hallazgo 1): el texto sólo se elige
                    // como una entrada de la propia lista del campo (un ComboBox), por
                    // patrón; si la lista no tiene una entrada así, no cambia nada y
                    // nunca se escribe como texto libre.
                    Boolean("entry", types: NullableBoolean),
                    // El campo de la última vista que recibe el texto (goal v3,
                    // punto 0): se le entrega sin teclado ni primer plano
                    // (SetValue o mensajes a su ventana) cuando lo acepta.
                    Integer("index", 0, VisibleViewNumbering.HighestIndex, types: NullableInteger),
                    // Poner el campo en ese valor: su contenido se reemplaza (nunca
                    // en un documento ni en una contraseña) y la prueba es el valor
                    // releído; sin el campo mismo, por teclado no se envía nada.
                    Boolean("replace", types: NullableBoolean),
                    String("text", maximumUtf8Bytes: 8_192, nonWhitespace: true),
                    // La ventana mirada: el texto va dirigido sólo a ella (hwnd,
                    // proceso y hora de creación); por teclado, sólo mientras ella
                    // está delante, y si deja de estarlo, se para. Con o sin ella, un
                    // texto no lleva caracteres de control: un salto de línea es una
                    // tecla (input.key.press).
                    Integer("window", 1, uint.MaxValue, types: NullableInteger),
                ],
                ["text"]),
            OperationRisks.PrivacySensitive,
            "input.text.type.win32.sendinput.accepted.v1",
            "Escribe texto Unicode literal, sin saltos de línea ni tabuladores, en el control enfocado (o en el campo de la vista que nombra index) y verifica que Windows aceptó cada evento SendInput; como mucho 4.096 caracteres, sin saltos de línea ni tabuladores; si no, se rechaza y no se escribe nada.",
            effects: [WindowInput()]),
        Descriptor(
            "input.visible.click",
            // El clic por el índice de la vista, o por la identidad que dio un clic, cuando la
            // etiqueta se repite; la etiqueta sigue siendo obligatoria, debe nombrar ese mismo
            // control y es lo que el revisor ve.
            Schema(
                [
                    // Goal v3 punto 2: lo que el clic consuma y no se deshace según la
                    // vista donde se decidió («¿Desea reemplazarlo?» → «Sí»): overwrite
                    // pisa un archivo que ya existe y RiskPolicy lo confirma.
                    // Goal v3 punto 0, arreglo 3 (ráfaga compuesta): el resultado exacto
                    // que la búsqueda elige; RiskPolicy lo lee como la etiqueta (un canal
                    // de voz pide confirmación ligada a esta invocación).
                    String("choose", types: NullableString, maximumUtf8Bytes: 256),
                    String("consequence", types: NullableString, values: ["overwrite"]),
                    String("controlId", types: NullableString, maximumLength: 128),
                    Integer("index", 0, VisibleViewNumbering.HighestIndex, types: NullableInteger),
                    String("label", maximumUtf8Bytes: 256, nonWhitespace: true),
                    // Goal v3 B3 (órdenes en menús cerrados): cómo se pulsa el control de la
                    // vista, sólo por su identidad y sin puntero. open: sólo su
                    // ExpandCollapse (la flecha de un botón dividido, un desplegable),
                    // nunca su Invoke; menu: su menú contextual (ShowContextMenu o
                    // WM_CONTEXTMENU); double: doble clic por mensaje. Sin él, el clic
                    // de siempre. Los mismos guards de etiqueta y confirmación.
                    String("manner", types: NullableString, values: ["double", "menu", "open"]),
                    // Goal v3 punto 0, arreglo 3 (ráfaga compuesta): el destino que se
                    // escribe en lo que el clic abre y cuyo resultado se elige por su
                    // nombre, en una sola ráfaga dentro de una pausa de la persona.
                    String("search", types: NullableString, maximumUtf8Bytes: 256),
                    // La ventana mirada (el número que dio la vista sobre la que se
                    // decidió): el clic la trae al frente y actúa sólo en ella; si
                    // Windows no se la da, no se pulsa nada.
                    Integer("window", 1, uint.MaxValue, types: NullableInteger),
                ],
                ["label"]),
            OperationRisks.ExternalCommunication,
            "input.visible.click.windows.uia.invoke.postread.v2",
            "Invoca un único control visible por etiqueta, o por el índice de la vista o la identidad que dio un clic, en la ventana nombrada o, sin ella, en la de la última mirada (con índice), en la aplicación recién abierta o en la de delante (UIA, luego OCR, luego el globo de ayuda, y visión sólo si está configurada), nunca en una ventana protegida, y exige postlectura: seleccionado, conmutado, desaparecido o superficie cambiada.",
            effects: [WindowInput()]),
        Descriptor(
            "input.visible.controls",
            // La vista compacta que lee el modelo (ScreenViewProjection): número, tipo,
            // etiqueta y estado de cada control, el texto por zonas, título y proceso,
            // y la espera acotada de una etiqueta que la aplicación aún no dibujó.
            Schema(
                [
                    // La aplicación a mirar, por su nombre exacto (la ventana de su proceso o cuyo
                    // título la nombra); sin ella, la ventana de delante.
                    String("application", types: NullableString, maximumUtf8Bytes: 128),
                    Boolean("includeText", types: NullableBoolean),
                    Integer("limit", 1, VisibleViewNumbering.Cap),
                    // Encargo IMP4: the written lines read from the window's own drawing, each kept by its place (up to
                    // OperationVisibleFacts.ChatLines).
                    Boolean("lines", types: NullableBoolean),
                    // Encargo IMP3: the cut of a look keeps the last entries of the window's tree (a conversation's
                    // newest messages).
                    Boolean("tail", types: NullableBoolean),
                    String("waitForLabel", types: NullableString, maximumUtf8Bytes: 256),
                    // Ronda 21: las palabras de lo que se busca en la ventana; con ellas el corte de los sesenta
                    // guarda un cupo acotado para los controles que las nombran. Sin ellas la vista es la de siempre.
                    new OperationArgumentProperty(
                        "wanted",
                        OperationJsonType.Array | OperationJsonType.Null,
                        itemTypes: OperationJsonType.String,
                        maximumItems: 24,
                        itemMaximumUtf8Bytes: 64,
                        itemNonWhitespace: true),
                ],
                []),
            OperationRisks.ReadOnly,
            "input.visible.controls.windows.uia.snapshot.v2",
            "Vista compacta de una ventana (la de la aplicación nombrada o la de delante): hasta sesenta controles visibles con número, tipo, etiqueta y estado, el texto leído por zonas cuando se pide (includeText) o la ventana no muestra controles, y si no se leyó o se cortó, el título y el proceso; no pulsa ni escribe nada (una ventana minimizada se muestra detrás de la de delante, sin activarla, y la vista lo dice).",
            // Ronda final 25: a look at an application by its name shows its window behind the person's when it is
            // minimized (ShowBehind), and it stays shown.
            effects: [WindowInput(EffectCondition.Named("application"))]),
        Descriptor(
            "media.control",
            Schema(
                [
                    String("action", values: ["next", "pause", "play", "previous", "stop", "toggle"]),
                    String("sourceApp", types: NullableString, maximumUtf8Bytes: 256),
                ],
                ["action"]),
            OperationRisks.LowReversible,
            "media.control.smtc.postread.v1",
            "Controla una sesión SMTC seleccionada y verifica su estado posterior.",
            // BAXY's own player (mpv, by its pipe), then the system's media controls (SMTC), then the YouTube tab of
            // BAXY's browser, which CDP drives by a script run in the page as a user gesture, in a window that holds the
            // person's session: unless sourceApp names another session, which that tab's adapter refuses before any
            // effect (WebBrowserAdapter.ControlYouTubeTabAsync).
            effects:
            [
                WindowInput(
                    EffectCondition.Unnamed("sourceApp"),
                    EffectCondition.Is("sourceApp", YouTubeTabMediaSource)),
            ]),
        Descriptor(
            "media.play.exact",
            Schema(
                [
                    String("provider", values: ["spotify"]),
                    String("title", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                ],
                ["provider", "title"]),
            OperationRisks.ExternalCommunication,
            "media.play.exact.session.postread.v1",
            "Reproduce un resultado musical exacto en una sesión autenticada y verifica now-playing.",
            // Auditoría del núcleo 2026-10-23: el título sale a la búsqueda de Spotify.
            effects: [Network()],
            // Al máximo, flujos: SpotifyDesktopAdapter.CallBudget.
            budget: TimeSpan.FromSeconds(85)),
        Descriptor(
            "media.play.query",
            Schema(
                [
                    String("provider", values: ["spotify"]),
                    String("query", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                ],
                ["provider", "query"]),
            OperationRisks.ExternalCommunication,
            "media.play.query.session.postread.v1",
            "Busca en Spotify y reproduce el primer resultado de su propia búsqueda (o el titulado como la búsqueda, si Spotify muestra uno) y verifica now-playing.",
            // Auditoría del núcleo 2026-10-23: lo que se busca sale a la búsqueda de Spotify.
            effects: [Network()],
            // Al máximo, flujos: SpotifyDesktopAdapter.CallBudget.
            budget: TimeSpan.FromSeconds(85)),
        Descriptor(
            "media.play.youtube",
            Schema([String("query", maximumUtf8Bytes: 1_024, nonWhitespace: true)], ["query"]),
            OperationRisks.ExternalCommunication,
            "media.play.youtube.cdp.video.postread.v1",
            "Busca en YouTube, reproduce un resultado de video y verifica la reproducción: en el navegador propio del producto, el elemento multimedia y que avanza; en el de la persona, que la sesión multimedia del sistema dice que reproduce; con el reproductor propio instalado, sólo el sonido (audioOnly) en una ventana «BAXY YouTube»; en el navegador reproduce el primer vídeo que lista YouTube.",
            // Auditoría del núcleo 2026-10-23: lo que se busca sale a YouTube.
            effects: [Network()]),
        Descriptor(
            "media.seek.relative",
            Schema([Integer("seconds", -3_600, 3_600)], ["seconds"]),
            OperationRisks.LowReversible,
            "media.seek.relative.smtc.timeline.postread.v1",
            "Adelanta o retrocede la sesión SMTC actual y verifica la posición final en su timeline."),
        Descriptor(
            "media.status",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "media.status.smtc.read.v1",
            "Lee la sesión multimedia actual de Windows y devuelve título, artista y estado sin modificarla."),
        Descriptor(
            "memory.correct",
            Schema(
                [
                    ScalarProperty("expectedValue"),
                    String("kind", values: KindValues()),
                    String("retention", values: RetentionValues()),
                    String("selector", maximumUtf8Bytes: 256, nonWhitespace: true),
                    ScalarProperty("value"),
                    Version(),
                ],
                ["retention", "selector", "value", "version"]),
            OperationRisks.LowReversible,
            "memory.correct.protected.postread.v1",
            "Corrige una memoria local mediante comparación y sustitución."),
        Descriptor(
            "memory.disable",
            Schema(
                [Boolean("enabled", constant: false), Version()],
                ["enabled", "version"]),
            OperationRisks.LowReversible,
            "memory.disable.protected.status.v1",
            "Deshabilita nuevas lecturas y escrituras de memoria local."),
        Descriptor(
            "memory.enable",
            Schema(
                [Boolean("enabled", constant: true), Version()],
                ["enabled", "version"]),
            OperationRisks.PrivacySensitive,
            "memory.enable.protected.status.v1",
            "Habilita la memoria privada local."),
        Descriptor(
            "memory.export",
            Schema(
                [
                    String("destination", values: ["documents"]),
                    Boolean("includeSecrets", constant: false),
                    Version(),
                ],
                ["destination", "includeSecrets", "version"]),
            OperationRisks.PrivacySensitive,
            "memory.export.protected.receipt.v1",
            "Prepara una exportación privada local sin secretos."),
        Descriptor(
            "memory.forget",
            Schema(
                [
                    Boolean("confirmationRequired", constant: true),
                    String("scope", values: ["all", "exact", "kind", "topic"]),
                    String("selector", types: NullableString, maximumUtf8Bytes: 256),
                    Version(),
                ],
                ["confirmationRequired", "scope", "selector", "version"]),
            OperationRisks.WorkLoss,
            "memory.forget.protected.absence.v1",
            "Elimina memorias locales del alcance confirmado."),
        Descriptor(
            "memory.list",
            Schema(
                [Integer("limit", 1, 100), Integer("offset", 0, 512), Version()],
                ["limit", "offset", "version"]),
            OperationRisks.ReadOnly,
            "memory.list.protected.page.v1",
            "Lista la memoria local visible, 20 recuerdos como mucho por vista (dice cuántos hay)."),
        Descriptor(
            "memory.recall",
            Schema(
                [
                    String("scope", values: ["all", "exact", "kind"]),
                    String("selector", types: NullableString, maximumUtf8Bytes: 256),
                    Version(),
                ],
                ["scope", "version"]),
            OperationRisks.ReadOnly,
            "memory.recall.protected.records.v1",
            "Recupera memorias locales visibles para la sesión actual; 5 como mucho (dice cuántos hay)."),
        Descriptor(
            "memory.save",
            MemorySaveSchema(["normal", "personal"]),
            OperationRisks.LowReversible,
            "memory.save.protected.postread.v1",
            "Guarda una memoria explícita local no secreta; hasta 512 recuerdos; con la memoria llena, falla."),
        Descriptor(
            "memory.sensitive.save",
            MemorySaveSchema(["secret", "sensitive"]),
            OperationRisks.PrivacySensitive,
            "memory.sensitive.save.protected.postread.v1",
            "Guarda una memoria sensible local; hasta 512 recuerdos; con la memoria llena, falla."),
        Descriptor(
            "memory.session.clear",
            Schema(
                [
                    Boolean("confirmationRequired", constant: false),
                    Boolean("mustNotDeletePersistent", constant: true),
                    String("scope", values: ["session"]),
                    new OperationArgumentProperty("selector", OperationJsonType.Null),
                    Version(),
                ],
                [
                    "confirmationRequired",
                    "mustNotDeletePersistent",
                    "scope",
                    "selector",
                    "version",
                ]),
            OperationRisks.LowReversible,
            "memory.session.clear.protected.scope.v1",
            "Elimina lo recordado con retención de sesión desde que BAXY arrancó (no por conversación: una conversación nueva del panel no empieza otra sesión de memoria); las memorias temporales de 24 h y las permanentes quedan."),
        Descriptor(
            "memory.status",
            Schema([Version()], ["version"]),
            OperationRisks.ReadOnly,
            "memory.status.protected.snapshot.v1",
            "Informa el estado y los límites de la memoria local."),
        Descriptor(
            "message.draft",
            Schema(
                [
                    String("channel", values: ["discord", "whatsapp"]),
                    String("recipient", maximumUtf8Bytes: 512, nonWhitespace: true),
                    String("text", maximumUtf8Bytes: 16_384, nonWhitespace: true),
                ],
                ["channel", "recipient", "text"]),
            OperationRisks.PrivacySensitive,
            "message.draft.client.composer.visible.postread.v1",
            "Abre el chat del destinatario en el cliente de escritorio nombrado (WhatsApp o Discord), deja el mensaje escrito en el cuadro de redacción, lo corrobora en pantalla y se detiene sin enviarlo: la persona lo envía; en WhatsApp, hasta 8 candidatos (candidateCount).",
            effects: [WindowInput()]),
        // Uso real 2026-10-21 (decisión del dueño): «mándale un mensaje» se envía. El mismo envío verificado de
        // message.send.test, al destinatario nombrado; pide el sí en modo normal (RiskPolicy), no en Bypass.
        Descriptor(
            "message.send",
            Schema(
                [
                    String("channel", values: ["discord", "whatsapp"]),
                    String("recipient", maximumUtf8Bytes: 512, nonWhitespace: true),
                    String("text", maximumUtf8Bytes: 16_384, nonWhitespace: true),
                ],
                ["channel", "recipient", "text"]),
            OperationRisks.ExternalCommunication,
            "message.send.client.composer.send.ocr.postread.v1",
            "Abre el chat del destinatario en el cliente de escritorio nombrado (WhatsApp o Discord), escribe el mensaje, pulsa enviar y lee en el chat que salió; en modo normal pide antes el sí de la persona; en WhatsApp, hasta 8 candidatos (candidateCount) cuando el nombre no es exacto.",
            effects: [WindowInput()]),
        Descriptor(
            "message.send.test",
            Schema(
                [
                    String("channel", values: ["discord", "email", "whatsapp"]),
                    String("requestedRecipient", maximumUtf8Bytes: 512, nonWhitespace: true),
                    String("text", maximumUtf8Bytes: 16_384, nonWhitespace: true),
                ],
                ["channel", "requestedRecipient", "text"]),
            OperationRisks.ExternalCommunication,
            "message.send.test.forced.destination.ocr.postread.v1",
            "Decisión del dueño §6 (y §3 del 18-09 para el correo): envío real a sus canales de prueba. El destino se fuerza SIEMPRE al destino de prueba del dueño para ese canal (un chat de WhatsApp, un mensaje directo de Discord o su casilla de correo de pruebas, guardados en sus datos privados), nunca al destinatario nombrado; sin ese destino configurado no envía nada; en WhatsApp/Discord escribe el texto, pulsa enviar y verifica la entrega por OCR; en correo envía por el Outlook del dueño y verifica la copia en Elementos enviados; el recibo guarda el destinatario pedido y el destino real forzado.",
            // Al máximo, flujos: the mail is sent by a script given 90 s.
            budget: TimeSpan.FromSeconds(90)),
        Descriptor(
            "network.dns.status",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "network.dns.status.windows.interfaces.secondread.v1",
            "Lee los servidores DNS de las interfaces activas de Windows y exige dos observaciones coherentes."),
        Descriptor(
            "network.ip.list",
            EmptySchema(),
            // Owner decision 2026-09-13 (DECISIONES_DUENO, point 6): listing the
            // machine's own addresses no longer asks for confirmation.
            OperationRisks.ReadOnly,
            "network.ip.list.windows.unicast.secondread.v1",
            "Enumera direcciones IP unicast activas del equipo y solo devuelve valores presentes en dos observaciones consecutivas, sin exponer nombres de interfaz."),
        Descriptor(
            "network.ping",
            Schema(
                [String("host", maximumUtf8Bytes: 253, nonWhitespace: true)],
                ["host"]),
            OperationRisks.ReadOnly,
            "network.ping.icmp.reply.receipt.v1",
            "Envía un único eco ICMP acotado a un host explícito e informa su recibo, latencia o fallo de resolución.",
            effects: [Network()]),
        Descriptor(
            "network.port.list",
            Schema([Integer("limit", 1, 100)], []),
            OperationRisks.ReadOnly,
            "network.port.list.windows.listeners.secondread.v1",
            "Enumera puertos TCP y UDP locales en escucha y solo devuelve endpoints presentes en dos observaciones consecutivas; 50 por defecto (truncated); una vista muestra 20 como mucho (lo marca y no alcanza lo que pasa de ahí)."),
        Descriptor(
            "network.status",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "network.status.interfaces.secondread.v1",
            "Lee conectividad e interfaces activas sin exponer direcciones, SSID ni nombres locales."),
        Descriptor(
            "note.create",
            Schema(
                [
                    String("content", maximumUtf8Bytes: 65_536),
                    String("title", maximumUtf8Bytes: 512, nonWhitespace: true),
                ],
                ["content", "title"]),
            OperationRisks.LowReversible,
            "note.create.local.reopen.v1",
            "Crea una nota privada local y verifica su relectura; hasta 512 notas, contando las de la papelera; llena, falla."),
        Descriptor(
            "note.list",
            Schema(
                [
                    Integer("limit", 1, 100, types: NullableInteger),
                    Integer("offset", 0, types: NullableInteger),
                    String("scope", types: NullableString, values: ["active", "all", "trashed"]),
                ],
                []),
            OperationRisks.ReadOnly,
            "note.list.local.snapshot.v1",
            "Enumera notas privadas locales activas o enviadas a la papelera; 50 por defecto, pero una vista muestra 20 como mucho; nextOffset sigue (totalCount dice cuántas)."),
        Descriptor(
            "note.read",
            NoteSelectorSchema(),
            OperationRisks.ReadOnly,
            "note.read.local.identity.v1",
            "Lee una nota privada local por su identificador o título exacto."),
        Descriptor(
            "note.restore",
            NoteSelectorSchema(),
            OperationRisks.LowReversible,
            "note.restore.local.postread.v1",
            "Restaura una nota privada local, seleccionada por identificador o título exacto, desde la papelera."),
        Descriptor(
            "note.search",
            Schema(
                [
                    Boolean("includeTrashed"),
                    Integer("limit", 1, 100),
                    String("query", maximumUtf8Bytes: 512, nonWhitespace: true),
                ],
                ["query"]),
            OperationRisks.ReadOnly,
            "note.search.local.reopen.v1",
            "Busca texto en notas locales y verifica por relectura cada resultado acotado; 20 por defecto (totalCount); una vista muestra 20 como mucho (lo marca y no alcanza lo que pasa de ahí)."),
        Descriptor(
            "note.trash",
            NoteSelectorSchema(),
            OperationRisks.RecoverableDelete,
            "note.trash.local.postread.v1",
            "Mueve una nota privada local, seleccionada por identificador o título exacto, a una papelera reversible."),
        Descriptor(
            "note.update",
            Schema(
                [
                    String("content", maximumUtf8Bytes: 65_536),
                    Integer("expectedRevision", 1),
                    String("expectedTitle", maximumUtf8Bytes: 512, nonWhitespace: true),
                    String("noteId", maximumLength: 36, nonWhitespace: true),
                    String("title", maximumUtf8Bytes: 512, nonWhitespace: true),
                ],
                ["content", "expectedRevision", "expectedTitle", "noteId", "title"]),
            OperationRisks.LowReversible,
            "note.update.local.reopen.v1",
            "Reemplaza titulo y contenido de una nota seleccionada por identidad y revision, y verifica su relectura."),
        Descriptor(
            "ocr.read",
            Schema(
                [
                    String("captureId", maximumLength: 128, nonWhitespace: true),
                    String("language", types: NullableString, maximumLength: 32),
                ],
                ["captureId"]),
            OperationRisks.PrivacySensitive,
            "ocr.read.windows.capture.binding.v1",
            "Ejecuta OCR local sobre una captura identificada y un language pack disponible; sólo se guardan las 16 últimas capturas.",
            requiresObservedEffect: false,
            // Al máximo, flujos: CaptureVisionAdapter: the local endpoint has 90 s.
            budget: TimeSpan.FromSeconds(90)),
        Descriptor(
            "office.document.create",
            Schema(
                [
                    String("format", values: ["docx", "xlsx"]),
                    String("title", maximumUtf8Bytes: 512, nonWhitespace: true),
                ],
                ["format", "title"]),
            OperationRisks.LowReversible,
            "office.document.create.adapter.postread.v1",
            "Escribe en este PC un documento de Office mínimo (.docx o .xlsx) con ese título en Documentos\\BAXY, verifica el paquete releído y devuelve su identidad; no usa Office ni ninguna cuenta."),
        Descriptor(
            "office.document.read",
            Schema([String("documentId", maximumLength: 128, nonWhitespace: true)], ["documentId"]),
            OperationRisks.ReadOnly,
            "office.document.read.adapter.snapshot.v1",
            "Lee una proyección estructurada de un documento identificado mediante el adapter oficial."),
        // BAXY Renew cu (C10 variante, C11): a format given to what the person has open in Word (its selection) or Excel
        // (its selection, a row, a column or a range), through the running application's object model, read back.
        Descriptor(
            "office.format.apply",
            Schema(
                [
                    String("app", values: ["excel", "word"]),
                    String("cells", types: NullableString, maximumLength: 32, nonWhitespace: true),
                    String("column", types: NullableString, maximumLength: 3, nonWhitespace: true),
                    Boolean("on", types: NullableBoolean),
                    Integer("paragraph", 1, 100_000, types: NullableInteger),
                    Integer("row", 1, 1_048_576, types: NullableInteger),
                    String("style", values: ["bold", "center", "italic", "left", "right", "underline"]),
                    String("target", types: NullableString, values: ["cells", "column", "paragraph", "row", "selection", "title"]),
                ],
                ["app", "style"]),
            OperationRisks.LowReversible,
            "office.format.apply.com.postread.v1",
            "Da un formato (negrita, cursiva, subrayado o una alineación) a lo que la persona tiene abierto en Word (su selección, su título o un párrafo por número) o en Excel (su selección, una fila, una columna o un rango, que deja elegido) por el modelo de objetos de la aplicación en marcha, y lo relee; no abre ninguna aplicación.",
            effects: [WindowInput()]),
        // BAXY Renew 2026-10-15: one call that resolves, installs and verifies, after the person's yes (installation
        // risk); it replaces the prepare/commit pair, which the 4B took for uninstalling.
        Descriptor(
            "package.install",
            Schema(
                [
                    String("packageId", maximumUtf8Bytes: 256, nonWhitespace: true),
                    String("version", types: NullableString, maximumLength: 64),
                ],
                ["packageId"]),
            OperationRisks.Installation,
            "package.install.winget.list.postread.v1",
            "Instala mediante winget el paquete que se nombra (por su id exacto o su nombre único) y verifica su presencia en la lista de paquetes instalados; si el nombre no es de un solo paquete, falla sin instalar y devuelve los candidatos."),
        // Auditoría semántica 2026-09-20 (REOPEN1993, grupo G): «desinstalá Discord»
        // es una desinstalación real por el gestor de paquetes, verificada por su
        // ausencia después; pierde lo instalado, así que confirma en modo normal.
        Descriptor(
            "package.uninstall",
            Schema([String("packageId", maximumUtf8Bytes: 256, nonWhitespace: true)], ["packageId"]),
            OperationRisks.WorkLoss,
            "package.uninstall.winget.absence.postread.v1",
            "Desinstala mediante winget el paquete instalado que se nombra (por su id exacto o su nombre único) y verifica su ausencia en la lista de paquetes instalados; hasta 8 candidatos (candidateCount); a los 12 segundos dice winget_uninstall_still_running (sigue desinstalando)."),
        Descriptor(
            "peripheral.list",
            Schema([String("kind", values:
                ["all", "keyboard", "mouse", "printer", "scanner", "usb"])], []),
            OperationRisks.ReadOnly,
            "peripheral.list.hardware.snapshot.v1",
            "Enumera periféricos conectados, incluidos mouse y teclado, mediante APIs de Windows; puede filtrar por tipo; una vista muestra 20 como mucho (lo marca y no alcanza lo que pasa de ahí)."),
        Descriptor(
            "peripheral.print",
            Schema(
                [
                    String("deviceId", maximumLength: 128, nonWhitespace: true),
                    String("documentId", maximumLength: 128, nonWhitespace: true),
                ],
                ["deviceId", "documentId"]),
            OperationRisks.PrivacySensitive,
            "peripheral.print.hardware.job.v1",
            "Envía un documento identificado a una impresora resuelta y verifica el job.",
            // The printer may be on the network.
            effects: [Network()]),
        Descriptor(
            "peripheral.scan",
            Schema([String("deviceId", maximumLength: 128, nonWhitespace: true)], ["deviceId"]),
            OperationRisks.PrivacySensitive,
            "peripheral.scan.hardware.capture.v1",
            "Captura desde un escáner resuelto y devuelve una identidad privada verificable."),
        Descriptor(
            "schedule.alarms",
            Schema(
                [
                    String("action", values: ["cancel", "create", "diagnose", "list"]),
                    String("at", maximumLength: 32, nonWhitespace: true),
                    Integer("inMinutes", 1, 525_600),
                    Integer("inSeconds", 10, 86_400),
                    String("kind", values: ["alarm", "reminder"]),
                    Integer("limit", 1, 50),
                    String("recurrence", values: ["daily", "hourly"]),
                    String("title", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                ],
                ["action"]),
            OperationRisks.LowReversible,
            "schedule.windows.task.local.clock.postread.v1",
            "Programa, lista o cancela alarmas y recordatorios audibles de BAXY (o diagnostica por qué no sonaron) en el Programador de tareas de Windows: al crear, a los minutos o segundos indicados o a una hora local (HH:mm o fecha y hora), única o diaria u horaria; al cancelar, el de esa hora local o el único pendiente (con varios no cancela ninguno y dice cuáles hay); al listar, las próximas 20 por hora como mucho (dice cuántas hay); y verifica la tarea en Windows."),
        Descriptor(
            "shell.command.run",
            Schema(
                [
                    String("command", maximumUtf8Bytes: 512, nonWhitespace: true),
                    String("cwd", types: NullableString, maximumUtf8Bytes: 260),
                ],
                ["command"]),
            OperationRisks.LowReversible,
            "shell.command.run.powershell.captured.output.v1",
            "Ejecuta un comando de consola en PowerShell sin perfil, en la carpeta conocida indicada (desktop, documents, downloads o una subcarpeta) o, sin carpeta, en una carpeta de trabajo propia y vacía del producto, con 60 segundos de plazo, y devuelve su código de salida y los primeros 8.192 caracteres de su salida (con más de un millón de caracteres se detiene y no devuelve nada); un código distinto de cero es un fallo con su salida y su error; lo que no sólo lee (escribe, borra, instala, envía o corre un programa) se confirma antes con el comando exacto.",
            // A command that only reads ran with no effect; one that may change something reports what ran.
            requiresObservedEffect: false,
            // One that only reads still reaches \\host\share or another computer by name.
            effects: [Network()]),
        Descriptor(
            "software.python.package.status",
            Schema([String("package")], ["package"]),
            OperationRisks.ReadOnly,
            "software.python.package.status.pip.show.read.v1",
            "Lee si un paquete de Python está instalado en cada instalación de Python registrada en Windows (pip show por instalación: instalada o no, versión del paquete, pip disponible) sin instalar ni cambiar nada; sin efecto."),
        Descriptor(
            "software.python.status",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "software.python.status.windows.registry.pep514.read.v1",
            "Lee las instalaciones de Python registradas en Windows (claves PEP 514 del registro: versión, nombre y ejecutable) sin ejecutar nada; sin efecto."),
        Descriptor(
            "storage.removable.list",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "storage.removable.list.driveinfo.read.v1",
            "Lee las unidades extraíbles conectadas ahora (pendrives, tarjetas SD; un disco USB que Windows ve como fijo no sale: letra, etiqueta, espacio libre y total) sin copiar ni cambiar nada; sin efecto."),
        Descriptor(
            "streaming.navigate",
            Schema(
                [
                    String("resourceUri", maximumUtf8Bytes: 2_048, nonWhitespace: true),
                    String("service", values: ["hbo_max", "netflix", "prime_video", "youtube"]),
                ],
                ["resourceUri", "service"]),
            OperationRisks.ExternalCommunication,
            "streaming.navigate.session.uri.postread.v1",
            "Navega una sesión autenticada de streaming a un recurso exacto y verifica su URI.",
            // Auditoría del núcleo 2026-10-23: la dirección sale al servicio.
            effects: [Network()]),
        Descriptor(
            "streaming.play.named",
            Schema(
                [
                    // VIDEO1947: Disney+ joins Netflix. Its player refuses the
                    // PlayReady path on this PC (MediaFoundation 0x8004CD…) and
                    // plays with Widevine when the page sees a Chrome user agent;
                    // the provider sets that override on the Disney+ target only.
                    // 2026-10-06: HBO Max joins them, played in the person's default
                    // browser with their session (documentacion/NAVEGADOR_USUARIO.md).
                    String("service", values: ["disney_plus", "hbo_max", "netflix"]),
                    String("title", maximumUtf8Bytes: 512, nonWhitespace: true),
                ],
                ["service", "title"]),
            OperationRisks.ExternalCommunication,
            "streaming.play.named.netflix.cdp.video.progress.v1",
            "Busca y reproduce un título en una sesión autenticada de Netflix, Disney+ o HBO Max y verifica la reproducción: en el navegador propio del producto, que el video avanza; en el de la persona, que la sesión multimedia del sistema dice que reproduce; en el navegador de la persona, hasta 10 candidatos.",
            // Auditoría del núcleo 2026-10-23: el título sale a la búsqueda del servicio.
            effects: [Network()]),
        Descriptor(
            "system.application.crash.diagnose",
            Schema(
                [
                    Integer("hours", 1, 168),
                    Integer("limit", 1, 50),
                ],
                []),
            OperationRisks.ReadOnly,
            "system.application.crash.diagnose.windows.eventlog.recordid.secondread.v1",
            "Consulta fallos y bloqueos recientes de aplicaciones en el registro Application de Windows y solo devuelve eventos con RecordId presentes en dos observaciones; mira las últimas 24 horas, 20 eventos por defecto; sus recuentos paran en cuatro veces limit (80 por defecto, 200 como mucho); una vista muestra 20 como mucho (lo marca y no alcanza lo que pasa de ahí)."),
        Descriptor(
            "system.identity",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "system.identity.windows.environment.secondread.v1",
            "Lee la cuenta de Windows bajo la que se ejecuta BAXY: su dominio y nombre de usuario, mediante dos observaciones coherentes. No identifica a la persona ni recupera su nombre dicho en conversación."),
        Descriptor(
            "system.power",
            Schema([String("action", values: ["lock", "restart", "shutdown", "signout", "sleep"])], ["action"]),
            OperationRisks.WorkLoss,
            "system.power.windows.transition.receipt.v1",
            "Solicita la transición de bloqueo, cierre de sesión o energía mediante la API oficial de Windows y exige su recibo de aceptación."),
        Descriptor(
            "system.process.list",
            Schema(
                [
                    Integer("limit", 1, 50),
                    String("sort", values: ["cpu", "memory", "name"]),
                ],
                []),
            OperationRisks.ReadOnly,
            "system.process.list.windows.identity.secondread.v1",
            "Enumera procesos locales acotados por CPU, memoria o nombre y verifica PID, nombre y tiempo de creacion con dos observaciones; no expone rutas ni argumentos; 10 por defecto (observedProcessCount es el total)."),
        Descriptor(
            "system.process.terminate.named",
            Schema([String("name", maximumLength: 128, nonWhitespace: true)], ["name"]),
            OperationRisks.WorkLoss,
            "system.process.terminate.named.windows.original.identity.absence.postread.v1",
            "Fuerza el cierre de un proceso por nombre ejecutable exacto, conserva sus identidades observadas y verifica que las identidades originales desaparecieron; acepta identidades nuevas creadas por reinicio automatico y requiere confirmacion por posible perdida de trabajo."),
        Descriptor(
            "system.recyclebin.empty",
            EmptySchema(),
            OperationRisks.WorkLoss,
            "system.recyclebin.empty.windows.zero.count.postread.v1",
            "Vacia la Papelera de reciclaje de Windows y verifica mediante postlectura que no queden elementos."),
        Descriptor(
            "system.settings.adjust",
            Schema(
                [
                    Integer("amount", 1, 100),
                    String("direction", values: ["down", "up"]),
                    String("setting", values: ["brightness"]),
                ],
                ["amount", "direction", "setting"]),
            OperationRisks.LowReversible,
            "system.settings.adjust.windows.postread.v1",
            "Sube o baja el brillo una cantidad acotada desde su valor observado y verifica cada monitor mediante WMI."),
        Descriptor(
            "system.settings.set",
            Schema(
                [
                    // REOPEN1957 H0107 «poneme el modo avión»: 1 apaga todas las
                    // radios (Wi-Fi, Bluetooth, móvil) por la API de radios y 0 las
                    // vuelve a encender; la postlectura mira cada radio.
                    // Estabilización U (identidad, accesibilidad y bypass): los dos ajustes
                    // propios de BAXY en el mismo ajuste. accessible_mode cambia sólo la
                    // presentación de su interfaz; confirmation_bypass desde el chat sólo
                    // se apaga (0): encenderlo es un gesto consciente en la interfaz.
                    String(
                        "setting",
                        values:
                        [
                            "accessible_mode", "airplane_mode", "brightness", "confirmation_bypass",
                            "do_not_disturb",
                        ]),
                    Integer("value", 0, 100),
                ],
                ["setting", "value"]),
            OperationRisks.PrivacySensitive,
            "system.settings.set.windows.postread.v1",
            "Cambia un ajuste permitido (brillo; no molestar, por la página Notificaciones de Configuración, que queda abierta; o modo avión sobre todas las radios, por la API de radios) o un ajuste de BAXY (su modo accesible; apagar el modo bypass) y verifica su postlectura.",
            // do_not_disturb opens ms-settings:notifications (it takes the front) and presses its switch by UI
            // Automation's Toggle (DoNotDisturbScript); airplane_mode goes through the radios API and reaches no window.
            effects:
            [
                WindowInput(EffectCondition.Is("setting", "do_not_disturb")),
                SystemChange(EffectCondition.Is("setting", "airplane_mode")),
            ]),
        Descriptor(
            "system.settings.status",
            Schema([String("setting", values: ["airplane_mode", "brightness"])], ["setting"]),
            OperationRisks.ReadOnly,
            "system.settings.status.windows.monitor.brightness.secondread.v1",
            "Lee el brillo actual de cada monitor compatible mediante WMI y exige dos observaciones coherentes sin modificarlo."),
        Descriptor(
            "system.status",
            Schema(
                [String(
                    "scope",
                    values:
                    [
                        "battery",
                        "cpu",
                        "cpu_memory",
                        "disk",
                        "firewall",
                        "gpu_identity",
                        "gpu_usage",
                        "memory",
                        "os",
                        "os_memory",
                        "summary",
                        "updates",
                    ])],
                []),
            OperationRisks.ReadOnly,
            "system.status.windows.measurement.v1",
            "Mide CPU, memoria, disco, batería, GPU y Windows; lee también el cortafuegos (sus perfiles, si están activos y los conectados ahora) y Windows Update (reinicio pendiente y actualizaciones por instalar según la última búsqueda de Windows, leída de su caché local: los títulos de las 10 primeras), sin modificar el equipo.",
            // Al máximo, flujos: WindowsSecurityStatusProvider: Windows Update is read for up to 90 s.
            budget: TimeSpan.FromSeconds(90)),
        Descriptor(
            "system.time",
            // Uso real tanda 4 «convertir nueve de la mañana huso horario a madrid»:
            // con un lugar o una zona horaria nombrados, la misma lectura trae el
            // desfase de esa zona en el mismo instante; no hay un reloj más.
            Schema(
                [String("place", types: NullableString, maximumUtf8Bytes: 128)],
                []),
            OperationRisks.ReadOnly,
            "system.time.clock.secondread.v1",
            "Lee la fecha y hora actuales, la hora UTC y el desfase local mediante dos observaciones coherentes; con un lugar o una zona horaria nombrados, también el desfase de esa zona en ese instante.",
            // A place's clock comes from Open-Meteo.
            effects: [Network(EffectCondition.Named("place"))]),
        Descriptor(
            "task.complete",
            TaskCasSchema(),
            OperationRisks.LowReversible,
            "task.complete.local.postread.v1",
            "Marca completa una tarea local seleccionada por identidad y versión exactas."),
        Descriptor(
            "task.create",
            Schema(
                [
                    String("details", maximumUtf8Bytes: 65_536),
                    String("due", types: NullableString, maximumLength: 64),
                    String("title", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                ],
                ["title"]),
            OperationRisks.LowReversible,
            "task.create.local.postread.v1",
            "Crea una tarea local privada; la fecha opcional es metadato y no programa recordatorios."),
        Descriptor(
            "task.delete",
            Schema(
                [
                    Integer("expectedVersion", 1),
                    String("reviewLabel", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                    String("taskId", maximumLength: 36, nonWhitespace: true),
                ],
                ["expectedVersion", "reviewLabel", "taskId"]),
            OperationRisks.RecoverableDelete,
            "task.delete.local.postread.v1",
            "Envía una tarea exacta a la papelera reversible después de revisar su etiqueta."),
        Descriptor(
            "task.list",
            Schema(
                [
                    Boolean("includeDeleted"),
                    Integer("limit", 1, 50),
                    String("status", values: ["all", "completed", "open"]),
                ],
                []),
            OperationRisks.ReadOnly,
            "task.list.local.reopen.v1",
            "Lista de forma acotada tareas locales abiertas, completadas o eliminadas; 20 por defecto (totalCount); sin status, sólo las abiertas; una vista muestra 20 como mucho (lo marca y no alcanza lo que pasa de ahí)."),
        Descriptor(
            "task.reopen",
            TaskCasSchema(),
            OperationRisks.LowReversible,
            "task.reopen.local.postread.v1",
            "Reabre una tarea completada usando identidad y versión exactas."),
        Descriptor(
            "task.restore",
            TaskCasSchema(),
            OperationRisks.LowReversible,
            "task.restore.local.postread.v1",
            "Restaura una tarea eliminada usando identidad y versión exactas."),
        Descriptor(
            "task.search",
            Schema(
                [
                    Integer("limit", 1, 50),
                    String("query", maximumUtf8Bytes: 2_000, nonWhitespace: true),
                    String("status", values: ["all", "completed", "open"]),
                ],
                ["query"]),
            OperationRisks.ReadOnly,
            "task.search.local.reopen.v1",
            "Busca en título y detalles de tareas locales sin crear índices de texto plano; 20 por defecto (totalCount); no busca en las borradas; una vista muestra 20 como mucho (lo marca y no alcanza lo que pasa de ahí)."),
        Descriptor(
            "task.update",
            Schema(
                [
                    String("details", maximumUtf8Bytes: 65_536),
                    String("due", types: NullableString, maximumLength: 64),
                    Integer("expectedVersion", 1),
                    String("taskId", maximumLength: 36, nonWhitespace: true),
                    String("title", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                ],
                ["details", "due", "expectedVersion", "taskId", "title"]),
            OperationRisks.LowReversible,
            "task.update.local.postread.v1",
            "Reemplaza los campos editables de una tarea bajo control de versión y postlectura."),
        Descriptor(
            "vision.describe",
            Schema(
                [
                    String("captureId", maximumLength: 128, nonWhitespace: true),
                    String("prompt", types: NullableString, maximumUtf8Bytes: 2_000),
                ],
                ["captureId"]),
            OperationRisks.PrivacySensitive,
            "vision.describe.provider.capture.binding.v1",
            "Describe una captura identificada mediante un modelo de visión local configurado en este PC, sin aceptar rutas arbitrarias; sin uno configurado falla con vision_provider_not_configured; sólo se guardan las 16 últimas capturas.",
            // Al máximo, flujos: CaptureVisionAdapter: the local endpoint has 90 s.
            budget: TimeSpan.FromSeconds(90)),
        // Auditoría semántica 2026-09-20 (REOPEN1993, grupo W): la encuesta pide el
        // clima, no páginas sobre el clima. Lectura pública sin clave (Open-Meteo:
        // geocodificación del lugar nombrado, o la ubicación de este PC por su IP) con
        // temperatura, sensación, cielo, viento, humedad y la lluvia de hoy y mañana.
        // Uso real tanda 4c: el recibo nombra el lugar leído (la ciudad de este PC
        // cuando no se nombra ninguno) y trae la calidad del aire del mismo lugar.
        Descriptor(
            "weather.current",
            Schema(
                [
                    // Ronda 19 (r17 t2-c13 «… en Valencia? ¿cojo paraguas?» → Valencia, Venezuela): el país que
                    // marca el habla de la persona (código ISO de dos letras): entre lugares homónimos de tamaño
                    // comparable se queda con el de ese país; sin uno así, los homónimos vuelven como candidatos.
                    // Ronda final 19 (W18): su significado llega al modelo en «arguments» de
                    // tool_descriptions.en.v1.json, no sólo en este comentario.
                    String("dialectCountry", types: NullableString, values: ["AR", "CL", "CO", "ES", "MX", "VE"]),
                    String("location", types: NullableString, maximumUtf8Bytes: 128),
                ],
                []),
            OperationRisks.ReadOnly,
            "weather.current.openmeteo.read.v1",
            "Lee el clima actual y el pronóstico de mañana del lugar nombrado, o de la ubicación aproximada de este PC (la que un servicio público deduce de su dirección de internet) si no se nombra ninguno, desde un servicio público sin clave, y devuelve temperatura, sensación térmica, estado del cielo, viento, humedad, probabilidad de lluvia, horas de salida y puesta del sol, calidad del aire y el lugar leído (la ciudad que ese servicio deduce, cuando no se nombra ninguno); hasta 8 candidatos (candidateCount).",
            effects: [Network()]),
        // Auditoría semántica 2026-09-20 (REOPEN1957 H0077 «descarga la imagen de
        // portada de wikipedia.org y guardala en el escritorio», H0069; D11): bajar un
        // archivo o imagen de una dirección a una carpeta conocida, verificado por el
        // tamaño del archivo escrito; una página entrega la imagen que ella misma anuncia.
        Descriptor(
            "web.download",
            Schema(
                [
                    String("folder", types: NullableString, values: ["desktop", "documents", "downloads", "pictures"]),
                    String("name", types: NullableString, maximumUtf8Bytes: 200),
                    String("url", maximumUtf8Bytes: 2_048, nonWhitespace: true),
                ],
                ["url"]),
            OperationRisks.PrivacySensitive,
            "web.download.http.file.size.postread.v1",
            "Descarga un archivo o una imagen de una dirección web pública (nunca este PC ni la red local), de 50 MiB como mucho, a una carpeta conocida (Descargas si no se nombra) y verifica el archivo escrito; de una página descarga la imagen de portada que la página anuncia; 3 redirecciones como mucho; se abandona si el servidor tarda más de 40 segundos en responder (cada redirección incluida); la descarga entera debe acabar en unos 100 segundos (lo que BAXY espera a una operación) o BAXY dice que falló (una que acabe justo después puede escribirse igual).",
            effects: [Network()]),
        // BAXY Renew, herramientas de agente (2026-10-15): leer una página como texto, como web_fetch de OpenClaw,
        // WebFetch de Claude Code o VisitWebpage de smolagents. Sólo una dirección pública por GET, sin cookies ni
        // nada de la persona (SearchPageReader); lo que entra es información, no sale nada suyo.
        Descriptor(
            "web.fetch",
            Schema(
                [
                    Integer("maximumCharacters", 500, 20_000),
                    Integer("offset", 0, 10_000_000),
                    String("url", maximumUtf8Bytes: 2_048, nonWhitespace: true),
                ],
                ["url"]),
            OperationRisks.ReadOnly,
            "web.fetch.public.http.text.v1",
            "Lee una página web pública (http o https) como texto, sin cookies ni datos de la persona, y devuelve su título, la dirección final y el texto por páginas (offset); sólo páginas HTML, y de una página de más de 1,5 MB (1.500.000 bytes) sólo el principio; 3 redirecciones como mucho.",
            effects: [Network()]),
        // BAXY Renew (2026-10-15): el modelo elige la fuente (source) y llena sus argumentos tipados; el proveedor
        // pregunta sólo a esa fuente y devuelve lo que ella devolvió. Lo que significa cada argumento lo dice la
        // descripción de la herramienta (tool_descriptions.en.v1.json).
        Descriptor(
            "web.search",
            Schema(
                [
                    // currency: la cantidad a convertir (1 si no se da).
                    new OperationArgumentProperty("amount", OperationJsonType.Null | OperationJsonType.Number),
                    // currency: códigos ISO 4217.
                    String("from", types: NullableString, maximumLength: 3),
                    // places: la clase de sitio, en inglés («pharmacy», «parking»).
                    String("kind", types: NullableString, maximumUtf8Bytes: 128),
                    // encyclopedia y news: la Wikipedia o la edición de noticias.
                    String("language", types: NullableString, values: ["en", "es"]),
                    Integer("limit", 1, 10, types: NullableInteger),
                    // La ciudad y el país de este PC se añaden a la consulta (o son el lugar, en places).
                    Boolean("nearby", types: NullableBoolean),
                    // places: el lugar donde se buscan los sitios.
                    String("place", types: NullableString, maximumUtf8Bytes: 256),
                    String("query", maximumUtf8Bytes: 2_000, nonWhitespace: true),
                    String(
                        "source",
                        types: NullableString,
                        values: ["currency", "encyclopedia", "news", "places", "sports", "web"]),
                    // sports: el equipo, y si se pide el próximo partido o el último.
                    String("team", types: NullableString, maximumUtf8Bytes: 128),
                    String("to", types: NullableString, maximumLength: 3),
                    String("wants", types: NullableString, values: ["last", "next"]),
                ],
                ["query"]),
            OperationRisks.ReadOnly,
            "web.search.provider.results.v1",
            "Busca en la fuente pública que elige el modelo (buscador web, noticias, enciclopedia, divisas, deportes o sitios de un lugar) con sus argumentos tipados y devuelve los resultados tal como esa fuente los dio, acotados; con nearby, añade la ciudad y el país de este PC a la consulta; 5 resultados por defecto.",
            effects: [Network()]),
        Descriptor(
            "wifi.connect",
            Schema([String("profileId", maximumLength: 128, nonWhitespace: true)], ["profileId"]),
            OperationRisks.PrivacySensitive,
            "wifi.connect.wlan.profile.postread.v1",
            "Conecta un perfil WLAN ya guardado y verifica el estado sin exponer SSID ni credenciales."),
        // Auditoría semántica 2026-09-20 (REOPEN1957 H0170/H0376 «conectate al wifi de
        // casa», D24): «casa» no es un SSID. Con `place`, el proveedor conecta la red
        // que la persona asoció antes a ese lugar; si nombra el perfil y el lugar a la
        // vez, conecta ese perfil y recuerda la asociación en los datos privados.
        Descriptor(
            "wifi.connect.named",
            Schema(
                [
                    String("place", types: NullableString, values: ["casa", "oficina", "trabajo"]),
                    String("profileName", maximumUtf8Bytes: 256, nonWhitespace: true),
                ],
                ["profileName"]),
            OperationRisks.PrivacySensitive,
            "wifi.connect.named.wlan.profile.postread.v1",
            "Resuelve de forma única un perfil WLAN guardado por el nombre indicado (o por el lugar asociado antes: casa, trabajo, oficina), lo conecta, verifica el estado sin exponer credenciales y recuerda la asociación lugar→red cuando se dan ambos."),
        Descriptor(
            "wifi.disconnect",
            EmptySchema(),
            OperationRisks.PrivacySensitive,
            "wifi.disconnect.wlan.postread.v1",
            "Desconecta WLAN mediante API oficial y verifica ausencia de conexión.",
            effects: [SystemChange()]),
        Descriptor(
            "wifi.ensure.connected",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "wifi.ensure.connected.wlan.current.profile.postread.v1",
            "Comprueba que Wi-Fi ya está conectado y devuelve la identidad opaca del perfil observado."),
        Descriptor(
            "wifi.profile.list",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "wifi.profile.list.wlan.snapshot.v1",
            "Enumera perfiles WLAN guardados mediante identidades opacas sin exponer credenciales; una vista muestra 20 como mucho (lo marca y no alcanza lo que pasa de ahí)."),
        Descriptor(
            "wifi.radio.set",
            Schema([Boolean("state")], ["state"]),
            OperationRisks.PrivacySensitive,
            "wifi.radio.set.windows.radio.postread.v1",
            "Enciende o apaga la radio Wi-Fi mediante la API oficial de Windows y verifica su estado final.",
            effects: [SystemChange()]),
        Descriptor(
            "wifi.radio.status",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "wifi.radio.status.windows.radio.read.v1",
            "Lee si la radio Wi-Fi está encendida mediante la API oficial de Windows sin cambiar nada."),
        Descriptor(
            "wifi.scan",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "wifi.scan.netsh.wlan.networks.bssid.v1",
            "Lista las redes Wi-Fi visibles ahora para el adaptador WLAN (nombre, autenticación y señal) mediante netsh; si la radio está apagada devuelve ese estado sin cambiar nada; lee 50 redes como mucho y una vista muestra 20 (lo marca)."),
        Descriptor(
            "wifi.status",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "wifi.status.netsh.wlan.secondread.v1",
            "Lee dos veces el estado WLAN actual y devuelve conexión e identidad opaca del perfil sin exponer SSID ni credenciales."),
        Descriptor(
            "window.active",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "window.active.identity.foreground.v1",
            "Lee la ventana visible en primer plano y verifica su proceso, estado, geometría e identidad efímera."),
        Descriptor(
            "window.application.status",
            Schema([String("name", maximumUtf8Bytes: 256, nonWhitespace: true)], ["name"]),
            OperationRisks.ReadOnly,
            "window.application.status.catalog.visible.snapshot.v1",
            "Comprueba por nombre cualquier aplicación del catálogo Inicio y verifica si tiene una ventana visible sin abrirla ni modificarla."),
        Descriptor(
            "window.close.all",
            EmptySchema(),
            OperationRisks.WorkLoss,
            "window.close.all.desktop.postread.v1",
            "Pide el cierre de todas las ventanas visibles de este escritorio salvo las de BAXY (las de otro escritorio virtual no se tocan y se cuentan), verifica cuáles se cerraron y cuenta las que siguen abiertas (por ejemplo, las que preguntan si guardar); nunca fuerza un proceso."),
        Descriptor(
            "window.focus",
            WindowIdSchema(),
            OperationRisks.LowReversible,
            "window.focus.identity.foreground.v1",
            "Enfoca una ventana resuelta previamente y verifica su identidad y foco; el windowId caduca a los 5 minutos.",
            effects: [WindowInput()]),
        Descriptor(
            "window.maximize",
            WindowIdSchema(),
            OperationRisks.LowReversible,
            "window.maximize.identity.state.v1",
            "Maximiza una ventana resuelta previamente y verifica su identidad y estado; el windowId caduca a los 5 minutos.",
            effects: [WindowInput()]),
        Descriptor(
            "window.minimize",
            WindowIdSchema(),
            OperationRisks.LowReversible,
            "window.minimize.identity.state.v1",
            "Minimiza una ventana resuelta previamente y verifica su identidad y estado; el windowId caduca a los 5 minutos."),
        Descriptor(
            "window.minimize.all",
            EmptySchema(),
            OperationRisks.LowReversible,
            "window.minimize.all.desktop.postread.v1",
            "Minimiza todas las ventanas visibles de este escritorio (salvo la propia; las de otro escritorio virtual no se tocan y se cuentan) y comprueba que quedaron minimizadas; no cierra nada.",
            effects: [WindowInput()]),
        Descriptor(
            "window.move",
            Schema(
                [
                    String("windowId", maximumLength: 36, nonWhitespace: true),
                    Integer("x", -32_768, 32_767),
                    Integer("y", -32_768, 32_767),
                ],
                ["windowId", "x", "y"]),
            OperationRisks.LowReversible,
            "window.move.identity.bounds.v1",
            "Mueve una ventana resuelta a coordenadas de escritorio y verifica sus límites exactos.",
            effects: [WindowInput()]),
        Descriptor(
            "window.resize",
            Schema(
                [
                    Integer("height", 1, 32_768),
                    Integer("width", 1, 32_768),
                    String("windowId", maximumLength: 36, nonWhitespace: true),
                ],
                ["height", "width", "windowId"]),
            OperationRisks.LowReversible,
            "window.resize.identity.bounds.v1",
            "Redimensiona una ventana resuelta y verifica ancho y alto exactos.",
            effects: [WindowInput()]),
        Descriptor(
            "window.resolve",
            Schema(
                [
                    String("applicationName", maximumUtf8Bytes: 256, nonWhitespace: true),
                    Boolean("byTitle"),
                    Integer("limit", 1, 50),
                    Integer("offset", 0, int.MaxValue),
                    String("process", maximumLength: 260, nonWhitespace: true),
                ],
                []),
            OperationRisks.ReadOnly,
            "window.resolve.identity.inventory.v3",
            "Lee ventanas de nivel superior con estilo visible. Requiere exactamente un selector: applicationName (nombre exacto instalado, identidad AUMID o ejecutable comprobada, sin byTitle ni offset; devuelve la selección completa o falla), o process. Nunca convierte un nombre de aplicación en título o proceso. process='*' y byTitle=false enumeran todas; otro process busca ese proceso, y byTitle=true busca el título explícito solicitado. limit limita la página (1–50, 20 por defecto; una vista muestra 20), offset empieza en 0. count cuenta la página; observedCount cuenta las observadas; complete=false implica lectura parcial y totalCount desconocido. nextOffset continúa sólo las observadas. Cada página vuelve a enumerar y puede cambiar: no es una foto estable ni prueba de que las ventanas estén descubiertas en pantalla. Devuelve títulos e identificadores efímeros; para modificar una ventana hay que elegir su identificador."),
        Descriptor(
            "window.restore",
            WindowIdSchema(),
            OperationRisks.LowReversible,
            "window.restore.identity.state.v1",
            "Restaura una ventana resuelta previamente y verifica su identidad y estado."),
        Descriptor(
            "window.snap",
            Schema(
                [
                    String("side", values: ["left", "right"]),
                    String("windowId", maximumLength: 36, nonWhitespace: true),
                ],
                ["side", "windowId"]),
            OperationRisks.LowReversible,
            "window.snap.identity.bounds.v1",
            "Coloca una ventana resuelta en la mitad izquierda o derecha del área de trabajo de su monitor (la restaura antes si estaba maximizada o minimizada) y verifica sus límites exactos; el windowId caduca a los 5 minutos.",
            effects: [WindowInput()]),
    ];

    private static readonly IReadOnlyList<ProductOperationDescriptor> ReadOnlyCatalog =
        Array.AsReadOnly(Catalog);

    static ProductCatalog()
    {
        string[] names = Catalog.Select(static descriptor => descriptor.Name).ToArray();
        if (!names.SequenceEqual(names.Order(StringComparer.Ordinal), StringComparer.Ordinal)
            || names.Distinct(StringComparer.Ordinal).Count() != names.Length
            || Catalog.Select(static descriptor => descriptor.VerifierContractId)
                .Distinct(StringComparer.Ordinal).Count() != Catalog.Length)
        {
            throw new InvalidOperationException(
                "The product operation catalog must have stable unique operation and verifier identities.");
        }
    }

    // Every operation is a tool the model is offered (the internal steps nothing sent were retired in the final audit).
    public static IReadOnlyList<ProductOperationDescriptor> ToolDescriptors => ReadOnlyCatalog;

    public static bool TryGet(
        string? name,
        [NotNullWhen(true)] out ProductOperationDescriptor? descriptor)
    {
        descriptor = name is null
            ? null
            : Catalog.FirstOrDefault(candidate =>
                string.Equals(candidate.Name, name, StringComparison.Ordinal));
        return descriptor is not null;
    }

    public static ProductOperationDescriptor GetRequired(string name)
    {
        if (!TryGet(name, out ProductOperationDescriptor? descriptor))
        {
            throw new ArgumentException("The operation is not part of the product catalog.", nameof(name));
        }

        return descriptor!;
    }

    public static OperationDefinition CreateDefinition(string name) =>
        new(GetRequired(name));

    public static OperationDescriptor CreateToolDescriptor(OperationDefinition definition)
    {
        ArgumentNullException.ThrowIfNull(definition);
        ProductOperationDescriptor descriptor = definition.ProductDescriptor
            ?? throw new ArgumentException(
                "A tool definition must be bound to a product descriptor.",
                nameof(definition));
        if (!Catalog.Any(candidate => ReferenceEquals(candidate, descriptor)))
        {
            throw new ArgumentException(
                "Only an exact product descriptor may be exported as a tool.",
                nameof(definition));
        }

        using JsonDocument schema = JsonDocument.Parse(descriptor.ArgumentsSchema.CanonicalJson);
        return new OperationDescriptor(
            descriptor.Name,
            schema.RootElement.Clone(),
            descriptor.Risk,
            descriptor.VerifierContractId,
            descriptor.Description,
            descriptor.EffectKinds.Count == 0 ? null : descriptor.EffectKinds);
    }

    public static void ValidateAgainst(OperationRegistry registry)
    {
        ArgumentNullException.ThrowIfNull(registry);
        if (registry.Definitions.Count != Catalog.Length)
        {
            throw new InvalidOperationException(
                "The product operation catalog does not match the registered core operations.");
        }

        for (int index = 0; index < Catalog.Length; index++)
        {
            OperationDefinition definition = registry.Definitions[index];
            if (!ReferenceEquals(definition.ProductDescriptor, Catalog[index]))
            {
                throw new InvalidOperationException(
                    "A registered core handler is not bound to its exact product descriptor.");
            }
        }
    }

    public static OperationRisk ToPolicyRisk(string exactRisk) => exactRisk switch
    {
        OperationRisks.ReadOnly => OperationRisk.ReadOnly,
        OperationRisks.LowReversible => OperationRisk.Reversible,
        // Decisión del dueño (2026-10-16): mandar a la Papelera, o una nota o tarea a su papelera, pide su «sí» como lo
        // que no se deshace, aunque se pueda restaurar.
        OperationRisks.RecoverableDelete => OperationRisk.Irreversible,
        OperationRisks.PrivacySensitive => OperationRisk.Sensitive,
        OperationRisks.ExternalCommunication => OperationRisk.External,
        // Decisión 8 del dueño (2026-10-10, PROMPT_ESTABILIZACION): en Normal se confirma lo que destruye datos y lo
        // que sale al mundo, también instalar; D3 (2026-09-20) lo dejaba directo.
        OperationRisks.WorkLoss or OperationRisks.Installation => OperationRisk.Irreversible,
        // ProductOperationDescriptor admits only the known labels above.
        _ => throw new ArgumentOutOfRangeException(nameof(exactRisk)),
    };

    private static ProductOperationDescriptor Descriptor(
        string name,
        OperationArgumentsSchema schema,
        string risk,
        string verifierContractId,
        string description,
        bool? requiresObservedEffect = null,
        IReadOnlyList<OperationEffect>? effects = null,
        TimeSpan? budget = null) =>
        new(name, schema, risk, verifierContractId, description, requiresObservedEffect, effects, budget);

    // Al máximo 5.1: what each provider does, read from it (the App held these by name before).
    private static OperationEffect WindowInput(params EffectCondition[] when) =>
        when.Length == 0
            ? OperationEffect.Always(OperationEffects.WindowInput)
            : OperationEffect.With(OperationEffects.WindowInput, when);

    private static OperationEffect Network(params EffectCondition[] when) =>
        when.Length == 0
            ? OperationEffect.Always(OperationEffects.Network)
            : OperationEffect.With(OperationEffects.Network, when);

    private static OperationEffect SystemChange(params EffectCondition[] when) =>
        when.Length == 0
            ? OperationEffect.Always(OperationEffects.System)
            : OperationEffect.With(OperationEffects.System, when);

    private static OperationArgumentsSchema EmptySchema() => Schema([], []);

    // The known folders a capture can also be saved to, as a PNG the person can find.
    private static OperationArgumentsSchema CaptureSchema() =>
        Schema([String("folder", values: ["desktop", "documents", "downloads", "pictures"])], []);

    private static OperationArgumentsSchema Schema(
        IReadOnlyList<OperationArgumentProperty> properties,
        IReadOnlyList<string> required) =>
        new(properties, required);

    private static OperationArgumentsSchema MemorySaveSchema(IReadOnlyList<string> sensitivities) =>
        Schema(
            [
                String(
                    "expiryPolicy",
                    values: ["after_relevance_window", "session_end"]),
                String("kind", values: KindValues()),
                String("retention", values: RetentionValues()),
                String("selector", maximumUtf8Bytes: 256, nonWhitespace: true),
                String("sensitivity", values: sensitivities),
                new OperationArgumentProperty(
                    "tags",
                    OperationJsonType.Array,
                    itemTypes: OperationJsonType.String,
                    maximumItems: 16,
                    itemMaximumUtf8Bytes: 64,
                    itemNonWhitespace: true),
                ScalarProperty("value"),
                Version(),
            ],
            ["kind", "retention", "selector", "sensitivity", "tags", "value", "version"]);

    private static OperationArgumentsSchema NoteSelectorSchema() =>
        Schema(
            [
                Boolean("expectedIsTrashed", types: NullableBoolean),
                Integer("expectedRevision", 1, types: NullableInteger),
                String(
                    "expectedTitle",
                    types: NullableString,
                    maximumUtf8Bytes: 512,
                    nonWhitespace: true),
                String("noteId", types: NullableString, maximumLength: 36),
                String(
                    "title",
                    types: NullableString,
                    maximumUtf8Bytes: 512,
                    nonWhitespace: true),
            ],
            []);

    private static OperationArgumentsSchema WindowIdSchema() =>
        Schema(
            [String("windowId", maximumLength: 36, nonWhitespace: true)],
            ["windowId"]);

    private static OperationArgumentsSchema TaskCasSchema() =>
        Schema(
            [
                Integer("expectedVersion", 1),
                String("taskId", maximumLength: 36, nonWhitespace: true),
            ],
            ["expectedVersion", "taskId"]);

    private static OperationArgumentsSchema FilesystemTransferSchema() =>
        Schema(
            [
                String("destinationRelativePath", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                String("expectedSha256", maximumLength: 64, nonWhitespace: true),
                String("resourceId", maximumLength: 35, nonWhitespace: true),
            ],
            ["destinationRelativePath", "expectedSha256", "resourceId"]);



    private static OperationArgumentProperty Version() => Integer("version", 1, 1);

    private static OperationArgumentProperty ScalarProperty(string name) =>
        new(name, Scalar);

    private static OperationArgumentProperty Boolean(
        string name,
        bool? constant = null,
        OperationJsonType types = OperationJsonType.Boolean) =>
        new(name, types, constantBoolean: constant);

    private static OperationArgumentProperty Integer(
        string name,
        long? minimum = null,
        long? maximum = null,
        OperationJsonType types = OperationJsonType.Integer) =>
        new(name, types, minimum: minimum, maximum: maximum);

    private static OperationArgumentProperty String(
        string name,
        OperationJsonType types = OperationJsonType.String,
        int? maximumLength = null,
        int? maximumUtf8Bytes = null,
        bool nonWhitespace = false,
        IReadOnlyList<string>? values = null) =>
        new(
            name,
            types,
            maximumLength: maximumLength,
            maximumUtf8Bytes: maximumUtf8Bytes,
            allowedValues: values,
            nonWhitespace: nonWhitespace);

    private static string[] KindValues() => ["context", "fact", "preference", "rule"];

    private static string[] RetentionValues() => ["persistent", "session", "temporary"];
}
