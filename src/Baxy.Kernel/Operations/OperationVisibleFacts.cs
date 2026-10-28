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

    // Al máximo 8.2 (Tool Receipts, arXiv 2603.10060): how a completed call was verified, one typed fact the mind
    // translates (mind.py, _outcome), from what the receipts already write at the top of their result. The table, by
    // what the receipt says, first match:
    //   changed:false                  → unchanged       the state asked was already the current one: ExternalCapability
    //                                                     handlers' StateAlreadyReached (Spotify alreadyPlaying, winget
    //                                                     alreadyInstalled, a field alreadyFocused, radios, Bluetooth,
    //                                                     display, brightness, a bin already empty…), windows already as
    //                                                     asked, an app.close with nothing to close, note, task, clipboard
    //                                                     (the same text), known files, memory configuration and mutation
    //   alreadyGone:true               → unchanged       app.close: the window was gone before BAXY touched it
    //   applied:false, reconciled:false→ unchanged       audio: already at the level or state asked, nothing set
    //   effectReadBack:false           → delivered_only  sent and its effect never read: a console command that exited,
    //                                                     app.open's place, a power transition, a media command, a link
    //                                                     to a page the browser already showed (alreadyShown)
    //   delivered, readBack not true   → delivered_only  keys and text Windows accepted, a queued key, a paste whose
    //                                                     text could not be read where it went (readBack not_readable)
    //   an operation that requires no observed effect (catalog) → output_only   a read: its output is the result
    //   otherwise                      → readback        the effect was read back (the engine turns an unverified success
    //                                                     into a failure)
    // The App's own completed result it could not read (result_unreadable) says none. A call that did not complete says
    // nothing of it: its status and error tell how it ended. observedLimit is not in the table: the receipt is read here
    // before the observation is cut, so a verified result that did not fit stays verified. Neither is a «verified» inside
    // a result (a backup's manifest, a restore): it is a fact of that item, not of how the call was verified; nor a
    // count of windows or processes already gone among others (window.close.all, process ends), which the others' ends
    // read back.
    public const string VerificationKey = "verification";
    public const string VerificationReadback = "readback";
    public const string VerificationDeliveredOnly = "delivered_only";
    public const string VerificationUnchanged = "unchanged";
    public const string VerificationOutputOnly = "output_only";
    public const string VerificationNone = "none";

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
        "state", "status", "mode", "kind", "operation", "unit",
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
        // Ronda final 12 (regla 3): only an operation whose typed schema takes an offset pages its list (window.resolve,
        // note.list); note.search, with a nextOffset null and no offset to take, is never given a next page.
        bool paged = ProductCatalog.TryGet(operation, out ProductOperationDescriptor? descriptor)
            && descriptor.ArgumentsSchema.Properties.Any(static property => property.Name == "offset");
        // SHELL2075 «ejecutá dir en el escritorio»: the console adapter already
        // bounds what it returns (8 KiB of output), and with the rest of the
        // result beside it that bundle crosses 8 KiB, so the observation was
        // dropped whole and the final could say nothing of what came out.
        bool consoleOutput = operation == "shell.command.run";
        // Rondas finales 43-44 (regla 3 and the model's context): the clipboard's, the page's and the email's text are
        // bounded by their own operations at 6,000 characters, so they fit this 8 KiB budget whole unless their escapes
        // take them past it (then the projection's steps cut them, with truncated); 40,000 let through beside the tool
        // prefix and the history could overflow the model's 49,152 tokens.
        int messageLimit = processInventory || ocrObservation || consoleOutput
            ? ProtocolLimits.MaximumOperationResponseMessageChars
            : MaximumMessageChars;

        // One header: the status says how the call ended (a completed call is a verified one: the engine turns an
        // unverified success into a failure); the operation is the one the model just called. Revisión 2026-10-22
        // (C-2): a retryable outcome is pending, as the engine's response says it.
        var payload = new JsonObject
        {
            ["status"] = success ? OperationStatuses.Completed
                : outcome.Retryable ? OperationStatuses.Pending
                : OperationStatuses.Failed,
        };
        if (success)
        {
            // A sealed private result is read by the App, which says its own (MemoryOperationResponseProjection).
            payload[VerificationKey] = Verification(operation, outcome.ProtectedPrivateResult ? null : outcome.Result);
        }

        if (!string.IsNullOrWhiteSpace(outcome.ErrorCode))
        {
            payload["error"] = outcome.ErrorCode;
        }

        if (!string.IsNullOrWhiteSpace(outcome.CauseCode))
        {
            payload["cause"] = outcome.CauseCode;
        }

        if (outcome.EffectMayHaveOccurred)
        {
            payload["effectUncertain"] = true;
        }

        if (outcome.ArgumentProblems.Count > 0)
        {
            payload["argumentProblems"] = ArgumentProblemsJson(outcome.ArgumentProblems);
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
                captureObservation: captureObservation, paged: paged);
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
            json = WithProjectedObservation(payload, sanitized, messageLimit, paged);
        }
        // Ronda final 45 (the model's context): past the 8 KiB budget an OCR's word boxes go first, said as layout
        // available false; with them, ~150 words on screen no longer fit beside the 42k-token tool prefix.
        if (ocrObservation && json.Length > MaximumMessageChars
            && payload["observed"] is JsonObject observed && observed.ContainsKey("layout"))
        {
            observed["layout"] = OcrSizeLimit();
            json = payload.ToJsonString(JsonOptions);
        }
        if (ocrObservation && json.Length > messageLimit)
        {
            payload["observed"] = OcrSizeLimit();
            json = payload.ToJsonString(JsonOptions);
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

        return json;
    }

    /// <summary>How a completed <paramref name="operation"/> was verified, by the table above, from its result.</summary>
    public static string Verification(string operation, JsonElement? result)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(operation);
        if (result is { ValueKind: JsonValueKind.Object } receipt)
        {
            if (Is(receipt, "changed", JsonValueKind.False) || Is(receipt, "alreadyGone", JsonValueKind.True)
                || (Is(receipt, "applied", JsonValueKind.False) && Is(receipt, "reconciled", JsonValueKind.False)))
            {
                return VerificationUnchanged;
            }

            if (Is(receipt, "effectReadBack", JsonValueKind.False)
                || (receipt.TryGetProperty("delivered", out _) && !Is(receipt, "readBack", JsonValueKind.True)))
            {
                return VerificationDeliveredOnly;
            }
        }

        return ProductCatalog.TryGet(operation, out ProductOperationDescriptor? descriptor)
            && !descriptor.RequiresObservedEffect
                ? VerificationOutputOnly
                : VerificationReadback;
    }

    private static bool Is(JsonElement receipt, string name, JsonValueKind kind) =>
        receipt.TryGetProperty(name, out JsonElement value) && value.ValueKind == kind;

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
        var payload = new JsonObject
        {
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

    /// <summary>
    /// The arguments a call got wrong as the model reads them: one object per argument, name and problem, and the
    /// fields that correct it when known (<c>nearest</c>, <c>allowed</c>, <c>accepted</c>, <c>oneOf</c>).
    /// </summary>
    public static JsonArray ArgumentProblemsJson(IReadOnlyList<ArgumentProblem> problems) =>
        new([.. problems.Select(static problem =>
        {
            var item = new JsonObject
            {
                ["argument"] = problem.Name,
                ["problem"] = problem.Problem,
            };
            if (problem.Nearest is { } nearest)
            {
                item["nearest"] = nearest;
            }

            if (problem.Allowed is { } allowed)
            {
                item["allowed"] = new JsonArray([.. allowed.Select(static value => (JsonNode?)value)]);
            }

            if (problem.Accepted is { } accepted)
            {
                item["accepted"] = new JsonArray([.. accepted.Select(static name => (JsonNode?)name)]);
            }

            if (problem.OneOf is { } oneOf)
            {
                item["oneOf"] = new JsonArray([.. oneOf.Select(static name => (JsonNode?)name)]);
            }

            return (JsonNode?)item;
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
    private static string WithProjectedObservation(JsonObject payload, JsonNode observed, int limit, bool paged)
    {
        payload[ObservedLimitKey] = ObservedProjected;
        // A page of a text read by offset (file.read, web.fetch) keeps as much of its text as the message holds, not
        // the first step's 2,000 characters (practice p11: six pages of 2,000 where 7,000 fit), and goes on from there.
        if (observed is JsonObject page && page["text"] is JsonValue pageText && pageText.TryGetValue(out string? _)
            && page["offset"] is JsonValue)
        {
            JsonObject probe = page.DeepClone().AsObject();
            probe["text"] = string.Empty;
            payload["observed"] = probe;
            // At most the page's own length minus one, so the first try always cuts (a page that fits unescaped but
            // not escaped would otherwise fall to the 2,000 step; round 3).
            int room = Math.Min(limit - payload.ToJsonString(JsonOptions).Length - 64,
                pageText.GetValue<string>().Length - 1);
            // The room counts the text's characters, not its escaped JSON (each line break or quote takes two): a try
            // that does not fit shrinks by what it went over and tries again (round 2: p11's pages went over by 140-260).
            for (int attempt = 0; attempt < 3 && room > ObservedProjectionSteps[0].Text; attempt++)
            {
                bool cut = false;
                JsonNode projected = Project(observed, null, room, int.MaxValue, paged, ref cut);
                if (!cut || projected is not JsonObject root)
                {
                    break;
                }

                root["truncated"] = true;
                payload["observed"] = projected;
                string json = payload.ToJsonString(JsonOptions);
                if (json.Length <= limit)
                {
                    return json;
                }

                room -= json.Length - limit + 16;
            }
        }

        foreach ((int text, int items) in ObservedProjectionSteps)
        {
            bool cut = false;
            JsonNode projected = Project(observed, null, text, items, paged, ref cut);
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

    // A page by offset (window.resolve, note.list) whose list was cut to «shown» goes on from the first item not shown,
    // never from the provider's next page: the model never skips items it did not see, and «no more» is never said of
    // a page it saw only part of.
    /// <summary>
    /// Rondas finales 42-43 (regla 3): a provider's own facts about its list spoke of it before this cut; they now say what
    /// the model sees: its «shownCount» is the items shown, «hasMore» is true, and a truncation flag it set to false
    /// («resultsMayBeTruncated», «truncated», any «…Truncated») is true.
    /// </summary>
    private static void CorrectCutListFacts(JsonObject facts, int shown)
    {
        if (facts.ContainsKey("shownCount"))
        {
            facts["shownCount"] = shown;
        }

        if (facts.ContainsKey("hasMore"))
        {
            facts["hasMore"] = true;
        }

        MarkTruncated(facts);
        // A sibling object describing the same search («searchScope») carries its own flag.
        foreach (JsonNode? child in facts.Select(static pair => pair.Value).ToArray())
        {
            if (child is JsonObject scope)
            {
                MarkTruncated(scope);
            }
        }
    }

    private static void MarkTruncated(JsonObject facts)
    {
        foreach (string key in facts.Select(static pair => pair.Key).ToArray())
        {
            if ((key is "resultsMayBeTruncated" or "truncated" || key.EndsWith("Truncated", StringComparison.Ordinal))
                && facts[key] is JsonValue flag && flag.TryGetValue(out bool value) && !value)
            {
                facts[key] = true;
            }
        }
    }

    private static void PageFrom(JsonNode? offset, bool paged, int shown, JsonObject target)
    {
        if (!paged)
            return;
        int start = offset is JsonValue value && value.TryGetValue(out int read) ? read : 0;
        target["nextOffset"] = start + shown;
        target["hasMore"] = true;
    }

    private static JsonNode Project(JsonNode node, string? key, int text, int items, bool paged, ref bool cut)
    {
        switch (node)
        {
            case JsonObject obj:
                var projected = new JsonObject();
                int? listShown = null;
                foreach ((string name, JsonNode? value) in obj)
                {
                    projected[name] = value is null ? null : Project(value, name, text, items, paged, ref cut);
                    if (value is JsonArray list && list.Count > items
                        && !obj.ContainsKey("count") && !obj.ContainsKey("totalCount")
                        && !obj.ContainsKey(name + "Count"))
                    {
                        projected[name + "Count"] = list.Count;
                    }

                    // Ronda final 10 (regla 3): a list cut here says how many it shows now (an earlier «Shown» counted
                    // the provider's page).
                    if (value is JsonArray cutList && cutList.Count > items)
                    {
                        listShown = items;
                    }
                }

                // Ronda final 11 (regla 3): after every key is copied (the provider's nextOffset and hasMore come after
                // the list), a cut list's Shown and a page by offset's next offset are the shown ones.
                if (listShown is int shownItems)
                {
                    foreach ((string name, JsonNode? value) in obj)
                    {
                        if (value is JsonArray list && list.Count > items)
                            projected[name + "Shown"] = shownItems;
                    }

                    PageFrom(obj["offset"], paged && obj.ContainsKey("nextOffset"), shownItems, projected);
                    CorrectCutListFacts(projected, shownItems);
                }

                // A page of a text read by offset (file.read, web.fetch) whose text was cut here goes on from where
                // its shown text ends, not from where the provider's page ended: the model never skips text it did
                // not see (audit 2026-10-15, R2). Revisión de calidad del núcleo (final2): a text one character over the
                // bound with no space near it is as long cut as whole (its last character gave way to «…»), so it is
                // told cut by what it shows, not by its length.
                if (obj["text"] is JsonValue whole && whole.TryGetValue(out string? read)
                    && projected["text"] is JsonValue part && part.TryGetValue(out string? shown)
                    && !string.Equals(shown, read, StringComparison.Ordinal)
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
                    // Holdout v4 (falsedad, a partial read told as a whole one): the page shown ends before the
                    // provider's did, so it ends on the line its shown text reaches, never the file's end.
                    if (obj["fromLine"] is JsonValue from && from.TryGetValue(out int fromLine)
                        && obj.ContainsKey("toLine"))
                    {
                        projected["toLine"] = fromLine + Math.Max(0, LineCount(shown[..shownCharacters]) - 1);
                    }

                    if (obj.ContainsKey("endReached"))
                    {
                        projected["endReached"] = false;
                    }

                    projected["readInPart"] = true;
                }

                return projected;
            case JsonArray array:
                var kept = new JsonArray();
                foreach (JsonNode? item in array.Take(items))
                {
                    kept.Add(item is null ? null : Project(item, key, text, items, paged, ref cut));
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

    // The lines of a text as the file reader counts them (WindowsKnownFileAdapter.LineCount): each break ends one, and a
    // last line without a break counts too.
    private static int LineCount(string text)
    {
        int lines = 0;
        for (int index = 0; index < text.Length; index++)
        {
            if (text[index] == '\n' || (text[index] == '\r' && (index + 1 == text.Length || text[index + 1] != '\n')))
                lines++;
        }

        return text.Length > 0 && text[^1] is not ('\n' or '\r') ? lines + 1 : lines;
    }

    // Held back from the model is only what is a secret or the kernel's own
    // bookkeeping: the confirmation «token», the request «fingerprint», the
    // invocation, request and mission ids, and window and process handles
    // («hwnd», «handle», «windowHandle», «pid», «processId») of a provider's receipt: the window number an operation
    // takes is the one a look shows («window <hwnd>», ScreenViewProjection) or app.open's «window» (NB-R1 P1.12), and
    // app.open's windowId for the window operations, not these
    // (revisión 2026-10-22, C-7: app.open's and a capture's windowHandle reopened e2e p3 E007).
    // An id a typed argument asks for travels: «id», «noteId» (note.update),
    // «deviceId» (peripheral.print, peripheral.scan, bluetooth.device.pair),
    // «sha256»/«hash» (expectedSha256 of filesystem.copy and filesystem.move)
    // and «recordId».
    // Bounded too: past four levels nothing is kept, and a list keeps its first twenty items (fifty processes); each
    // cut sets «cut». A list cut under a name says how many items it shows («<name>Shown»: a count or a next offset
    // of the provider speaks of all of them) and, when the observation carries no count of its own, how many it had
    // («<name>Count»).
    // Bookkeeping of a provider's receipt that no operation takes and the model never needs to tell (round 1, results
    // agent: endpoint hashes, the adapter's cascade stage, SendInput counters, Win32 error numbers, the evidence's
    // authority): the receipt keeps them for the journal; the model reads what happened.
    private static readonly HashSet<string> OpaqueKeys = new(StringComparer.Ordinal)
    {
        "endpointIdHash", "cascadeStage", "waitedMs", "acceptedEvents", "expectedEvents", "inputSize",
        "lastWin32Error", "foregroundProcessIdBefore", "foregroundProcessIdAfter", "sequenceNumber", "executablePath",
        "authority", "taskName",
    };

    private static JsonNode? Sanitize(
        JsonElement element, ref bool cut, int depth = 0, bool processInventory = false, bool ocrObservation = false,
        bool captureObservation = false, bool paged = false)
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
                int? cleanShown = null;
                foreach (JsonProperty property in element.EnumerateObject())
                {
                    string key = property.Name;
                    if (OpaqueKeys.Contains(key) && depth == 0)
                    {
                        continue;
                    }

                    if ((key is "hwnd" or "handle" or "windowHandle" or "pid" or "processId" or "fingerprint"
                        or "invocationId" or "requestId" or "missionId" or "token")
                        && !(processInventory && key == "processId")
                        && !(ocrObservation && key is "pid" or "processId" or "hwnd" or "handle")
                        && !(captureObservation && key == "processId"))
                    {
                        continue;
                    }

                    JsonNode? sanitized = Sanitize(property.Value, ref cut, depth + 1, processInventory, ocrObservation, captureObservation, paged);
                    // Ronda final 12 (regla 3): a last page's «nextOffset: null» is kept, so a later cut of its list
                    // still knows it is a page by offset and says where to go on.
                    if (sanitized is not null || key == "nextOffset")
                    {
                        clean[key] = sanitized;
                    }

                    if (property.Value.ValueKind == JsonValueKind.Array
                        && sanitized is JsonArray kept
                        && property.Value.GetArrayLength() > kept.Count)
                    {
                        clean[key + "Shown"] = kept.Count;
                        cleanShown = kept.Count;
                        if (!element.TryGetProperty("count", out _) && !element.TryGetProperty("totalCount", out _)
                            && !element.TryGetProperty(key + "Count", out _))
                        {
                            clean[key + "Count"] = property.Value.GetArrayLength();
                        }
                    }
                }

                // Ronda final 11 (regla 3): a page by offset whose list was cut goes on from the first item not shown.
                if (cleanShown is int keptItems)
                {
                    PageFrom(clean["offset"], paged && element.TryGetProperty("nextOffset", out _), keptItems, clean);
                    CorrectCutListFacts(clean, keptItems);
                }

                return clean;
            case JsonValueKind.Array:
                var cleanArray = new JsonArray();
                int shown = ocrObservation ? int.MaxValue : processInventory ? 50 : 20;
                foreach (JsonElement item in element.EnumerateArray().Take(shown))
                {
                    cleanArray.Add(Sanitize(item, ref cut, depth + 1, processInventory, ocrObservation, captureObservation, paged));
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
