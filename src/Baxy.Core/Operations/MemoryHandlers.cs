using System.Globalization;
using System.Numerics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization.Metadata;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Memory;
using Baxy.Security.Windows;

namespace Baxy.Core.Operations;

internal static class MemoryOperationIds
{
    internal const string Enable = "memory.enable";
    internal const string Disable = "memory.disable";
    internal const string Save = "memory.save";
    internal const string SensitiveSave = "memory.sensitive.save";
    internal const string Forget = "memory.forget";
    internal const string SessionClear = "memory.session.clear";
    internal const string Export = "memory.export";
    internal const string Correct = "memory.correct";
    internal const string Recall = "memory.recall";
    internal const string List = "memory.list";
    internal const string Status = "memory.status";
}

internal static class MemoryHandlers
{
    internal static IReadOnlyList<IOperationHandler> Create(
        IMemoryStore store,
        BoundProtectedJsonCodec codec,
        TimeProvider? timeProvider = null,
        IMemoryExportWriter? exportWriter = null)
    {
        ArgumentNullException.ThrowIfNull(store);
        ArgumentNullException.ThrowIfNull(codec);
        TimeProvider clock = timeProvider ?? TimeProvider.System;
        IMemoryExportWriter exports = exportWriter ?? new LocalMemoryExportWriter();
        return
        [
            new MemoryOperationHandler(
                store,
                codec,
                exports,
                clock,
                MemoryOperationIds.Enable),
            new MemoryOperationHandler(
                store,
                codec,
                exports,
                clock,
                MemoryOperationIds.Disable),
            new MemoryOperationHandler(
                store,
                codec,
                exports,
                clock,
                MemoryOperationIds.Save),
            new MemoryOperationHandler(
                store,
                codec,
                exports,
                clock,
                MemoryOperationIds.SensitiveSave),
            new MemoryOperationHandler(
                store,
                codec,
                exports,
                clock,
                MemoryOperationIds.Forget),
            new MemoryOperationHandler(
                store,
                codec,
                exports,
                clock,
                MemoryOperationIds.SessionClear),
            new MemoryOperationHandler(
                store,
                codec,
                exports,
                clock,
                MemoryOperationIds.Export),
            new MemoryOperationHandler(
                store,
                codec,
                exports,
                clock,
                MemoryOperationIds.Correct),
            new MemoryOperationHandler(
                store,
                codec,
                exports,
                clock,
                MemoryOperationIds.Recall),
            new MemoryOperationHandler(
                store,
                codec,
                exports,
                clock,
                MemoryOperationIds.List),
            new MemoryOperationHandler(
                store,
                codec,
                exports,
                clock,
                MemoryOperationIds.Status),
        ];
    }
}

internal sealed class MemoryOperationHandler : IOperationHandler
{
    private const int PayloadVersion = 1;
    private const int MaximumListPageSize = 100;
    private const int MaximumCanonicalNumberCharacters = 8192;
    private static readonly TimeSpan TemporaryLifetime = TimeSpan.FromHours(24);
    private readonly IMemoryStore _store;
    private readonly BoundProtectedJsonCodec _codec;
    private readonly IMemoryExportWriter _exportWriter;
    private readonly TimeProvider _timeProvider;

    internal MemoryOperationHandler(
        IMemoryStore store,
        BoundProtectedJsonCodec codec,
        IMemoryExportWriter exportWriter,
        TimeProvider timeProvider,
        string operation)
    {
        _store = store ?? throw new ArgumentNullException(nameof(store));
        _codec = codec ?? throw new ArgumentNullException(nameof(codec));
        _exportWriter = exportWriter ?? throw new ArgumentNullException(nameof(exportWriter));
        _timeProvider = timeProvider ?? throw new ArgumentNullException(nameof(timeProvider));
        Definition = ProductCatalog.CreateDefinition(operation);
    }

    public OperationDefinition Definition { get; }

    public ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        try
        {
            using OpenedBoundProtectedJson opened = _codec.OpenArguments(
                invocation.Arguments,
                Definition.Name,
                invocation.MissionId,
                invocation.InvocationId);
            OperationOutcome outcome = ExecuteOpened(invocation, opened);
            return ValueTask.FromResult(outcome);
        }
        catch (ProtectedPayloadException)
        {
            return ValueTask.FromResult(Failure("memory_protection_failed"));
        }
        catch (MemoryDisabledException)
        {
            return ValueTask.FromResult(Failure("memory_disabled"));
        }
        catch (MemoryNotFoundException)
        {
            return ValueTask.FromResult(Failure("memory_not_found"));
        }
        catch (MemoryInvocationConflictException)
        {
            return ValueTask.FromResult(Failure("memory_invocation_conflict"));
        }
        catch (MemoryConflictException)
        {
            return ValueTask.FromResult(Failure("memory_conflict"));
        }
        catch (MemoryCapacityException)
        {
            return ValueTask.FromResult(Failure("memory_capacity_reached"));
        }
        catch (MemoryStoreCorruptException)
        {
            return ValueTask.FromResult(Failure("memory_store_unavailable"));
        }
        catch (UnsafeMemoryStorePathException)
        {
            return ValueTask.FromResult(Failure("memory_store_unavailable"));
        }
        catch (MemoryExportConflictException)
        {
            return ValueTask.FromResult(Failure("memory_export_conflict"));
        }
        catch (MemoryExportException)
        {
            return ValueTask.FromResult(Failure("memory_export_unavailable"));
        }
        catch (Exception exception) when (exception is JsonException
            or ArgumentException
            or FormatException
            or OverflowException)
        {
            return ValueTask.FromResult(Failure("invalid_arguments"));
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException
            or CryptographicException)
        {
            return ValueTask.FromResult(Failure("memory_store_unavailable"));
        }
    }

    private OperationOutcome ExecuteOpened(
        OperationInvocation invocation,
        OpenedBoundProtectedJson opened) => Definition.Name switch
        {
            MemoryOperationIds.Enable => Configure(invocation, opened, enabled: true),
            MemoryOperationIds.Disable => Configure(invocation, opened, enabled: false),
            MemoryOperationIds.Save => Save(invocation, opened, sensitiveWire: false),
            MemoryOperationIds.SensitiveSave => Save(invocation, opened, sensitiveWire: true),
            MemoryOperationIds.Forget => Forget(invocation, opened),
            MemoryOperationIds.SessionClear => ClearSession(invocation, opened),
            MemoryOperationIds.Export => Export(invocation, opened),
            MemoryOperationIds.Correct => Correct(invocation, opened),
            MemoryOperationIds.Recall => Recall(invocation, opened),
            MemoryOperationIds.List => List(invocation, opened),
            MemoryOperationIds.Status => Status(invocation, opened),
            _ => Failure("unknown_operation"),
        };

    private OperationOutcome Configure(
        OperationInvocation invocation,
        OpenedBoundProtectedJson opened,
        bool enabled)
    {
        JsonElement payload = opened.Payload;
        RequireExactProperties(payload, ["version", "enabled"]);
        RequireVersion(payload);
        if (!payload.TryGetProperty("enabled", out JsonElement enabledElement)
            || enabledElement.ValueKind is not (JsonValueKind.True or JsonValueKind.False)
            || enabledElement.GetBoolean() != enabled)
        {
            throw new JsonException("The configuration state does not match the operation.");
        }

        MemoryConfigurationResult result = _store.Configure(
            new MemoryConfigureRequest(invocation.InvocationId, enabled));
        MemoryStatusResult status = _store.Status(new MemoryStatusRequest());
        if (status.Enabled != result.Enabled)
        {
            return Failure("verification_failed", effectMayHaveOccurred: true);
        }

        return Success(
            invocation,
            opened.SessionId,
            new MemoryConfigurationWireResult(PayloadVersion, result.Enabled, result.Replayed),
            MemoryHandlersJsonContext.Default.MemoryConfigurationWireResult);
    }

    private OperationOutcome Save(
        OperationInvocation invocation,
        OpenedBoundProtectedJson opened,
        bool sensitiveWire)
    {
        JsonElement payload = opened.Payload;
        RequireAllowedProperties(
            payload,
            ["version", "selector", "value", "kind", "retention", "sensitivity", "tags"],
            ["expiryPolicy"]);
        RequireVersion(payload);
        string selector = RequiredString(payload, "selector");
        string value = CanonicalScalar(RequiredProperty(payload, "value"));
        _ = NormalizeSelectorForComparison(selector);
        ValidateMemoryValue(value);
        MemoryKind kind = ParseKind(RequiredString(payload, "kind"));
        MemoryRetention retention = ParseRetention(RequiredString(payload, "retention"));
        MemorySensitivity sensitivity = ParseSensitivity(RequiredString(payload, "sensitivity"));
        if (sensitiveWire != sensitivity is MemorySensitivity.Sensitive or MemorySensitivity.Secret)
        {
            throw new JsonException("The sensitivity does not match the operation risk.");
        }

        string[] tags = RequiredStringArray(payload, "tags", LocalMemoryStore.MaximumTags);
        foreach (string tag in tags)
        {
            ValidateTag(tag);
        }
        string? expiryPolicy = OptionalString(payload, "expiryPolicy");
        DateTimeOffset now = _timeProvider.GetUtcNow().ToUniversalTime();
        DateTimeOffset? expiresAtUtc;
        string? storeSessionId;
        switch (retention)
        {
            case MemoryRetention.Persistent when expiryPolicy is null:
                expiresAtUtc = null;
                storeSessionId = null;
                break;
            case MemoryRetention.Session when string.Equals(
                expiryPolicy,
                "session_end",
                StringComparison.Ordinal):
                _ = _store.BeginSession(new MemoryBeginSessionRequest(opened.SessionId));
                expiresAtUtc = null;
                storeSessionId = opened.SessionId;
                break;
            case MemoryRetention.Temporary when string.Equals(
                expiryPolicy,
                "after_relevance_window",
                StringComparison.Ordinal):
                _ = _store.BeginSession(new MemoryBeginSessionRequest(opened.SessionId));
                expiresAtUtc = now.Add(TemporaryLifetime);
                storeSessionId = null;
                break;
            default:
                throw new JsonException("The retention fields are inconsistent.");
        }

        MemorySaveResult result = _store.Save(new MemorySaveRequest(
            invocation.InvocationId,
            selector,
            selector,
            value,
            kind,
            sensitivity,
            retention,
            tags,
            expiresAtUtc,
            invocation.MissionId,
            now,
            storeSessionId));
        if (!SavedRecordMatches(result, value, storeSessionId))
        {
            return Failure("verification_failed", effectMayHaveOccurred: true);
        }

        return Success(
            invocation,
            opened.SessionId,
            new MemoryMutationWireResult(
                PayloadVersion,
                result.RecordId.ToString("D"),
                result.Revision,
                result.Selector,
                result.Replayed),
            MemoryHandlersJsonContext.Default.MemoryMutationWireResult);
    }

    private OperationOutcome Forget(
        OperationInvocation invocation,
        OpenedBoundProtectedJson opened)
    {
        JsonElement payload = opened.Payload;
        RequireExactProperties(
            payload,
            ["version", "scope", "selector", "confirmationRequired"]);
        RequireVersion(payload);
        if (!RequiredBoolean(payload, "confirmationRequired"))
        {
            throw new JsonException("A destructive forget request must require confirmation.");
        }

        string scope = RequiredString(payload, "scope");
        string? selector = OptionalNullableString(payload, "selector");
        MemoryForgetRequest request = scope switch
        {
            "exact" when selector is not null => new MemoryForgetRequest(
                invocation.InvocationId,
                MemoryForgetScope.Exact,
                Selector: selector),
            "kind" when selector is not null => new MemoryForgetRequest(
                invocation.InvocationId,
                MemoryForgetScope.Kind,
                Kind: ParseKindSelector(selector)),
            "topic" when selector is not null => new MemoryForgetRequest(
                invocation.InvocationId,
                MemoryForgetScope.Topic,
                Topic: selector),
            "all" when selector is null => new MemoryForgetRequest(
                invocation.InvocationId,
                MemoryForgetScope.All),
            _ => throw new JsonException("The forget scope is invalid."),
        };
        MemoryForgetResult result = _store.Forget(request);
        if (!ForgottenStateMatches(request, result, opened.SessionId))
        {
            return Failure("verification_failed", effectMayHaveOccurred: true);
        }

        return Success(
            invocation,
            opened.SessionId,
            new MemoryForgetWireResult(PayloadVersion, result.DeletedCount, result.Replayed),
            MemoryHandlersJsonContext.Default.MemoryForgetWireResult);
    }

    private OperationOutcome ClearSession(
        OperationInvocation invocation,
        OpenedBoundProtectedJson opened)
    {
        JsonElement payload = opened.Payload;
        RequireExactProperties(
            payload,
            ["version", "scope", "selector", "confirmationRequired", "mustNotDeletePersistent"]);
        RequireVersion(payload);
        if (!string.Equals(RequiredString(payload, "scope"), "session", StringComparison.Ordinal)
            || OptionalNullableString(payload, "selector") is not null
            || RequiredBoolean(payload, "confirmationRequired")
            || !RequiredBoolean(payload, "mustNotDeletePersistent"))
        {
            throw new JsonException("The session-clear contract is invalid.");
        }

        _ = _store.BeginSession(new MemoryBeginSessionRequest(opened.SessionId));
        MemoryForgetResult result = _store.Forget(new MemoryForgetRequest(
            invocation.InvocationId,
            MemoryForgetScope.Session,
            SessionId: opened.SessionId));
        if (!ForgottenStateMatches(
                new MemoryForgetRequest(
                    invocation.InvocationId,
                    MemoryForgetScope.Session,
                    SessionId: opened.SessionId),
                result,
                opened.SessionId))
        {
            return Failure("verification_failed", effectMayHaveOccurred: true);
        }

        return Success(
            invocation,
            opened.SessionId,
            new MemoryForgetWireResult(PayloadVersion, result.DeletedCount, result.Replayed),
            MemoryHandlersJsonContext.Default.MemoryForgetWireResult);
    }

    private OperationOutcome Export(
        OperationInvocation invocation,
        OpenedBoundProtectedJson opened)
    {
        JsonElement payload = opened.Payload;
        RequireExactProperties(payload, ["version", "destination", "includeSecrets"]);
        RequireVersion(payload);
        if (!string.Equals(RequiredString(payload, "destination"), "documents", StringComparison.Ordinal)
            || RequiredBoolean(payload, "includeSecrets"))
        {
            throw new JsonException("The export policy is invalid.");
        }

        _ = _store.BeginSession(new MemoryBeginSessionRequest(opened.SessionId));
        MemoryRecord[] records = _store.List(new MemoryListRequest(
            opened.SessionId,
            MaximumResults: LocalMemoryStore.MaximumListResults)).Records.ToArray();
        MemoryExportResult result = _exportWriter.Export(new MemoryExportRequest(
            invocation.InvocationId,
            records));
        if (!_exportWriter.Verify(new MemoryExportVerificationRequest(
                invocation.InvocationId,
                result.Path,
                result.RecordCount,
                result.Sha256)))
        {
            return Failure("verification_failed", effectMayHaveOccurred: true);
        }

        return Success(
            invocation,
            opened.SessionId,
            new MemoryExportWireResult(
                PayloadVersion,
                result.Path,
                result.RecordCount,
                result.Sha256,
                result.Replayed),
            MemoryHandlersJsonContext.Default.MemoryExportWireResult);
    }

    private OperationOutcome Correct(
        OperationInvocation invocation,
        OpenedBoundProtectedJson opened)
    {
        JsonElement payload = opened.Payload;
        RequireAllowedProperties(
            payload,
            ["version", "selector", "value", "retention"],
            ["expectedValue", "kind"]);
        RequireVersion(payload);
        string selector = RequiredString(payload, "selector");
        string newValue = CanonicalScalar(RequiredProperty(payload, "value"));
        string normalizedSelector = NormalizeSelectorForComparison(selector);
        ValidateMemoryValue(newValue);
        string? expectedValue = payload.TryGetProperty("expectedValue", out JsonElement expected)
            ? CanonicalScalar(expected)
            : null;
        if (expectedValue is not null)
        {
            ValidateMemoryValue(expectedValue);
        }
        MemoryRetention retention = ParseRetention(RequiredString(payload, "retention"));
        MemoryKind? expectedKind = payload.TryGetProperty("kind", out JsonElement kindElement)
            ? ParseKind(RequireString(kindElement))
            : null;

        _ = _store.BeginSession(new MemoryBeginSessionRequest(opened.SessionId));
        MemoryRecord[] exact = _store.Recall(new MemoryRecallRequest(
                selector,
                opened.SessionId,
                LocalMemoryStore.MaximumRecallResults))
            .Records
            .Where(record => string.Equals(
                    record.Selector,
                    normalizedSelector,
                    StringComparison.Ordinal)
                && record.Retention == retention)
            .ToArray();
        if (exact.Length == 0)
        {
            throw new MemoryNotFoundException();
        }

        if (exact.Length != 1
            || (expectedKind.HasValue && exact[0].Kind != expectedKind.Value)
            || (expectedValue is not null
                && !string.Equals(exact[0].Value, expectedValue, StringComparison.Ordinal)))
        {
            throw new MemoryConflictException();
        }

        MemoryRecord current = exact[0];
        DateTimeOffset now = _timeProvider.GetUtcNow().ToUniversalTime();
        MemoryCorrectResult result = _store.Correct(new MemoryCorrectRequest(
            invocation.InvocationId,
            selector,
            newValue,
            ExpectedRevision: current.Revision,
            ExpectedValue: expectedValue,
            SourceMissionId: invocation.MissionId,
            CapturedAtUtc: now,
            SessionId: opened.SessionId));
        if (!SavedRecordMatches(
                new MemorySaveResult(result.RecordId, result.Revision, result.Selector, result.Replayed),
                newValue,
                opened.SessionId))
        {
            return Failure("verification_failed", effectMayHaveOccurred: true);
        }

        return Success(
            invocation,
            opened.SessionId,
            new MemoryMutationWireResult(
                PayloadVersion,
                result.RecordId.ToString("D"),
                result.Revision,
                result.Selector,
                result.Replayed),
            MemoryHandlersJsonContext.Default.MemoryMutationWireResult);
    }

    private OperationOutcome Recall(
        OperationInvocation invocation,
        OpenedBoundProtectedJson opened)
    {
        JsonElement payload = opened.Payload;
        RequireExactProperties(payload, ["version", "scope", "selector"]);
        RequireVersion(payload);
        string scope = RequiredString(payload, "scope");
        string? selector = OptionalNullableString(payload, "selector");
        MemoryKind? selectedKind = null;
        switch (scope)
        {
            case "exact" when selector is not null:
                _ = NormalizeSelectorForComparison(selector);
                break;
            case "all" when selector is null:
                break;
            case "kind" when selector is not null:
                selectedKind = ParseKindSelector(selector);
                break;
            default:
                throw new JsonException("The recall scope is invalid.");
        }

        _ = _store.BeginSession(new MemoryBeginSessionRequest(opened.SessionId));
        MemoryRecord[] records;
        int totalCount;
        switch (scope)
        {
            case "exact" when selector is not null:
                {
                    records = _store.Recall(new MemoryRecallRequest(
                        selector,
                        opened.SessionId,
                        LocalMemoryStore.MaximumRecallResults)).Records.ToArray();
                    totalCount = records.Length;
                    break;
                }
            case "all" when selector is null:
                {
                    MemoryRecord[] all = _store.List(new MemoryListRequest(
                        opened.SessionId,
                        MaximumResults: LocalMemoryStore.MaximumListResults)).Records.ToArray();
                    totalCount = all.Length;
                    records = all.Take(LocalMemoryStore.MaximumRecallResults).ToArray();
                    break;
                }
            case "kind" when selector is not null:
                {
                    MemoryRecord[] all = _store.List(new MemoryListRequest(
                        opened.SessionId,
                        selectedKind,
                        MaximumResults: LocalMemoryStore.MaximumListResults)).Records.ToArray();
                    totalCount = all.Length;
                    records = all.Take(LocalMemoryStore.MaximumRecallResults).ToArray();
                    break;
                }
            default:
                throw new InvalidOperationException("The recall scope was not normalized.");
        }

        return SealedRecordsSuccess(
            invocation,
            opened.SessionId,
            records,
            totalCount,
            offset: 0,
            limit: LocalMemoryStore.MaximumRecallResults);
    }

    private OperationOutcome List(
        OperationInvocation invocation,
        OpenedBoundProtectedJson opened)
    {
        JsonElement payload = opened.Payload;
        RequireExactProperties(payload, ["version", "limit", "offset"]);
        RequireVersion(payload);
        int limit = RequiredInt32(payload, "limit");
        int offset = RequiredInt32(payload, "offset");
        if (limit is < 1 or > MaximumListPageSize
            || offset < 0
            || offset > LocalMemoryStore.MaximumListResults
            || (long)offset + limit > LocalMemoryStore.MaximumListResults)
        {
            throw new JsonException("The memory list page is out of range.");
        }

        _ = _store.BeginSession(new MemoryBeginSessionRequest(opened.SessionId));
        MemoryRecord[] all = _store.List(new MemoryListRequest(
            opened.SessionId,
            MaximumResults: LocalMemoryStore.MaximumListResults)).Records.ToArray();
        MemoryRecord[] page = all.Skip(offset).Take(limit).ToArray();
        return SealedRecordsSuccess(
            invocation,
            opened.SessionId,
            page,
            all.Length,
            offset,
            limit);
    }

    private OperationOutcome Status(
        OperationInvocation invocation,
        OpenedBoundProtectedJson opened)
    {
        JsonElement payload = opened.Payload;
        RequireExactProperties(payload, ["version"]);
        RequireVersion(payload);
        _ = _store.BeginSession(new MemoryBeginSessionRequest(opened.SessionId));
        MemoryStatusResult result = _store.Status(new MemoryStatusRequest(opened.SessionId));
        return Success(
            invocation,
            opened.SessionId,
            new MemoryStatusWireResult(
                PayloadVersion,
                result.Enabled,
                result.TotalRecords,
                result.PersistentRecords,
                result.SessionRecords,
                result.TemporaryRecords,
                result.MaximumRecords),
            MemoryHandlersJsonContext.Default.MemoryStatusWireResult);
    }

    private OperationOutcome SealedRecordsSuccess(
        OperationInvocation invocation,
        string sessionId,
        IReadOnlyList<MemoryRecord> records,
        int totalCount,
        int offset,
        int limit)
    {
        MemoryRecordWireResult[] projected = records.Select(static record =>
            new MemoryRecordWireResult(
                record.Id.ToString("D"),
                record.Revision,
                record.Selector,
                record.Label,
                record.Value,
                ToWire(record.Kind),
                "explicit",
                ToWire(record.Sensitivity),
                ToWire(record.Retention),
                record.Tags.ToArray(),
                record.CreatedAtUtc,
                record.UpdatedAtUtc,
                record.ExpiresAtUtc,
                record.SourceMissionId,
                record.CapturedAtUtc,
                record.SessionId)).ToArray();
        var result = new MemoryRecordsWireResult(
            PayloadVersion,
            projected,
            projected.Length,
            totalCount,
            offset,
            limit);
        return Success(
            invocation,
            sessionId,
            result,
            MemoryHandlersJsonContext.Default.MemoryRecordsWireResult);
    }

    private OperationOutcome Success<T>(
        OperationInvocation invocation,
        string sessionId,
        T privateResult,
        JsonTypeInfo<T> typeInfo)
    {
        JsonElement clearResult = JsonSerializer.SerializeToElement(privateResult, typeInfo);
        JsonElement sealedResult = _codec.SealResult(
            Definition.Name,
            invocation.MissionId,
            invocation.InvocationId,
            sessionId,
            clearResult);
        return OperationOutcome.PrivateSuccess(sealedResult);
    }

    private bool SavedRecordMatches(
        MemorySaveResult result,
        string value,
        string? sessionId)
    {
        MemoryRecord[] observed = _store.Recall(new MemoryRecallRequest(
                result.Selector,
                sessionId,
                LocalMemoryStore.MaximumRecallResults))
            .Records
            .Where(record => record.Id == result.RecordId)
            .ToArray();
        return observed.Length == 1
            && observed[0].Revision == result.Revision
            && string.Equals(observed[0].Selector, result.Selector, StringComparison.Ordinal)
            && (string.Equals(observed[0].Value, value, StringComparison.Ordinal)
                || string.Equals(
                    observed[0].Value,
                    LocalMemoryStore.RedactedSecretValue,
                    StringComparison.Ordinal));
    }

    private bool ForgottenStateMatches(
        MemoryForgetRequest request,
        MemoryForgetResult result,
        string? sessionId)
    {
        if (result.DeletedCount <= 0)
        {
            return true;
        }

        if (request.Scope == MemoryForgetScope.Exact && request.Selector is not null)
        {
            return !_store.Recall(new MemoryRecallRequest(
                    request.Selector,
                    sessionId,
                    LocalMemoryStore.MaximumRecallResults))
                .Records
                .Any(record => string.Equals(
                    record.Selector,
                    request.Selector,
                    StringComparison.OrdinalIgnoreCase));
        }

        if (request.Scope == MemoryForgetScope.Session)
        {
            return _store.Status(new MemoryStatusRequest(sessionId)).SessionRecords == 0;
        }

        MemoryStatusResult status = _store.Status(new MemoryStatusRequest(sessionId));
        return status.TotalRecords == 0;
    }

    private static OperationOutcome Failure(
        string errorCode,
        bool effectMayHaveOccurred = false) =>
        OperationOutcome.Failure(errorCode, effectMayHaveOccurred: effectMayHaveOccurred);

    private static void RequireVersion(JsonElement payload)
    {
        JsonElement version = RequiredProperty(payload, "version");
        if (version.ValueKind != JsonValueKind.Number
            || !version.TryGetInt32(out int value)
            || value != PayloadVersion
            || !string.Equals(version.GetRawText(), "1", StringComparison.Ordinal))
        {
            throw new JsonException("Unsupported private payload version.");
        }
    }

    private static void RequireExactProperties(JsonElement payload, string[] expected)
    {
        RequireAllowedProperties(payload, expected, []);
    }

    private static void RequireAllowedProperties(
        JsonElement payload,
        string[] required,
        string[] optional)
    {
        if (payload.ValueKind != JsonValueKind.Object)
        {
            throw new JsonException("The private payload must be an object.");
        }

        var allowed = new HashSet<string>(required, StringComparer.Ordinal);
        allowed.UnionWith(optional);
        var present = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonProperty property in payload.EnumerateObject())
        {
            if (!allowed.Contains(property.Name) || !present.Add(property.Name))
            {
                throw new JsonException("The private payload schema is not exact.");
            }
        }

        if (required.Any(name => !present.Contains(name)))
        {
            throw new JsonException("The private payload is missing a required field.");
        }
    }

    private static JsonElement RequiredProperty(JsonElement payload, string name)
    {
        if (!payload.TryGetProperty(name, out JsonElement value))
        {
            throw new JsonException("A required private field is missing.");
        }

        return value;
    }

    private static string RequiredString(JsonElement payload, string name) =>
        RequireString(RequiredProperty(payload, name));

    private static string RequireString(JsonElement value)
    {
        if (value.ValueKind != JsonValueKind.String
            || string.IsNullOrWhiteSpace(value.GetString()))
        {
            throw new JsonException("A private string field is invalid.");
        }

        return value.GetString()!;
    }

    private static string? OptionalString(JsonElement payload, string name) =>
        payload.TryGetProperty(name, out JsonElement value) ? RequireString(value) : null;

    private static string? OptionalNullableString(JsonElement payload, string name)
    {
        JsonElement value = RequiredProperty(payload, name);
        return value.ValueKind == JsonValueKind.Null ? null : RequireString(value);
    }

    private static bool RequiredBoolean(JsonElement payload, string name)
    {
        JsonElement value = RequiredProperty(payload, name);
        if (value.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
        {
            throw new JsonException("A private Boolean field is invalid.");
        }

        return value.GetBoolean();
    }

    private static int RequiredInt32(JsonElement payload, string name)
    {
        JsonElement value = RequiredProperty(payload, name);
        if (value.ValueKind != JsonValueKind.Number
            || !value.TryGetInt32(out int result)
            || !string.Equals(
                value.GetRawText(),
                result.ToString(CultureInfo.InvariantCulture),
                StringComparison.Ordinal))
        {
            throw new JsonException("A private integer field is invalid.");
        }

        return result;
    }

    private static string[] RequiredStringArray(
        JsonElement payload,
        string name,
        int maximumCount)
    {
        JsonElement value = RequiredProperty(payload, name);
        if (value.ValueKind != JsonValueKind.Array || value.GetArrayLength() > maximumCount)
        {
            throw new JsonException("A private string array is invalid.");
        }

        return value.EnumerateArray().Select(RequireString).ToArray();
    }

    private static string CanonicalScalar(JsonElement value)
    {
        return value.ValueKind switch
        {
            JsonValueKind.String => value.GetString()!,
            JsonValueKind.True => "true",
            JsonValueKind.False => "false",
            JsonValueKind.Null => "null",
            JsonValueKind.Number => CanonicalNumber(value.GetRawText()),
            _ => throw new JsonException("Only scalar memory values are supported."),
        };
    }

    private static string CanonicalNumber(string raw)
    {
        if (raw.Length > MaximumCanonicalNumberCharacters)
        {
            throw new JsonException("The numeric memory value is too large.");
        }

        if (!raw.ContainsAny('.', 'e', 'E')
            && BigInteger.TryParse(
                raw,
                NumberStyles.AllowLeadingSign,
                CultureInfo.InvariantCulture,
                out BigInteger integer))
        {
            return integer.ToString(CultureInfo.InvariantCulture);
        }

        if (decimal.TryParse(
            raw,
            NumberStyles.Float,
            CultureInfo.InvariantCulture,
            out decimal decimalValue))
        {
            return decimalValue.ToString("G29", CultureInfo.InvariantCulture);
        }

        if (double.TryParse(
                raw,
                NumberStyles.Float,
                CultureInfo.InvariantCulture,
                out double doubleValue)
            && double.IsFinite(doubleValue))
        {
            string canonical = doubleValue.ToString("R", CultureInfo.InvariantCulture);
            return canonical.Replace("E+", "e", StringComparison.Ordinal)
                .Replace("E", "e", StringComparison.Ordinal);
        }

        throw new JsonException("The numeric memory value is invalid.");
    }

    private static MemoryKind ParseKind(string value) => value switch
    {
        "fact" => MemoryKind.Fact,
        "preference" => MemoryKind.Preference,
        "context" => MemoryKind.Context,
        "rule" => MemoryKind.Rule,
        _ => throw new JsonException("The memory kind is invalid."),
    };

    private static MemoryKind ParseKindSelector(string value) => value switch
    {
        "fact" or "facts" => MemoryKind.Fact,
        "preference" or "preferences" or "style_preferences" => MemoryKind.Preference,
        "context" or "contexts" => MemoryKind.Context,
        "rule" or "rules" => MemoryKind.Rule,
        _ => throw new JsonException("The memory kind selector is invalid."),
    };

    private static MemorySensitivity ParseSensitivity(string value) => value switch
    {
        "normal" => MemorySensitivity.Normal,
        "personal" => MemorySensitivity.Personal,
        "sensitive" => MemorySensitivity.Sensitive,
        "secret" => MemorySensitivity.Secret,
        _ => throw new JsonException("The memory sensitivity is invalid."),
    };

    private static MemoryRetention ParseRetention(string value) => value switch
    {
        "persistent" => MemoryRetention.Persistent,
        "session" => MemoryRetention.Session,
        "temporary" => MemoryRetention.Temporary,
        _ => throw new JsonException("The memory retention is invalid."),
    };

    private static string ToWire(MemoryKind value) => value switch
    {
        MemoryKind.Fact => "fact",
        MemoryKind.Preference => "preference",
        MemoryKind.Context => "context",
        MemoryKind.Rule => "rule",
        _ => throw new InvalidOperationException("Unknown memory kind."),
    };

    private static string ToWire(MemorySensitivity value) => value switch
    {
        MemorySensitivity.Normal => "normal",
        MemorySensitivity.Personal => "personal",
        MemorySensitivity.Sensitive => "sensitive",
        MemorySensitivity.Secret => "secret",
        _ => throw new InvalidOperationException("Unknown memory sensitivity."),
    };

    private static string ToWire(MemoryRetention value) => value switch
    {
        MemoryRetention.Persistent => "persistent",
        MemoryRetention.Session => "session",
        MemoryRetention.Temporary => "temporary",
        _ => throw new InvalidOperationException("Unknown memory retention."),
    };

    private static string NormalizeSelectorForComparison(string value)
    {
        string normalized = value.Normalize(NormalizationForm.FormC);
        var builder = new StringBuilder(normalized.Length);
        bool pendingSpace = false;
        foreach (char character in normalized)
        {
            if (char.IsWhiteSpace(character))
            {
                pendingSpace = builder.Length > 0;
                continue;
            }

            if (char.IsControl(character))
            {
                throw new JsonException("The memory selector is invalid.");
            }

            if (pendingSpace)
            {
                _ = builder.Append(' ');
                pendingSpace = false;
            }

            _ = builder.Append(character);
        }

        if (builder.Length == 0)
        {
            throw new JsonException("The memory selector is invalid.");
        }

        string result = builder.ToString().ToUpperInvariant();
        if (Encoding.UTF8.GetByteCount(result) > LocalMemoryStore.MaximumSelectorUtf8Bytes)
        {
            throw new JsonException("The memory selector is invalid.");
        }

        return result;
    }

    private static void ValidateMemoryValue(string value)
    {
        if (value.Length == 0
            || value.Any(character => char.IsControl(character)
                && character is not ('\r' or '\n' or '\t'))
            || Encoding.UTF8.GetByteCount(value) > LocalMemoryStore.MaximumValueUtf8Bytes)
        {
            throw new JsonException("The memory value is invalid.");
        }
    }

    private static void ValidateTag(string value)
    {
        string normalized = value.Normalize(NormalizationForm.FormC).Trim();
        if (normalized.Length == 0
            || normalized.Any(char.IsControl)
            || Encoding.UTF8.GetByteCount(normalized) > LocalMemoryStore.MaximumTagUtf8Bytes)
        {
            throw new JsonException("A memory tag is invalid.");
        }
    }
}
