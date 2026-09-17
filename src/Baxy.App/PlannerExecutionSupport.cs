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
    internal static bool MustRetainAmbiguousEffect(OperationResponse response)
    {
        ArgumentNullException.ThrowIfNull(response);
        return response.EffectMayHaveOccurred
            && (response.Status != OperationStatuses.Completed || !response.Verified);
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
            ["peripheral.list"] = new(StringComparer.Ordinal)
                { "kind", "name" },
            ["reminder.resolve.exact"] = new(StringComparer.Ordinal)
                { "expectedVersion", "reviewLabel" },
            // FILES1705 «crea un archivo de texto con los 5 procesos que más
            // memoria usan»: the write that follows projects its text from
            // the listing's names and measures.
            ["system.process.list"] = new(StringComparer.Ordinal)
                { "cpuUsagePercent", "name", "processes", "sort", "totalProcessorSeconds", "workingSetBytes" },
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
            "filesystem.read.text" => ["resourceId"],
            "game.install.commit" or "package.install.commit" =>
                ["confirmationId"],
            "game.purchase.commit" => ["confirmationId", "expectedPriceCents"],
            "message.send" => ["recipientId"],
            "note.read" => ["noteId"],
            "notification.dismiss" => ["reminderId", "expectedVersion"],
            "office.document.read" => ["documentId"],
            "peripheral.print" => ["deviceId"],
            "reminder.delete" => ["reminderId", "expectedVersion", "reviewLabel"],
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
