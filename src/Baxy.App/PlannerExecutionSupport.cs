using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Kernel.Planning;

namespace Baxy.App;

internal sealed class PendingMindPlanExecution
{
    internal PendingMindPlanExecution(
        string objective,
        IReadOnlyList<MindPlanStep> steps,
        int replanCount = 0)
    {
        Objective = objective;
        Steps = steps;
        ReplanCount = replanCount;
    }

    internal string Objective { get; }

    internal IReadOnlyList<MindPlanStep> Steps { get; }

    internal int NextIndex { get; set; }

    internal int ReplanCount { get; }

    internal JsonArray Observations { get; } = [];

    internal List<string> CompletedMessages { get; } = [];

    internal PreparedOperation? PendingOperation { get; set; }

    internal PendingOperationConfirmation? Confirmation { get; set; }

    internal bool PendingEffectMayHaveOccurred { get; set; }

    /// <summary>
    /// M56: the failure of an earlier step that changed nothing and ended only its own
    /// chain; the independent steps ran on and the end reports it. Not persisted: a plan
    /// never resumes across sessions.
    /// </summary>
    internal string? DeferredFailure { get; init; }

    internal MindPlanStep CurrentStep => Steps[NextIndex];

    internal bool CanAbandonConfirmation =>
        Confirmation is not null
        && !Confirmation.ReconciliationRequired
        && !PendingEffectMayHaveOccurred;

    internal void RequireConfirmation(PendingOperationConfirmation confirmation)
    {
        ArgumentNullException.ThrowIfNull(confirmation);
        if (PendingOperation is not null
            && !ReferenceEquals(PendingOperation, confirmation.Prepared))
        {
            throw new InvalidDataException(
                "La confirmación no pertenece a la operación pendiente del plan.");
        }

        PendingOperation = confirmation.Prepared;
        Confirmation = confirmation;
        PendingEffectMayHaveOccurred |= confirmation.ReconciliationRequired;
    }
}

internal sealed class PendingOperationConfirmation
{
    private PendingOperationConfirmation(
        PreparedOperation prepared,
        string token,
        DateTimeOffset expiresAtUtc,
        bool reconciliationRequired)
    {
        Prepared = prepared;
        Token = token;
        ExpiresAtUtc = expiresAtUtc;
        ReconciliationRequired = reconciliationRequired;
    }

    internal PreparedOperation Prepared { get; }

    internal string Token { get; }

    internal DateTimeOffset ExpiresAtUtc { get; }

    internal bool ReconciliationRequired { get; }

    internal static bool TryCreate(
        OperationResponse response,
        PreparedOperation prepared,
        TimeProvider timeProvider,
        out PendingOperationConfirmation? confirmation)
    {
        ArgumentNullException.ThrowIfNull(response);
        ArgumentNullException.ThrowIfNull(prepared);
        ArgumentNullException.ThrowIfNull(timeProvider);
        confirmation = null;
        if (!ConfirmationChallengeParser.TryParse(
                response,
                prepared,
                timeProvider,
                out ValidatedConfirmationChallenge challenge))
        {
            return false;
        }

        confirmation = new PendingOperationConfirmation(
            prepared,
            challenge.Token,
            challenge.ExpiresAtUtc,
            challenge.ReconciliationRequired);
        return true;
    }

    public override string ToString() =>
        $"{nameof(PendingOperationConfirmation)} {{ Operation = {Prepared.OperationName}, "
        + $"Token = [REDACTED], ExpiresAtUtc = {ExpiresAtUtc:O}, "
        + $"ReconciliationRequired = {ReconciliationRequired} }}";
}

internal sealed record MindPendingStepConstraint(
    string Operation,
    string Purpose,
    string ArgumentsMode,
    JsonObject? Arguments);

internal sealed class MindReplanSuffixContract
{
    internal MindReplanSuffixContract(
        IReadOnlyList<MindPendingStepConstraint> steps)
    {
        ArgumentNullException.ThrowIfNull(steps);
        Steps = steps;
    }

    internal IReadOnlyList<MindPendingStepConstraint> Steps { get; }

    internal JsonObject ToRecoveryJson()
    {
        var steps = new JsonArray();
        foreach (MindPendingStepConstraint step in Steps)
        {
            steps.Add(new JsonObject
            {
                ["operation"] = step.Operation,
                ["purpose"] = step.Purpose,
                ["argumentsMode"] = step.ArgumentsMode,
                ["arguments"] = step.Arguments?.DeepClone(),
            });
        }

        return new JsonObject
        {
            ["version"] = 1,
            ["steps"] = steps,
        };
    }
}

internal static class MindPlanBoundary
{
    /// <summary>
    /// M56 (v3c-final F-w06-t1, F-w06-t2): the steps after a failed read that do not depend
    /// on it, directly or through another skipped step. Only a read that changed nothing
    /// is stepped over, and only when every effect left acts on what its own producer in
    /// the remainder observes (the other window's resolve and snap): an effect with no
    /// producer of its own (typing into whatever is in front) never runs past a failure.
    /// Null otherwise: the failure ends the plan as before.
    /// </summary>
    internal static IReadOnlyList<MindPlanStep>? IndependentRemainder(
        PendingMindPlanExecution execution,
        OperationResponse response)
    {
        ArgumentNullException.ThrowIfNull(execution);
        ArgumentNullException.ThrowIfNull(response);
        if (response.EffectMayHaveOccurred
            || response.Status == OperationStatuses.Completed
            || execution.NextIndex < 0
            || execution.NextIndex >= execution.Steps.Count
            || !IsReadOnly(execution.CurrentStep.Operation))
        {
            return null;
        }

        var ended = new HashSet<string>(StringComparer.Ordinal) { execution.CurrentStep.Id };
        var kept = new List<MindPlanStep>();
        for (int index = execution.NextIndex + 1; index < execution.Steps.Count; index++)
        {
            MindPlanStep step = execution.Steps[index];
            if (step.DependsOn.Any(ended.Contains))
            {
                ended.Add(step.Id);
                continue;
            }

            kept.Add(step);
        }

        var keptIds = new HashSet<string>(kept.Select(static step => step.Id), StringComparer.Ordinal);
        return kept.Count > 0
            && kept.All(step => IsReadOnly(step.Operation) || step.DependsOn.Any(keptIds.Contains))
            ? kept
            : null;
    }

    private static bool IsReadOnly(string operation) =>
        Baxy.Kernel.Operations.ProductCatalog.TryGet(
            operation,
            out Baxy.Kernel.Operations.ProductOperationDescriptor? descriptor)
        && descriptor.Risk == OperationRisks.ReadOnly;

    /// <summary>
    /// The grounded arguments that name what a step was about, in the order one is chosen.
    /// M94 (DEV-D D-s102 «abre google keep», D-s087 the weather of «Abingdon Virginia», D-p24-t4
    /// «Hustlers» on Netflix, D-w07-t2 «1850 entre 7», D-w09-t3 the newest file of Descargas, D-p37-t3
    /// «chips»): a failed or unverified step's facts said only the cause, so the reply named the
    /// thing from the person's words and nothing showed which one was tried. Identifiers, versions
    /// and free text are never a target.
    /// </summary>
    private static readonly string[] TargetArguments =
    [
        "applicationName", "app", "appId", "title", "name", "fileName", "query", "expression", "location", "place",
        "folder", "topic",
        // M111 (DEV-F v4d F-s005, F-s014: drafts that failed with the client closed named no one): the person a
        // message was for.
        "recipient",
    ];

    private const string NotDoneKey = "notDone";
    private const int MaximumNotDone = 4;

    /// <summary>
    /// M56 (v3c-final F-w06-t1 «ninguna de las aplicaciones tenía una ventana abierta»): a
    /// failed step's facts name the application it was about, from its own grounded
    /// arguments, so the reply says which window was missing instead of guessing. M94: any
    /// step names what it was about (<see cref="TargetArguments"/>); a catalog id
    /// («windows.calculator», an AUMID) is not a name. M116: the facts also carry every
    /// argument of the step a person can read (<see cref="AttemptedArguments"/>), so the
    /// reply says what was attempted — to whom, which words, where — beside the cause.
    /// </summary>
    internal static string WithStepFacts(string message, JsonObject? arguments)
    {
        ArgumentNullException.ThrowIfNull(message);
        string? target = StepTarget(arguments);
        JsonObject? attempted = AttemptedArguments.Project(arguments);
        if (target is null && attempted is null)
        {
            return message;
        }

        JsonObject? facts = ParsedFacts(message);
        if (facts is null)
        {
            return message;
        }

        bool changed = false;
        if (target is not null && !facts.ContainsKey("target"))
        {
            facts["target"] = target;
            changed = true;
        }

        if (attempted is not null && !facts.ContainsKey(AttemptedArguments.Key))
        {
            facts[AttemptedArguments.Key] = attempted;
            changed = true;
        }

        return changed ? facts.ToJsonString() : message;
    }

    /// <summary>
    /// M116 (DEV-F v4e2 F-w30-t2, F-w30-t3, F-w30-t4, F-w58-t4: «maximízalo», «ponlo a la izquierda» with Obsidian
    /// absent or Discord closed): the plan's resolve failed and its facts named only the window looked for, never the
    /// effect that would have followed. The effects left undone by a failure (<paramref name="kept"/> still run) go with
    /// its facts as <c>notDone</c>: each one's operation, what it was about — its own target, or the failed step's when
    /// it acts on what that step was producing — and its readable arguments. Reads left undone are not listed.
    /// </summary>
    internal static string WithNotDone(
        string failure,
        PendingMindPlanExecution execution,
        IReadOnlyCollection<MindPlanStep> kept)
    {
        ArgumentNullException.ThrowIfNull(failure);
        ArgumentNullException.ThrowIfNull(execution);
        ArgumentNullException.ThrowIfNull(kept);
        if (execution.NextIndex < 0 || execution.NextIndex >= execution.Steps.Count)
        {
            return failure;
        }

        JsonObject? facts = ParsedFacts(failure);
        if (facts is null || facts.ContainsKey(NotDoneKey))
        {
            return failure;
        }

        var keptIds = new HashSet<string>(kept.Select(static step => step.Id), StringComparer.Ordinal);
        var dependents = new HashSet<string>(StringComparer.Ordinal) { execution.CurrentStep.Id };
        var notDone = new JsonArray();
        for (int index = execution.NextIndex + 1; index < execution.Steps.Count; index++)
        {
            MindPlanStep step = execution.Steps[index];
            bool dependent = step.DependsOn.Any(dependents.Contains);
            if (dependent)
            {
                dependents.Add(step.Id);
            }

            if (keptIds.Contains(step.Id) || IsReadOnly(step.Operation) || notDone.Count == MaximumNotDone)
            {
                continue;
            }

            var entry = new JsonObject { ["operation"] = step.Operation };
            if (StepTarget(step.Arguments) is { } own)
            {
                entry["target"] = own;
            }
            else if (dependent && facts["target"] is { } inherited)
            {
                entry["target"] = inherited.DeepClone();
            }

            if (AttemptedArguments.Project(step.Arguments) is { } attempted)
            {
                entry[AttemptedArguments.Key] = attempted;
            }

            notDone.Add(entry);
        }

        if (notDone.Count == 0)
        {
            return failure;
        }

        facts[NotDoneKey] = notDone;
        return facts.ToJsonString();
    }

    private static string? StepTarget(JsonObject? arguments)
    {
        foreach (string key in TargetArguments)
        {
            if (arguments?[key] is JsonValue value
                && value.TryGetValue(out string? named)
                && !string.IsNullOrWhiteSpace(named)
                && !(key == "appId" && named.IndexOfAny(['.', '!']) >= 0))
            {
                return named.Trim();
            }
        }

        return null;
    }

    private static JsonObject? ParsedFacts(string message)
    {
        try
        {
            return JsonNode.Parse(message) as JsonObject;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    /// <summary>
    /// M56: two failures of the same operation for the same reason («Word» and «Google
    /// Chrome» both without a window) are one fact with both targets; otherwise the later
    /// failure is the one that ended the plan.
    /// </summary>
    internal static string MergeFailures(string? earlier, string later)
    {
        ArgumentNullException.ThrowIfNull(later);
        if (earlier is null)
        {
            return later;
        }

        try
        {
            if (JsonNode.Parse(earlier) is JsonObject first
                && JsonNode.Parse(later) is JsonObject second
                && string.Equals((string?)first["operation"], (string?)second["operation"], StringComparison.Ordinal)
                && string.Equals((string?)first["error"], (string?)second["error"], StringComparison.Ordinal)
                && first["target"] is { } firstTarget
                && second["target"] is { } secondTarget)
            {
                var targets = new JsonArray();
                foreach (JsonNode? target in new[] { firstTarget, secondTarget })
                {
                    if (target is JsonArray many)
                    {
                        foreach (JsonNode? item in many)
                        {
                            targets.Add(item?.DeepClone());
                        }
                    }
                    else
                    {
                        targets.Add(target.DeepClone());
                    }
                }

                second["target"] = targets;
                // M116: what each one attempted and left undone stays beside its target.
                foreach (string key in new[] { AttemptedArguments.Key, NotDoneKey })
                {
                    if (Concatenated(first[key], second[key]) is { } both)
                    {
                        second[key] = both;
                    }
                    else if (key == NotDoneKey && first[key] is { } undoneBefore)
                    {
                        second[key] = undoneBefore.DeepClone();
                    }
                }

                return second.ToJsonString();
            }
        }
        catch (Exception exception) when (exception is JsonException or InvalidOperationException)
        {
            return later;
        }

        return later;
    }

    private static JsonArray? Concatenated(JsonNode? first, JsonNode? second)
    {
        if (first is null || second is null)
        {
            return null;
        }

        var both = new JsonArray();
        foreach (JsonNode? node in new[] { first, second })
        {
            foreach (JsonNode? item in node is JsonArray many ? many : new JsonArray(node.DeepClone()))
            {
                both.Add(item?.DeepClone());
            }
        }

        return both;
    }

    internal static bool MustRetainAmbiguousEffect(OperationResponse response)
    {
        ArgumentNullException.ThrowIfNull(response);
        return response.EffectMayHaveOccurred
            && (response.Status != OperationStatuses.Completed || !response.Verified);
    }

    /// <summary>
    /// Whether a failed step may ask the mind for a replacement suffix. A safe
    /// replacement repeats the pending suffix exactly (<see cref="IsSafeReplanSuffix(MindReplanSuffixContract, MindPlanResult)"/>),
    /// so for a single direct action it could only repeat the invocation that
    /// just failed. Tandas 01–05 (2026-09-23/24): all 18 such recovery plans
    /// after a failed action published nothing and held the failure 3.8 s
    /// (median, p90 6.5 s) before the person heard it.
    /// </summary>
    internal static bool MayReplan(
        PendingMindPlanExecution execution,
        OperationResponse response)
    {
        ArgumentNullException.ThrowIfNull(execution);
        ArgumentNullException.ThrowIfNull(response);
        return !response.EffectMayHaveOccurred
            && execution.ReplanCount < 2
            && execution.Steps.Count > 1;
    }

    internal static bool CanRefreshConfirmationChallenge(
        PendingMindPlanExecution execution)
    {
        ArgumentNullException.ThrowIfNull(execution);
        if (!execution.PendingEffectMayHaveOccurred
            || execution.PendingOperation is not { } pending
            || !Baxy.Kernel.Operations.ProductCatalog.TryGet(
                pending.OperationName,
                out Baxy.Kernel.Operations.ProductOperationDescriptor? descriptor))
        {
            return false;
        }

        var definition = new Baxy.Kernel.Operations.OperationDefinition(descriptor);
        return Baxy.Kernel.Policy.RiskPolicy.Evaluate(
                definition.Risk,
                operation: pending.OperationName)
            == Baxy.Kernel.Policy.PolicyDecision.RequireConfirmation;
    }

    internal static bool IsSafeReplanSuffix(
        PendingMindPlanExecution execution,
        MindPlanResult replacement)
    {
        ArgumentNullException.ThrowIfNull(execution);
        ArgumentNullException.ThrowIfNull(replacement);
        return IsSafeReplanSuffix(CapturePendingSuffix(execution), replacement);
    }

    internal static MindReplanSuffixContract CapturePendingSuffix(
        PendingMindPlanExecution execution)
    {
        ArgumentNullException.ThrowIfNull(execution);
        if (execution.NextIndex < 0 || execution.NextIndex >= execution.Steps.Count)
        {
            throw new InvalidOperationException(
                "A replan suffix requires one current pending step.");
        }

        MindPendingStepConstraint[] remaining = execution.Steps
            .Skip(execution.NextIndex)
            .Select(static step => new MindPendingStepConstraint(
                step.Operation,
                step.Purpose,
                step.ArgumentsMode,
                step.Arguments?.DeepClone().AsObject()))
            .ToArray();
        return new MindReplanSuffixContract(remaining);
    }

    internal static bool IsSafeReplanSuffix(
        MindReplanSuffixContract expected,
        MindPlanResult replacement)
    {
        ArgumentNullException.ThrowIfNull(expected);
        ArgumentNullException.ThrowIfNull(replacement);
        if (replacement.Kind != "plan"
            || replacement.Steps.Count != expected.Steps.Count)
        {
            return false;
        }

        for (int index = 0; index < expected.Steps.Count; index++)
        {
            MindPendingStepConstraint constraint = expected.Steps[index];
            MindPlanStep candidate = replacement.Steps[index];
            if (!string.Equals(
                    candidate.Operation,
                    constraint.Operation,
                    StringComparison.Ordinal)
                || !string.Equals(
                    candidate.Purpose,
                    constraint.Purpose,
                    StringComparison.Ordinal)
                || !string.Equals(
                    candidate.ArgumentsMode,
                    constraint.ArgumentsMode,
                    StringComparison.Ordinal)
                || !JsonNode.DeepEquals(candidate.Arguments, constraint.Arguments))
            {
                return false;
            }
        }

        return true;
    }

    internal static MissionPlanProposal ValidateAndConvert(
        string objective,
        MindPlanResult result)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(objective);
        ArgumentNullException.ThrowIfNull(result);
        if (result.Kind != "plan")
        {
            throw new MissionPlanValidationException("Only a plan can cross this boundary.");
        }

        var steps = new List<MissionPlanStepProposal>(result.Steps.Count);
        foreach (MindPlanStep step in result.Steps)
        {
            JsonElement? arguments = null;
            if (step.Arguments is not null)
            {
                using JsonDocument document = JsonDocument.Parse(step.Arguments.ToJsonString());
                arguments = document.RootElement.Clone();
            }

            steps.Add(new MissionPlanStepProposal(
                step.Id,
                step.Operation,
                step.Purpose,
                step.DependsOn,
                step.ArgumentsMode,
                arguments));
        }

        var proposal = new MissionPlanProposal(1, objective, steps);
        MissionPlanValidator.Validate(proposal);
        return proposal;
    }

    internal static void ValidateGroundedArguments(string operation, JsonObject arguments)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(operation);
        ArgumentNullException.ThrowIfNull(arguments);
        if (!Baxy.Kernel.Operations.ProductCatalog.TryGet(
                operation,
                out Baxy.Kernel.Operations.ProductOperationDescriptor? descriptor)
            || descriptor.ToolExposure != Baxy.Kernel.Operations.ToolExposure.Public
            || operation.StartsWith("memory.", StringComparison.Ordinal))
        {
            throw new MissionPlanValidationException(
                "Grounded arguments target an operation outside the planning boundary.");
        }

        using JsonDocument document = JsonDocument.Parse(arguments.ToJsonString());
        if (!Baxy.Kernel.Operations.OperationArgumentValidator.IsValid(
                document.RootElement,
                descriptor.ArgumentsSchema))
        {
            throw new MissionPlanValidationException(
                "Grounded arguments do not satisfy the exact operation schema.");
        }
    }

    internal static bool ArgumentsSatisfyExactSchema(
        string operation,
        JsonObject arguments)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(operation);
        ArgumentNullException.ThrowIfNull(arguments);
        if (!Baxy.Kernel.Operations.ProductCatalog.TryGet(
                operation,
                out Baxy.Kernel.Operations.ProductOperationDescriptor? descriptor)
            || descriptor.ToolExposure != Baxy.Kernel.Operations.ToolExposure.Public
            || operation.StartsWith("memory.", StringComparison.Ordinal))
        {
            return false;
        }

        using JsonDocument document = JsonDocument.Parse(arguments.ToJsonString());
        return Baxy.Kernel.Operations.OperationArgumentValidator.IsValid(
            document.RootElement,
            descriptor.ArgumentsSchema);
    }
}

internal static class PlanObservationProjector
{
    private const int MaximumDepth = 5;
    private const int MaximumArrayItems = 32;
    private const int MaximumStringLength = 2_048;
    private static readonly HashSet<string> SafeFields = new(StringComparer.Ordinal)
    {
        "available",
        "backupId",
        "captureId",
        "connected",
        "count",
        "devices",
        "deviceId",
        "enabled",
        "entries",
        "exists",
        "fileId",
        "files",
        "hash",
        "installed",
        "items",
        "isTrashed",
        "jobId",
        "noteId",
        "notes",
        "processId",
        "recipientId",
        "reminderId",
        "reminders",
        "resourceId",
        "resourceUri",
        "results",
        "revision",
        "routineId",
        "routines",
        "sessionId",
        "sha256",
        "state",
        "status",
        "taskId",
        "tasks",
        "totalCount",
        "version",
        "windowId",
        "windows",
    };
    private static readonly Dictionary<string, HashSet<string>> OperationSafeFields =
        new Dictionary<string, HashSet<string>>(StringComparer.Ordinal)
        {
            ["bluetooth.device.list"] = new(StringComparer.Ordinal)
                { "canPair", "name", "paired" },
            ["browser.page.read"] = new(StringComparer.Ordinal)
                { "truncated", "url" },
            ["browser.tabs.list"] = new(StringComparer.Ordinal)
                { "tabs", "targetId", "truncated", "url" },
            ["filesystem.list"] = new(StringComparer.Ordinal)
                { "relativePath" },
            ["filesystem.search"] = new(StringComparer.Ordinal)
                { "relativePath" },
            ["game.catalog.list"] = new(StringComparer.Ordinal)
                { "games", "name" },
            ["game.purchase.prepare"] = new(StringComparer.Ordinal)
                { "expectedPriceCents" },
            // H0096 «aprieta en Among Us»: el clic mira la pantalla antes de
            // pulsar, y lo que ve sólo sirve si sale del paso. Sin estos
            // campos la observación proyectada llegaba vacía: los ojos leían
            // 47 controles de la ventana y el paso siguiente no veía ninguno.
            ["input.visible.controls"] = new(StringComparer.Ordinal)
                { "authority", "controlCount", "controls", "kind", "name", "window" },
            ["peripheral.list"] = new(StringComparer.Ordinal)
                { "kind", "name" },
            ["reminder.resolve.exact"] = new(StringComparer.Ordinal)
                { "expectedVersion", "reviewLabel" },
            // FILES1705 «crea un archivo de texto con los 5 procesos que más
            // memoria usan»: the write that follows projects its text from
            // the listing's names and measures.
            // task.delete copies the version and review label the verified
            // resolver returned, exactly as reminder.delete does.
            ["task.resolve.exact"] = new(StringComparer.Ordinal)
                { "expectedVersion", "reviewLabel" },
            ["system.process.list"] = new(StringComparer.Ordinal)
                { "cpuUsagePercent", "name", "processes", "sort", "totalProcessorSeconds", "workingSetBytes" },
            // MEME2053 «Tienes algun meme?»: the open that follows copies the
            // folder and the name of the file the download wrote.
            ["web.download"] = new(StringComparer.Ordinal)
                { "folder", "name" },
            ["web.search"] = new(StringComparer.Ordinal)
                { "url" },
            ["wifi.profile.list"] = new(StringComparer.Ordinal)
                { "label", "profiles" },
            // The reviewed-close shape reads the page scope and the foreground
            // flag of the window observation; without them the projected
            // observation could never establish one candidate (CLOSE1217/000).
            ["window.active"] = new(StringComparer.Ordinal)
                { "foreground" },
            ["window.resolve"] = new(StringComparer.Ordinal)
                { "complete", "foreground", "hasMore", "limit", "nextOffset", "observedCount", "offset" },
        };

    internal static JsonObject Create(
        string stepId,
        string operation,
        OperationResponse response)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(stepId);
        ArgumentException.ThrowIfNullOrWhiteSpace(operation);
        ArgumentNullException.ThrowIfNull(response);
        var observation = new JsonObject
        {
            ["stepId"] = stepId,
            ["operation"] = operation,
            ["verified"] = response.Verified,
            ["status"] = response.Status,
        };
        if (response.Verified && response.Result is { } result)
        {
            observation["result"] = Project(result, operation, depth: 0);
        }

        return observation;
    }

    internal static bool TrySelectVerifiedDependencies(
        MindPlanStep step,
        JsonArray observations,
        out JsonArray selected)
    {
        ArgumentNullException.ThrowIfNull(step);
        ArgumentNullException.ThrowIfNull(observations);
        selected = [];
        if (step.ArgumentsMode != "after_dependencies"
            || step.DependsOn.Count == 0
            || step.DependsOn.Distinct(StringComparer.Ordinal).Count()
                != step.DependsOn.Count)
        {
            return false;
        }

        foreach (string dependency in step.DependsOn)
        {
            JsonObject[] matches = observations
                .OfType<JsonObject>()
                .Where(observation =>
                    string.Equals(
                        (string?)observation["stepId"],
                        dependency,
                        StringComparison.Ordinal)
                    && (bool?)observation["verified"] == true
                    && string.Equals(
                        (string?)observation["status"],
                        OperationStatuses.Completed,
                        StringComparison.Ordinal))
                .ToArray();
            if (matches.Length != 1)
            {
                selected = [];
                return false;
            }

            selected.Add(matches[0].DeepClone());
        }

        return true;
    }

    internal static bool TryGroundIdentityArguments(
        MindPlanStep step,
        JsonArray observations,
        out JsonObject? arguments)
    {
        ArgumentNullException.ThrowIfNull(step);
        ArgumentNullException.ThrowIfNull(observations);
        arguments = null;
        string[] fields = DeterministicDependencyFields(step.Operation);
        if (fields.Length == 0)
        {
            return false;
        }

        JsonObject[] producerResults = VerifiedIdentityProducerResults(step, observations);
        if (producerResults.Length == 0)
        {
            return false;
        }

        var grounded = new JsonObject();
        foreach (string field in fields)
        {
            JsonNode[] values = producerResults
                .SelectMany(result => CollectFieldNodes(result, field))
                .GroupBy(static value => value.ToJsonString(), StringComparer.Ordinal)
                .Select(static group => group.First())
                .ToArray();
            if (values.Length == 1)
            {
                grounded[field] = values[0].DeepClone();
            }
        }
        if (grounded.Count == 0)
        {
            return false;
        }

        arguments = grounded;
        return true;
    }

    internal static bool IsVerifiedEmptyFileSearch(MindPlanStep step, JsonArray observations)
    {
        ArgumentNullException.ThrowIfNull(step);
        ArgumentNullException.ThrowIfNull(observations);
        if (step.Operation != "filesystem.read.text")
        {
            return false;
        }

        JsonObject[] results = VerifiedIdentityProducerResults(step, observations);
        // An explicit zero is a completed search result, not missing data.
        // Missing, inconsistent or unverified results cannot prove no matches.
        return results.Length > 0 && results.All(static result =>
            result["entries"] is JsonArray { Count: 0 }
            && result["count"] is JsonValue count
            && count.TryGetValue<int>(out int value) && value == 0);
    }

    /// <summary>
    /// Tanda 4c «add flour to my shopping list if it's not already on it»: the
    /// add waits on the verified search of that list (a literal step that
    /// depends on it) and runs only when the search found nothing. A search
    /// that found the entry ends the plan with that read; a missing,
    /// unverified or unreadable count never skips the add.
    /// </summary>
    internal static bool IsGuardedByAFoundEntry(MindPlanStep step, JsonArray observations)
    {
        ArgumentNullException.ThrowIfNull(step);
        ArgumentNullException.ThrowIfNull(observations);
        if (step.Operation != "task.create"
            || step.ArgumentsMode != "literal"
            || step.DependsOn.Count == 0)
        {
            return false;
        }

        var dependencies = new HashSet<string>(step.DependsOn, StringComparer.Ordinal);
        return observations.OfType<JsonObject>().Any(observation =>
            (string?)observation["stepId"] is { } stepId && dependencies.Contains(stepId)
            && string.Equals((string?)observation["operation"], "task.search", StringComparison.Ordinal)
            && (bool?)observation["verified"] == true
            && string.Equals((string?)observation["status"], OperationStatuses.Completed, StringComparison.Ordinal)
            && observation["result"] is JsonObject { } result
            && result["count"] is JsonValue count
            && count.TryGetValue<int>(out int value) && value > 0);
    }

    private static JsonObject[] VerifiedIdentityProducerResults(MindPlanStep step, JsonArray observations)
    {
        if (step.ArgumentsMode != "after_dependencies" || step.DependsOn.Count == 0)
        {
            return [];
        }
        var dependencies = new HashSet<string>(step.DependsOn, StringComparer.Ordinal);
        string[] producers = MissionPlanValidator.DependencyProducerOperations(step.Operation);
        return observations.OfType<JsonObject>()
            .Where(observation =>
                (bool?)observation["verified"] == true
                && string.Equals((string?)observation["status"], OperationStatuses.Completed, StringComparison.Ordinal)
                && producers.Contains((string?)observation["operation"], StringComparer.Ordinal)
                && (string?)observation["stepId"] is { } stepId && dependencies.Contains(stepId))
            .Select(observation => observation["result"] as JsonObject)
            .Where(static result => result is not null)
            .Cast<JsonObject>()
            .ToArray();
    }

    private static string[] DeterministicDependencyFields(string operation) =>
        operation switch
        {
            "app.close" or "window.focus" or "window.maximize"
                or "window.minimize" or "window.move" or "window.resize"
                or "window.restore" or "window.snap" => ["windowId"],
            "bluetooth.device.pair" or "peripheral.scan" => ["deviceId"],
            "file.open" => ["folder", "name"],
            "filesystem.read.text" => ["resourceId"],
            "game.install.commit" or "package.install.commit" =>
                ["confirmationId"],
            "game.purchase.commit" => ["confirmationId", "expectedPriceCents"],
            "message.send" => ["recipientId"],
            // M160: the rest of a note.update (revision, title, content) comes from the mind, read off the same read.
            "note.read" or "note.update" => ["noteId"],
            "notification.dismiss" => ["reminderId", "expectedVersion"],
            "office.document.read" => ["documentId"],
            "peripheral.print" => ["deviceId"],
            "reminder.delete" => ["reminderId", "expectedVersion", "reviewLabel"],
            "task.delete" => ["taskId", "expectedVersion", "reviewLabel"],
            // M76 (DEV-D v3l D-w17-t2): the version the resolver verified, never one asked of the person.
            "task.complete" or "task.reopen" => ["taskId", "expectedVersion"],
            "wifi.connect" => ["profileId"],
            _ => [],
        };

    private static IEnumerable<JsonNode> CollectFieldNodes(
        JsonNode node,
        string field)
    {
        if (node is JsonObject objectNode)
        {
            foreach ((string name, JsonNode? child) in objectNode)
            {
                if (string.Equals(name, field, StringComparison.Ordinal)
                    && child is JsonValue)
                {
                    yield return child;
                }

                if (child is not null)
                {
                    foreach (JsonNode nested in CollectFieldNodes(child, field))
                    {
                        yield return nested;
                    }
                }
            }
        }
        else if (node is JsonArray arrayNode)
        {
            foreach (JsonNode? child in arrayNode)
            {
                if (child is null)
                {
                    continue;
                }

                foreach (JsonNode nested in CollectFieldNodes(child, field))
                {
                    yield return nested;
                }
            }
        }
    }

    internal static bool ArgumentsUseVerifiedDependencyAuthority(
        string operation,
        JsonObject arguments,
        JsonArray observations)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(operation);
        ArgumentNullException.ThrowIfNull(arguments);
        ArgumentNullException.ThrowIfNull(observations);
        if (string.Equals(operation, "filesystem.write.text", StringComparison.Ordinal))
        {
            return TextIsProjectedFromProcessListing(arguments, observations);
        }

        string[] authorityFields = MissionPlanValidator
            .DependencyAuthorityFields(operation);
        if (authorityFields.Length == 0)
        {
            return false;
        }

        foreach (string field in authorityFields)
        {
            HashSet<string> argumentValues = CollectFieldValues(arguments, field);
            HashSet<string> observedValues = CollectFieldValues(observations, field);
            if (argumentValues.Count == 0
                || !argumentValues.IsSubsetOf(observedValues))
            {
                return false;
            }
        }

        return true;
    }

    // FILES1705: a deferred write carries no identity to copy; its authority is
    // that every listed line is an observed process name with one of that
    // listing's observed measures, exactly as the verified producer returned them.
    private static bool TextIsProjectedFromProcessListing(
        JsonObject arguments,
        JsonArray observations)
    {
        if (arguments["text"] is not JsonValue textValue
            || !textValue.TryGetValue<string>(out string? text)
            || string.IsNullOrWhiteSpace(text))
        {
            return false;
        }

        HashSet<string> names = CollectFieldValues(observations, "name");
        var measures = new HashSet<string>(StringComparer.Ordinal);
        foreach (string field in new[] { "workingSetBytes", "cpuUsagePercent", "totalProcessorSeconds" })
        {
            measures.UnionWith(CollectFieldValues(observations, field));
        }

        string[] lines = text.Split('\n', StringSplitOptions.RemoveEmptyEntries)
            .Select(static line => line.TrimEnd('\r'))
            .Where(static line => line.Length > 0)
            .ToArray();
        if (lines.Length < 2 || names.Count == 0 || measures.Count == 0)
        {
            return false;
        }

        foreach (string line in lines.Skip(1))
        {
            int separator = line.LastIndexOf(": ", StringComparison.Ordinal);
            if (separator <= 0)
            {
                return false;
            }

            string name = JsonValue.Create(line[..separator]).ToJsonString();
            string measure = line[(separator + 2)..].Trim();
            if (!names.Contains(name) || !measures.Contains(measure))
            {
                return false;
            }
        }

        return true;
    }

    private static HashSet<string> CollectFieldValues(JsonNode node, string field)
    {
        var values = new HashSet<string>(StringComparer.Ordinal);
        Visit(node);
        return values;

        void Visit(JsonNode? current)
        {
            if (current is JsonObject objectNode)
            {
                foreach ((string name, JsonNode? child) in objectNode)
                {
                    if (string.Equals(name, field, StringComparison.Ordinal))
                    {
                        AddScalars(child);
                    }

                    Visit(child);
                }
            }
            else if (current is JsonArray arrayNode)
            {
                foreach (JsonNode? child in arrayNode)
                {
                    Visit(child);
                }
            }
        }

        void AddScalars(JsonNode? current)
        {
            if (current is JsonArray arrayNode)
            {
                foreach (JsonNode? child in arrayNode)
                {
                    AddScalars(child);
                }
            }
            else if (current is JsonValue)
            {
                values.Add(current.ToJsonString());
            }
        }
    }

    private static JsonNode? Project(JsonElement value, string operation, int depth)
    {
        if (depth > MaximumDepth)
        {
            return null;
        }

        switch (value.ValueKind)
        {
            case JsonValueKind.Object:
                var projected = new JsonObject();
                foreach (JsonProperty property in value.EnumerateObject())
                {
                    if (!IsSafeField(operation, property.Name))
                    {
                        continue;
                    }

                    JsonNode? child = Project(property.Value, operation, depth + 1);
                    if (child is not null)
                    {
                        projected[property.Name] = child;
                    }
                }

                return projected;
            case JsonValueKind.Array:
                var array = new JsonArray();
                foreach (JsonElement item in value.EnumerateArray().Take(MaximumArrayItems))
                {
                    JsonNode? child = Project(item, operation, depth + 1);
                    if (child is not null)
                    {
                        array.Add(child);
                    }
                }

                return array;
            case JsonValueKind.String:
                string text = value.GetString()!;
                return JsonValue.Create(
                    text.Length <= MaximumStringLength
                        ? text
                        : text[..MaximumStringLength]);
            case JsonValueKind.Number:
                return JsonNode.Parse(value.GetRawText());
            case JsonValueKind.True:
                return JsonValue.Create(true);
            case JsonValueKind.False:
                return JsonValue.Create(false);
            case JsonValueKind.Null:
                return JsonValue.Create((string?)null);
            default:
                return null;
        }
    }

    private static bool IsSafeField(string operation, string name) =>
        SafeFields.Contains(name)
        || OperationSafeFields.TryGetValue(operation, out HashSet<string>? fields)
            && fields.Contains(name)
        || name.EndsWith("Id", StringComparison.Ordinal)
        || name.EndsWith("Ids", StringComparison.Ordinal);
}
