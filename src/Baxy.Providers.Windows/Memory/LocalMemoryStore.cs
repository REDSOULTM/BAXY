using System.Buffers.Binary;
using System.Collections.Concurrent;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Baxy.Security.Windows;

namespace Baxy.Providers.Windows.Memory;

public sealed class LocalMemoryStore : IMemoryStore
{
    public const int MaximumRecords = 512;
    public const int MaximumSelectorUtf8Bytes = 256;
    public const int MaximumLabelUtf8Bytes = 512;
    public const int MaximumValueUtf8Bytes = 4096;
    public const int MaximumTags = 16;
    public const int MaximumTagUtf8Bytes = 64;
    public const int MaximumRecallResults = 5;
    public const int MaximumListResults = MaximumRecords;
    public const int MaximumMutationReceipts = 4096;
    public const int MaximumClearSnapshotBytes = 4 * 1024 * 1024;
    public const string RedactedSecretValue = "[REDACTED]";
    public static readonly TimeSpan MaximumTemporaryLifetime = TimeSpan.FromDays(30);

    private const int SchemaVersion = 1;
    private const int MaximumIdentifierUtf8Bytes = 256;
    private const int MaximumProtectionModeUtf8Bytes = 128;
    private const int MaximumSnapshotEnvelopeBytes = MaximumClearSnapshotBytes + 4096;
    private const int MaximumIntentEnvelopeBytes = 6 * 1024 * 1024;
    private const int MaximumWatermarkEnvelopeBytes = 16 * 1024;
    private const int PrivacyEmergencyHeadroomBytes = 16 * 1024;
    private const string SnapshotPurpose = "memory.store.v1";
    private const string IntentPurpose = "memory.intent.v1";
    private const string WatermarkPurpose = "memory.watermark.v1";
    private const string CurrentFileName = "current.bin";
    private const string RecoveryFileName = "recovery.bin";
    private const string WatermarkFileName = "watermark.bin";
    private const string IntentFileName = "mutation.intent";
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);
    private static readonly ConcurrentDictionary<string, object> RootLocks =
        new(StringComparer.OrdinalIgnoreCase);

    private readonly string _rootDirectory;
    private readonly string _currentPath;
    private readonly string _recoveryPath;
    private readonly string _watermarkPath;
    private readonly string _intentPath;
    private readonly IProtectedPayload _protector;
    private readonly TimeProvider _timeProvider;
    private readonly object _rootLock;
    private readonly Action<MemoryCommitStage>? _crashHook;
    private readonly int _maximumRecords;
    private readonly int _maximumReceipts;

    public LocalMemoryStore(
        string rootDirectory,
        IProtectedPayload protector,
        TimeProvider? timeProvider = null)
        : this(
            rootDirectory,
            protector,
            timeProvider,
            crashHook: null,
            maximumRecords: MaximumRecords,
            maximumReceipts: MaximumMutationReceipts)
    {
    }

    internal LocalMemoryStore(
        string rootDirectory,
        IProtectedPayload protector,
        TimeProvider? timeProvider,
        Action<MemoryCommitStage>? crashHook,
        int maximumRecords = MaximumRecords,
        int maximumReceipts = MaximumMutationReceipts)
    {
        ArgumentNullException.ThrowIfNull(protector);
        if (maximumRecords is < 1 or > MaximumRecords)
        {
            throw new ArgumentOutOfRangeException(nameof(maximumRecords));
        }

        if (maximumReceipts is < 1 or > MaximumMutationReceipts)
        {
            throw new ArgumentOutOfRangeException(nameof(maximumReceipts));
        }

        ValidateProtectionMode(protector.ProtectionMode);
        _rootDirectory = MemoryPathPolicy.NormalizeRoot(rootDirectory);
        _currentPath = MemoryPathPolicy.GetManagedPath(_rootDirectory, CurrentFileName);
        _recoveryPath = MemoryPathPolicy.GetManagedPath(_rootDirectory, RecoveryFileName);
        _watermarkPath = MemoryPathPolicy.GetManagedPath(_rootDirectory, WatermarkFileName);
        _intentPath = MemoryPathPolicy.GetManagedPath(_rootDirectory, IntentFileName);
        _protector = protector;
        _timeProvider = timeProvider ?? TimeProvider.System;
        _rootLock = RootLocks.GetOrAdd(_rootDirectory, static _ => new object());
        _crashHook = crashHook;
        _maximumRecords = maximumRecords;
        _maximumReceipts = maximumReceipts;

        lock (_rootLock)
        {
            MemoryPathPolicy.CreateAndValidateRoot(_rootDirectory);
            EnsureSafeManagedTreeUnsafe();
            DeleteAbandonedTemporaryFilesUnsafe();
            InitializeOrRecoverUnsafe();
        }
    }

    public string RootDirectory => _rootDirectory;

    public MemoryConfigurationResult Configure(MemoryConfigureRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        string invocationId = NormalizeIdentifier(request.InvocationId, nameof(request.InvocationId));
        string digest = CreateDigest("configure", builder => builder.Append(request.Enabled));

        lock (_rootLock)
        {
            MemoryStateDocument state = LoadAuthoritativeStateUnsafe();
            MemoryReceiptDocument? replay = FindReceiptUnsafe(state, invocationId, digest);
            if (replay is not null)
            {
                if (!string.Equals(replay.Operation, "configure", StringComparison.Ordinal)
                    || !replay.Enabled.HasValue)
                {
                    throw new MemoryStoreCorruptException();
                }

                return new MemoryConfigurationResult(replay.Enabled.Value, Replayed: true);
            }

            if (request.Enabled)
            {
                EnsureReceiptCapacity(state);
            }

            AdvanceClockAndPurgeUnsafe(state);
            state.Enabled = request.Enabled;
            var receipt = new MemoryReceiptDocument
            {
                InvocationId = invocationId,
                RequestDigest = digest,
                Operation = "configure",
                Enabled = request.Enabled,
            };
            AddReceiptUnsafe(state, receipt, privacyReducing: !request.Enabled);
            CommitMutationUnsafe(state, allowPrivacyHeadroom: !request.Enabled);
            return new MemoryConfigurationResult(request.Enabled, Replayed: false);
        }
    }

    public MemoryBeginSessionResult BeginSession(MemoryBeginSessionRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        string sessionId = NormalizeIdentifier(request.SessionId, nameof(request.SessionId));

        lock (_rootLock)
        {
            MemoryStateDocument state = LoadAuthoritativeStateUnsafe();
            if (string.Equals(state.ActiveSessionId, sessionId, StringComparison.Ordinal))
            {
                return new MemoryBeginSessionResult(0, Changed: false);
            }

            AdvanceClockAndPurgeUnsafe(state);
            int purged = state.Records.RemoveAll(record =>
                record.Retention == MemoryRetention.Session);
            state.ActiveSessionId = sessionId;
            CommitMutationUnsafe(state, allowPrivacyHeadroom: true);
            return new MemoryBeginSessionResult(purged, Changed: true);
        }
    }

    public MemoryStatusResult Status(MemoryStatusRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        string? sessionId = NormalizeOptionalIdentifier(request.SessionId, nameof(request.SessionId));

        lock (_rootLock)
        {
            MemoryStateDocument state = LoadAuthoritativeStateUnsafe();
            EnsureActiveSession(state, sessionId);
            _ = AdvanceClockAndPersistHousekeepingUnsafe(state);
            return new MemoryStatusResult(
                state.Enabled,
                state.Records.Count,
                state.Records.Count(record => record.Retention == MemoryRetention.Persistent),
                state.Records.Count(record => record.Retention == MemoryRetention.Session),
                state.Records.Count(record => record.Retention == MemoryRetention.Temporary),
                _maximumRecords);
        }
    }

    public MemorySaveResult Save(MemorySaveRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        string invocationId = NormalizeIdentifier(request.InvocationId, nameof(request.InvocationId));
        NormalizedSave normalized = NormalizeSaveRequest(request);
        string digest = CreateSaveDigest(normalized);

        lock (_rootLock)
        {
            MemoryStateDocument state = LoadAuthoritativeStateUnsafe();
            EnsureActiveSession(state, normalized.SessionId);
            MemoryReceiptDocument? replay = FindReceiptUnsafe(state, invocationId, digest);
            if (replay is not null)
            {
                return ToSaveReplay(replay);
            }

            EnsureEnabled(state);
            EnsureReceiptCapacity(state);
            DateTimeOffset now = AdvanceClockAndPurgeUnsafe(state);
            ValidateRetention(normalized.Retention, normalized.ExpiresAtUtc, normalized.SessionId, now);

            MemoryRecordDocument? existing = state.Records.SingleOrDefault(record =>
                string.Equals(record.Selector, normalized.Selector, StringComparison.Ordinal)
                && IsSameStorageScope(record, normalized.Retention, normalized.SessionId));
            MemoryRecordDocument record;
            if (existing is not null)
            {
                if (!IsEquivalentExistingSave(existing, normalized))
                {
                    throw new MemoryConflictException();
                }

                record = existing;
            }
            else
            {
                if (state.Records.Count >= _maximumRecords)
                {
                    throw new MemoryCapacityException();
                }

                Guid id;
                do
                {
                    id = Guid.NewGuid();
                }
                while (state.Records.Exists(candidate => candidate.Id == id));

                DateTimeOffset capturedAt = normalized.CapturedAtUtc ?? now;
                record = new MemoryRecordDocument
                {
                    Id = id,
                    Revision = 1,
                    Selector = normalized.Selector,
                    Label = normalized.Label,
                    Value = normalized.Value,
                    Kind = normalized.Kind,
                    Origin = MemoryOrigin.Explicit,
                    Sensitivity = normalized.Sensitivity,
                    Retention = normalized.Retention,
                    Tags = [.. normalized.Tags],
                    CreatedAtUtc = now,
                    UpdatedAtUtc = now,
                    ExpiresAtUtc = normalized.ExpiresAtUtc,
                    SourceMissionId = normalized.SourceMissionId,
                    CapturedAtUtc = capturedAt,
                    SessionId = normalized.SessionId,
                };
                state.Records.Add(record);
            }

            state.Receipts.Add(new MemoryReceiptDocument
            {
                InvocationId = invocationId,
                RequestDigest = digest,
                Operation = "save",
                RecordId = record.Id,
                Revision = record.Revision,
                Selector = record.Selector,
            });
            CommitMutationUnsafe(state);
            return new MemorySaveResult(record.Id, record.Revision, record.Selector, Replayed: false);
        }
    }

    public MemoryRecallResult Recall(MemoryRecallRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        string query = NormalizeSelector(request.Query, nameof(request.Query));
        string? sessionId = NormalizeOptionalIdentifier(request.SessionId, nameof(request.SessionId));
        if (request.MaximumResults is < 1 or > MaximumRecallResults)
        {
            throw new ArgumentOutOfRangeException(nameof(request));
        }

        lock (_rootLock)
        {
            MemoryStateDocument state = LoadAuthoritativeStateUnsafe();
            EnsureActiveSession(state, sessionId);
            EnsureEnabled(state);
            DateTimeOffset now = AdvanceClockAndPersistHousekeepingUnsafe(state);
            MemoryRecord[] records = state.Records
                .Where(record => IsVisible(record, sessionId, now) && MatchesQuery(record, query))
                .OrderByDescending(record => string.Equals(record.Selector, query, StringComparison.Ordinal))
                .ThenByDescending(record => record.UpdatedAtUtc)
                .ThenBy(record => record.Selector, StringComparer.Ordinal)
                .Take(request.MaximumResults)
                .Select(ToPublicRecord)
                .ToArray();
            return new MemoryRecallResult(records);
        }
    }

    public MemoryListResult List(MemoryListRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        string? sessionId = NormalizeOptionalIdentifier(request.SessionId, nameof(request.SessionId));
        string? topic = request.Topic is null
            ? null
            : NormalizeSelector(request.Topic, nameof(request.Topic));
        if (request.MaximumResults is < 1 or > MaximumListResults)
        {
            throw new ArgumentOutOfRangeException(nameof(request));
        }

        if (request.Kind.HasValue && !Enum.IsDefined(request.Kind.Value))
        {
            throw new ArgumentOutOfRangeException(nameof(request));
        }

        lock (_rootLock)
        {
            MemoryStateDocument state = LoadAuthoritativeStateUnsafe();
            EnsureActiveSession(state, sessionId);
            EnsureEnabled(state);
            DateTimeOffset now = AdvanceClockAndPersistHousekeepingUnsafe(state);
            MemoryRecord[] records = state.Records
                .Where(record => IsVisible(record, sessionId, now)
                    && (!request.Kind.HasValue || record.Kind == request.Kind.Value)
                    && (topic is null || MatchesQuery(record, topic)))
                .OrderByDescending(record => record.UpdatedAtUtc)
                .ThenBy(record => record.Selector, StringComparer.Ordinal)
                .Take(request.MaximumResults)
                .Select(ToPublicRecord)
                .ToArray();
            return new MemoryListResult(records);
        }
    }

    public MemoryCorrectResult Correct(MemoryCorrectRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        string invocationId = NormalizeIdentifier(request.InvocationId, nameof(request.InvocationId));
        string selector = NormalizeSelector(request.Selector, nameof(request.Selector));
        string newValue = NormalizeValue(request.NewValue, nameof(request.NewValue));
        string? expectedValue = request.ExpectedValue is null
            ? null
            : NormalizeValue(request.ExpectedValue, nameof(request.ExpectedValue));
        string? sourceMissionId = NormalizeOptionalIdentifier(
            request.SourceMissionId,
            nameof(request.SourceMissionId));
        string? sessionId = NormalizeOptionalIdentifier(request.SessionId, nameof(request.SessionId));
        DateTimeOffset? capturedAt = NormalizeOptionalUtc(request.CapturedAtUtc);
        if ((!request.ExpectedRevision.HasValue && expectedValue is null)
            || request.ExpectedRevision is <= 0)
        {
            throw new ArgumentException(
                "A positive expected revision or an expected previous value is required.",
                nameof(request));
        }

        string digest = CreateDigest("correct", builder =>
        {
            builder.Append(selector);
            builder.Append(newValue);
            builder.Append(request.ExpectedRevision);
            builder.Append(expectedValue);
            builder.Append(sourceMissionId);
            builder.Append(capturedAt);
            builder.Append(sessionId);
        });

        lock (_rootLock)
        {
            MemoryStateDocument state = LoadAuthoritativeStateUnsafe();
            EnsureActiveSession(state, sessionId);
            MemoryReceiptDocument? replay = FindReceiptUnsafe(state, invocationId, digest);
            if (replay is not null)
            {
                return ToCorrectReplay(replay);
            }

            EnsureEnabled(state);
            EnsureReceiptCapacity(state);
            DateTimeOffset now = AdvanceClockAndPurgeUnsafe(state);
            MemoryRecordDocument[] matches = state.Records
                .Where(record => string.Equals(record.Selector, selector, StringComparison.Ordinal)
                    && IsVisible(record, sessionId, now))
                .ToArray();
            if (matches.Length == 0)
            {
                throw new MemoryNotFoundException();
            }

            if (matches.Length != 1)
            {
                throw new MemoryConflictException();
            }

            MemoryRecordDocument record = matches[0];
            if ((request.ExpectedRevision.HasValue
                    && record.Revision != request.ExpectedRevision.Value)
                || (expectedValue is not null
                    && !string.Equals(record.Value, expectedValue, StringComparison.Ordinal)))
            {
                throw new MemoryConflictException();
            }

            if (!string.Equals(record.Value, newValue, StringComparison.Ordinal))
            {
                if (record.Revision == int.MaxValue)
                {
                    throw new MemoryCapacityException();
                }

                record.Value = newValue;
                record.Revision++;
                record.UpdatedAtUtc = now;
                record.SourceMissionId = sourceMissionId;
                record.CapturedAtUtc = capturedAt ?? now;
            }

            state.Receipts.Add(new MemoryReceiptDocument
            {
                InvocationId = invocationId,
                RequestDigest = digest,
                Operation = "correct",
                RecordId = record.Id,
                Revision = record.Revision,
                Selector = record.Selector,
            });
            CommitMutationUnsafe(state);
            return new MemoryCorrectResult(record.Id, record.Revision, record.Selector, Replayed: false);
        }
    }

    public MemoryForgetResult Forget(MemoryForgetRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        string invocationId = NormalizeIdentifier(request.InvocationId, nameof(request.InvocationId));
        NormalizedForget normalized = NormalizeForgetRequest(request);
        string digest = CreateForgetDigest(normalized);

        lock (_rootLock)
        {
            MemoryStateDocument state = LoadAuthoritativeStateUnsafe();
            EnsureActiveSession(state, normalized.SessionId);
            MemoryReceiptDocument? replay = FindReceiptUnsafe(state, invocationId, digest);
            if (replay is not null)
            {
                if (!string.Equals(replay.Operation, "forget", StringComparison.Ordinal)
                    || !replay.DeletedCount.HasValue)
                {
                    throw new MemoryStoreCorruptException();
                }

                return new MemoryForgetResult(replay.DeletedCount.Value, Replayed: true);
            }

            AdvanceClockAndPurgeUnsafe(state);
            int deleted = state.Records.RemoveAll(record => MatchesForget(record, normalized));
            var receipt = new MemoryReceiptDocument
            {
                InvocationId = invocationId,
                RequestDigest = digest,
                Operation = "forget",
                DeletedCount = deleted,
            };
            AddReceiptUnsafe(state, receipt, privacyReducing: true);
            CommitMutationUnsafe(state, allowPrivacyHeadroom: true);
            VerifyForgetAbsentUnsafe(normalized);
            return new MemoryForgetResult(deleted, Replayed: false);
        }
    }

    private void InitializeOrRecoverUnsafe()
    {
        if (MemoryPathPolicy.RegularFileExists(_intentPath))
        {
            RollForwardIntentUnsafe(ReadIntentUnsafe());
            return;
        }

        bool hasCurrent = MemoryPathPolicy.RegularFileExists(_currentPath);
        bool hasRecovery = MemoryPathPolicy.RegularFileExists(_recoveryPath);
        bool hasWatermark = MemoryPathPolicy.RegularFileExists(_watermarkPath);
        if (!hasCurrent && !hasRecovery && !hasWatermark)
        {
            DateTimeOffset now = GetUtcNow();
            var initial = new MemoryStateDocument
            {
                SchemaVersion = SchemaVersion,
                Generation = 0,
                Enabled = false,
                MaxObservedUtc = now,
                ProtectionMode = _protector.ProtectionMode,
            };
            CommitStateUnsafe(initial);
            return;
        }

        if (!hasWatermark)
        {
            throw new MemoryStoreCorruptException();
        }

        _ = LoadAuthoritativeStateUnsafe();
    }

    private MemoryStateDocument LoadAuthoritativeStateUnsafe()
    {
        EnsureSafeManagedTreeUnsafe();
        DeleteAbandonedTemporaryFilesUnsafe();
        if (MemoryPathPolicy.RegularFileExists(_intentPath))
        {
            RollForwardIntentUnsafe(ReadIntentUnsafe());
        }

        if (!MemoryPathPolicy.RegularFileExists(_watermarkPath))
        {
            throw new MemoryStoreCorruptException();
        }

        MemoryWatermarkDocument watermark;
        try
        {
            watermark = ReadWatermarkUnsafe();
        }
        catch (MemoryStoreCorruptException)
        {
            throw;
        }
        catch (Exception exception) when (IsRecoverableStoreReadFailure(exception))
        {
            throw new MemoryStoreCorruptException(exception);
        }
        SnapshotCandidate? current = TryReadSnapshotUnsafe(_currentPath);
        SnapshotCandidate? recovery = TryReadSnapshotUnsafe(_recoveryPath);
        RejectSnapshotAheadOfWatermark(current, watermark);
        RejectSnapshotAheadOfWatermark(recovery, watermark);

        SnapshotCandidate? authoritative = IsWatermarkMatch(current, watermark)
            ? current
            : IsWatermarkMatch(recovery, watermark)
                ? recovery
                : null;
        if (authoritative is null)
        {
            throw new MemoryStoreCorruptException();
        }

        if (!IsExactEnvelopeMatch(current, authoritative))
        {
            AtomicWriteUnsafe(_currentPath, authoritative.Envelope);
        }

        if (!IsExactEnvelopeMatch(recovery, authoritative))
        {
            AtomicWriteUnsafe(_recoveryPath, authoritative.Envelope);
        }

        VerifyAuthoritativeFilesUnsafe(authoritative.Envelope, watermark);
        return authoritative.State;
    }

    private void CommitMutationUnsafe(
        MemoryStateDocument state,
        bool allowPrivacyHeadroom = false)
    {
        if (state.Generation == long.MaxValue)
        {
            throw new MemoryCapacityException();
        }

        state.Generation++;
        CommitStateUnsafe(state, allowPrivacyHeadroom);
    }

    private void CommitStateUnsafe(
        MemoryStateDocument state,
        bool allowPrivacyHeadroom = false)
    {
        ValidateStateDocument(state);
        byte[] clearSnapshot = SerializeState(state, allowPrivacyHeadroom);
        byte[]? snapshotEnvelope = null;
        byte[]? clearIntent = null;
        byte[]? intentEnvelope = null;
        try
        {
            string digest = Convert.ToHexStringLower(SHA256.HashData(clearSnapshot));
            snapshotEnvelope = _protector.Seal(clearSnapshot, SnapshotPurpose);
            if (snapshotEnvelope.Length > MaximumSnapshotEnvelopeBytes)
            {
                throw new MemoryCapacityException();
            }

            var intent = new MemoryIntentDocument
            {
                SchemaVersion = SchemaVersion,
                Generation = state.Generation,
                SnapshotDigest = digest,
                ProtectionMode = _protector.ProtectionMode,
                SnapshotEnvelope = snapshotEnvelope,
            };
            clearIntent = SerializeIntent(intent);
            intentEnvelope = _protector.Seal(clearIntent, IntentPurpose);
            if (intentEnvelope.Length > MaximumIntentEnvelopeBytes)
            {
                throw new MemoryCapacityException();
            }

            AtomicWriteUnsafe(_intentPath, intentEnvelope);
            InvokeCrashHook(MemoryCommitStage.IntentDurable);
            RollForwardIntentUnsafe(intent);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(clearSnapshot);
            if (clearIntent is not null)
            {
                CryptographicOperations.ZeroMemory(clearIntent);
            }

            if (snapshotEnvelope is not null)
            {
                CryptographicOperations.ZeroMemory(snapshotEnvelope);
            }

            if (intentEnvelope is not null)
            {
                CryptographicOperations.ZeroMemory(intentEnvelope);
            }
        }
    }

    private void RollForwardIntentUnsafe(MemoryIntentDocument intent)
    {
        ValidateIntentDocument(intent);
        SnapshotCandidate intended = OpenSnapshotEnvelope(intent.SnapshotEnvelope);
        if (intended.State.Generation != intent.Generation
            || !string.Equals(intended.Digest, intent.SnapshotDigest, StringComparison.Ordinal))
        {
            throw new MemoryStoreCorruptException();
        }

        MemoryWatermarkDocument? existingWatermark = MemoryPathPolicy.RegularFileExists(_watermarkPath)
            ? ReadWatermarkUnsafe()
            : null;
        if (existingWatermark is not null)
        {
            if (existingWatermark.Generation > intent.Generation
                || (existingWatermark.Generation == intent.Generation
                    && !string.Equals(
                        existingWatermark.SnapshotDigest,
                        intent.SnapshotDigest,
                        StringComparison.Ordinal)))
            {
                throw new MemoryStoreCorruptException();
            }
        }

        RejectSnapshotAheadOfIntent(TryReadSnapshotUnsafe(_currentPath), intent);
        RejectSnapshotAheadOfIntent(TryReadSnapshotUnsafe(_recoveryPath), intent);

        AtomicWriteUnsafe(_currentPath, intent.SnapshotEnvelope);
        InvokeCrashHook(MemoryCommitStage.CurrentDurable);
        AtomicWriteUnsafe(_recoveryPath, intent.SnapshotEnvelope);
        InvokeCrashHook(MemoryCommitStage.RecoveryDurable);

        var watermark = new MemoryWatermarkDocument
        {
            SchemaVersion = SchemaVersion,
            Generation = intent.Generation,
            SnapshotDigest = intent.SnapshotDigest,
            ProtectionMode = _protector.ProtectionMode,
        };
        byte[] clearWatermark = SerializeWatermark(watermark);
        byte[]? watermarkEnvelope = null;
        try
        {
            watermarkEnvelope = _protector.Seal(clearWatermark, WatermarkPurpose);
            if (watermarkEnvelope.Length > MaximumWatermarkEnvelopeBytes)
            {
                throw new MemoryCapacityException();
            }

            AtomicWriteUnsafe(_watermarkPath, watermarkEnvelope);
            InvokeCrashHook(MemoryCommitStage.WatermarkDurable);
            VerifyCommittedStateUnsafe(intent.SnapshotEnvelope, watermarkEnvelope, watermark);
            InvokeCrashHook(MemoryCommitStage.Verified);
            DeleteManagedFileUnsafe(_intentPath);
            InvokeCrashHook(MemoryCommitStage.IntentDeleted);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(clearWatermark);
            if (watermarkEnvelope is not null)
            {
                CryptographicOperations.ZeroMemory(watermarkEnvelope);
            }
        }
    }

    private MemoryIntentDocument ReadIntentUnsafe()
    {
        byte[] envelope = ReadBoundedFileUnsafe(_intentPath, MaximumIntentEnvelopeBytes);
        byte[]? clear = null;
        try
        {
            clear = _protector.Open(envelope, IntentPurpose);
            MemoryIntentDocument? intent = JsonSerializer.Deserialize(
                clear,
                MemoryJsonContext.Default.MemoryIntentDocument);
            if (intent is null)
            {
                throw new MemoryStoreCorruptException();
            }

            ValidateIntentDocument(intent);
            EnsureCanonicalDocument(
                clear,
                SerializeIntent(intent));
            return intent;
        }
        catch (JsonException exception)
        {
            throw new MemoryStoreCorruptException(exception);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(envelope);
            if (clear is not null)
            {
                CryptographicOperations.ZeroMemory(clear);
            }
        }
    }

    private MemoryWatermarkDocument ReadWatermarkUnsafe()
    {
        byte[] envelope = ReadBoundedFileUnsafe(_watermarkPath, MaximumWatermarkEnvelopeBytes);
        byte[]? clear = null;
        try
        {
            clear = _protector.Open(envelope, WatermarkPurpose);
            MemoryWatermarkDocument? watermark = JsonSerializer.Deserialize(
                clear,
                MemoryJsonContext.Default.MemoryWatermarkDocument);
            if (watermark is null)
            {
                throw new MemoryStoreCorruptException();
            }

            ValidateWatermarkDocument(watermark);
            EnsureCanonicalDocument(
                clear,
                SerializeWatermark(watermark));
            return watermark;
        }
        catch (JsonException exception)
        {
            throw new MemoryStoreCorruptException(exception);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(envelope);
            if (clear is not null)
            {
                CryptographicOperations.ZeroMemory(clear);
            }
        }
    }

    private SnapshotCandidate? TryReadSnapshotUnsafe(string path)
    {
        if (!MemoryPathPolicy.RegularFileExists(path))
        {
            return null;
        }

        try
        {
            byte[] envelope = ReadBoundedFileUnsafe(path, MaximumSnapshotEnvelopeBytes);
            try
            {
                return OpenSnapshotEnvelope(envelope);
            }
            catch
            {
                CryptographicOperations.ZeroMemory(envelope);
                throw;
            }
        }
        catch (Exception exception) when (IsRecoverableStoreReadFailure(exception))
        {
            return null;
        }
    }

    private SnapshotCandidate OpenSnapshotEnvelope(byte[] envelope)
    {
        byte[]? clear = null;
        try
        {
            clear = _protector.Open(envelope, SnapshotPurpose);
            if (clear.Length > MaximumClearSnapshotBytes)
            {
                throw new MemoryStoreCorruptException();
            }

            string digest = Convert.ToHexStringLower(SHA256.HashData(clear));
            MemoryStateDocument? state = JsonSerializer.Deserialize(
                clear,
                MemoryJsonContext.Default.MemoryStateDocument);
            if (state is null)
            {
                throw new MemoryStoreCorruptException();
            }

            ValidateStateDocument(state);
            EnsureCanonicalDocument(
                clear,
                JsonSerializer.SerializeToUtf8Bytes(
                    state,
                    MemoryJsonContext.Default.MemoryStateDocument));
            return new SnapshotCandidate(state, envelope, digest);
        }
        catch (JsonException exception)
        {
            throw new MemoryStoreCorruptException(exception);
        }
        finally
        {
            if (clear is not null)
            {
                CryptographicOperations.ZeroMemory(clear);
            }
        }
    }

    private void VerifyCommittedStateUnsafe(
        byte[] expectedSnapshotEnvelope,
        byte[] expectedWatermarkEnvelope,
        MemoryWatermarkDocument expectedWatermark)
    {
        byte[] current = ReadBoundedFileUnsafe(_currentPath, MaximumSnapshotEnvelopeBytes);
        byte[] recovery = ReadBoundedFileUnsafe(_recoveryPath, MaximumSnapshotEnvelopeBytes);
        byte[] watermark = ReadBoundedFileUnsafe(_watermarkPath, MaximumWatermarkEnvelopeBytes);
        try
        {
            if (!current.AsSpan().SequenceEqual(expectedSnapshotEnvelope)
                || !recovery.AsSpan().SequenceEqual(expectedSnapshotEnvelope)
                || !watermark.AsSpan().SequenceEqual(expectedWatermarkEnvelope))
            {
                throw new MemoryStoreCorruptException();
            }

            SnapshotCandidate currentState = OpenSnapshotEnvelope(current);
            SnapshotCandidate recoveryState = OpenSnapshotEnvelope(recovery);
            MemoryWatermarkDocument actualWatermark = ReadWatermarkUnsafe();
            if (!IsWatermarkMatch(currentState, expectedWatermark)
                || !IsWatermarkMatch(recoveryState, expectedWatermark)
                || actualWatermark.Generation != expectedWatermark.Generation
                || !string.Equals(
                    actualWatermark.SnapshotDigest,
                    expectedWatermark.SnapshotDigest,
                    StringComparison.Ordinal))
            {
                throw new MemoryStoreCorruptException();
            }
        }
        finally
        {
            CryptographicOperations.ZeroMemory(current);
            CryptographicOperations.ZeroMemory(recovery);
            CryptographicOperations.ZeroMemory(watermark);
        }
    }

    private void VerifyAuthoritativeFilesUnsafe(
        byte[] expectedSnapshotEnvelope,
        MemoryWatermarkDocument watermark)
    {
        byte[] current = ReadBoundedFileUnsafe(_currentPath, MaximumSnapshotEnvelopeBytes);
        byte[] recovery = ReadBoundedFileUnsafe(_recoveryPath, MaximumSnapshotEnvelopeBytes);
        try
        {
            if (!current.AsSpan().SequenceEqual(expectedSnapshotEnvelope)
                || !recovery.AsSpan().SequenceEqual(expectedSnapshotEnvelope))
            {
                throw new MemoryStoreCorruptException();
            }

            SnapshotCandidate currentState = OpenSnapshotEnvelope(current);
            SnapshotCandidate recoveryState = OpenSnapshotEnvelope(recovery);
            if (!IsWatermarkMatch(currentState, watermark)
                || !IsWatermarkMatch(recoveryState, watermark))
            {
                throw new MemoryStoreCorruptException();
            }
        }
        finally
        {
            CryptographicOperations.ZeroMemory(current);
            CryptographicOperations.ZeroMemory(recovery);
        }
    }

    private void VerifyForgetAbsentUnsafe(NormalizedForget request)
    {
        if (MemoryPathPolicy.RegularFileExists(_intentPath))
        {
            throw new MemoryStoreCorruptException();
        }

        foreach (string path in new[] { _currentPath, _recoveryPath })
        {
            byte[] envelope = ReadBoundedFileUnsafe(path, MaximumSnapshotEnvelopeBytes);
            try
            {
                SnapshotCandidate snapshot = OpenSnapshotEnvelope(envelope);
                if (snapshot.State.Records.Exists(record => MatchesForget(record, request)))
                {
                    throw new MemoryStoreCorruptException();
                }
            }
            finally
            {
                CryptographicOperations.ZeroMemory(envelope);
            }
        }
    }

    private DateTimeOffset AdvanceClockAndPersistHousekeepingUnsafe(MemoryStateDocument state)
    {
        long generation = state.Generation;
        int count = state.Records.Count;
        DateTimeOffset previous = state.MaxObservedUtc;
        DateTimeOffset now = AdvanceClockAndPurgeUnsafe(state);
        if (state.Records.Count != count || state.MaxObservedUtc != previous)
        {
            if (generation == long.MaxValue)
            {
                throw new MemoryCapacityException();
            }

            state.Generation = generation + 1;
            CommitStateUnsafe(state);
        }

        return now;
    }

    private DateTimeOffset AdvanceClockAndPurgeUnsafe(MemoryStateDocument state)
    {
        DateTimeOffset observed = GetUtcNow();
        DateTimeOffset effective = observed > state.MaxObservedUtc
            ? observed
            : state.MaxObservedUtc;
        state.MaxObservedUtc = effective;
        _ = state.Records.RemoveAll(record =>
            record.Retention == MemoryRetention.Temporary
            && record.ExpiresAtUtc.HasValue
            && record.ExpiresAtUtc.Value <= effective);
        return effective;
    }

    private static MemoryReceiptDocument? FindReceiptUnsafe(
        MemoryStateDocument state,
        string invocationId,
        string requestDigest)
    {
        MemoryReceiptDocument? receipt = state.Receipts.Find(candidate =>
            string.Equals(candidate.InvocationId, invocationId, StringComparison.Ordinal));
        if (receipt is null
            && string.Equals(
                state.EmergencyPrivacyReceipt?.InvocationId,
                invocationId,
                StringComparison.Ordinal))
        {
            receipt = state.EmergencyPrivacyReceipt;
        }

        if (receipt is null)
        {
            return null;
        }

        if (!string.Equals(receipt.RequestDigest, requestDigest, StringComparison.Ordinal))
        {
            throw new MemoryInvocationConflictException();
        }

        return receipt;
    }

    private void AddReceiptUnsafe(
        MemoryStateDocument state,
        MemoryReceiptDocument receipt,
        bool privacyReducing)
    {
        if (state.Receipts.Count < _maximumReceipts)
        {
            state.Receipts.Add(receipt);
            return;
        }

        if (!privacyReducing || !IsPrivacyReducingReceipt(receipt))
        {
            throw new MemoryCapacityException();
        }

        state.EmergencyPrivacyReceipt = receipt;
    }

    private void EnsureReceiptCapacity(MemoryStateDocument state)
    {
        if (state.Receipts.Count >= _maximumReceipts)
        {
            throw new MemoryCapacityException();
        }
    }

    private static bool IsPrivacyReducingReceipt(MemoryReceiptDocument receipt) =>
        string.Equals(receipt.Operation, "forget", StringComparison.Ordinal)
        || (string.Equals(receipt.Operation, "configure", StringComparison.Ordinal)
            && receipt.Enabled == false);

    private static void EnsureEnabled(MemoryStateDocument state)
    {
        if (!state.Enabled)
        {
            throw new MemoryDisabledException();
        }
    }

    private static void EnsureActiveSession(
        MemoryStateDocument state,
        string? requestedSessionId)
    {
        if (requestedSessionId is not null
            && !string.Equals(
                state.ActiveSessionId,
                requestedSessionId,
                StringComparison.Ordinal))
        {
            throw new MemoryConflictException();
        }
    }

    private static MemorySaveResult ToSaveReplay(MemoryReceiptDocument receipt)
    {
        if (!string.Equals(receipt.Operation, "save", StringComparison.Ordinal)
            || !receipt.RecordId.HasValue
            || !receipt.Revision.HasValue
            || receipt.Selector is null)
        {
            throw new MemoryStoreCorruptException();
        }

        return new MemorySaveResult(
            receipt.RecordId.Value,
            receipt.Revision.Value,
            receipt.Selector,
            Replayed: true);
    }

    private static MemoryCorrectResult ToCorrectReplay(MemoryReceiptDocument receipt)
    {
        if (!string.Equals(receipt.Operation, "correct", StringComparison.Ordinal)
            || !receipt.RecordId.HasValue
            || !receipt.Revision.HasValue
            || receipt.Selector is null)
        {
            throw new MemoryStoreCorruptException();
        }

        return new MemoryCorrectResult(
            receipt.RecordId.Value,
            receipt.Revision.Value,
            receipt.Selector,
            Replayed: true);
    }

    private static bool IsVisible(
        MemoryRecordDocument record,
        string? sessionId,
        DateTimeOffset effectiveNow)
    {
        if (record.Retention == MemoryRetention.Session
            && !string.Equals(record.SessionId, sessionId, StringComparison.Ordinal))
        {
            return false;
        }

        return record.Retention != MemoryRetention.Temporary
            || !record.ExpiresAtUtc.HasValue
            || record.ExpiresAtUtc.Value > effectiveNow;
    }

    private static bool IsSameStorageScope(
        MemoryRecordDocument record,
        MemoryRetention retention,
        string? sessionId)
    {
        return retention == MemoryRetention.Session
            ? record.Retention == MemoryRetention.Session
                && string.Equals(record.SessionId, sessionId, StringComparison.Ordinal)
            : record.Retention != MemoryRetention.Session;
    }

    private static bool IsEquivalentExistingSave(
        MemoryRecordDocument record,
        NormalizedSave request) =>
        string.Equals(record.Value, request.Value, StringComparison.Ordinal)
        && string.Equals(record.Label, request.Label, StringComparison.OrdinalIgnoreCase)
        && record.Kind == request.Kind
        && record.Sensitivity == request.Sensitivity
        && record.Retention == request.Retention
        && record.ExpiresAtUtc == request.ExpiresAtUtc
        && record.Tags.SequenceEqual(request.Tags, StringComparer.Ordinal);

    private static bool MatchesQuery(MemoryRecordDocument record, string query)
    {
        if (string.Equals(record.Selector, query, StringComparison.Ordinal)
            || record.Selector.Contains(query, StringComparison.Ordinal))
        {
            return true;
        }

        string normalizedLabel = NormalizeSearchText(record.Label);
        return normalizedLabel.Contains(query, StringComparison.Ordinal)
            || record.Tags.Exists(tag => tag.Contains(query, StringComparison.Ordinal));
    }

    private static bool MatchesForget(MemoryRecordDocument record, NormalizedForget request)
    {
        return request.Scope switch
        {
            MemoryForgetScope.Exact => string.Equals(
                record.Selector,
                request.Selector,
                StringComparison.Ordinal),
            MemoryForgetScope.Kind => record.Kind == request.Kind,
            MemoryForgetScope.Topic => request.Topic is not null && MatchesQuery(record, request.Topic),
            MemoryForgetScope.Session => record.Retention == MemoryRetention.Session
                && string.Equals(record.SessionId, request.SessionId, StringComparison.Ordinal),
            MemoryForgetScope.All => true,
            _ => false,
        };
    }

    private static MemoryRecord ToPublicRecord(MemoryRecordDocument record) => new(
        record.Id,
        record.Revision,
        record.Selector,
        record.Label,
        record.Sensitivity is MemorySensitivity.Sensitive or MemorySensitivity.Secret
            ? RedactedSecretValue
            : record.Value,
        record.Kind,
        record.Origin,
        record.Sensitivity,
        record.Retention,
        record.Tags.ToArray(),
        record.CreatedAtUtc,
        record.UpdatedAtUtc,
        record.ExpiresAtUtc,
        record.SourceMissionId,
        record.CapturedAtUtc,
        record.SessionId);

    private static NormalizedSave NormalizeSaveRequest(MemorySaveRequest request)
    {
        if (!Enum.IsDefined(request.Kind))
        {
            throw new ArgumentOutOfRangeException(nameof(request));
        }

        if (!Enum.IsDefined(request.Sensitivity))
        {
            throw new ArgumentOutOfRangeException(nameof(request));
        }

        if (!Enum.IsDefined(request.Retention))
        {
            throw new ArgumentOutOfRangeException(nameof(request));
        }

        string[] tags = (request.Tags ?? Array.Empty<string>())
            .Select((tag, index) => NormalizeTag(tag, $"{nameof(request.Tags)}[{index}]"))
            .Distinct(StringComparer.Ordinal)
            .Order(StringComparer.Ordinal)
            .ToArray();
        if (tags.Length > MaximumTags)
        {
            throw new ArgumentOutOfRangeException(nameof(request));
        }

        return new NormalizedSave(
            NormalizeSelector(request.Selector, nameof(request.Selector)),
            NormalizeLabel(request.Label, nameof(request.Label)),
            NormalizeValue(request.Value, nameof(request.Value)),
            request.Kind,
            request.Sensitivity,
            request.Retention,
            tags,
            NormalizeOptionalUtc(request.ExpiresAtUtc),
            NormalizeOptionalIdentifier(request.SourceMissionId, nameof(request.SourceMissionId)),
            NormalizeOptionalUtc(request.CapturedAtUtc),
            NormalizeOptionalIdentifier(request.SessionId, nameof(request.SessionId)));
    }

    private static NormalizedForget NormalizeForgetRequest(MemoryForgetRequest request)
    {
        if (!Enum.IsDefined(request.Scope))
        {
            throw new ArgumentOutOfRangeException(nameof(request));
        }

        string? selector = request.Selector is null
            ? null
            : NormalizeSelector(request.Selector, nameof(request.Selector));
        string? topic = request.Topic is null
            ? null
            : NormalizeSelector(request.Topic, nameof(request.Topic));
        string? sessionId = NormalizeOptionalIdentifier(request.SessionId, nameof(request.SessionId));
        if (request.Kind.HasValue && !Enum.IsDefined(request.Kind.Value))
        {
            throw new ArgumentOutOfRangeException(nameof(request));
        }

        bool valid = request.Scope switch
        {
            MemoryForgetScope.Exact => selector is not null
                && !request.Kind.HasValue && topic is null && sessionId is null,
            MemoryForgetScope.Kind => selector is null
                && request.Kind.HasValue && topic is null && sessionId is null,
            MemoryForgetScope.Topic => selector is null
                && !request.Kind.HasValue && topic is not null && sessionId is null,
            MemoryForgetScope.Session => selector is null
                && !request.Kind.HasValue && topic is null && sessionId is not null,
            MemoryForgetScope.All => selector is null
                && !request.Kind.HasValue && topic is null && sessionId is null,
            _ => false,
        };
        if (!valid)
        {
            throw new ArgumentException(
                "The forget scope requires exactly its matching selector.",
                nameof(request));
        }

        return new NormalizedForget(request.Scope, selector, request.Kind, topic, sessionId);
    }

    private static void ValidateRetention(
        MemoryRetention retention,
        DateTimeOffset? expiresAtUtc,
        string? sessionId,
        DateTimeOffset now)
    {
        bool valid = retention switch
        {
            MemoryRetention.Persistent => !expiresAtUtc.HasValue && sessionId is null,
            MemoryRetention.Session => !expiresAtUtc.HasValue && sessionId is not null,
            MemoryRetention.Temporary => expiresAtUtc.HasValue
                && expiresAtUtc.Value > now
                && expiresAtUtc.Value - now <= MaximumTemporaryLifetime
                && sessionId is null,
            _ => false,
        };
        if (!valid)
        {
            throw new ArgumentException("The memory retention fields are inconsistent.");
        }
    }

    private static string CreateSaveDigest(NormalizedSave request) =>
        CreateDigest("save", builder =>
        {
            builder.Append(request.Selector);
            builder.Append(request.Label);
            builder.Append(request.Value);
            builder.Append((int)request.Kind);
            builder.Append((int)request.Sensitivity);
            builder.Append((int)request.Retention);
            builder.Append(request.Tags.Length);
            foreach (string tag in request.Tags)
            {
                builder.Append(tag);
            }

            builder.Append(request.ExpiresAtUtc);
            builder.Append(request.SourceMissionId);
            builder.Append(request.CapturedAtUtc);
            builder.Append(request.SessionId);
        });

    private static string CreateForgetDigest(NormalizedForget request) =>
        CreateDigest("forget", builder =>
        {
            builder.Append((int)request.Scope);
            builder.Append(request.Selector);
            builder.Append(request.Kind.HasValue ? (int)request.Kind.Value : null);
            builder.Append(request.Topic);
            builder.Append(request.SessionId);
        });

    private static string CreateDigest(string operation, Action<RequestDigestBuilder> append)
    {
        using var builder = new RequestDigestBuilder();
        builder.Append(operation);
        append(builder);
        return builder.GetDigest();
    }

    private static byte[] SerializeState(
        MemoryStateDocument state,
        bool allowPrivacyHeadroom)
    {
        byte[] clear = JsonSerializer.SerializeToUtf8Bytes(
            state,
            MemoryJsonContext.Default.MemoryStateDocument);
        int maximumBytes = allowPrivacyHeadroom || state.EmergencyPrivacyReceipt is not null
            ? MaximumClearSnapshotBytes
            : MaximumClearSnapshotBytes - PrivacyEmergencyHeadroomBytes;
        if (clear.Length > maximumBytes)
        {
            CryptographicOperations.ZeroMemory(clear);
            throw new MemoryCapacityException();
        }

        return clear;
    }

    private static byte[] SerializeIntent(MemoryIntentDocument intent) =>
        JsonSerializer.SerializeToUtf8Bytes(
            intent,
            MemoryJsonContext.Default.MemoryIntentDocument);

    private static byte[] SerializeWatermark(MemoryWatermarkDocument watermark) =>
        JsonSerializer.SerializeToUtf8Bytes(
            watermark,
            MemoryJsonContext.Default.MemoryWatermarkDocument);

    private void ValidateStateDocument(MemoryStateDocument state)
    {
        if (state.SchemaVersion != SchemaVersion
            || state.Generation < 0
            || state.MaxObservedUtc.Offset != TimeSpan.Zero
            || !string.Equals(state.ProtectionMode, _protector.ProtectionMode, StringComparison.Ordinal)
            || state.Records is null
            || state.Receipts is null
            || state.Records.Count > _maximumRecords
            || state.Receipts.Count > _maximumReceipts)
        {
            throw new MemoryStoreCorruptException();
        }

        try
        {
            if (!string.Equals(
                state.ActiveSessionId,
                NormalizeOptionalIdentifier(state.ActiveSessionId, "activeSessionId"),
                StringComparison.Ordinal))
            {
                throw new MemoryStoreCorruptException();
            }
        }
        catch (Exception exception) when (exception is ArgumentException
            or EncoderFallbackException)
        {
            throw new MemoryStoreCorruptException(exception);
        }

        var ids = new HashSet<Guid>();
        var scopedSelectors = new HashSet<string>(StringComparer.Ordinal);
        foreach (MemoryRecordDocument record in state.Records)
        {
            ValidateRecordDocument(record);
            string scope = record.Retention == MemoryRetention.Session
                ? string.Concat("session\0", record.SessionId, "\0", record.Selector)
                : string.Concat("global\0", record.Selector);
            if (!ids.Add(record.Id) || !scopedSelectors.Add(scope))
            {
                throw new MemoryStoreCorruptException();
            }

            if (record.Retention == MemoryRetention.Session
                && !string.Equals(record.SessionId, state.ActiveSessionId, StringComparison.Ordinal))
            {
                throw new MemoryStoreCorruptException();
            }
        }

        var invocations = new HashSet<string>(StringComparer.Ordinal);
        foreach (MemoryReceiptDocument receipt in state.Receipts)
        {
            ValidateReceiptDocument(receipt);
            if (!invocations.Add(receipt.InvocationId))
            {
                throw new MemoryStoreCorruptException();
            }
        }

        if (state.EmergencyPrivacyReceipt is not null)
        {
            ValidateReceiptDocument(state.EmergencyPrivacyReceipt);
            if (state.Receipts.Count != _maximumReceipts
                || !IsPrivacyReducingReceipt(state.EmergencyPrivacyReceipt)
                || !invocations.Add(state.EmergencyPrivacyReceipt.InvocationId))
            {
                throw new MemoryStoreCorruptException();
            }
        }
    }

    private static void ValidateRecordDocument(MemoryRecordDocument record)
    {
        try
        {
            if (record.Id == Guid.Empty
                || record.Revision < 1
                || !string.Equals(record.Selector, NormalizeSelector(record.Selector, "selector"), StringComparison.Ordinal)
                || !string.Equals(record.Label, NormalizeLabel(record.Label, "label"), StringComparison.Ordinal)
                || !string.Equals(record.Value, NormalizeValue(record.Value, "value"), StringComparison.Ordinal)
                || !Enum.IsDefined(record.Kind)
                || record.Origin != MemoryOrigin.Explicit
                || !Enum.IsDefined(record.Sensitivity)
                || !Enum.IsDefined(record.Retention)
                || record.Tags is null
                || record.Tags.Count > MaximumTags
                || record.Tags.Any(tag => !string.Equals(tag, NormalizeTag(tag, "tag"), StringComparison.Ordinal))
                || record.Tags.Distinct(StringComparer.Ordinal).Count() != record.Tags.Count
                || record.CreatedAtUtc.Offset != TimeSpan.Zero
                || record.UpdatedAtUtc.Offset != TimeSpan.Zero
                || record.CapturedAtUtc.Offset != TimeSpan.Zero
                || record.UpdatedAtUtc < record.CreatedAtUtc
                || (record.ExpiresAtUtc.HasValue && record.ExpiresAtUtc.Value.Offset != TimeSpan.Zero)
                || !string.Equals(
                    record.SourceMissionId,
                    NormalizeOptionalIdentifier(record.SourceMissionId, "sourceMissionId"),
                    StringComparison.Ordinal)
                || !string.Equals(
                    record.SessionId,
                    NormalizeOptionalIdentifier(record.SessionId, "sessionId"),
                    StringComparison.Ordinal))
            {
                throw new MemoryStoreCorruptException();
            }

            ValidateRetention(
                record.Retention,
                record.ExpiresAtUtc,
                record.SessionId,
                record.CreatedAtUtc);
        }
        catch (Exception exception) when (exception is ArgumentException
            or EncoderFallbackException)
        {
            throw new MemoryStoreCorruptException(exception);
        }
    }

    private static void ValidateReceiptDocument(MemoryReceiptDocument receipt)
    {
        try
        {
            if (!string.Equals(
                    receipt.InvocationId,
                    NormalizeIdentifier(receipt.InvocationId, "invocationId"),
                    StringComparison.Ordinal)
                || !IsSha256Hex(receipt.RequestDigest)
                || receipt.Operation is not ("configure" or "save" or "correct" or "forget"))
            {
                throw new MemoryStoreCorruptException();
            }

            bool shapeValid = receipt.Operation switch
            {
                "configure" => receipt.Enabled.HasValue
                    && !receipt.RecordId.HasValue
                    && !receipt.Revision.HasValue
                    && receipt.Selector is null
                    && !receipt.DeletedCount.HasValue,
                "save" or "correct" => !receipt.Enabled.HasValue
                    && receipt.RecordId.HasValue
                    && receipt.RecordId.Value != Guid.Empty
                    && receipt.Revision is > 0
                    && receipt.Selector is not null
                    && string.Equals(
                        receipt.Selector,
                        NormalizeSelector(receipt.Selector, "selector"),
                        StringComparison.Ordinal)
                    && !receipt.DeletedCount.HasValue,
                "forget" => !receipt.Enabled.HasValue
                    && !receipt.RecordId.HasValue
                    && !receipt.Revision.HasValue
                    && receipt.Selector is null
                    && receipt.DeletedCount is >= 0,
                _ => false,
            };
            if (!shapeValid)
            {
                throw new MemoryStoreCorruptException();
            }
        }
        catch (Exception exception) when (exception is ArgumentException
            or EncoderFallbackException)
        {
            throw new MemoryStoreCorruptException(exception);
        }
    }

    private void ValidateIntentDocument(MemoryIntentDocument intent)
    {
        if (intent.SchemaVersion != SchemaVersion
            || intent.Generation < 0
            || !IsSha256Hex(intent.SnapshotDigest)
            || !string.Equals(intent.ProtectionMode, _protector.ProtectionMode, StringComparison.Ordinal)
            || intent.SnapshotEnvelope is null
            || intent.SnapshotEnvelope.Length is < 1 or > MaximumSnapshotEnvelopeBytes)
        {
            throw new MemoryStoreCorruptException();
        }
    }

    private void ValidateWatermarkDocument(MemoryWatermarkDocument watermark)
    {
        if (watermark.SchemaVersion != SchemaVersion
            || watermark.Generation < 0
            || !IsSha256Hex(watermark.SnapshotDigest)
            || !string.Equals(watermark.ProtectionMode, _protector.ProtectionMode, StringComparison.Ordinal))
        {
            throw new MemoryStoreCorruptException();
        }
    }

    private static bool IsSha256Hex(string value)
    {
        if (value.Length != 64)
        {
            return false;
        }

        foreach (char character in value)
        {
            if (character is not (>= '0' and <= '9') and not (>= 'a' and <= 'f'))
            {
                return false;
            }
        }

        return true;
    }

    private static void EnsureCanonicalDocument(
        ReadOnlySpan<byte> actual,
        byte[] canonical)
    {
        try
        {
            if (!actual.SequenceEqual(canonical))
            {
                throw new MemoryStoreCorruptException();
            }
        }
        finally
        {
            CryptographicOperations.ZeroMemory(canonical);
        }
    }

    private static void ValidateProtectionMode(string protectionMode)
    {
        if (string.IsNullOrWhiteSpace(protectionMode)
            || StrictUtf8.GetByteCount(protectionMode) > MaximumProtectionModeUtf8Bytes)
        {
            throw new ArgumentException("The protected-payload mode is invalid.", nameof(protectionMode));
        }
    }

    private static void RejectSnapshotAheadOfWatermark(
        SnapshotCandidate? candidate,
        MemoryWatermarkDocument watermark)
    {
        if (candidate is not null && candidate.State.Generation > watermark.Generation)
        {
            throw new MemoryStoreCorruptException();
        }
    }

    private static void RejectSnapshotAheadOfIntent(
        SnapshotCandidate? candidate,
        MemoryIntentDocument intent)
    {
        if (candidate is null)
        {
            return;
        }

        if (candidate.State.Generation > intent.Generation
            || (candidate.State.Generation == intent.Generation
                && !string.Equals(candidate.Digest, intent.SnapshotDigest, StringComparison.Ordinal)))
        {
            throw new MemoryStoreCorruptException();
        }
    }

    private static bool IsWatermarkMatch(
        SnapshotCandidate? candidate,
        MemoryWatermarkDocument watermark) =>
        candidate is not null
        && candidate.State.Generation == watermark.Generation
        && string.Equals(candidate.Digest, watermark.SnapshotDigest, StringComparison.Ordinal);

    private static bool IsExactEnvelopeMatch(
        SnapshotCandidate? candidate,
        SnapshotCandidate authoritative) =>
        candidate is not null
        && candidate.Envelope.AsSpan().SequenceEqual(authoritative.Envelope);

    private void EnsureSafeManagedTreeUnsafe()
    {
        MemoryPathPolicy.EnsureDirectory(_rootDirectory);
        foreach (string path in GetAllManagedAndTemporaryPaths())
        {
            MemoryPathPolicy.EnsureRegularFileIfPresent(path);
        }
    }

    private void DeleteAbandonedTemporaryFilesUnsafe()
    {
        foreach (string path in GetManagedPaths())
        {
            string temporaryPath = string.Concat(path, ".tmp");
            DeleteManagedFileUnsafe(temporaryPath);
        }
    }

    private IEnumerable<string> GetManagedPaths()
    {
        yield return _currentPath;
        yield return _recoveryPath;
        yield return _watermarkPath;
        yield return _intentPath;
    }

    private IEnumerable<string> GetAllManagedAndTemporaryPaths()
    {
        foreach (string path in GetManagedPaths())
        {
            yield return path;
            yield return string.Concat(path, ".tmp");
        }
    }

    private void AtomicWriteUnsafe(string path, ReadOnlySpan<byte> bytes)
    {
        EnsureSafeManagedTreeUnsafe();
        string temporaryPath = string.Concat(path, ".tmp");
        DeleteManagedFileUnsafe(temporaryPath);

        WindowsPrivateFileLease? candidate = null;
        try
        {
            candidate = MemoryPathPolicy.CreateRegularFile(temporaryPath);
            candidate.Stream.Write(bytes);
            candidate.Stream.Flush(flushToDisk: true);
            _ = MemoryPathPolicy.RenameRegularFile(
                candidate,
                Path.GetFileName(path),
                replace: true);
        }
        catch
        {
            if (candidate is not null)
            {
                DestroyCandidateUnsafe(candidate);
            }

            throw;
        }
        finally
        {
            candidate?.Dispose();
        }
    }

    private static byte[] ReadBoundedFileUnsafe(string path, int maximumBytes)
    {
        if (!MemoryPathPolicy.TryOpenRegularFile(
                path,
                FileAccess.Read,
                FileShare.Read,
                deleteAccess: false,
                out WindowsPrivateFileLease? file))
        {
            throw new MemoryStoreCorruptException();
        }

        using (file)
        {
            FileStream stream = file.Stream;
            if (stream.Length is < 1 || stream.Length > maximumBytes)
            {
                throw new MemoryStoreCorruptException();
            }

            int length = checked((int)stream.Length);
            byte[] bytes = GC.AllocateUninitializedArray<byte>(length);
            try
            {
                stream.ReadExactly(bytes);
                if (stream.ReadByte() != -1)
                {
                    throw new MemoryStoreCorruptException();
                }

                return bytes;
            }
            catch
            {
                CryptographicOperations.ZeroMemory(bytes);
                throw;
            }
        }
    }

    private static void DeleteManagedFileUnsafe(string path)
    {
        if (MemoryPathPolicy.TryOpenRegularFile(
                path,
                FileAccess.Read,
                FileShare.Read,
                deleteAccess: true,
                out WindowsPrivateFileLease? file))
        {
            using (file)
            {
                MemoryPathPolicy.DeleteRegularFile(file);
            }
        }
    }

    private static void DestroyCandidateUnsafe(WindowsPrivateFileLease candidate)
    {
        try
        {
            MemoryPathPolicy.DeleteRegularFile(candidate);
        }
        catch (UnsafeMemoryStorePathException)
        {
            candidate.Stream.SetLength(0);
            candidate.Stream.Flush(flushToDisk: true);
        }
    }

    private void InvokeCrashHook(MemoryCommitStage stage) => _crashHook?.Invoke(stage);

    private DateTimeOffset GetUtcNow() => _timeProvider.GetUtcNow().ToUniversalTime();

    private static bool IsRecoverableStoreReadFailure(Exception exception) =>
        exception is MemoryStoreException
            or ProtectedPayloadException
            or IOException
            or UnauthorizedAccessException
            or CryptographicException
            or JsonException;

    private static string NormalizeSelector(string value, string parameterName) =>
        NormalizeCollapsedText(
            value,
            parameterName,
            MaximumSelectorUtf8Bytes,
            caseFold: true);

    private static string NormalizeTag(string value, string parameterName) =>
        NormalizeCollapsedText(value, parameterName, MaximumTagUtf8Bytes, caseFold: true);

    private static string NormalizeLabel(string value, string parameterName) =>
        NormalizeCollapsedText(value, parameterName, MaximumLabelUtf8Bytes, caseFold: false);

    private static string NormalizeIdentifier(string value, string parameterName) =>
        NormalizeCollapsedText(value, parameterName, MaximumIdentifierUtf8Bytes, caseFold: false);

    private static string? NormalizeOptionalIdentifier(string? value, string parameterName) =>
        value is null ? null : NormalizeIdentifier(value, parameterName);

    private static string NormalizeValue(string value, string parameterName)
    {
        ArgumentNullException.ThrowIfNull(value, parameterName);
        string normalized;
        try
        {
            normalized = value.Normalize(NormalizationForm.FormC);
            if (normalized.Length == 0
                || normalized.Any(character => char.IsControl(character)
                    && character is not ('\r' or '\n' or '\t'))
                || StrictUtf8.GetByteCount(normalized) > MaximumValueUtf8Bytes)
            {
                throw new ArgumentException("The memory value is invalid.", parameterName);
            }
        }
        catch (EncoderFallbackException exception)
        {
            throw new ArgumentException("The memory value is invalid.", parameterName, exception);
        }

        return normalized;
    }

    private static string NormalizeCollapsedText(
        string value,
        string parameterName,
        int maximumUtf8Bytes,
        bool caseFold)
    {
        ArgumentNullException.ThrowIfNull(value, parameterName);
        string normalized;
        try
        {
            normalized = value.Normalize(NormalizationForm.FormC);
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
                    throw new ArgumentException("The memory text is invalid.", parameterName);
                }

                if (pendingSpace)
                {
                    _ = builder.Append(' ');
                    pendingSpace = false;
                }

                _ = builder.Append(character);
            }

            normalized = builder.ToString();
            if (caseFold)
            {
                normalized = normalized.ToUpperInvariant();
            }

            if (normalized.Length == 0 || StrictUtf8.GetByteCount(normalized) > maximumUtf8Bytes)
            {
                throw new ArgumentException("The memory text is invalid.", parameterName);
            }
        }
        catch (EncoderFallbackException exception)
        {
            throw new ArgumentException("The memory text is invalid.", parameterName, exception);
        }

        return normalized;
    }

    private static string NormalizeSearchText(string value) =>
        NormalizeCollapsedText(value, "value", MaximumLabelUtf8Bytes, caseFold: true);

    private static DateTimeOffset? NormalizeOptionalUtc(DateTimeOffset? value) =>
        value?.ToUniversalTime();

    private readonly record struct NormalizedSave(
        string Selector,
        string Label,
        string Value,
        MemoryKind Kind,
        MemorySensitivity Sensitivity,
        MemoryRetention Retention,
        string[] Tags,
        DateTimeOffset? ExpiresAtUtc,
        string? SourceMissionId,
        DateTimeOffset? CapturedAtUtc,
        string? SessionId);

    private readonly record struct NormalizedForget(
        MemoryForgetScope Scope,
        string? Selector,
        MemoryKind? Kind,
        string? Topic,
        string? SessionId);

    private sealed record SnapshotCandidate(
        MemoryStateDocument State,
        byte[] Envelope,
        string Digest);

    private sealed class RequestDigestBuilder : IDisposable
    {
        private readonly IncrementalHash _hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);

        public void Append(string? value)
        {
            if (value is null)
            {
                Append(-1);
                return;
            }

            byte[] bytes = StrictUtf8.GetBytes(value);
            try
            {
                Append(bytes.Length);
                _hash.AppendData(bytes);
            }
            finally
            {
                CryptographicOperations.ZeroMemory(bytes);
            }
        }

        public void Append(bool value) => Append(value ? 1 : 0);

        public void Append(int? value) => Append(value ?? int.MinValue);

        public void Append(int value)
        {
            Span<byte> bytes = stackalloc byte[sizeof(int)];
            BinaryPrimitives.WriteInt32LittleEndian(bytes, value);
            _hash.AppendData(bytes);
        }

        public void Append(DateTimeOffset? value)
        {
            if (!value.HasValue)
            {
                Append((string?)null);
                return;
            }

            Span<byte> bytes = stackalloc byte[sizeof(long)];
            BinaryPrimitives.WriteInt64LittleEndian(bytes, value.Value.UtcTicks);
            Append(bytes.Length);
            _hash.AppendData(bytes);
        }

        public string GetDigest() => Convert.ToHexStringLower(_hash.GetHashAndReset());

        public void Dispose() => _hash.Dispose();
    }
}

internal enum MemoryCommitStage
{
    IntentDurable,
    CurrentDurable,
    RecoveryDurable,
    WatermarkDurable,
    Verified,
    IntentDeleted,
}
