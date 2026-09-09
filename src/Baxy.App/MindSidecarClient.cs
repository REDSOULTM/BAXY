using System.Collections.Concurrent;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Kernel.Planning;

namespace Baxy.App;

/// <summary>
/// Decisión de turno emitida por la política contextual de la mente. Es una
/// clasificación abstinente: el shell sigue siendo la única autoridad para
/// ejecutar, confirmar y validar operaciones.
/// </summary>
internal sealed record MindTurnDecision(
    string Kind,
    string? Operation,
    IReadOnlyList<string> EffectOperations,
    string Question,
    string Reply)
{
    /// <summary>
    /// Non-authoritative model selection retained for presentation and
    /// diagnostics. Only <see cref="EffectOperations"/> may reach execution.
    /// </summary>
    public IReadOnlyList<string> IntentOperations { get; init; } = [];

    /// <summary>
    /// Whether a clarification supplies a missing slot for the current
    /// objective. Recovery clarifications set this to false so a failed
    /// conversational turn cannot poison later dialogue context.
    /// </summary>
    public bool PreserveObjective { get; init; } = true;

    /// <summary>
    /// The mind recognized a new request that needs its own clarification.
    /// It must not be appended as a value for an older pending objective.
    /// This flag grants no execution authority and does not discard the new objective.
    /// </summary>
    public bool StartsNewObjective { get; init; }

    /// <summary>
    /// Language the mind actually wrote <see cref="Reply"/> in, as reported by
    /// the mind. The shell never re-derives it: a second reading here is what
    /// vetoed an English greeting composed as Spanish and left the turn silent.
    /// </summary>
    public string? ResponseLanguage { get; init; }

    // Presentation disposition only; this never grants an executable effect.
    public string? ConversationKind { get; init; }

    public string? RecoveryFailureCode { get; init; }
}

internal sealed record MindArgumentResult(
    JsonObject? Arguments,
    string Question);

internal sealed record MindPlanStep(
    string Id,
    string Operation,
    string Purpose,
    IReadOnlyList<string> DependsOn,
    string ArgumentsMode,
    JsonObject? Arguments);

internal sealed record MindPlanResult(
    string Kind,
    string Question,
    IReadOnlyList<MindPlanStep> Steps);

internal sealed record MindComposedMessage(string Text);

internal sealed record MindVoiceStatus(
    bool Available,
    bool InputAvailable,
    bool SttAvailable,
    bool VadAvailable,
    bool TtsAvailable,
    bool AecAvailable,
    bool DuckingAvailable,
    string Mode,
    bool Listening,
    bool Speaking);

/// <summary>
/// Cliente del sidecar de inteligencia (baxy.mind.v1, ADR-0005). Es un
/// segundo proceso local sobre la misma frontera JSONL + Job Object que el
/// core. Es OPCIONAL y degradable: si no está configurado, no arranca o
/// muere, todos los métodos devuelven null y el shell no ejecuta lenguaje
/// libre por una ruta alternativa (fail-closed).
/// </summary>
internal sealed class MindSidecarClient : IAsyncDisposable
{
    internal const string DisabledEnvironmentVariable = "BAXY_MIND_DISABLED";
    internal const string PythonEnvironmentVariable = "BAXY_MIND_PYTHON";
    internal const string PythonPathEnvironmentVariable = "BAXY_MIND_PYTHONPATH";
    internal const string GpuLayersEnvironmentVariable = "BAXY_MIND_NGL";
    // The sidecar owns an 18 s total deadline for argument extraction and may
    // use the remaining budget for a second, schema-grounded clarification
    // generation. Keep 2 s for transport scheduling outside that boundary.
    internal static readonly TimeSpan ArgumentRequestTimeout =
        TimeSpan.FromSeconds(20);
    // turn.decide is read-only and can perform one bounded local retry after
    // a transient constrained-decoding failure.
    internal static readonly TimeSpan TurnDecisionRequestTimeout =
        TimeSpan.FromSeconds(22);
    // One factual status composition may need a zero-temperature correction
    // when the first draft omits actor or verified literals. A five-second
    // ceiling covers the measured cold 4.5 s path without delaying successful
    // one-pass responses; the shell already exposes honest progress meanwhile.
    internal static readonly TimeSpan MessageCompositionRequestTimeout =
        TimeSpan.FromSeconds(5);
    internal static readonly TimeSpan DenseMessageCompositionRequestTimeout =
        TimeSpan.FromSeconds(10);
    // CPU composition keeps the same model-authored and grounded contract as
    // GPU. Ordinary drafts receive 55 s inside a 60 s transport boundary;
    // dense verified missions receive the full 120 s model budget inside a
    // 130 s boundary. The remaining time belongs to JSONL delivery and cleanup.
    internal static readonly TimeSpan CpuMessageCompositionRequestTimeout =
        TimeSpan.FromSeconds(60);
    internal static readonly TimeSpan CpuDenseMessageCompositionRequestTimeout =
        TimeSpan.FromSeconds(130);
    private const double MaximumMessageCompositionProtocolBudgetSeconds = 120d;
    private const int MaximumLineBytes = 1024 * 1024;

    private readonly ConcurrentDictionary<string, TaskCompletionSource<JsonObject>> _pending = new();
    private readonly SemaphoreSlim _writeLock = new(1, 1);
    // Model work is serial in Python. Its execution deadline starts only after
    // the previous request completes, not while waiting behind that request.
    private readonly SemaphoreSlim _requestLock = new(1, 1);
    private LocalJsonlSidecarProcess? _sidecar;
    private Task? _pump;
    private CancellationTokenSource? _pumpCancellation;
    private long _requestSequence;
    private volatile bool _ready;
    private volatile bool _plannerAvailable;
    private volatile bool _turnDecisionAvailable;
    private bool _disposed;

    public bool IsReady => _ready && _sidecar?.Process is { HasExited: false };

    internal bool HasActiveRequest => _requestLock.CurrentCount == 0;

    public bool IsPlannerAvailable => IsReady && _plannerAvailable;

    public bool IsTurnDecisionAvailable => IsReady && _turnDecisionAvailable;

    internal static bool IsCpuFallbackProfile =>
        string.Equals(
            Environment.GetEnvironmentVariable(GpuLayersEnvironmentVariable)?.Trim(),
            "0",
            StringComparison.Ordinal);

    internal static TimeSpan SelectWelcomeCompositionTimeout(bool cpuFallback) =>
        cpuFallback
            ? CpuMessageCompositionRequestTimeout
            : DenseMessageCompositionRequestTimeout;

    internal static double SelectMessageCompositionProtocolBudget(TimeSpan timeout) =>
        Math.Clamp(
            timeout.TotalSeconds >= CpuMessageCompositionRequestTimeout.TotalSeconds
                ? timeout.TotalSeconds - 5d
                : timeout.TotalSeconds - 1d,
            1d,
            MaximumMessageCompositionProtocolBudgetSeconds);

    internal static TimeSpan SelectMessageCompositionTimeout(
        JsonObject facts,
        bool cpuFallback = false)
    {
        ArgumentNullException.ThrowIfNull(facts);
        int requiredFactCount = facts["requiredFacts"] is JsonArray requiredFacts
            ? requiredFacts.Count
            : 0;
        int requiredFactCharacters = facts["requiredFacts"] is JsonArray factValues
            ? factValues.Sum(static fact => (fact?.GetValue<string>() ?? string.Empty).Length)
            : 0;
        bool partialMission = facts["partialMission"]?.GetValue<bool>() is true;
        bool dense = partialMission
            || requiredFactCount >= 8
            || requiredFactCharacters >= 512;
        if (cpuFallback)
        {
            return dense
                ? CpuDenseMessageCompositionRequestTimeout
                : CpuMessageCompositionRequestTimeout;
        }

        return dense
            ? DenseMessageCompositionRequestTimeout
            : MessageCompositionRequestTimeout;
    }

    /// <summary>Transcripción de voz emitida por el sidecar (hilo del pump).</summary>
    public event Action<string>? TranscriptReceived;

    /// <summary>Estado no sensible de la tubería de voz (hilo del pump).</summary>
    public event Action<JsonObject>? VoiceEventReceived;

    /// <summary>Señal temprana o hito: prosa formulada, nunca un resultado.</summary>
    public event Action<string>? TurnSignalReceived;

    internal static bool IsDisabled =>
        string.Equals(
            Environment.GetEnvironmentVariable(DisabledEnvironmentVariable),
            "1",
            StringComparison.Ordinal);

    public static bool IsConfigured =>
        !IsDisabled
        && !string.IsNullOrWhiteSpace(
            Environment.GetEnvironmentVariable(PythonEnvironmentVariable));

    /// <summary>
    /// Arranca el sidecar si está configurado. Nunca lanza hacia el caller:
    /// devuelve false y queda deshabilitado ante cualquier fallo.
    /// </summary>
    public async Task<bool> TryStartAsync(
        IReadOnlyList<OperationDescriptor> capabilities,
        TimeSpan handshakeTimeout,
        CancellationToken cancellationToken) =>
        await TryStartAsync(
            capabilities,
            applicationCatalog: null,
            gameCatalog: null,
            handshakeTimeout,
            cancellationToken).ConfigureAwait(false);

    public async Task<bool> TryStartAsync(
        IReadOnlyList<OperationDescriptor> capabilities,
        ApplicationCatalogSnapshot? applicationCatalog,
        TimeSpan handshakeTimeout,
        CancellationToken cancellationToken) =>
        await TryStartAsync(
            capabilities,
            applicationCatalog,
            gameCatalog: null,
            handshakeTimeout,
            cancellationToken).ConfigureAwait(false);

    public async Task<bool> TryStartAsync(
        IReadOnlyList<OperationDescriptor> capabilities,
        ApplicationCatalogSnapshot? applicationCatalog,
        GameCatalogSnapshot? gameCatalog,
        TimeSpan handshakeTimeout,
        CancellationToken cancellationToken)
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        ArgumentNullException.ThrowIfNull(capabilities);
        if (_ready)
        {
            return true;
        }

        string? python = Environment.GetEnvironmentVariable(PythonEnvironmentVariable);
        if (string.IsNullOrWhiteSpace(python) || !File.Exists(python))
        {
            return false;
        }

        using var startupTimeout = new CancellationTokenSource(handshakeTimeout);
        using var startupCancellation = CancellationTokenSource.CreateLinkedTokenSource(
            cancellationToken,
            startupTimeout.Token);
        try
        {
            var environment = new Dictionary<string, string>(StringComparer.Ordinal);
            string? pythonPath =
                Environment.GetEnvironmentVariable(PythonPathEnvironmentVariable);
            if (!string.IsNullOrWhiteSpace(pythonPath))
            {
                environment["PYTHONPATH"] = pythonPath;
            }

            var sidecar = LocalJsonlSidecarProcess.Start(new LocalJsonlSidecarDefinition(
                "mind",
                python,
                Path.GetDirectoryName(python)!,
                arguments: ["-X", "utf8", "-m", "baxy_mind"],
                environment: environment));
            _sidecar = sidecar;
            _pumpCancellation = new CancellationTokenSource();
            var helloCompletion = new TaskCompletionSource<JsonObject>(
                TaskCreationOptions.RunContinuationsAsynchronously);
            _pump = PumpAsync(sidecar.Process, helloCompletion, _pumpCancellation.Token);

            JsonObject hello = await helloCompletion.Task
                .WaitAsync(startupCancellation.Token)
                .ConfigureAwait(false);
            if ((string?)hello["protocol"] != "baxy.mind.v1")
            {
                throw new InvalidDataException("El sidecar de mente no habla baxy.mind.v1.");
            }

            _ready = true;
            bool hasLlm = hello["models"] is JsonObject models
                && models["llm"] is JsonValue;
            JsonArray? requests = hello["requests"] as JsonArray;
            _plannerAvailable = hasLlm
                && requests?.Any(static request => (string?)request == "plan") == true;
            _turnDecisionAvailable = hasLlm
                && requests?.Any(static request => (string?)request == "turn.decide") == true;
            if (!await ConfigureCatalogAsync(
                    capabilities,
                    applicationCatalog,
                    gameCatalog,
                    handshakeTimeout,
                    startupCancellation.Token).ConfigureAwait(false))
            {
                throw new InvalidDataException(
                    "El sidecar de mente rechazó el catálogo autenticado del core.");
            }

            return true;
        }
        catch (Exception exception) when (exception is not OperationCanceledException
            || !cancellationToken.IsCancellationRequested)
        {
            await ShutdownQuietlyAsync().ConfigureAwait(false);
            return false;
        }
    }

    private async Task<bool> ConfigureCatalogAsync(
        IReadOnlyList<OperationDescriptor> capabilities,
        ApplicationCatalogSnapshot? applicationCatalog,
        GameCatalogSnapshot? gameCatalog,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        JsonObject request = CreateCatalogConfigureRequest(
            capabilities,
            applicationCatalog,
            gameCatalog);
        JsonObject? reply = await RequestAsync(
            request,
            timeout,
            cancellationToken).ConfigureAwait(false);
        return reply is not null
            && (string?)reply["type"] == "catalog.ready"
            && (int?)reply["count"] == capabilities.Count;
    }

    internal static JsonObject CreateCatalogConfigureRequest(
        IReadOnlyList<OperationDescriptor> capabilities,
        ApplicationCatalogSnapshot? applicationCatalog,
        GameCatalogSnapshot? gameCatalog = null)
    {
        ArgumentNullException.ThrowIfNull(capabilities);
        var catalog = new JsonArray();
        foreach (OperationDescriptor capability in capabilities)
        {
            catalog.Add(new JsonObject
            {
                ["name"] = capability.Name,
                ["description"] = capability.Description,
                ["argumentsSchema"] = JsonNode.Parse(
                    capability.ArgumentsSchema.GetRawText()),
                ["risk"] = capability.Risk,
            });
        }

        var request = new JsonObject
        {
            ["type"] = "catalog.configure",
            ["capabilities"] = catalog,
        };
        if (applicationCatalog is not null)
        {
            ContractValidator.Validate(applicationCatalog);
            var names = new JsonArray();
            foreach (string name in applicationCatalog.Names)
            {
                names.Add(name);
            }

            request["applicationCatalog"] = new JsonObject
            {
                ["version"] = applicationCatalog.Version,
                ["verified"] = applicationCatalog.Verified,
                ["complete"] = applicationCatalog.Complete,
                ["names"] = names,
            };
        }
        if (gameCatalog is not null)
        {
            ContractValidator.Validate(gameCatalog);
            var entries = new JsonArray();
            foreach (GameCatalogEntry entry in gameCatalog.Entries)
            {
                entries.Add(new JsonObject
                {
                    ["provider"] = entry.Provider,
                    ["appId"] = entry.AppId,
                    ["name"] = entry.Name,
                });
            }

            request["gameCatalog"] = new JsonObject
            {
                ["version"] = gameCatalog.Version,
                ["verified"] = gameCatalog.Verified,
                ["complete"] = gameCatalog.Complete,
                ["entries"] = entries,
            };
        }

        return request;
    }

    public async Task<MindTurnDecision?> DecideTurnAsync(
        string text,
        IReadOnlyList<(string Role, string Content)> history,
        TimeSpan timeout,
        CancellationToken cancellationToken,
        bool pendingClarification = false)
    {
        if (!IsTurnDecisionAvailable)
        {
            return null;
        }

        var historyArray = new JsonArray();
        foreach ((string role, string content) in history)
        {
            historyArray.Add(new JsonObject
            {
                ["role"] = role,
                ["content"] = content,
            });
        }

        JsonObject? reply = await RequestAsync(
            new JsonObject
            {
                ["type"] = "turn.decide",
                ["text"] = text,
                ["history"] = historyArray,
                ["pendingClarification"] = pendingClarification,
                ["uiLanguage"] =
                    CultureInfo.CurrentUICulture.TwoLetterISOLanguageName,
            },
            timeout,
            cancellationToken).ConfigureAwait(false);
        if (reply is null || (string?)reply["type"] != "turn.result")
        {
            return null;
        }

        string kind = (string?)reply["kind"] ?? string.Empty;
        string? operation = (string?)reply["operation"];
        if (!TryParseEffectOperations(reply, out string[] effectOperations))
        {
            return null;
        }
        string[] intentOperations = [];
        if (reply["intentOperations"] is not null
            && !TryParseOperations(
                reply,
                "intentOperations",
                out intentOperations))
        {
            return null;
        }
        string question = (string?)reply["question"] ?? string.Empty;
        string response = (string?)reply["reply"] ?? string.Empty;
        string? conversationKind = null;
        if (reply["conversationKind"] is JsonNode disposition
            && (kind != "conversation"
                || disposition is not JsonValue value
                || !value.TryGetValue(out conversationKind)
                || conversationKind is not ("social" or "knowledge" or "followup"
                    or "unsupported" or "unsupported_language")))
        {
            return null;
        }
        string? responseLanguage = (string?)reply["responseLanguage"] is { } language
            && language is "es" or "en" or "mixed"
                ? language
                : null;
        if (!TryParsePreserveObjective(reply, out bool preserveObjective)
            || !TryParseStartsNewObjective(reply, out bool startsNewObjective))
        {
            return null;
        }
        string? recoveryFailureCode = (string?)reply["failure_code"];
        if (recoveryFailureCode is not null
            && (recoveryFailureCode is not ("turn_contract_failure" or "turn_runtime_failure" or "turn_unavailable")
                || effectOperations.Length != 0))
        {
            return null;
        }
        bool validEffects = effectOperations.Length <= 8
            && effectOperations.All(static value =>
                value.Length <= 256
                && value.All(static character =>
                    char.IsAsciiLetterOrDigit(character) || character == '.'))
            && (kind switch
            {
                "action" => effectOperations.Length == 1
                    && string.Equals(
                        effectOperations[0],
                        operation,
                        StringComparison.Ordinal),
                "plan" => operation is null,
                "conversation" =>
                    effectOperations.Length == 0 && operation is null,
                "clarify" =>
                    effectOperations.Length == 0
                    && operation is null
                    && IsSingleClarificationQuestion(question)
                    && string.IsNullOrEmpty(response),
                _ => false,
            });
        bool validIntents = intentOperations.All(static value =>
            value.Length <= 256
            && value.All(static character =>
                char.IsAsciiLetterOrDigit(character) || character == '.'));
        return kind is "conversation" or "clarify" or "action" or "plan"
            && validEffects
            && validIntents
            ? new MindTurnDecision(
                kind,
                operation,
                effectOperations,
                question,
                response)
            {
                IntentOperations = intentOperations,
                PreserveObjective = preserveObjective,
                StartsNewObjective = startsNewObjective,
                ResponseLanguage = responseLanguage,
                ConversationKind = conversationKind,
                RecoveryFailureCode = recoveryFailureCode,
            }
            : null;
    }

    internal static bool TryParsePreserveObjective(
        JsonObject reply,
        out bool preserveObjective)
        => TryParseOptionalBoolean(reply, "preserveObjective", true, out preserveObjective);

    internal static bool TryParseStartsNewObjective(
        JsonObject reply,
        out bool startsNewObjective)
        => TryParseOptionalBoolean(reply, "startsNewObjective", false, out startsNewObjective);

    private static bool TryParseOptionalBoolean(
        JsonObject reply,
        string property,
        bool defaultValue,
        out bool result)
    {
        ArgumentNullException.ThrowIfNull(reply);
        result = defaultValue;
        JsonNode? value = reply[property];
        if (value is null)
        {
            return true;
        }

        return value is JsonValue scalar
            && scalar.TryGetValue(out result);
    }

    internal static bool TryParseEffectOperations(
        JsonObject reply,
        out string[] effectOperations)
        => TryParseOperations(
            reply,
            "effectOperations",
            out effectOperations);

    internal static bool TryParseOperations(
        JsonObject reply,
        string propertyName,
        out string[] effectOperations)
    {
        effectOperations = [];
        if (reply[propertyName] is not JsonArray effects
            || effects.Count > 8)
        {
            return false;
        }

        var parsed = new List<string>(effects.Count);
        foreach (JsonNode? node in effects)
        {
            if (node is not JsonValue value
                || !value.TryGetValue(out string? operation)
                || string.IsNullOrWhiteSpace(operation))
            {
                return false;
            }

            parsed.Add(operation);
        }

        effectOperations = parsed.ToArray();
        return true;
    }

    public async Task<MindArgumentResult?> ExtractArgumentResultAsync(
        string operation,
        string text,
        TimeSpan timeout,
        CancellationToken cancellationToken,
        IReadOnlyList<(string Role, string Content)>? history = null)
    {
        // El grounding de argumentos es un tramo propio: no pertenece ni a la
        // decisión ni al Core, y fundirlo con ellos oculta dónde está el coste.
        ShellTraceSink.Record(
            ShellTraceScopes.Turn,
            ShellTraceSink.TurnId,
            ShellTraceStages.ArgumentsStart);
        try
        {
            var historyArray = new JsonArray();
            foreach ((string role, string content) in history ?? [])
            {
                historyArray.Add(new JsonObject
                {
                    ["role"] = role,
                    ["content"] = content,
                });
            }
            JsonObject? reply = await RequestAsync(
                new JsonObject
                {
                    ["type"] = "arguments",
                    ["operation"] = operation,
                    ["text"] = text,
                    ["history"] = historyArray,
                },
                timeout,
                cancellationToken).ConfigureAwait(false);
            return ParseArgumentResult(reply, operation);
        }
        finally
        {
            ShellTraceSink.Record(
                ShellTraceScopes.Turn,
                ShellTraceSink.TurnId,
                ShellTraceStages.ArgumentsEnd);
        }
    }

    public async Task<JsonObject?> ExtractArgumentsAsync(
        string operation,
        string text,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        MindArgumentResult? result = await ExtractArgumentResultAsync(
            operation,
            text,
            timeout,
            cancellationToken).ConfigureAwait(false);
        return result?.Arguments;
    }

    internal static MindArgumentResult? ParseArgumentResult(
        JsonObject? reply,
        string expectedOperation)
    {
        if (reply is null
            || (string?)reply["type"] != "arguments.result"
            || (string?)reply["operation"] != expectedOperation
            || (bool?)reply["ok"] is not bool ok)
        {
            return null;
        }

        JsonObject? arguments = reply["arguments"]?.DeepClone() as JsonObject;
        string question = (string?)reply["question"] ?? string.Empty;
        if (ok)
        {
            return arguments is not null && string.IsNullOrEmpty(question)
                ? new MindArgumentResult(arguments, string.Empty)
                : null;
        }

        return arguments is null && IsSingleClarificationQuestion(question)
            ? new MindArgumentResult(null, question)
            : null;
    }

    private static bool IsSingleClarificationQuestion(string question)
    {
        if (string.IsNullOrWhiteSpace(question)
            || question.Length > 512
            || !string.Equals(question, question.Trim(), StringComparison.Ordinal)
            || question.Contains('\r')
            || question.Contains('\n')
            || !question.EndsWith('?'))
        {
            return false;
        }

        return question.Count(character => character == '?') == 1;
    }

    public async Task<MindPlanResult?> PlanAsync(
        string text,
        IReadOnlyList<(string Role, string Content)> history,
        TimeSpan timeout,
        CancellationToken cancellationToken,
        JsonObject? recovery = null,
        IReadOnlyList<string>? expectedOperations = null,
        MindReplanSuffixContract? expectedSuffix = null)
    {
        JsonObject request = CreatePlanRequest(
            text,
            history,
            recovery,
            expectedOperations,
            expectedSuffix);

        JsonObject? reply = await RequestAsync(
            request,
            timeout,
            cancellationToken,
            returnProtocolError: true).ConfigureAwait(false);
        if (reply is null || (string?)reply["type"] == "error")
        {
            return new MindPlanResult(
                "failed",
                TurnVisibleFacts.Failure("plan_incomplete"),
                Array.Empty<MindPlanStep>());
        }

        MindPlanResult? result = ParsePlanResult(reply);
        return ValidateExpectedPlanResult(
            result,
            expectedOperations,
            expectedSuffix);
    }

    internal static JsonObject CreatePlanRequest(
        string text,
        IReadOnlyList<(string Role, string Content)> history,
        JsonObject? recovery = null,
        IReadOnlyList<string>? expectedOperations = null,
        MindReplanSuffixContract? expectedSuffix = null)
    {
        ArgumentNullException.ThrowIfNull(text);
        ArgumentNullException.ThrowIfNull(history);
        if (expectedOperations is { Count: > 0 } && expectedSuffix is not null)
        {
            throw new ArgumentException(
                "A plan request cannot combine effect-name and pending-suffix constraints.");
        }

        var historyArray = new JsonArray();
        foreach ((string role, string content) in history)
        {
            historyArray.Add(new JsonObject
            {
                ["role"] = role,
                ["content"] = content,
            });
        }

        var request = new JsonObject
        {
            ["type"] = "plan",
            ["text"] = text,
            ["history"] = historyArray,
        };
        JsonObject? recoveryContract = recovery?.DeepClone().AsObject();
        if (expectedSuffix is not null)
        {
            recoveryContract ??= new JsonObject();
            if (recoveryContract.ContainsKey("pendingSuffix"))
            {
                throw new ArgumentException(
                    "Recovery already contains a pending-suffix contract.",
                    nameof(recovery));
            }

            recoveryContract["pendingSuffix"] = expectedSuffix.ToRecoveryJson();
        }

        if (recoveryContract is not null)
        {
            request["recovery"] = recoveryContract;
        }
        if (expectedOperations is { Count: > 0 })
        {
            var expected = new JsonArray();
            foreach (string operation in expectedOperations)
            {
                expected.Add(operation);
            }

            request["expectedOperations"] = expected;
        }

        return request;
    }

    internal static MindPlanResult? ValidateExpectedPlanResult(
        MindPlanResult? result,
        IReadOnlyList<string>? expectedOperations,
        MindReplanSuffixContract? expectedSuffix = null)
    {
        if (expectedOperations is { Count: > 0 } && expectedSuffix is not null)
        {
            return null;
        }

        if (result is not null && expectedSuffix is not null)
        {
            return (result.Kind == "clarify"
                || MindPlanBoundary.IsSafeReplanSuffix(expectedSuffix, result))
                ? result
                : null;
        }

        if (result is null || expectedOperations is not { Count: > 0 })
        {
            return result;
        }

        if (expectedOperations.Count > 8
            || expectedOperations.Any(static operation =>
                string.IsNullOrWhiteSpace(operation)
                || operation.Length > 256
                || operation.Any(static character =>
                    !char.IsAsciiLetterOrDigit(character) && character != '.')))
        {
            return null;
        }

        if (result.Kind == "clarify")
        {
            return result;
        }

        if (result.Kind != "plan")
        {
            return null;
        }

        string[] observedPlan = result.Steps
            .Select(static step => step.Operation)
            .ToArray();
        return ExpandExpectedPlanOperationVariants(expectedOperations)
            .Any(expectedPlan => observedPlan.SequenceEqual(
                expectedPlan,
                StringComparer.Ordinal))
            ? result
            : null;
    }

    private static string[][] ExpandExpectedPlanOperationVariants(
        IReadOnlyList<string> expectedOperations)
    {
        var variants = new List<List<string>> { new() };
        var seenEffects = new HashSet<string>(StringComparer.Ordinal);
        foreach (string operation in expectedOperations)
        {
            string[] prerequisites = MissionPlanValidator
                .RequiredPredecessorOperations(operation);
            bool repeatedIdentityConsumer = prerequisites.Length > 0
                && seenEffects.Contains(operation);
            var next = new List<List<string>>(variants.Count * 2);
            foreach (List<string> expanded in variants)
            {
                bool needsPredecessor = prerequisites.Length > 0
                    && (repeatedIdentityConsumer
                        || !expanded.Any(prerequisites.Contains));
                if (needsPredecessor)
                {
                    foreach (string prerequisite in prerequisites)
                    {
                        var candidate = new List<string>(expanded)
                        {
                            prerequisite,
                            operation,
                        };
                        next.Add(candidate);
                    }
                }
                else
                {
                    var candidate = new List<string>(expanded) { operation };
                    next.Add(candidate);
                }
            }

            variants = next;
            seenEffects.Add(operation);
        }

        return variants
            .Where(static variant => variant.Count <= MissionPlanValidator.MaximumSteps)
            .Select(static variant => variant.ToArray())
            .Distinct(StringArrayComparer.Instance)
            .ToArray();
    }

    private sealed class StringArrayComparer : IEqualityComparer<string[]>
    {
        internal static StringArrayComparer Instance { get; } = new();

        public bool Equals(string[]? left, string[]? right) =>
            ReferenceEquals(left, right)
            || left is not null
            && right is not null
            && left.SequenceEqual(right, StringComparer.Ordinal);

        public int GetHashCode(string[] value)
        {
            var hash = new HashCode();
            foreach (string item in value)
            {
                hash.Add(item, StringComparer.Ordinal);
            }

            return hash.ToHashCode();
        }
    }

    public async Task<JsonObject?> GroundPlanStepAsync(
        string objective,
        MindPlanStep step,
        JsonArray observations,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(step);
        ArgumentNullException.ThrowIfNull(observations);
        JsonObject? reply = await RequestAsync(
            new JsonObject
            {
                ["type"] = "plan.ground",
                ["objective"] = objective,
                ["operation"] = step.Operation,
                ["purpose"] = step.Purpose,
                ["observations"] = observations.DeepClone(),
            },
            timeout,
            cancellationToken).ConfigureAwait(false);
        if (reply is null
            || (string?)reply["type"] != "plan.ground.result"
            || (string?)reply["operation"] != step.Operation)
        {
            return null;
        }

        return reply["arguments"]?.DeepClone() as JsonObject;
    }

    public async Task<MindComposedMessage?> ComposeUserMessageAsync(
        string userText,
        string intent,
        JsonObject facts,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(facts);
        switch (FieldCompositionInjection.Resolve())
        {
            case FieldCompositionInjectionMode.Reject:
                return new MindComposedMessage("planner tool catalog schema");
            case FieldCompositionInjectionMode.Timeout:
                throw new TimeoutException("composition_injection_timeout");
            case FieldCompositionInjectionMode.Exhaust:
                return null;
        }
        JsonObject? reply = await RequestAsync(
            new JsonObject
            {
                ["type"] = "message.compose",
                ["userText"] = userText,
                ["intent"] = intent,
                ["facts"] = facts.DeepClone(),
                ["budgetSeconds"] = SelectMessageCompositionProtocolBudget(timeout),
            },
            timeout,
            cancellationToken).ConfigureAwait(false);
        if (reply is null
            || (string?)reply["type"] != "message.compose.result"
            || (string?)reply["text"] is not { Length: > 0 } text)
        {
            return null;
        }

        return new MindComposedMessage(text.Trim());
    }

    internal static MindPlanResult? ParsePlanResult(JsonObject? reply)
    {
        if (reply is null
            || (string?)reply["type"] != "plan.result"
            || (int?)reply["version"] != 1
            || (string?)reply["kind"] is not { } kind
            || kind is not ("plan" or "clarify" or "conversation")
            || (string?)reply["question"] is not { } question
            || reply["steps"] is not JsonArray rawSteps
            || rawSteps.Count > MissionPlanValidator.MaximumSteps)
        {
            return null;
        }

        var steps = new List<MindPlanStep>(rawSteps.Count);
        foreach (JsonNode? node in rawSteps)
        {
            if (node is not JsonObject raw
                || raw.Count != 6
                || (string?)raw["id"] is not { Length: > 0 } id
                || (string?)raw["operation"] is not { Length: > 0 } operation
                || (string?)raw["purpose"] is not { Length: > 0 } purpose
                || raw["dependsOn"] is not JsonArray dependencies
                || (string?)raw["argumentsMode"] is not { } argumentsMode
                || argumentsMode is not ("literal" or "after_dependencies"))
            {
                return null;
            }

            var dependsOn = new List<string>(dependencies.Count);
            foreach (JsonNode? dependency in dependencies)
            {
                if ((string?)dependency is not { Length: > 0 } value)
                {
                    return null;
                }

                dependsOn.Add(value);
            }

            JsonObject? arguments = raw["arguments"]?.DeepClone() as JsonObject;
            if (argumentsMode == "literal" && arguments is null
                || argumentsMode == "after_dependencies" && raw["arguments"] is not null)
            {
                return null;
            }

            steps.Add(new MindPlanStep(
                id,
                operation,
                purpose,
                dependsOn,
                argumentsMode,
                arguments));
        }

        if (kind == "plan" && (question.Length != 0 || steps.Count == 0)
            || kind == "clarify" && (string.IsNullOrWhiteSpace(question) || steps.Count != 0)
            || kind == "conversation" && (question.Length != 0 || steps.Count != 0))
        {
            return null;
        }

        return new MindPlanResult(kind, question, steps);
    }

    public Task<bool> VoiceStartAsync(
        TimeSpan timeout,
        CancellationToken cancellationToken) =>
        VoiceStartAsync("direct", timeout, cancellationToken);

    public async Task<bool> VoiceStartAsync(
        string mode,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        if (mode is not ("direct" or "wake"))
        {
            return false;
        }

        JsonObject? reply = await RequestAsync(
            new JsonObject { ["type"] = "voice.start", ["mode"] = mode },
            timeout,
            cancellationToken).ConfigureAwait(false);
        return reply is not null
            && (string?)reply["type"] == "voice.started"
            && (string?)reply["mode"] == mode;
    }

    public async Task<bool> VoiceStopAsync(TimeSpan timeout, CancellationToken cancellationToken)
    {
        JsonObject? reply = await RequestAsync(
            new JsonObject { ["type"] = "voice.stop" },
            timeout,
            cancellationToken).ConfigureAwait(false);
        return reply is not null && (string?)reply["type"] == "voice.stopped";
    }

    public async Task<MindVoiceStatus?> VoiceStatusAsync(
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        JsonObject? reply = await RequestAsync(
            new JsonObject { ["type"] = "voice.status" },
            timeout,
            cancellationToken).ConfigureAwait(false);
        if (reply is null
            || (string?)reply["type"] != "voice.status.result"
            || reply["status"] is not JsonObject status)
        {
            return null;
        }

        return new MindVoiceStatus(
            (bool?)status["available"] ?? false,
            (bool?)status["input"] ?? false,
            (bool?)status["stt"] ?? false,
            (bool?)status["vad"] ?? false,
            (bool?)status["tts"] ?? false,
            (bool?)status["aec"] ?? false,
            (bool?)status["ducking"] ?? false,
            (string?)status["mode"] ?? "off",
            (bool?)status["listening"] ?? false,
            (bool?)status["speaking"] ?? false);
    }

    public async Task<bool> VoiceSpeakAsync(
        string text,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(text) || text.Length > 8_192)
        {
            return false;
        }

        JsonObject? reply = await RequestAsync(
            new JsonObject { ["type"] = "voice.speak", ["text"] = text },
            timeout,
            cancellationToken).ConfigureAwait(false);
        return reply is not null
            && (string?)reply["type"] == "voice.speak.result"
            && (bool?)reply["accepted"] == true;
    }

    public async Task<bool> VoiceCancelAsync(
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        JsonObject? reply = await RequestAsync(
            new JsonObject { ["type"] = "voice.cancel" },
            timeout,
            cancellationToken).ConfigureAwait(false);
        return reply is not null && (string?)reply["type"] == "voice.cancelled";
    }

    private async Task<JsonObject?> RequestAsync(
        JsonObject request,
        TimeSpan timeout,
        CancellationToken cancellationToken,
        bool returnProtocolError = false)
    {
        // Cancellation is handled by the sidecar control plane independently
        // of model work and must never wait for an inference to finish.
        if ((string?)request["type"] is "voice.cancel" or "shutdown")
        {
            return await SendRequestAsync(request, timeout, returnProtocolError,
                cancellationToken).ConfigureAwait(false);
        }

        await _requestLock.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            return await SendRequestAsync(request, timeout, returnProtocolError,
                cancellationToken).ConfigureAwait(false);
        }
        finally
        {
            _requestLock.Release();
        }
    }

    private async Task<JsonObject?> SendRequestAsync(
        JsonObject request,
        TimeSpan timeout,
        bool returnProtocolError,
        CancellationToken cancellationToken)
    {
        if (!IsReady)
        {
            return null;
        }

        string requestId = Interlocked.Increment(ref _requestSequence)
            .ToString(System.Globalization.CultureInfo.InvariantCulture);
        request["id"] = requestId;
        string requestType = (string?)request["type"] ?? "unknown";
        string traceId = ShellTraceSink.TurnId;
        ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "mind.request.start",
            $"{requestType}.id.{requestId}.budget_ms.{(long)timeout.TotalMilliseconds}");
        var completion = new TaskCompletionSource<JsonObject>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        if (!_pending.TryAdd(requestId, completion))
        {
            return null;
        }

        try
        {
            byte[] utf8Line = SerializeRequestToUtf8(request);
            if (utf8Line.Length > MaximumLineBytes)
            {
                return null;
            }

            LocalJsonlSidecarProcess? sidecar = _sidecar;
            Process? process = sidecar?.Process;
            if (sidecar is null || process is null || process.HasExited)
            {
                _ready = false;
                return null;
            }

            await _writeLock.WaitAsync(cancellationToken).ConfigureAwait(false);
            try
            {
                await sidecar.WriteUtf8LineAsync(utf8Line, cancellationToken)
                    .ConfigureAwait(false);
            }
            finally
            {
                _writeLock.Release();
            }

            using var timeoutSource = new CancellationTokenSource(timeout);
            using var linked = CancellationTokenSource.CreateLinkedTokenSource(
                cancellationToken, timeoutSource.Token);
            JsonObject reply = await completion.Task.WaitAsync(linked.Token).ConfigureAwait(false);
            return (string?)reply["type"] == "error" && !returnProtocolError
                ? null
                : reply;
        }
        catch (Exception exception) when (exception is not OperationCanceledException
            || !cancellationToken.IsCancellationRequested)
        {
            // A late voice-cancel acknowledgement does not invalidate concurrent
            // model work. The caller receives false and the late reply is discarded.
            // Model deadlines and transport failures still trigger owner recovery.
            bool voiceCancelTimeout = exception is OperationCanceledException
                && requestType == "voice.cancel";
            if (!voiceCancelTimeout)
            {
                _ready = false;
            }

            string failure = exception is OperationCanceledException
                ? "request_timeout" : "request_io";
            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId,
                "mind.request.failed", $"{failure}.{requestType}.id.{requestId}");
            return null;
        }
        finally
        {
            _pending.TryRemove(requestId, out _);
        }
    }

    internal static byte[] SerializeRequestToUtf8(JsonObject request)
    {
        ArgumentNullException.ThrowIfNull(request);
        return JsonSerializer.SerializeToUtf8Bytes(request);
    }

    private async Task PumpAsync(
        Process process,
        TaskCompletionSource<JsonObject> helloCompletion,
        CancellationToken cancellationToken)
    {
        try
        {
            var reader = new BoundedUtf8LineReader(
                process.StandardOutput.BaseStream,
                MaximumLineBytes);
            while (!cancellationToken.IsCancellationRequested)
            {
                BoundedUtf8Line? line = await reader.ReadAsync(cancellationToken).ConfigureAwait(false);
                if (line is null)
                {
                    break;
                }

                if (line.Value.TooLarge || line.Value.Utf8 is not { } utf8)
                {
                    continue;
                }

                JsonObject? message;
                try
                {
                    message = JsonNode.Parse(utf8) as JsonObject;
                }
                catch (JsonException)
                {
                    continue;
                }

                if (message is null)
                {
                    continue;
                }

                if ((string?)message["type"] == "hello")
                {
                    helloCompletion.TrySetResult(message);
                    continue;
                }

                if ((string?)message["type"] == "voice.transcript")
                {
                    if ((string?)message["text"] is { Length: > 0 } transcript)
                    {
                        TranscriptReceived?.Invoke(transcript);
                    }

                    continue;
                }

                if ((string?)message["type"] == "voice.event")
                {
                    VoiceEventReceived?.Invoke(message);
                    continue;
                }

                if ((string?)message["type"] == "turn.signal")
                {
                    if ((string?)message["id"] is { Length: > 0 } signalRequestId
                        && _pending.ContainsKey(signalRequestId)
                        && (string?)message["text"] is { Length: > 0 } signal)
                    {
                        TurnSignalReceived?.Invoke(signal);
                    }

                    continue;
                }

                if ((string?)message["id"] is { Length: > 0 } id
                    && _pending.TryRemove(id, out var completion))
                {
                    completion.TrySetResult(message);
                }
            }
        }
        catch (Exception)
        {
            // El pump nunca propaga: la mente queda no-disponible y el shell
            // continúa por su camino determinista.
        }
        finally
        {
            _ready = false;
            helloCompletion.TrySetException(
                new IOException("El sidecar de mente terminó antes del saludo."));
            foreach (var pending in _pending)
            {
                if (_pending.TryRemove(pending.Key, out var completion))
                {
                    completion.TrySetCanceled(CancellationToken.None);
                }
            }
        }
    }

    private async Task ShutdownQuietlyAsync()
    {
        _ready = false;
        _plannerAvailable = false;
        Task? pump = _pump;
        _pump = null;
        CancellationTokenSource? pumpCancellation = _pumpCancellation;
        _pumpCancellation = null;
        LocalJsonlSidecarProcess? sidecar = _sidecar;
        _sidecar = null;
        pumpCancellation?.Cancel();
        try
        {
            if (sidecar is not null)
            {
                await sidecar.DisposeAsync().ConfigureAwait(false);
            }
        }
        finally
        {
            await ObservePumpAsync(pump).ConfigureAwait(false);
            pumpCancellation?.Dispose();
        }
    }

    private static async Task ObservePumpAsync(Task? pump)
    {
        if (pump is null)
        {
            return;
        }

        try
        {
            await pump.ConfigureAwait(false);
        }
        catch (Exception)
        {
            // Pump failures never prevent closing the owned sidecar.
        }
    }

    public async ValueTask DisposeAsync()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        await ShutdownQuietlyAsync().ConfigureAwait(false);
        _writeLock.Dispose();
    }
}
