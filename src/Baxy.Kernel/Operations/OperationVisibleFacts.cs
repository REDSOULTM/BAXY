using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;

namespace Baxy.Kernel.Operations;

/// <summary>
/// Hechos de una operación ya verificada. El modelo formula la frase visible;
/// este texto no se publica.
/// </summary>
public static class OperationVisibleFacts
{
    // M106 (DEV-D v4a D-w08-t3 «ponme recordatorio una ora antes d ese partido»):
    // an observation over the budget used to be dropped whole, and so was one
    // with a repeated key, so a verified reminder reached the mind without its
    // title or time and every draft that said the time died as extra_claim. The
    // budget is the 8 KiB the observation always had (the message used to stop
    // at 4 KiB, so anything between the two vanished too); past it the
    // observation is projected (ObservedProjectionSteps) and the message says so
    // in ObservedLimitKey, which the trace counts.
    private const int MaximumMessageChars = 8_192;

    // How many placed lines a look at a chat drawn without an accessible tree keeps
    // (WindowsVisibleControlAdapter.PlacedLinesRead). Nothing here reads them apart:
    // they travel under the same budget as any other observation.
    public const int ChatLines = 200;
    public const string ObservedLimitKey = "observedLimit";
    public const string ObservedProjected = "projected";
    public const string ObservedOmitted = "omitted";
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    // Each step bounds every free-text string and every list; identifying and
    // asked fields (ObservedIdentityKeys) keep their text whole at every step.
    private static readonly (int Text, int Items)[] ObservedProjectionSteps =
        [(2_000, 20), (600, 10), (280, 5), (120, 3)];

    private static readonly HashSet<string> ObservedIdentityKeys = new(StringComparer.Ordinal)
    {
        "title", "name", "label", "reviewLabel", "displayName", "subject", "from", "sender",
        "query", "url", "host", "site", "folder", "askedFolder", "relativePath", "path", "fileName",
        "dueUtc", "due", "utc", "date", "time", "localTime", "weekday", "when", "at",
        "start", "startUtc", "end", "endUtc", "receivedUtc", "createdUtc",
        "state", "status", "mode", "kind", "operation", "authority", "unit",
        "app", "application", "process", "processName", "window", "windowTitle",
        "ssid", "device", "location", "city", "condition",
    };

    public static string FromOutcome(string operation, OperationOutcome outcome)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(operation);
        ArgumentNullException.ThrowIfNull(outcome);
        bool success = outcome.Succeeded && outcome.Verified;
        bool processInventory = operation == "system.process.list";
        bool ocrObservation = operation == "ocr.read";
        bool captureObservation = operation is "capture.active.window" or "capture.screenshot";
        // SHELL2075 «ejecutá dir en el escritorio»: the console adapter already
        // bounds what it returns (8 KiB of output and sixty lines), and with the
        // lines beside the text that bundle crosses 8 KiB, so the observation was
        // dropped whole and the final could say nothing of what came out.
        bool consoleOutput = operation == "shell.command.run";
        int messageLimit = processInventory || ocrObservation || consoleOutput ? ProtocolLimits.MaximumOperationResponseMessageChars : MaximumMessageChars;

        var payload = new JsonObject
        {
            ["kind"] = "operation",
            ["operation"] = operation,
            ["polarity"] = success ? "success" : "failure",
            ["verified"] = outcome.Verified,
            ["succeeded"] = outcome.Succeeded,
        };
        if (!string.IsNullOrWhiteSpace(outcome.ErrorCode))
        {
            payload["error"] = outcome.ErrorCode;
        }

        if (!string.IsNullOrWhiteSpace(outcome.CauseCode))
        {
            payload["cause"] = outcome.CauseCode;
        }

        if (outcome.Retryable)
        {
            payload["pending"] = true;
        }

        if (outcome.EffectMayHaveOccurred)
        {
            payload["effectUncertain"] = true;
        }

        JsonNode? sanitized = null;
        if (!outcome.ProtectedPrivateResult
            && outcome.Result is { } result
            && result.ValueKind is JsonValueKind.Object or JsonValueKind.Array)
        {
            // Read from the element itself: a repeated key keeps its last value,
            // as every other reader of the result does (JsonElement.GetProperty),
            // instead of failing the whole parse.
            bool cut = false;
            sanitized = Sanitize(
                result, ref cut,
                processInventory: processInventory, ocrObservation: ocrObservation,
                captureObservation: captureObservation);
            // Auditoría final V2: what the bounds below left out is said where the model reads, as the size budget
            // says it (WithProjectedObservation).
            if (cut && sanitized is JsonObject root)
            {
                root["truncated"] = true;
            }

            payload["observed"] = sanitized;
        }

        string json = payload.ToJsonString(JsonOptions);
        if (!ocrObservation && sanitized is not null && json.Length > messageLimit)
        {
            json = WithProjectedObservation(payload, sanitized, messageLimit);
        }
        if (ocrObservation && json.Length > messageLimit)
        {
            if (payload["observed"] is JsonObject observed && observed.ContainsKey("layout"))
            {
                observed["layout"] = OcrSizeLimit();
                json = payload.ToJsonString(JsonOptions);
            }
            if (json.Length > messageLimit)
            {
                payload["observed"] = OcrSizeLimit();
                json = payload.ToJsonString(JsonOptions);
            }
            if (json.Length > messageLimit)
            {
                payload.Remove("error");
                payload.Remove("cause");
                payload["messageDetailsOmitted"] = true;
                json = payload.ToJsonString(JsonOptions);
            }
        }
        if (json.Length > messageLimit && payload.Remove("observed"))
        {
            payload[ObservedLimitKey] = ObservedOmitted;
            json = payload.ToJsonString(JsonOptions);
        }

        return json.Length <= messageLimit
            ? json
            : json[..messageLimit];
    }

    public static string FromStatus(string operation, string status, string? errorCode) =>
        FromStatus(operation, status, errorCode, problems: null);

    /// <summary>The same facts, with the arguments a refused call got wrong (name and what it takes) when known.</summary>
    public static string FromStatus(
        string operation,
        string status,
        string? errorCode,
        IReadOnlyList<ArgumentProblem>? problems)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(operation);
        ArgumentException.ThrowIfNullOrWhiteSpace(status);
        bool pending = string.Equals(status, OperationStatuses.Pending, StringComparison.Ordinal);
        var payload = new JsonObject
        {
            ["kind"] = "operation",
            ["operation"] = operation,
            ["polarity"] = pending ? "pending" : "failure",
            ["status"] = status,
        };
        if (!string.IsNullOrWhiteSpace(errorCode))
        {
            payload["error"] = errorCode;
        }

        if (problems is { Count: > 0 })
        {
            payload["argumentProblems"] = ArgumentProblemsJson(problems);
        }

        return payload.ToJsonString(JsonOptions);
    }

    /// <summary>The arguments a call got wrong as the model reads them: one object per argument, name and problem.</summary>
    public static JsonArray ArgumentProblemsJson(IReadOnlyList<ArgumentProblem> problems) =>
        new([.. problems.Select(static problem => (JsonNode?)new JsonObject
        {
            ["argument"] = problem.Name,
            ["problem"] = problem.Problem,
        })]);

    /// <summary>
    /// The bound an operation message records for its observation
    /// (<see cref="ObservedProjected"/> or <see cref="ObservedOmitted"/>), or null
    /// when the observation travelled whole or there was none.
    /// </summary>
    public static string? ObservedLimit(string? message)
    {
        if (string.IsNullOrWhiteSpace(message) || !message.TrimStart().StartsWith('{'))
        {
            return null;
        }

        try
        {
            using JsonDocument document = JsonDocument.Parse(message);
            return document.RootElement.ValueKind == JsonValueKind.Object
                && document.RootElement.TryGetProperty(ObservedLimitKey, out JsonElement limit)
                && limit.ValueKind == JsonValueKind.String
                ? limit.GetString()
                : null;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    /// <summary>
    /// Where a provider says its time went (<c>observed.elapsedMs</c>, whole milliseconds by part), as a trace
    /// detail such as <c>elapsed.place.120.forecast.640</c>, or null when the observation carries none. Ronda 22:
    /// the weather's 5.3 s were one number; geocoding and forecast are told apart in the trace.
    /// </summary>
    public static string? ObservedElapsed(string? message)
    {
        if (string.IsNullOrWhiteSpace(message) || !message.TrimStart().StartsWith('{'))
        {
            return null;
        }

        try
        {
            using JsonDocument document = JsonDocument.Parse(message);
            if (document.RootElement.ValueKind != JsonValueKind.Object
                || !document.RootElement.TryGetProperty("observed", out JsonElement observed)
                || observed.ValueKind != JsonValueKind.Object
                || !observed.TryGetProperty("elapsedMs", out JsonElement elapsed)
                || elapsed.ValueKind != JsonValueKind.Object)
            {
                return null;
            }

            var parts = new List<string>();
            foreach (JsonProperty part in elapsed.EnumerateObject())
            {
                if (part.Value.ValueKind == JsonValueKind.Number
                    && part.Value.TryGetInt64(out long milliseconds)
                    && part.Name.Length is > 0 and <= 32
                    && part.Name.All(char.IsAsciiLetterOrDigit))
                {
                    parts.Add(part.Name.ToLowerInvariant() + "." + milliseconds.ToString(System.Globalization.CultureInfo.InvariantCulture));
                }
            }

            return parts.Count == 0 ? null : "elapsed." + string.Join('.', parts);
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static JsonObject OcrSizeLimit() => new()
    {
        ["available"] = false,
        ["reason"] = "observation_size_limit",
    };

    // The first projection step that cuts something and fits the message wins.
    // A cut observation says so in «truncated» (the field the mind already
    // reads as «more not shown»), and a cut list keeps its full length beside
    // it when the observation carries no count of its own. Nothing is added
    // that the observation did not hold.
    private static string WithProjectedObservation(JsonObject payload, JsonNode observed, int limit)
    {
        payload[ObservedLimitKey] = ObservedProjected;
        foreach ((int text, int items) in ObservedProjectionSteps)
        {
            bool cut = false;
            JsonNode projected = Project(observed, null, text, items, ref cut);
            if (!cut)
            {
                continue;
            }

            if (projected is JsonObject root)
            {
                root["truncated"] = true;
            }

            payload["observed"] = projected;
            string json = payload.ToJsonString(JsonOptions);
            if (json.Length <= limit)
            {
                return json;
            }
        }

        payload.Remove("observed");
        payload[ObservedLimitKey] = ObservedOmitted;
        return payload.ToJsonString(JsonOptions);
    }

    private static JsonNode Project(JsonNode node, string? key, int text, int items, ref bool cut)
    {
        switch (node)
        {
            case JsonObject obj:
                var projected = new JsonObject();
                foreach ((string name, JsonNode? value) in obj)
                {
                    projected[name] = value is null ? null : Project(value, name, text, items, ref cut);
                    if (value is JsonArray list && list.Count > items
                        && !obj.ContainsKey("count") && !obj.ContainsKey("totalCount")
                        && !obj.ContainsKey(name + "Count"))
                    {
                        projected[name + "Count"] = list.Count;
                    }
                }

                // A page of a text read by offset (file.read, web.fetch) whose text was cut here goes on from where
                // its shown text ends, not from where the provider's page ended: the model never skips text it did
                // not see (audit 2026-10-15, R2).
                if (obj["text"] is JsonValue whole && whole.TryGetValue(out string? read)
                    && projected["text"] is JsonValue part && part.TryGetValue(out string? shown)
                    && shown.Length < read.Length
                    && obj["offset"] is JsonValue offset && offset.TryGetValue(out int start))
                {
                    int shownCharacters = shown.Length - 1; // without the «…» that marks the cut
                    projected["hasMore"] = true;
                    projected["nextOffset"] = start + shownCharacters;
                    if (obj.ContainsKey("returnedCharacters"))
                    {
                        projected["returnedCharacters"] = shownCharacters;
                    }

                    // The provider's line count was of its whole page.
                    projected.Remove("lines");
                }

                return projected;
            case JsonArray array:
                var kept = new JsonArray();
                foreach (JsonNode? item in array.Take(items))
                {
                    kept.Add(item is null ? null : Project(item, key, text, items, ref cut));
                }

                cut |= array.Count > items;
                return kept;
            default:
                if (node.GetValueKind() == JsonValueKind.String
                    && (key is null || !ObservedIdentityKeys.Contains(key))
                    && node.GetValue<string>() is { } free
                    && free.Length > text)
                {
                    cut = true;
                    return JsonValue.Create(Shortened(free, text));
                }

                return node.DeepClone();
        }
    }

    // A text cut to «length» at a word boundary near the bound, never inside a
    // surrogate pair, marked with «…».
    private static string Shortened(string value, int length)
    {
        ArgumentNullException.ThrowIfNull(value);
        ArgumentOutOfRangeException.ThrowIfLessThan(length, 2);
        if (value.Length <= length)
        {
            return value;
        }

        int keep = length;
        if (char.IsHighSurrogate(value[keep - 1]))
        {
            keep--;
        }

        int space = value.LastIndexOf(' ', keep - 1, keep);
        if (space >= keep * 3 / 4)
        {
            keep = space;
        }

        return string.Concat(value.AsSpan(0, keep).TrimEnd(), "…");
    }

    // Held back from the model is only what is a secret or the kernel's own
    // bookkeeping: the confirmation «token», the request «fingerprint», the
    // invocation, request and mission ids, and window and process handles
    // («hwnd», «handle», «pid», «processId»), which no public operation takes.
    // An id a typed argument asks for travels: «id», «noteId» (note.update),
    // «deviceId» (peripheral.print, peripheral.scan, bluetooth.device.pair),
    // «sha256»/«hash» (expectedSha256 of filesystem.copy and filesystem.move)
    // and «recordId».
    // Bounded too: past four levels nothing is kept, and a list keeps its first twenty items (fifty processes); each
    // cut sets «cut». A list cut under a name says how many items it shows («<name>Shown»: a count or a next offset
    // of the provider speaks of all of them) and, when the observation carries no count of its own, how many it had
    // («<name>Count»).
    private static JsonNode? Sanitize(
        JsonElement element, ref bool cut, int depth = 0, bool processInventory = false, bool ocrObservation = false,
        bool captureObservation = false)
    {
        if (!ocrObservation && depth > 4)
        {
            cut |= element.ValueKind != JsonValueKind.Null;
            return null;
        }

        switch (element.ValueKind)
        {
            case JsonValueKind.Object:
                var clean = new JsonObject();
                foreach (JsonProperty property in element.EnumerateObject())
                {
                    string key = property.Name;
                    if ((key is "hwnd" or "handle" or "pid" or "processId" or "fingerprint"
                        or "invocationId" or "requestId" or "missionId" or "token")
                        && !(processInventory && key == "processId")
                        && !(ocrObservation && key is "pid" or "processId" or "hwnd" or "handle")
                        && !(captureObservation && key == "processId"))
                    {
                        continue;
                    }

                    JsonNode? sanitized = Sanitize(property.Value, ref cut, depth + 1, processInventory, ocrObservation, captureObservation);
                    if (sanitized is not null)
                    {
                        clean[key] = sanitized;
                    }

                    if (property.Value.ValueKind == JsonValueKind.Array
                        && sanitized is JsonArray kept
                        && property.Value.GetArrayLength() > kept.Count)
                    {
                        clean[key + "Shown"] = kept.Count;
                        if (!element.TryGetProperty("count", out _) && !element.TryGetProperty("totalCount", out _)
                            && !element.TryGetProperty(key + "Count", out _))
                        {
                            clean[key + "Count"] = property.Value.GetArrayLength();
                        }
                    }
                }

                return clean;
            case JsonValueKind.Array:
                var cleanArray = new JsonArray();
                int shown = ocrObservation ? int.MaxValue : processInventory ? 50 : 20;
                foreach (JsonElement item in element.EnumerateArray().Take(shown))
                {
                    cleanArray.Add(Sanitize(item, ref cut, depth + 1, processInventory, ocrObservation, captureObservation));
                }

                cut |= element.GetArrayLength() > shown;
                return cleanArray;
            case JsonValueKind.Null:
                return null;
            default:
                return JsonValue.Create(element);
        }
    }
}
