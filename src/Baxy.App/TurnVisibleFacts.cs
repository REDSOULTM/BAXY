using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// Hechos de un turno de shell. El modelo formula la frase; esto no se publica.
/// </summary>
internal static class TurnVisibleFacts
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    internal static readonly string[] ConfirmCancel =
        ["confirmar", "confirm", "cancelar", "cancel"];

    internal static readonly string[] ContinueCancel =
        ["continuar", "continue", "cancelar", "cancel"];

    internal static readonly string[] ContinueRetry =
        ["continuar", "continue", "retry"];

    internal static string Welcome() => Event("welcome");

    internal static string Failure(string cause, JsonObject? extra = null) =>
        Event("failure", cause, extra);

    internal static string LastResortFailureProse(string? cause)
    {
        // Only when the composer produced no text after its bounded retries.
        // The live prompt already names these causes; silence is the worse lie.
        string key = (cause ?? "").Trim().ToLowerInvariant();
        return key switch
        {
            "no_response" or "provider_down" or "composer_request_failed"
                or "composer_unavailable" => "No pude: no responde.",
            "timeout" => "No pude: se agotó el tiempo.",
            "composition_lost_verified_facts" =>
                "No pude: no pude formular el resultado.",
            _ => "No pude: no pude formular el resultado.",
        };
    }

    internal static string LastResortProse(
        string? cause,
        string? source,
        string? userText = null)
    {
        if (!string.IsNullOrWhiteSpace(source)
            && TryVerifiedFactsProse(source, userText) is { Length: > 0 } prose)
        {
            return prose;
        }

        if (IsAlreadyPersonFacing(source))
        {
            return source!.Trim();
        }

        if (cause is "echo_of_user" or "wrong_language_greeting"
            || UnderspecifiedUserTurn(userText))
        {
            return ConversationPrompt(userText);
        }

        return LastResortFailureProse(cause);
    }

    internal static bool UnderspecifiedUserTurn(string? userText)
    {
        if (string.IsNullOrWhiteSpace(userText))
        {
            return false;
        }

        string fold = userText.Trim();
        return fold.Length <= 2 && !RequestLooksEnglish(userText);
    }

    internal static string ConversationPrompt(string? userText) =>
        RequestLooksEnglish(userText) ? "Yes?" : "¿Sí?";

    internal static bool LooksLikeBareEnglishGreeting(string? modelText)
    {
        if (string.IsNullOrWhiteSpace(modelText))
        {
            return false;
        }

        string fold = modelText.Trim().ToLowerInvariant().TrimEnd('.', '!', '?');
        return fold is "hello" or "hi" or "hey" or "hello there";
    }

    internal static bool IsAlreadyPersonFacing(string? source)
    {
        if (string.IsNullOrWhiteSpace(source))
        {
            return false;
        }

        string trimmed = source.Trim();
        if (trimmed.StartsWith('{'))
        {
            return false;
        }

        string fold = trimmed.ToLowerInvariant();
        if (System.Text.RegularExpressions.Regex.IsMatch(
            trimmed,
            @"\b\d{9,}\b",
            System.Text.RegularExpressions.RegexOptions.CultureInvariant
                | System.Text.RegularExpressions.RegexOptions.NonBacktracking))
        {
            return false;
        }

        return fold.StartsWith("listo", StringComparison.Ordinal)
            || fold.StartsWith("guardé", StringComparison.Ordinal)
            || fold.StartsWith("guarde ", StringComparison.Ordinal)
            || fold.StartsWith("eliminé", StringComparison.Ordinal)
            || fold.StartsWith("elimine ", StringComparison.Ordinal)
            || fold.StartsWith("la memoria local", StringComparison.Ordinal)
            || fold.StartsWith("no había memoria", StringComparison.Ordinal)
            || fold.StartsWith("no habia memoria", StringComparison.Ordinal);
    }

    private static string? TryVerifiedFactsProse(string source, string? userText = null)
    {
        try
        {
            using JsonDocument document = JsonDocument.Parse(source);
            JsonElement root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object)
            {
                return null;
            }

            if (root.TryGetProperty("steps", out JsonElement steps)
                && steps.ValueKind == JsonValueKind.Array)
            {
                var parsed = new List<string>();
                foreach (JsonElement step in steps.EnumerateArray())
                {
                    if (step.ValueKind == JsonValueKind.String
                        && step.GetString() is { Length: > 0 } nested)
                    {
                        parsed.Add(nested);
                    }
                }

                var parts = new List<string>();
                foreach (string nested in parsed)
                {
                    if (TryVerifiedFactsProse(nested, userText) is { Length: > 0 } fromStep
                        && !IsSupportOnlyFact(nested, parsed))
                    {
                        parts.Add(fromStep);
                    }
                }

                if (parts.Count > 0)
                {
                    return string.Join(' ', parts);
                }
            }

            return TrySingleFactProse(root, userText);
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static bool IsSupportOnlyFact(string nested, IReadOnlyList<string> siblings)
    {
        string? operation = ReadJsonString(nested, "operation");
        if (operation is not "window.resolve" and not "window.active" and not "web.search"
            and not "capture.screenshot")
        {
            return false;
        }

        foreach (string sibling in siblings)
        {
            if (string.Equals(sibling, nested, StringComparison.Ordinal))
            {
                continue;
            }

            string? other = ReadJsonString(sibling, "operation");
            if (other is "app.close" or "app.open" or "browser.navigate"
                or "browser.navigate.named" or "ocr.read" or "input.text.type"
                or "input.visible.click" or "window.maximize" or "window.minimize"
                or "window.restore")
            {
                return true;
            }
        }

        return false;
    }

    private static string? TrySingleFactProse(JsonElement root, string? userText = null)
    {
        string? kind = ReadString(root, "kind");
        string? polarity = ReadString(root, "polarity");
        string? cause = ReadString(root, "cause");
        string? operation = ReadString(root, "operation");
        string? error = ReadString(root, "error")
            ?? ReadString(root, "reason")
            ?? (cause is "opened" or "focused" or "mission_completed" or "mission_failed"
                ? null
                : cause);
        bool uncertain = root.TryGetProperty("effectUncertain", out JsonElement uncertainNode)
            && uncertainNode.ValueKind is JsonValueKind.True;
        bool success = string.Equals(polarity, "success", StringComparison.Ordinal)
            || cause is "opened" or "focused" or "mission_completed";
        JsonElement observed = default;
        bool hasObserved = root.TryGetProperty("observed", out observed)
            && observed.ValueKind == JsonValueKind.Object;
        string? name = PersonFacingName(root, hasObserved ? observed : default);

        if (kind is "confirmation")
        {
            return ConfirmationProse(cause, root);
        }

        if (kind is "clarification")
        {
            return "¿Puedes precisarlo?";
        }

        if (string.Equals(cause, "memory_records", StringComparison.Ordinal)
            && root.TryGetProperty("records", out JsonElement records)
            && records.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement record in records.EnumerateArray())
            {
                string? value = record.ValueKind == JsonValueKind.Object
                    ? ReadString(record, "value")
                    : null;
                if (!string.IsNullOrWhiteSpace(value))
                {
                    return value.Trim();
                }
            }
        }

        if (!success)
        {
            return FailureProse(error, name, uncertain);
        }

        if (operation is "audio.volume" && hasObserved)
        {
            JsonElement volumeSource = observed;
            if (observed.TryGetProperty("final", out JsonElement final)
                && final.ValueKind == JsonValueKind.Object)
            {
                volumeSource = final;
            }

            if (TryReadInt(volumeSource, "volumePercent", out int percent))
            {
                return "Listo, el volumen está al " + percent + ".";
            }
        }

        if (operation is "reminder.create" or "notification.schedule")
        {
            string? title = hasObserved ? ReadString(observed, "title") : null;
            return string.IsNullOrWhiteSpace(title)
                ? "Listo, te aviso."
                : "Listo, te aviso " + title + ".";
        }

        if (operation is "note.create")
        {
            string? title = hasObserved ? ReadString(observed, "title") : null;
            return string.IsNullOrWhiteSpace(title)
                ? "Listo, anoté."
                : "Listo, anoté " + title + ".";
        }

        if (operation is "media.status" && hasObserved)
        {
            string? title = ReadString(observed, "title");
            string? playback = ReadString(observed, "playbackStatus");
            if (string.Equals(playback, "paused", StringComparison.OrdinalIgnoreCase))
            {
                return string.IsNullOrWhiteSpace(title)
                    ? "Listo, la reproducción está en pausa."
                    : "Listo, está en pausa " + title + ".";
            }

            if (!string.IsNullOrWhiteSpace(title))
            {
                return "Listo, está sonando " + title + ".";
            }

            return "Listo, no hay nada sonando.";
        }

        if (operation is "audio.status" && hasObserved)
        {
            if (observed.TryGetProperty("muted", out JsonElement muted)
                && muted.ValueKind is JsonValueKind.True)
            {
                return "Listo, el audio está silenciado.";
            }

            if (TryReadInt(observed, "volumePercent", out int percent)
                || (observed.TryGetProperty("final", out JsonElement audioFinal)
                    && audioFinal.ValueKind == JsonValueKind.Object
                    && TryReadInt(audioFinal, "volumePercent", out percent)))
            {
                return "Listo, el volumen está al " + percent + ".";
            }
        }

        if (operation is "media.play.query" or "media.play.exact"
            or "media.play.youtube" or "streaming.play.named" or "media.control")
        {
            string? title = hasObserved ? ReadString(observed, "title") : null;
            string? playback = hasObserved ? ReadString(observed, "playbackStatus") : null;
            if (string.Equals(playback, "paused", StringComparison.OrdinalIgnoreCase)
                || string.Equals(operation, "media.control", StringComparison.Ordinal)
                    && string.IsNullOrWhiteSpace(title))
            {
                return "Listo, pausé la música.";
            }

            if (!string.IsNullOrWhiteSpace(title))
            {
                return "Listo, está sonando " + title + ".";
            }
        }

        if (operation is "input.text.type")
        {
            string? text = hasObserved ? ReadString(observed, "text") : null;
            return string.IsNullOrWhiteSpace(text)
                ? "Listo, escribí."
                : "Listo, escribí " + text + ".";
        }

        if (operation is "input.visible.click")
        {
            string? label = hasObserved
                ? ReadString(observed, "label") ?? ReadString(observed, "name")
                : null;
            return string.IsNullOrWhiteSpace(label)
                ? "Listo, hice click."
                : "Listo, hice click en " + label + ".";
        }

        if (operation is "input.key.press")
        {
            string? key = hasObserved ? ReadString(observed, "key") : null;
            return string.IsNullOrWhiteSpace(key)
                ? "Listo, apreté la tecla."
                : "Listo, apreté " + key + ".";
        }

        if (operation is "system.time" && hasObserved)
        {
            string? local = ReadString(observed, "localTime");
            if (!string.IsNullOrWhiteSpace(local) && local.Length >= 16)
            {
                string clock = local.Contains('T', StringComparison.Ordinal)
                    ? local[(local.IndexOf('T') + 1)..Math.Min(local.IndexOf('T') + 6, local.Length)]
                    : local;
                return RequestLooksEnglish(userText)
                    ? "Ready, it's " + clock + "."
                    : "Listo, son las " + clock + ".";
            }
        }

        if (operation is "system.status" && hasObserved)
        {
            return StatusReadingsProse(observed, RequestLooksEnglish(userText));
        }

        if ((operation is "browser.navigate" or "browser.navigate.named") && hasObserved)
        {
            string? url = ReadString(observed, "finalUrl")
                ?? ReadString(observed, "requestedUrl");
            if (!string.IsNullOrWhiteSpace(url)
                && Uri.TryCreate(url, UriKind.Absolute, out Uri? uri)
                && !string.IsNullOrWhiteSpace(uri.Host))
            {
                return "Listo, abrí " + uri.Host + ".";
            }
        }

        if (operation is "web.search" && hasObserved)
        {
            string? query = ReadString(observed, "query");
            return string.IsNullOrWhiteSpace(query)
                ? "Listo, busqué."
                : "Listo, busqué " + query + ".";
        }

        if (operation is "window.maximize")
        {
            return "Listo, maximicé la ventana.";
        }

        if (operation is "window.minimize")
        {
            return "Listo, minimicé la ventana.";
        }

        if (operation is "window.restore")
        {
            return "Listo, restauré la ventana.";
        }

        if (operation is "app.close"
            || (hasObserved && observed.TryGetProperty("windowClosed", out JsonElement closed)
                && closed.ValueKind is JsonValueKind.True))
        {
            if (string.IsNullOrWhiteSpace(name))
            {
                return "Listo, cerré la ventana.";
            }

            return Feminine(name)
                ? "Listo, " + name + " está cerrada."
                : "Listo, " + name + " está cerrado.";
        }

        if (!string.IsNullOrWhiteSpace(name)
            && (operation is "app.open" or "window.resolve" or "window.active" or null
                || cause is "opened" or "focused" or "mission_completed"))
        {
            return Feminine(name)
                ? "Listo, " + name + " está abierta."
                : "Listo, " + name + " está abierto.";
        }

        return null;
    }

    private static string? StatusReadingsProse(JsonElement observed, bool english)
    {
        var parts = new List<string>();
        if (observed.TryGetProperty("disk", out JsonElement disk)
            && TryReadLong(disk, "availableBytes", out long diskBytes))
        {
            parts.Add(
                english
                    ? FormatBytes(diskBytes, english) + " free on disk"
                    : "quedan " + FormatBytes(diskBytes, english) + " libres en disco");
        }

        if (observed.TryGetProperty("memory", out JsonElement memory)
            && TryReadLong(memory, "availableBytes", out long memoryBytes))
        {
            parts.Add(
                english
                    ? FormatBytes(memoryBytes, english) + " of memory available"
                    : "hay " + FormatBytes(memoryBytes, english) + " de memoria disponibles");
        }

        if (observed.TryGetProperty("battery", out JsonElement battery)
            && TryReadInt(battery, "chargePercent", out int charge))
        {
            parts.Add(
                english
                    ? "the battery is at " + charge + "%"
                    : "la batería está al " + charge + "%");
        }

        if (parts.Count == 0)
        {
            return null;
        }

        string joined = string.Join(english ? " and " : " y ", parts);
        return english ? "Ready, " + joined + "." : "Listo, " + joined + ".";
    }

    internal static bool RequestLooksEnglish(string? userText)
    {
        if (string.IsNullOrWhiteSpace(userText))
        {
            return false;
        }

        string fold = userText.Trim().ToLowerInvariant();
        return fold.StartsWith("hello", StringComparison.Ordinal)
            || fold.StartsWith("hi ", StringComparison.Ordinal)
            || fold.StartsWith("hi?", StringComparison.Ordinal)
            || fold.StartsWith("hey", StringComparison.Ordinal)
            || fold is "hi"
            || fold.Contains("how much", StringComparison.Ordinal)
            || fold.Contains("disk space", StringComparison.Ordinal)
            || fold.Contains("free disk", StringComparison.Ordinal)
            || fold.Contains("free space", StringComparison.Ordinal)
            || fold.Contains("what time is it", StringComparison.Ordinal)
            || fold.Contains("what's the time", StringComparison.Ordinal)
            || fold.Contains("whats the time", StringComparison.Ordinal)
            || fold.Contains("tell me the time", StringComparison.Ordinal);
    }

    private static string FormatBytes(long bytes, bool english)
    {
        double giga = bytes / 1_073_741_824d;
        if (giga >= 1)
        {
            string number = giga >= 10
                ? ((int)Math.Round(giga, MidpointRounding.AwayFromZero)).ToString(
                    System.Globalization.CultureInfo.InvariantCulture)
                : giga.ToString(
                    english ? "0.0" : "0.0",
                    System.Globalization.CultureInfo.InvariantCulture);
            if (!english)
            {
                number = number.Replace('.', ',');
            }

            return number + " GB";
        }

        double mega = bytes / 1_048_576d;
        return ((int)Math.Round(mega, MidpointRounding.AwayFromZero)).ToString(
            System.Globalization.CultureInfo.InvariantCulture) + " MB";
    }

    private static string ConfirmationProse(string? cause, JsonElement root)
    {
        bool hasContinuar = HasChoice(root, "continuar") || HasChoice(root, "continue");
        bool hasConfirmar = HasChoice(root, "confirmar") || HasChoice(root, "confirm");
        bool hasCancelar = HasChoice(root, "cancelar") || HasChoice(root, "cancel");
        return cause switch
        {
            "memory_recovery_pending" =>
                "Quedó una operación de memoria pendiente. Escribe continuar o reintentar.",
            "memory_reconcile_only" or "memory_reconcile_same_attempt"
                or "cannot_withdraw_uncertain" =>
                "Esa memoria puede haber cambiado. ¿Confirmas?",
            "pending_audio_reconcile" or "audio_volume_pending" or "audio_mute_pending" =>
                "Quedó un ajuste de audio pendiente. Escribe continuar o reintentar.",
            _ when hasContinuar =>
                "Quedó una operación pendiente. Escribe continuar o reintentar.",
            _ when hasConfirmar && hasCancelar =>
                "¿Confirmas o cancelas?",
            _ when hasConfirmar =>
                "¿Confirmas?",
            _ => "¿Confirmas o cancelas?",
        };
    }

    private static bool HasChoice(JsonElement root, string value)
    {
        if (!root.TryGetProperty("choices", out JsonElement choices)
            || choices.ValueKind != JsonValueKind.Array)
        {
            return false;
        }

        foreach (JsonElement choice in choices.EnumerateArray())
        {
            if (choice.ValueKind == JsonValueKind.String
                && string.Equals(choice.GetString(), value, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }

        return false;
    }

    private static string? FailureProse(string? error, string? name, bool uncertain)
    {
        if (error is "visible_click_no_receipt"
            or "visible_button_not_found"
            or "visible_button_uia_failed"
            or "visible_button_not_invokable"
            or "visible_click_receipt_invalid"
            or "visible_click_postread_invalid"
            or "visible_button_postread_unchanged"
            or "visible_click_argument_invalid"
            or "active_window_not_found"
            or "visible_button_ambiguous")
        {
            return "No pude: no vi el control.";
        }

        if (string.Equals(error, "window_not_found", StringComparison.Ordinal))
        {
            return "No pude: no lo encontré.";
        }

        if (string.Equals(error, "external_provider_failed", StringComparison.Ordinal))
        {
            return "No pude: el proveedor externo falló.";
        }

        if (string.Equals(error, "netflix_authentication_required", StringComparison.Ordinal))
        {
            return "No pude: Netflix pide iniciar sesión.";
        }

        if (error is "vision_provider_not_configured"
            or "vision_session_adapter_required")
        {
            return "No pude: no tengo visión configurada.";
        }

        if (string.Equals(error, "external_verification_failed", StringComparison.Ordinal))
        {
            return "No pude: no pude leer eso.";
        }

        if (string.Equals(error, "power_transition_physical_gate_required", StringComparison.Ordinal))
        {
            return "No pude: no apago ni reinicio este equipo desde esta campaña.";
        }

        if (string.Equals(error, "memory_forget_empty", StringComparison.Ordinal))
        {
            return "No pude: no encontré esa memoria.";
        }

        if (string.Equals(error, "recipient_identity_not_verified", StringComparison.Ordinal))
        {
            return "No pude: no pude confirmar el destinatario.";
        }

        if (!string.IsNullOrWhiteSpace(error)
            && error.Contains("spotify", StringComparison.OrdinalIgnoreCase))
        {
            return "No pude: Spotify no confirmó la reproducción.";
        }

        if (!string.IsNullOrWhiteSpace(error)
            && error.Contains("youtube", StringComparison.OrdinalIgnoreCase))
        {
            return "No pude: YouTube no confirmó la reproducción.";
        }

        if (string.Equals(error, "verification_failed", StringComparison.Ordinal))
        {
            return string.IsNullOrWhiteSpace(name)
                ? "No pude: no pude confirmar que se abrió."
                : "No pude: " + name + " no responde.";
        }

        if (uncertain)
        {
            return "No pude: no pude comprobarlo.";
        }

        if (!string.IsNullOrWhiteSpace(name))
        {
            return "No pude: " + name + " no responde.";
        }

        return null;
    }

    private static string? PersonFacingName(JsonElement root, JsonElement observed)
    {
        if (observed.ValueKind == JsonValueKind.Object)
        {
            string? display = ReadString(observed, "displayName");
            if (!string.IsNullOrWhiteSpace(display))
            {
                return display;
            }

            if (observed.TryGetProperty("windows", out JsonElement windows)
                && windows.ValueKind == JsonValueKind.Array)
            {
                foreach (JsonElement window in windows.EnumerateArray())
                {
                    if (window.ValueKind != JsonValueKind.Object)
                    {
                        continue;
                    }

                    string? windowName = ReadString(window, "displayName")
                        ?? ReadString(window, "title")
                        ?? ReadString(window, "processName");
                    if (!string.IsNullOrWhiteSpace(windowName)
                        && !string.Equals(
                            windowName,
                            "ApplicationFrameHost",
                            StringComparison.OrdinalIgnoreCase))
                    {
                        return ShortProcessName(windowName);
                    }
                }
            }

            string? process = ReadString(observed, "processName");
            if (!string.IsNullOrWhiteSpace(process)
                && !string.Equals(
                    process,
                    "ApplicationFrameHost",
                    StringComparison.OrdinalIgnoreCase))
            {
                return ShortProcessName(process);
            }
        }

        return ReadString(root, "displayName");
    }

    private static string ShortProcessName(string name)
    {
        string trimmed = name.Trim();
        if (trimmed.EndsWith(".exe", StringComparison.OrdinalIgnoreCase))
        {
            trimmed = trimmed[..^4];
        }

        int dot = trimmed.IndexOf('.');
        return dot > 0 ? trimmed[..dot] : trimmed;
    }

    private static bool Feminine(string name) =>
        name.EndsWith('a')
        || name.Contains("calculadora", StringComparison.OrdinalIgnoreCase);

    private static string? ReadString(JsonElement root, string name)
    {
        return root.TryGetProperty(name, out JsonElement value)
            && value.ValueKind == JsonValueKind.String
                ? value.GetString()
                : null;
    }

    private static string? ReadJsonString(string json, string name)
    {
        try
        {
            using JsonDocument document = JsonDocument.Parse(json);
            return ReadString(document.RootElement, name);
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static bool TryReadInt(JsonElement root, string name, out int value)
    {
        value = 0;
        if (!root.TryGetProperty(name, out JsonElement node))
        {
            return false;
        }

        if (node.ValueKind == JsonValueKind.Number && node.TryGetInt32(out value))
        {
            return true;
        }

        return node.ValueKind == JsonValueKind.Number
            && node.TryGetDouble(out double number)
            && (value = (int)Math.Round(number, MidpointRounding.AwayFromZero)) >= 0;
    }

    private static bool TryReadLong(JsonElement root, string name, out long value)
    {
        value = 0;
        if (!root.TryGetProperty(name, out JsonElement node)
            || node.ValueKind != JsonValueKind.Number)
        {
            return false;
        }

        if (node.TryGetInt64(out value))
        {
            return true;
        }

        if (node.TryGetDouble(out double number) && number >= 0)
        {
            value = (long)Math.Round(number, MidpointRounding.AwayFromZero);
            return true;
        }

        return false;
    }

    internal static string Status(string cause, JsonObject? extra = null) =>
        Event("status", cause, extra);

    internal static string Clarification(string cause, JsonObject? extra = null) =>
        Event("clarification", cause, extra);

    internal static string Confirmation(string cause, IReadOnlyList<string> choices, JsonObject? extra = null)
    {
        JsonObject payload = Base("confirmation", cause);
        var array = new JsonArray();
        foreach (string choice in choices)
        {
            array.Add(choice);
        }

        payload["choices"] = array;
        Merge(payload, extra);
        return payload.ToJsonString(JsonOptions);
    }

    internal static string Event(string kind, string? cause = null, JsonObject? extra = null)
    {
        JsonObject payload = Base(kind, cause);
        Merge(payload, extra);
        return payload.ToJsonString(JsonOptions);
    }

    private static JsonObject Base(string kind, string? cause)
    {
        string polarity = kind switch
        {
            "failure" or "error" => "failure",
            "confirmation" or "clarification" => "pending",
            _ => "success",
        };
        var payload = new JsonObject
        {
            ["kind"] = kind,
            ["polarity"] = polarity,
        };
        if (!string.IsNullOrWhiteSpace(cause))
        {
            payload["cause"] = cause;
        }

        return payload;
    }

    private static void Merge(JsonObject payload, JsonObject? extra)
    {
        if (extra is null)
        {
            return;
        }

        foreach ((string key, JsonNode? value) in extra)
        {
            payload[key] = value?.DeepClone();
        }
    }
}
