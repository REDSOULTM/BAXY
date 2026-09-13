using System.Globalization;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;

namespace Baxy.App;

internal sealed record MemoryOperationResponseProjection(string Message)
{
    private const int MaximumMessageLength = 16_384;
    private const int MaximumProjectedRecords = 20;
    private const int MaximumRecordCount = 512;
    private const int MaximumSelectorUtf8Bytes = 256;
    private const int MaximumLabelUtf8Bytes = 512;
    private const int MaximumValueUtf8Bytes = 4096;
    private const int MaximumTagUtf8Bytes = 64;
    private const int MaximumTags = 16;
    private const int MaximumExportPathUtf8Bytes = 2048;
    private static readonly UTF8Encoding StrictUtf8 = new(
        encoderShouldEmitUTF8Identifier: false,
        throwOnInvalidBytes: true);

    internal static bool TryCreateCompleted(
        string operationName,
        JsonElement privatePayload,
        out MemoryOperationResponseProjection? projection,
        bool responseReplayed = false,
        JsonElement? privateArguments = null)
    {
        projection = null;
        if (!MemoryOperationProtector.IsMemoryOperation(operationName)
            || privatePayload.ValueKind != JsonValueKind.Object)
        {
            return false;
        }

        string? message;
        switch (operationName)
        {
            case "memory.enable":
            case "memory.disable":
                message = TryProjectConfiguration(
                    privatePayload,
                    operationName,
                    out string configuration,
                    responseReplayed)
                        ? configuration
                        : null;
                break;
            case "memory.save":
            case "memory.sensitive.save":
            case "memory.correct":
                message = TryProjectMutation(
                    privatePayload,
                    operationName,
                    out string mutation,
                    responseReplayed,
                    privateArguments)
                        ? mutation
                        : null;
                break;
            case "memory.forget":
            case "memory.session.clear":
                message = TryProjectForget(
                    privatePayload,
                    operationName,
                    out string forget,
                    responseReplayed)
                        ? forget
                        : null;
                break;
            case "memory.status":
                message = TryProjectStatus(privatePayload, out string status, responseReplayed)
                    ? status
                    : null;
                break;
            case "memory.export":
                message = TryProjectExport(
                    privatePayload,
                    responseReplayed,
                    out string export)
                    ? export
                    : null;
                break;
            case "memory.recall":
            case "memory.list":
                message = TryProjectRecords(privatePayload, out ProjectedRecords? records)
                    && records is not null
                        ? CreateRecordsMessage(records, operationName, responseReplayed)
                        : null;
                break;
            default:
                message = null;
                break;
        }
        if (string.IsNullOrWhiteSpace(message)
            || message.Length > MaximumMessageLength)
        {
            return false;
        }

        projection = new MemoryOperationResponseProjection(message);
        return true;
    }

    private static bool TryProjectConfiguration(
        JsonElement payload,
        string operationName,
        out string message,
        bool responseReplayed)
    {
        message = string.Empty;
        if (!HasExactProperties(payload, ["version", "enabled", "replayed"])
            || !HasVersionOne(payload)
            || !TryGetBoolean(payload, "enabled", out bool enabled)
            || !TryGetBoolean(payload, "replayed", out bool replayed)
            || enabled != string.Equals(operationName, "memory.enable", StringComparison.Ordinal))
        {
            return false;
        }

        message = CompletedFacts(operationName, "memory_configuration",
            new JsonObject { ["enabled"] = enabled }, responseReplayed || replayed);
        return true;
    }

    private static bool TryProjectMutation(
        JsonElement payload,
        string operationName,
        out string message,
        bool responseReplayed,
        JsonElement? privateArguments = null)
    {
        message = string.Empty;
        if (!HasExactProperties(
                payload,
                ["version", "recordId", "revision", "selector", "replayed"])
            || !HasVersionOne(payload)
            || !TryGetCanonicalIdentifier(payload, "recordId", out _)
            || !TryGetInt32(payload, "revision", minimum: 1, maximum: int.MaxValue, out _)
            || !TryGetBoundedText(
                payload,
                "selector",
                MaximumSelectorUtf8Bytes,
                allowEmpty: false,
                out _)
            || !TryGetBoolean(payload, "replayed", out bool replayed))
        {
            return false;
        }

        // The person just stated the datum; a non-secret save may say it back
        // («recordaré que te llamás Reta»). Flags that are false carry no fact
        // and used to be verbalized as «no se realizaron correcciones ni
        // acciones de replay» (MEMORY1247); a secret stays unspoken.
        var observed = new JsonObject { ["saved"] = true };
        if (operationName == "memory.correct")
        {
            observed["corrected"] = true;
        }
        if (operationName == "memory.sensitive.save")
        {
            observed["sensitive"] = true;
        }
        if (privateArguments is { ValueKind: JsonValueKind.Object } arguments
            && operationName != "memory.sensitive.save"
            && arguments.TryGetProperty("value", out JsonElement valueElement)
            && valueElement.ValueKind == JsonValueKind.String
            && valueElement.GetString() is { } value
            && !string.IsNullOrWhiteSpace(value)
            && StrictUtf8.GetByteCount(value) <= MaximumSelectorUtf8Bytes
            && !HasControlCharacter(value))
        {
            observed["remembered"] = value.Trim();
        }
        message = CompletedFacts(operationName, "memory_updated", observed, responseReplayed || replayed);
        return true;
    }

    private static bool HasControlCharacter(string value)
    {
        foreach (char character in value)
        {
            if (char.IsControl(character))
            {
                return true;
            }
        }

        return false;
    }

    private static bool TryProjectForget(
        JsonElement payload,
        string operationName,
        out string message,
        bool responseReplayed)
    {
        message = string.Empty;
        if (!HasExactProperties(payload, ["version", "deletedCount", "replayed"])
            || !HasVersionOne(payload)
            || !TryGetInt32(
                payload,
                "deletedCount",
                minimum: 0,
                maximum: MaximumRecordCount,
                out int deleted)
            || !TryGetBoolean(payload, "replayed", out bool replayed))
        {
            return false;
        }

        message = deleted == 0 && operationName != "memory.session.clear"
            ? TurnVisibleFacts.Failure("memory_forget_empty")
            : CompletedFacts(operationName, "memory_deleted",
                new JsonObject { ["deletedCount"] = deleted }, responseReplayed || replayed);
        return true;
    }

    private static bool TryProjectStatus(JsonElement payload, out string message, bool responseReplayed)
    {
        message = string.Empty;
        if (!HasExactProperties(
                payload,
                [
                    "version",
                    "enabled",
                    "totalRecords",
                    "persistentRecords",
                    "sessionRecords",
                    "temporaryRecords",
                    "maximumRecords",
                ])
            || !HasVersionOne(payload)
            || !TryGetBoolean(payload, "enabled", out bool enabled)
            || !TryGetInt32(
                payload,
                "maximumRecords",
                minimum: 1,
                maximum: 4096,
                out int maximum)
            || !TryGetInt32(payload, "totalRecords", 0, maximum, out int total)
            || !TryGetInt32(payload, "persistentRecords", 0, maximum, out int persistent)
            || !TryGetInt32(payload, "sessionRecords", 0, maximum, out int session)
            || !TryGetInt32(payload, "temporaryRecords", 0, maximum, out int temporary)
            || (long)persistent + session + temporary != total)
        {
            return false;
        }

        message = CompletedFacts("memory.status", "memory_status", new JsonObject
        {
            ["enabled"] = enabled,
            ["totalRecords"] = total,
            ["persistentRecords"] = persistent,
            ["sessionRecords"] = session,
            ["temporaryRecords"] = temporary,
            ["maximumRecords"] = maximum,
        }, responseReplayed);
        return true;
    }

    private static bool TryProjectExport(
        JsonElement payload,
        bool responseReplayed,
        out string message)
    {
        message = string.Empty;
        if (!HasExactProperties(
                payload,
                ["version", "path", "recordCount", "sha256", "replayed"])
            || !HasVersionOne(payload)
            || !TryGetBoundedText(
                payload,
                "path",
                MaximumExportPathUtf8Bytes,
                allowEmpty: false,
                out string path)
            || !IsSafeExportResultPath(path)
            || !TryGetInt32(
                payload,
                "recordCount",
                minimum: 0,
                maximum: MaximumRecordCount,
                out int count)
            || !TryGetBoundedText(
                payload,
                "sha256",
                64,
                allowEmpty: false,
                out string sha256)
            || sha256.Length != 64
            || !ContainsOnlyLowerHex(sha256.AsSpan())
            || !TryGetBoolean(payload, "replayed", out bool payloadReplayed))
        {
            return false;
        }

        message = CompletedFacts("memory.export", "memory_exported", new JsonObject
        {
            ["destination"] = "Documents/BAXY",
            ["recordCount"] = count,
            ["integrityVerified"] = true,
            ["integrityAlgorithm"] = "SHA-256",
            ["mayRedirectOrSync"] = true,
        }, responseReplayed || payloadReplayed);
        return true;
    }

    private static bool IsSafeExportResultPath(string candidate)
    {
        try
        {
            if (candidate.StartsWith("\\\\", StringComparison.Ordinal)
                || candidate.StartsWith("//", StringComparison.Ordinal)
                || !Path.IsPathFullyQualified(candidate))
            {
                return false;
            }

            string fullPath = Path.GetFullPath(candidate);
            string? root = Path.GetPathRoot(fullPath);
            string? directory = Path.GetDirectoryName(fullPath);
            string fileName = Path.GetFileName(fullPath);
            const string prefix = "memory-export-";
            const string suffix = ".json";
            if (string.IsNullOrEmpty(root)
                || string.IsNullOrEmpty(directory)
                || !string.Equals(fullPath, candidate, StringComparison.OrdinalIgnoreCase)
                || fullPath.AsSpan(root.Length).Contains(':')
                || !string.Equals(
                    Path.GetFileName(directory),
                    "BAXY",
                    StringComparison.Ordinal)
                || !fileName.StartsWith(prefix, StringComparison.Ordinal)
                || !fileName.EndsWith(suffix, StringComparison.Ordinal)
                || fileName.Length != prefix.Length + 64 + suffix.Length)
            {
                return false;
            }

            ReadOnlySpan<char> digest = fileName.AsSpan(
                prefix.Length,
                64);
            return ContainsOnlyLowerHex(digest);
        }
        catch (Exception exception) when (exception is ArgumentException
            or NotSupportedException
            or PathTooLongException)
        {
            return false;
        }
    }

    private static bool TryProjectRecords(
        JsonElement payload,
        out ProjectedRecords? projected)
    {
        projected = null;
        if (!HasExactProperties(
                payload,
                ["version", "records", "count", "totalCount", "offset", "limit"])
            || !HasVersionOne(payload)
            || !payload.TryGetProperty("records", out JsonElement records)
            || records.ValueKind != JsonValueKind.Array
            || records.GetArrayLength() > 100
            || !TryGetInt32(payload, "count", 0, 100, out int count)
            || count != records.GetArrayLength()
            || !TryGetInt32(
                payload,
                "totalCount",
                count,
                MaximumRecordCount,
                out int totalCount)
            || !TryGetInt32(payload, "offset", 0, MaximumRecordCount, out int offset)
            || !TryGetInt32(payload, "limit", 1, 100, out int limit)
            || count > limit
            || (offset < totalCount && (long)offset + count > totalCount)
            || (offset >= totalCount && count != 0)
            || (long)offset + limit > MaximumRecordCount)
        {
            return false;
        }

        var values = new List<ProjectedRecord>(count);
        foreach (JsonElement record in records.EnumerateArray())
        {
            if (!TryProjectRecord(record, out ProjectedRecord? value) || value is null)
            {
                return false;
            }

            values.Add(value);
        }

        projected = new ProjectedRecords(values, totalCount, offset);
        return true;
    }

    private static bool TryProjectRecord(
        JsonElement record,
        out ProjectedRecord? projected)
    {
        projected = null;
        if (!HasExactProperties(
                record,
                [
                    "recordId",
                    "revision",
                    "selector",
                    "label",
                    "value",
                    "kind",
                    "origin",
                    "sensitivity",
                    "retention",
                    "tags",
                    "createdAtUtc",
                    "updatedAtUtc",
                    "expiresAtUtc",
                    "sourceMissionId",
                    "capturedAtUtc",
                    "sessionId",
                ])
            || !TryGetCanonicalIdentifier(record, "recordId", out _)
            || !TryGetInt32(record, "revision", 1, int.MaxValue, out _)
            || !TryGetBoundedText(
                record,
                "selector",
                MaximumSelectorUtf8Bytes,
                allowEmpty: false,
                out _)
            || !TryGetBoundedText(
                record,
                "label",
                MaximumLabelUtf8Bytes,
                allowEmpty: false,
                out string label)
            || !TryGetBoundedText(
                record,
                "value",
                MaximumValueUtf8Bytes,
                allowEmpty: false,
                out string value)
            || !TryGetEnumText(record, "kind", ["fact", "preference", "context", "rule"], out _)
            || !TryGetEnumText(record, "origin", ["explicit"], out _)
            || !TryGetEnumText(
                record,
                "sensitivity",
                ["normal", "personal", "sensitive", "secret"],
                out string sensitivity)
            || !TryGetEnumText(
                record,
                "retention",
                ["persistent", "session", "temporary"],
                out string retention)
            || !TryGetTags(record, out _)
            || !TryGetUtcTimestamp(record, "createdAtUtc", out DateTimeOffset created)
            || !TryGetUtcTimestamp(record, "updatedAtUtc", out DateTimeOffset updated)
            || updated < created
            || !TryGetNullableUtcTimestamp(record, "expiresAtUtc", out DateTimeOffset? expiry)
            || !TryGetNullableCanonicalIdentifier(record, "sourceMissionId", out _)
            || !TryGetUtcTimestamp(record, "capturedAtUtc", out _)
            || !TryGetNullableCanonicalIdentifier(record, "sessionId", out string? sessionId)
            || !RetentionMetadataIsConsistent(retention, expiry, sessionId))
        {
            return false;
        }

        string safeValue = sensitivity is "sensitive" or "secret"
            ? "[REDACTED]"
            : value;
        projected = new ProjectedRecord(label, safeValue);
        return true;
    }

    private static bool RetentionMetadataIsConsistent(
        string retention,
        DateTimeOffset? expiry,
        string? sessionId) => retention switch
        {
            "persistent" => expiry is null && sessionId is null,
            "session" => expiry is null && sessionId is not null,
            "temporary" => expiry is not null && sessionId is null,
            _ => false,
        };

    private static string CreateRecordsMessage(ProjectedRecords projected, string operationName, bool responseReplayed)
    {
        if (projected.TotalCount == 0)
        {
            return TurnVisibleFacts.Failure("memory_none");
        }

        var records = new JsonArray();
        int shown = 0;
        foreach (ProjectedRecord record in projected.Records.Take(MaximumProjectedRecords))
        {
            string label = TruncateText(record.Label, 160, "…");
            string value = TruncateText(record.Value, 512, "…");
            records.Add(new JsonObject
            {
                ["label"] = label,
                ["value"] = value,
            });
            shown++;
            if (shown >= MaximumProjectedRecords)
            {
                break;
            }
        }

        string cause = shown == 0 ? "memory_view_unsafe" : "memory_records";
        JsonObject extra = new()
        {
            ["shown"] = shown,
            ["total"] = projected.TotalCount,
            ["records"] = records,
        };
        return shown == 0
            ? TurnVisibleFacts.Failure(cause, extra)
            : CompletedFacts(operationName, cause, extra, responseReplayed);
    }

    private static string CompletedFacts(string operation, string cause, JsonObject observed, bool replayed)
    {
        if (replayed)
        {
            observed["replayed"] = true;
        }
        return TurnVisibleFacts.Status(cause, new JsonObject
        {
            ["operation"] = operation,
            ["verified"] = true,
            ["succeeded"] = true,
            ["observed"] = observed,
        });
    }

    private static bool HasExactProperties(JsonElement element, string[] expected)
    {
        if (element.ValueKind != JsonValueKind.Object)
        {
            return false;
        }

        var actual = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonProperty property in element.EnumerateObject())
        {
            if (!actual.Add(property.Name))
            {
                return false;
            }
        }

        return actual.SetEquals(expected);
    }

    private static bool HasVersionOne(JsonElement payload) =>
        payload.TryGetProperty("version", out JsonElement version)
        && version.ValueKind == JsonValueKind.Number
        && version.TryGetInt32(out int parsed)
        && parsed == 1
        && string.Equals(version.GetRawText(), "1", StringComparison.Ordinal);

    private static bool TryGetBoolean(
        JsonElement payload,
        string name,
        out bool value)
    {
        value = false;
        if (!payload.TryGetProperty(name, out JsonElement element)
            || element.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
        {
            return false;
        }

        value = element.GetBoolean();
        return true;
    }

    private static bool TryGetInt32(
        JsonElement payload,
        string name,
        int minimum,
        int maximum,
        out int value)
    {
        value = 0;
        return payload.TryGetProperty(name, out JsonElement element)
            && element.ValueKind == JsonValueKind.Number
            && element.TryGetInt32(out value)
            && value >= minimum
            && value <= maximum
            && string.Equals(
                element.GetRawText(),
                value.ToString(CultureInfo.InvariantCulture),
                StringComparison.Ordinal);
    }

    private static bool TryGetCanonicalIdentifier(
        JsonElement payload,
        string name,
        out string value)
    {
        value = string.Empty;
        if (!payload.TryGetProperty(name, out JsonElement element)
            || element.ValueKind != JsonValueKind.String
            || element.GetString() is not { } candidate
            || !ContractValidator.IsCanonicalIdentifier(candidate))
        {
            return false;
        }

        value = candidate;
        return true;
    }

    private static bool TryGetNullableCanonicalIdentifier(
        JsonElement payload,
        string name,
        out string? value)
    {
        value = null;
        if (!payload.TryGetProperty(name, out JsonElement element))
        {
            return false;
        }

        if (element.ValueKind == JsonValueKind.Null)
        {
            return true;
        }

        if (element.ValueKind != JsonValueKind.String
            || element.GetString() is not { } candidate
            || !ContractValidator.IsCanonicalIdentifier(candidate))
        {
            return false;
        }

        value = candidate;
        return true;
    }

    private static bool TryGetBoundedText(
        JsonElement payload,
        string name,
        int maximumUtf8Bytes,
        bool allowEmpty,
        out string value)
    {
        value = string.Empty;
        if (!payload.TryGetProperty(name, out JsonElement element)
            || element.ValueKind != JsonValueKind.String
            || element.GetString() is not { } candidate
            || (!allowEmpty && candidate.Length == 0)
            || !candidate.IsNormalized(NormalizationForm.FormC)
            || candidate.Any(static character => char.IsControl(character)))
        {
            return false;
        }

        try
        {
            if (StrictUtf8.GetByteCount(candidate) > maximumUtf8Bytes)
            {
                return false;
            }
        }
        catch (EncoderFallbackException)
        {
            return false;
        }

        value = candidate;
        return true;
    }

    private static bool TryGetEnumText(
        JsonElement payload,
        string name,
        string[] allowed,
        out string value)
    {
        value = string.Empty;
        if (!payload.TryGetProperty(name, out JsonElement element)
            || element.ValueKind != JsonValueKind.String
            || element.GetString() is not { } candidate
            || !allowed.Contains(candidate, StringComparer.Ordinal))
        {
            return false;
        }

        value = candidate;
        return true;
    }

    private static bool TryGetTags(JsonElement payload, out string[] tags)
    {
        tags = [];
        if (!payload.TryGetProperty("tags", out JsonElement element)
            || element.ValueKind != JsonValueKind.Array
            || element.GetArrayLength() > MaximumTags)
        {
            return false;
        }

        var values = new List<string>(element.GetArrayLength());
        var unique = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonElement tag in element.EnumerateArray())
        {
            if (tag.ValueKind != JsonValueKind.String
                || tag.GetString() is not { } candidate
                || candidate.Length == 0
                || !candidate.IsNormalized(NormalizationForm.FormC)
                || candidate.Any(static character => char.IsControl(character)))
            {
                return false;
            }

            try
            {
                if (StrictUtf8.GetByteCount(candidate) > MaximumTagUtf8Bytes)
                {
                    return false;
                }
            }
            catch (EncoderFallbackException)
            {
                return false;
            }

            if (!unique.Add(candidate))
            {
                return false;
            }

            values.Add(candidate);
        }

        tags = values.ToArray();
        return true;
    }

    private static bool TryGetUtcTimestamp(
        JsonElement payload,
        string name,
        out DateTimeOffset value)
    {
        value = default;
        return payload.TryGetProperty(name, out JsonElement element)
            && element.ValueKind == JsonValueKind.String
            && TryParseCanonicalUtcTimestamp(element.GetString(), out value);
    }

    private static bool TryGetNullableUtcTimestamp(
        JsonElement payload,
        string name,
        out DateTimeOffset? value)
    {
        value = null;
        if (!payload.TryGetProperty(name, out JsonElement element))
        {
            return false;
        }

        if (element.ValueKind == JsonValueKind.Null)
        {
            return true;
        }

        if (element.ValueKind != JsonValueKind.String
            || !TryParseCanonicalUtcTimestamp(element.GetString(), out DateTimeOffset parsed))
        {
            return false;
        }

        value = parsed;
        return true;
    }

    private static bool TryParseCanonicalUtcTimestamp(
        string? text,
        out DateTimeOffset value)
    {
        value = default;
        if (text is null
            || !text.EndsWith("+00:00", StringComparison.Ordinal)
            || text.Length is < 25 or > 33)
        {
            return false;
        }

        int offsetStart = text.Length - 6;
        bool noFraction = offsetStart == 19;
        int fractionDigits = offsetStart - 20;
        if (!noFraction
            && (text[19] != '.'
                || fractionDigits is < 1 or > 7
                || !ContainsOnlyAsciiDigits(text.AsSpan(20, fractionDigits))))
        {
            return false;
        }

        string format = noFraction
            ? "yyyy-MM-dd'T'HH:mm:sszzz"
            : "yyyy-MM-dd'T'HH:mm:ss.FFFFFFFzzz";
        return DateTimeOffset.TryParseExact(
                text,
                format,
                CultureInfo.InvariantCulture,
                DateTimeStyles.None,
                out value)
            && value.Offset == TimeSpan.Zero;
    }

    private static bool ContainsOnlyAsciiDigits(ReadOnlySpan<char> value)
    {
        foreach (char character in value)
        {
            if (character is < '0' or > '9')
            {
                return false;
            }
        }

        return true;
    }

    private static bool ContainsOnlyLowerHex(ReadOnlySpan<char> value)
    {
        foreach (char character in value)
        {
            if (character is not (>= '0' and <= '9' or >= 'a' and <= 'f'))
            {
                return false;
            }
        }

        return true;
    }

    private static string TruncateText(string value, int maximumLength, string suffix)
    {
        if (value.Length <= maximumLength)
        {
            return value;
        }

        int keep = Math.Max(0, maximumLength - suffix.Length);
        if (keep > 0
            && keep < value.Length
            && char.IsHighSurrogate(value[keep - 1])
            && char.IsLowSurrogate(value[keep]))
        {
            keep--;
        }

        return string.Concat(value.AsSpan(0, keep), suffix);
    }

    private sealed record ProjectedRecord(string Label, string Value);

    private sealed record ProjectedRecords(
        IReadOnlyList<ProjectedRecord> Records,
        int TotalCount,
        int Offset);
}
