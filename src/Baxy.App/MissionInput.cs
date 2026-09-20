using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;

namespace Baxy.App;

internal enum MissionInputSource
{
    Text,
    VoiceTranscript,
}

internal sealed record MissionInput(
    string Text,
    MissionInputSource Source)
{
    public override string ToString() =>
        $"{nameof(MissionInput)} {{ Source = {Source}, Text = [REDACTED] }}";
}

internal enum MissionInputRejectionReason
{
    Empty,
    ContainsNull,
    MalformedUtf16,
    TooLarge,
    UnsupportedSource,
}

internal sealed class MissionInputRejectedException : ArgumentException
{
    internal MissionInputRejectedException(MissionInputRejectionReason reason)
        : base(MessageFor(reason), nameof(MissionInput.Text))
    {
        Reason = reason;
    }

    internal MissionInputRejectionReason Reason { get; }

    private static string MessageFor(MissionInputRejectionReason reason) => reason switch
    {
        MissionInputRejectionReason.Empty =>
            "La entrada de misi\u00f3n est\u00e1 vac\u00eda.",
        MissionInputRejectionReason.ContainsNull =>
            "La entrada de misi\u00f3n contiene un car\u00e1cter nulo.",
        MissionInputRejectionReason.MalformedUtf16 =>
            "La entrada de misi\u00f3n no es texto UTF-16 bien formado.",
        MissionInputRejectionReason.TooLarge =>
            "La entrada de misi\u00f3n supera el l\u00edmite de caracteres.",
        MissionInputRejectionReason.UnsupportedSource =>
            "La fuente de entrada de misi\u00f3n no est\u00e1 admitida.",
        _ => "La entrada de misi\u00f3n no es v\u00e1lida.",
    };
}

internal static class MissionInputContract
{
    // This is the existing WPF composer MaxLength, not the memory parser's
    // narrower UTF-8 limit. It preserves the text-entry contract for every route.
    internal const int MaximumCharacters = 4096;

    internal const string SafeRejectionGuidance =
        "La entrada no es v\u00e1lida. El borrador sigue intacto; rev\u00edsalo y mantenlo " +
        "dentro de 4096 caracteres.";

    internal static string ValidateAndTrim(MissionInput? input)
    {
        if (!TryValidate(
                input,
                out string text,
                out MissionInputRejectionReason rejection))
        {
            throw new MissionInputRejectedException(rejection);
        }

        return text;
    }

    private static bool TryValidate(
        MissionInput? input,
        out string text,
        out MissionInputRejectionReason rejection)
    {
        text = string.Empty;
        if (input?.Text is { Length: > MaximumCharacters })
        {
            rejection = MissionInputRejectionReason.TooLarge;
            return false;
        }

        if (input is null || string.IsNullOrWhiteSpace(input.Text))
        {
            rejection = MissionInputRejectionReason.Empty;
            return false;
        }

        if (!Enum.IsDefined(input.Source))
        {
            rejection = MissionInputRejectionReason.UnsupportedSource;
            return false;
        }

        text = input.Text.Trim();
        if (text.Contains('\0'))
        {
            rejection = MissionInputRejectionReason.ContainsNull;
            return false;
        }

        if (!IsWellFormedUtf16(text))
        {
            rejection = MissionInputRejectionReason.MalformedUtf16;
            return false;
        }

        if (text.Length > MaximumCharacters)
        {
            rejection = MissionInputRejectionReason.TooLarge;
            return false;
        }

        rejection = default;
        return true;
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
}

internal sealed record MissionOperationContract(
    string Name,
    string Risk,
    PolicyDecision ConfirmationPolicy);

internal sealed class MissionInputRoute
{
    private readonly Lazy<RoutedOperation?> _standaloneOperation;
    private readonly Lazy<MissionOperationContract?> _operationContract;

    internal MissionInputRoute(
        string text,
        MissionInputSource source,
        MemoryParseResult memory,
        string? publicObjective = null)
    {
        Text = text;
        Source = source;
        Memory = memory ?? throw new ArgumentNullException(nameof(memory));
        PublicObjective = string.IsNullOrWhiteSpace(publicObjective)
            ? null
            : publicObjective;
        _standaloneOperation = new Lazy<RoutedOperation?>(ResolveStandaloneOperationCore);
        _operationContract = new Lazy<MissionOperationContract?>(ResolveOperationContractCore);
    }

    internal string Text { get; }

    internal MissionInputSource Source { get; }

    internal MemoryParseResult Memory { get; }

    internal string? PublicObjective { get; }

    internal bool HasPrivatePublicComposition => PublicObjective is not null;

    internal MissionOperationContract? OperationContract => _operationContract.Value;

    internal RoutedOperation? ResolveStandaloneOperation() => _standaloneOperation.Value;

    private RoutedOperation? ResolveStandaloneOperationCore()
    {
        if (Memory.Outcome != MemoryParseOutcome.NoRoute ||
            Memory.MustNotClaimStandaloneRoute)
        {
            return null;
        }

        return NaturalNoteRequestParser.TryParse(Text, out RoutedOperation? operation)
            ? operation
            : null;
    }

    private MissionOperationContract? ResolveOperationContractCore()
    {
        string? operationName = Memory.Operation is null
            ? ResolveStandaloneOperation()?.Name
            : MemoryOperationProtector.ResolveWireOperationName(Memory.Operation);
        if (operationName is null)
        {
            return null;
        }

        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired(operationName);
        OperationDefinition definition = new(descriptor);
        return new MissionOperationContract(
            descriptor.Name,
            descriptor.Risk,
            RiskPolicy.Evaluate(definition.Risk, operation: descriptor.Name));
    }
}

internal static class MissionInputPipeline
{
    internal static MissionInputRoute Route(MissionInput input)
    {
        string text = MissionInputContract.ValidateAndTrim(input);
        if (PrivateCompoundMissionParser.TrySplit(
                text,
                out MemoryParseResult? privateMemory,
                out string? publicObjective))
        {
            return new MissionInputRoute(
                text,
                input.Source,
                privateMemory!,
                publicObjective);
        }

        MemoryParseResult memory = NaturalMemoryRequestParser.Classify(text);
        return new MissionInputRoute(text, input.Source, memory);
    }

    internal static async Task DispatchAsync(
        MissionInput input,
        Func<MissionInputRoute, CancellationToken, Task> execute,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(execute);
        MissionInputRoute route = Route(input);
        await execute(route, cancellationToken);
    }
}

internal static class PrivateCompoundMissionParser
{
    // Strong structural separators only. A bare "y/and" may belong to the
    // private value ("recuerda que prefiero café y té") and is never split.
    private static readonly string[] Separators =
    [
        ";",
        "\r\n",
        "\n",
        ", y luego ",
        ", luego ",
        ", después ",
        ", despues ",
        ", and then ",
        ", then ",
        ", y ",
        ", and ",
        "? ",
    ];

    internal static bool TrySplit(
        string text,
        out MemoryParseResult? privateMemory,
        out string? publicObjective)
    {
        privateMemory = null;
        publicObjective = null;
        string[] clauses = SplitClauses(text);
        if (clauses.Length < 2)
        {
            return false;
        }

        var publicClauses = new List<string>();
        foreach (string clause in clauses)
        {
            MemoryParseResult classification = NaturalMemoryRequestParser.Classify(clause);
            if (classification.Outcome is MemoryParseOutcome.Route
                or MemoryParseOutcome.ConfirmSensitiveSave)
            {
                if (privateMemory is not null || classification.Operation is null)
                {
                    return false;
                }

                privateMemory = classification;
                continue;
            }

            if (classification.Outcome != MemoryParseOutcome.NoRoute
                || classification.MustNotClaimStandaloneRoute
                || NaturalMemoryRequestParser.ContainsSensitiveMaterial(clause))
            {
                return false;
            }

            publicClauses.Add(clause);
        }

        if (privateMemory is null || publicClauses.Count == 0)
        {
            privateMemory = null;
            return false;
        }

        publicObjective = string.Join("; luego ", publicClauses);
        return true;
    }

    private static string[] SplitClauses(string text)
    {
        var clauses = new List<string> { text };
        foreach (string separator in Separators)
        {
            clauses = clauses
                .SelectMany(value => value.Split(
                    separator,
                    StringSplitOptions.RemoveEmptyEntries
                    | StringSplitOptions.TrimEntries))
                .ToList();
        }

        return clauses.Where(static value => value.Length > 0).ToArray();
    }
}
