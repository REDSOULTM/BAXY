using System.Globalization;
using System.IO;
using System.Text;
using System.Text.Json;
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
        bool responseReplayed = false)
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
                    out string configuration)
                        ? configuration
                        : null;
                break;
            case "memory.save":
            case "memory.sensitive.save":
            case "memory.correct":
                message = TryProjectMutation(
                    privatePayload,
                    operationName,
                    out string mutation)
                        ? mutation
                        : null;
                break;
            case "memory.forget":
            case "memory.session.clear":
                message = TryProjectForget(
                    privatePayload,
                    operationName,
                    out string forget)
                        ? forget
                        : null;
                break;
            case "memory.status":
                message = TryProjectStatus(privatePayload, out string status)
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
                        ? CreateRecordsMessage(records)
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
        out string message)
    {
        message = string.Empty;
        if (!HasExactProperties(payload, ["version", "enabled", "replayed"])
            || !HasVersionOne(payload)
            || !TryGetBoolean(payload, "enabled", out bool enabled)
            || !TryGetBoolean(payload, "replayed", out _)
            || enabled != string.Equals(operationName, "memory.enable", StringComparison.Ordinal))
        {
            return false;
        }

        message = enabled
            ? "La memoria local está habilitada."
            : "La memoria local está deshabilitada.";
        return true;
    }

    private static bool TryProjectMutation(
        JsonElement payload,
        string operationName,
        out string message)
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
            || !TryGetBoolean(payload, "replayed", out _))
        {
            return false;
        }

        message = operationName switch
        {
            "memory.correct" => "Corregí la memoria local solicitada.",
            "memory.sensitive.save" => "Guardé el dato sensible en la memoria local protegida.",
            _ => "Guardé el dato en la memoria local.",
        };
        return true;
    }

    private static bool TryProjectForget(
        JsonElement payload,
        string operationName,
        out string message)
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
            || !TryGetBoolean(payload, "replayed", out _))
        {
            return false;
        }

        message = deleted switch
        {
            0 when operationName == "memory.session.clear" =>
                "No había memoria temporal de esta sesión para eliminar.",
            0 => "No encontré memorias que eliminaran esa selección exacta.",
            1 => "Eliminé una memoria local.",
            _ => $"Eliminé {deleted} memorias locales.",
        };
        return true;
    }

    private static bool TryProjectStatus(JsonElement payload, out string message)
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

        string state = enabled ? "habilitada" : "deshabilitada";
        message = $"La memoria local está {state}: {total} en total ({persistent} persistentes, {session} de esta sesión y {temporary} temporales), con un máximo de {maximum}.";
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

        string countText = count == 1 ? "una memoria" : $"{count} memorias";
        message = responseReplayed || payloadReplayed
            ? $"El archivo de exportación de {countText} ya estaba disponible en Documentos/BAXY y su integridad SHA-256 fue verificada. Esa carpeta puede estar redirigida o sincronizada según la configuración de Windows."
            : $"Exporté {countText} en Documentos/BAXY y verifiqué su integridad SHA-256. Esa carpeta puede estar redirigida o sincronizada según la configuración de Windows.";
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

    private static string CreateRecordsMessage(ProjectedRecords projected)
    {
        if (projected.TotalCount == 0)
        {
            return "No encontré memorias visibles para esa consulta.";
        }

        var builder = new StringBuilder();
        int shown = 0;
        foreach (ProjectedRecord record in projected.Records.Take(MaximumProjectedRecords))
        {
            string label = TruncateText(record.Label, 160, "…");
            string value = TruncateText(record.Value, 512, "…");
            string line = $"\n• {label}: {value}";
            if (builder.Length + line.Length + 96 > MaximumMessageLength)
            {
                break;
            }

            _ = builder.Append(line);
            shown++;
        }

        string header = shown switch
        {
            0 => TurnVisibleFacts.Failure("memory_view_unsafe"),
            1 => "Encontré esta memoria local:",
            _ => $"Encontré estas {shown} memorias locales:",
        };
        string suffix = projected.TotalCount > shown
            ? $"\nMostré {shown} de {projected.TotalCount} memorias visibles."
            : string.Empty;
        string message = string.Concat(header, builder.ToString(), suffix);
        return TruncateText(message, MaximumMessageLength, "… [vista truncada]");
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
