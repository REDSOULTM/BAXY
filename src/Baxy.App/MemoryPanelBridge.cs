using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Security.Windows;

namespace Baxy.App;

/// <summary>
/// GET/POST/DELETE del panel de memoria contra el mismo almacén que el chat.
/// El confirm del panel es la confirmación de esa invocación: si Core pide
/// token, se reenvía el de esa petición y no se abre un segundo diálogo.
/// </summary>
internal sealed class MemoryPanelBridge
{
    private static readonly TimeSpan OperationTimeout = TimeSpan.FromSeconds(20);
    private readonly Func<CoreProcessClient?> _client;
    private readonly Func<MemoryOperationProtector?> _protector;

    internal MemoryPanelBridge(
        Func<CoreProcessClient?> client,
        Func<MemoryOperationProtector?> protector)
    {
        _client = client ?? throw new ArgumentNullException(nameof(client));
        _protector = protector ?? throw new ArgumentNullException(nameof(protector));
    }

    internal async Task<FieldHttpResponse> HandleAsync(
        string method,
        string route,
        string? body,
        CancellationToken cancellationToken)
    {
        CoreProcessClient? client = _client();
        MemoryOperationProtector? protector = _protector();
        if (client is not { IsReady: true } || protector is null)
        {
            return FieldHttpResponse.Json(
                new JsonObject { ["error"] = "agent_not_ready", ["items"] = new JsonArray() },
                409);
        }

        if (method == "GET" && route == "/memory")
        {
            return await ListAsync(client, protector, cancellationToken).ConfigureAwait(true);
        }

        if (method == "POST" && route == "/memory")
        {
            return await SaveOrCorrectAsync(client, protector, body, cancellationToken)
                .ConfigureAwait(true);
        }

        if (method == "DELETE" && route.StartsWith("/memory/", StringComparison.Ordinal))
        {
            string key = Uri.UnescapeDataString(route["/memory/".Length..]);
            return await ForgetAsync(client, protector, key, cancellationToken)
                .ConfigureAwait(true);
        }

        return FieldHttpResponse.Json(
            new JsonObject { ["error"] = "memory_route_not_found" },
            404);
    }

    private static async Task<FieldHttpResponse> ListAsync(
        CoreProcessClient client,
        MemoryOperationProtector protector,
        CancellationToken cancellationToken)
    {
        JsonElement payload = await ExecuteAsync(
                client,
                protector,
                new MemoryRoutedOperation(
                    "memory.list",
                    new JsonObject
                    {
                        ["version"] = 1,
                        ["limit"] = 100,
                        ["offset"] = 0,
                    }),
                cancellationToken)
            .ConfigureAwait(true);
        var items = new JsonArray();
        if (payload.TryGetProperty("records", out JsonElement records)
            && records.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement record in records.EnumerateArray())
            {
                string key = record.TryGetProperty("selector", out JsonElement selector)
                    ? selector.GetString() ?? string.Empty
                    : string.Empty;
                if (key.Length == 0)
                {
                    continue;
                }

                string value = record.TryGetProperty("value", out JsonElement valueElement)
                    ? valueElement.ValueKind == JsonValueKind.String
                        ? valueElement.GetString() ?? string.Empty
                        : valueElement.GetRawText()
                    : string.Empty;
                string updated = record.TryGetProperty("updatedAtUtc", out JsonElement updatedAt)
                    ? updatedAt.GetString() ?? string.Empty
                    : string.Empty;
                items.Add(new JsonObject
                {
                    ["key"] = key,
                    ["value"] = value,
                    ["updated_at"] = updated,
                });
            }
        }

        return FieldHttpResponse.Json(new JsonObject { ["items"] = items });
    }

    private static async Task<FieldHttpResponse> SaveOrCorrectAsync(
        CoreProcessClient client,
        MemoryOperationProtector protector,
        string? body,
        CancellationToken cancellationToken)
    {
        JsonObject? node = string.IsNullOrWhiteSpace(body)
            ? null
            : JsonNode.Parse(body) as JsonObject;
        string key = ((string?)node?["key"] ?? string.Empty).Trim();
        string value = (string?)node?["value"] ?? string.Empty;
        if (key.Length == 0)
        {
            return FieldHttpResponse.Json(
                new JsonObject { ["error"] = "invalid_text" },
                400);
        }

        await EnsureEnabledAsync(client, protector, cancellationToken).ConfigureAwait(true);
        JsonElement listed = await ExecuteAsync(
                client,
                protector,
                new MemoryRoutedOperation(
                    "memory.list",
                    new JsonObject
                    {
                        ["version"] = 1,
                        ["limit"] = 100,
                        ["offset"] = 0,
                    }),
                cancellationToken)
            .ConfigureAwait(true);
        bool exists = false;
        if (listed.TryGetProperty("records", out JsonElement records)
            && records.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement record in records.EnumerateArray())
            {
                string selector = record.TryGetProperty("selector", out JsonElement current)
                    ? current.GetString() ?? string.Empty
                    : string.Empty;
                if (string.Equals(selector, key, StringComparison.OrdinalIgnoreCase))
                {
                    exists = true;
                    key = selector;
                    break;
                }
            }
        }

        MemoryRoutedOperation operation = exists
            ? new MemoryRoutedOperation(
                "memory.correct",
                new JsonObject
                {
                    ["version"] = 1,
                    ["selector"] = key,
                    ["value"] = value,
                    ["retention"] = "persistent",
                })
            : new MemoryRoutedOperation(
                "memory.save",
                new JsonObject
                {
                    ["version"] = 1,
                    ["selector"] = key,
                    ["value"] = value,
                    ["kind"] = "preference",
                    ["retention"] = "persistent",
                    ["sensitivity"] = "normal",
                    ["tags"] = new JsonArray(),
                });
        _ = await ExecuteAsync(client, protector, operation, cancellationToken)
            .ConfigureAwait(true);
        return await ListAsync(client, protector, cancellationToken).ConfigureAwait(true);
    }

    private static async Task<FieldHttpResponse> ForgetAsync(
        CoreProcessClient client,
        MemoryOperationProtector protector,
        string key,
        CancellationToken cancellationToken)
    {
        MemoryRoutedOperation operation = key is "*" or ""
            ? new MemoryRoutedOperation(
                "memory.forget",
                new JsonObject
                {
                    ["version"] = 1,
                    ["scope"] = "all",
                    ["selector"] = null,
                    ["confirmationRequired"] = true,
                })
            : new MemoryRoutedOperation(
                "memory.forget",
                new JsonObject
                {
                    ["version"] = 1,
                    ["scope"] = "exact",
                    ["selector"] = key,
                    ["confirmationRequired"] = true,
                });
        _ = await ExecuteAsync(client, protector, operation, cancellationToken)
            .ConfigureAwait(true);
        return await ListAsync(client, protector, cancellationToken).ConfigureAwait(true);
    }

    private static async Task EnsureEnabledAsync(
        CoreProcessClient client,
        MemoryOperationProtector protector,
        CancellationToken cancellationToken)
    {
        JsonElement status = await ExecuteAsync(
                client,
                protector,
                new MemoryRoutedOperation(
                    "memory.status",
                    new JsonObject { ["version"] = 1 }),
                cancellationToken)
            .ConfigureAwait(true);
        if (status.TryGetProperty("enabled", out JsonElement enabled)
            && enabled.ValueKind == JsonValueKind.True)
        {
            return;
        }

        _ = await ExecuteAsync(
                client,
                protector,
                new MemoryRoutedOperation(
                    "memory.configure",
                    new JsonObject { ["version"] = 1, ["enabled"] = true }),
                cancellationToken)
            .ConfigureAwait(true);
    }

    private static async Task<JsonElement> ExecuteAsync(
        CoreProcessClient client,
        MemoryOperationProtector protector,
        MemoryRoutedOperation operation,
        CancellationToken cancellationToken)
    {
        PreparedOperation prepared = protector.Prepare(operation).Prepared;
        OperationResponse response = await client.SendOperationAsync(
                prepared,
                OperationTimeout,
                cancellationToken)
            .ConfigureAwait(true);
        if (PendingMemoryConfirmation.TryCreate(
                response,
                prepared,
                TimeProvider.System,
                out PendingMemoryConfirmation? challenge)
            && challenge is not null)
        {
            response = await client.SendOperationAsync(
                    prepared,
                    OperationTimeout,
                    cancellationToken,
                    challenge.Token)
                .ConfigureAwait(true);
        }

        if (!string.Equals(response.Status, OperationStatuses.Completed, StringComparison.Ordinal)
            || !response.Verified)
        {
            throw new InvalidDataException(
                string.Create(
                    CultureInfo.InvariantCulture,
                    $"memory_panel_{operation.Name}_{response.ErrorCode ?? response.Status}"));
        }

        using OpenedBoundProtectedJson opened = protector.OpenResult(response, prepared);
        return opened.Payload.Clone();
    }
}
