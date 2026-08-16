using System.Text.Json;
using Baxy.Contracts;

namespace Baxy.App;

internal sealed record OperationResponseProjection(string Message)
{
    private const int MaximumMessageLength = 16_384;

    public static OperationResponseProjection Create(OperationResponse response, string operationName)
    {
        ArgumentNullException.ThrowIfNull(response);
        ArgumentException.ThrowIfNullOrWhiteSpace(operationName);
        if (response.Status == OperationStatuses.Completed
            && string.Equals(operationName, "note.list", StringComparison.Ordinal)
            && TryProjectNoteList(response.Result, out string? noteList))
        {
            return new OperationResponseProjection(TruncateMessage(noteList));
        }

        if (response.Status == OperationStatuses.Completed
            && string.Equals(operationName, "note.read", StringComparison.Ordinal)
            && TryProjectNoteRead(response.Result, out string? noteRead))
        {
            return new OperationResponseProjection(TruncateMessage(
                noteRead,
                "\n\n[Contenido truncado en la vista.]"));
        }

        if (!string.IsNullOrWhiteSpace(response.Message) && !LooksLikeRawJson(response.Message))
        {
            var trimmed = response.Message.Trim();
            return new OperationResponseProjection(TruncateMessage(trimmed));
        }

        return new OperationResponseProjection(response.Status switch
        {
            OperationStatuses.Rejected => "No pude realizar esa petición de forma segura.",
            OperationStatuses.Pending => "La petición sigue pendiente de una comprobación segura.",
            OperationStatuses.Failed => "No pude completar la petición.",
            OperationStatuses.Completed => "La misión terminó, pero no recibí un resumen natural.",
            _ => "No pude convertir el resultado en una respuesta clara.",
        });
    }

    private static bool LooksLikeRawJson(string value)
    {
        var trimmed = value.TrimStart();
        return trimmed.StartsWith('{') || trimmed.StartsWith('[');
    }

    private static bool TryProjectNoteRead(JsonElement? result, out string message)
    {
        message = string.Empty;
        if (result is not { ValueKind: JsonValueKind.Object } value
            || !value.TryGetProperty("title", out JsonElement titleElement)
            || titleElement.ValueKind != JsonValueKind.String
            || !value.TryGetProperty("content", out JsonElement contentElement)
            || contentElement.ValueKind != JsonValueKind.String)
        {
            return false;
        }

        string? title = titleElement.GetString();
        string? content = contentElement.GetString();
        if (string.IsNullOrWhiteSpace(title) || content is null)
        {
            return false;
        }

        message = string.IsNullOrEmpty(content)
            ? $"La nota «{title}» está vacía."
            : $"Nota «{title}»:\n{content}";
        return true;
    }

    private static string TruncateMessage(
        string value,
        string suffix = "… [respuesta truncada]")
    {
        if (value.Length <= MaximumMessageLength)
        {
            return value;
        }

        int keep = Math.Max(0, MaximumMessageLength - suffix.Length);
        if (keep > 0
            && keep < value.Length
            && char.IsHighSurrogate(value[keep - 1])
            && char.IsLowSurrogate(value[keep]))
        {
            keep--;
        }

        return string.Concat(value.AsSpan(0, keep), suffix);
    }

    private static bool TryProjectNoteList(JsonElement? result, out string message)
    {
        message = string.Empty;
        if (result is not { ValueKind: JsonValueKind.Object } value
            || !value.TryGetProperty("notes", out JsonElement notes)
            || notes.ValueKind != JsonValueKind.Array)
        {
            return false;
        }

        string[] titles = notes
            .EnumerateArray()
            .Select(static note => note.TryGetProperty("title", out JsonElement title)
                ? title.GetString()
                : null)
            .Where(static title => !string.IsNullOrWhiteSpace(title))
            .Select(static title => title!)
            .Take(20)
            .ToArray();
        int totalCount = value.TryGetProperty("totalCount", out JsonElement total)
            && total.TryGetInt32(out int parsedTotal)
            && parsedTotal >= titles.Length
                ? parsedTotal
                : titles.Length;
        message = titles.Length switch
        {
            0 when totalCount == 0 => "No encontré notas en esa lista.",
            0 => $"Hay {totalCount} notas, pero esta página no contiene títulos visibles.",
            1 when totalCount == 1 => $"Encontré la nota «{titles[0]}».",
            _ when titles.Length < totalCount =>
                $"Mostré {titles.Length} de {totalCount} notas: {string.Join(", ", titles.Select(static title => $"«{title}»"))}.",
            _ => $"Encontré {titles.Length} notas: {string.Join(", ", titles.Select(static title => $"«{title}»"))}.",
        };
        return true;
    }
}
