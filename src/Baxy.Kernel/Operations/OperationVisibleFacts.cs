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
    public const int MaximumDenseMessageChars = 48_000;
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    public static string FromOutcome(string operation, OperationOutcome outcome)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(operation);
        ArgumentNullException.ThrowIfNull(outcome);
        bool success = outcome.Succeeded && outcome.Verified;
        bool processInventory = operation == "system.process.list";
        bool ocrObservation = operation == "ocr.read";
        bool captureObservation = operation is "capture.active.window" or "capture.screenshot";
        int observedLimit = processInventory || ocrObservation ? MaximumDenseMessageChars : MaximumObservedUtf8Bytes;
        int messageLimit = processInventory || ocrObservation ? MaximumDenseMessageChars : MaximumMessageChars;
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
            if (raw.Length <= observedLimit || ocrObservation)
            {
                try
                {
                    payload["observed"] = Sanitize(
                        JsonNode.Parse(raw),
                        processInventory: processInventory, ocrObservation: ocrObservation,
                        captureObservation: captureObservation);
                }
                catch (JsonException)
                {
                    // Observed payload stays omitted when it is not JSON.
                    if (ocrObservation) payload["observed"] = OcrSizeLimit("observation_invalid");
                }
                catch (ArgumentException)
                {
                    // Duplicate keys or re-parented nodes stay omitted.
                    if (ocrObservation) payload["observed"] = OcrSizeLimit("observation_invalid");
                }
            }
        }

        string json = payload.ToJsonString(JsonOptions);
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
        if (json.Length > messageLimit)
        {
            payload.Remove("observed");
            json = payload.ToJsonString(JsonOptions);
        }

        return json.Length <= messageLimit
            ? json
            : json[..messageLimit];
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

    private static JsonObject OcrSizeLimit(string reason = "observation_size_limit") => new()
    {
        ["available"] = false,
        ["reason"] = reason,
    };

    private static JsonNode? Sanitize(
        JsonNode? node, int depth = 0, bool processInventory = false, bool ocrObservation = false,
        bool captureObservation = false)
    {
        if (node is null || (!ocrObservation && depth > 4))
        {
            return null;
        }

        if (node is JsonObject obj)
        {
            var clean = new JsonObject();
            foreach ((string key, JsonNode? value) in obj)
            {
                if ((key is "id" or "noteId" or "hwnd" or "handle" or "fingerprint"
                    or "hash" or "sha256" or "pid" or "processId" or "invocationId"
                    or "requestId" or "missionId" or "token" or "recordId"
                    or "deviceId") && !(processInventory && key == "processId")
                    && !(ocrObservation && key is "sha256" or "hash" or "pid" or "processId" or "hwnd" or "handle")
                    && !(captureObservation && key is "sha256" or "processId"))
                {
                    continue;
                }

                JsonNode? sanitized = Sanitize(value, depth + 1, processInventory, ocrObservation, captureObservation);
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
            foreach (JsonNode? item in array.Take(ocrObservation ? array.Count : processInventory ? 50 : 20))
            {
                clean.Add(Sanitize(item, depth + 1, processInventory, ocrObservation, captureObservation));
            }

            return clean;
        }

        return node.DeepClone();
    }
}
