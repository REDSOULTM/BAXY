using System.Text.Json;
using System.Text.Json.Serialization.Metadata;
using System.Globalization;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Audio;

namespace Baxy.Core.Operations;

internal sealed class ProductOperationNarrator : IOperationResponseNarrator
{
    internal static ProductOperationNarrator Instance { get; } = new();

    private ProductOperationNarrator()
    {
    }

    public string Narrate(string operation, OperationOutcome outcome)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(operation);
        ArgumentNullException.ThrowIfNull(outcome);
        return outcome.Succeeded && outcome.Verified
            ? NarrateSuccess(operation, outcome)
            : NarrateFailure(operation, outcome);
    }

    public string NarrateStatus(string operation, string status, string? errorCode)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(operation);
        ArgumentException.ThrowIfNullOrWhiteSpace(status);
        return errorCode switch
        {
            "invalid_private_envelope" =>
                "La solicitud privada no tiene un envelope autenticado válido.",
            "idempotency_conflict" =>
                "Ese identificador ya pertenece a otra acción.",
            ConfirmationChallengeContract.RequiredErrorCode =>
                "Necesito tu confirmación antes de hacer eso.",
            "journal_capacity_reached" =>
                "El historial seguro alcanzó su capacidad. No ejecuté este intento y conservé su identidad para evitar duplicados; libera espacio antes de reintentar.",
            "unknown_operation" => "No reconozco esa petición.",
            "operation_forbidden" => "Esa petición no está permitida.",
            "invalid_arguments" => NarrateFailure(
                operation,
                OperationOutcome.Failure("invalid_arguments")),
            _ when operation.StartsWith("memory.", StringComparison.Ordinal) =>
                NarrateGenericFailure(operation),
            _ when string.Equals(status, Baxy.Contracts.OperationStatuses.Pending, StringComparison.Ordinal) =>
                "La petición necesita confirmación antes de continuar.",
            _ => NarrateGenericFailure(operation),
        };
    }

    private static string NarrateSuccess(string operation, OperationOutcome outcome) => operation switch
    {
        "app.close" => "Listo, cerré la ventana.",
        "app.installed" => NarrateAppInstalled(outcome),
        "app.open" => NarrateAppOpen(outcome),
        "app.status" => "BAXY está listo.",
        "audio.microphone.mute" => "Listo, verifiqué el estado de silencio del micrófono predeterminado.",
        "audio.volume.adjust" => "Listo, ajusté y verifiqué el volumen de salida.",
        "bluetooth.radio.set" => NarrateBluetoothRadio(outcome),
        "backup.list" => NarrateBackupList(outcome),
        "browser.control" => "Listo, controlé y verifiqué la página actual.",
        "browser.page.read" => NarrateBrowserPage(outcome),
        "browser.tabs.list" => NarrateBrowserTabs(outcome),
        "clipboard.copy" => "Listo, copié la selección del control enfocado y verifiqué el cambio real del portapapeles.",
        "clipboard.paste" => "Listo, pegué el contenido del portapapeles en el control enfocado y Windows aceptó todos los eventos.",
        "filesystem.folder.open" => "Listo, abrí y verifiqué la carpeta.",
        "filesystem.file.open.latest" => "Listo, abrí y verifiqué el archivo más reciente.",
        "game.install.named" => "Listo, resolví el juego y verifiqué su estado de instalación en Steam.",
        "input.key.press" => "Listo, Windows aceptó la tecla en la ventana activa.",
        "input.keyboard.layout" => "Listo, activé y verifiqué el teclado español en la ventana activa.",
        "input.keyboard.open" => "Listo, abrí y verifiqué el teclado en pantalla de Windows.",
        "input.keyboard.status" => "El teclado activo está configurado en el idioma indicado por Windows.",
        "input.pointer.control" => "Listo, controlé y verifiqué el puntero.",
        "input.select.all" => "Listo, seleccioné todo en el control activo.",
        "input.text.type" => "Listo, Windows aceptó todo el texto en el control activo.",
        "media.control" => "Listo, cambié y verifiqué la reproducción.",
        "media.play.exact" or "media.play.query" => NarrateMediaPlayed(outcome),
        "media.seek.relative" => NarrateMediaSeek(outcome),
        "media.status" => NarrateMediaStatus(outcome),
        "message.send" => "Listo, envié el mensaje y verifiqué el recibo.",
        "network.dns.status" => NarrateDnsStatus(outcome),
        "network.ip.list" => "Estas son las direcciones IP locales activas confirmadas en dos lecturas.",
        "network.ping" => NarrateNetworkPing(outcome),
        "network.port.list" => "Estos son los puertos locales en escucha confirmados en dos lecturas.",
        "routine.phrase.create" => "Listo, guardé la rutina de frase exacta.",
        AudioOperationIds.Mute => NarrateAudioMute(outcome),
        AudioOperationIds.Status => NarrateAudioStatus(outcome),
        AudioOperationIds.Volume => NarrateAudioVolume(outcome),
        "note.create" => NarrateNote(outcome, "Guardé la nota «{0}»."),
        "note.read" => NarrateNote(outcome, "Encontré la nota «{0}»."),
        "note.list" => NarrateNoteList(outcome),
        "note.restore" => NarrateNote(outcome, "La nota «{0}» está activa."),
        "note.trash" => NarrateNote(outcome, "La nota «{0}» está en la papelera."),
        "task.complete" => NarrateTask(outcome, "Marqué como completada la tarea «{0}»."),
        "task.create" => NarrateTask(outcome, "Creé la tarea «{0}»."),
        "task.delete" => NarrateTask(outcome, "Moví la tarea «{0}» a la papelera."),
        "task.list" or "task.search" => NarrateTaskList(outcome),
        "task.reopen" => NarrateTask(outcome, "Reabrí la tarea «{0}»."),
        "task.resolve.exact" => NarrateTaskSelection(outcome),
        "task.restore" => NarrateTask(outcome, "Restauré la tarea «{0}»."),
        "task.update" => NarrateTask(outcome, "Actualicé la tarea «{0}»."),
        "peripheral.list" => NarratePeripheralList(outcome),
        "system.settings.adjust" => "Listo, ajusté y verifiqué el brillo de la pantalla.",
        "system.application.crash.diagnose" => "Estos son los fallos recientes confirmados en el registro de aplicaciones de Windows.",
        "system.settings.status" => "Este es el brillo actual confirmado de los monitores compatibles.",
        "system.identity" => NarrateSystemIdentity(outcome),
        "wifi.connect.named" => "Listo, resolví y conecté el perfil Wi-Fi guardado.",
        "wifi.status" => "Este es el estado Wi-Fi actual confirmado en dos lecturas estables.",
        "system.status" => NarrateSystemStatus(outcome),
        "system.process.list" => NarrateProcessList(outcome),
        "system.process.terminate.named" => "Listo, forcé el cierre del proceso y verifiqué que ya no está ejecutándose.",
        "system.time" => NarrateSystemTime(outcome),
        "window.active" => NarrateActiveWindow(outcome),
        "window.application.status" => NarrateApplicationWindowStatus(outcome),
        _ when operation.StartsWith("memory.", StringComparison.Ordinal) =>
            NarrateGenericSuccess(operation),
        _ => NarrateGenericSuccess(operation),
    };

    private static string NarrateFailure(string operation, OperationOutcome outcome)
    {
        if (operation.StartsWith("memory.", StringComparison.Ordinal))
        {
            return NarrateGenericFailure(operation);
        }
        if (operation.StartsWith("task.", StringComparison.Ordinal))
        {
            return NarrateTaskFailure(outcome);
        }

        return operation switch
        {
            "app.close" => outcome.ErrorCode switch
            {
                "window_not_found" => "No encontré una ventana visible de esa aplicación.",
                "window_identity_changed" or "invalid_or_expired_window_id" =>
                    "La ventana cambió antes de poder cerrarla; no cerré otra por accidente.",
                _ => "No pude cerrar y verificar esa ventana.",
            },
            "app.open" => NarrateAppOpenFailure(outcome),
            "game.install.named" =>
                "No pude resolver, autorizar o verificar la instalación de ese juego en Steam.",
            "app.status" when outcome.ErrorCode == "invalid_arguments" =>
                "Los datos del estado no tienen el formato esperado.",
            "audio.microphone.mute" =>
                "No pude verificar el estado final del micrófono predeterminado.",
            "audio.volume.adjust" =>
                "No pude verificar el ajuste relativo del volumen de salida.",
            "clipboard.copy" =>
                "No pude verificar una selección copiada, el foco estable y el cambio real del portapapeles.",
            "clipboard.paste" =>
                "No pude verificar un portapapeles con contenido, el foco estable y la aceptación completa de Ctrl+V.",
            "input.key.press" or "input.keyboard.layout" or "input.keyboard.open" or
                "input.keyboard.status" or
                "input.pointer.control" or "input.text.type" =>
                "Windows no pudo verificar completamente el efecto de entrada solicitado.",
            "system.settings.adjust" =>
                "No pude verificar el ajuste relativo del brillo de la pantalla.",
            "wifi.connect.named" =>
                "No pude resolver de forma única y conectar ese perfil Wi-Fi guardado.",
            "bluetooth.radio.set" => outcome.ErrorCode switch
            {
                "bluetooth_radio_access_denied" =>
                    "Windows no autorizó el control de la radio Bluetooth.",
                "bluetooth_radio_not_found" =>
                    "No encontré una radio Bluetooth en este equipo.",
                _ => "No pude verificar el estado final de Bluetooth.",
            },
            "media.status" => outcome.ErrorCode switch
            {
                "invalid_arguments" => "La consulta de reproducción no acepta argumentos.",
                "media_session_not_found" =>
                    "No hay ninguna reproducción visible para Windows en este momento.",
                "smtc_session_access_failed" =>
                    "Windows no permitió consultar la reproducción actual.",
                _ => "No pude verificar qué se está reproduciendo ahora.",
            },
            "media.seek.relative" => outcome.ErrorCode switch
            {
                "media_timeline_not_available" =>
                    "La reproducción actual no publica una línea de tiempo que pueda mover.",
                "media_session_not_found" =>
                    "No hay ninguna reproducción visible para Windows en este momento.",
                _ => "No pude verificar la nueva posición de la reproducción.",
            },
            "network.dns.status" => outcome.ErrorCode == "invalid_arguments"
                ? "La consulta de DNS no acepta argumentos."
                : "No pude verificar la configuración DNS activa.",
            "network.ping" => outcome.ErrorCode == "invalid_arguments"
                ? "Necesito un host o dirección IP válidos para hacer ping."
                : "No pude completar el diagnóstico de ping.",
            "network.port.list" => outcome.ErrorCode == "invalid_arguments"
                ? "El limite solicitado para los puertos no es valido."
                : "No pude verificar los puertos locales en escucha.",
            AudioOperationIds.Mute or AudioOperationIds.Volume =>
                NarrateAudioControlFailure(operation, outcome),
            AudioOperationIds.Status => NarrateAudioStatusFailure(outcome.ErrorCode),
            "note.create" or "note.list" or "note.read" or "note.restore" or "note.trash" =>
                NarrateNoteFailure(operation, outcome),
            "peripheral.list" => outcome.ErrorCode == "invalid_arguments"
                ? "La consulta de periféricos no acepta argumentos."
                : "No pude enumerar los periféricos conectados.",
            "system.application.crash.diagnose" =>
                "No pude verificar los fallos recientes en el registro de aplicaciones de Windows.",
            "system.settings.status" =>
                "No pude leer dos veces un valor coherente del brillo de la pantalla.",
            "system.identity" => outcome.ErrorCode == "invalid_arguments"
                ? "La consulta de identidad no acepta argumentos."
                : "No pude verificar el usuario efectivo de Windows.",
            "system.status" => NarrateSystemStatusFailure(outcome),
            "system.process.list" => outcome.ErrorCode == "invalid_arguments"
                ? "La consulta de procesos no tiene el formato esperado."
                : "No pude verificar la lista actual de procesos.",
            "system.process.terminate.named" => outcome.ErrorCode == "invalid_arguments"
                ? "Necesito el nombre ejecutable exacto del proceso que quieres forzar a cerrar."
                : "No pude forzar y verificar el cierre completo de ese proceso.",
            "system.time" => outcome.ErrorCode == "invalid_arguments"
                ? "La consulta de hora no acepta argumentos."
                : "No pude verificar la hora local del equipo.",
            "window.active" => outcome.ErrorCode == "window_not_found"
                ? "No encontré una ventana visible en primer plano."
                : "No pude verificar qué aplicación está activa.",
            "window.application.status" => outcome.ErrorCode switch
            {
                "app_ambiguous" => "Ese nombre coincide con varias aplicaciones; necesito el nombre completo.",
                "app_not_found" => "No encontré esa aplicación en el catálogo Inicio de Windows.",
                _ => "No pude verificar si esa aplicación tiene una ventana visible.",
            },
            _ => NarrateGenericFailure(operation),
        };
    }

    private static string NarrateGenericSuccess(string operation) =>
        $"Completé y verifiqué {NarrationSubject(operation)}.";

    private static string NarrateGenericFailure(string operation) =>
        $"No pude completar {NarrationSubject(operation)}.";

    private static string NarrationSubject(string operation) =>
        operation.Split('.', 2, StringSplitOptions.None)[0] switch
        {
            "app" => "la petición sobre la aplicación",
            "audio" => "la petición de audio",
            "backup" => "la petición de copia de seguridad",
            "bluetooth" => "la petición de Bluetooth",
            "browser" => "la petición del navegador",
            "calendar" => "la petición del calendario",
            "capture" => "la captura solicitada",
            "clipboard" => "la petición del portapapeles",
            "email" => "la petición de correo",
            "filesystem" => "la petición sobre tus archivos",
            "game" => "la petición sobre el juego",
            "input" => "la interacción solicitada",
            "media" => "la petición multimedia",
            "memory" => "la petición sobre la memoria local",
            "message" => "la petición de mensajería",
            "network" => "la consulta de red",
            "note" => "la petición sobre las notas",
            "notification" => "la petición sobre las notificaciones",
            "ocr" => "la lectura de texto solicitada",
            "office" => "la petición sobre el documento",
            "package" => "la petición de instalación",
            "peripheral" => "la petición sobre el periférico",
            "reminder" => "la petición sobre el recordatorio",
            "routine" => "la petición sobre la rutina",
            "streaming" => "la petición de reproducción",
            "system" => "la petición del sistema",
            "task" => "la petición sobre las tareas",
            "vision" => "la descripción visual solicitada",
            "web" => "la búsqueda web",
            "wifi" => "la petición de Wi-Fi",
            "window" => "la petición sobre la ventana",
            _ => "la petición",
        };

    private static string NarrateActiveWindow(OperationOutcome outcome)
    {
        if (outcome.Result is not { ValueKind: JsonValueKind.Object } result
            || !result.TryGetProperty("windows", out JsonElement windows)
            || windows.ValueKind != JsonValueKind.Array
            || windows.GetArrayLength() != 1)
        {
            return "La ventana activa fue verificada.";
        }

        JsonElement window = windows[0];
        string processName = window.TryGetProperty("processName", out JsonElement process)
            ? process.GetString() ?? "desconocida"
            : "desconocida";
        string state = window.TryGetProperty("state", out JsonElement stateElement)
            ? stateElement.GetString() ?? "visible"
            : "visible";
        int width = 0;
        int height = 0;
        bool hasWidth = window.TryGetProperty("width", out JsonElement widthElement)
            && widthElement.TryGetInt32(out width);
        bool hasHeight = window.TryGetProperty("height", out JsonElement heightElement)
            && heightElement.TryGetInt32(out height);
        return hasWidth && hasHeight
            ? $"La aplicación activa es {processName}; su ventana está {state} y mide {width} × {height} píxeles."
            : $"La aplicación activa es {processName}; su ventana está {state}.";
    }

    private static string NarrateAppInstalled(OperationOutcome outcome)
    {
        if (outcome.Result is not { ValueKind: JsonValueKind.Object } result
            || !result.TryGetProperty("installed", out JsonElement installed))
            return "Terminé de comprobar la instalación.";
        string name = result.TryGetProperty("displayName", out JsonElement display)
            && display.ValueKind == JsonValueKind.String
                ? display.GetString() ?? "La aplicación"
                : result.TryGetProperty("requestedName", out JsonElement requested)
                    ? requested.GetString() ?? "La aplicación" : "La aplicación";
        if (installed.ValueKind != JsonValueKind.True)
            return $"No encontré {name} instalado en este equipo.";
        string? version = result.TryGetProperty("installedVersion", out JsonElement versionValue)
            && versionValue.ValueKind == JsonValueKind.String
                ? versionValue.GetString() : null;
        return string.IsNullOrWhiteSpace(version)
            ? $"Sí, {name} está instalado."
            : $"Sí, {name} está instalado; su versión es {version}.";
    }

    private static string NarrateApplicationWindowStatus(OperationOutcome outcome)
    {
        if (outcome.Result is not { ValueKind: JsonValueKind.Object } result
            || !result.TryGetProperty("installed", out JsonElement installed)
            || !result.TryGetProperty("hasVisibleWindow", out JsonElement visible))
            return "Terminé de comprobar el estado visible de la aplicación.";
        string name = result.TryGetProperty("displayName", out JsonElement display)
            && display.ValueKind == JsonValueKind.String
                ? display.GetString() ?? "La aplicación"
                : result.TryGetProperty("requestedName", out JsonElement requested)
                    ? requested.GetString() ?? "La aplicación" : "La aplicación";
        if (installed.ValueKind != JsonValueKind.True)
            return $"No encontré {name} instalado en este equipo.";
        return visible.ValueKind == JsonValueKind.True
            ? $"Sí, {name} tiene una ventana abierta."
            : $"No, {name} no tiene ninguna ventana visible abierta.";
    }

    private static string NarrateBackupList(OperationOutcome outcome)
    {
        int count = outcome.Result is { ValueKind: JsonValueKind.Object } result
            && result.TryGetProperty("count", out JsonElement value)
            && value.TryGetInt32(out int observed) ? observed : 0;
        return count == 0
            ? "No hay copias privadas guardadas."
            : count == 1 ? "Hay una copia privada verificada." : $"Hay {count} copias privadas verificadas.";
    }

    private static string NarrateBrowserPage(OperationOutcome outcome)
    {
        if (outcome.Result is not { } result)
            return "No pude leer la página actual.";
        string title = result.TryGetProperty("title", out JsonElement titleElement)
            ? titleElement.GetString() ?? string.Empty : string.Empty;
        string text = result.TryGetProperty("text", out JsonElement textElement)
            ? textElement.GetString() ?? string.Empty : string.Empty;
        string excerpt = text.Length <= 1_500 ? text : text[..1_500] + "…";
        if (string.IsNullOrWhiteSpace(excerpt))
            return string.IsNullOrWhiteSpace(title)
                ? "La página actual no contiene texto visible."
                : $"La página actual es «{title}» y no contiene texto visible.";
        return string.IsNullOrWhiteSpace(title) ? excerpt : $"{title}: {excerpt}";
    }

    private static string NarrateBrowserTabs(OperationOutcome outcome)
    {
        if (outcome.Result is not { } result
            || !result.TryGetProperty("count", out JsonElement countElement)
            || !countElement.TryGetInt32(out int count))
        {
            return "No pude enumerar las pestañas del navegador.";
        }
        return count switch
        {
            0 => "No hay pestañas web abiertas en la sesión de BAXY.",
            1 => "Hay 1 pestaña web abierta en la sesión de BAXY.",
            _ => $"Hay {count} pestañas web abiertas en la sesión de BAXY.",
        };
    }

    private static string NarrateMediaPlayed(OperationOutcome outcome)
    {
        if (outcome.Result is { ValueKind: JsonValueKind.Object } result
            && result.TryGetProperty("title", out JsonElement title)
            && title.ValueKind == JsonValueKind.String)
            return $"Listo, está sonando «{title.GetString()}».";
        return "Listo, la reproducción quedó iniciada y verificada.";
    }

    private static string NarrateSystemTime(OperationOutcome outcome)
    {
        if (outcome.Result is not { ValueKind: JsonValueKind.Object } result
            || !result.TryGetProperty("version", out JsonElement versionElement)
            || !versionElement.TryGetInt32(out int version)
            || version != 1
            || !result.TryGetProperty("utc", out JsonElement utcElement)
            || utcElement.ValueKind != JsonValueKind.String
            || !DateTimeOffset.TryParseExact(
                utcElement.GetString(),
                "O",
                CultureInfo.InvariantCulture,
                DateTimeStyles.RoundtripKind,
                out DateTimeOffset utc)
            || utc.Offset != TimeSpan.Zero
            || !result.TryGetProperty("localUtcOffsetMinutes", out JsonElement offsetElement)
            || !offsetElement.TryGetInt32(out int offsetMinutes)
            || offsetMinutes is < -14 * 60 or > 14 * 60)
        {
            return "Terminé de consultar la hora local.";
        }

        DateTimeOffset local = utc.ToOffset(TimeSpan.FromMinutes(offsetMinutes));
        string date = local.ToString("dd/MM/yyyy", CultureInfo.InvariantCulture);
        string time = local.ToString("HH:mm", CultureInfo.InvariantCulture);
        return $"La fecha local es {date} y la hora local es {time}.";
    }

    private static string NarrateProcessList(OperationOutcome outcome)
    {
        ProcessListResult? result = ReadResult(
            outcome,
            CoreJsonContext.Default.ProcessListResult);
        if (result is null || result.Processes.Count == 0)
        {
            return "Terminé de consultar los procesos actuales.";
        }
        string order = result.Sort switch
        {
            "cpu" => "CPU acumulada",
            "memory" => "memoria",
            _ => "nombre",
        };
        string processes = string.Join(
            ", ",
            result.Processes.Select(static item => $"{item.Name} (PID {item.ProcessId})"));
        return $"Procesos verificados por {order}: {processes}.";
    }

    private static string NarrateMediaStatus(OperationOutcome outcome)
    {
        if (outcome.Result is not { ValueKind: JsonValueKind.Object } result
            || !result.TryGetProperty("title", out JsonElement titleElement)
            || titleElement.ValueKind != JsonValueKind.String
            || !result.TryGetProperty("artist", out JsonElement artistElement)
            || artistElement.ValueKind != JsonValueKind.String
            || !result.TryGetProperty("playbackStatus", out JsonElement statusElement)
            || statusElement.ValueKind != JsonValueKind.String)
        {
            return "Terminé de consultar la reproducción actual.";
        }

        string title = titleElement.GetString()?.Trim() ?? string.Empty;
        string artist = artistElement.GetString()?.Trim() ?? string.Empty;
        string status = statusElement.GetString()?.Trim().ToLowerInvariant() ?? string.Empty;
        if (title.Length == 0)
        {
            return "No hay ninguna reproducción identificable en este momento.";
        }

        string item = artist.Length == 0 ? $"«{title}»" : $"«{title}» de {artist}";
        return status switch
        {
            "playing" => $"Está sonando {item}.",
            "paused" => $"Está en pausa {item}.",
            _ => $"La sesión multimedia actual muestra {item} ({status}).",
        };
    }

    private static string NarrateMediaSeek(OperationOutcome outcome)
    {
        if (outcome.Result is not { ValueKind: JsonValueKind.Object } result
            || !result.TryGetProperty("requestedDeltaSeconds", out JsonElement deltaElement)
            || !deltaElement.TryGetInt32(out int delta)
            || delta == 0)
        {
            return "Listo, cambié y verifiqué la posición de la reproducción.";
        }

        return delta > 0
            ? $"Listo, adelanté {delta} segundos y verifiqué la posición."
            : $"Listo, retrocedí {Math.Abs(delta)} segundos y verifiqué la posición.";
    }

    private static string NarrateDnsStatus(OperationOutcome outcome)
    {
        if (outcome.Result is not { ValueKind: JsonValueKind.Object } result
            || !result.TryGetProperty("serverAddresses", out JsonElement servers)
            || servers.ValueKind != JsonValueKind.Array)
        {
            return "La configuración DNS activa quedó verificada.";
        }

        string[] addresses = servers.EnumerateArray()
            .Where(static item => item.ValueKind == JsonValueKind.String)
            .Select(static item => item.GetString()?.Trim() ?? string.Empty)
            .Where(static item => item.Length > 0)
            .ToArray();
        return addresses.Length == 0
            ? "Windows no informa servidores DNS en las interfaces activas."
            : $"Servidores DNS activos verificados: {string.Join(", ", addresses)}.";
    }

    private static string NarrateNetworkPing(OperationOutcome outcome)
    {
        if (outcome.Result is not { ValueKind: JsonValueKind.Object } result
            || !result.TryGetProperty("host", out JsonElement hostElement)
            || hostElement.ValueKind != JsonValueKind.String
            || !result.TryGetProperty("reachable", out JsonElement reachableElement))
        {
            return "El diagnóstico de ping quedó verificado.";
        }

        string host = hostElement.GetString() ?? "el host";
        if (reachableElement.ValueKind != JsonValueKind.True)
        {
            string status = result.TryGetProperty("status", out JsonElement statusElement)
                && statusElement.ValueKind == JsonValueKind.String
                    ? statusElement.GetString() ?? "sin respuesta"
                    : "sin respuesta";
            return $"{host} no respondió al ping; estado verificado: {status}.";
        }

        long milliseconds = result.TryGetProperty(
            "roundtripMilliseconds", out JsonElement roundtripElement)
            && roundtripElement.TryGetInt64(out long observed) ? observed : 0;
        return $"{host} respondió al ping en {milliseconds} ms.";
    }

    private static string NarrateSystemIdentity(OperationOutcome outcome)
    {
        if (outcome.Result is { ValueKind: JsonValueKind.Object } result
            && result.TryGetProperty("qualifiedName", out JsonElement identity)
            && identity.ValueKind == JsonValueKind.String
            && !string.IsNullOrWhiteSpace(identity.GetString()))
        {
            return $"El usuario efectivo de Windows es {identity.GetString()}.";
        }
        return "La identidad efectiva de Windows quedó verificada.";
    }

    private static string NarrateBluetoothRadio(OperationOutcome outcome)
    {
        bool enabled = outcome.Result is { ValueKind: JsonValueKind.Object } result
            && result.TryGetProperty("state", out JsonElement state)
            && state.ValueKind == JsonValueKind.True;
        return enabled
            ? "Listo, Bluetooth está encendido y verificado."
            : "Listo, Bluetooth está apagado y verificado.";
    }

    private static string NarratePeripheralList(OperationOutcome outcome)
    {
        if (outcome.Result is not { ValueKind: JsonValueKind.Object } result
            || !result.TryGetProperty("devices", out JsonElement devices)
            || devices.ValueKind != JsonValueKind.Array)
        {
            return "Terminé de consultar los periféricos conectados.";
        }

        string requestedKind = result.TryGetProperty("requestedKind", out JsonElement kind)
            && kind.ValueKind == JsonValueKind.String
                ? kind.GetString()?.Trim().ToLowerInvariant() ?? "all"
                : "all";
        string[] names = devices.EnumerateArray()
            .Select(device => device.TryGetProperty("name", out JsonElement name)
                && name.ValueKind == JsonValueKind.String
                    ? name.GetString()?.Trim() ?? string.Empty
                    : string.Empty)
            .Where(name => name.Length > 0)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Take(12)
            .ToArray();
        if (names.Length == 0)
        {
            return requestedKind switch
            {
                "mouse" => "No encontré ningún mouse o dispositivo apuntador conectado.",
                "keyboard" => "No encontré ningún teclado conectado.",
                "printer" => "No encontré ninguna impresora conectada.",
                "scanner" => "No encontré ningún escáner conectado.",
                "usb" => "No encontré ningún dispositivo USB conectado.",
                _ => "No encontré periféricos conectados.",
            };
        }

        string joinedNames = string.Join(", ", names);
        return requestedKind switch
        {
            "mouse" => $"Mouse y dispositivos apuntadores detectados: {joinedNames}.",
            "keyboard" => $"Teclados detectados: {joinedNames}.",
            "printer" => $"Impresoras detectadas: {joinedNames}.",
            "scanner" => $"Escáneres detectados: {joinedNames}.",
            "usb" => $"Dispositivos USB detectados: {joinedNames}.",
            _ => $"Periféricos conectados: {joinedNames}.",
        };
    }

    private static string NarrateAppOpen(OperationOutcome outcome)
    {
        OpenApplicationResult? result = ReadResult(
            outcome,
            CoreJsonContext.Default.OpenApplicationResult);
        if (result is null)
        {
            return "La aplicación quedó abierta.";
        }

        return result.AlreadyRunning
            ? $"Listo, enfoqué {result.DisplayName}."
            : $"Listo, abrí {result.DisplayName}.";
    }

    private static string NarrateAppOpenFailure(OperationOutcome outcome)
    {
        string errorCode = outcome.ErrorCode ?? "application_open_failed";
        if (outcome.EffectMayHaveOccurred)
        {
            return errorCode switch
            {
                "app_not_found" =>
                    "No pude resolver el catálogo local durante la reconciliación; Bloc de notas puede haber quedado abierto.",
                "verification_failed" =>
                    "La apertura pudo haber comenzado, pero no pude corroborar la identidad, ventana visible y foco; Bloc de notas puede haber quedado abierto.",
                "inventory_failed" =>
                    "La apertura pudo haber comenzado, pero perdí la observación segura del proceso; Bloc de notas puede haber quedado abierto.",
                "state_capacity_reached" =>
                    "La apertura pudo haber comenzado, pero no pude conservar su recibo durable; Bloc de notas puede haber quedado abierto.",
                "state_corrupt" =>
                    "La apertura pudo haber comenzado, pero el recibo durable dejó de ser confiable; Bloc de notas puede haber quedado abierto.",
                "state_unavailable" =>
                    "La apertura pudo haber comenzado, pero no pude confirmar el recibo durable; Bloc de notas puede haber quedado abierto.",
                _ => "La apertura comenzó, pero no pude corroborar su estado final.",
            };
        }

        return errorCode switch
        {
            "invalid_arguments" =>
                "La solicitud para abrir la aplicación no tiene el formato esperado.",
            "app_ambiguous" =>
                "Encontré varias aplicaciones con un nombre parecido. Dime el nombre exacto que aparece en Inicio.",
            "app_not_found" => "No encontré esa aplicación instalada en este equipo.",
            "invalid_application" => "Esa aplicación no pertenece al catálogo local permitido.",
            "invalid_invocation" => "La identidad durable de esta apertura no es válida.",
            "inventory_failed" =>
                "No pude inventariar las instancias existentes sin riesgo de abrir un duplicado.",
            "launch_failed" => "No pude abrir la aplicación de forma segura.",
            "state_capacity_reached" =>
                "El historial durable de aperturas alcanzó su capacidad; no abrí otra instancia.",
            "state_corrupt" =>
                "El recibo durable no superó la comprobación de integridad; no inicié otra instancia en este intento, pero una apertura anterior puede seguir abierta.",
            "state_unavailable" =>
                "El almacenamiento durable no está disponible; no inicié otra instancia en este intento, pero una apertura anterior puede seguir abierta.",
            "verification_failed" =>
                "No pude corroborar la identidad, ventana visible y foco de la aplicación.",
            _ => "No pude completar la apertura de la aplicación.",
        };
    }

    private static string NarrateAudioMute(OperationOutcome outcome)
    {
        AudioControlResult? result = ReadResult(outcome, CoreJsonContext.Default.AudioControlResult);
        if (result is null)
        {
            return "El estado de silencio quedó confirmado.";
        }

        bool muted = result.Final.Muted;
        return result.Reconciled
            ? muted
                ? "Confirmé que el audio del sistema está silenciado tras recuperar el intento."
                : "Confirmé que el audio del sistema está activo tras recuperar el intento."
            : muted
                ? result.Applied
                    ? "Listo, silencié el audio del sistema."
                    : "Listo, el audio del sistema ya estaba silenciado."
                : result.Applied
                    ? "Listo, reactivé el audio del sistema."
                    : "Listo, el audio del sistema ya estaba activo.";
    }

    private static string NarrateAudioVolume(OperationOutcome outcome)
    {
        AudioControlResult? result = ReadResult(outcome, CoreJsonContext.Default.AudioControlResult);
        if (result is null)
        {
            return "El volumen quedó confirmado.";
        }

        int volume = result.Final.VolumePercent;
        return result.Reconciled
            ? $"Confirmé que el volumen del sistema está en {volume} % tras recuperar el intento."
            : result.Applied
                ? $"Listo, el volumen del sistema quedó en {volume} %."
                : $"Listo, el volumen del sistema ya estaba en {volume} %.";
    }

    private static string NarrateAudioStatus(OperationOutcome outcome)
    {
        AudioStatusResult? result = ReadResult(outcome, CoreJsonContext.Default.AudioStatusResult);
        if (result is null)
        {
            return "El estado del audio quedó confirmado.";
        }

        string muteState = result.State.Muted ? "silenciado" : "activo";
        return $"El volumen de la salida predeterminada está en {result.State.VolumePercent} % y el audio está {muteState}.";
    }

    private static string NarrateAudioControlFailure(
        string operation,
        OperationOutcome outcome)
    {
        if (outcome.ErrorCode == "invalid_arguments")
        {
            return operation == AudioOperationIds.Mute
                ? "El estado de silencio debe ser verdadero o falso."
                : "El nivel de volumen debe ser un entero entre 0 y 100.";
        }

        string errorCode = outcome.CauseCode ?? outcome.ErrorCode ?? string.Empty;
        string message = AudioControlFailureMessage(errorCode, outcome.EffectMayHaveOccurred);
        return outcome.Retryable
            ? message
                + " Debo reconciliar este mismo intento antes de aceptar otra acción; repite la misma petición."
            : message;
    }

    private static string AudioControlFailureMessage(string errorCode, bool mayHaveChanged)
    {
        if (mayHaveChanged)
        {
            return errorCode switch
            {
                AudioControlErrorCodes.EndpointChanged =>
                    "La salida predeterminada cambió durante el ajuste; el audio pudo haber cambiado y no repetí la acción sobre el dispositivo nuevo.",
                AudioControlErrorCodes.StateCapacityReached =>
                    "El audio pudo haber cambiado, pero el historial durable alcanzó su capacidad y no pude conservar una verificación confiable.",
                AudioControlErrorCodes.StateCorrupt =>
                    "El audio pudo haber cambiado, pero su recibo durable dejó de ser confiable.",
                AudioControlErrorCodes.StateUnavailable =>
                    "El audio pudo haber cambiado, pero no pude confirmar su recibo durable.",
                _ => "El audio pudo haber cambiado, pero no pude corroborar su estado final.",
            };
        }

        return errorCode switch
        {
            AudioControlErrorCodes.InvalidInvocation =>
                "La identidad durable del ajuste de audio no es válida.",
            AudioControlErrorCodes.InvalidLevel => "El nivel de volumen solicitado no es válido.",
            AudioControlErrorCodes.AudioBusy =>
                "El control de audio está ocupado; no inicié otro ajuste.",
            AudioControlErrorCodes.NoDefaultOutput =>
                "No encontré una salida de audio predeterminada.",
            AudioControlErrorCodes.AudioServiceUnavailable =>
                "El servicio de audio de Windows no está disponible.",
            AudioControlErrorCodes.EndpointUnavailable =>
                "La salida de audio dejó de estar disponible antes de completar el ajuste.",
            AudioControlErrorCodes.EndpointChanged =>
                "La salida predeterminada cambió durante el ajuste; no repetí la acción sobre el dispositivo nuevo.",
            AudioControlErrorCodes.OperationFailed => "No pude aplicar el ajuste de audio.",
            AudioControlErrorCodes.EffectUncertain =>
                "El audio pudo haber cambiado, pero no pude corroborar su estado final.",
            AudioControlErrorCodes.StateCorrupt =>
                "El recibo durable del audio no superó la comprobación de integridad.",
            AudioControlErrorCodes.StateCapacityReached =>
                "El historial durable de audio alcanzó su capacidad; no inicié otro ajuste.",
            AudioControlErrorCodes.StateUnavailable =>
                "El almacenamiento durable del audio no está disponible; no inicié otro ajuste.",
            _ => "No pude corroborar el estado final del audio.",
        };
    }

    private static string NarrateAudioStatusFailure(string? errorCode) => errorCode switch
    {
        "invalid_arguments" => "La consulta de audio no acepta argumentos.",
        AudioControlErrorCodes.InvalidInvocation =>
            "La identidad de la consulta de audio no es válida.",
        AudioControlErrorCodes.AudioBusy =>
            "El control de audio está ocupado; no pude leer un estado coherente.",
        AudioControlErrorCodes.NoDefaultOutput =>
            "No encontré una salida de audio predeterminada.",
        AudioControlErrorCodes.AudioServiceUnavailable =>
            "El servicio de audio de Windows no está disponible.",
        AudioControlErrorCodes.VerificationFailed =>
            "No pude corroborar el estado actual del audio.",
        _ => "La salida de audio no está disponible.",
    };

    private static string NarrateNote(OperationOutcome outcome, string format)
    {
        NoteResult? result = ReadResult(outcome, CoreJsonContext.Default.NoteResult);
        return result is null
            ? "La nota quedó actualizada."
            : string.Format(System.Globalization.CultureInfo.InvariantCulture, format, result.Title);
    }

    private static string NarrateTask(OperationOutcome outcome, string format)
    {
        TaskResult? result = ReadResult(outcome, CoreJsonContext.Default.TaskResult);
        return result is null || string.IsNullOrWhiteSpace(result.Title)
            ? "La tarea quedó actualizada y verificada."
            : string.Format(CultureInfo.InvariantCulture, format, result.Title);
    }

    private static string NarrateTaskList(OperationOutcome outcome)
    {
        TaskListResult? result = ReadResult(outcome, CoreJsonContext.Default.TaskListResult);
        if (result is null)
        {
            return "Terminé de consultar las tareas.";
        }

        return result.Count switch
        {
            0 => "No encontré tareas en esa lista.",
            1 => "Encontré una tarea en esa lista.",
            _ => $"Encontré {result.Count} tareas en esa lista.",
        };
    }

    private static string NarrateTaskSelection(OperationOutcome outcome)
    {
        TaskSelectionResult? result = ReadResult(
            outcome,
            CoreJsonContext.Default.TaskSelectionResult);
        return result is null || string.IsNullOrWhiteSpace(result.ReviewLabel)
            ? "Encontré la tarea exacta."
            : $"Encontré la tarea «{result.ReviewLabel}».";
    }

    private static string NarrateTaskFailure(OperationOutcome outcome) =>
        outcome.ErrorCode switch
        {
            "invalid_arguments" => "Los datos de la tarea no tienen el formato esperado.",
            "invalid_task" => "La tarea contiene datos no válidos o excede el límite permitido.",
            "task_not_found" => "No encontré esa tarea.",
            "task_ambiguous" =>
                "Encontré más de una tarea con ese título exacto; no hice cambios.",
            "task_version_conflict" =>
                "La tarea cambió desde la última consulta; no hice cambios.",
            "task_integrity_failed" =>
                "La tarea local no superó la comprobación de integridad.",
            "storage_failed" => "No pude guardar el cambio de forma segura.",
            "verification_failed" => "No pude verificar el estado final de la tarea.",
            _ => "No pude completar la petición sobre esa tarea.",
        };

    private static string NarrateNoteList(OperationOutcome outcome)
    {
        NoteListResult? result = ReadResult(outcome, CoreJsonContext.Default.NoteListResult);
        if (result is null)
        {
            return "Terminé de consultar las notas.";
        }

        return result.Count switch
        {
            0 => "No encontré notas en esa página.",
            1 => "Encontré una nota.",
            _ when result.Count < result.TotalCount =>
                $"Mostré {result.Count} de {result.TotalCount} notas.",
            _ => $"Encontré {result.Count} notas.",
        };
    }

    private static string NarrateNoteFailure(string operation, OperationOutcome outcome) =>
        outcome.ErrorCode switch
        {
            "invalid_arguments" => "Los datos de la nota no tienen el formato esperado.",
            "invalid_note" =>
                "La nota contiene datos no válidos o excede el límite permitido.",
            "note_not_found" when outcome.CauseCode == "by_title" =>
                "No encontré una nota con ese título exacto.",
            "note_not_found" => "No encontré esa nota.",
            "note_ambiguous" =>
                "Encontré más de una nota con ese título exacto; no hice cambios.",
            "note_selection_stale" =>
                "La lista de notas cambió; no hice cambios. Vuelve a pedir esa nota.",
            "idempotency_conflict" =>
                "La solicitud repetida no coincide con la nota original.",
            "note_capacity_reached" => "El almacén local alcanzó su capacidad de notas.",
            "note_integrity_failed" =>
                "La nota local no superó la comprobación de integridad.",
            "unsafe_storage" => "El almacenamiento local dejó de ser seguro.",
            "storage_failed" => "No pude guardar el cambio de forma segura.",
            "verification_failed" when operation == "note.trash" =>
                "No pude verificar que la nota quedara en la papelera.",
            "verification_failed" when operation == "note.restore" =>
                "No pude verificar la restauración de la nota.",
            _ => "No pude completar la petición sobre las notas.",
        };

    private static string NarrateSystemStatus(OperationOutcome outcome)
    {
        if (TryReadGpuResult(outcome, out GpuSystemStatusResult? gpu))
        {
            return SystemStatusNarration.BuildGpuMessage(gpu!);
        }

        SystemStatusResult? status = ReadResult(outcome, CoreJsonContext.Default.SystemStatusResult);
        return status is null
            ? "Terminé de consultar el estado del equipo."
            : SystemStatusNarration.BuildMessage(status);
    }

    private static string NarrateSystemStatusFailure(OperationOutcome outcome)
    {
        if (outcome.ErrorCode == "invalid_arguments")
        {
            return "La consulta de estado no tiene el formato esperado.";
        }

        if (outcome.ErrorCode == "verification_failed")
        {
            return outcome.CauseCode == "gpu_measurements"
                ? "Las mediciones de GPU no superaron la verificación de consistencia."
                : "Las mediciones del equipo no superaron la verificación de consistencia.";
        }

        if (TryReadGpuResult(outcome, out GpuSystemStatusResult? gpu))
        {
            return SystemStatusNarration.GpuFailureMessage(gpu!);
        }

        SystemStatusResult? status = ReadResult(outcome, CoreJsonContext.Default.SystemStatusResult);
        return status is null
            ? "No pude obtener ninguna medición verificable del estado del equipo."
            : SystemStatusNarration.FailureMessage(status.Scope);
    }

    private static bool TryReadGpuResult(
        OperationOutcome outcome,
        out GpuSystemStatusResult? result)
    {
        result = ReadResult(outcome, GpuSystemStatusJsonContext.Default.GpuSystemStatusResult);
        return result?.Scope is "gpu_identity" or "gpu_usage";
    }

    private static T? ReadResult<T>(OperationOutcome outcome, JsonTypeInfo<T> typeInfo)
        where T : class
    {
        if (outcome.Result is not { } result)
        {
            return null;
        }

        try
        {
            return JsonSerializer.Deserialize(result, typeInfo);
        }
        catch (JsonException)
        {
            return null;
        }
    }
}
