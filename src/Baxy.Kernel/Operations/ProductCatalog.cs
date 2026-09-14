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
                [String("appId", maximumUtf8Bytes: 512, nonWhitespace: true)],
                ["appId"]),
            OperationRisks.LowReversible,
            "app.open.process.window.focus.v1",
            ToolExposure.Public,
            "Abre por nombre exacto una aplicación del catálogo Inicio del usuario y verifica su proceso, ventana visible y foco; también acepta windows.notepad y windows.calculator."),
        Descriptor(
            "app.status",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "app.status.catalog.ready.v1",
            ToolExposure.Internal,
            "Checks that the local core is available and lists its operations."),
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
            "browser.control",
            Schema([String("action", values:
                ["back", "close", "fullscreen_video", "reload", "scroll_down", "scroll_up"])], ["action"]),
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
                    String("browser", values: ["opera", "opera_gx"]),
                    String("url", maximumUtf8Bytes: 2_048, nonWhitespace: true),
                ],
                ["browser", "url"]),
            OperationRisks.ExternalCommunication,
            "browser.navigate.named.cdp.url.postread.v1",
            ToolExposure.Public,
            "Navega la edición indicada de Opera u Opera GX mediante un perfil CDP privado y verifica ejecutable y URL final."),
        Descriptor(
            "browser.page.read",
            Schema([Integer("maximumCharacters", 256, 32_768)], []),
            OperationRisks.PrivacySensitive,
            "browser.page.read.cdp.dom.snapshot.v1",
            ToolExposure.Public,
            "Lee titulo, URL y texto visible de la pagina CDP activa sin modificarla y limita el contenido devuelto."),
        Descriptor(
            "browser.tabs.list",
            Schema([Integer("limit", 1, 50)], []),
            OperationRisks.PrivacySensitive,
            "browser.tabs.list.cdp.targets.snapshot.v1",
            ToolExposure.Public,
            "Enumera las pestanas web de la sesion CDP local con identidad, titulo y URL observados."),
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
        Descriptor(
            "capture.active.window",
            EmptySchema(),
            OperationRisks.PrivacySensitive,
            "capture.active.window.gdi.foreground.bounds.bmp.hash.v1",
            ToolExposure.Public,
            "Captura solo los límites visibles de la ventana activa en un BMP privado y devuelve metadatos verificados."),
        Descriptor(
            "capture.screenshot",
            EmptySchema(),
            OperationRisks.PrivacySensitive,
            "capture.screenshot.gdi.bmp.hash.v1",
            ToolExposure.Public,
            "Captura el escritorio virtual en un BMP privado y devuelve solo identidad, dimensiones y hash."),
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
        Descriptor(
            "filesystem.file.open.latest",
            Schema([String("folder", values: ["desktop", "documents", "downloads", "pictures"])], ["folder"]),
            OperationRisks.LowReversible,
            "filesystem.file.open.latest.windows.shell.process.postread.v1",
            ToolExposure.Public,
            "Abre el archivo seguro modificado mas recientemente de una carpeta conocida y verifica el proceso observado."),
        Descriptor(
            "filesystem.folder.open",
            Schema([String("folder", values: ["desktop", "documents", "downloads", "pictures"])], ["folder"]),
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
            "filesystem.known.list",
            Schema(
                [
                    String("folder", values: ["desktop", "documents", "downloads"]),
                    Integer("limit", 1, 100),
                    String("order", values: ["name", "recent"]),
                ],
                ["folder"]),
            OperationRisks.ReadOnly,
            "filesystem.known.list.windows.toplevel.identities.v1",
            ToolExposure.Public,
            "Lista las entradas de primer nivel (archivos y carpetas) de una carpeta conocida de Windows sin revelar rutas."),
        Descriptor(
            "filesystem.known.search",
            Schema(
                [
                    String("folder", values: ["all_known", "desktop", "documents", "downloads"]),
                    Integer("limit", 1, 100),
                    String("query", maximumUtf8Bytes: 512, nonWhitespace: true),
                    String("subdirectory", maximumUtf8Bytes: 512, nonWhitespace: true),
                ],
                ["folder", "query"]),
            OperationRisks.ReadOnly,
            "filesystem.known.search.windows.identities.v1",
            ToolExposure.Public,
            "Busca archivos por nombre en carpetas conocidas de Windows sin seguir puntos de reanálisis ni revelar rutas."),
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
            "filesystem.sandbox.append.named",
            Schema(
                [
                    String("fileName", maximumUtf8Bytes: 512, nonWhitespace: true),
                    String("text", maximumUtf8Bytes: 65_536),
                ],
                ["fileName", "text"]),
            OperationRisks.LowReversible,
            "filesystem.sandbox.append.named.hash.postread.v1",
            ToolExposure.Public,
            "Añade texto a un archivo de nombre único del sandbox y verifica bytes y hashes."),
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
            "filesystem.write.text",
            Schema(
                [
                    String("expectedSha256", types: NullableString, maximumLength: 64),
                    // Owner decision 2026-09-13 (DECISIONES_DUENO, point 2): a known
                    // folder may be the root instead of the sandbox; an existing file
                    // there is never overwritten without its current hash.
                    String("folder", values: ["desktop", "documents", "downloads"]),
                    String("relativePath", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                    String("text", maximumUtf8Bytes: 1_048_576),
                ],
                ["relativePath", "text"]),
            OperationRisks.LowReversible,
            "filesystem.write.text.sandbox.cas.hash.v1",
            ToolExposure.Public,
            "Escribe UTF-8 atómicamente; reemplazar exige el SHA-256 exacto observado antes."),
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
            Schema([String("title", maximumUtf8Bytes: 256, nonWhitespace: true)], ["title"]),
            OperationRisks.Installation,
            "game.install.named.steam.manifest.postread.v1",
            ToolExposure.Public,
            "Resuelve un título cerrado de Steam a su AppID, exige entitlement autenticado, inicia la instalación confirmada y verifica la transición del manifest."),
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
        Descriptor(
            "input.key.press",
            Schema([String("key", values:
                [
                    "alt_tab", "arrow_down", "arrow_left", "arrow_right", "arrow_up",
                    "backspace", "context_menu", "control", "ctrl_shift_escape", "ctrl_v",
                    "delete", "end", "enter", "escape", "home", "page_down", "page_up",
                    "shift", "space", "tab", "win",
                ])], ["key"]),
            OperationRisks.LowReversible,
            "input.key.press.win32.sendinput.accepted.v1",
            ToolExposure.Public,
            "Presiona una tecla o la combinación segura Ctrl+Shift+Escape en la ventana enfocada y verifica que Windows aceptó todos los eventos SendInput."),
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
        Descriptor(
            "input.select.all",
            EmptySchema(),
            OperationRisks.LowReversible,
            "input.select.all.focused.uia.postread.v1",
            ToolExposure.Public,
            "Selecciona todo en el control enfocado de la ventana activa y verifica la seleccion mediante UI Automation."),
        Descriptor(
            "input.text.type",
            Schema([String("text", maximumUtf8Bytes: 8_192, nonWhitespace: true)], ["text"]),
            OperationRisks.PrivacySensitive,
            "input.text.type.win32.sendinput.accepted.v1",
            ToolExposure.Public,
            "Escribe texto Unicode literal en el control enfocado y verifica que Windows aceptó cada evento SendInput."),
        Descriptor(
            "input.visible.click",
            Schema([String("label", maximumUtf8Bytes: 256, nonWhitespace: true)], ["label"]),
            OperationRisks.ExternalCommunication,
            "input.visible.click.windows.uia.invoke.postread.v1",
            ToolExposure.Public,
            "Invoca un único control visible por etiqueta en la ventana en primer plano (UIA, luego OCR, luego visión) y exige postlectura: seleccionado, desaparecido o superficie cambiada."),
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
            "message.recipient.resolve",
            Schema(
                [
                    String("channel", values: ["discord", "whatsapp"]),
                    String("recipient", maximumUtf8Bytes: 512, nonWhitespace: true),
                ],
                ["channel", "recipient"]),
            OperationRisks.ReadOnly,
            "message.recipient.resolve.session.identity.v1",
            ToolExposure.Public,
            "Resuelve un único destinatario autenticado y emite un identificador revisable."),
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
            "notification.cancel.at",
            Schema(
                [
                    Integer("hour", 0, 23),
                    String("kind", values: ["alarm", "reminder"]),
                    Integer("minute", 0, 59),
                    String("period", values: ["am", "pm"]),
                ],
                ["hour", "kind"]),
            OperationRisks.LowReversible,
            "notification.cancel.windows.task.clock.identity.absent.v1",
            ToolExposure.Public,
            "Cancela una única alarma o recordatorio futuro de BAXY que coincida con la hora local solicitada, después de resolver y volver a verificar su identidad exacta."),
        Descriptor(
            "notification.cancel.latest",
            Schema([String("kind", values: ["alarm", "reminder"])], ["kind"]),
            OperationRisks.LowReversible,
            "notification.cancel.windows.task.absent.v1",
            ToolExposure.Public,
            "Cancela la alarma o recordatorio de BAXY más reciente y verifica que su tarea ya no exista."),
        Descriptor(
            "notification.diagnose",
            EmptySchema(),
            OperationRisks.ReadOnly,
            "notification.diagnose.windows.task.receipt.postread.v1",
            ToolExposure.Public,
            "Diagnostica el servicio, las tareas y los recibos de alarmas de BAXY sin modificar el sistema."),
        Descriptor(
            "notification.dismiss",
            ReminderCasSchema(),
            OperationRisks.LowReversible,
            "notification.dismiss.reminder.postread.v1",
            ToolExposure.Public,
            "Descarta una notificación vencida seleccionada mediante identidad y versión exactas."),
        Descriptor(
            "notification.list",
            Schema([Integer("limit", 1, 50)], []),
            OperationRisks.ReadOnly,
            "notification.list.windows.task.postread.v1",
            ToolExposure.Public,
            "Enumera las alarmas y recordatorios programados por BAXY (tipo, título y próxima ejecución) sin modificar el sistema."),
        Descriptor(
            "notification.list.due",
            Schema([Integer("limit", 1, 50)], []),
            OperationRisks.ReadOnly,
            "notification.list.due.clock.postread.v1",
            ToolExposure.Public,
            "Enumera recordatorios vencidos no descartados para que la superficie de usuario los presente."),
        Descriptor(
            "notification.schedule",
            Schema(
                [
                    String("dueUtc", maximumLength: 64, nonWhitespace: true),
                    String("kind", values: ["alarm", "reminder"]),
                    String("recurrence", values: ["daily", "hourly"]),
                    String("title", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                ],
                ["dueUtc", "kind", "title"]),
            OperationRisks.LowReversible,
            "notification.schedule.windows.task.postread.v1",
            ToolExposure.Public,
            "Programa una alarma o recordatorio audible, único o recurrente, y verifica la tarea futura en Windows."),
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
            "Resuelve un paquete winget exacto y prepara una confirmación sin instalar."),
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
            "reminder.create",
            Schema(
                [
                    String("details", maximumUtf8Bytes: 65_536),
                    String("dueUtc", maximumLength: 64, nonWhitespace: true),
                    String("title", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                ],
                ["dueUtc", "title"]),
            OperationRisks.LowReversible,
            "reminder.create.local.clock.postread.v1",
            ToolExposure.Public,
            "Crea un recordatorio local futuro durable sin confundirlo con una tarea."),
        Descriptor(
            "reminder.delete",
            Schema(
                [
                    Integer("expectedVersion", 1),
                    String("reminderId", maximumLength: 36, nonWhitespace: true),
                    String("reviewLabel", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                ],
                ["expectedVersion", "reminderId", "reviewLabel"]),
            OperationRisks.RecoverableDelete,
            "reminder.delete.local.postread.v1",
            ToolExposure.Public,
            "Envía un recordatorio exacto a papelera recuperable después de revisar su etiqueta."),
        Descriptor(
            "reminder.list",
            Schema([Integer("limit", 1, 50)], []),
            OperationRisks.ReadOnly,
            "reminder.list.local.postread.v1",
            ToolExposure.Public,
            "Lista recordatorios programados locales de forma acotada."),
        Descriptor(
            "reminder.resolve.exact",
            Schema(
                [
                    Boolean("includeDeleted"),
                    String("title", maximumUtf8Bytes: 1_024, nonWhitespace: true),
                ],
                ["title"]),
            OperationRisks.ReadOnly,
            "reminder.resolve.exact.local.identity.v1",
            ToolExposure.Public,
            "Resuelve un recordatorio por título literal y devuelve autoridad CAS."),
        Descriptor(
            "reminder.restore",
            ReminderCasSchema(),
            OperationRisks.LowReversible,
            "reminder.restore.local.postread.v1",
            ToolExposure.Public,
            "Restaura un recordatorio eliminado mediante identidad y versión exactas."),
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
        Descriptor(
            "streaming.navigate",
            Schema(
                [
                    String("resourceUri", maximumUtf8Bytes: 2_048, nonWhitespace: true),
                    String("service", values: ["netflix", "prime_video", "youtube"]),
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
                    String("service", values: ["netflix"]),
                    String("title", maximumUtf8Bytes: 512, nonWhitespace: true),
                ],
                ["service", "title"]),
            OperationRisks.ExternalCommunication,
            "streaming.play.named.netflix.cdp.video.progress.v1",
            ToolExposure.Public,
            "Busca y reproduce un título en una sesión Netflix autenticada y verifica que el video avanza."),
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
                    String("setting", values: ["brightness", "do_not_disturb", "night_light"]),
                    Integer("value", 0, 100),
                ],
                ["setting", "value"]),
            OperationRisks.PrivacySensitive,
            "system.settings.set.windows.postread.v1",
            ToolExposure.Public,
            "Cambia un ajuste permitido mediante API oficial y verifica su postlectura."),
        Descriptor(
            "system.settings.status",
            Schema([String("setting", values: ["brightness"])], ["setting"]),
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
            EmptySchema(),
            OperationRisks.ReadOnly,
            "system.time.clock.secondread.v1",
            ToolExposure.Public,
            "Lee la fecha y hora actuales, la hora UTC y el desfase local mediante dos observaciones coherentes."),
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
        Descriptor(
            "web.search",
            Schema(
                [
                    Integer("limit", 1, 20),
                    String("query", maximumUtf8Bytes: 2_000, nonWhitespace: true),
                ],
                ["query"]),
            OperationRisks.ReadOnly,
            "web.search.provider.results.v1",
            ToolExposure.Public,
            "Busca mediante un proveedor web configurado y devuelve resultados estructurados acotados."),
        Descriptor(
            "wifi.connect",
            Schema([String("profileId", maximumLength: 128, nonWhitespace: true)], ["profileId"]),
            OperationRisks.PrivacySensitive,
            "wifi.connect.wlan.profile.postread.v1",
            ToolExposure.Public,
            "Conecta un perfil WLAN ya guardado y verifica el estado sin exponer SSID ni credenciales."),
        Descriptor(
            "wifi.connect.named",
            Schema([String("profileName", maximumUtf8Bytes: 256, nonWhitespace: true)], ["profileName"]),
            OperationRisks.PrivacySensitive,
            "wifi.connect.named.wlan.profile.postread.v1",
            ToolExposure.Public,
            "Resuelve de forma única un perfil WLAN guardado por el nombre indicado, lo conecta y verifica el estado sin exponer credenciales."),
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
        OperationRisks.PrivacySensitive or OperationRisks.Installation => OperationRisk.Sensitive,
        OperationRisks.ExternalCommunication => OperationRisk.External,
        OperationRisks.SessionDisruption or OperationRisks.WorkLoss or OperationRisks.Monetary =>
            OperationRisk.Irreversible,
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

    private static OperationArgumentsSchema ReminderCasSchema() =>
        Schema(
            [
                Integer("expectedVersion", 1),
                String("reminderId", maximumLength: 36, nonWhitespace: true),
            ],
            ["expectedVersion", "reminderId"]);

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
