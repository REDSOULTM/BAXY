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

    private static readonly ProductOperationDescriptor[] Catalog =
    [
        Descriptor(
            "app.close",
            WindowIdSchema(),
            OperationRisks.WorkLoss,
            "app.close.identity.window.absence.v1",
            ToolExposure.Public,
            "Solicita el cierre de una ventana resuelta y verifica su ausencia sin forzar la terminacion del proceso."),
        Descriptor(
            "app.installed",
            Schema([String("name", maximumUtf8Bytes: 256, nonWhitespace: true)], ["name"]),
            OperationRisks.ReadOnly,
            "app.installed.windows.catalog.snapshot.v1",
            ToolExposure.Public,
            "Comprueba en el catalogo Inicio de Windows si una aplicacion concreta esta instalada sin abrirla."),
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
            ToolExposure.Public,
            "Abre por nombre exacto una aplicación del catálogo Inicio del usuario y verifica su proceso, ventana visible y foco; sin ese nombre exacto no abre nada y dice los nombres instalados más cercanos. También acepta windows.calculator."),
        Descriptor(
            "app.status",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "app.status.catalog.ready.v1",
            ToolExposure.Internal,
            "Checks that the local core is available and lists its operations."),
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
            ToolExposure.Public,
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
            ToolExposure.Public,
            "Fija el volumen propio de una aplicación (sus sesiones de audio en la salida predeterminada, el control por aplicación del mezclador) en un nivel absoluto de 0 a 100, aunque esté en pausa, y verifica la postlectura; no toca el volumen del sistema."),
        Descriptor(
            "audio.microphone.mute",
            Schema([Boolean("state")], ["state"]),
            OperationRisks.LowReversible,
            "audio.microphone.mute.capture.endpoint.postread.v1",
            ToolExposure.Public,
            "Silencia o reactiva el micrófono predeterminado de Windows y corrobora la postlectura del endpoint de captura."),
        Descriptor(
            "audio.mute",
            Schema([Boolean("state")], ["state"]),
            OperationRisks.LowReversible,
            "audio.mute.endpoint.postread.v1",
            ToolExposure.Public,
            "Silencia o reactiva la salida predeterminada y corrobora la postlectura."),
        Descriptor(
            "audio.status",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "audio.status.endpoint.read.v1",
            ToolExposure.Public,
            "Identifica por nombre la salida de audio predeterminada actual y lee su volumen y silencio, sin modificarla."),
        Descriptor(
            "audio.volume",
            Schema([Integer("level", 0, 100)], ["level"]),
            OperationRisks.LowReversible,
            "audio.volume.endpoint.postread.v1",
            ToolExposure.Public,
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
            ToolExposure.Public,
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
            ToolExposure.Public,
            "Crea una copia privada inmutable de un archivo identificado y verifica su SHA-256."),
        Descriptor(
            "backup.known.create",
            Schema(
                [String("folder", values: ["all_known", "desktop", "documents", "pictures", "projects"])],
                ["folder"]),
            OperationRisks.LowReversible,
            "backup.known.create.windows.zip.hash.postread.v1",
            ToolExposure.Public,
            "Crea un ZIP privado de una carpeta conocida de Windows y verifica su manifiesto y SHA-256."),
        Descriptor(
            "backup.known.list",
            Schema([Integer("limit", 1, 50)], []),
            OperationRisks.ReadOnly,
            "backup.known.list.windows.manifest.hash.snapshot.v1",
            ToolExposure.Public,
            "Lista los backups ZIP de carpetas conocidas y vuelve a verificar sus hashes."),
        Descriptor(
            "backup.known.restore.latest",
            Schema(
                [String("folder", values: ["all_known", "desktop", "documents", "pictures", "projects"])],
                ["folder"]),
            OperationRisks.LowReversible,
            "backup.known.restore.latest.windows.extract.hash.postread.v1",
            ToolExposure.Public,
            "Restaura el backup ZIP más reciente en un directorio privado nuevo y verifica archivos y bytes extraídos."),
        Descriptor(
            "backup.known.verify.latest",
            Schema(
                [String("folder", values: ["all_known", "desktop", "documents", "pictures", "projects"])],
                ["folder"]),
            OperationRisks.ReadOnly,
            "backup.known.verify.latest.windows.hash.postread.v1",
            ToolExposure.Public,
            "Verifica el SHA-256 del backup ZIP más reciente de la carpeta indicada."),
        Descriptor(
            "backup.list",
            Schema([Integer("limit", 1, 50)], []),
            OperationRisks.ReadOnly,
            "backup.list.sandbox.hash.snapshot.v1",
            ToolExposure.Public,
            "Lista copias privadas verificadas, ordenadas desde la mas reciente, sin exponer rutas internas."),
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
            ToolExposure.Public,
            "Restaura un backup verificado únicamente en un destino libre del sandbox."),
        Descriptor(
            "backup.verify",
            Schema([String("backupId", maximumLength: 39, nonWhitespace: true)], ["backupId"]),
            OperationRisks.ReadOnly,
            "backup.verify.sandbox.hash.v1",
            ToolExposure.Public,
            "Reabre un backup privado y verifica tamaño y SHA-256."),
        Descriptor(
            "bluetooth.device.list",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "bluetooth.device.list.hardware.snapshot.v1",
            ToolExposure.Public,
            "Enumera dispositivos Bluetooth mediante un adapter oficial y un gate físico de hardware."),
        Descriptor(
            "bluetooth.device.pair",
            Schema([String("deviceId", maximumUtf8Bytes: 256, nonWhitespace: true)], ["deviceId"]),
            OperationRisks.PrivacySensitive,
            "bluetooth.device.pair.hardware.postread.v1",
            ToolExposure.Public,
            "Empareja un dispositivo resuelto mediante el diálogo y permisos oficiales del sistema."),
        Descriptor(
            "bluetooth.radio.set",
            Schema([Boolean("state")], ["state"]),
            OperationRisks.LowReversible,
            "bluetooth.radio.set.windows.radio.postread.v1",
            ToolExposure.Public,
            "Enciende o apaga las radios Bluetooth mediante la API oficial de Windows y verifica su estado final."),
        Descriptor(
            "bluetooth.radio.status",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "bluetooth.radio.status.windows.radio.read.v1",
            ToolExposure.Public,
            "Lee si las radios Bluetooth están encendidas o apagadas mediante la API oficial de Windows; sin efecto."),
        Descriptor(
            "browser.control",
            Schema([String("action", values:
                ["back", "close", "close_all", "fullscreen_video", "new_tab", "reload", "scroll_down", "scroll_up"])], ["action"]),
            OperationRisks.LowReversible,
            "browser.control.cdp.postread.v1",
            ToolExposure.Public,
            "Controla la pagina CDP actual y verifica historial, desplazamiento o cierre mediante postlectura."),
        Descriptor(
            "browser.navigate",
            Schema([String("url", maximumUtf8Bytes: 2_048, nonWhitespace: true)], ["url"]),
            OperationRisks.ExternalCommunication,
            "browser.navigate.cdp.url.postread.v1",
            ToolExposure.Public,
            "Navega una sesión CDP autenticada a una URL exacta y verifica la URL final."),
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
            ToolExposure.Public,
            "Navega el navegador Chromium indicado (Opera, Opera GX, Chrome, Edge o Brave) mediante un perfil CDP privado y verifica ejecutable y URL final."),
        Descriptor(
            "browser.page.read",
            Schema([Integer("maximumCharacters", 256, 32_768)], []),
            OperationRisks.PrivacySensitive,
            "browser.page.read.cdp.dom.snapshot.v1",
            ToolExposure.Public,
            "Lee titulo, URL y texto visible de la pagina CDP activa sin modificarla y limita el contenido devuelto.",
            // WEB1541: a read observes no effect; the receipt says so truthfully.
            requiresObservedEffect: false),
        Descriptor(
            "browser.tabs.list",
            Schema([Integer("limit", 1, 50)], []),
            OperationRisks.PrivacySensitive,
            "browser.tabs.list.cdp.targets.snapshot.v1",
            ToolExposure.Public,
            "Enumera las pestanas web de la sesion CDP local con identidad, titulo y URL observados.",
            requiresObservedEffect: false),
        Descriptor(
            "calculator.expression.evaluate",
            Schema([String("expression", maximumLength: 64, nonWhitespace: true)], ["expression"]),
            OperationRisks.LowReversible,
            "calculator.expression.evaluate.windows.calculator.uia.display.v1",
            ToolExposure.Public,
            "Escribe una expresión aritmética simple en la Calculadora de Windows abierta (en primer plano, verificada) y lee el resultado que muestra su pantalla mediante UI Automation; sin efecto fuera de la Calculadora."),
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
            ToolExposure.Public,
            "Crea un evento en una cuenta de calendario autenticada y verifica su identidad remota."),
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
            ToolExposure.Public,
            "Lista eventos acotados desde una cuenta autenticada sin modificarlos."),
        // Ronda 22 (uso real r18 t2-c16, t3-c11, t4-c09 «…y guárdala en el escritorio»): a capture the person asks to
        // keep is also saved as a PNG in the known folder named («folder»; pictures: its screenshots subfolder), with
        // a dated name that never overwrites, read back against its hash. Without «folder» it stays private only.
        Descriptor(
            "capture.active.window",
            CaptureSchema(),
            OperationRisks.PrivacySensitive,
            "capture.active.window.gdi.foreground.bounds.bmp.hash.v1",
            ToolExposure.Public,
            "Captura solo los límites visibles de la ventana activa en un BMP privado y devuelve metadatos verificados; con folder guarda además una copia PNG verificada en esa carpeta conocida."),
        Descriptor(
            "capture.screenshot",
            CaptureSchema(),
            OperationRisks.PrivacySensitive,
            "capture.screenshot.gdi.bmp.hash.v1",
            ToolExposure.Public,
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
            ToolExposure.Public,
            "Busca un canal o chat por nombre en el buscador rápido del cliente de escritorio (Discord: Ctrl+K), lee las coincidencias por UI Automation y cierra el buscador sin unirse ni abrir nada; sin efecto.",
            // The locate is a post-read: it joins and opens nothing, so it verifies by its result
            // (the matches read from the switcher), not by an observed external mutation.
            requiresObservedEffect: false),
        Descriptor(
            "clipboard.copy",
            EmptySchema(),
            OperationRisks.PrivacySensitive,
            "clipboard.copy.win32.foreground.sendinput.sequence.postread.v1",
            ToolExposure.Public,
            "Copia la selección del control enfocado y verifica foco estable, aceptación completa de Ctrl+C y un cambio real del portapapeles."),
        Descriptor(
            "clipboard.paste",
            EmptySchema(),
            OperationRisks.PrivacySensitive,
            "clipboard.paste.win32.clipboard.foreground.sendinput.accepted.v1",
            ToolExposure.Public,
            "Pega el contenido actual del portapapeles en el control enfocado y verifica que el portapapeles no esté vacío, que el foco no cambie y que Windows acepte todos los eventos Ctrl+V."),
        Descriptor(
            "clipboard.read.text",
            Schema([Integer("maxCharacters", 1, 65_536)], []),
            OperationRisks.PrivacySensitive,
            "clipboard.read.text.sequence.secondread.v1",
            ToolExposure.Public,
            "Lee texto privado acotado del portapapeles y exige dos snapshots idénticos."),
        Descriptor(
            "clipboard.write.text",
            Schema([String("text", maximumLength: 65_536)], ["text"]),
            OperationRisks.PrivacySensitive,
            "clipboard.write.text.sequence.postread.v1",
            ToolExposure.Public,
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
            ToolExposure.Public,
            "Cambia el fondo de escritorio a un color liso nombrado o a una imagen de una carpeta conocida y verifica la postlectura del sistema; devuelve el fondo anterior."),
        Descriptor(
            "display.status",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "display.status.windows.display.devices.read.v1",
            ToolExposure.Public,
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
            ToolExposure.Public,
            "Crea una presentación .pptx con el título dado y una diapositiva por entrada (primera línea título, las demás viñetas) en una carpeta conocida y verifica cuántas diapositivas tiene el paquete escrito."),
        Descriptor(
            "email.latest.read",
            EmptySchema(),
            OperationRisks.PrivacySensitive,
            "email.latest.read.outlook.mapi.snapshot.v1",
            ToolExposure.Public,
            "Lee el mensaje mas reciente del buzon Outlook autenticado y verifica su identidad MAPI."),
        Descriptor(
            "email.latest.reply",
            Schema([String("text", maximumUtf8Bytes: 16_384, nonWhitespace: true)], ["text"]),
            OperationRisks.ExternalCommunication,
            "email.latest.reply.outlook.sent.postread.v1",
            ToolExposure.Public,
            "Responde al mensaje mas reciente de Outlook y verifica la copia enviada por contenido y hora."),
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
            ToolExposure.Public,
            "Envía un correo a la dirección indicada (asunto opcional; sin asunto, el comienzo del texto) desde el perfil clásico de Outlook del dueño y verifica la copia en Elementos enviados por destinatario, texto y hora."),
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
            ToolExposure.Public,
            "Comprime un archivo o una carpeta de una carpeta conocida en un zip con el mismo nombre al lado y verifica que el zip existe y tiene entradas."),
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
            ToolExposure.Public,
            "Reemplaza un texto exacto en un archivo de texto nombrado de forma única en una carpeta conocida (una vez, o todas si se pide; si aparece más de una vez sin pedirlo no cambia nada y dice cuántas), conserva su codificación, envía la versión anterior a la Papelera de reciclaje y verifica releyendo el archivo."),
        Descriptor(
            "file.find",
            Schema(
                [
                    String("content", maximumUtf8Bytes: 512, nonWhitespace: true),
                    String("folder", values: ["all_known", "desktop", "documents", "downloads", "home"]),
                    Integer("limit", 1, 100),
                    String("order", values: ["name", "recent"]),
                    String("query", maximumUtf8Bytes: 512, nonWhitespace: true),
                    String("subdirectory", maximumUtf8Bytes: 512, nonWhitespace: true),
                ],
                ["folder"]),
            OperationRisks.ReadOnly,
            "file.find.windows.known.name.content.bounded.v1",
            ToolExposure.Public,
            "Lista el primer nivel de una carpeta conocida de Windows, o busca bajo ella archivos por nombre (parte del nombre o patrón con * y ?) o por un texto dentro de sus archivos de texto, de forma acotada y sin seguir puntos de reanálisis; devuelve cada archivo con su ruta relativa a la carpeta, nunca la absoluta; sin efecto."),
        Descriptor(
            "file.open",
            Schema(
                [
                    // cu-v3-abrir-archivo: the installed application to open it with (as app.open's appId); without it,
                    // the default one.
                    String("application", maximumUtf8Bytes: 512, nonWhitespace: true),
                    String("folder", values: ["desktop", "documents", "downloads", "home", "pictures"]),
                    // molestia-ayudantes: the person asked to see it (set by the App, as app.open's), so the opened
                    // application keeps the front; a mission's file.open goes without it and stays behind.
                    Boolean("foreground"),
                    String("name", maximumUtf8Bytes: 200, nonWhitespace: true),
                ],
                ["folder", "name"]),
            OperationRisks.LowReversible,
            "file.open.shell.window.process.postread.v1",
            ToolExposure.Public,
            "Abre por nombre un archivo seguro de una carpeta conocida con su aplicación predeterminada, o con la aplicación instalada que se nombre, y verifica la ventana o el proceso que aparece."),
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
            ToolExposure.Public,
            "Localiza un archivo nombrado de forma única (por su nombre o su ruta relativa) en una carpeta conocida de Windows y devuelve una página de su texto desde offset: un archivo de texto en su codificación, o el texto que ya contiene un PDF (pypdf, sin OCR); dice qué tipo leyó, el largo total y si queda más; sin efecto."),
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
            ToolExposure.Public,
            "Escribe UTF-8 atómicamente en el sandbox o en una carpeta conocida; reemplazar exige el SHA-256 exacto observado antes y envía la versión anterior a la Papelera de reciclaje; append añade al final conservando lo que había; verifica el hash releído."),
        Descriptor(
            "filesystem.copy",
            FilesystemTransferSchema(),
            OperationRisks.LowReversible,
            "filesystem.copy.sandbox.hash.postread.v1",
            ToolExposure.Public,
            "Copia un archivo identificado dentro del sandbox y verifica su hash en destino."),
        Descriptor(
            "filesystem.create.directory",
            Schema(
                [
                    // Owner decision 2026-09-13 (DECISIONES_DUENO, point 2): a known
                    // folder may be the root instead of the sandbox.
                    String("folder", values: ["desktop", "documents", "downloads"]),
                    String("relativePath", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                ],
                ["relativePath"]),
            OperationRisks.LowReversible,
            "filesystem.create.directory.sandbox.postread.v1",
            ToolExposure.Public,
            "Crea un directorio relativo confinado al sandbox o a una carpeta conocida (escritorio, documentos, descargas) y verifica su identidad sin aceptar rutas absolutas."),
        // Auditoría semántica 2026-09-20 (REOPEN1957 H0701 «Dime cuantos archivos .py
        // hay en el directorio actual», D24): el directorio actual es la carpeta del
        // Explorador en primer plano; sin Explorador delante, el escritorio.
        Descriptor(
            "filesystem.explorer.count",
            Schema([String("extension", maximumUtf8Bytes: 16, nonWhitespace: true)], ["extension"]),
            OperationRisks.ReadOnly,
            "filesystem.explorer.count.foreground.folder.toplevel.v1",
            ToolExposure.Public,
            "Cuenta los archivos de primer nivel con la extensión dada en la carpeta que muestra la ventana del Explorador en primer plano (o en el escritorio si no hay un Explorador delante) y nombra esa carpeta sin revelar su ruta."),
        Descriptor(
            "filesystem.file.open.latest",
            Schema([String("folder", values: ["desktop", "documents", "downloads", "pictures"])], ["folder"]),
            OperationRisks.LowReversible,
            "filesystem.file.open.latest.windows.shell.process.postread.v1",
            ToolExposure.Public,
            "Abre el archivo seguro modificado mas recientemente de una carpeta conocida y verifica el proceso observado."),
        Descriptor(
            "filesystem.folder.open",
            Schema([String("folder", values: ["desktop", "documents", "downloads", "home", "pictures"])], ["folder"]),
            OperationRisks.LowReversible,
            "filesystem.folder.open.windows.shell.postread.v1",
            ToolExposure.Public,
            "Abre una carpeta conocida de Windows y verifica la ventana de Explorer observada."),
        Descriptor(
            "filesystem.hash",
            FilesystemResourceSchema(),
            OperationRisks.ReadOnly,
            "filesystem.hash.sandbox.revalidated.v1",
            ToolExposure.Public,
            "Calcula SHA-256 después de revalidar la identidad opaca del archivo."),
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
            ToolExposure.Public,
            "Busca grupos de archivos duplicados en Descargas mediante tamaño y SHA-256 sin modificarlos."),
        Descriptor(
            "filesystem.known.trash.named",
            Schema(
                [
                    String("fileName", maximumUtf8Bytes: 512, nonWhitespace: true),
                    String("folder", values: ["all_known", "desktop", "documents", "downloads"]),
                ],
                ["fileName", "folder"]),
            OperationRisks.RecoverableDelete,
            "filesystem.known.trash.named.windows.absence.v1",
            ToolExposure.Public,
            "Resuelve un archivo nombrado de forma única y lo mueve a una papelera privada después de confirmar."),
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
            ToolExposure.Public,
            "Lista entradas acotadas del sandbox y emite identificadores opacos de corta vida."),
        Descriptor(
            "filesystem.move",
            FilesystemTransferSchema(),
            OperationRisks.LowReversible,
            "filesystem.move.sandbox.hash.absence.v1",
            ToolExposure.Public,
            "Mueve un archivo identificado y verifica hash de destino y ausencia de origen."),
        Descriptor(
            "filesystem.path.ensure.absent",
            Schema([String("path", maximumUtf8Bytes: 2_048, nonWhitespace: true)], ["path"]),
            OperationRisks.RecoverableDelete,
            "filesystem.path.ensure.absent.windows.private.trash.postread.v1",
            ToolExposure.Public,
            "Verifica la ausencia de una ruta absoluta; si existe, solo mueve archivos del perfil o TEMP a una papelera privada recuperable."),
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
            ToolExposure.Public,
            "Lee UTF-8 acotado desde una identidad revalidada y devuelve su hash."),
        Descriptor(
            "filesystem.sandbox.diff.named",
            Schema(
                [
                    String("leftQuery", maximumUtf8Bytes: 512, nonWhitespace: true),
                    String("rightQuery", maximumUtf8Bytes: 512, nonWhitespace: true),
                ],
                ["leftQuery", "rightQuery"]),
            OperationRisks.ReadOnly,
            "filesystem.sandbox.diff.named.hash.snapshot.v1",
            ToolExposure.Public,
            "Compara dos archivos de texto resueltos de forma única y devuelve hashes y líneas diferentes."),
        Descriptor(
            "filesystem.sandbox.move.named",
            Schema(
                [
                    String("destinationRelativePath", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                    String("sourceFileName", maximumUtf8Bytes: 512, nonWhitespace: true),
                ],
                ["destinationRelativePath", "sourceFileName"]),
            OperationRisks.LowReversible,
            "filesystem.sandbox.move.named.hash.absence.v1",
            ToolExposure.Public,
            "Mueve un archivo de nombre único dentro del sandbox y verifica hash y ausencia del origen."),
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
            ToolExposure.Public,
            "Busca nombres dentro del sandbox sin seguir puntos de reanálisis."),
        Descriptor(
            "filesystem.trash.commit",
            Schema(
                [
                    String("reviewLabel", maximumUtf8Bytes: 512, nonWhitespace: true),
                    String("trashId", maximumLength: 38, nonWhitespace: true),
                ],
                ["reviewLabel", "trashId"]),
            OperationRisks.RecoverableDelete,
            "filesystem.trash.commit.sandbox.absence.v1",
            ToolExposure.Public,
            "Confirma una selección preparada y mueve el recurso a una papelera privada recuperable."),
        Descriptor(
            "filesystem.trash.prepare",
            FilesystemResourceSchema(),
            OperationRisks.ReadOnly,
            "filesystem.trash.prepare.sandbox.selection.v1",
            ToolExposure.Public,
            "Prepara una selección de papelera de un solo uso con etiqueta revisable."),
        Descriptor(
            "filesystem.trash.restore",
            Schema([String("restoreId", maximumLength: 40, nonWhitespace: true)], ["restoreId"]),
            OperationRisks.LowReversible,
            "filesystem.trash.restore.sandbox.postread.v1",
            ToolExposure.Public,
            "Restaura un recurso de la papelera privada si su destino original sigue libre."),
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
            ToolExposure.Public,
            "Lista el catálogo local de Steam mediante una sesión resuelta y acotada."),
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
            ToolExposure.Public,
            "Comprueba por título si un juego de Steam o de Epic Games figura en la biblioteca autenticada local y si está instalado; no descarga, no compra ni abre diálogos."),
        Descriptor(
            "game.install.cancel",
            Schema([String("appId", maximumLength: 16, nonWhitespace: true)], ["appId"]),
            OperationRisks.WorkLoss,
            "game.install.cancel.steam.postread.v1",
            ToolExposure.Public,
            "Cancela una descarga parcial exacta desde el administrador autenticado de Steam y verifica que dejó de progresar."),
        Descriptor(
            "game.install.cancel.active",
            EmptySchema(),
            OperationRisks.WorkLoss,
            "game.install.cancel.active.steam.all.postread.v1",
            ToolExposure.Public,
            "Cancela todas las descargas activas observadas en Steam y verifica que ninguna siga progresando."),
        Descriptor(
            "game.install.commit",
            Schema([String("confirmationId", maximumLength: 96, nonWhitespace: true)], ["confirmationId"]),
            OperationRisks.Installation,
            "game.install.commit.steam.job.v1",
            ToolExposure.Public,
            "Confirma una instalación preparada en una sesión Steam autenticada y verifica su job."),
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
            ToolExposure.Public,
            "Resuelve el título de un juego de Steam (sus manifiestos locales o la búsqueda pública de la tienda; o de Epic Games) a su identidad, abre la instalación por su dirección, confirma el diálogo propio de Steam y verifica la transición del manifiesto local."),
        Descriptor(
            "game.install.prepare",
            Schema([String("appId", maximumLength: 16, nonWhitespace: true)], ["appId"]),
            OperationRisks.ReadOnly,
            "game.install.prepare.steam.selection.v1",
            ToolExposure.Public,
            "Prepara la instalación de un AppID exacto sin iniciar descarga ni aceptar diálogos."),
        Descriptor(
            "game.install.status",
            Schema([String("appId", maximumLength: 16, nonWhitespace: true)], ["appId"]),
            OperationRisks.ReadOnly,
            "game.install.status.steam.snapshot.v1",
            ToolExposure.Public,
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
            ToolExposure.Public,
            "Comprueba por nombre si un juego esta instalado mediante manifiestos de Steam y Epic y verifica que exista su directorio local."),
        Descriptor(
            "game.launch",
            Schema([String("appId", maximumLength: 16, nonWhitespace: true)], ["appId"]),
            OperationRisks.LowReversible,
            "game.launch.steam.process.postread.v1",
            ToolExposure.Public,
            "Inicia un AppID poseído y verifica la identidad del proceso lanzado."),
        Descriptor(
            "game.purchase.commit",
            Schema(
                [
                    String("confirmationId", maximumLength: 96, nonWhitespace: true),
                    Integer("expectedPriceCents", 0),
                ],
                ["confirmationId", "expectedPriceCents"]),
            OperationRisks.Monetary,
            "game.purchase.commit.steam.receipt.v1",
            ToolExposure.Public,
            "Confirma una compra preparada con precio exacto; nunca se prueba contra dinero real."),
        Descriptor(
            "game.purchase.prepare",
            Schema([String("appId", maximumLength: 16, nonWhitespace: true)], ["appId"]),
            OperationRisks.ReadOnly,
            "game.purchase.prepare.steam.selection.v1",
            ToolExposure.Public,
            "Prepara una selección monetaria exacta y devuelve precio y autoridad revisables."),
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
            ToolExposure.Public,
            "Resuelve un título instalado de Steam a su AppID, abre su desinstalación por su dirección, confirma el diálogo propio de Steam y verifica que el manifiesto local ya no lo declare instalado."),
        Descriptor(
            "input.key.press",
            Schema([
                // Goal v3 punto 2: Enter o Espacio sobre el «Sí» enfocado de un aviso de
                // sobrescritura pisa el archivo igual que el clic; la misión lo marca
                // desde la vista y RiskPolicy lo confirma.
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
                    // pestaña, deshacer, recargar—. Ninguno cierra una ventana ni un
                    // proceso: cerrar una pestaña deja el navegador abierto (D16).
                    // Goal v3 punto 2: guardar, guardar como, abrir, reemplazar,
                    // cortar, la barra de menús (F10) y el menú contextual del
                    // control enfocado (Shift+F10); ninguno cierra nada.
                    "backspace", "context_menu", "control", "ctrl_a", "ctrl_c", "ctrl_f", "ctrl_h", "ctrl_k",
                    "ctrl_l", "ctrl_o", "ctrl_s", "ctrl_shift_escape", "ctrl_shift_s", "ctrl_t", "ctrl_v", "ctrl_w",
                    "ctrl_x", "ctrl_z", "delete", "end", "enter", "escape", "f10", "f5", "home", "page_down", "page_up",
                    "shift", "shift_f10", "space", "tab", "win",
                ]),
                // Revisión de V (H1): lo que Enter o Espacio pulsan según la vista del paso (el control
                // enfocado o, desde un campo, el resultado elegido de su lista) cuando pide la palabra de la
                // persona: lo marca la misión y RiskPolicy lo juzga como la etiqueta de un clic.
                String("onto", types: NullableString, maximumUtf8Bytes: 256),
                // El bucle de computer use declara cuándo Enter cae sobre un
                // compositor de mensajes con texto: esa pulsación llega a una
                // persona y el Kernel la confirma en modo normal (§2.1). Suprimir
                // pregunta salvo que el paso declare que el teclado está en un
                // campo de texto (text_field): fuera de uno borra lo seleccionado.
                String("target", types: NullableString, values: ["message_composer", "text_field"]),
                // La ventana de la misión (el hwnd de su última vista): la tecla
                // va sólo a ella; si no está delante y no se la puede traer, nada
                // se envía.
                Integer("window", 1, uint.MaxValue, types: NullableInteger),
            ], ["key"]),
            OperationRisks.LowReversible,
            "input.key.press.win32.sendinput.accepted.v1",
            ToolExposure.Public,
            "Presiona una tecla o una combinación segura (Ctrl+A/C/F/H/K/L/O/S/T/V/W/X/Z, Ctrl+Shift+S, Ctrl+Shift+Escape, F5, F10, Shift+F10) en la ventana enfocada y verifica que Windows aceptó todos los eventos SendInput; con target message_composer la pulsación de Enter se trata como un envío."),
        Descriptor(
            "input.keyboard.layout",
            Schema([String("language", values: ["spanish"])], ["language"]),
            OperationRisks.LowReversible,
            "input.keyboard.layout.win32.foreground.postread.v1",
            ToolExposure.Public,
            "Activa el teclado español en la ventana enfocada y verifica el idioma de entrada de su hilo mediante Win32."),
        Descriptor(
            "input.keyboard.open",
            EmptySchema(),
            OperationRisks.LowReversible,
            "input.keyboard.open.window.visible.postread.v1",
            ToolExposure.Public,
            "Abre el teclado en pantalla de Windows y verifica su proceso y ventana visible sin quitar el foco al control de destino."),
        Descriptor(
            "input.keyboard.status",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "input.keyboard.status.win32.foreground.read.v1",
            ToolExposure.Public,
            "Lee y verifica el idioma de entrada del hilo de la ventana enfocada mediante Win32."),
        Descriptor(
            "input.pointer.control",
            Schema([String("action", values: ["click", "move_center", "scroll_down"])], ["action"]),
            OperationRisks.LowReversible,
            "input.pointer.control.win32.postread.v1",
            ToolExposure.Public,
            "Mueve el puntero al centro, hace clic en su posición actual o desplaza hacia abajo y verifica el recibo Win32."),
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
                    // ventana de la misión tiene fuera de vista se trae a la vista por
                    // UI Automation, sin rueda ni puntero; la prueba es verlo.
                    String("label", types: NullableString, maximumUtf8Bytes: 256),
                    // La ventana de la misión (el hwnd de la vista sobre la que se
                    // decidió): la vista ya no la trae al frente, así que la rueda
                    // la trae ella; si Windows no se la da, no se mueve nada.
                    Integer("window", 1, uint.MaxValue, types: NullableInteger),
                ],
                ["amount", "direction"]),
            OperationRisks.LowReversible,
            "input.scroll.win32.wheel.surface.postread.v1",
            ToolExposure.Public,
            "Desplaza la ventana en primer plano, o el control de la última vista que nombra su índice, hacia arriba o hacia abajo la cantidad de pasos de rueda pedida y verifica que la superficie visible cambió; con label trae a la vista ese elemento de la ventana nombrada sin rueda ni puntero y verifica que se ve."),
        Descriptor(
            "input.select.all",
            EmptySchema(),
            OperationRisks.LowReversible,
            "input.select.all.focused.uia.postread.v1",
            ToolExposure.Public,
            "Selecciona todo en el control enfocado de la ventana activa y verifica la seleccion mediante UI Automation."),
        Descriptor(
            "input.text.type",
            Schema(
                [
                    // Revisión de combos-galerías (hallazgo 1): el texto sólo se elige
                    // como una entrada de la propia lista del campo (un ComboBox), por
                    // patrón; si la lista no tiene una entrada así, no cambia nada y
                    // nunca se escribe como texto libre.
                    Boolean("entry", types: NullableBoolean),
                    // Goal v3 punto 2 (formularios): el rótulo del campo que recibe el
                    // valor («Ancho», «Nombre de archivo»); la misión lo resuelve a su
                    // índice en la vista y, si no lo encuentra, no se escribe nada.
                    String("field", types: NullableString, maximumUtf8Bytes: 256),
                    // El campo de la última vista que recibe el texto (goal v3,
                    // punto 0): se le entrega sin teclado ni primer plano
                    // (SetValue o mensajes a su ventana) cuando lo acepta.
                    Integer("index", 0, VisibleViewNumbering.HighestIndex, types: NullableInteger),
                    // Poner el campo en ese valor: su contenido se reemplaza (nunca
                    // en un documento ni en una contraseña) y la prueba es el valor
                    // releído; sin el campo mismo, por teclado no se envía nada.
                    Boolean("replace", types: NullableBoolean),
                    String("text", maximumUtf8Bytes: 8_192, nonWhitespace: true),
                    // La ventana de la misión: el texto va dirigido sólo a ella
                    // (hwnd, proceso y hora de creación); por teclado, sólo
                    // mientras ella está delante, y si deja de estarlo, se para.
                    Integer("window", 1, uint.MaxValue, types: NullableInteger),
                ],
                ["text"]),
            OperationRisks.PrivacySensitive,
            "input.text.type.win32.sendinput.accepted.v1",
            ToolExposure.Public,
            "Escribe texto Unicode literal en el control enfocado y verifica que Windows aceptó cada evento SendInput."),
        Descriptor(
            "input.visible.click",
            // Motor de computer use (CONTRATO_VISTA_ACCION.md §2): el clic por la
            // identidad que la vista entregó (índice o RuntimeId) cuando la etiqueta
            // se repite; la etiqueta sigue siendo obligatoria, debe nombrar ese
            // mismo control y es lo que el revisor ve.
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
                    // Ronda 20b, palanca 6 (revisión, hallazgo 1, v3-40 b): collapse cierra
                    // por su ExpandCollapse la lista que la misión abrió y dejó abierta
                    // al no llegar; sólo la manda la App, nunca el modelo. Revisión 2
                    // (hallazgo 3): sin ExpandCollapse abierto, el popup nacido en la
                    // misión junto al control se cierra con Escape a su propia ventana.
                    // Revisión 3 (hallazgo 1): ese cierre es dismiss, que nunca toca el
                    // ExpandCollapse del control; collapse nunca pliega una rama de árbol.
                    String("manner", types: NullableString, values: ["collapse", "dismiss", "double", "menu", "open"]),
                    // Goal v3 punto 0, arreglo 3 (ráfaga compuesta): el destino que se
                    // escribe en lo que el clic abre y cuyo resultado se elige por su
                    // nombre, en una sola ráfaga dentro de una pausa de la persona.
                    String("search", types: NullableString, maximumUtf8Bytes: 256),
                    // La ventana de la misión (el hwnd de la vista sobre la que se
                    // decidió): el clic la trae al frente y actúa sólo en ella; si
                    // Windows no se la da, no se pulsa nada.
                    Integer("window", 1, uint.MaxValue, types: NullableInteger),
                ],
                ["label"]),
            OperationRisks.ExternalCommunication,
            "input.visible.click.windows.uia.invoke.postread.v2",
            ToolExposure.Public,
            "Invoca un único control visible por etiqueta, o por el índice o la identidad que dio la vista, en la ventana en primer plano (UIA, luego OCR, luego visión) y exige postlectura: seleccionado, conmutado, desaparecido o superficie cambiada."),
        Descriptor(
            "input.visible.controls",
            // Motor de computer use (CONTRATO_VISTA_ACCION.md §1): la vista compacta
            // —índice, tipo, etiqueta, estado, rectángulo, zona y color de cada
            // control, texto por zonas, título y proceso— y la espera acotada de
            // una etiqueta que la aplicación aún no dibujó.
            Schema(
                [
                    // La aplicación de la misión: la ventana cuyo título la nombra es
                    // la superficie mientras su proceso no se conoce o no muestra
                    // ventana; «el navegador», la de delante del navegador de la persona.
                    String("application", types: NullableString, maximumUtf8Bytes: 128),
                    // Ronda 21, destino por contenido: sin aplicación ni ventana de la misión, las ventanas del
                    // escritorio (de arriba abajo) con la firma de su árbol; la App busca en cuál está lo que el
                    // pedido nombra. No se trae nada al frente ni se captura nada.
                    Boolean("candidates", types: NullableBoolean),
                    // Ronda 26: si la aplicación nombrada no tiene ventana, la mirada sólo dice qué ventana está
                    // delante (título, proceso), sin árbol, captura ni texto: sobre eso se decide abrirla.
                    Boolean("identityIfAbsent", types: NullableBoolean),
                    Boolean("includeText", types: NullableBoolean),
                    // Goal v3 ventana-misión: las ventanas que la misión sabe que no son suyas (otras del
                    // mismo proceso, vistas al atarse); la mirada nunca las toma por la superficie.
                    new OperationArgumentProperty(
                        "known",
                        OperationJsonType.Array | OperationJsonType.Null,
                        itemTypes: OperationJsonType.Integer,
                        maximumItems: 256),
                    Integer("limit", 1, VisibleViewNumbering.Cap),
                    // Encargo IMP4: the written lines with their boxes, read from the window's own drawing.
                    Boolean("lines", types: NullableBoolean),
                    // El proceso de la aplicación que la misión acaba de abrir: su
                    // ventana es la superficie aunque otra tenga el foco.
                    Integer("processId", 1, int.MaxValue, types: NullableInteger),
                    // La app abierta en frío todavía arranca: si se activó sola, el frente vuelve a la
                    // ventana de la persona (computer use v3, punto 1).
                    Boolean("starting", types: NullableBoolean),
                    // Encargo IMP3: the cut of a look keeps the last entries of the window's tree (a conversation's
                    // newest messages), read once at the end of a mission that answers a question.
                    Boolean("tail", types: NullableBoolean),
                    String("waitForLabel", types: NullableString, maximumUtf8Bytes: 256),
                    // Ronda 21: las palabras del objetivo del paso (y sus otros nombres) que la mente ya usa para
                    // ordenar la vista; con ellas el corte de los sesenta guarda un cupo acotado para los controles que
                    // las nombran. Sin ellas (las lecturas que no son de una misión) la vista es la de siempre.
                    new OperationArgumentProperty(
                        "wanted",
                        OperationJsonType.Array | OperationJsonType.Null,
                        itemTypes: OperationJsonType.String,
                        maximumItems: 24,
                        itemMaximumUtf8Bytes: 64,
                        itemNonWhitespace: true),
                    // Goal v3 ventana-misión: las ventanas a las que la misión está atada (la que abrió,
                    // creó o nombró la persona, y las que nacieron de ella); la mirada sólo lee ésas.
                    new OperationArgumentProperty(
                        "windows",
                        OperationJsonType.Array | OperationJsonType.Null,
                        itemTypes: OperationJsonType.Integer,
                        maximumItems: 16),
                ],
                []),
            OperationRisks.ReadOnly,
            "input.visible.controls.windows.uia.snapshot.v2",
            ToolExposure.Public,
            "Vista compacta de la ventana en primer plano: hasta sesenta controles visibles y habilitados con índice, tipo, etiqueta, estado, rectángulo, zona y color, el texto leído por zonas, el título y el proceso; no toca nada."),
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
            ToolExposure.Public,
            "Controla una sesión SMTC seleccionada y verifica su estado posterior."),
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
            ToolExposure.Public,
            "Reproduce un resultado musical exacto en una sesión autenticada y verifica now-playing."),
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
            ToolExposure.Public,
            "Busca y reproduce el primer resultado musical pertinente en Spotify y verifica now-playing."),
        Descriptor(
            "media.play.youtube",
            Schema([String("query", maximumUtf8Bytes: 1_024, nonWhitespace: true)], ["query"]),
            OperationRisks.ExternalCommunication,
            "media.play.youtube.cdp.video.postread.v1",
            ToolExposure.Public,
            "Busca en YouTube, reproduce un resultado de video y verifica el elemento multimedia y su estado posterior."),
        Descriptor(
            "media.seek.relative",
            Schema([Integer("seconds", -3_600, 3_600)], ["seconds"]),
            OperationRisks.LowReversible,
            "media.seek.relative.smtc.timeline.postread.v1",
            ToolExposure.Public,
            "Adelanta o retrocede la sesión SMTC actual y verifica la posición final en su timeline."),
        Descriptor(
            "media.status",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "media.status.smtc.read.v1",
            ToolExposure.Public,
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
            ToolExposure.Public,
            "Corrige una memoria local mediante comparación y sustitución."),
        Descriptor(
            "memory.disable",
            Schema(
                [Boolean("enabled", constant: false), Version()],
                ["enabled", "version"]),
            OperationRisks.LowReversible,
            "memory.disable.protected.status.v1",
            ToolExposure.Public,
            "Deshabilita nuevas lecturas y escrituras de memoria local."),
        Descriptor(
            "memory.enable",
            Schema(
                [Boolean("enabled", constant: true), Version()],
                ["enabled", "version"]),
            OperationRisks.PrivacySensitive,
            "memory.enable.protected.status.v1",
            ToolExposure.Public,
            "Habilita la memoria privada local con confirmación explícita."),
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
            ToolExposure.Public,
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
            ToolExposure.Public,
            "Elimina memorias locales del alcance confirmado."),
        Descriptor(
            "memory.list",
            Schema(
                [Integer("limit", 1, 100), Integer("offset", 0, 512), Version()],
                ["limit", "offset", "version"]),
            OperationRisks.ReadOnly,
            "memory.list.protected.page.v1",
            ToolExposure.Public,
            "Lista memoria local visible de forma acotada."),
        Descriptor(
            "memory.recall",
            Schema(
                [
                    String("scope", values: ["all", "exact", "kind"]),
                    String("selector", types: NullableString, maximumUtf8Bytes: 256),
                    Version(),
                ],
                ["scope", "selector", "version"]),
            OperationRisks.ReadOnly,
            "memory.recall.protected.records.v1",
            ToolExposure.Public,
            "Recupera memorias locales visibles para la sesión actual."),
        Descriptor(
            "memory.save",
            MemorySaveSchema(["normal", "personal"]),
            OperationRisks.LowReversible,
            "memory.save.protected.postread.v1",
            ToolExposure.Public,
            "Guarda una memoria explícita local no secreta."),
        Descriptor(
            "memory.sensitive.save",
            MemorySaveSchema(["secret", "sensitive"]),
            OperationRisks.PrivacySensitive,
            "memory.sensitive.save.protected.postread.v1",
            ToolExposure.Public,
            "Guarda una memoria sensible local después de confirmación."),
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
            ToolExposure.Public,
            "Elimina únicamente la memoria temporal de la sesión actual."),
        Descriptor(
            "memory.status",
            Schema([Version()], ["version"]),
            OperationRisks.ReadOnly,
            "memory.status.protected.snapshot.v1",
            ToolExposure.Public,
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
            ToolExposure.Public,
            "Abre el chat del destinatario en el cliente de escritorio nombrado (WhatsApp o Discord), deja el mensaje escrito en el cuadro de redacción, lo corrobora en pantalla y se detiene sin enviarlo: la persona lo envía."),
        Descriptor(
            "message.recipient.resolve",
            Schema(
                [
                    // Auditoría semántica 2026-09-20 (REOPEN1993 grupo E, D24): con «any» el
                    // destinatario se busca en los clientes (el canal recordado, WhatsApp y
                    // Discord); único → resuelto y recordado; en ninguno o en varios, se dice.
                    String("channel", values: ["any", "discord", "whatsapp"]),
                    String("recipient", maximumUtf8Bytes: 512, nonWhitespace: true),
                ],
                ["channel", "recipient"]),
            OperationRisks.ReadOnly,
            "message.recipient.resolve.session.identity.v1",
            ToolExposure.Public,
            "Resuelve un único destinatario autenticado (en el cliente nombrado o, con «any», en el que lo tenga: el recordado, WhatsApp o Discord) y emite un identificador revisable."),
        Descriptor(
            "message.send",
            Schema(
                [
                    String("recipientId", maximumLength: 128, nonWhitespace: true),
                    String("text", maximumUtf8Bytes: 16_384),
                ],
                ["recipientId", "text"]),
            OperationRisks.ExternalCommunication,
            "message.send.session.receipt.v1",
            ToolExposure.Public,
            "Envía un mensaje a un destinatario resuelto y exige recibo del provider oficial."),
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
            ToolExposure.Public,
            "Decisión del dueño §6 (y §3 del 18-09 para el correo): envío real a sus canales de prueba. El destino se fuerza SIEMPRE al canal seguro del dueño (WhatsApp grupo Música, Discord mensaje directo Ron92, correo a la casilla de pruebas del dueño), nunca al destinatario nombrado; en WhatsApp/Discord escribe el texto, pulsa enviar y verifica la entrega por OCR; en correo envía por el Outlook del dueño y verifica la copia en Elementos enviados; el recibo guarda el destinatario pedido y el destino real forzado."),
        // Motor general de computer use (plan post-goal Fase 4, D21;
        // documentacion/computer-use/CONTRATO_VISTA_ACCION.md §4). El shell mira la
        // ventana en primer plano (vista compacta), la mente elige UN paso del
        // repertorio cerrado, el core ejecuta esa primitiva con su postlectura y
        // se vuelve a mirar, hasta que la comprobación de éxito se cumple o se
        // agota el presupuesto. Cada paso lleva el riesgo de su primitiva. El
        // core solo no puede correr el bucle: sin el shell y la mente delante
        // contesta que le faltan. Una misión encadenada trae sus sub-objetivos
        // en orden (steps): cada uno con su aplicación y su comprobación.
        Descriptor(
            "mission.computer.use",
            Schema(
                [
                    String("application", types: NullableString, maximumUtf8Bytes: 128),
                    Integer("budgetSteps", 1, 30, types: NullableInteger),
                    // Integración ronda 5 (seguridad): sin aplicación, la ventana de delante es de la persona y la
                    // misión no actúa en ella, salvo que la persona la nombre («en esta ventana…»).
                    Boolean("frontWindow"),
                    String("goal", maximumUtf8Bytes: 512, nonWhitespace: true),
                    // Ronda 21, destino por contenido: sin aplicación, lo que el pedido nombra de la ventana donde
                    // ocurre (un menú, un cuadro, un panel por su nombre; una selección; un documento sin guardar).
                    // La App busca la única ventana visible que lo muestra; con varias o ninguna, pregunta.
                    // Ronda 24 (pasada r23 t-form-4, t-drag-2): los diálogos nombrados («el cuadro de diálogo de
                    // Fuente») van aparte, porque uno todavía cerrado no se ve; los nombres citados («la diapositiva
                    // «Tres»») son contenido: suman a una ventana que ya encaja y nunca la habilitan solos.
                    new OperationArgumentProperty(
                        "referentDialogs",
                        OperationJsonType.Array | OperationJsonType.Null,
                        itemTypes: OperationJsonType.String,
                        maximumItems: 8,
                        itemMaximumUtf8Bytes: 64,
                        itemNonWhitespace: true),
                    new OperationArgumentProperty(
                        "referentItems",
                        OperationJsonType.Array | OperationJsonType.Null,
                        itemTypes: OperationJsonType.String,
                        maximumItems: 8,
                        itemMaximumUtf8Bytes: 64,
                        itemNonWhitespace: true),
                    new OperationArgumentProperty(
                        "referentLabels",
                        OperationJsonType.Array | OperationJsonType.Null,
                        itemTypes: OperationJsonType.String,
                        maximumItems: 8,
                        itemMaximumUtf8Bytes: 64,
                        itemNonWhitespace: true),
                    Boolean("referentSelection", types: NullableBoolean),
                    new OperationArgumentProperty(
                        "steps",
                        OperationJsonType.Array | OperationJsonType.Null,
                        minimumItems: 1,
                        // Goal v3 punto 2: tareas largas de diez sub-objetivos (semantic/missions.py MAX_STEPS,
                        // fijados iguales en tests/test_cu_v3_tipos_lectura.py).
                        maximumItems: 10,
                        itemSchema: Schema(
                            [
                                String("application", types: NullableString, maximumUtf8Bytes: 128),
                                // Ronda 20b, revisión 2: el formulario es una unidad. Sus campos vinculados y su botón
                                // por defecto llevan la comprobación del formulario entero (semantic/missions.py
                                // _with_form_checks), que la mente vuelve a evaluar antes de aceptar.
                                String("formCheck", types: NullableString, maximumUtf8Bytes: 512),
                                String("goal", maximumUtf8Bytes: 512, nonWhitespace: true),
                                // Estabilización L (límites de partida): el sub-objetivo que es un límite declarado
                                // (semantic/limits.py, leído sobre su acto) no se intenta: la App para al llegar.
                                String("limit", types: NullableString, maximumUtf8Bytes: 32),
                                // El dispositivo que necesita el lugar (data computerUse.limits.devices): la App lo lee
                                // antes del sub-objetivo y para si el equipo no lo tiene.
                                String("requires", types: NullableString, maximumUtf8Bytes: 32),
                                String("successCheck", types: NullableString, maximumUtf8Bytes: 512),
                            ],
                            ["goal"])),
                    String("successCheck", types: NullableString, maximumUtf8Bytes: 512),
                ],
                ["goal"]),
            OperationRisks.LowReversible,
            "mission.computer.use.shell.loop.v1",
            ToolExposure.Public,
            "Cumple un objetivo dentro de cualquier aplicación —o una cadena ordenada de sub-objetivos, cada uno en su aplicación— mirando la ventana en primer plano, eligiendo un paso a la vez (pulsar, escribir, tecla, desplazar, abrir) y verificando cada uno hasta ver la comprobación de éxito o agotar el presupuesto.",
            requiresObservedEffect: false),
        Descriptor(
            "network.dns.status",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "network.dns.status.windows.interfaces.secondread.v1",
            ToolExposure.Public,
            "Lee los servidores DNS de las interfaces activas de Windows y exige dos observaciones coherentes."),
        Descriptor(
            "network.ip.list",
            EmptySchema(),
            // Owner decision 2026-09-13 (DECISIONES_DUENO, point 6): listing the
            // machine's own addresses no longer asks for confirmation.
            OperationRisks.ReadOnly,
            "network.ip.list.windows.unicast.secondread.v1",
            ToolExposure.Public,
            "Enumera direcciones IP unicast activas del equipo y solo devuelve valores presentes en dos observaciones consecutivas, sin exponer nombres de interfaz."),
        Descriptor(
            "network.ping",
            Schema(
                [String("host", maximumUtf8Bytes: 253, nonWhitespace: true)],
                ["host"]),
            OperationRisks.ReadOnly,
            "network.ping.icmp.reply.receipt.v1",
            ToolExposure.Public,
            "Envía un único eco ICMP acotado a un host explícito e informa su recibo, latencia o fallo de resolución."),
        Descriptor(
            "network.port.list",
            Schema([Integer("limit", 1, 100)], []),
            OperationRisks.ReadOnly,
            "network.port.list.windows.listeners.secondread.v1",
            ToolExposure.Public,
            "Enumera puertos TCP y UDP locales en escucha y solo devuelve endpoints presentes en dos observaciones consecutivas."),
        Descriptor(
            "network.status",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "network.status.interfaces.secondread.v1",
            ToolExposure.Public,
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
            ToolExposure.Public,
            "Crea una nota privada local y verifica su relectura."),
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
            ToolExposure.Public,
            "Enumera notas privadas locales activas o enviadas a la papelera."),
        Descriptor(
            "note.read",
            NoteSelectorSchema(),
            OperationRisks.ReadOnly,
            "note.read.local.identity.v1",
            ToolExposure.Public,
            "Lee una nota privada local por su identificador o título exacto."),
        Descriptor(
            "note.restore",
            NoteSelectorSchema(),
            OperationRisks.LowReversible,
            "note.restore.local.postread.v1",
            ToolExposure.Public,
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
            ToolExposure.Public,
            "Busca texto en notas locales y verifica por relectura cada resultado acotado."),
        Descriptor(
            "note.trash",
            NoteSelectorSchema(),
            OperationRisks.RecoverableDelete,
            "note.trash.local.postread.v1",
            ToolExposure.Public,
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
            ToolExposure.Public,
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
            ToolExposure.Public,
            "Ejecuta OCR local sobre una captura identificada y un language pack disponible.",
            requiresObservedEffect: false),
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
            ToolExposure.Public,
            "Crea un documento mediante un adapter Office autenticado y devuelve su identidad."),
        Descriptor(
            "office.document.read",
            Schema([String("documentId", maximumLength: 128, nonWhitespace: true)], ["documentId"]),
            OperationRisks.ReadOnly,
            "office.document.read.adapter.snapshot.v1",
            ToolExposure.Public,
            "Lee una proyección estructurada de un documento identificado mediante el adapter oficial."),
        Descriptor(
            "package.install.commit",
            Schema([String("confirmationId", maximumLength: 96, nonWhitespace: true)], ["confirmationId"]),
            OperationRisks.Installation,
            "package.install.commit.winget.receipt.v1",
            ToolExposure.Public,
            "Confirma una instalación preparada mediante winget y verifica su recibo."),
        Descriptor(
            "package.install.prepare",
            Schema(
                [
                    String("packageId", maximumUtf8Bytes: 256, nonWhitespace: true),
                    String("version", types: NullableString, maximumLength: 64),
                ],
                ["packageId"]),
            OperationRisks.ReadOnly,
            "package.install.prepare.winget.selection.v1",
            ToolExposure.Public,
            "Resuelve un paquete winget exacto, o el único paquete que lleva el nombre pedido, y prepara una confirmación sin instalar."),
        // Auditoría semántica 2026-09-20 (REOPEN1993, grupo G): «desinstalá Discord»
        // es una desinstalación real por el gestor de paquetes, verificada por su
        // ausencia después; pierde lo instalado, así que confirma en modo normal.
        Descriptor(
            "package.uninstall",
            Schema([String("packageId", maximumUtf8Bytes: 256, nonWhitespace: true)], ["packageId"]),
            OperationRisks.WorkLoss,
            "package.uninstall.winget.absence.postread.v1",
            ToolExposure.Public,
            "Desinstala mediante winget el paquete instalado que se nombra (por su id exacto o su nombre único) y verifica su ausencia en la lista de paquetes instalados."),
        Descriptor(
            "peripheral.list",
            Schema([String("kind", values:
                ["all", "keyboard", "mouse", "printer", "scanner", "usb"])], []),
            OperationRisks.ReadOnly,
            "peripheral.list.hardware.snapshot.v1",
            ToolExposure.Public,
            "Enumera periféricos conectados, incluidos mouse y teclado, mediante APIs de Windows; puede filtrar por tipo."),
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
            ToolExposure.Public,
            "Envía un documento identificado a una impresora resuelta y verifica el job."),
        Descriptor(
            "peripheral.scan",
            Schema([String("deviceId", maximumLength: 128, nonWhitespace: true)], ["deviceId"]),
            OperationRisks.PrivacySensitive,
            "peripheral.scan.hardware.capture.v1",
            ToolExposure.Public,
            "Captura desde un escáner resuelto y devuelve una identidad privada verificable."),
        Descriptor(
            "routine.delete",
            Schema(
                [
                    Integer("expectedRevision", 1),
                    String("reviewLabel", maximumUtf8Bytes: 640, nonWhitespace: true),
                    String("routineId", maximumLength: 36, nonWhitespace: true),
                ],
                ["expectedRevision", "reviewLabel", "routineId"]),
            OperationRisks.RecoverableDelete,
            "routine.delete.local.postread.v1",
            ToolExposure.Public,
            "Elimina de forma recuperable una rutina ya seleccionada; nunca ejecuta sus pasos."),
        Descriptor(
            "routine.list",
            Schema([Boolean("includeDeleted"), Integer("limit", 1, 50)], []),
            OperationRisks.ReadOnly,
            "routine.list.local.postread.v1",
            ToolExposure.Public,
            "Lista definiciones de rutina creadas por el controlador confiable."),
        Descriptor(
            "routine.phrase.create",
            Schema(
                [
                    String("action", values: ["capture.screenshot", "media.control"]),
                    String("name", maximumUtf8Bytes: 640, nonWhitespace: true),
                    String("phrase", maximumUtf8Bytes: 640, nonWhitespace: true),
                ],
                ["name", "phrase"]),
            OperationRisks.LowReversible,
            "routine.phrase.create.local.postread.v1",
            ToolExposure.Public,
            "Crea una rutina local acotada de reproducción o captura al oir una frase exacta."),
        Descriptor(
            "routine.read",
            Schema(
                [
                    Boolean("includeDeleted"),
                    String("routineId", maximumLength: 36, nonWhitespace: true),
                ],
                ["routineId"]),
            OperationRisks.ReadOnly,
            "routine.read.local.identity.v1",
            ToolExposure.Public,
            "Lee metadatos de una rutina exacta sin ejecutarla."),
        Descriptor(
            "routine.resolve.exact",
            Schema(
                [
                    Boolean("includeDeleted"),
                    String("name", maximumUtf8Bytes: 640, nonWhitespace: true),
                ],
                ["name"]),
            OperationRisks.ReadOnly,
            "routine.resolve.exact.local.identity.v1",
            ToolExposure.Public,
            "Resuelve por nombre literal una rutina y emite autoridad CAS sin exponer inputs."),
        Descriptor(
            "routine.restore",
            RoutineCasSchema(),
            OperationRisks.LowReversible,
            "routine.restore.local.postread.v1",
            ToolExposure.Public,
            "Restaura deshabilitada una rutina eliminada; no la ejecuta."),
        Descriptor(
            "routine.set.enabled",
            Schema(
                [
                    Boolean("enabled"),
                    Integer("expectedRevision", 1),
                    String("routineId", maximumLength: 36, nonWhitespace: true),
                ],
                ["enabled", "expectedRevision", "routineId"]),
            OperationRisks.LowReversible,
            "routine.set.enabled.local.postread.v1",
            ToolExposure.Public,
            "Activa o desactiva metadatos de una rutina bajo CAS sin ejecutarla."),
        // Auditoría semántica 2026-09-20 (REOPEN1993, comandos; D11): «ejecuta ls»,
        // «ejecuta pytest» se corren de verdad en una consola sin perfil, con plazo y
        // salida acotados; lo destructivo no se corre por aquí (código propio).
        // BAXY Renew (2026-10-15): una sola operación para lo que BAXY hace sonar después (alarmas y recordatorios), como
        // cron de OpenClaw y la consolidación de herramientas que recomienda Anthropic. Sustituye a notification.* y a
        // reminder.* (éstos sólo guardaban un registro que nadie hacía sonar). La hora es la de la persona: minutos
        // desde ahora o una hora local; el modelo no escribe UTC (e2e E004: dueUtc mal escrito y 15 reintentos).
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
            ToolExposure.Public,
            "Programa, lista o cancela alarmas y recordatorios audibles de BAXY (o diagnostica por qué no sonaron) en el Programador de tareas de Windows: al crear, a los minutos o segundos indicados o a una hora local (HH:mm o fecha y hora), única o diaria u horaria; al cancelar, el de esa hora local o el último; y verifica la tarea en Windows."),
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
            ToolExposure.Public,
            "Ejecuta un comando de consola en PowerShell sin perfil, en la carpeta conocida indicada (desktop, documents, downloads o una subcarpeta) o, sin carpeta, en una carpeta de trabajo propia y vacía del producto, con 60 segundos de plazo, y devuelve su código de salida y su salida tal cual acotada; lo que no sólo lee (escribe, borra, instala, envía o corre un programa) se confirma antes con el comando exacto."),
        Descriptor(
            "software.python.package.status",
            Schema([String("package")], ["package"]),
            OperationRisks.ReadOnly,
            "software.python.package.status.pip.show.read.v1",
            ToolExposure.Public,
            "Lee si un paquete de Python está instalado en cada instalación de Python registrada en Windows (pip show por instalación: instalada o no, versión del paquete, pip disponible) sin instalar ni cambiar nada; sin efecto."),
        Descriptor(
            "software.python.status",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "software.python.status.windows.registry.pep514.read.v1",
            ToolExposure.Public,
            "Lee las instalaciones de Python registradas en Windows (claves PEP 514 del registro: versión, nombre y ejecutable) sin ejecutar nada; sin efecto."),
        Descriptor(
            "storage.removable.list",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "storage.removable.list.driveinfo.read.v1",
            ToolExposure.Public,
            "Lee las unidades extraíbles conectadas ahora (pendrives, discos USB: letra, etiqueta, espacio libre y total) sin copiar ni cambiar nada; sin efecto."),
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
            ToolExposure.Public,
            "Navega una sesión autenticada de streaming a un recurso exacto y verifica su URI."),
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
            ToolExposure.Public,
            "Busca y reproduce un título en una sesión autenticada de Netflix, Disney+ o HBO Max y verifica que el video avanza."),
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
            ToolExposure.Public,
            "Consulta fallos y bloqueos recientes de aplicaciones en el registro Application de Windows y solo devuelve eventos con RecordId presentes en dos observaciones."),
        Descriptor(
            "system.identity",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "system.identity.windows.environment.secondread.v1",
            ToolExposure.Public,
            "Lee la cuenta de Windows bajo la que se ejecuta BAXY: su dominio y nombre de usuario, mediante dos observaciones coherentes. No identifica a la persona ni recupera su nombre dicho en conversación."),
        Descriptor(
            "system.power",
            Schema([String("action", values: ["lock", "restart", "shutdown", "signout", "sleep"])], ["action"]),
            OperationRisks.WorkLoss,
            "system.power.windows.transition.receipt.v1",
            ToolExposure.Public,
            "Solicita una transición confirmada de bloqueo, cierre de sesión o energía mediante la API oficial de Windows y exige su recibo de aceptación."),
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
            ToolExposure.Public,
            "Enumera procesos locales acotados por CPU, memoria o nombre y verifica PID, nombre y tiempo de creacion con dos observaciones; no expone rutas ni argumentos."),
        Descriptor(
            "system.process.terminate.named",
            Schema([String("name", maximumLength: 128, nonWhitespace: true)], ["name"]),
            OperationRisks.WorkLoss,
            "system.process.terminate.named.windows.original.identity.absence.postread.v1",
            ToolExposure.Public,
            "Fuerza el cierre de un proceso por nombre ejecutable exacto, conserva sus identidades observadas y verifica que las identidades originales desaparecieron; acepta identidades nuevas creadas por reinicio automatico y requiere confirmacion por posible perdida de trabajo."),
        Descriptor(
            "system.recyclebin.empty",
            EmptySchema(),
            OperationRisks.WorkLoss,
            "system.recyclebin.empty.windows.zero.count.postread.v1",
            ToolExposure.Public,
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
            ToolExposure.Public,
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
                            "do_not_disturb", "night_light",
                        ]),
                    Integer("value", 0, 100),
                ],
                ["setting", "value"]),
            OperationRisks.PrivacySensitive,
            "system.settings.set.windows.postread.v1",
            ToolExposure.Public,
            "Cambia un ajuste permitido mediante API oficial (brillo, no molestar, luz nocturna o modo avión sobre todas las radios) o un ajuste de BAXY (su modo accesible; apagar el modo bypass) y verifica su postlectura."),
        Descriptor(
            "system.settings.status",
            Schema([String("setting", values: ["airplane_mode", "brightness"])], ["setting"]),
            OperationRisks.ReadOnly,
            "system.settings.status.windows.monitor.brightness.secondread.v1",
            ToolExposure.Public,
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
                        "gpu_identity",
                        "gpu_usage",
                        "memory",
                        "os",
                        "os_memory",
                        "summary",
                    ])],
                []),
            OperationRisks.ReadOnly,
            "system.status.windows.measurement.v1",
            ToolExposure.Public,
            "Mide CPU, memoria, disco, batería, GPU y Windows sin modificar el equipo."),
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
            ToolExposure.Public,
            "Lee la fecha y hora actuales, la hora UTC y el desfase local mediante dos observaciones coherentes; con un lugar o una zona horaria nombrados, también el desfase de esa zona en ese instante."),
        Descriptor(
            "task.complete",
            TaskCasSchema(),
            OperationRisks.LowReversible,
            "task.complete.local.postread.v1",
            ToolExposure.Public,
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
            ToolExposure.Public,
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
            ToolExposure.Public,
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
            ToolExposure.Public,
            "Lista de forma acotada tareas locales abiertas, completadas o eliminadas."),
        Descriptor(
            "task.reopen",
            TaskCasSchema(),
            OperationRisks.LowReversible,
            "task.reopen.local.postread.v1",
            ToolExposure.Public,
            "Reabre una tarea completada usando identidad y versión exactas."),
        Descriptor(
            "task.resolve.exact",
            Schema(
                [
                    Boolean("includeDeleted"),
                    String("title", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                ],
                ["title"]),
            OperationRisks.ReadOnly,
            "task.resolve.exact.local.identity.v1",
            ToolExposure.Public,
            "Resuelve un único título literal y emite autoridad CAS sin exponer detalles."),
        Descriptor(
            "task.restore",
            TaskCasSchema(),
            OperationRisks.LowReversible,
            "task.restore.local.postread.v1",
            ToolExposure.Public,
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
            ToolExposure.Public,
            "Busca en título y detalles de tareas locales sin crear índices de texto plano."),
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
            ToolExposure.Public,
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
            ToolExposure.Public,
            "Describe una captura identificada mediante un VLM configurado sin aceptar rutas arbitrarias."),
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
                    // marca el habla de la persona (código ISO de dos letras), una pista para desempatar entre
                    // lugares homónimos de tamaño comparable; nunca elige un lugar mucho menor ni pasa sobre la
                    // región dicha.
                    String("dialectCountry", types: NullableString, values: ["AR", "CL", "CO", "ES", "MX", "VE"]),
                    String("location", types: NullableString, maximumUtf8Bytes: 128),
                ],
                []),
            OperationRisks.ReadOnly,
            "weather.current.openmeteo.read.v1",
            ToolExposure.Public,
            "Lee el clima actual y el pronóstico de mañana del lugar nombrado, o de la ubicación de este PC si no se nombra ninguno, desde un servicio público sin clave, y devuelve temperatura, sensación térmica, estado del cielo, viento, humedad, probabilidad de lluvia, horas de salida y puesta del sol, calidad del aire y el lugar leído (la ciudad donde está este PC cuando no se nombra ninguno)."),
        // Auditoría semántica 2026-09-20 (REOPEN1993, grupo N): la encuesta pide las
        // noticias, no nombres de portales. Titulares del día o de un tema nombrado
        // desde un canal RSS público, cada uno con su medio y su hora.
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
                    // REOPEN1957 H0069 «Tienes algun meme?» (D11): with a query and no
                    // address, the first image the search engine lists is downloaded.
                    String("query", types: NullableString, maximumUtf8Bytes: 200),
                    String("url", types: NullableString, maximumUtf8Bytes: 2_048),
                ],
                []),
            OperationRisks.PrivacySensitive,
            "web.download.http.file.size.postread.v1",
            ToolExposure.Public,
            "Descarga un archivo o una imagen de una dirección web (o, con una consulta y sin dirección, la primera imagen que lista el buscador) a una carpeta conocida (Descargas si no se nombra) y verifica el archivo escrito; de una página descarga la imagen de portada que la página anuncia."),
        // BAXY Renew, herramientas de agente (2026-10-15): leer una página como texto, como web_fetch de OpenClaw,
        // WebFetch de Claude Code o VisitWebpage de smolagents. Sólo una dirección pública por GET, sin cookies ni
        // nada de la persona (SearchPageReader); lo que entra es información, no sale nada suyo.
        Descriptor(
            "web.fetch",
            Schema(
                [
                    Integer("maximumCharacters", 500, 20_000),
                    String("url", maximumUtf8Bytes: 2_048, nonWhitespace: true),
                ],
                ["url"]),
            OperationRisks.ReadOnly,
            "web.fetch.public.http.text.v1",
            ToolExposure.Public,
            "Lee una página web pública (http o https) como texto, sin cookies ni datos de la persona, y devuelve su título, la dirección final y el texto acotado."),
        Descriptor(
            "web.news.headlines",
            Schema(
                [
                    Integer("limit", 1, 10, types: NullableInteger),
                    String("topic", types: NullableString, maximumUtf8Bytes: 128),
                ],
                []),
            OperationRisks.ReadOnly,
            "web.news.headlines.googlenews.rss.read.v1",
            ToolExposure.Public,
            "Lee los titulares del día, o los de un tema nombrado, desde un canal público de noticias y devuelve cada titular tal cual con su medio, su hora y su enlace."),
        Descriptor(
            "web.search",
            Schema(
                [
                    // Uso real v3 tanda 1 «quien gano el mundial del 2014» → «Brasil ganó…»: la mente
                    // da los comienzos de palabra con que una página dice lo preguntado (quién ganó,
                    // dirigió…); si ningún fragmento los trae, se lee la primera fuente pertinente.
                    String("answerWords", types: NullableString, maximumUtf8Bytes: 512),
                    // Y las palabras enteras que empiezan así pero nombran otra cosa («campeonato»,
                    // «championship»): el fragmento que sólo las trae no dice quién ganó.
                    String("answerWordsNot", types: NullableString, maximumUtf8Bytes: 256),
                    Integer("limit", 1, 20),
                    // Uso real 2026-10-07 «un top 3 peliculas de suspenso del 2026»: la mente
                    // dice que se pide un listado (limit = cuántos); el proveedor no lee palabras.
                    Boolean("listing", types: NullableBoolean),
                    // Uso real tanda 4c: «cerca de mí», «en mi ciudad» se buscan con
                    // la ciudad de este PC (sólo su nombre) añadida a la consulta.
                    Boolean("nearby", types: NullableBoolean),
                    String("query", maximumUtf8Bytes: 2_000, nonWhitespace: true),
                ],
                ["query"]),
            OperationRisks.ReadOnly,
            "web.search.provider.results.v1",
            ToolExposure.Public,
            "Busca mediante un proveedor web configurado y devuelve resultados estructurados acotados; con nearby, busca cerca de la ciudad donde está este PC."),
        Descriptor(
            "wifi.connect",
            Schema([String("profileId", maximumLength: 128, nonWhitespace: true)], ["profileId"]),
            OperationRisks.PrivacySensitive,
            "wifi.connect.wlan.profile.postread.v1",
            ToolExposure.Public,
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
            ToolExposure.Public,
            "Resuelve de forma única un perfil WLAN guardado por el nombre indicado (o por el lugar asociado antes: casa, trabajo, oficina), lo conecta, verifica el estado sin exponer credenciales y recuerda la asociación lugar→red cuando se dan ambos."),
        Descriptor(
            "wifi.disconnect",
            EmptySchema(),
            OperationRisks.PrivacySensitive,
            "wifi.disconnect.wlan.postread.v1",
            ToolExposure.Public,
            "Desconecta WLAN mediante API oficial y verifica ausencia de conexión."),
        Descriptor(
            "wifi.ensure.connected",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "wifi.ensure.connected.wlan.current.profile.postread.v1",
            ToolExposure.Public,
            "Comprueba que Wi-Fi ya está conectado y devuelve la identidad opaca del perfil observado."),
        Descriptor(
            "wifi.profile.list",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "wifi.profile.list.wlan.snapshot.v1",
            ToolExposure.Public,
            "Enumera perfiles WLAN guardados mediante identidades opacas sin exponer credenciales."),
        Descriptor(
            "wifi.radio.set",
            Schema([Boolean("state")], ["state"]),
            OperationRisks.PrivacySensitive,
            "wifi.radio.set.windows.radio.postread.v1",
            ToolExposure.Public,
            "Enciende o apaga la radio Wi-Fi mediante la API oficial de Windows, con confirmación de la persona, y verifica su estado final."),
        Descriptor(
            "wifi.radio.status",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "wifi.radio.status.windows.radio.read.v1",
            ToolExposure.Public,
            "Lee si la radio Wi-Fi está encendida mediante la API oficial de Windows sin cambiar nada."),
        Descriptor(
            "wifi.scan",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "wifi.scan.netsh.wlan.networks.bssid.v1",
            ToolExposure.Public,
            "Lista las redes Wi-Fi visibles ahora para el adaptador WLAN (nombre, autenticación y señal) mediante netsh; si la radio está apagada devuelve ese estado sin cambiar nada."),
        Descriptor(
            "wifi.status",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "wifi.status.netsh.wlan.secondread.v1",
            ToolExposure.Public,
            "Lee dos veces el estado WLAN actual y devuelve conexión e identidad opaca del perfil sin exponer SSID ni credenciales."),
        Descriptor(
            "window.active",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "window.active.identity.foreground.v1",
            ToolExposure.Public,
            "Lee la ventana visible en primer plano y verifica su proceso, estado, geometría e identidad efímera."),
        Descriptor(
            "window.application.status",
            Schema([String("name", maximumUtf8Bytes: 256, nonWhitespace: true)], ["name"]),
            OperationRisks.ReadOnly,
            "window.application.status.catalog.visible.snapshot.v1",
            ToolExposure.Public,
            "Comprueba por nombre cualquier aplicación del catálogo Inicio y verifica si tiene una ventana visible sin abrirla ni modificarla."),
        Descriptor(
            "window.close.all",
            EmptySchema(),
            OperationRisks.WorkLoss,
            "window.close.all.desktop.postread.v1",
            ToolExposure.Public,
            "Pide el cierre de todas las ventanas visibles del escritorio salvo Visual Studio Code, la terminal y la propia, verifica cuáles se cerraron y cuenta las que siguen abiertas (por ejemplo, las que preguntan si guardar); nunca fuerza un proceso."),
        Descriptor(
            "window.focus",
            WindowIdSchema(),
            OperationRisks.LowReversible,
            "window.focus.identity.foreground.v1",
            ToolExposure.Public,
            "Enfoca una ventana resuelta previamente y verifica su identidad y foco."),
        Descriptor(
            "window.maximize",
            WindowIdSchema(),
            OperationRisks.LowReversible,
            "window.maximize.identity.state.v1",
            ToolExposure.Public,
            "Maximiza una ventana resuelta previamente y verifica su identidad y estado."),
        Descriptor(
            "window.minimize",
            WindowIdSchema(),
            OperationRisks.LowReversible,
            "window.minimize.identity.state.v1",
            ToolExposure.Public,
            "Minimiza una ventana resuelta previamente y verifica su identidad y estado."),
        Descriptor(
            "window.minimize.all",
            EmptySchema(),
            OperationRisks.LowReversible,
            "window.minimize.all.desktop.postread.v1",
            ToolExposure.Public,
            "Minimiza todas las ventanas visibles del escritorio (salvo la propia) y comprueba que quedaron minimizadas; no cierra nada."),
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
            ToolExposure.Public,
            "Mueve una ventana resuelta a coordenadas de escritorio y verifica sus límites exactos."),
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
            ToolExposure.Public,
            "Redimensiona una ventana resuelta y verifica ancho y alto exactos."),
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
            ToolExposure.Public,
            "Lee ventanas de nivel superior con estilo visible. Requiere exactamente un selector: applicationName (nombre exacto instalado, identidad AUMID o ejecutable comprobada, sin byTitle ni offset; devuelve la selección completa o falla), o process. Nunca convierte un nombre de aplicación en título o proceso. process='*' y byTitle=false enumeran todas; otro process busca ese proceso, y byTitle=true busca el título explícito solicitado. limit limita la página (1–50, defecto20), offset empieza en0. count cuenta la página; observedCount cuenta las observadas; complete=false implica lectura parcial y totalCount desconocido. nextOffset continúa sólo las observadas. Cada página vuelve a enumerar y puede cambiar: no es una foto estable ni prueba de que las ventanas estén descubiertas en pantalla. Devuelve títulos e identificadores efímeros; para modificar una ventana hay que elegir su identificador."),
        Descriptor(
            "window.restore",
            WindowIdSchema(),
            OperationRisks.LowReversible,
            "window.restore.identity.state.v1",
            ToolExposure.Public,
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
            ToolExposure.Public,
            "Coloca una ventana resuelta en la mitad izquierda o derecha del área de trabajo de su monitor (la restaura antes si estaba maximizada o minimizada) y verifica sus límites exactos."),
    ];

    private static readonly IReadOnlyList<ProductOperationDescriptor> ReadOnlyCatalog =
        Array.AsReadOnly(Catalog);
    private static readonly IReadOnlyList<ProductOperationDescriptor> ReadOnlyToolCatalog =
        Array.AsReadOnly(Catalog.Where(static descriptor =>
            descriptor.ToolExposure == ToolExposure.Public).ToArray());
    private static readonly IReadOnlyList<string> ReadOnlyOperationNames =
        Array.AsReadOnly(Catalog.Select(static descriptor => descriptor.Name).ToArray());

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

    public static IReadOnlyList<ProductOperationDescriptor> Descriptors => ReadOnlyCatalog;

    public static IReadOnlyList<ProductOperationDescriptor> ToolDescriptors => ReadOnlyToolCatalog;

    public static IReadOnlyList<string> OperationNames => ReadOnlyOperationNames;

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
        if (descriptor.ToolExposure != ToolExposure.Public
            || !Catalog.Any(candidate => ReferenceEquals(candidate, descriptor)))
        {
            throw new ArgumentException(
                "Only an exact public product descriptor may be exported as a tool.",
                nameof(definition));
        }

        using JsonDocument schema = JsonDocument.Parse(descriptor.ArgumentsSchema.CanonicalJson);
        return new OperationDescriptor(
            descriptor.Name,
            schema.RootElement.Clone(),
            descriptor.Risk,
            descriptor.VerifierContractId,
            descriptor.Description);
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

    internal static OperationRisk ToPolicyRisk(string exactRisk) => exactRisk switch
    {
        OperationRisks.ReadOnly => OperationRisk.ReadOnly,
        OperationRisks.LowReversible or OperationRisks.RecoverableDelete => OperationRisk.Reversible,
        OperationRisks.PrivacySensitive => OperationRisk.Sensitive,
        OperationRisks.ExternalCommunication => OperationRisk.External,
        // Decisión 8 del dueño (2026-10-10, PROMPT_ESTABILIZACION): en Normal se confirma lo que destruye datos y lo
        // que sale al mundo, también instalar; D3 (2026-09-20) lo dejaba directo.
        OperationRisks.SessionDisruption or OperationRisks.WorkLoss or OperationRisks.Monetary
            or OperationRisks.Installation => OperationRisk.Irreversible,
        OperationRisks.ForbiddenDestructive => OperationRisk.Forbidden,
        _ => OperationRisk.Forbidden,
    };

    private static ProductOperationDescriptor Descriptor(
        string name,
        OperationArgumentsSchema schema,
        string risk,
        string verifierContractId,
        ToolExposure exposure,
        string description,
        bool? requiresObservedEffect = null) =>
        new(name, schema, risk, verifierContractId, exposure, description, requiresObservedEffect);

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

    private static OperationArgumentsSchema FilesystemResourceSchema() =>
        Schema(
            [String("resourceId", maximumLength: 35, nonWhitespace: true)],
            ["resourceId"]);

    private static OperationArgumentsSchema FilesystemTransferSchema() =>
        Schema(
            [
                String("destinationRelativePath", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                String("expectedSha256", maximumLength: 64, nonWhitespace: true),
                String("resourceId", maximumLength: 35, nonWhitespace: true),
            ],
            ["destinationRelativePath", "expectedSha256", "resourceId"]);


    private static OperationArgumentsSchema RoutineCasSchema() =>
        Schema(
            [
                Integer("expectedRevision", 1),
                String("routineId", maximumLength: 36, nonWhitespace: true),
            ],
            ["expectedRevision", "routineId"]);

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
