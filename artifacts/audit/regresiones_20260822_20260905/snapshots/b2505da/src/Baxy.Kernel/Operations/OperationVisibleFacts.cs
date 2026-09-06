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
    private const int MaximumObservedUtf8Bytes = 8_192;
    private const int MaximumMessageChars = 4_096;
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    public static string FromOutcome(string operation, OperationOutcome outcome)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(operation);
        ArgumentNullException.ThrowIfNull(outcome);
        bool success = outcome.Succeeded && outcome.Verified;
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

        if (!outcome.ProtectedPrivateResult
            && outcome.Result is { } result
            && result.ValueKind is JsonValueKind.Object or JsonValueKind.Array)
        {
            string raw = result.GetRawText();
            if (raw.Length <= MaximumObservedUtf8Bytes)
            {
                try
                {
                    payload["observed"] = Sanitize(JsonNode.Parse(raw));
                }
                catch (JsonException)
                {
                    // Observed payload stays omitted when it is not JSON.
                }
                catch (ArgumentException)
                {
                    // Duplicate keys or re-parented nodes stay omitted.
                }
            }
        }

        string json = payload.ToJsonString(JsonOptions);
        if (json.Length > MaximumMessageChars)
        {
            payload.Remove("observed");
            json = payload.ToJsonString(JsonOptions);
        }

        return json.Length <= MaximumMessageChars
            ? json
            : json[..MaximumMessageChars];
    }

    public static string FromStatus(string operation, string status, string? errorCode)
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

        return payload.ToJsonString(JsonOptions);
    }

    private static JsonNode? Sanitize(JsonNode? node, int depth = 0)
    {
        if (node is null || depth > 4)
        {
            return null;
        }

        if (node is JsonObject obj)
        {
            var clean = new JsonObject();
            foreach ((string key, JsonNode? value) in obj)
            {
                if (key is "id" or "noteId" or "hwnd" or "handle" or "fingerprint"
                    or "hash" or "sha256" or "pid" or "processId" or "invocationId"
                    or "requestId" or "missionId" or "token" or "recordId"
                    or "deviceId")
                {
                    continue;
                }

                JsonNode? sanitized = Sanitize(value, depth + 1);
                if (sanitized is not null && !clean.ContainsKey(key))
                {
                    clean[key] = sanitized;
                }
            }

            return clean;
        }

        if (node is JsonArray array)
        {
            var clean = new JsonArray();
            foreach (JsonNode? item in array.Take(20))
            {
                clean.Add(Sanitize(item, depth + 1));
            }

            return clean;
        }

        return node.DeepClone();
    }
}
