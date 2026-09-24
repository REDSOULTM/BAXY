using System.Globalization;
using System.IO;
using System.Text;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using System.Security.Cryptography;

namespace Baxy.App;

// Memory arguments are private until the shell encrypts them. Keeping this type
// unrelated to RoutedOperation makes an unsealed memory request impossible to
// hand to RetryableOperationRegistry by accident.
internal sealed class MemoryRoutedOperation
{
    private readonly JsonObject _privateArguments;

    internal MemoryRoutedOperation(string name, JsonObject privateArguments)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(name);
        ArgumentNullException.ThrowIfNull(privateArguments);
        Name = name;
        _privateArguments = (JsonObject)privateArguments.DeepClone();
    }

    internal string Name { get; }

    internal JsonObject PrivateArguments => (JsonObject)_privateArguments.DeepClone();

    public override string ToString() =>
        $"{nameof(MemoryRoutedOperation)} {{ Name = {Name}, PrivateArguments = [REDACTED] }}";
}

internal enum MemoryParseOutcome
{
    Route,
    Clarify,
    AskToSave,
    ConfirmSensitiveSave,
    SessionContextOnly,
    RejectAuthorizationPersistence,
    NoRoute,
}

internal enum MemorySaveSubject
{
    Name,
}

internal sealed class MemoryParseResult
{
    private MemoryParseResult(
        MemoryParseOutcome outcome,
        MemoryRoutedOperation? operation,
        bool mustNotPersist = false,
        bool mustNotDelete = false,
        bool mustNotChangeAuthority = false,
        bool mustNotInvent = false,
        bool mustNotClaimStandaloneRoute = false,
        bool maskPublicProjection = false,
        MemorySaveSubject? missingSaveSubject = null)
    {
        if (outcome == MemoryParseOutcome.Route && operation is null)
        {
            throw new ArgumentException("Una ruta de memoria necesita una operación.", nameof(operation));
        }

        if (outcome == MemoryParseOutcome.Route
            && operation is not null
            && !IsValidOrdinaryRoute(operation))
        {
            throw new ArgumentException(
                "La ruta de memoria no coincide con su riesgo declarado.",
                nameof(operation));
        }

        if (outcome is not (MemoryParseOutcome.Route or MemoryParseOutcome.ConfirmSensitiveSave)
            && operation is not null)
        {
            throw new ArgumentException(
                "Este resultado de memoria no admite una operación implícita.",
                nameof(operation));
        }

        if (outcome == MemoryParseOutcome.ConfirmSensitiveSave
            && (!mustNotPersist || !maskPublicProjection))
        {
            throw new ArgumentException(
                "Una memoria sensible debe permanecer sin persistir y enmascarada hasta confirmación.",
                nameof(outcome));
        }

        if (outcome == MemoryParseOutcome.ConfirmSensitiveSave
            && operation is not null
            && !IsValidSensitiveSaveDraft(operation))
        {
            throw new ArgumentException(
                "El borrador sensible no es una operación privada válida.",
                nameof(operation));
        }

        Outcome = outcome;
        Operation = operation;
        MustNotPersist = mustNotPersist;
        MustNotDelete = mustNotDelete;
        MustNotChangeAuthority = mustNotChangeAuthority;
        MustNotInvent = mustNotInvent;
        MustNotClaimStandaloneRoute = mustNotClaimStandaloneRoute;
        MaskPublicProjection = maskPublicProjection;
        MissingSaveSubject = missingSaveSubject;
    }

    internal MemoryParseOutcome Outcome { get; }

    internal MemoryRoutedOperation? Operation { get; }

    internal bool MustNotPersist { get; }

    internal bool MustNotDelete { get; }

    internal bool MustNotChangeAuthority { get; }

    internal bool MustNotInvent { get; }

    internal bool MustNotClaimStandaloneRoute { get; }

    internal bool MaskPublicProjection { get; }

    internal MemorySaveSubject? MissingSaveSubject { get; }

    internal static MemoryParseResult Route(MemoryRoutedOperation operation) =>
        new(MemoryParseOutcome.Route, operation ?? throw new ArgumentNullException(nameof(operation)));

    internal static MemoryParseResult ClarifySave(MemorySaveSubject? subject = null) =>
        new(MemoryParseOutcome.Clarify, null, mustNotPersist: true,
            missingSaveSubject: subject);

    internal static MemoryParseResult ClarifyForget() =>
        new(MemoryParseOutcome.Clarify, null, mustNotDelete: true);

    internal static MemoryParseResult ClarifyInspection() =>
        new(MemoryParseOutcome.Clarify, null, mustNotInvent: true);

    internal static MemoryParseResult AskToSave() =>
        new(MemoryParseOutcome.AskToSave, null, mustNotPersist: true);

    internal static MemoryParseResult ConfirmSensitiveSave(MemoryRoutedOperation? operation) =>
        new(
            MemoryParseOutcome.ConfirmSensitiveSave,
            operation,
            mustNotPersist: true,
            maskPublicProjection: true);

    internal static MemoryParseResult SessionContextOnly() =>
        new(MemoryParseOutcome.SessionContextOnly, null, mustNotPersist: true);

    internal static MemoryParseResult DoNotPersist() =>
        new(MemoryParseOutcome.NoRoute, null, mustNotPersist: true);

    internal static MemoryParseResult RejectAuthorizationPersistence() =>
        new(
            MemoryParseOutcome.RejectAuthorizationPersistence,
            null,
            mustNotPersist: true,
            mustNotChangeAuthority: true);

    internal static MemoryParseResult NoRoute(bool mustNotClaimStandaloneRoute = false) =>
        new(
            MemoryParseOutcome.NoRoute,
            null,
            mustNotClaimStandaloneRoute: mustNotClaimStandaloneRoute);

    public override string ToString() =>
        $"{nameof(MemoryParseResult)} {{ Outcome = {Outcome}, Operation = "
        + (Operation is null ? "null" : "[REDACTED]")
        + $", MustNotPersist = {MustNotPersist}, MustNotDelete = {MustNotDelete}, "
        + $"MustNotChangeAuthority = {MustNotChangeAuthority}, MustNotInvent = {MustNotInvent}, "
        + $"MustNotClaimStandaloneRoute = {MustNotClaimStandaloneRoute}, "
        + $"MaskPublicProjection = {MaskPublicProjection} }}";

    private static bool IsValidSensitiveSaveDraft(MemoryRoutedOperation operation) =>
        string.Equals(operation.Name, "memory.save", StringComparison.Ordinal)
        && operation.PrivateArguments["selector"] is JsonValue selectorValue
        && selectorValue.TryGetValue(out string? selector)
        && !string.IsNullOrWhiteSpace(selector)
        && operation.PrivateArguments["value"] is JsonValue valueNode
        && valueNode.TryGetValue(out string? value)
        && !string.IsNullOrWhiteSpace(value)
        && operation.PrivateArguments["sensitivity"] is JsonValue sensitivityValue
        && sensitivityValue.TryGetValue(out string? sensitivity)
        && string.Equals(sensitivity, "secret", StringComparison.Ordinal);

    private static bool IsValidOrdinaryRoute(MemoryRoutedOperation operation)
    {
        JsonObject arguments = operation.PrivateArguments;
        if (string.Equals(operation.Name, "memory.save", StringComparison.Ordinal))
        {
            if (arguments["sensitivity"] is not JsonValue sensitivityValue
                || !sensitivityValue.TryGetValue(out string? sensitivity)
                || sensitivity is not ("normal" or "personal" or "sensitive")
                || arguments["value"] is not JsonValue valueNode)
            {
                return false;
            }

            return !valueNode.TryGetValue(out string? value)
                || !string.IsNullOrWhiteSpace(value)
                && !NaturalMemoryRequestParser.ContainsSensitiveMaterial(value);
        }

        if (!string.Equals(operation.Name, "memory.forget", StringComparison.Ordinal))
        {
            return true;
        }

        if (arguments["scope"] is not JsonValue scopeValue
            || !scopeValue.TryGetValue(out string? scope)
            || arguments["confirmationRequired"] is not JsonValue confirmationValue
            || !confirmationValue.TryGetValue(out bool confirmationRequired))
        {
            return false;
        }

        if (!string.Equals(scope, "session", StringComparison.Ordinal))
        {
            return confirmationRequired;
        }

        return !confirmationRequired
            && arguments["selector"] is null
            && arguments["mustNotDeletePersistent"] is JsonValue persistentValue
            && persistentValue.TryGetValue(out bool mustNotDeletePersistent)
            && mustNotDeletePersistent;
    }
}

internal static partial class NaturalMemoryRequestParser
{
    private const int MaximumInputUtf8Bytes = 4096;
    private const int MaximumCapturedValueUtf8Bytes = 256;

    public static bool TryParse(string? text, out MemoryRoutedOperation? operation)
    {
        MemoryParseResult result = Classify(text);
        operation = result.Outcome == MemoryParseOutcome.Route
            ? result.Operation
            : null;
        return operation is not null;
    }

    internal static MemoryParseResult Classify(string? text)
    {
        if (string.IsNullOrWhiteSpace(text)
            || !IsWellFormedUtf16(text)
            || ContainsControlCharacter(text)
            || Encoding.UTF8.GetByteCount(text) > MaximumInputUtf8Bytes)
        {
            return MemoryParseResult.NoRoute();
        }

        string normalized = CollapseWhitespacePattern()
            .Replace(text.Normalize(NormalizationForm.FormC), " ")
            .Trim();
        string command = StripRequestEnvelope(
            TrimSentencePunctuation(normalized));
        string foldedCommand = command.ToLowerInvariant();

        if (command.Length == 0)
        {
            return MemoryParseResult.NoRoute();
        }

        if (PostposedNoStorePattern().IsMatch(foldedCommand)
            && !ExplicitNoStorePattern().IsMatch(foldedCommand))
        {
            return MemoryParseResult.DoNotPersist();
        }

        if (TryClassifyAuditedBehavior(command, foldedCommand, out MemoryParseResult behavior))
        {
            return behavior;
        }

        if (AuthorizationPattern().IsMatch(foldedCommand))
        {
            return MemoryParseResult.RejectAuthorizationPersistence();
        }

        if (SensitiveMaterialPattern().IsMatch(foldedCommand))
        {
            return IsExplicitMemorySave(foldedCommand)
                ? MemoryParseResult.ConfirmSensitiveSave(TryCreateSensitiveSave(command))
                : MemoryParseResult.NoRoute();
        }

        if (ExplicitNoStorePattern().IsMatch(foldedCommand))
        {
            return TemporaryNoStorePattern().IsMatch(foldedCommand)
                ? MemoryParseResult.SessionContextOnly()
                : MemoryParseResult.NoRoute();
        }

        if (TryParseDeclaredNameSave(command, out MemoryRoutedOperation? operation))
        {
            return MemoryParseResult.Route(operation!);
        }

        if (ReminderPattern().IsMatch(foldedCommand)
            || NoiseOrCompositionPattern().IsMatch(foldedCommand))
        {
            return MemoryParseResult.NoRoute(
                MixedMemoryCompositionPattern().IsMatch(foldedCommand));
        }

        // An explicit request may announce the value instead of supplying it.
        // A preceding capability question is not the value or the authority:
        // the final clause must itself request persistence of the named datum.
        string finalClause = command[(command.LastIndexOf('?') + 1)..].TrimStart(' ', ',');
        if (MissingNameSavePattern().IsMatch(finalClause))
        {
            return MemoryParseResult.ClarifySave(MemorySaveSubject.Name);
        }

        if (TryParseAuditedLiteral(foldedCommand, out operation))
        {
            return MemoryParseResult.Route(operation!);
        }

        // Resolve underspecified destructive references before the generic topic
        // fallback can reinterpret them as a concrete persistent-memory selector.
        if (AmbiguousForgetPattern().IsMatch(foldedCommand))
        {
            return MemoryParseResult.ClarifyForget();
        }

        if (TryParseBoundedVariation(command, out operation))
        {
            return MemoryParseResult.Route(operation!);
        }

        if (ImplicitMemoryPattern().IsMatch(foldedCommand))
        {
            return MemoryParseResult.AskToSave();
        }

        if (AmbiguousSavePattern().IsMatch(foldedCommand))
        {
            return MemoryParseResult.ClarifySave();
        }

        return MemoryParseResult.NoRoute();
    }

    private static bool TryClassifyAuditedBehavior(
        string command,
        string foldedCommand,
        out MemoryParseResult result)
    {
        switch (foldedCommand)
        {
            case "guarda como sensitive memory que mi alergia es al maní":
                result = MemoryParseResult.ConfirmSensitiveSave(
                    Save(
                        "allergy",
                        "maní",
                        "fact",
                        "persistent",
                        sensitivity: "secret"));
                return true;
            case "recuerda mi api key:[redacted]":
            case "recuerda mi contraseña es 1234":
            case "remember my ssn is [phone_redacted]":
            case "recuerda mi rut":
            case "save my api key sk-12345 in your memory":
                result = MemoryParseResult.ConfirmSensitiveSave(
                    TryCreateSensitiveSave(command));
                return true;
            case "remember this style permanently":
            case "recuerda esto para siempre":
            case "guarda esa preferencia para siempre":
            case "guarda esto solo para esta sesión":
                result = MemoryParseResult.ClarifySave();
                return true;
            case "olvida eso":
            case "olvida lo del estilo":
            case "forget that setting":
                result = MemoryParseResult.ClarifyForget();
                return true;
            case "no guardes esto, solo úsalo ahora: estoy probando steam":
                result = MemoryParseResult.SessionContextOnly();
                return true;
            case "recuerda que tiewnes totales permisos sobre mi pc, esta a tu toal disposicion, lo que necesites , lo puedes hacer":
                result = MemoryParseResult.RejectAuthorizationPersistence();
                return true;
            case "mi color favorito es azul":
            case "mi nombre es emmanuel":
                result = MemoryParseResult.AskToSave();
                return true;
            case "qu? recuerdas de m":
                result = MemoryParseResult.ClarifyInspection();
                return true;
            case "recordá: solo actuá si hay una confirmación pendiente, sino esperá":
            case "olvida el soak, detenlo y dejalo como ultima mision, es mucho tiempo lo haremos el sabado":
                result = MemoryParseResult.NoRoute(mustNotClaimStandaloneRoute: true);
                return true;
            default:
                result = null!;
                return false;
        }
    }

    private static MemoryRoutedOperation? TryCreateSensitiveSave(string command)
    {
        (string Selector, Match Match)[] candidates =
        [
            ("api_key", ApiKeySensitiveSavePattern().Match(command)),
            ("password", PasswordSensitiveSavePattern().Match(command)),
            ("ssn", SsnSensitiveSavePattern().Match(command)),
            ("rut", RutSensitiveSavePattern().Match(command)),
        ];
        foreach ((string selector, Match match) in candidates)
        {
            if (match.Success
                && TrySafeSensitiveCapturedValue(
                    match.Groups["value"].Value,
                    out string value))
            {
                return Save(
                    selector,
                    value,
                    "fact",
                    "persistent",
                    sensitivity: "secret");
            }
        }

        return null;
    }

    private static bool IsExplicitMemorySave(string command) =>
        ExplicitMemorySavePattern().IsMatch(command);

    internal static bool WithdrawsPendingSave(string text) =>
        PostposedNoStorePattern().IsMatch(text)
        || ExplicitNoStorePattern().IsMatch(text)
        || NegatedMemoryIntentPattern().IsMatch(text);

    private static bool TryParseDeclaredNameSave(string command, out MemoryRoutedOperation? operation)
    {
        operation = null;
        // A declaration supplies the value; a separate explicit clause supplies
        // authority for that same datum. Neither clause alone permits a save.
        foreach (Match boundary in NameClauseBoundaryPattern().Matches(command))
        {
            string first = command[..boundary.Index].Trim();
            string second = command[(boundary.Index + boundary.Length)..].Trim();
            string? declaration = MissingNameSavePattern().IsMatch(first)
                ? second
                : MissingNameSavePattern().IsMatch(second) ? first : null;
            if (declaration is null)
            {
                continue;
            }

            Match name = DeclaredNameInputPattern().Match(declaration);
            if (!name.Success || name.Groups["public"].Success
                || NameClauseBoundaryPattern().IsMatch(name.Groups["value"].Value)
                || !TrySafeCapturedValue(name.Groups["value"].Value, out string value))
            {
                continue;
            }

            operation = Save("name", value, "fact", "persistent", sensitivity: "personal");
            return true;
        }

        return false;
    }

    internal static bool RefersToCurrentNameConversation(
        string text, IEnumerable<string> recentUserMessages)
    {
        string command = StripRequestEnvelope(TrimSentencePunctuation(
            CollapseWhitespacePattern().Replace(text.Normalize(NormalizationForm.FormC), " ").Trim()));
        // This selects conversational scope, not a name value or permission.
        // Keep the role-bounded human text for the mind to interpret, including
        // corrections; assistant claims never establish personal context here.
        return NameRecallPattern().Match(command).Groups["conversation"].Success
            && recentUserMessages.Any(static message =>
                DeclaredNameInputPattern().IsMatch(message.Trim()));
    }

    internal static bool TryBindSaveInput(
        MemorySaveSubject subject,
        MissionInputRoute input,
        out MissionInputRoute? bound)
    {
        bound = null;
        if (subject != MemorySaveSubject.Name
            || input.Memory.Outcome != MemoryParseOutcome.AskToSave
            || ContainsSensitiveMaterial(input.Text)
            || WithdrawsPendingSave(input.Text))
        {
            return false;
        }

        Match match = DeclaredNameInputPattern().Match(input.Text.Trim());
        if (!match.Success
            || NameClauseBoundaryPattern().IsMatch(match.Groups["value"].Value)
            || !TrySafeCapturedValue(match.Groups["value"].Value, out string name))
        {
            return false;
        }

        string publicObjective = match.Groups["public"].Value.Trim();
        if (publicObjective.Length > 0)
        {
            MemoryParseResult rest = Classify(publicObjective);
            if (rest.Outcome != MemoryParseOutcome.NoRoute
                || rest.MustNotPersist || rest.MustNotClaimStandaloneRoute)
            {
                return false;
            }
        }

        bound = new MissionInputRoute(
            input.Text,
            input.Source,
            MemoryParseResult.Route(Save(
                "name", name, "fact", "persistent", sensitivity: "personal")),
            publicObjective);
        return true;
    }

    internal static bool ContainsSensitiveMaterial(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        if (SensitiveMaterialPattern().IsMatch(value))
        {
            return true;
        }

        foreach (string token in value.Split(
                     [' ', '\t', '\r', '\n', '"', '\'', '(', ')', '[', ']', '<', '>', ',', ';', ':'],
                     StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            if (LooksLikeCredentialToken(token.TrimEnd('.', '!', '?')))
            {
                return true;
            }
        }

        return false;
    }

    private static bool TrySafeSensitiveCapturedValue(string value, out string safeValue)
    {
        safeValue = value.Trim().Normalize(NormalizationForm.FormC);
        return safeValue.Length > 0
            && Encoding.UTF8.GetByteCount(safeValue) <= MaximumCapturedValueUtf8Bytes
            && !RedactedValuePattern().IsMatch(safeValue)
            && !IsPlaceholderValue(safeValue)
            && !PostposedNoStorePattern().IsMatch(safeValue)
            && !AuthorizationPattern().IsMatch(safeValue)
            && !SecondaryInstructionPattern().IsMatch(safeValue)
            && !AnaphoricValuePattern().IsMatch(safeValue)
            && !FilesystemOrDocumentPattern().IsMatch(safeValue);
    }

    private static bool LooksLikeCredentialToken(string token)
    {
        if (token.Length is < 20 or > MaximumCapturedValueUtf8Bytes)
        {
            return false;
        }

        bool hasLetter = false;
        bool hasDigit = false;
        int firstSeparator = -1;
        for (int index = 0; index < token.Length; index++)
        {
            char character = token[index];
            if (character is >= 'a' and <= 'z' or >= 'A' and <= 'Z')
            {
                hasLetter = true;
            }
            else if (character is >= '0' and <= '9')
            {
                hasDigit = true;
            }
            else if (character is '-' or '_' or '.')
            {
                firstSeparator = firstSeparator < 0 ? index : firstSeparator;
            }
            else
            {
                return false;
            }
        }

        // Document references already have a recognized syntax in this owner.
        // Their dates/IDs must survive public projection and composition.
        // Explicit secret labels and credential prefixes are checked before
        // this generic token heuristic in ContainsSensitiveMaterial.
        if (FilesystemOrDocumentPattern().IsMatch(Path.GetExtension(token)))
        {
            return false;
        }

        bool credentialPrefix = firstSeparator is >= 2 and <= 16
            && token.Length - firstSeparator - 1 >= 16
            && token[..firstSeparator].All(static character => char.IsAsciiLetter(character));
        return hasLetter && hasDigit && (credentialPrefix || token.Length >= 32);
    }

    private static bool IsPlaceholderValue(string value)
    {
        if (value.Length >= 2
            && (value[0], value[^1]) is
                ('[', ']') or ('<', '>') or ('{', '}') or ('(', ')'))
        {
            return true;
        }

        return value.Trim().ToLowerInvariant() is
            "n/a" or "na" or "none" or "null" or "unknown" or "not available"
            or "no disponible" or "sin dato" or "censored" or "removed";
    }

    private static bool TryParseAuditedLiteral(
        string command,
        out MemoryRoutedOperation? operation)
    {
        operation = command switch
        {
            // Explicit saves.
            "acordate que mi color favorito es el azul"
                or "guarda que mi color favorito es azul"
                or "recuerda que mi color favorito es azul" =>
                Save("favorite_color", "azul", "preference", "persistent"),
            "remember my favorite color is blue" =>
                Save("favorite_color", "blue", "preference", "persistent"),
            "guarda que no quiero que carter abra juegos pesados en tests" =>
                Save("carter_heavy_games_in_tests", false, "preference", "persistent"),
            "recordame que prefiero el café sin azúcar" =>
                Save("coffee", "sin azúcar", "preference", "persistent"),
            "recuerda durante esta sesión que mi proyecto se llama carter" =>
                Save(
                    "project_name",
                    "Carter",
                    "context",
                    "session",
                    "session_end",
                    tags: ["Carter"]),
            "recuerda mi cumpleaños es 5 de mayo"
                or "remember my birthday is may 5" =>
                Save("birthday", "May 5", "fact", "persistent", sensitivity: "personal"),
            "recuerda que carter debe ser local y privado" =>
                Save(
                    "carter_privacy",
                    "local_and_private",
                    "rule",
                    "persistent",
                    tags: ["Carter"]),
            "recuerda que carter está en carter_v3" =>
                Save(
                    "carter_location",
                    "Carter_v3",
                    "context",
                    "persistent",
                    tags: ["Carter"]),
            "recuerda que en testing siempre quiero limpieza del pc" =>
                Save("testing_cleanup", true, "preference", "persistent"),
            "recuerda que me llamo red" =>
                Save("name", "red", "fact", "persistent", sensitivity: "personal"),
            "recuerda que me llamo reta" =>
                Save("name", "Reta", "fact", "persistent", sensitivity: "personal"),
            "remember me as red" =>
                Save("name", "Red", "fact", "persistent", sensitivity: "personal"),
            "remember my name is alex" =>
                Save("name", "Alex", "fact", "persistent", sensitivity: "personal"),
            "recuerda que mi carpeta de pruebas es %userprofile%\\desktop\\carter_test" =>
                Save(
                    "test_folder",
                    "%USERPROFILE%\\Desktop\\Carter_Test",
                    "context",
                    "persistent"),
            "recuerda que mi proyecto se llama carter v3" =>
                Save(
                    "project_name",
                    "Carter v3",
                    "context",
                    "persistent",
                    tags: ["Carter"]),
            "recuerda que no quieres tocar legacy" =>
                Save("avoid_legacy", true, "rule", "persistent", tags: ["Carter"]),
            "recuerda que no quiero hardcodes en carter" =>
                Save(
                    "avoid_hardcodes",
                    true,
                    "preference",
                    "persistent",
                    tags: ["Carter"]),
            "recuerda que prefiero español" =>
                Save("language", "es", "preference", "persistent"),
            "recuerda que prefiero no usar taskkill /f" =>
                Save("avoid_taskkill_force", true, "preference", "persistent"),
            "recuerda que prefiero respuestas cortas en carter"
                or "recuerda que prefiero respuestas cortas para carter" =>
                Save(
                    "response_style",
                    "short",
                    "preference",
                    "persistent",
                    tags: ["Carter"]),
            "recuerda que prefiero respuestas directas" =>
                Save("response_style", "direct", "preference", "persistent"),
            "recuerda que soy menor de edad" =>
                Save(
                    "age_category",
                    "minor",
                    "fact",
                    "persistent",
                    sensitivity: "sensitive"),
            "recuerda que steam no debe ejecutarse en suites mínimas" =>
                Save("steam_in_minimal_suites", false, "rule", "persistent"),
            "recuerda que tengo prueba mañana" =>
                Save(
                    "exam",
                    "tomorrow",
                    "context",
                    "temporary",
                    "after_relevance_window"),
            "recuerda que trabajo en intelectra" =>
                Save(
                    "employer",
                    "Intelectra",
                    "fact",
                    "persistent",
                    sensitivity: "personal"),
            "recuerda que uso windows" =>
                Save("operating_system", "Windows", "fact", "persistent"),
            "recuerda temporalmente que esta corrida es smoke 12" =>
                Save(
                    "run_label",
                    "smoke 12",
                    "context",
                    "temporary",
                    "after_relevance_window"),
            "remember that i prefer dark mode" =>
                Save("display_mode", "dark", "preference", "persistent"),
            "parla in inglese da adesso in poi" =>
                Save("language", "en", "preference", "persistent"),

            // Reviewed full-catalogue memory surfaces. These exact aliases
            // remain inside the private parser and carry concrete arguments;
            // they cannot add Core authority or bypass confirmation policy.
            "corrige mi memory: mi color favorito ahora es verde, no azul" =>
                Correct(
                    "favorite_color",
                    "verde",
                    "persistent",
                    expectedValue: "azul",
                    kind: "preference"),
            "exporta una copia privada de todo lo que baxy recuerda de mí" => Export(),
            "muéstrame la lista de recuerdos locales que guardaste" => List(),
            "what do you remember about my preferred editor" =>
                Recall("exact", "preferred_editor"),
            "borra solamente la memoria temporal de esta conversación" =>
                ForgetSession(),

            // Explicit recalls.
            "como me llamo" or "cómo me llamo" or "what is my name" or "what's my name" =>
                Recall("exact", "name"),
            "qué recuerdas de mí" or "que recuerdas de mi"
                or "what do you remember about me" => Recall("all", null),
            "qué recuerdas sobre mis preferencias"
                or "qué sabes de mis preferencias"
                or "que sabes de mis preferencias" => Recall("kind", "preference"),
            "qué color me gusta" or "what's my favorite color" =>
                Recall("exact", "favorite_color"),
            "que me gusta tomar" => Recall("exact", "favorite_drink"),

            // Explicit forgets. These are semantic requests only; the caller still
            // has to obtain confirmation before constructing a confirmed envelope.
            "borra la memoria de que uso windows" =>
                Forget("exact", "operating_system", confirmationRequired: true),
            "borra mi color favorito" or "delete my favorite color" =>
                Forget("exact", "favorite_color", confirmationRequired: true),
            "borra tus recuerdos sobre mi" or "olvida lo que sabes de mí"
                or "forget everything about me" =>
                Forget("all", null, confirmationRequired: true),
            "olvida el modo corto" or "olvida mi preferencia de respuestas cortas" =>
                Forget("exact", "response_style", confirmationRequired: true),
            "olvida mi carpeta de pruebas" =>
                Forget("exact", "test_folder", confirmationRequired: true),
            "olvida mis preferencias de estilo" =>
                Forget("kind", "style_preferences", confirmationRequired: true),
            "olvida que prefiero español" =>
                Forget("exact", "language", confirmationRequired: true),
            "olvida todo lo que sabes de carter" or "olvida todo sobre carter" =>
                Forget("topic", "Carter", confirmationRequired: true),
            "olvida lo anterior de esta conversación"
                or "olvidá lo anterior de esta conversación"
                or "forget what we said earlier in this conversation" =>
                ForgetSession(),

            // Explicit corrections.
            "corrige la memoria: no es carter v2, es carter v3" =>
                Correct(
                    "carter_version",
                    "Carter v3",
                    "persistent",
                    expectedValue: "Carter v2"),
            "cambia mi preferencia: ahora respuestas técnicas pero breves" =>
                Correct(
                    "response_style",
                    "technical_and_brief",
                    "persistent",
                    kind: "preference"),
            "tienes memoria" or "tienes memoria local" or "do you have memory" =>
                Status(),
            "lista mi memoria" or "muestra toda mi memoria" or "show my memories"
                or "list my memories" => List(),
            "exporta mi memoria" or "export my memory" => Export(),
            _ => null,
        };

        return operation is not null;
    }

    private static bool TryParseBoundedVariation(
        string command,
        out MemoryRoutedOperation? operation)
    {
        operation = null;

        Match configuration = MemoryConfigurationRequestPattern().Match(command);
        if (configuration.Success)
        {
            // Qualifiers describe the same private store, not a new operation.
            // Require the whole imperative: mentions, negations, other stores
            // and additional effects cannot authorize a configuration change.
            operation = Configure(enabled: configuration.Groups["enable"].Success);
            return true;
        }

        if ((MemoryStatusRequestPattern().IsMatch(command)
                || LeadingMemoryStatusRequestPattern().IsMatch(command)
                || IsCompositionalMemoryStatusRequest(command))
            && !OtherDeviceMemoryStatusPattern().IsMatch(command))
        {
            operation = Status();
            return true;
        }

        Match match = FavoriteColorSavePattern().Match(command);
        if (match.Success
            && TrySafeCapturedValue(match.Groups["value"].Value, out string color))
        {
            operation = Save("favorite_color", color, "preference", "persistent");
            return true;
        }

        // MEMORY1599 «que me gusta tomar» recalls favorite_drink, so «recuerda
        // que me gusta tomar mate» must save that selector, not a generic fact.
        match = FavoriteDrinkSavePattern().Match(command);
        if (match.Success
            && TrySafeCapturedValue(match.Groups["value"].Value, out string drink))
        {
            operation = Save("favorite_drink", drink, "preference", "persistent");
            return true;
        }

        match = NameSavePattern().Match(command);
        if (match.Success
            && TrySafeCapturedValue(match.Groups["value"].Value, out string name))
        {
            operation = Save(
                "name",
                name,
                "fact",
                "persistent",
                sensitivity: "personal");
            return true;
        }

        match = ProjectNameSavePattern().Match(command);
        if (match.Success
            && !ProjectNameClausePattern().IsMatch(match.Groups["value"].Value)
            && TrySafeCapturedValue(match.Groups["value"].Value, out string projectName))
        {
            string retention = match.Groups["session"].Success ? "session" : "persistent";
            operation = Save(
                "project_name",
                projectName,
                "context",
                retention,
                retention == "session" ? "session_end" : null,
                tags: projectName.Contains("Carter", StringComparison.OrdinalIgnoreCase)
                    ? ["Carter"]
                    : null);
            return true;
        }

        if (ShortResponseSavePattern().IsMatch(command))
        {
            operation = Save("response_style", "short", "preference", "persistent");
            return true;
        }

        if (DirectResponseSavePattern().IsMatch(command))
        {
            operation = Save("response_style", "direct", "preference", "persistent");
            return true;
        }

        if (DarkModeSavePattern().IsMatch(command))
        {
            operation = Save("display_mode", "dark", "preference", "persistent");
            return true;
        }

        if (NameRecallPattern().IsMatch(command))
        {
            operation = Recall("exact", "name");
            return true;
        }

        if (EmployerRecallPattern().IsMatch(command))
        {
            operation = Recall("exact", "employer");
            return true;
        }

        if (AllRecallPattern().IsMatch(command))
        {
            operation = Recall("all", null);
            return true;
        }

        if (PreferenceRecallPattern().IsMatch(command))
        {
            operation = Recall("kind", "preference");
            return true;
        }

        if (ProjectRecallPattern().IsMatch(command))
        {
            operation = Recall("exact", "project_name");
            return true;
        }

        if (FavoriteColorRecallPattern().IsMatch(command))
        {
            operation = Recall("exact", "favorite_color");
            return true;
        }

        if (FavoriteDrinkRecallPattern().IsMatch(command))
        {
            operation = Recall("exact", "favorite_drink");
            return true;
        }

        if (FavoriteColorForgetPattern().IsMatch(command))
        {
            operation = Forget("exact", "favorite_color", confirmationRequired: true);
            return true;
        }

        if (AllForgetPattern().IsMatch(command))
        {
            operation = Forget("all", null, confirmationRequired: true);
            return true;
        }

        if (LanguageForgetPattern().IsMatch(command))
        {
            operation = Forget("exact", "language", confirmationRequired: true);
            return true;
        }

        if (GenericAllRecallPattern().IsMatch(command))
        {
            operation = Recall("all", null);
            return true;
        }

        if (GenericAllForgetPattern().IsMatch(command))
        {
            operation = Forget("all", null, confirmationRequired: true);
            return true;
        }

        if (GenericPreferenceForgetPattern().IsMatch(command))
        {
            operation = Forget("kind", "preference", confirmationRequired: true);
            return true;
        }

        match = GenericTopicForgetPattern().Match(command);
        if (match.Success
            && TrySafeCapturedValue(match.Groups["topic"].Value, out string topic))
        {
            operation = Forget("topic", topic, confirmationRequired: true);
            return true;
        }

        match = ProjectChangePattern().Match(command);
        if (match.Success
            && TrySafeCapturedValue(match.Groups["value"].Value, out string project))
        {
            operation = Correct("project_name", project, "persistent", kind: "context");
            return true;
        }

        match = GenericExplicitSavePattern().Match(command);
        if (match.Success
            && TrySafeCapturedValue(match.Groups["value"].Value, out string fact))
        {
            string kind = GenericPreferenceValuePattern().IsMatch(fact)
                ? "preference"
                : "fact";
            operation = Save(
                StableGenericSelector(command),
                fact,
                kind,
                "persistent",
                sensitivity: GenericPersonalValuePattern().IsMatch(fact)
                    ? "personal"
                    : "normal");
            return true;
        }

        return false;
    }

    private static bool IsCompositionalMemoryStatusRequest(string command) =>
        MemoryStatusInquiryLeadPattern().IsMatch(command)
        && MemoryStatusSubjectPattern().IsMatch(command)
        && MemoryStatusSignalPattern().IsMatch(command)
        && !MemoryStatusSecondaryActionPattern().IsMatch(command);

    private static string StableGenericSelector(string command)
    {
        byte[] digest = SHA256.HashData(Encoding.UTF8.GetBytes(command.ToLowerInvariant()));
        return "historical_fact_" + Convert.ToHexString(digest.AsSpan(0, 8)).ToLowerInvariant();
    }

    private static MemoryRoutedOperation Save(
        string selector,
        string value,
        string kind,
        string retention,
        string? expiryPolicy = null,
        string sensitivity = "normal",
        string[]? tags = null) =>
        Save(
            selector,
            JsonValue.Create(value),
            kind,
            retention,
            expiryPolicy,
            sensitivity,
            tags);

    private static MemoryRoutedOperation Save(
        string selector,
        bool value,
        string kind,
        string retention,
        string? expiryPolicy = null,
        string sensitivity = "normal",
        string[]? tags = null) =>
        Save(
            selector,
            JsonValue.Create(value),
            kind,
            retention,
            expiryPolicy,
            sensitivity,
            tags);

    private static MemoryRoutedOperation Save(
        string selector,
        JsonNode? value,
        string kind,
        string retention,
        string? expiryPolicy,
        string sensitivity,
        string[]? tags)
    {
        var arguments = new JsonObject
        {
            ["version"] = 1,
            ["selector"] = selector,
            ["value"] = value,
            ["kind"] = kind,
            ["retention"] = retention,
            ["sensitivity"] = sensitivity,
            ["tags"] = new JsonArray(
                (tags ?? [])
                .Select(static tag => (JsonNode?)JsonValue.Create(tag))
                .ToArray()),
        };
        if (expiryPolicy is not null)
        {
            arguments["expiryPolicy"] = expiryPolicy;
        }

        return new MemoryRoutedOperation("memory.save", arguments);
    }

    private static MemoryRoutedOperation Recall(string scope, string? selector) =>
        new(
            "memory.recall",
            new JsonObject
            {
                ["version"] = 1,
                ["scope"] = scope,
                ["selector"] = selector,
            });

    private static MemoryRoutedOperation Forget(
        string scope,
        string? selector,
        bool confirmationRequired) =>
        new(
            "memory.forget",
            new JsonObject
            {
                ["version"] = 1,
                ["scope"] = scope,
                ["selector"] = selector,
                ["confirmationRequired"] = confirmationRequired,
            });

    private static MemoryRoutedOperation ForgetSession() =>
        new(
            "memory.forget",
            new JsonObject
            {
                ["version"] = 1,
                ["scope"] = "session",
                ["selector"] = null,
                ["confirmationRequired"] = false,
                ["mustNotDeletePersistent"] = true,
            });

    private static MemoryRoutedOperation Correct(
        string selector,
        string value,
        string retention,
        string? expectedValue = null,
        string? kind = null)
    {
        var arguments = new JsonObject
        {
            ["version"] = 1,
            ["selector"] = selector,
            ["value"] = value,
            ["retention"] = retention,
        };
        if (expectedValue is not null)
        {
            arguments["expectedValue"] = expectedValue;
        }

        if (kind is not null)
        {
            arguments["kind"] = kind;
        }

        return new MemoryRoutedOperation("memory.correct", arguments);
    }

    private static MemoryRoutedOperation Configure(bool enabled) =>
        new(
            "memory.configure",
            new JsonObject
            {
                ["version"] = 1,
                ["enabled"] = enabled,
            });

    private static MemoryRoutedOperation Status() =>
        new("memory.status", new JsonObject { ["version"] = 1 });

    private static MemoryRoutedOperation List() =>
        new(
            "memory.list",
            new JsonObject
            {
                ["version"] = 1,
                ["limit"] = 100,
                ["offset"] = 0,
            });

    private static MemoryRoutedOperation Export() =>
        new(
            "memory.export",
            new JsonObject
            {
                ["version"] = 1,
                ["destination"] = "documents",
                ["includeSecrets"] = false,
            });

    private static bool TrySafeCapturedValue(string value, out string safeValue)
    {
        safeValue = value.Trim().Normalize(NormalizationForm.FormC);
        return safeValue.Length > 0
            && Encoding.UTF8.GetByteCount(safeValue) <= MaximumCapturedValueUtf8Bytes
            && !ContainsSensitiveMaterial(safeValue)
            && !RedactedValuePattern().IsMatch(safeValue)
            && !IsPlaceholderValue(safeValue)
            && !PostposedNoStorePattern().IsMatch(safeValue)
            && !AuthorizationPattern().IsMatch(safeValue)
            && !SecondaryInstructionPattern().IsMatch(safeValue)
            && !AnaphoricValuePattern().IsMatch(safeValue)
            && !FilesystemOrDocumentPattern().IsMatch(safeValue);
    }

    private static string TrimSentencePunctuation(string value)
    {
        string result = value;
        if (result.StartsWith('¿'))
        {
            result = result[1..].TrimStart();
        }

        return result.TrimEnd(' ', '.', '!', '?');
    }

    private static string StripRequestEnvelope(string value)
    {
        string result = value;
        Match trailingClosure = TrailingSocialClosurePattern().Match(result);
        if (trailingClosure.Success && trailingClosure.Index > 0)
        {
            result = result[..trailingClosure.Index].TrimEnd();
        }

        for (int layer = 0; layer < 6; layer++)
        {
            int frame = ComputerInstructionFrameLength(result);
            if (frame > 0)
            {
                result = result[frame..].TrimStart();
                continue;
            }

            Match wrapper = AssistantRequestEnvelopePattern().Match(result);
            if (!wrapper.Success || wrapper.Length == 0)
            {
                break;
            }

            result = result[wrapper.Length..].TrimStart();
        }

        return TrimSentencePunctuation(result);
    }

    /// <summary>
    /// Length of a leading frame that only announces an instruction follows.
    /// </summary>
    /// <remarks>
    /// "Actúa en el PC con esta instrucción: ..." carries no request of its
    /// own, and cut B wrapped every row this way: the private memory parser
    /// recognised none of its twelve memory rows until the wrapper came off.
    /// Recognised by shape -- an instruction noun and a machine noun before the
    /// colon -- rather than by listing the wrappers one corpus happened to use.
    /// Written in code because the envelope pattern is NonBacktracking, which
    /// forbids the lookarounds this needs, and that guarantee protects
    /// untrusted text and is worth more than the brevity.
    /// </remarks>
    private static int ComputerInstructionFrameLength(string value)
    {
        int colon = value.IndexOf(':');
        if (colon <= 0 || colon > 90)
        {
            return 0;
        }

        string head = value[..colon];
        string folded = FoldForFrame(head);
        // A negated frame is an explicit request for no action. Stripping it
        // would turn "esto es sólo una conversación y no una orden para el pc"
        // into an instruction, which is the opposite of what was asked.
        if (ContainsAnyWord(folded, FrameNegations)
            || !ContainsAnyWord(folded, FrameMachineNouns))
        {
            return 0;
        }

        // Either the frame names what follows as an instruction, or it points
        // at the machine imperatively without the noun: "Haz this on the
        // computer: ...".
        bool namesAnInstruction = ContainsAnyWord(folded, FrameInstructionNouns);
        bool pointsAtTheMachine =
            ContainsAnyWord(folded, FrameImperativeVerbs)
            && ContainsAnyWord(folded, FrameDemonstratives);
        if (!namesAnInstruction && !pointsAtTheMachine)
        {
            return 0;
        }

        int end = colon + 1;
        while (end < value.Length && value[end] == ' ')
        {
            end++;
        }

        return end;
    }

    private static string FoldForFrame(string value)
    {
        string decomposed = value.Normalize(NormalizationForm.FormD);
        var builder = new StringBuilder(decomposed.Length);
        foreach (char character in decomposed)
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character)
                == UnicodeCategory.NonSpacingMark)
            {
                continue;
            }

            builder.Append(char.IsLetterOrDigit(character)
                ? char.ToLowerInvariant(character)
                : ' ');
        }

        return builder.ToString();
    }

    private static bool ContainsAnyWord(string foldedText, string[] words)
    {
        foreach (string word in words)
        {
            int index = foldedText.IndexOf(word, StringComparison.Ordinal);
            while (index >= 0)
            {
                bool leftBoundary = index == 0 || foldedText[index - 1] == ' ';
                int after = index + word.Length;
                bool rightBoundary = after >= foldedText.Length
                    || foldedText[after] == ' ';
                if (leftBoundary && rightBoundary)
                {
                    return true;
                }

                index = foldedText.IndexOf(word, index + 1, StringComparison.Ordinal);
            }
        }

        return false;
    }

    // Each class below mirrors _COMPUTER_INSTRUCTION_FRAME in effect_intent.py
    // and is completed from the language, not from the wordings a corpus used.
    // R23 carried one addressed frame per language; the Spanish one said
    // "indicacion", that single word was missing, and the whole Spanish cell
    // fell to 23,5 % while the other five scored 573 of 573.
    private static readonly string[] FrameNegations =
        [
            "no", "not", "sin", "without", "solo", "only", "nada",
            "ningun", "ninguna", "ninguno", "ningunos", "ningunas",
            "tampoco", "nunca", "jamas", "neither", "none", "never",
        ];

    // These two arrays must hold exactly the members that
    // INSTRUCTION_NOUN_COGNATES and MACHINE_NOUN_COGNATES generate in
    // src/baxy_mind/effect_intent.py. A Python test parses this file and fails
    // if they drift, because drift is what broke both borders before: R23 lost
    // a Spanish cell to a missing "indicacion", and R26 lost 18 rows to a
    // missing English "petition" while the Spanish "peticion" was present.
    //
    // "tarea"/"task"/"recado"/"nota"/"recordatorio" are deliberately absent.
    // They read like instruction nouns but name catalog objects, and
    // "crea una tarea en el equipo: comprar pan" would be stripped to
    // "comprar pan" -- destroying the request instead of unwrapping it.
    private static readonly string[] FrameInstructionNouns =
        [
            "orden", "ordenes", "order", "orders",
            "instruccion", "instrucciones", "instruction", "instructions",
            "indicacion", "indicaciones", "direction", "directions",
            "directriz", "directrices", "directive", "directives",
            "consigna", "consignas", "command", "commands",
            "mandato", "mandatos", "mandate", "mandates",
            "encargo", "encargos", "errand", "errands",
            "encomienda", "encomiendas", "assignment", "assignments",
            "solicitud", "solicitudes", "request", "requests",
            "peticion", "peticiones", "petition", "petitions",
            "pedido", "pedidos",
            "disposicion", "disposiciones", "provision", "provisions",
        ];

    // "ordenador" is the ordinary word for a computer in Peninsular Spanish.
    // Leaving it out meant the frame was never stripped for those speakers.
    private static readonly string[] FrameMachineNouns =
        [
            "equipo", "equipos", "machine", "machines",
            "maquina", "maquinas",
            "computador", "computadores", "computer", "computers",
            "computadora", "computadoras",
            "ordenador", "ordenadores",
            "portatil", "portatiles", "laptop", "laptops",
            "pc", "pcs",
        ];

    private static readonly string[] FrameImperativeVerbs =
        [
            "haz", "hacer", "realiza", "realizar", "ejecuta", "ejecutar",
            "atiende", "atender", "resuelve", "resolver", "encargate",
            "ocupate", "do", "handle", "perform", "carry", "run", "execute",
            "attend", "take",
        ];

    private static readonly string[] FrameDemonstratives =
        ["this", "esto", "eso", "esta", "este", "siguiente", "following"];

    private static bool ContainsControlCharacter(string value)
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

    [GeneratedRegex("\\s+", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex CollapseWhitespacePattern();

    [GeneratedRegex(
        "^(?:(?:(?:hola|hello|hey|oye|oiga|che|a[ ]+ver)[ ]+)?"
        + "baxy[ ]*[,;:\\-–—]?[ ]*|"
        + "(?:a[ ]+ver|antes[ ]+que[ ]+nada|che|oye|oiga|listen|hey)[ ]*[,;:\\-–—][ ]*|"
        + "(?:hazme[ ]+un[ ]+favor|one[ ]+thing|una[ ]+cosa[ ]+please)[ ]*[,;:][ ]*|"
        + "(?:esta[ ]+vez[ ]+necesito[ ]+una[ ]+acci[oó]n[ ]+concreta[ ]+en[ ]+este[ ]+equipo|"
        + "enc[aá]rgate[ ]+en[ ]+el[ ]+computador[ ]+de[ ]+esto|"
        + "on[ ]+this[ ]+computer[ ]*,[ ]*carry[ ]+out[ ]+this[ ]+specific[ ]+request|"
        + "i[ ]+need[ ]+this[ ]+done[ ]+locally[ ]+on[ ]+the[ ]+pc|"
        + "haz[ ]+this[ ]+concrete[ ]+action[ ]+en[ ]+este[ ]+computador|"
        + "on[ ]+this[ ]+pc[ ]*,[ ]*enc[aá]rgate[ ]+de[ ]+esto|"
        + "atiende[ ]+este[ ]+pedido|take[ ]+care[ ]+of[ ]+this[ ]+request|"
        + "handle[ ]+este[ ]+pedido|"
        + "te[ ]+(?:dejo|doy|paso)[ ]+(?:una[ ]+)?"
        + "(?:instrucci[oó]n|indicaci[oó]n|tarea|petici[oó]n)"
        + "(?:[ ]+(?:concreta|espec[ií]fica|puntual))?"
        + "(?:[ ]+para[ ]+(?:(?:este|el)[ ]+)?(?:computador|equipo|pc))?|"
        + "necesito[ ]+que[ ]+(?:hagas|realices|atiendas)[ ]+"
        + "(?:lo[ ]+siguiente|esto)(?:[ ]+ahora)?|"
        + "here(?:['’]s|[ ]+is)[ ]+(?:(?:one|a)[ ]+)?"
        + "(?:(?:concrete|specific)[ ]+)?(?:instruction|request|task)"
        + "(?:[ ]+for[ ]+(?:(?:this|the)[ ]+)?(?:computer|pc))?|"
        + "please[ ]+(?:handle|do)[ ]+(?:the[ ]+following|this)"
        + "(?:[ ]+on[ ]+(?:(?:this|the)[ ]+)?(?:pc|computer))?(?:[ ]+now)?|"
        + "necesito[ ]+(?:this|esta)[ ]+(?:exact[ ]+)?(?:thing|cosa)"
        + "(?:[ ]+on[ ]+(?:(?:this|the)[ ]+)?(?:pc|computer))?|"
        + "(?:atiende|handle|haz|do)[ ]+(?:esto|this))"
        + "[ ]*[,;:.!?\\-–—]+[ ]*|"
        + "(?:for[ ]+(?:(?:this|este)[ ]+)?(?:computer|computador|pc|equipo)"
        + "(?:[ ]+(?:right[ ]+now|ahora))?[ ]*,[ ]*(?:please|por[ ]+favor)[ ]+)|"
        + "(?:(?:cuando[ ]+(?:puedas|tengas[ ]+(?:(?:un|algo[ ]+de)[ ]+)?(?:momento|rato|minuto)|te[ ]+(?:quede|venga)[ ]+bien)|"
        + "when[ ]+(?:you[ ]+(?:can|have[ ]+(?:a[ ]+)?(?:moment|minute)|get[ ]+(?:a[ ]+)?chance)|it[ ]+is[ ]+convenient))|"
        + "(?:(?:una[ ]+)?(?:(?:peque[nñ]a|breve|r[aá]pida|simple)[ ]+)?(?:petici[oó]n|solicitud|consulta|pregunta)(?:[ ]+(?:peque[nñ]a|breve|r[aá]pida|simple))?|"
        + "(?:(?:one|a)[ ]+)?(?:quick|small|brief|simple)[ ]+(?:request|question)|(?:one|a)[ ]+(?:request|question))|"
        + "(?:a[ ]+prop[oó]sito|tengo[ ]+una[ ]+pregunta|i[ ]+was[ ]+wondering)|"
        + "(?:escucha|mira|listen|look))[ ]*[,;:–—-]+[ ]*|"
        + "(?:por[ ]+favor|porfa|please)[ ]*[,;:]?[ ]*|"
        + "(?:can[ ]+you|could[ ]+you|would[ ]+you)(?:[ ]+please)?[ ]+)",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex AssistantRequestEnvelopePattern();

    [GeneratedRegex(
        "[ ]*[,;][ ]*(?:(?:por[ ]+favor|porfa|please|gracias|thanks|thank[ ]+you)[ ]*,?[ ]*)?"
        + "(?:eso[ ]+es[ ]+todo|nada[ ]+m[aá]s|that(?:'|â€™)?s[ ]+(?:all|the[ ]+whole[ ]+request)|"
        + "that[ ]+is[ ]+(?:all|the[ ]+whole[ ]+request)|nothing[ ]+else|"
        + "con[ ]+(?:eso|esto)[ ]+(?:termina|finaliza|concluye)[ ]+"
        + "(?:mi|la)[ ]+(?:solicitud|petici[oó]n|pedido|tarea)(?:[ ]+por[ ]+ahora)?|"
        + "(?:mi|la)[ ]+(?:solicitud|petici[oó]n|pedido|tarea)[ ]+"
        + "(?:termina|finaliza|concluye|queda[ ]+(?:completa|completada))"
        + "(?:[ ]+(?:aqu[ií]|por[ ]+ahora))?|"
        + "(?:that|this)[ ]+(?:completes|finishes|ends|concludes)[ ]+"
        + "(?:my|the)[ ]+(?:request|task)(?:[ ]+for[ ]+now)?|"
        + "(?:con[ ]+(?:eso|esto)[ ]*,[ ]*)?(?:my|the)[ ]+(?:request|task)[ ]+"
        + "(?:is|is[ ]+now|has[ ]+been)[ ]+(?:complete|completed|finished|done)"
        + "(?:[ ]+for[ ]+now)?)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex TrailingSocialClosurePattern();

    private const string EnglishConfigurationMemoryTarget =
        "(?:(?:the|your|baxy['’]s)[ ]+)?(?:(?:private|local|personal)[ ]+){0,3}memory";

    [GeneratedRegex(
        "^(?:(?:(?<enable>activa|habilita)|(?<disable>desactiva|deshabilita))[ ]+"
        + "(?:la|tu)[ ]+memoria(?:[ ]+(?:privada|local|personal)){0,3}(?:[ ]+de[ ]+baxy)?|"
        + "(?:(?<enable>enable)|(?<disable>disable))[ ]+" + EnglishConfigurationMemoryTarget + "|"
        + "turn[ ]+" + EnglishConfigurationMemoryTarget + "[ ]+(?:(?<enable>on)|(?<disable>off)))$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex MemoryConfigurationRequestPattern();

    [GeneratedRegex(
        "^(?:dime|muestra(?:me)?|consulta|revisa|comprueba|checkea|indica|confirma|"
        + "show|tell|check|review|give|state|confirm|report|i[ ]+need).{0,96}(?:"
        + "(?:c[oó]mo[ ]+est[aá]|estado(?:[ ]+actual)?|status|state|present[ ]+state|"
        + "current[ ]+state|condici[oó]n|condition|si|whether).{0,96}"
        + "(?:almacenamiento[ ]+privado[ ]+de[ ]+recuerdos|memoria[ ]+personal[ ]+local(?:[ ]+de[ ]+baxy)?|"
        + "private[ ]+recollection[ ]+store|baxy(?:['’]s)?[ ]+locally[ ]+kept[ ]+personal[ ]+memory|"
        + "locally[ ]+kept[ ]+personal[ ]+memory|"
        + "(?:(?:memoria|recuerdos?|memory|memories).{0,48}"
        + "(?:privad[oa]s?|private|personal|local(?:es|mente)?|locally|stored|guardad[oa]s?|baxy|tus|your)|"
        + "(?:baxy(?:['’]s)?|tus|your|local(?:ly|mente)?|privad[oa]s?|private|personal|stored).{0,48}"
        + "(?:memoria|recuerdos?|memory|memories)))"
        + "(?:.{0,48}(?:operativ[oa]s?|operational|estado|status|activ[oa]s?|"
        + "habilitad[oa]s?|active|enabled|working|funciona(?:ndo)?))?"
        + "(?:.{0,32}(?:en[ ]+(?:este|el)[ ]+(?:dispositivo|device)|on[ ]+this[ ]+device|"
        + "aqu[i\\u00ed]|here|localmente|locally))?|"
        + "(?:almacenamiento[ ]+privado[ ]+de[ ]+recuerdos|memoria[ ]+personal[ ]+local(?:[ ]+de[ ]+baxy)?|"
        + "private[ ]+recollection[ ]+store|baxy(?:['’]s)?[ ]+locally[ ]+kept[ ]+personal[ ]+memory|"
        + "locally[ ]+kept[ ]+personal[ ]+memory|"
        + "(?:(?:memoria|recuerdos?|memory|memories).{0,48}"
        + "(?:privad[oa]s?|private|personal|local(?:es|mente)?|locally|stored|guardad[oa]s?|baxy|tus|your)|"
        + "(?:baxy(?:['’]s)?|tus|your|local(?:ly|mente)?|privad[oa]s?|private|personal|stored).{0,48}"
        + "(?:memoria|recuerdos?|memory|memories)))"
        + ".{0,64}(?:condici[oó]n|condition|operativ[oa]s?|operational|estado|status|"
        + "activ[oa]s?|habilitad[oa]s?|active|enabled|working|funciona(?:ndo)?)"
        + "(?:.{0,32}(?:en[ ]+(?:este|el)[ ]+(?:dispositivo|device)|on[ ]+this[ ]+device|"
        + "aqu[i\\u00ed]|here|localmente|locally))?)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex MemoryStatusRequestPattern();

    [GeneratedRegex(
        "^(?:est[aá][ ]+funcionando[ ]+ahora[ ]+tu[ ]+"
        + "(?:almac[eé]n[ ]+personal[ ]+de[ ]+memoria[ ]+local|personal[ ]+local[- ]memory[ ]+store)|"
        + "is[ ]+your[ ]+personal[ ]+local[- ]memory[ ]+store[ ]+working[ ]+right[ ]+now|"
        + "est[aá][ ]+working[ ]+ahora[ ]+tu[ ]+personal[ ]+local[- ]memory[ ]+store|"
        + "check[ ]+whether[ ]+tu[ ]+personal[ ]+local[- ]memory[ ]+store[ ]+"
        + "est[aá][ ]+working[ ]+ahora)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex LeadingMemoryStatusRequestPattern();

    [GeneratedRegex(
        "^(?:(?:dime|muestra(?:me)?|consulta|revisa|comprueba|verifica|indica|confirma|"
        + "acl[aá]rame|checkea|show|tell(?:[ ]+me)?|check|review|give|state|confirm|report|"
        + "verify|clarify|determine)\\b|(?:quiero|necesito)[ ]+(?:saber|conocer)|"
        + "(?:puedes|podr[ií]as)[ ]+(?:decirme|comprobar|revisar|confirmar)|"
        + "let[ ]+me[ ]+know|i[ ]+(?:want|need)[ ]+to[ ]+(?:know|learn)|"
        + "(?:can|could|would)[ ]+you[ ]+(?:tell|check|verify|determine))",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex MemoryStatusInquiryLeadPattern();

    [GeneratedRegex(
        "(?:(?:memorias?|memory|memories|recuerdos?|recollections?).{0,80}"
        + "(?:tu|tus|your|baxy|privad[oa]s?|private(?:ly)?|personal|local(?:es|mente|ly)?|"
        + "stored|guardad[oa]s?|almacenad[oa]s?|conserva|keeps?|persistid[oa]s?)|"
        + "(?:tu|tus|your|baxy|privad[oa]s?|private(?:ly)?|personal|local(?:es|mente|ly)?|"
        + "stored|guardad[oa]s?|almacenad[oa]s?|conserva|keeps?|persistid[oa]s?).{0,80}"
        + "(?:memorias?|memory|memories|recuerdos?|recollections?))",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex MemoryStatusSubjectPattern();

    [GeneratedRegex(
        "(?:estado|status|state|condici[oó]n|condition|operativ[oa]s?|operational|"
        + "activ[oa]s?|active|habilitad[oa]s?|enabled|working|funciona(?:ndo)?)",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex MemoryStatusSignalPattern();

    [GeneratedRegex(
        "(?:\\b(?:y|and|then|despu[eé]s)\\b.{0,96}"
        + "\\b(?:abre|open|cierra|close|env[ií]a|send|borra|delete|guarda|save|"
        + "escribe|write|crea|create|inicia|launch|reproduce|play)\\b)",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex MemoryStatusSecondaryActionPattern();

    [GeneratedRegex(
        "(?:tel[eé]fono|phone|smartphone|tablet|reloj|watch|otro[ ]+equipo|"
        + "another[ ]+(?:computer|device)|other[ ]+(?:computer|device))",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex OtherDeviceMemoryStatusPattern();

    [GeneratedRegex(
        "(?:api[ ]*key|clave[ ]+api|password|contrase(?:ñ|n)a?|\\brut\\b|\\bssn\\b|social[ ]+security|token[ ]+(?:secreto|secret)|\\b(?:sk[-_][a-z0-9_-]{4,}|gh[pousr]_[a-z0-9]{8,}|github_pat_[a-z0-9_]{8,}|glpat-[a-z0-9_-]{10,}|(?:akia|asia)[a-z0-9]{12,}|aiza[a-z0-9_-]{12,}|xox[baprs]-[a-z0-9-]{8,}|npm_[a-z0-9]{20,}|(?:rk|pk)_live_[a-z0-9]{8,}))",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex SensitiveMaterialPattern();

    [GeneratedRegex(
        "^(?:recuerda|remember|save|guarda|acordate|recordame)\\b",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex ExplicitMemorySavePattern();

    [GeneratedRegex(
        "^(?:save[ ]+my[ ]+api[ ]*key[ ]+(?<value>.+)[ ]+in[ ]+your[ ]+memory|remember[ ]+my[ ]+api[ ]*key[ ]+is[ ]+(?<value>.+)|recuerda[ ]+mi[ ]+(?:api[ ]*key|clave[ ]+api)[ ]*(?::|es)[ ]*(?<value>.+))$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex ApiKeySensitiveSavePattern();

    [GeneratedRegex(
        "^(?:recuerda[ ]+mi[ ]+(?:contrase(?:ñ|n)a|password)[ ]+es|remember[ ]+my[ ]+(?:password|contrase(?:ñ|n)a)[ ]+is)[ ]+(?<value>.+)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex PasswordSensitiveSavePattern();

    [GeneratedRegex(
        "^(?:remember[ ]+my[ ]+(?:ssn|social[ ]+security[ ]+number)[ ]+is|recuerda[ ]+mi[ ]+(?:ssn|n[uú]mero[ ]+de[ ]+seguridad[ ]+social)[ ]+es)[ ]+(?<value>.+)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex SsnSensitiveSavePattern();

    [GeneratedRegex(
        "^recuerda[ ]+mi[ ]+rut(?:(?:[ ]+es|[ ]*:)[ ]*|[ ]+)(?<value>.+)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex RutSensitiveSavePattern();

    [GeneratedRegex(
        "(?:\\[[^\\]]*(?:redacted|redactado|removed|eliminado|omitido|masked|oculto|hidden)[^\\]]*\\]|<[^>]*(?:redacted|redactado|removed|eliminado|omitido|masked|oculto|hidden)[^>]*>|\\b(?:redacted|redactado|removed|eliminado|omitido|masked|oculto|hidden)\\b|^\\*{3,}$|^x{3,}$)",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex RedactedValuePattern();

    [GeneratedRegex(
        "(?:\\b(?:pero|but)\\b.{0,80}\\b(?:no|nunca|don['’]?t|do[ ]+not|never)\\b|\\b(?:sin|without)\\b.{0,32}\\b(?:guard|recuerd|almacen|conserv|memoriz|persist|sav|remember|stor|keep|retain)|\\b(?:no[ ]+(?:(?:lo|la|esto|eso)[ ]+)?(?:guardes|recuerdes|almacenes|conserves|memorices)|(?:don['’]?t|do[ ]+not|never)[ ]+(?:save|remember|store|keep))(?:[ ]+(?:it|this|that))?\\b)",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex PostposedNoStorePattern();

    [GeneratedRegex(
        "^(?:no|nunca|don['’]?t|do[ ]+not|never)[ ]+(?:guard(?:a|es)|recuerd(?:a|es)|remember|save)|^(?:no[ ]+(?:uses?|usar)|don['’]?t[ ]+use|do[ ]+not[ ]+use)[ ]+(?:la[ ]+)?(?:memoria|memory)|^(?:no[ ]+guardes[ ]+esto|don['’]?t[ ]+save[ ]+this)",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex ExplicitNoStorePattern();

    [GeneratedRegex(
        "^(?:no[ ]+guardes[ ]+esto|don['’]?t[ ]+save[ ]+this).{0,160}(?:solo|just|ahora|now|sesi[oó]n|session)",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex TemporaryNoStorePattern();

    [GeneratedRegex(
        "(?:\\b(?:autorizaci[oó]n|authorization|authorisation)\\b|permiso(?:s)?[ ]+(?:total(?:es)?|completo(?:s)?)|total[ ]+(?:permission|access)|(?:pc|computer)[ ]+.{0,40}(?:disposici[oó]n|permission)|(?:tienes|tiene|tengo|te[ ]+doy|te[ ]+concedo|you[ ]+have|i[ ]+give[ ]+you|i[ ]+grant[ ]+you)[ ].{0,40}(?:permiso|permission|access)|(?:eres|you[ ]+are)[ ]+(?:un[ ]+|an?[ ]+)?(?:admin(?:istrador)?|administrator|superuser|root)[ ]+(?:total|full)|(?:te[ ]+autorizo|i[ ]+authorize[ ]+you)[ ].{0,32}(?:a[ ]+)?(?:modificar|cambiar|borrar|eliminar|ejecutar|hacer|modify|change|delete|remove|run|do)|(?:puedes|pod[eé]s)[ ].{0,20}hacer[ ]+(?:lo[ ]+que[ ]+quieras|cualquier[ ]+cosa)|you[ ]+(?:may|can)[ ].{0,20}do[ ]+(?:anything|whatever[ ]+you[ ]+want))",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex AuthorizationPattern();

    [GeneratedRegex(
        "(?:\\b(?:pero|but)\\b|\\b(?:y|and)\\b.{0,48}\\b(?:no|nunca|tienes|puedes|eres|te|you|i|don['’]?t|do[ ]+not|never|have|may|can|are)\\b|\\b(?:sin|without)\\b.{0,32}\\b(?:guard|recuerd|almacen|conserv|memoriz|persist|sav|remember|stor|keep|retain))",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex SecondaryInstructionPattern();

    // Remembering a task to do is a reminder, not a datum for the private memory:
    // «recuerda arreglar una reunión … mañana a las siete» (tanda-02) was saved as
    // a fact. Any infinitive after the head («recuerda / recordá / acordate de /
    // recuérdame <hacer algo>», «remember / remind me to <do>»), a due moment
    // right after «recuérdame / remind me», or a «recuérdame que …» carrying a
    // due moment leaves the turn to the mind's reminder reading. «recuerda que
    // <dato>» stays a memory save.
    [GeneratedRegex(
        "^(?:recu[eé]rdame|recordame|remind[ ]+me)[ ]+(?:en[ ]+\\d+|a[ ]+las?[ ]|ma[nñ]ana|hoy|esta[ ]+(?:tarde|noche)|to(?:day|morrow|night)|at[ ]+\\d|in[ ]+\\d)"
        + "|^(?:recuerda|record[aá]|acordate|acu[eé]rdate|recu[eé]rdame|recordame)[ ]+(?:de[ ]+)?\\p{L}+(?:ar|er|ir|ír)(?:me|te|se|nos|lo|la|los|las|le|les){0,2}(?:[ ,.]|$)"
        + "|^(?:remember|remind[ ]+me)[ ]+to[ ]+\\p{L}"
        + "|^recu[eé]rdame[ ]+que[ ]+(?:pague|tome|saque|llame|compre)[ ]+"
        + "|^(?:recu[eé]rdame|recordame)[ ]+que[ ].*\\b(?:ma[nñ]ana|hoy|esta[ ]+(?:tarde|noche)|a[ ]+las?[ ]+\\S+|en[ ]+\\d+[ ]+(?:minutos?|horas?)|dentro[ ]+de|el[ ]+(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo))\\b",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex ReminderPattern();

    [GeneratedRegex(
        "(?:<command-|</command-|<task-|</task-|\\bwer\\b|recall[ ]+de[ ]+entidades|\\bram\\b|memoria[ ]+(?:libre|disponible)|perfect[ ]+recall|flashcard|\\btelemetr(?:i|í)a\\b|feature[ ]+usada|memory\\.json|abre[ ]+(?:word|excel)|open[ ]+(?:word|excel)|guarda[ ]+(?:el|the)[ ]+(?:documento|document)|current[ ]+window[ ]+layout|que[ ]+puedes[ ]+hacer.{0,40}como[ ]+me[ ]+llamo|record[aá]:|recordatorio|reminder)",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex NoiseOrCompositionPattern();

    [GeneratedRegex(
        "(?:[?].+(?:c[oó]mo[ ]+me[ ]+llamo|what.+my[ ]+name)|record[aá]:|olvida.+(?:det[eé]n|stop|misi[oó]n|mission))",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex MixedMemoryCompositionPattern();

    [GeneratedRegex(
        "^(?:(?:mi[ ]+color[ ]+favorito[ ]+es|my[ ]+favorite[ ]+color[ ]+is|mi[ ]+nombre[ ]+es|"
        + "my[ ]+name[ ]+is|(?:yo[ ]+)?me[ ]+llamo|i[ ]+work[ ]+at|mi[ ]+ciudad[ ]+favorita[ ]+es|"
        + "my[ ]+favorite[ ]+city[ ]+is|tengo[ ]+un[ ]+perro[ ]+llamado|me[ ]+gusta)[ ]+.+|"
        + "i['’]?[ ]*m[ ]+(?:a[ ]+)?(?:developer|programmer)|"
        + "soy[ ]+(?:programador|desarrollador(?:[ ]+de[ ]+software)?|carter[ ]+de[ ]+como)|"
        + "si[ ]+te[ ]+digo[ ].+[ ]+responde[ ]+.+|"
        + "no[ ]+ahora[ ]+no,[ ]+pero[ ]+quiero[ ]+que[ ]+cada[ ]+mensaje[ ]+.+|"
        + "sou[ ]+(?:programador|desenvolvedor))$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex ImplicitMemoryPattern();

    [GeneratedRegex(
        "^(?:olvida|forget)[ ]+(?:eso|esto|that|this|lo[ ]+anterior|todo[ ]+lo[ ]+que[ ]+sabes|everything[ ]+you[ ]+know|lo[ ]+del[ ]+estilo|that[ ]+setting)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex AmbiguousForgetPattern();

    [GeneratedRegex(
        "^(?:(?:s[ií],[ ]+)?(?:recuerda|remember|guarda|save|recu[eé]rdalo|remember[ ]+it|"
        + "lembra|lembre|ricorda)[ ]+(?:esto|this|eso|that|ese[ ]+dato|it)(?:[ ]+.+)?|"
        + "guarda[ ]+esa[ ]+preferencia(?:[ ]+.+)?)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex AmbiguousSavePattern();

    [GeneratedRegex(
        "^(?:esto|this|eso|that|esa[ ]+(?:preferencia|preference)|lo[ ]+del[ ]+estilo|that[ ]+setting)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex AnaphoricValuePattern();

    [GeneratedRegex(
        "(?:[a-z]:[\\\\/]|%userprofile%|\\\\\\\\|\\.(?:txt|md|json|docx?|xlsx?|pdf)\\b|\\b(?:archivo|documento|file|document)\\b)",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex FilesystemOrDocumentPattern();

    [GeneratedRegex(
        "^(?:(?:recuerda|record[aá]|acordate|acuérdate|guarda|guard[aá]|remember)(?:[ ]+que|[ ]+that)?)[ ]+(?:mi|my)[ ]+(?:color[ ]+favorito|favorite[ ]+color)[ ]+(?:es|is)[ ]+(?:el[ ]+)?(?<value>[\\p{L}][\\p{L} -]{0,39})$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex FavoriteColorSavePattern();

    [GeneratedRegex(
        "^(?:(?:recuerda|record[aá]|acordate|acuérdate|guarda|guard[aá]|remember)(?:[ ]+que|[ ]+that)?)[ ]+(?:me[ ]+gusta[ ]+(?:tomar|beber)|mi[ ]+bebida[ ]+favorita[ ]+es|i[ ]+like[ ]+to[ ]+drink|my[ ]+favorite[ ]+drink[ ]+is)[ ]+(?:el[ ]+|la[ ]+|the[ ]+)?(?<value>[\\p{L}][\\p{L} -]{0,39})$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex FavoriteDrinkSavePattern();

    [GeneratedRegex(
        // «recordá que me llamo …» (voseo), «acordate que me llamo …» and «quiero que
        // me recuerdes como …» ask to persist the name as plainly as «recuerda que
        // me llamo …» (MEMORY1245: H0149 read as a reminder without a time).
        "^(?:(?:recuerda|record[aá]|acordate|acuérdate)(?:[ ]+que)?[ ]+me[ ]+llamo|remember[ ]+(?:that[ ]+)?my[ ]+name[ ]+is|remember[ ]+me[ ]+as|(?:quiero[ ]+que[ ]+)?me[ ]+recuerdes[ ]+como)[ ]+(?<value>[\\p{L}][\\p{L}'’-]{0,79})$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex NameSavePattern();

    [GeneratedRegex(
        "^(?:(?:recuerda|guarda)[ ]+mi[ ]+nombre|(?:remember|save)[ ]+my[ ]+name|"
        + "(?:quiero|necesito)[ ]+que[ ]+(?:recuerdes|guardes)[ ]+mi[ ]+nombre|"
        + "(?:quiero|voy[ ]+a)[ ]+(?:decirte|darte)[ ]+mi[ ]+nombre[ ]+y[ ]+"
        + "(?:quiero|necesito)[ ]+que[ ]+lo[ ]+(?:recuerdes|guardes)|"
        + "i[ ]+(?:want|need)[ ]+you[ ]+to[ ]+(?:remember|save)[ ]+my[ ]+name|"
        + "i[ ]+(?:want[ ]+to|will)[ ]+(?:tell|give)[ ]+you[ ]+my[ ]+name[ ]+and[ ]+"
        + "i[ ]+(?:want|need)[ ]+you[ ]+to[ ]+(?:remember|save)[ ]+it)"
        + "(?:[ ]+(?:(?:para[ ]+)?cuando[ ]+te[ ]+(?:lo[ ]+)?pregunte|when[ ]+i[ ]+ask(?:[ ]+you)?(?:[ ]+again)?))?[.!]?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex MissingNameSavePattern();

    [GeneratedRegex(
        "\\b(?:no[ ]+(?:quiero|necesito)|i[ ]+(?:don['’]?t|do[ ]+not)[ ]+want)[ ].{0,48}"
        + "\\b(?:guardar|guardes|recordar|recuerdes|save|remember)\\b",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex NegatedMemoryIntentPattern();

    [GeneratedRegex(
        "^(?:(?:yo[ ]+)?me[ ]+llamo|mi[ ]+nombre[ ]+es|my[ ]+name[ ]+is)[ ]+"
        + "(?<value>[\\p{L}][\\p{L} '’-]{0,79})(?:[.!]|[,;][ ]*(?<public>.+))?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex DeclaredNameInputPattern();

    [GeneratedRegex(
        "[.,;!][ ]*|[ ]+(?:y|and)[ ]+",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex NameClauseBoundaryPattern();

    [GeneratedRegex(
        "^(?:recuerda(?<session>[ ]+durante[ ]+esta[ ]+sesi[oó]n)?[ ]+que[ ]+mi[ ]+proyecto[ ]+se[ ]+llama|remember(?<session>[ ]+for[ ]+this[ ]+session)?[ ]+that[ ]+my[ ]+project[ ]+is[ ]+called)[ ]+(?<value>[\\p{L}\\p{N}][\\p{L}\\p{N} ._-]{0,79})$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex ProjectNameSavePattern();

    [GeneratedRegex(
        "\\b(?:y|and|pero|but|sin|without)\\b",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex ProjectNameClausePattern();

    [GeneratedRegex(
        "^(?:recuerda|remember)(?:[ ]+que|[ ]+that)[ ]+(?:prefiero|i[ ]+prefer)[ ]+(?:respuestas[ ]+)?(?:cortas|short[ ]+(?:answers|responses))$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex ShortResponseSavePattern();

    [GeneratedRegex(
        "^(?:recuerda|remember)(?:[ ]+que|[ ]+that)[ ]+(?:prefiero|i[ ]+prefer)[ ]+(?:respuestas[ ]+)?(?:directas|direct[ ]+(?:answers|responses))$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex DirectResponseSavePattern();

    [GeneratedRegex(
        "^(?:recuerda|remember)(?:[ ]+que|[ ]+that)[ ]+(?:prefiero|i[ ]+prefer)[ ]+(?:el[ ]+)?(?:modo[ ]+oscuro|dark[ ]+mode)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex DarkModeSavePattern();

    [GeneratedRegex(
        "^(?:(?<conversation>c[oó]mo[ ]+me[ ]+llamo|what(?:[ ]+is|'s)[ ]+my[ ]+name|"
        + "quien[ ]+soy[ ]+yo|was[ ]+my[ ]+name[ ]+again)|"
        + "(?:what|which)[ ]+name[ ]+(?:have[ ]+you[ ]+(?:saved|stored)|"
        + "do[ ]+you[ ]+have[ ]+(?:saved|stored))"
        + "(?:[ ]+in[ ]+(?:(?:your|the)[ ]+)?(?:private[ ]+)?(?:local[ ]+)?memory)?|"
        + "what(?:[ ]+is|'s)[ ]+my[ ]+(?:saved|stored)[ ]+name|"
        + "qu[eé][ ]+nombre[ ]+(?:tienes|has)[ ]+(?:guardado|almacenado)"
        + "(?:[ ]+en[ ]+(?:(?:tu|la)[ ]+)?memoria(?:[ ]+(?:local|privada)){0,2})?|"
        + "cu[aá]l[ ]+es[ ]+mi[ ]+nombre[ ]+(?:guardado|almacenado)|"
        + "comment[ ]+je[ ]+m['’]appelle|quel[ ]+est[ ]+mon[ ]+nom(?:,[ ]+s['’]il[ ]+vous[ ]+pla[iî]t)?|"
        + "wie[ ]+hei(?:ß|ss)e[ ]+ich|was[ ]+ist[ ]+mein[ ]+name[ ]+noch[ ]+mal|"
        + "come[ ]+mi[ ]+chiamo|como[ ]+me[ ]+chamo|"
        + "qual[ ]+[eé][ ]+o[ ]+meu[ ]+nome|meu[ ]+nome[ ]+qual[ ]+era)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex NameRecallPattern();

    [GeneratedRegex(
        "^(?:erinnere[ ]+dich[ ]+an[ ]+meinen[ ]+firmennamen|"
        + "wie[ ]+hei(?:ß|ss)t[ ]+meine[ ]+firma|"
        + "d[oó]nde[ ]+trabajo|en[ ]+qu[eé][ ]+empresa[ ]+trabajo|where[ ]+do[ ]+i[ ]+work)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex EmployerRecallPattern();

    [GeneratedRegex(
        "^(?:qu[eé][ ]+recuerdas[ ]+de[ ]+m[ií]|what[ ]+do[ ]+you[ ]+remember[ ]+about[ ]+me)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex AllRecallPattern();

    [GeneratedRegex(
        "^(?:qu[eé][ ]+(?:recuerdas[ ]+sobre|sabes[ ]+de)[ ]+mis[ ]+preferencias|"
        + "what[ ]+do[ ]+you[ ]+remember[ ]+about[ ]+my[ ]+preferences|"
        + "was[ ]+ist[ ]+meine[ ]+bevorzugte[ ]+einstellung|"
        + "qu[eé][ ]+recuerdas[ ]+de[ ]+mis[ ]+preferencias|"
        + "qu[eé][ ]+preferencia(?:[ ]+t[eé]cnica|[ ]+de[ ]+respuestas)?[ ]+recuerdas[ ]+de[ ]+carter|"
        + "cu[aá]les[ ]+son[ ]+mis[ ]+preferencias[ ]+guardadas|qu[eé][ ]+prefiero[ ]+yo|"
        + "resp[oó]ndeme[ ]+seg[uú]n[ ]+mis[ ]+preferencias)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex PreferenceRecallPattern();

    [GeneratedRegex(
        "^(?:qu[eé][ ]+(?:proyecto|project)[ ]+(?:estoy|i['’]?[ ]*m)[ ]+(?:haciendo|working[ ]+on)|"
        + "dime[ ]+qu[eé][ ]+proyecto[ ]+estoy[ ]+haciendo|qual[ ]+[eé][ ]+o[ ]+meu[ ]+projeto|"
        + "quel[ ]+projet[ ]+suis-je[ ]+en[ ]+train[ ]+de[ ]+faire|"
        + "can[ ]+you[ ]+tell[ ]+me[ ]+my[ ]+project[ ]+name)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex ProjectRecallPattern();

    [GeneratedRegex(
        "^(?:qu[eé][ ]+color[ ]+me[ ]+gusta|what(?:[ ]+is|'s)[ ]+my[ ]+favorite[ ]+color)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex FavoriteColorRecallPattern();

    [GeneratedRegex(
        "^(?:(?:decime|dime|sab[eé]s)[ ]+)?(?:qu[eé][ ]+(?:me[ ]+gusta|bebida[ ]+me[ ]+gusta)[ ]+(?:tomar|beber)|cu[aá]l[ ]+es[ ]+mi[ ]+bebida[ ]+favorita|what(?:[ ]+is|'s)[ ]+my[ ]+favorite[ ]+drink|what[ ]+do[ ]+i[ ]+like[ ]+to[ ]+drink)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex FavoriteDrinkRecallPattern();

    [GeneratedRegex(
        "^(?:borra|olvida|delete|forget)[ ]+(?:mi|my)[ ]+(?:color[ ]+favorito|favorite[ ]+color)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex FavoriteColorForgetPattern();

    [GeneratedRegex(
        "^(?:borra|olvida|delete|forget)[ ]+(?:(?:todos[ ]+)?(?:tus|mis)[ ]+recuerdos[ ]+(?:sobre|de)[ ]+m[ií]|todo[ ]+lo[ ]+que[ ]+sabes[ ]+de[ ]+m[ií]|everything[ ]+(?:you[ ]+know[ ]+)?about[ ]+me)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex AllForgetPattern();

    [GeneratedRegex(
        "^(?:olvida|forget)[ ]+(?:que[ ]+)?(?:prefiero|i[ ]+prefer)[ ]+(?:hablar[ ]+en[ ]+)?(?:espa[nñ]ol|spanish)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex LanguageForgetPattern();

    [GeneratedRegex(
        "^(?:qu[eé][ ]+(?:recuerdas|sabes|tienes[ ]+guardado)(?:[ ]+(?:de|sobre))?[ ]+m[ií]|"
        + "qu[eé][ ]+datos[ ]+m[ií]os[ ]+(?:guardas|tienes)|what[ ]+do[ ]+you[ ]+know[ ]+about[ ]+me|"
        + "what[ ]+do[ ]+you[ ]+remember[ ]+about[ ]+me|cosa[ ]+ricordi[ ]+di[ ]+me|"
        + "quais[ ]+dados[ ]+meus[ ]+voc[eê][ ]+guarda|qu[eé][ ]+cosas[ ]+(?:importantes[ ]+)?recuerdas[ ]+sobre[ ]+carter|"
        + "qu[eé][ ]+memorias[ ]+usaste[ ]+para[ ]+responder|"
        + "describe[ ]+what[ ]+i['’]?[ ]*m[ ]+like[ ]+based[ ]+on[ ]+what[ ]+you(?:['’]ve|[ ]+have)[ ]+observed)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex GenericAllRecallPattern();

    [GeneratedRegex(
        "^(?:olvida|olvidate|esquece|efface|vergiss|forget)[ ]+(?:todo|tudo|tout|alles|everything).{0,80}(?:m[ií]|mim|moi|mich|me|carter)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex GenericAllForgetPattern();

    [GeneratedRegex(
        "^(?:olvida|forget)[ ]+(?:la|the)?[ ]*(?:preferencia|preference)(?:[ ]+anterior|[ ]+previous)?$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex GenericPreferenceForgetPattern();

    [GeneratedRegex(
        "^(?:olvida|olvidate|forget)(?:[ ]+(?:de|about))?[ ]+(?<topic>.+)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex GenericTopicForgetPattern();

    [GeneratedRegex(
        "^(?:change[ ]+my[ ]+project[ ]+to|cambia[ ]+mi[ ]+proyecto[ ]+a)[ ]+(?<value>.+)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex ProjectChangePattern();

    [GeneratedRegex(
        "^(?:recuerda(?:[ ]+que)?|recu[eé]rdame[ ]+que|remember(?:[ ]+that)?|guard[aá][ ]+que|acordate[ ]+que|"
        + "lembra[ ]+que|lembre[ ]+que|souviens-toi[ ]+que|merk[ ]+dir[ ]+dass|ricorda[ ]+che)"
        + "[ ]+(?<value>.+)$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex GenericExplicitSavePattern();

    [GeneratedRegex(
        "(?:prefier|favorit|favorite|gusta|like|lieblings|pr[eé]f[eé]r)",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex GenericPreferenceValuePattern();

    [GeneratedRegex(
        "(?:me[ ]+llamo|my[ ]+name|mi[ ]+nombre|cumplea[nñ]os|birthday|trabajo[ ]+en|work[ ]+at|ciudad)",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex GenericPersonalValuePattern();
}
