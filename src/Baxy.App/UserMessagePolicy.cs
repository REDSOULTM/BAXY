using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Baxy.App;

internal sealed record UserMessageDraft(
    string Source,
    string Intent,
    string? DiagnosticCode);

internal enum UserMessageEventType
{
    Welcome,
    Status,
    Clarification,
    Confirmation,
    Error,
}

internal sealed record UserMessageEvent
{
    private static readonly Regex StableDiagnosticCodePattern = new(
        @"^[1-5][0-9]{2}: ""[a-z0-9_]+""$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);

    private UserMessageEvent(
        UserMessageEventType type,
        string intent,
        string? diagnosticCode = null)
    {
        Type = type;
        Intent = intent;
        DiagnosticCode = diagnosticCode;
    }

    public UserMessageEventType Type { get; }

    public string Intent { get; }

    public string? DiagnosticCode { get; }

    public static UserMessageEvent Welcome { get; } = new(
        UserMessageEventType.Welcome,
        "welcome");

    public static UserMessageEvent Status { get; } = new(
        UserMessageEventType.Status,
        "status");

    public static UserMessageEvent Clarification { get; } = new(
        UserMessageEventType.Clarification,
        "clarification");

    public static UserMessageEvent Confirmation { get; } = new(
        UserMessageEventType.Confirmation,
        "confirmation");

    public static UserMessageEvent Error(string diagnosticCode)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(diagnosticCode);
        if (!StableDiagnosticCodePattern.IsMatch(diagnosticCode)
            || diagnosticCode is not UserMessageDiagnosticCodes.MissingData
                and not UserMessageDiagnosticCodes.Timeout
                and not UserMessageDiagnosticCodes.ActionNotCompleted
                and not UserMessageDiagnosticCodes.LocalService)
        {
            throw new ArgumentException(
                "El código de diagnóstico no pertenece al conjunto estable.",
                nameof(diagnosticCode));
        }

        return new UserMessageEvent(
            UserMessageEventType.Error,
            "error",
            diagnosticCode);
    }
}

internal static class UserMessageDiagnosticCodes
{
    public const string MissingData = "344: \"faltan_datos\"";
    public const string Timeout = "408: \"tiempo_agotado\"";
    public const string ActionNotCompleted = "500: \"accion_no_completada\"";
    public const string LocalService = "503: \"servicio_local\"";
}

internal static class MindClarificationPolicy
{
    private const string TrustedClarificationPrefix =
        "\nAclaración confiable del usuario: ";

    public static bool IsSelfContainedRequest(
        string userText,
        MindTurnDecision decision)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(userText);
        ArgumentNullException.ThrowIfNull(decision);
        return decision.Kind switch
        {
            "action" =>
                decision.Operation is { Length: > 0 } operation
                && decision.EffectOperations.Count == 1
                && string.Equals(
                    decision.EffectOperations[0],
                    operation,
                    StringComparison.Ordinal),
            "plan" => decision.Operation is null,
            // Slot values such as "mañana a las 9", "Opera" or "la segunda"
            // can look conversational in isolation. They must keep the
            // pending objective instead of silently discarding it.
            "conversation" => false,
            _ => false,
        };
    }

    public static bool ShouldResumePendingObjective(
        string userText,
        MindTurnDecision decision) =>
        decision.PreserveObjective
        && !IsSelfContainedRequest(userText, decision);

    public static string ResumeObjective(
        string pendingObjective,
        string clarification)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(pendingObjective);
        ArgumentException.ThrowIfNullOrWhiteSpace(clarification);
        return string.Concat(
            pendingObjective,
            TrustedClarificationPrefix,
            clarification);
    }
}

internal static class UserMessagePolicy
{
    internal static bool BypassLlmCompositionForTests { get; set; }

    private static readonly string[] ForbiddenTerms =
    [
        "planner",
        "router",
        "tool",
        "catálogo",
        "catalogo",
        "schema",
        "operación",
        "operacion",
        "capacidad interna",
        "grounding",
        "checkpoint",
        "reconciliación",
        "reconciliacion",
        "motor local",
        "core",
        "datos verificables",
        "pasos verificables",
        "identificador interno",
    ];

    internal static IReadOnlyList<string> ForbiddenResponseTerms => ForbiddenTerms;

    internal static bool IsStructuredFacts(string source)
    {
        ReadOnlySpan<char> trimmed = source.AsSpan().Trim();
        return trimmed.Length >= 2 && trimmed[0] == '{' && trimmed[^1] == '}';
    }

    public static UserMessageDraft Create(
        string source,
        UserMessageEvent messageEvent)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(source);
        ArgumentNullException.ThrowIfNull(messageEvent);
        return new UserMessageDraft(
            source,
            messageEvent.Intent,
            messageEvent.DiagnosticCode);
    }

    public static bool IsSafe(string text) =>
        !string.IsNullOrWhiteSpace(text)
        && text.Length <= 4_096
        && !ForbiddenTerms.Any(term => text.Contains(term, StringComparison.OrdinalIgnoreCase));

    public static bool IsSafe(string text, UserMessageDraft draft)
    {
        return ModelResponseRejectionReason(text, draft) is null;
    }

    public static string? ModelResponseRejectionReason(
        string? modelText,
        UserMessageDraft draft)
    {
        ArgumentNullException.ThrowIfNull(draft);
        if (string.IsNullOrWhiteSpace(modelText))
        {
            return "no_response";
        }
        if (IsStructuredFacts(modelText))
        {
            return "structured_facts_not_prose";
        }
        if (!IsSafe(modelText))
        {
            return "unsafe_language";
        }
        if (Regex.IsMatch(
                modelText,
                @"\b[a-z]{2,}(?:_[a-z0-9]+){1,}\b",
                RegexOptions.CultureInvariant | RegexOptions.NonBacktracking))
        {
            return "internal_code";
        }
        if (draft.Intent is "status" or "error")
        {
            if (AttributesBaxyActionToUser(draft.Source, modelText))
            {
                return "wrong_actor";
            }
            if (!PreservesBaxyFirstPerson(draft.Source, modelText))
            {
                return "missing_baxy_action";
            }
            if (!PreservesRequiredFacts(draft.Source, modelText))
            {
                return "missing_structured_fact";
            }
            if (!PreservesRequiredLiteralFacts(draft.Source, modelText))
            {
                return "missing_literal_fact";
            }
            if (AddsGenericFollowUp(modelText))
            {
                return "generic_follow_up";
            }
            if (draft.Intent == "status" && StartsWithRequestImperative(modelText))
            {
                return "imperative_result";
            }
            if (draft.Intent == "status"
                && ReversesSuccessfulResult(draft.Source, modelText))
            {
                return "reversed_result";
            }
            if (draft.Intent == "error"
                && ReversesFailedResult(draft.Source, modelText))
            {
                return "reversed_result";
            }
        }
        if (draft.Intent == "confirmation"
            && (!PreservesChoicePair(draft.Source, modelText, "confirm", "cancel")
                || !PreservesChoicePair(
                    draft.Source,
                    modelText,
                    "continuar",
                    "cancel")
                || !PreservesChoicePair(
                    draft.Source,
                    modelText,
                    "siguiente",
                    "anterior")))
        {
            return "missing_confirmation_choice";
        }
        return null;
    }

    public static string? AcceptModelAuthoredResponse(
        string? modelText,
        UserMessageDraft draft)
    {
        ArgumentNullException.ThrowIfNull(draft);
        return ModelResponseRejectionReason(modelText, draft) is null
            ? WithDiagnosticCode(modelText!, draft)
            : null;
    }

    public static bool IsSafeConversationReply(string userText, string reply)
    {
        _ = userText;
        if (!IsSafe(reply))
        {
            return false;
        }
        string folded = FoldForPolicy(reply);
        return !ContainsPersonMetadiscourse(folded);
    }

    private static bool ContainsPersonMetadiscourse(string folded)
    {
        const RegexOptions options =
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking;

        // A conversational answer should address the person, not narrate
        // what "the user/person" did or wanted. Check every sentence rather
        // than only the beginning of the whole reply.
        if (Regex.IsMatch(
                folded,
                @"(?:^|[\r\n]+|[.!?]\s+)[\s«»“”‘’'()\[\]-]*(?:(?:(?:al|del|el|la|este|esta|ese|esa)\s+|(?:a|de|para)\s+(?:el|la|este|esta|ese|esa)\s+)(?:usuario|usuaria|persona)|(?:the|this|that)\s+(?:user|person|requester))\b",
                options))
        {
            return true;
        }

        // Also reject a short introductory clause followed by an explicit
        // attribution, while avoiding ordinary guidance such as
        // "Puedes crear el usuario admin desde Configuración".
        return Regex.IsMatch(
            folded,
            @"[,;:]\s*(?:(?:(?:al|del|el|la|este|esta|ese|esa)\s+|(?:a|de|para)\s+(?:el|la|este|esta|ese|esa)\s+)(?:usuario|usuaria|persona)|(?:the|this|that)\s+(?:user|person|requester))\b[^.!?\r\n]{0,80}\b(?:le gustaria|le interesa|quiere|quisiera|desea|prefiere|pidio|ha pedido|pregunto|dijo|saludo|solicito|menciono|would like|wants|asked|said|greeted|requested|mentioned|prefers|has asked)\b",
            options);
    }

    public static string WithDiagnosticCode(string text, UserMessageDraft draft)
    {
        _ = draft;
        // El código estable queda disponible para diagnóstico interno; nunca
        // forma parte del mensaje que recibe una persona.
        return text.Trim();
    }

    private static bool LooksLikeFailure(string sourceOrResult)
    {
        if (IsStructuredFacts(sourceOrResult)
            && TryReadJson(sourceOrResult, out JsonElement root)
            && root.TryGetProperty("polarity", out JsonElement polarity)
            && polarity.ValueKind == JsonValueKind.String)
        {
            return string.Equals(polarity.GetString(), "failure", StringComparison.Ordinal);
        }

        string normalized = FoldForPolicy(sourceOrResult);
        return normalized.Contains("no pude", StringComparison.Ordinal)
        || normalized.Contains("no puedo", StringComparison.Ordinal)
        || normalized.Contains("no complete", StringComparison.Ordinal)
        || normalized.Contains("no logre", StringComparison.Ordinal)
        || normalized.Contains("no se pudo", StringComparison.Ordinal)
        || normalized.Contains("falló", StringComparison.Ordinal)
        || normalized.Contains("fallo", StringComparison.Ordinal)
        || normalized.Contains("no recibí", StringComparison.Ordinal)
        || normalized.Contains("no realicé", StringComparison.Ordinal)
        || normalized.Contains("no interpreté", StringComparison.Ordinal)
        || normalized.Contains("no está disponible", StringComparison.Ordinal)
        || normalized.Contains("i couldn't", StringComparison.Ordinal)
        || normalized.Contains("i could not", StringComparison.Ordinal)
        || normalized.Contains("wasn't able", StringComparison.Ordinal)
        || normalized.Contains("was not able", StringComparison.Ordinal)
        || normalized.Contains("failed", StringComparison.Ordinal);
    }

    private static bool AttributesBaxyActionToUser(string source, string result)
    {
        string sourceFolded = FoldForPolicy(source);
        bool baxyPerformedAction = Regex.IsMatch(
            sourceFolded,
            @"\b(?:abri|enfoque|cerre|ejecute|inicie|hice|puse|ajuste|controle|copie|pegue|resolvi|active|desactive|seleccione|cambie|envie|guarde|conecte|force|adelante|retrocedi|silencie|reactive|presione|escribi|cree|elimine|verifique)\b",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
        if (!baxyPerformedAction)
        {
            return false;
        }

        string resultFolded = FoldForPolicy(result);
        return Regex.IsMatch(
            resultFolded,
            @"\b(?:abriste|enfocaste|cerraste|ejecutaste|iniciaste|hiciste|pusiste|ajustaste|controlaste|copiaste|pegaste|resolviste|activaste|desactivaste|seleccionaste|cambiaste|enviaste|guardaste|conectaste|forzaste|adelantaste|retrocediste|silenciaste|reactivaste|presionaste|escribiste|creaste|eliminaste|verificaste)\b",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    }

    public static IReadOnlyList<string> RequiredBaxyActions(string source)
    {
        if (IsStructuredFacts(source))
        {
            return [];
        }

        MatchCollection matches = Regex.Matches(
            source,
            @"\b(?:abrí|enfoqué|cerré|ejecuté|inicié|hice|puse|ajusté|controlé|copié|pegué|resolví|activé|desactivé|seleccioné|cambié|envié|guardé|conecté|forcé|adelanté|retrocedí|silencié|reactivé|presioné|escribí|creé|eliminé|verifiqué)\b",
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant
                | RegexOptions.NonBacktracking);
        return matches
            .Select(static match => match.Value.ToLowerInvariant())
            .Distinct(StringComparer.Ordinal)
            .ToArray();
    }

    public static IReadOnlyList<string> RequiredConfirmationWords(string source)
    {
        if (IsStructuredFacts(source)
            && TryReadJson(source, out JsonElement root)
            && root.TryGetProperty("choices", out JsonElement choices)
            && choices.ValueKind == JsonValueKind.Array)
        {
            return choices.EnumerateArray()
                .Select(static item => item.GetString())
                .Where(static item => !string.IsNullOrWhiteSpace(item))
                .Select(static item => item!)
                .ToArray();
        }

        var words = new List<string>();
        AddPair("confirmar", "confirm");
        AddPair("cancelar", "cancel");
        AddPair("continuar", "continue");
        AddPair("siguiente", "anterior");
        return words;

        void AddPair(string first, string second)
        {
            if (source.Contains(first, StringComparison.OrdinalIgnoreCase))
            {
                words.Add(first);
            }

            if (source.Contains(second, StringComparison.OrdinalIgnoreCase))
            {
                words.Add(second);
            }
        }
    }

    public static IReadOnlyList<string> RequiredFactualFragments(string source)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(source);
        return source
            .Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
            .Select(static line => line.Trim())
            .Where(static line => line.StartsWith("• ", StringComparison.Ordinal))
            .Select(static line => line[2..].Trim())
            .Where(static line => line.Contains(':'))
            .Take(20)
            .ToArray();
    }

    public static IReadOnlyList<string> RequiredLiteralFacts(string source)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(source);
        if (IsStructuredFacts(source))
        {
            return RequiredStructuredLiterals(source);
        }

        var facts = new List<string>();
        const RegexOptions options =
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant
                | RegexOptions.NonBacktracking;

        foreach (Match match in Regex.Matches(
                     source,
                     "[«\"“](?<value>[^»\"”\\r\\n]{1,256})[»\"”]",
                     options))
        {
            Add(match.Groups["value"].Value);
        }

        foreach (Match match in Regex.Matches(
                     source,
                     @"(?:^|[^\p{L}\p{N}_])(?<value>\d+(?:[.,:]\d+)*(?:\s*[%°])?)",
                     options))
        {
            Add(match.Groups["value"].Value);
        }

        Match application = Regex.Match(
            source,
            @"^\s*Listo,\s+(?:abrí|enfoqué)\s+(?<value>[^.!?\r\n]{1,120})[.!?]\s*$",
            options);
        if (application.Success)
        {
            Add(application.Groups["value"].Value);
        }

        foreach (string pattern in new[]
                 {
                     @"\b(?:fecha local es|local date is)\s+(?<value>.+?)(?:\s+(?:y la hora local es|and the local time is)|[.!?\r\n]|$)",
                     @"\b(?:hora local es|local time is)\s+(?<value>[^.!?\r\n]{1,80})",
                 })
        {
            Match match = Regex.Match(source, pattern, options);
            if (match.Success)
            {
                Add(match.Groups["value"].Value);
            }
        }

        // The family-aware Core floors intentionally avoid operation IDs and
        // other internal vocabulary. Their person-facing subject is still a
        // verified fact: require the local model to preserve it instead of
        // accepting a vague "ya lo hice" or "no pude" response.
        Match familyFloor = Regex.Match(
            source,
            @"^\s*(?:Completé y verifiqué|No pude completar)\s+(?<value>[^.!?\r\n]{1,160})[.!?]?\s*$",
            options);
        if (familyFloor.Success)
        {
            Add(familyFloor.Groups["value"].Value);
        }

        return facts
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Take(32)
            .ToArray();

        void Add(string value)
        {
            string trimmed = value.Trim().TrimEnd('.', ',', ';', ':');
            if (trimmed.Length > 0)
            {
                facts.Add(trimmed);
            }
        }
    }

    private static bool PreservesRequiredFacts(string source, string result)
    {
        IReadOnlyList<string> fragments = RequiredFactualFragments(source);
        if (fragments.Count == 0)
        {
            return true;
        }

        string foldedResult = FoldForPolicy(result);
        foreach (string fragment in fragments)
        {
            int separator = fragment.IndexOf(':');
            string label = FoldForPolicy(fragment[..separator].Trim());
            string value = FoldForPolicy(fragment[(separator + 1)..].Trim());
            if (string.IsNullOrEmpty(label)
                || string.IsNullOrEmpty(value)
                || !foldedResult.Contains(label, StringComparison.Ordinal)
                || !foldedResult.Contains(value, StringComparison.Ordinal))
            {
                return false;
            }
        }

        return true;
    }

    private static bool PreservesRequiredLiteralFacts(string source, string result)
    {
        string foldedResult = FoldForPolicy(result);
        return RequiredLiteralFacts(source).All(fact =>
            foldedResult.Contains(FoldForPolicy(fact), StringComparison.Ordinal));
    }

    private static bool PreservesBaxyFirstPerson(string source, string result)
    {
        if (IsStructuredFacts(source))
        {
            return true;
        }

        string sourceFolded = FoldForPolicy(source);
        string resultFolded = FoldForPolicy(result);
        foreach ((string sourcePattern, string resultPattern) in FirstPersonActionPatterns)
        {
            if (Regex.IsMatch(
                    sourceFolded,
                    sourcePattern,
                    RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)
                && !Regex.IsMatch(
                    resultFolded,
                    resultPattern,
                    RegexOptions.CultureInvariant | RegexOptions.NonBacktracking))
            {
                return false;
            }
        }

        return true;
    }

    private static bool AddsGenericFollowUp(string result)
    {
        string folded = FoldForPolicy(result);
        return Regex.IsMatch(
            folded,
            @"\b(?:que quieres hacer ahora|que deseas hacer ahora|que necesitas ahora|necesitas algo mas|algo mas)\b",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    }

    private static bool StartsWithRequestImperative(string result)
    {
        string folded = FoldForPolicy(result);
        return Regex.IsMatch(
            folded,
            @"^\s*(?:(?:list|show|tell|open|create|set|mute|close|delete|send)\b|(?:lista|muestra)\s+(?:el|la|los|las|un|una)\b|(?:dime|abre|crea|pon|silencia|cierra|elimina|envia)\b)",
            RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    }

    private static bool ReversesSuccessfulResult(string source, string result)
    {
        if (LooksLikeFailure(source))
        {
            return false;
        }

        string resultFolded = FoldForPolicy(result);
        return resultFolded.Contains("no pude", StringComparison.Ordinal)
            || resultFolded.Contains("no puedo", StringComparison.Ordinal)
            || resultFolded.Contains("no se pudo", StringComparison.Ordinal);
    }

    private static bool ReversesFailedResult(string source, string result)
    {
        return LooksLikeFailure(source) && !LooksLikeFailure(result);
    }

    private static string[] RequiredStructuredLiterals(string source)
    {
        if (!TryReadJson(source, out JsonElement root))
        {
            return [];
        }

        var facts = new List<string>();
        if (root.TryGetProperty("steps", out JsonElement steps)
            && steps.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement step in steps.EnumerateArray())
            {
                if (step.GetString() is { Length: > 0 } text)
                {
                    facts.Add(text);
                }
            }
        }

        foreach (string key in new[] { "reason", "title" })
        {
            if (root.TryGetProperty(key, out JsonElement value)
                && value.GetString() is { Length: > 0 } text)
            {
                facts.Add(text);
            }
        }

        return facts.Take(20).ToArray();
    }

    private static bool TryReadJson(string source, out JsonElement root)
    {
        try
        {
            using JsonDocument document = JsonDocument.Parse(source);
            root = document.RootElement.Clone();
            return root.ValueKind == JsonValueKind.Object;
        }
        catch (JsonException)
        {
            root = default;
            return false;
        }
    }

    private static string FoldForPolicy(string value)
    {
        var builder = new StringBuilder(value.Length);
        foreach (char character in value.Normalize(NormalizationForm.FormD))
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character)
                != UnicodeCategory.NonSpacingMark)
            {
                builder.Append(char.ToLowerInvariant(character));
            }
        }

        return builder.ToString().Normalize(NormalizationForm.FormC);
    }

    private static readonly (string Source, string Result)[] FirstPersonActionPatterns =
    [
        (@"\babri\b", @"\b(?:abri|he abierto)\b"),
        (@"\benfoque\b", @"\b(?:enfoque|he enfocado)\b"),
        (@"\bcerre\b", @"\b(?:cerre|he cerrado)\b"),
        (@"\bejecute\b", @"\b(?:ejecute|he ejecutado)\b"),
        (@"\binicie\b", @"\b(?:inicie|he iniciado)\b"),
        (@"\bhice\b", @"\b(?:hice|he hecho)\b"),
        (@"\bpuse\b", @"\b(?:puse|he puesto)\b"),
        (@"\bajuste\b", @"\b(?:ajuste|he ajustado)\b"),
        (@"\bcontrole\b", @"\b(?:controle|he controlado)\b"),
        (@"\bcopie\b", @"\b(?:copie|he copiado)\b"),
        (@"\bpegue\b", @"\b(?:pegue|he pegado)\b"),
        (@"\bresolvi\b", @"\b(?:resolvi|he resuelto)\b"),
        (@"\bcambie\b", @"\b(?:cambie|he cambiado)\b"),
        (@"\bactive\b", @"\b(?:active|he activado)\b"),
        (@"\bdesactive\b", @"\b(?:desactive|he desactivado)\b"),
        (@"\bseleccione\b", @"\b(?:seleccione|he seleccionado)\b"),
        (@"\benvie\b", @"\b(?:envie|he enviado)\b"),
        (@"\bconecte\b", @"\b(?:conecte|he conectado)\b"),
        (@"\bforce\b", @"\b(?:force|he forzado)\b"),
        (@"\badelante\b", @"\b(?:adelante|he adelantado)\b"),
        (@"\bretrocedi\b", @"\b(?:retrocedi|he retrocedido)\b"),
        (@"\bsilencie\b", @"\b(?:silencie|he silenciado)\b"),
        (@"\breactive\b", @"\b(?:reactive|he reactivado)\b"),
        (@"\bpresione\b", @"\b(?:presione|he presionado)\b"),
        (@"\bescribi\b", @"\b(?:escribi|he escrito)\b"),
        (@"\bguarde\b", @"\b(?:guarde|he guardado)\b"),
        (@"\bcree\b", @"\b(?:cree|he creado)\b"),
        (@"\belimine\b", @"\b(?:elimine|he eliminado)\b"),
        (@"\bverifique\b", @"\b(?:verifique|he verificado)\b"),
    ];

    private static bool PreservesChoicePair(
        string source,
        string result,
        string first,
        string second)
    {
        bool sourceHasPair = source.Contains(first, StringComparison.OrdinalIgnoreCase)
            && source.Contains(second, StringComparison.OrdinalIgnoreCase);
        return !sourceHasPair
            || result.Contains(first, StringComparison.OrdinalIgnoreCase)
                && result.Contains(second, StringComparison.OrdinalIgnoreCase);
    }
}
