using Baxy.Kernel.Operations;

namespace Baxy.Integration.Tests;

internal static class Goal05CatalogObservation
{
    internal sealed record Row(
        string Operation,
        string VerifierContractId,
        string Risk,
        string Observation,
        string Verdict,
        string Surface,
        string? Reason);

    internal static IReadOnlyList<Row> ClassifyCatalog()
    {
        var rows = new List<Row>(ProductCatalog.Descriptors.Count);
        foreach (ProductOperationDescriptor descriptor in ProductCatalog.Descriptors)
        {
            rows.Add(Classify(descriptor));
        }

        return rows;
    }

    internal static Row Classify(ProductOperationDescriptor descriptor)
    {
        string name = descriptor.Name;
        if (name.StartsWith("note.", StringComparison.Ordinal)
            || name.StartsWith("task.", StringComparison.Ordinal)
            || name.StartsWith("reminder.", StringComparison.Ordinal)
            || name.StartsWith("routine.", StringComparison.Ordinal)
            || name.StartsWith("memory.", StringComparison.Ordinal))
        {
            return Observed(
                descriptor,
                "Relectura del almacén local (CAS / reapertura del documento).",
                "isolated_store");
        }

        if (name.StartsWith("filesystem.sandbox.", StringComparison.Ordinal)
            || name is "filesystem.copy"
                or "filesystem.create.directory"
                or "filesystem.hash"
                or "filesystem.list"
                or "filesystem.move"
                or "filesystem.read.text"
                or "filesystem.search"
                or "filesystem.trash.commit"
                or "filesystem.trash.prepare"
                or "filesystem.trash.restore"
                or "filesystem.write.text"
                or "backup.create"
                or "backup.list"
                or "backup.restore"
                or "backup.verify")
        {
            return Observed(
                descriptor,
                "Postlectura del sandbox CAS: existencia, ausencia o SHA-256 del recurso.",
                "isolated_store");
        }

        return name switch
        {
            "app.close" => Observed(
                descriptor,
                "HWND de la ventana resuelta ausente tras WM_CLOSE, sin matar el proceso.",
                "live_windows"),
            "app.installed" => Observed(
                descriptor,
                "Catálogo Inicio de Windows: la aplicación está o no está, sin abrirla.",
                "live_windows"),
            "app.open" => Observed(
                descriptor,
                "Proceso vivo + ventana visible + foco, independientes del recibo del lanzador.",
                "live_windows"),
            "app.status" => Observed(
                descriptor,
                "El núcleo local responde y enumera el catálogo tipado.",
                "live_windows"),
            "audio.mute" or "audio.volume" => Observed(
                descriptor,
                "Postlectura del endpoint Core Audio, más una segunda lectura de estado en Core.",
                "live_windows"),
            "audio.status" => Observed(
                descriptor,
                "Lectura del volumen y silencio del endpoint predeterminado, sin mutar.",
                "live_windows"),
            "audio.microphone.mute" or "audio.volume.adjust" => Unverifiable(
                descriptor,
                "El adapter externo puede postleer el endpoint, pero no se muta el audio del usuario fuera de audio.volume/mute restaurables."),
            // Operaciones de C03 (2026-09-12 … 2026-09-20): cada una se verifica en su tanda sellada con su
            // postlectura; esta matriz no las recorre porque tocan apps, radios o carpetas del usuario, o
            // exigen un cliente con sesión (plan post-goal 2026-09-20, Fase 1 grupo B).
            "audio.app.volume.adjust" or "audio.app.volume.set" => Unverifiable(
                descriptor,
                "Postlectura de la sesión de audio de la app (autoridad windows_core_audio_session_postread, AUDIO1801); la matriz no muta el volumen de una app del usuario ni tiene una app con sesión de audio garantizada."),
            "bluetooth.radio.status" or "wifi.radio.status" => Unverifiable(
                descriptor,
                "Lectura de Windows.Devices.Radios (NETWORK1823/1827); esta sonda no acredita el estado de las radios del usuario sin observación."),
            "wifi.radio.set" => Unverifiable(
                descriptor,
                "Mutaría la radio Wi-Fi del usuario (postlectura de Radios en su tanda); no restaurable aquí."),
            "wifi.scan" => Unverifiable(
                descriptor,
                "netsh wlan show networks mode=bssid enumera redes vecinas del usuario; no se toma como pass simulado."),
            "calculator.expression.evaluate" => Unverifiable(
                descriptor,
                "Escribe en la Calculadora de Windows por UIA y lee su display (UI1731); abriría y teclearía en una app del usuario."),
            "client.channel.locate" => Unverifiable(
                descriptor,
                "Ctrl+K por UIA en Discord (DISCORD1839); exige el cliente con sesión y robaría el foco."),
            "display.status" or "storage.removable.list" or "software.python.status"
                or "software.python.package.status" or "notification.list" => Unverifiable(
                descriptor,
                "Lecturas de dispositivos, unidades, registro PEP 514, pip o Programador de tareas del usuario; verificadas en su tanda por doble lectura, no recorridas aquí para no inventariar la máquina del usuario."),
            "document.presentation.create" => Unverifiable(
                descriptor,
                "Escribiría un .pptx en Documentos del usuario (REOPEN1957 H0188); su postlectura cuenta las diapositivas del paquete, no se recorre aquí."),
            "file.compress" or "file.open" or "desktop.wallpaper.set" or "web.download" => Unverifiable(
                descriptor,
                "Escribiría un zip, abriría un archivo, cambiaría el fondo del escritorio o guardaría una descarga en las carpetas del usuario (REOPEN1957 H0542/H0459/H0077); no restaurable desde esta matriz."),
            "game.uninstall.named" => Unverifiable(
                descriptor,
                "Desinstalaría un juego instalado del usuario por la consola de Steam y verificaría la ausencia de su manifiesto (REOPEN1993 grupo S); no restaurable desde esta sesión."),
            "shell.command.run" => Unverifiable(
                descriptor,
                "Correría un comando en una consola del usuario y capturaría su salida (REOPEN1993 comandos, D11); esta matriz no ejecuta comandos ni toma una salida ajena como pass simulado."),
            "package.uninstall" => Unverifiable(
                descriptor,
                "Desinstalaría por winget un paquete del usuario y verificaría su ausencia (REOPEN1993 grupo G); no restaurable desde esta sesión."),
            "web.news.headlines" => Unverifiable(
                descriptor,
                "Lectura de un canal RSS público de noticias (REOPEN1993 grupo N); esta matriz no sale a internet ni toma titulares ajenos como pass simulado."),
            "weather.current" => Unverifiable(
                descriptor,
                "Lectura de un servicio público de pronóstico (Open-Meteo) y de la ubicación de este PC por su IP (REOPEN1993 grupo W); esta matriz no sale a internet ni toma un pronóstico ajeno como pass simulado."),
            "document.text.read" or "filesystem.explorer.count" => Unverifiable(
                descriptor,
                "Leería archivos de texto de carpetas conocidas y la carpeta del Explorador del usuario (REOPEN1957 H0299/H0701); no se rellena la celda con su contenido."),
            "document.pdf.read" or "filesystem.known.list" => Unverifiable(
                descriptor,
                "Leería PDFs y carpetas conocidas (Desktop/Documents/…) del usuario; no se rellena la celda con su contenido."),
            "game.entitlement.named" => Unverifiable(
                descriptor,
                "Manifiestos y librarycache de Steam (STEAM1825); sin cliente autorizado el adapter no observa una biblioteca."),
            "input.visible.controls" => Unverifiable(
                descriptor,
                "Instantánea UIA de la ventana en foreground; aquí sería la de esta sesión de pruebas."),
            "message.draft" or "message.send.test" => Unverifiable(
                descriptor,
                "Exige WhatsApp/Discord/Outlook con sesión; el borrador y el envío al destino forzado se verifican por OCR del compositor y la burbuja (MSGSEND1845/1847)."),
            "window.close.all" or "window.minimize.all" or "window.snap" => Unverifiable(
                descriptor,
                "Cerraría, minimizaría o movería las ventanas del escritorio del usuario (postlectura del inventario en CLOSEALL1733/MINALL1687); no restaurable desde esta sesión."),
            "bluetooth.device.list" => Unverifiable(
                descriptor,
                "Requiere radio Bluetooth y el adapter de hardware; no se recorre aquí para no enumerar dispositivos del usuario como pass simulado."),
            "bluetooth.device.pair" or "bluetooth.radio.set" => Unverifiable(
                descriptor,
                "Mutación de radio/emparejamiento no restaurable en esta sesión."),
            "browser.control" or "browser.navigate" or "browser.navigate.named"
                or "browser.page.read" or "browser.tabs.list" => Unverifiable(
                descriptor,
                "Exige una sesión CDP viva; sin ella el provider falla cerrado (cdp_browser_session_required)."),
            "calendar.event.create" or "calendar.event.list" => Unverifiable(
                descriptor,
                "Exige una cuenta Microsoft Graph autenticada."),
            "capture.active.window" or "capture.screenshot" => Observed(
                descriptor,
                "Hash SHA-256 del BMP GDI escrito en el almacén privado de capturas.",
                "isolated_store"),
            "clipboard.copy" or "clipboard.paste" => Unverifiable(
                descriptor,
                "SendInput sobre la ventana enfocada; el efecto semántico en la app no es observable de forma restaurable sin robar el foco de esta sesión."),
            "clipboard.read.text" or "clipboard.write.text" => Observed(
                descriptor,
                "Segunda lectura de la secuencia del portapapeles de Windows.",
                "isolated_store"),
            "email.latest.read" or "email.latest.reply" or "email.send" => Unverifiable(
                descriptor,
                "Exige un perfil Outlook autenticado."),
            "filesystem.file.open.latest" or "filesystem.folder.open" => Unverifiable(
                descriptor,
                "Abriría Explorer sobre carpetas del usuario; no se lanza un shell persistente para rellenar la celda."),
            "filesystem.known.duplicates" or "filesystem.known.search"
                or "filesystem.known.trash.named" or "filesystem.path.ensure.absent" => Unverifiable(
                descriptor,
                "Opera sobre carpetas conocidas del usuario (Desktop/Documents/…); no restaurable aquí."),
            "backup.known.create" or "backup.known.list"
                or "backup.known.restore.latest" or "backup.known.verify.latest" => Unverifiable(
                descriptor,
                "ZIP de carpetas conocidas del usuario; no se copia Desktop/Documents para rellenar la celda."),
            "game.catalog.list" or "game.installed.named" or "game.install.status" => Unverifiable(
                descriptor,
                "Inventario Steam/Epic; sin cliente autorizado el adapter no observa un catálogo."),
            "game.install.cancel" or "game.install.cancel.active" or "game.install.commit"
                or "game.install.named" or "game.install.prepare" or "game.launch"
                or "game.purchase.commit" or "game.purchase.prepare" => Unverifiable(
                descriptor,
                "Instalación, lanzamiento o cobro en Steam: no restaurable y, en purchase, efecto monetario."),
            "input.key.press" or "input.text.type" => Unverifiable(
                descriptor,
                "Win32 SendInput aceptado no es el efecto semántico en la app enfocada; dispararlo aquí escribiría en esta sesión."),
            "input.keyboard.layout" or "input.keyboard.open" or "input.keyboard.status"
                or "input.pointer.control" or "input.select.all" or "input.visible.click" => Unverifiable(
                descriptor,
                "Mutaría teclado, puntero o control UIA enfocado; no restaurable sin robar el foco."),
            "media.control" or "media.seek.relative" or "media.status" => Unverifiable(
                descriptor,
                "SMTC observa la sesión multimedia, pero no hay una sesión restaurable garantizada en esta máquina."),
            "media.play.exact" or "media.play.query" or "media.play.youtube" => Unverifiable(
                descriptor,
                "Reproducción de Spotify/YouTube: Windows no expone un API de «está sonando esta pista» sin sesión SMTC/CDP autenticada."),
            "message.recipient.resolve" or "message.send" => Unverifiable(
                descriptor,
                "Exige WhatsApp/Discord con sesión; el tick de enviado vive en UIA de esa app, no en el código de retorno."),
            "network.dns.status" or "network.ip.list" or "network.ping"
                or "network.port.list" or "network.status" => Observed(
                descriptor,
                "Dos observaciones consecutivas de interfaces, listeners o eco ICMP de Windows.",
                "live_windows"),
            "notification.cancel.at" or "notification.cancel.latest"
                or "notification.diagnose" or "notification.schedule" => Unverifiable(
                descriptor,
                "Crearía o borraría tareas visibles del Programador de tareas de Windows."),
            "notification.dismiss" or "notification.list.due" => Observed(
                descriptor,
                "Relectura del almacén local de recordatorios vencidos.",
                "isolated_store"),
            "ocr.read" => Unverifiable(
                descriptor,
                "Tesseract en esta máquina no tiene spa.traineddata; el OCR de una captura en español no es verificable con el paquete instalado."),
            "office.document.create" or "office.document.read" => Unverifiable(
                descriptor,
                "Exige un adapter Office autenticado."),
            "package.install.commit" or "package.install.prepare" => Unverifiable(
                descriptor,
                "winget instalaría software; prepare sin commit no afirma un efecto, y commit no es restaurable."),
            "peripheral.list" => Unverifiable(
                descriptor,
                "Enumeraría hardware del usuario; no se toma como pass sin un inventario restaurable acotado."),
            "peripheral.print" or "peripheral.scan" => Unverifiable(
                descriptor,
                "Enviaría un trabajo a impresora o escáner reales."),
            "streaming.navigate" or "streaming.play.named" => Unverifiable(
                descriptor,
                "Exige una sesión autenticada de Netflix/Prime/YouTube."),
            "system.application.crash.diagnose" => Unverifiable(
                descriptor,
                "Leería el registro Application; no se recorre el Event Log del usuario para rellenar la celda."),
            "system.identity" or "system.process.list" or "system.status" or "system.time" => Observed(
                descriptor,
                "Dos lecturas coherentes de entorno, procesos o reloj de Windows.",
                "live_windows"),
            "system.power" => Unverifiable(
                descriptor,
                "Lock/restart/shutdown/signout/sleep no son restaurables: la API oficial acepta la transición y la máquina abandona la sesión."),
            "system.process.terminate.named" => Unverifiable(
                descriptor,
                "Mataría procesos por nombre; no restaurable."),
            "system.recyclebin.empty" => Unverifiable(
                descriptor,
                "Vaciaría la Papelera del usuario."),
            "system.settings.adjust" or "system.settings.set" or "system.settings.status" => Unverifiable(
                descriptor,
                "WMI de brillo en esta máquina devolvió brightness_status_verification_failed; no se muta el brillo del usuario y no se afirma un estado que Windows no corroboró."),
            "vision.describe" => Unverifiable(
                descriptor,
                "Exige un VLM configurado sobre una captura; pertenece al goal 07."),
            "web.search" => Unverifiable(
                descriptor,
                "El proveedor web no está configurado (web_search_provider_not_configured)."),
            "wifi.connect" or "wifi.connect.named" or "wifi.disconnect" => Unverifiable(
                descriptor,
                "Mutaría la radio WLAN del usuario; no restaurable."),
            "wifi.ensure.connected" or "wifi.profile.list" or "wifi.status" => Unverifiable(
                descriptor,
                "WLAN netsh/WlanApi es de lectura; esta sonda no la ejecuta ni acredita conectividad o SSID sin observación."),
            "window.active" or "window.application.status" or "window.resolve" => Observed(
                descriptor,
                "Identidad HWND: proceso, visibilidad y geometría observados, sin mutar.",
                "live_windows"),
            "window.focus" or "window.maximize" or "window.minimize"
                or "window.move" or "window.resize" or "window.restore" => Unverifiable(
                descriptor,
                "Mutaría una ventana arbitraria del escritorio; sólo se ejercita app.open de Bloc de notas, que se deja como se encontró o se cierra si esta sesión la lanzó."),
            _ => throw new InvalidOperationException(
                $"Goal 05 has no observation rule for '{name}'."),
        };
    }

    private static Row Observed(
        ProductOperationDescriptor descriptor,
        string observation,
        string surface) =>
        new(
            descriptor.Name,
            descriptor.VerifierContractId,
            descriptor.Risk,
            observation,
            "observed",
            surface,
            Reason: null);

    private static Row Unverifiable(
        ProductOperationDescriptor descriptor,
        string reason) =>
        new(
            descriptor.Name,
            descriptor.VerifierContractId,
            descriptor.Risk,
            descriptor.VerifierContractId,
            "unverifiable",
            "none",
            reason);
}
