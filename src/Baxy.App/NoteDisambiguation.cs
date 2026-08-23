using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Baxy.Contracts;

namespace Baxy.App;

internal sealed record NoteChoiceCandidate(
    Guid NoteId,
    string Title,
    string ContentPreview,
    DateTimeOffset CreatedAtUtc,
    DateTimeOffset UpdatedAtUtc,
    long Revision,
    bool IsTrashed);

internal sealed class PendingNoteChoice
{
    internal const int MaximumCandidates = 512;
    internal const int PageSize = 5;
    private const int MaximumTitleUtf8Bytes = 512;
    private const int MaximumPreviewUtf8Bytes = 128;
    private static readonly string[] CandidatePropertyNames =
    [
        "noteId",
        "contentPreview",
        "createdAtUtc",
        "updatedAtUtc",
        "revision",
        "isTrashed",
    ];

    private PendingNoteChoice(
        string operationName,
        string title,
        IReadOnlyList<NoteChoiceCandidate> candidates)
    {
        OperationName = operationName;
        Title = title;
        Candidates = candidates;
    }

    public string OperationName { get; }

    public string Title { get; }

    public IReadOnlyList<NoteChoiceCandidate> Candidates { get; }

    public int PageOffset { get; private set; }

    public int FirstVisibleNumber => PageOffset + 1;

    public int LastVisibleNumber => Math.Min(PageOffset + PageSize, Candidates.Count);

    public static bool TryCreate(
        OperationResponse response,
        RoutedOperation routed,
        out PendingNoteChoice? choice)
    {
        ArgumentNullException.ThrowIfNull(response);
        ArgumentNullException.ThrowIfNull(routed);
        choice = null;
        if (response.Status != OperationStatuses.Failed
            || !string.Equals(response.ErrorCode, "note_ambiguous", StringComparison.Ordinal)
            || !IsChoiceOperation(routed.Name)
            || !TryGetOriginalTitle(routed, out string? originalTitle)
            || response.Result is not { ValueKind: JsonValueKind.Object } result
            || !HasExactProperties(result, ["candidates"])
            || !result.TryGetProperty("candidates", out JsonElement candidatesElement)
            || candidatesElement.ValueKind != JsonValueKind.Array)
        {
            return false;
        }

        int candidateCount = candidatesElement.GetArrayLength();
        if (candidateCount is < 2 or > MaximumCandidates)
        {
            return false;
        }

        var candidates = new List<NoteChoiceCandidate>(candidateCount);
        var ids = new HashSet<Guid>();
        foreach (JsonElement candidateElement in candidatesElement.EnumerateArray())
        {
            if (!TryParseCandidate(candidateElement, originalTitle!, out NoteChoiceCandidate? candidate)
                || candidate is null
                || !ids.Add(candidate.NoteId))
            {
                return false;
            }

            candidates.Add(candidate);
        }

        if (!HasStableOrder(candidates))
        {
            return false;
        }

        choice = new PendingNoteChoice(routed.Name, originalTitle!, candidates.AsReadOnly());
        return true;
    }

    public string CreatePrompt()
    {
        int pageNumber = (PageOffset / PageSize) + 1;
        int pageCount = (Candidates.Count + PageSize - 1) / PageSize;
        var items = new JsonArray();
        for (int index = PageOffset; index < LastVisibleNumber; index++)
        {
            NoteChoiceCandidate candidate = Candidates[index];
            items.Add(new JsonObject
            {
                ["n"] = index + 1,
                ["trashed"] = candidate.IsTrashed,
                ["updated"] = candidate.UpdatedAtUtc.ToString(
                    "yyyy-MM-dd HH:mm",
                    CultureInfo.InvariantCulture),
                ["preview"] = candidate.ContentPreview,
            });
        }

        return TurnVisibleFacts.Clarification(
            "note_choice",
            new JsonObject
            {
                ["count"] = Candidates.Count,
                ["title"] = Title,
                ["page"] = pageNumber,
                ["pageCount"] = pageCount,
                ["first"] = FirstVisibleNumber,
                ["last"] = LastVisibleNumber,
                ["hasNext"] = LastVisibleNumber < Candidates.Count,
                ["hasPrevious"] = PageOffset > 0,
                ["items"] = items,
                ["action"] = OperationName,
            });
    }

    public bool MoveNext()
    {
        if (LastVisibleNumber >= Candidates.Count)
        {
            return false;
        }

        PageOffset += PageSize;
        return true;
    }

    public bool MovePrevious()
    {
        if (PageOffset == 0)
        {
            return false;
        }

        PageOffset = Math.Max(0, PageOffset - PageSize);
        return true;
    }

    public bool TrySelect(int number, out NoteChoiceCandidate? candidate)
    {
        if (number < FirstVisibleNumber || number > LastVisibleNumber)
        {
            candidate = null;
            return false;
        }

        candidate = Candidates[number - 1];
        return true;
    }

    public RoutedOperation CreateSelectedRoute(NoteChoiceCandidate candidate)
    {
        ArgumentNullException.ThrowIfNull(candidate);
        if (!Candidates.Contains(candidate))
        {
            throw new InvalidOperationException("La opción no pertenece a la lista activa.");
        }

        return new RoutedOperation(
            OperationName,
            new JsonObject
            {
                ["noteId"] = candidate.NoteId.ToString("D"),
                ["expectedTitle"] = candidate.Title,
                ["expectedRevision"] = candidate.Revision,
                ["expectedIsTrashed"] = candidate.IsTrashed,
            });
    }

    private static bool TryParseCandidate(
        JsonElement value,
        string originalTitle,
        out NoteChoiceCandidate? candidate)
    {
        candidate = null;
        if (value.ValueKind != JsonValueKind.Object
            || !HasExactProperties(value, CandidatePropertyNames)
            || !TryGetString(value, "noteId", out string? noteIdText)
            || !Guid.TryParseExact(noteIdText, "D", out Guid noteId)
            || noteId == Guid.Empty
            || !string.Equals(noteIdText, noteId.ToString("D"), StringComparison.Ordinal)
            || !TryGetString(value, "contentPreview", out string? contentPreview)
            || !TryValidateText(contentPreview, MaximumPreviewUtf8Bytes, allowEmpty: true)
            || !TryGetUtcDateTime(value, "createdAtUtc", out DateTimeOffset createdAtUtc)
            || !TryGetUtcDateTime(value, "updatedAtUtc", out DateTimeOffset updatedAtUtc)
            || updatedAtUtc < createdAtUtc
            || !value.TryGetProperty("revision", out JsonElement revisionElement)
            || !revisionElement.TryGetInt64(out long revision)
            || revision < 1
            || !value.TryGetProperty("isTrashed", out JsonElement trashedElement)
            || trashedElement.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
        {
            return false;
        }

        candidate = new NoteChoiceCandidate(
            noteId,
            originalTitle,
            contentPreview!,
            createdAtUtc,
            updatedAtUtc,
            revision,
            trashedElement.GetBoolean());
        return true;
    }

    private static bool TryGetOriginalTitle(RoutedOperation routed, out string? title)
    {
        title = null;
        if (routed.Arguments.Count != 1
            || !routed.Arguments.TryGetPropertyValue("title", out JsonNode? titleNode)
            || titleNode is not JsonValue titleValue
            || !titleValue.TryGetValue(out title)
            || !TryValidateText(title, MaximumTitleUtf8Bytes, allowEmpty: false))
        {
            return false;
        }

        return true;
    }

    private static bool HasStableOrder(List<NoteChoiceCandidate> candidates)
    {
        for (int index = 1; index < candidates.Count; index++)
        {
            NoteChoiceCandidate previous = candidates[index - 1];
            NoteChoiceCandidate current = candidates[index];
            if (previous.UpdatedAtUtc < current.UpdatedAtUtc
                || (previous.UpdatedAtUtc == current.UpdatedAtUtc
                    && previous.NoteId.CompareTo(current.NoteId) > 0))
            {
                return false;
            }
        }

        return true;
    }

    private static bool HasExactProperties(JsonElement value, string[] names)
    {
        var remaining = new HashSet<string>(names, StringComparer.Ordinal);
        int count = 0;
        foreach (JsonProperty property in value.EnumerateObject())
        {
            count++;
            if (!remaining.Remove(property.Name))
            {
                return false;
            }
        }

        return count == names.Length && remaining.Count == 0;
    }

    private static bool TryGetString(JsonElement value, string propertyName, out string? result)
    {
        result = null;
        return value.TryGetProperty(propertyName, out JsonElement element)
            && element.ValueKind == JsonValueKind.String
            && (result = element.GetString()) is not null;
    }

    private static bool TryGetUtcDateTime(
        JsonElement value,
        string propertyName,
        out DateTimeOffset result)
    {
        result = default;
        return value.TryGetProperty(propertyName, out JsonElement element)
            && element.ValueKind == JsonValueKind.String
            && element.TryGetDateTimeOffset(out result)
            && result.Offset == TimeSpan.Zero;
    }

    private static bool TryValidateText(string? value, int maximumUtf8Bytes, bool allowEmpty)
    {
        if (value is null
            || (!allowEmpty && value.Length == 0)
            || !value.IsNormalized(NormalizationForm.FormC)
            || Encoding.UTF8.GetByteCount(value) > maximumUtf8Bytes)
        {
            return false;
        }

        return value.All(static character => !char.IsControl(character));
    }

    private static bool IsChoiceOperation(string operationName) =>
        operationName is "note.read" or "note.trash" or "note.restore";
}

internal enum NoteChoiceReplyKind
{
    Invalid,
    Select,
    Next,
    Previous,
    Cancel,
    Continue,
}

internal readonly record struct NoteChoiceReply(NoteChoiceReplyKind Kind, int Number = 0);

internal static partial class NoteChoiceReplyParser
{
    public static NoteChoiceReply Parse(string text)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(text);
        if (!IsWellFormedUtf16(text))
        {
            return new NoteChoiceReply(NoteChoiceReplyKind.Invalid);
        }

        string normalized = text.Trim().Normalize(NormalizationForm.FormC);
        if (normalized.Any(static character => char.IsControl(character)))
        {
            return new NoteChoiceReply(NoteChoiceReplyKind.Invalid);
        }

        if (CancelPattern().IsMatch(normalized))
        {
            return new NoteChoiceReply(NoteChoiceReplyKind.Cancel);
        }

        if (NextPattern().IsMatch(normalized))
        {
            return new NoteChoiceReply(NoteChoiceReplyKind.Next);
        }

        if (PreviousPattern().IsMatch(normalized))
        {
            return new NoteChoiceReply(NoteChoiceReplyKind.Previous);
        }

        if (ContinuePattern().IsMatch(normalized))
        {
            return new NoteChoiceReply(NoteChoiceReplyKind.Continue);
        }

        Match ordinalSelection = OrdinalSelectionPattern().Match(normalized);
        if (ordinalSelection.Success)
        {
            int ordinal = ordinalSelection.Groups["ordinal"].Value.ToLowerInvariant() switch
            {
                "primer" or "primero" or "primera" or "first" => 1,
                "segundo" or "segunda" or "second" => 2,
                "tercer" or "tercero" or "tercera" or "third" => 3,
                "cuarto" or "cuarta" or "fourth" => 4,
                "quinto" or "quinta" or "fifth" => 5,
                _ => 0,
            };
            return ordinal > 0
                ? new NoteChoiceReply(NoteChoiceReplyKind.Select, ordinal)
                : new NoteChoiceReply(NoteChoiceReplyKind.Invalid);
        }

        Match selection = SelectionPattern().Match(normalized);
        return selection.Success
            && int.TryParse(
                selection.Groups["number"].Value,
                NumberStyles.None,
                CultureInfo.InvariantCulture,
                out int number)
            && number <= PendingNoteChoice.MaximumCandidates
                ? new NoteChoiceReply(NoteChoiceReplyKind.Select, number)
                : new NoteChoiceReply(NoteChoiceReplyKind.Invalid);
    }

    private static bool IsWellFormedUtf16(string value)
    {
        for (int index = 0; index < value.Length; index++)
        {
            char character = value[index];
            if (char.IsHighSurrogate(character))
            {
                if (index + 1 >= value.Length || !char.IsLowSurrogate(value[index + 1]))
                {
                    return false;
                }

                index++;
            }
            else if (char.IsLowSurrogate(character))
            {
                return false;
            }
        }

        return true;
    }

    [GeneratedRegex(
        "^(?:cancela|cancelar|d[eé]jalo|olvida(?:lo)?|cancel|never[ \\t]+mind)[.!]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex CancelPattern();

    [GeneratedRegex(
        "^(?:m[aá]s|siguiente|otra[ \\t]+p[aá]gina|more|next|next[ \\t]+page)[.!]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex NextPattern();

    [GeneratedRegex(
        "^(?:anterior|p[aá]gina[ \\t]+anterior|atr[aá]s|previous|back|previous[ \\t]+page)[.!]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex PreviousPattern();

    [GeneratedRegex(
        "^(?:contin[uú]a|continuar|sigue|reintenta|retry|continue|go[ \\t]+ahead)[.!]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex ContinuePattern();

    [GeneratedRegex(
        "^(?:(?:elige|elijo|escojo|selecciona|choose|pick|select|i[ \\t]+choose)[ \\t]+)?(?:(?:la|el|the)[ \\t]+)?(?<ordinal>primero|primera|primer|segundo|segunda|tercero|tercera|tercer|cuarto|cuarta|quinto|quinta|first|second|third|fourth|fifth)(?:[ \\t]+one)?[.!]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex OrdinalSelectionPattern();

    [GeneratedRegex(
        "^(?:(?:elige|elijo|escojo|selecciona|choose|pick|select|i[ \\t]+choose)[ \\t]+)?(?:(?:la|el|the)[ \\t]+)?(?:(?:opci[oó]n|option)[ \\t]+)?(?<number>[1-9][0-9]{0,2})[.!]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex SelectionPattern();
}

internal sealed record PendingSelectedNote(
    PreparedOperation Prepared,
    string Title,
    long ExpectedRevision,
    bool ExpectedIsTrashed,
    int? SelectedNumber)
{
    private static readonly string[] SelectionPropertyNames =
    [
        "noteId",
        "expectedTitle",
        "expectedRevision",
        "expectedIsTrashed",
    ];

    public static bool TryCreate(
        PreparedOperation prepared,
        int? selectedNumber,
        out PendingSelectedNote? pending)
    {
        ArgumentNullException.ThrowIfNull(prepared);
        pending = null;
        JsonElement arguments = prepared.Arguments;
        if (prepared.OperationName is not ("note.read" or "note.trash" or "note.restore")
            || arguments.ValueKind != JsonValueKind.Object
            || !HasExactProperties(arguments, SelectionPropertyNames)
            || !arguments.TryGetProperty("noteId", out JsonElement noteIdElement)
            || noteIdElement.ValueKind != JsonValueKind.String
            || !Guid.TryParseExact(noteIdElement.GetString(), "D", out Guid noteId)
            || noteId == Guid.Empty
            || !string.Equals(noteIdElement.GetString(), noteId.ToString("D"), StringComparison.Ordinal)
            || !arguments.TryGetProperty("expectedTitle", out JsonElement titleElement)
            || titleElement.ValueKind != JsonValueKind.String
            || string.IsNullOrWhiteSpace(titleElement.GetString())
            || !arguments.TryGetProperty("expectedRevision", out JsonElement revisionElement)
            || !revisionElement.TryGetInt64(out long revision)
            || revision < 1
            || !arguments.TryGetProperty("expectedIsTrashed", out JsonElement stateElement)
            || stateElement.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
        {
            return false;
        }

        string title = titleElement.GetString()!;
        if (!title.IsNormalized(NormalizationForm.FormC)
            || Encoding.UTF8.GetByteCount(title) > 512
            || title.Any(static character => char.IsControl(character)))
        {
            return false;
        }

        pending = new PendingSelectedNote(
            prepared,
            title,
            revision,
            stateElement.GetBoolean(),
            selectedNumber);
        return true;
    }

    public string CreateRecoveryPrompt()
    {
        string action = Prepared.OperationName switch
        {
            "note.read" => "leer",
            "note.trash" => "enviar a la papelera",
            "note.restore" => "restaurar",
            _ => "procesar",
        };
        string option = SelectedNumber is int number
            ? $"la opción {number}"
            : "la opción que ya elegiste";
        return $"Quedó pendiente reconciliar {option} para {action} «{Title}». "
            + "Conservé exactamente esa nota y no volveré a interpretar el número. "
            + "Responde «continuar / continue» para comprobar el resultado.";
    }

    private static bool HasExactProperties(JsonElement value, string[] names)
    {
        var remaining = new HashSet<string>(names, StringComparer.Ordinal);
        int count = 0;
        foreach (JsonProperty property in value.EnumerateObject())
        {
            count++;
            if (!remaining.Remove(property.Name))
            {
                return false;
            }
        }

        return count == names.Length && remaining.Count == 0;
    }
}

internal sealed record PendingTitleNote(PreparedOperation Prepared, string Title)
{
    public static bool TryCreate(PreparedOperation prepared, out PendingTitleNote? pending)
    {
        ArgumentNullException.ThrowIfNull(prepared);
        pending = null;
        JsonElement arguments = prepared.Arguments;
        if (prepared.OperationName is not ("note.read" or "note.trash" or "note.restore")
            || arguments.ValueKind != JsonValueKind.Object
            || arguments.EnumerateObject().Count() != 1
            || !arguments.TryGetProperty("title", out JsonElement titleElement)
            || titleElement.ValueKind != JsonValueKind.String
            || string.IsNullOrWhiteSpace(titleElement.GetString()))
        {
            return false;
        }

        string title = titleElement.GetString()!;
        if (!title.IsNormalized(NormalizationForm.FormC)
            || Encoding.UTF8.GetByteCount(title) > 512
            || title.Any(static character => char.IsControl(character)))
        {
            return false;
        }

        pending = new PendingTitleNote(prepared, title);
        return true;
    }

    public RoutedOperation CreateRoute() => new(
        Prepared.OperationName,
        new JsonObject { ["title"] = Title });

    public string CreateRecoveryPrompt()
    {
        string action = Prepared.OperationName switch
        {
            "note.read" => "leer",
            "note.trash" => "enviar a la papelera",
            "note.restore" => "restaurar",
            _ => "procesar",
        };
        return TurnVisibleFacts.Confirmation(
            "note_recovery_pending",
            TurnVisibleFacts.ContinueRetry,
            extra: new System.Text.Json.Nodes.JsonObject
            {
                ["action"] = action,
                ["title"] = Title,
            });
    }
}
