using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Security.Windows;

namespace Baxy.App;

/// <summary>
/// Estabilización M (identity, «Memoria y privacidad»: it can be seen, edited and erased whole). The interface's memory
/// panel lists, edits and forgets through the same catalog operations the chat runs (<c>memory.list</c>,
/// <c>memory.recall</c>, <c>memory.correct</c>, <c>memory.forget</c>), sealed by the same
/// <see cref="MemoryOperationProtector"/> and sent to the same Core: the kernel authorizes each one and the journal
/// records it; there is no second way to the store. The person confirms a forget in the panel itself (its own two-step
/// button, never a browser dialog) and the panel answers the kernel's challenge with that request's token. Forgetting
/// everything has its own request (<c>DELETE /memory</c> with <c>{"scope":"all"}</c>); no entry's key means «all».
/// The channel reaches this only from the App's own document (<see cref="HistoricalFieldOriginPolicy"/>) or the
/// windowless conductor; web content cannot.
/// </summary>
internal sealed class MemoryPanel
{
    private const int PageSize = 100;
    private const int MaximumRecords = 512;
    private const string OutcomeUnknown = "memory_outcome_unknown";
    private static readonly TimeSpan OperationTimeout = TimeSpan.FromSeconds(20);

    private readonly Func<CoreProcessClient?> _client;
    private readonly Func<MemoryOperationProtector?> _protector;

    internal MemoryPanel(Func<CoreProcessClient?> client, Func<MemoryOperationProtector?> protector)
    {
        _client = client ?? throw new ArgumentNullException(nameof(client));
        _protector = protector ?? throw new ArgumentNullException(nameof(protector));
    }

    /// <summary>The number of entries the store held when it was last read (0 before the first read).</summary>
    internal int Count { get; private set; }

    internal async Task<FieldHttpResponse> HandleAsync(
        string method,
        string route,
        string? body,
        CancellationToken cancellationToken)
    {
        if (_client() is not { IsReady: true } client || _protector() is not { } protector)
        {
            return FieldHttpResponse.Json(
                new JsonObject { ["error"] = "agent_not_ready", ["items"] = new JsonArray() }, 409);
        }

        string? failed = null;
        if (method == "POST" && route == "/memory")
        {
            JsonObject? edit = Parse(body);
            string key = ((string?)edit?["key"] ?? string.Empty).Trim();
            string value = ((string?)edit?["value"] ?? string.Empty).Trim();
            if (key.Length == 0 || value.Length == 0)
            {
                return Failure("invalid_text", 400);
            }

            failed = await EditAsync(client, protector, key, value, cancellationToken);
        }
        else if (method == "DELETE" && route == "/memory")
        {
            // Revisión M H7: everything is forgotten only by its own request, never by an empty or starred key.
            if ((string?)Parse(body)?["scope"] != "all")
            {
                return Failure("invalid_scope", 400);
            }

            failed = (await ExecuteAsync(client, protector, "memory.forget", new JsonObject
            {
                ["version"] = 1,
                ["scope"] = "all",
                ["selector"] = null,
                ["confirmationRequired"] = true,
            }, cancellationToken)).Error;
        }
        else if (method == "DELETE" && route.StartsWith("/memory/", StringComparison.Ordinal))
        {
            string key = Uri.UnescapeDataString(route["/memory/".Length..]).Trim();
            if (key.Length == 0 || key == "*")
            {
                return Failure("invalid_key", 400);
            }

            failed = (await ExecuteAsync(client, protector, "memory.forget", new JsonObject
            {
                ["version"] = 1,
                ["scope"] = "exact",
                ["selector"] = key,
                ["confirmationRequired"] = true,
            }, cancellationToken)).Error;
        }
        else if (method != "GET" || route != "/memory")
        {
            return Failure("memory_route_not_found", 404);
        }

        if (failed is not null and not OutcomeUnknown)
        {
            return Failure(failed, failed == "memory_not_found" ? 404 : 409);
        }

        // Revisión M H8: a change whose outcome is unknown (the time ran out, the engine went away) is never told as
        // failed: the store is read again and the panel shows what it holds, marked unconfirmed.
        (JsonObject? listed, string? error) = await ListAsync(client, protector, PageSize, cancellationToken);
        if (listed is null)
        {
            return Failure(failed ?? error ?? "memory_unavailable", failed is null ? 409 : 503);
        }

        if (failed is not null)
        {
            listed["unconfirmed"] = true;
        }

        return FieldHttpResponse.Json(listed);
    }

    /// <summary>Reads the count again from the store (after the chat changed it); false when it could not be read.</summary>
    internal async Task<bool> RefreshCountAsync(CancellationToken cancellationToken)
    {
        if (_client() is not { IsReady: true } client || _protector() is not { } protector)
        {
            return false;
        }

        return (await ListAsync(client, protector, 1, cancellationToken)).Listed is not null;
    }

    /// <summary>
    /// Estabilización M3: the keys the store holds now (every entry's selector); null when the memory is off or cannot be
    /// read, so the request goes on as asked.
    /// </summary>
    internal async Task<IReadOnlyList<string>?> KeysAsync(CancellationToken cancellationToken)
    {
        if (_client() is not { IsReady: true } client || _protector() is not { } protector)
        {
            return null;
        }

        (JsonObject? listed, _) = await ListAsync(client, protector, PageSize, cancellationToken);
        return listed is not null && listed["enabled"] is JsonValue enabled && enabled.GetValue<bool>()
            && listed["items"] is JsonArray items
                ? items.Select(static item => (string?)item?["key"] ?? string.Empty).Where(static key => key.Length > 0)
                    .ToArray()
                : null;
    }

    /// <summary>
    /// Estabilización M3 (live 2026-10-12: «Olvidá mi color favorito de prueba» was asked «¿Qué alcance deseas
    /// eliminar…?»): the kept keys a datum named in the person's words stands for. The key itself, or one whose words (its
    /// selector's or its name's, <see cref="Label(string, bool)"/>) are exactly the asked ones, is the only one; else every
    /// key that carries all the asked words («mi color de prueba» → «color favorito de prueba»), never one that carries
    /// fewer («color favorito» is not «color favorito de prueba»). Empty when none does.
    /// </summary>
    internal static IReadOnlyList<string> Candidates(string asked, IReadOnlyList<string> stored)
    {
        ArgumentNullException.ThrowIfNull(asked);
        ArgumentNullException.ThrowIfNull(stored);
        HashSet<string>[] askedNames = Names(asked);
        if (askedNames[0].Count == 0)
        {
            return [];
        }

        string[] exact = stored
            .Where(key => string.Equals(key, asked, StringComparison.OrdinalIgnoreCase)
                || Names(key).Any(name => askedNames.Any(name.SetEquals)))
            .ToArray();
        return exact.Length > 0
            ? exact[..1]
            : stored.Where(key => Names(key).Any(name => askedNames.Any(name.IsSupersetOf))).ToArray();
    }

    private static HashSet<string>[] Names(string key) =>
        [Words(key), Words(Label(key, english: false)), Words(Label(key, english: true))];

    private static HashSet<string> Words(string text) =>
        new(
            Fold(text).Split(['_', ' ', '-', '\''], StringSplitOptions.RemoveEmptyEntries),
            StringComparer.Ordinal);

    private static string Fold(string text)
    {
        var builder = new System.Text.StringBuilder(text.Length);
        foreach (char character in text.Normalize(System.Text.NormalizationForm.FormD).ToLowerInvariant())
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) != UnicodeCategory.NonSpacingMark)
            {
                builder.Append(character);
            }
        }

        return builder.ToString();
    }

    private async Task<(JsonObject? Listed, string? Error)> ListAsync(
        CoreProcessClient client,
        MemoryOperationProtector protector,
        int pageSize,
        CancellationToken cancellationToken)
    {
        var items = new JsonArray();
        int total = 0;
        for (int offset = 0; offset < MaximumRecords; offset += pageSize)
        {
            (JsonElement page, string? error) = await ExecuteAsync(client, protector, "memory.list", new JsonObject
            {
                ["version"] = 1,
                ["limit"] = pageSize,
                ["offset"] = offset,
            }, cancellationToken);
            if (error == "memory_disabled")
            {
                // Off by default for privacy: an empty memory, never an error, and viewing it never switches it on.
                Count = 0;
                return (new JsonObject { ["enabled"] = false, ["total"] = 0, ["items"] = items }, null);
            }

            if (error is not null)
            {
                return (null, error);
            }

            total = page.GetProperty("totalCount").GetInt32();
            if (pageSize != PageSize)
            {
                break;
            }

            foreach (JsonElement record in page.GetProperty("records").EnumerateArray())
            {
                string selector = record.GetProperty("selector").GetString() ?? string.Empty;
                items.Add(new JsonObject
                {
                    ["key"] = selector,
                    ["label"] = Label(selector),
                    ["value"] = record.GetProperty("value").GetString(),
                    ["updated_at"] = record.GetProperty("updatedAtUtc").GetDateTimeOffset()
                        .ToLocalTime().ToString("yyyy-MM-dd HH:mm", CultureInfo.InvariantCulture),
                });
            }

            if (offset + pageSize >= total)
            {
                break;
            }
        }

        Count = total;
        // The store holds at most 512 entries, all listed; «total» lets the view say so if that ever differs.
        return (new JsonObject { ["enabled"] = true, ["total"] = total, ["items"] = items }, null);
    }

    // Estabilización M2 (identity live check 2026-10-11 §5: the panel showed FAVORITE_COLOR, BIRTHDAY): the datum's name
    // in the person's words (data: memory_subjects.v1.json labels, one file with the mind); a fact kept whole is a
    // «dato»; any other selector is said with its own words.
    private static readonly Lazy<JsonObject> Subjects = new(() =>
    {
        using Stream stream = typeof(MemoryPanel).Assembly.GetManifestResourceStream("Baxy.App.MemorySubjects.json")
            ?? throw new InvalidOperationException("The memory subjects are not embedded.");
        return JsonNode.Parse(stream) as JsonObject
            ?? throw new InvalidDataException("The memory subjects are not an object.");
    });

    internal static string Label(string selector) => Label(selector, english: false);

    internal static string Label(string selector, bool english)
    {
        string folded = selector.Trim().ToLowerInvariant();
        string language = english ? "en" : "es";
        if (Subjects.Value["labels"]?[folded]?[language] is JsonValue known)
        {
            return known.GetValue<string>();
        }

        return folded.StartsWith("historical_fact_", StringComparison.Ordinal)
            ? (string)Subjects.Value["factLabel"]![language]!
            : folded.Replace('_', ' ');
    }

    private static async Task<string?> EditAsync(
        CoreProcessClient client,
        MemoryOperationProtector protector,
        string key,
        string value,
        CancellationToken cancellationToken)
    {
        // A value that carries a secret is never kept from the panel either (privacy masking).
        if (string.IsNullOrWhiteSpace(value) || SensitiveText.Contains(value))
        {
            return "memory_value_refused";
        }

        // The record is named by what the store holds (its selector and retention), never guessed by the panel.
        (JsonElement found, string? error) = await ExecuteAsync(client, protector, "memory.recall", new JsonObject
        {
            ["version"] = 1,
            ["scope"] = "exact",
            ["selector"] = key,
        }, cancellationToken);
        if (error is not null)
        {
            return error;
        }

        string? retention = null;
        foreach (JsonElement candidate in found.GetProperty("records").EnumerateArray())
        {
            if (string.Equals(candidate.GetProperty("selector").GetString(), key, StringComparison.Ordinal))
            {
                retention = candidate.GetProperty("retention").GetString();
                break;
            }
        }

        if (retention is null)
        {
            return "memory_not_found";
        }

        return (await ExecuteAsync(client, protector, "memory.correct", new JsonObject
        {
            ["version"] = 1,
            ["selector"] = key,
            ["value"] = value,
            ["retention"] = retention,
        }, cancellationToken)).Error;
    }

    private static async Task<(JsonElement Payload, string? Error)> ExecuteAsync(
        CoreProcessClient client,
        MemoryOperationProtector protector,
        string operation,
        JsonObject arguments,
        CancellationToken cancellationToken)
    {
        PreparedOperation prepared = protector.Prepare(new MemoryRoutedOperation(operation, arguments)).Prepared;
        OperationResponse response;
        try
        {
            response = await client.SendOperationAsync(prepared, OperationTimeout, cancellationToken);
            if (PendingMemoryConfirmation.TryCreate(response, prepared, TimeProvider.System, out PendingMemoryConfirmation? asked)
                && asked is not null)
            {
                response = await client.SendOperationAsync(
                    prepared, OperationTimeout, cancellationToken, asked.Token);
            }
        }
        catch (Exception exception) when (exception is TimeoutException or IOException or InvalidOperationException
            || exception is OperationCanceledException && !cancellationToken.IsCancellationRequested)
        {
            return (default, OutcomeUnknown);
        }

        if (!string.Equals(response.Status, OperationStatuses.Completed, StringComparison.Ordinal) || !response.Verified)
        {
            return (default, response.EffectMayHaveOccurred ? OutcomeUnknown : response.ErrorCode ?? response.Status);
        }

        using OpenedBoundProtectedJson opened = protector.OpenResult(response, prepared);
        return (opened.Payload.Clone(), null);
    }

    private static JsonObject? Parse(string? body)
    {
        try
        {
            return string.IsNullOrWhiteSpace(body) ? null : JsonNode.Parse(body) as JsonObject;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static FieldHttpResponse Failure(string code, int status) =>
        FieldHttpResponse.Json(new JsonObject { ["ok"] = false, ["error"] = code }, status);
}
