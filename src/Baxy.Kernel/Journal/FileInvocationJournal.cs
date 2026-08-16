using System.Buffers;
using System.Security.Cryptography;
using System.Text.Json;
using Baxy.Contracts;

namespace Baxy.Kernel.Journal;

public sealed class FileInvocationJournal : IInvocationJournal, IAsyncDisposable
{
    private const int JournalFormatVersion = 2;
    private const long DefaultMaximumJournalBytes = 64L * 1024 * 1024;
    private const int DefaultCompletionReservationBytes = 2 * 1024 * 1024;
    private const int MaximumRecordBytes = DefaultCompletionReservationBytes;
    private const string InitialTag =
        "0000000000000000000000000000000000000000000000000000000000000000";
    private const string RecordAuthenticationDomain = "baxy.journal.record.v2";
    private const string AnchorAuthenticationDomain = "baxy.journal.anchor.v2";
    private const int MaximumAnchorBytes = 4096;
    private static readonly byte[] Newline = [(byte)'\n'];

    private readonly string _path;
    private readonly string _anchorPath;
    private readonly JournalHmacAuthenticator _authenticator;
    private FileStream _stream;
    private readonly SemaphoreSlim _gate = new(1, 1);
    private readonly Dictionary<string, CompletedInvocation> _completed =
        new(StringComparer.Ordinal);
    private readonly Dictionary<string, string> _started = new(StringComparer.Ordinal);
    private readonly Dictionary<string, JournalPayload> _retainedStates = new(StringComparer.Ordinal);
    private readonly HashSet<string> _completionReservations = new(StringComparer.Ordinal);
    private readonly long _maximumJournalBytes;
    private readonly int _completionReservationBytes;
    private readonly Action<JournalCommitStage>? _crashHook;
    private long _sequence;
    private string _lastTag = InitialTag;
    private bool _disposed;
    private bool _faulted;

    private FileInvocationJournal(
        string path,
        FileStream stream,
        JournalHmacAuthenticator authenticator,
        long maximumJournalBytes,
        int completionReservationBytes,
        Action<JournalCommitStage>? crashHook)
    {
        _path = path;
        _anchorPath = string.Concat(path, ".anchor");
        _stream = stream;
        _authenticator = authenticator;
        _maximumJournalBytes = maximumJournalBytes;
        _completionReservationBytes = completionReservationBytes;
        _crashHook = crashHook;
    }

    /// <summary>
    /// Opens an authenticated journal and takes ownership of
    /// <paramref name="authenticator"/>, including when opening fails.
    /// </summary>
    public static async ValueTask<FileInvocationJournal> OpenAsync(
        string journalPath,
        JournalHmacAuthenticator authenticator,
        CancellationToken cancellationToken = default) =>
        await OpenCoreAsync(
            journalPath,
            authenticator,
            DefaultMaximumJournalBytes,
            DefaultCompletionReservationBytes,
            crashHook: null,
            cancellationToken).ConfigureAwait(false);

    internal static async ValueTask<FileInvocationJournal> OpenWithCapacityForTestingAsync(
        string journalPath,
        JournalHmacAuthenticator authenticator,
        long maximumJournalBytes,
        int completionReservationBytes,
        Action<JournalCommitStage>? crashHook = null,
        CancellationToken cancellationToken = default) =>
        await OpenCoreAsync(
            journalPath,
            authenticator,
            maximumJournalBytes,
            completionReservationBytes,
            crashHook,
            cancellationToken).ConfigureAwait(false);

    private static async ValueTask<FileInvocationJournal> OpenCoreAsync(
        string journalPath,
        JournalHmacAuthenticator authenticator,
        long maximumJournalBytes,
        int completionReservationBytes,
        Action<JournalCommitStage>? crashHook,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(authenticator);
        bool ownershipTransferred = false;
        try
        {
            if (maximumJournalBytes <= 0)
            {
                throw new ArgumentOutOfRangeException(
                    nameof(maximumJournalBytes),
                    "Maximum journal size must be positive.");
            }

            if (completionReservationBytes <= 0
                || completionReservationBytes >= maximumJournalBytes
                || completionReservationBytes > MaximumRecordBytes)
            {
                throw new ArgumentOutOfRangeException(
                    nameof(completionReservationBytes),
                    "Completion reservation must fit inside the journal and record limits.");
            }

            string path = PreparePath(journalPath);
            FileStream stream = OpenJournalStream(path);
            var journal = new FileInvocationJournal(
                path,
                stream,
                authenticator,
                maximumJournalBytes,
                completionReservationBytes,
                crashHook);
            ownershipTransferred = true;
            try
            {
                await journal.LoadAsync(cancellationToken).ConfigureAwait(false);
                return journal;
            }
            catch
            {
                await journal.DisposeAsync().ConfigureAwait(false);
                throw;
            }
        }
        catch
        {
            if (!ownershipTransferred)
            {
                authenticator.Dispose();
            }

            throw;
        }
    }

    private static FileStream OpenJournalStream(string path) =>
        new(
            path,
            FileMode.OpenOrCreate,
            FileAccess.ReadWrite,
            FileShare.Read,
            bufferSize: 4096,
            FileOptions.Asynchronous | FileOptions.WriteThrough);

    public async ValueTask<string?> FindStartedFingerprintAsync(
        string invocationId,
        CancellationToken cancellationToken)
    {
        EnsureUsable();
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            return _started.GetValueOrDefault(invocationId);
        }
        finally
        {
            _gate.Release();
        }
    }

    public async ValueTask<CompletedInvocation?> FindCompletedAsync(
        string invocationId,
        CancellationToken cancellationToken)
    {
        EnsureUsable();
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            return _completed.GetValueOrDefault(invocationId);
        }
        finally
        {
            _gate.Release();
        }
    }

    public async ValueTask RecordStartedAsync(
        OperationRequest request,
        string requestFingerprint,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentException.ThrowIfNullOrWhiteSpace(requestFingerprint);
        EnsureUsable();

        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (_completed.ContainsKey(request.InvocationId))
            {
                throw new InvalidOperationException("Invocation is already complete.");
            }

            if (_started.TryGetValue(request.InvocationId, out string? previousFingerprint) &&
                !string.Equals(previousFingerprint, requestFingerprint, StringComparison.Ordinal))
            {
                throw new JournalIntegrityException(
                    "An incomplete invocation was reused with a different request fingerprint.");
            }

            if (previousFingerprint is not null)
            {
                await EnsureCapacityAsync(
                        immediateBytes: 0,
                        request.InvocationId,
                        cancellationToken)
                    .ConfigureAwait(false);
                _completionReservations.Add(request.InvocationId);
                return;
            }

            var payload = CreatePayload(JournalPhases.Started, request, requestFingerprint, response: null);
            payload = await AppendStartedAsync(payload, cancellationToken).ConfigureAwait(false);
            _started[request.InvocationId] = requestFingerprint;
            _retainedStates[request.InvocationId] = payload;
            _completionReservations.Add(request.InvocationId);
        }
        finally
        {
            _gate.Release();
        }
    }

    public async ValueTask RecordCompletedAsync(
        OperationRequest request,
        string requestFingerprint,
        OperationResponse response,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentException.ThrowIfNullOrWhiteSpace(requestFingerprint);
        ArgumentNullException.ThrowIfNull(response);
        if (!OperationStatuses.IsTerminal(response.Status))
        {
            throw new ArgumentException(
                "Only terminal responses can complete an invocation.",
                nameof(response));
        }

        EnsureUsable();

        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (!_started.TryGetValue(request.InvocationId, out string? startedFingerprint) ||
                !string.Equals(startedFingerprint, requestFingerprint, StringComparison.Ordinal))
            {
                throw new JournalIntegrityException(
                    "Completion does not match a recorded invocation start.");
            }

            if (_completed.ContainsKey(request.InvocationId))
            {
                throw new InvalidOperationException("Invocation is already complete.");
            }

            if (!_completionReservations.Contains(request.InvocationId))
            {
                throw new JournalCapacityException(
                    "Completion has no capacity reserved before effect execution.");
            }

            var payload = CreatePayload(JournalPhases.Completed, request, requestFingerprint, response);
            payload = await AppendCompletedAsync(payload, cancellationToken).ConfigureAwait(false);
            _completed.Add(
                request.InvocationId,
                new CompletedInvocation(requestFingerprint, response));
            _retainedStates[request.InvocationId] = payload;
            _completionReservations.Remove(request.InvocationId);
        }
        finally
        {
            _gate.Release();
        }
    }

    public async ValueTask DisposeAsync()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        try
        {
            await _stream.DisposeAsync().ConfigureAwait(false);
        }
        finally
        {
            _authenticator.Dispose();
            _gate.Dispose();
        }
    }

    private void EnsureUsable()
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        if (_faulted)
        {
            throw new JournalIntegrityException(
                "The journal must be reopened after an interrupted durable transition.");
        }
    }

    private static string PreparePath(string journalPath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(journalPath);
        string fullPath = Path.GetFullPath(journalPath);
        string? directory = Path.GetDirectoryName(fullPath);
        if (string.IsNullOrEmpty(directory))
        {
            throw new ArgumentException("Journal path must have a parent directory.", nameof(journalPath));
        }

        EnsureNoReparsePoint(directory, createMissing: true);
        string root = Path.GetPathRoot(fullPath) ?? string.Empty;
        if (fullPath.IndexOf(':', root.Length) >= 0)
        {
            throw new ArgumentException("Journal path cannot use an alternate data stream.", nameof(journalPath));
        }

        if (Path.Exists(fullPath) &&
            (File.GetAttributes(fullPath) & FileAttributes.ReparsePoint) != 0)
        {
            throw new IOException("Journal file cannot be a reparse point.");
        }

        return fullPath;
    }

    private static void EnsureNoReparsePoint(string directory, bool createMissing)
    {
        string fullDirectory = Path.GetFullPath(directory);
        string? root = Path.GetPathRoot(fullDirectory);
        if (string.IsNullOrEmpty(root))
        {
            throw new InvalidDataException("Directory has no filesystem root.");
        }

        string current = root;
        string remainder = fullDirectory[root.Length..];
        foreach (string segment in remainder.Split(
                     Path.DirectorySeparatorChar,
                     StringSplitOptions.RemoveEmptyEntries))
        {
            current = Path.Combine(current, segment);
            if (!Directory.Exists(current))
            {
                if (!createMissing)
                {
                    throw new DirectoryNotFoundException(current);
                }

                Directory.CreateDirectory(current);
            }

            if ((File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
            {
                throw new IOException("Journal directory cannot traverse a reparse point.");
            }
        }
    }

    private async ValueTask LoadAsync(CancellationToken cancellationToken)
    {
        _ = PreparePath(_anchorPath);
        if (_stream.Length > _maximumJournalBytes)
        {
            throw new JournalIntegrityException("Journal exceeds its safe startup size.");
        }

        JournalAnchorPayload anchor = LoadOrInitializeAnchor();

        _stream.Position = 0;
        var line = new ArrayBufferWriter<byte>();
        byte[] buffer = ArrayPool<byte>.Shared.Rent(16 * 1024);
        long completeLength = 0;
        JournalAnchorPosition position = InitialPosition();
        JournalAnchorPosition? positionBeforeLastRecord = null;
        bool incompleteTail = false;
        bool missingFinalNewline = false;
        try
        {
            int read;
            while ((read = await _stream
                       .ReadAsync(buffer.AsMemory(0, buffer.Length), cancellationToken)
                       .ConfigureAwait(false)) > 0)
            {
                long chunkOffset = _stream.Position - read;
                int segmentStart = 0;
                for (int index = 0; index < read; index++)
                {
                    if (buffer[index] != (byte)'\n')
                    {
                        continue;
                    }

                    AppendLineBytes(line, buffer.AsSpan(segmentStart, index - segmentStart));
                    if (line.WrittenCount == 0)
                    {
                        throw new JournalIntegrityException("Journal contains an empty record.");
                    }

                    positionBeforeLastRecord = position;
                    LoadRecord(line.WrittenSpan);
                    completeLength = chunkOffset + index + 1;
                    position = new JournalAnchorPosition(
                        _sequence,
                        _lastTag,
                        completeLength);
                    line.Clear();
                    segmentStart = index + 1;
                }

                AppendLineBytes(line, buffer.AsSpan(segmentStart, read - segmentStart));
            }
        }
        finally
        {
            CryptographicOperations.ZeroMemory(buffer);
            ArrayPool<byte>.Shared.Return(buffer);
        }

        if (line.WrittenCount > 0)
        {
            try
            {
                using JsonDocument document = JsonDocument.Parse(line.WrittenMemory);
            }
            catch (JsonException)
            {
                incompleteTail = true;
            }

            if (!incompleteTail)
            {
                if (_stream.Length >= _maximumJournalBytes)
                {
                    throw new JournalIntegrityException(
                        "Journal has no room to repair its missing final newline.");
                }

                positionBeforeLastRecord = position;
                LoadRecord(line.WrittenSpan);
                position = new JournalAnchorPosition(
                    _sequence,
                    _lastTag,
                    checked(_stream.Length + 1));
                missingFinalNewline = true;
            }

        }

        await ReconcileAnchorAndTailAsync(
                anchor,
                position,
                positionBeforeLastRecord,
                completeLength,
                incompleteTail,
                missingFinalNewline,
                cancellationToken)
            .ConfigureAwait(false);
        RestoreLoadedCompletionReservations();
    }

    private void RestoreLoadedCompletionReservations()
    {
        _completionReservations.Clear();
        foreach (string invocationId in _started.Keys)
        {
            if (!_completed.ContainsKey(invocationId))
            {
                _completionReservations.Add(invocationId);
            }
        }

        if (!FitsCapacity(immediateBytes: 0, _completionReservations.Count))
        {
            throw new JournalIntegrityException(
                "Journal cannot honor every incomplete invocation's completion reservation.");
        }
    }

    private JournalAnchorPayload LoadOrInitializeAnchor()
    {
        if (!File.Exists(_anchorPath))
        {
            if (_stream.Length != 0)
            {
                throw new JournalIntegrityException(
                    "An existing journal has no authenticated tail anchor. Unsigned journals are not migrated.");
            }

            JournalAnchorPayload initial = CommittedAnchor(InitialPosition());
            WriteAnchor(initial);
            return initial;
        }

        return ReadAnchorFile(_anchorPath);
    }

    private async ValueTask ReconcileAnchorAndTailAsync(
        JournalAnchorPayload anchor,
        JournalAnchorPosition actual,
        JournalAnchorPosition? positionBeforeLastRecord,
        long completeLength,
        bool incompleteTail,
        bool missingFinalNewline,
        CancellationToken cancellationToken)
    {
        JournalAnchorPosition committed;
        bool updateAnchor = false;
        if (string.Equals(anchor.Phase, JournalAnchorPhases.Committed, StringComparison.Ordinal))
        {
            if (PositionsEqual(actual, anchor.Current))
            {
                committed = anchor.Current;
            }
            else if (!incompleteTail
                && positionBeforeLastRecord is not null
                && PositionsEqual(positionBeforeLastRecord, anchor.Current)
                && actual.Sequence == anchor.Current.Sequence + 1)
            {
                // A record is made durable before its anchor. Exactly one valid,
                // canonical, HMAC-authenticated record may therefore be ahead.
                committed = actual;
                updateAnchor = true;
            }
            else
            {
                throw new JournalIntegrityException(
                    "Journal length or tail does not match its authenticated anchor.");
            }
        }
        else if (string.Equals(
            anchor.Phase,
            JournalAnchorPhases.CompactionPending,
            StringComparison.Ordinal))
        {
            if (PositionsEqual(actual, anchor.Current))
            {
                committed = anchor.Current;
            }
            else if (anchor.Next is not null && PositionsEqual(actual, anchor.Next))
            {
                committed = anchor.Next;
            }
            else
            {
                throw new JournalIntegrityException(
                    "Interrupted compaction matches neither authenticated journal state.");
            }

            updateAnchor = true;
        }
        else
        {
            throw new JournalIntegrityException("Journal anchor phase is invalid.");
        }

        if (incompleteTail)
        {
            if (_stream.Length <= completeLength)
            {
                throw new JournalIntegrityException("Journal tail recovery length is invalid.");
            }

            _stream.SetLength(completeLength);
            _stream.Flush(flushToDisk: true);
        }
        else if (missingFinalNewline)
        {
            _stream.Position = _stream.Length;
            await _stream.WriteAsync(Newline, cancellationToken).ConfigureAwait(false);
            await _stream.FlushAsync(cancellationToken).ConfigureAwait(false);
            _stream.Flush(flushToDisk: true);
        }

        if (_stream.Length != committed.JournalLength)
        {
            throw new JournalIntegrityException(
                "Journal physical length does not match its authenticated anchor.");
        }

        if (updateAnchor)
        {
            WriteCommittedAnchor(committed);
        }

        _stream.Position = _stream.Length;
    }

    private static JournalAnchorPosition InitialPosition() =>
        new(Sequence: 0, LastTag: InitialTag, JournalLength: 0);

    private static JournalAnchorPayload CommittedAnchor(JournalAnchorPosition position) =>
        new(
            JournalFormatVersion,
            JournalHmacAuthenticator.Algorithm,
            JournalAnchorPhases.Committed,
            position,
            Next: null);

    private static JournalAnchorPayload CompactionPendingAnchor(
        JournalAnchorPosition current,
        JournalAnchorPosition next) =>
        new(
            JournalFormatVersion,
            JournalHmacAuthenticator.Algorithm,
            JournalAnchorPhases.CompactionPending,
            current,
            next);

    private static bool PositionsEqual(
        JournalAnchorPosition left,
        JournalAnchorPosition right) =>
        left.Sequence == right.Sequence
        && left.JournalLength == right.JournalLength
        && string.Equals(left.LastTag, right.LastTag, StringComparison.Ordinal);

    private static void AppendLineBytes(
        ArrayBufferWriter<byte> line,
        ReadOnlySpan<byte> segment)
    {
        if (line.WrittenCount + segment.Length > MaximumRecordBytes)
        {
            throw new JournalIntegrityException("Journal contains an oversized record.");
        }

        line.Write(segment);
    }

    private void LoadRecord(ReadOnlySpan<byte> line)
    {
        JournalEnvelope envelope;
        try
        {
            envelope = JsonSerializer.Deserialize(line, JournalJsonContext.Default.JournalEnvelope)
                ?? throw new JournalIntegrityException("Journal contains a null record.");
        }
        catch (JsonException exception)
        {
            throw new JournalIntegrityException("Journal contains malformed JSON.", exception);
        }

        JournalPayload payload = envelope.Payload
            ?? throw new JournalIntegrityException("Journal payload is null.");
        if (envelope.Version != JournalFormatVersion
            || !string.Equals(
                envelope.Authentication,
                JournalHmacAuthenticator.Algorithm,
                StringComparison.Ordinal)
            || payload.Sequence != _sequence + 1
            || !IsLowerHexSha256(envelope.PreviousTag)
            || !IsLowerHexSha256(envelope.Tag)
            || !string.Equals(envelope.PreviousTag, _lastTag, StringComparison.Ordinal)
            || !FixedTimeTagEquals(
                ComputeRecordTag(payload, envelope.PreviousTag),
                envelope.Tag))
        {
            throw new JournalIntegrityException("Journal HMAC chain is invalid.");
        }

        byte[] canonical = JsonSerializer.SerializeToUtf8Bytes(
            envelope,
            JournalJsonContext.Default.JournalEnvelope);
        try
        {
            if (!line.SequenceEqual(canonical))
            {
                throw new JournalIntegrityException("Journal record is not canonical JSON.");
            }
        }
        finally
        {
            CryptographicOperations.ZeroMemory(canonical);
        }

        ValidatePayload(payload);
        if (string.Equals(payload.Phase, JournalPhases.Started, StringComparison.Ordinal))
        {
            if (payload.Response is not null)
            {
                throw new JournalIntegrityException("Journal start unexpectedly contains a response.");
            }

            if (_completed.ContainsKey(payload.InvocationId))
            {
                throw new JournalIntegrityException("Completed invocation was started again.");
            }

            if (_started.TryGetValue(payload.InvocationId, out string? previous) &&
                !string.Equals(previous, payload.RequestFingerprint, StringComparison.Ordinal))
            {
                throw new JournalIntegrityException("Invocation starts disagree on fingerprint.");
            }

            _started[payload.InvocationId] = payload.RequestFingerprint;
            _retainedStates[payload.InvocationId] = payload;
        }
        else if (string.Equals(payload.Phase, JournalPhases.Completed, StringComparison.Ordinal))
        {
            if (payload.Response is null ||
                !_started.TryGetValue(payload.InvocationId, out string? startedFingerprint) ||
                !string.Equals(startedFingerprint, payload.RequestFingerprint, StringComparison.Ordinal) ||
                _completed.ContainsKey(payload.InvocationId))
            {
                throw new JournalIntegrityException("Journal completion is inconsistent.");
            }

            ValidateTerminalResponse(payload.Response);
            _completed.Add(
                payload.InvocationId,
                new CompletedInvocation(payload.RequestFingerprint, payload.Response));
            _retainedStates[payload.InvocationId] = payload;
        }
        else if (string.Equals(payload.Phase, JournalPhases.RetainedCompleted, StringComparison.Ordinal))
        {
            if (payload.Response is null
                || _started.ContainsKey(payload.InvocationId)
                || _completed.ContainsKey(payload.InvocationId))
            {
                throw new JournalIntegrityException("Retained journal completion is inconsistent.");
            }

            ValidateTerminalResponse(payload.Response);
            _started.Add(payload.InvocationId, payload.RequestFingerprint);
            _completed.Add(
                payload.InvocationId,
                new CompletedInvocation(payload.RequestFingerprint, payload.Response));
            _retainedStates.Add(payload.InvocationId, payload);
        }
        else
        {
            throw new JournalIntegrityException("Journal phase is unknown.");
        }

        _sequence = payload.Sequence;
        _lastTag = envelope.Tag;
    }

    private async ValueTask<JournalPayload> AppendStartedAsync(
        JournalPayload payload,
        CancellationToken cancellationToken)
    {
        payload = payload with { Sequence = _sequence + 1 };
        byte[] json = SerializeEnvelope(payload, _lastTag, out string tag);
        try
        {
            int reservationCount = _completionReservations.Contains(payload.InvocationId)
                ? _completionReservations.Count
                : _completionReservations.Count + 1;
            if (!FitsCapacity(json.Length + 1, reservationCount) && _stream.Length > 0)
            {
                CryptographicOperations.ZeroMemory(json);
                await CompactAsync(cancellationToken).ConfigureAwait(false);
                payload = payload with { Sequence = _sequence + 1 };
                json = SerializeEnvelope(payload, _lastTag, out tag);
            }

            if (json.Length + 1 > MaximumRecordBytes
                || !FitsCapacity(json.Length + 1, reservationCount))
            {
                throw new JournalCapacityException(
                    "Journal cannot reserve a completion before effect execution.");
            }

            await WriteRecordAsync(payload, json, tag, cancellationToken).ConfigureAwait(false);
            return payload;
        }
        finally
        {
            CryptographicOperations.ZeroMemory(json);
        }
    }

    private async ValueTask<JournalPayload> AppendCompletedAsync(
        JournalPayload payload,
        CancellationToken cancellationToken)
    {
        payload = payload with { Sequence = _sequence + 1 };
        byte[] json = SerializeEnvelope(payload, _lastTag, out string tag);
        try
        {
            int remainingReservations = _completionReservations.Count - 1;
            if (json.Length + 1 > _completionReservationBytes)
            {
                throw new JournalCapacityException(
                    "Journal completion exceeds the capacity reserved before effect execution.");
            }

            if (!FitsCapacity(json.Length + 1, remainingReservations) && _stream.Length > 0)
            {
                CryptographicOperations.ZeroMemory(json);
                await CompactAsync(cancellationToken).ConfigureAwait(false);
                payload = payload with { Sequence = _sequence + 1 };
                json = SerializeEnvelope(payload, _lastTag, out tag);
            }

            if (json.Length + 1 > _completionReservationBytes
                || !FitsCapacity(json.Length + 1, remainingReservations))
            {
                throw new JournalCapacityException("Journal completion no longer fits its reservation.");
            }

            await WriteRecordAsync(payload, json, tag, cancellationToken).ConfigureAwait(false);
            return payload;
        }
        finally
        {
            CryptographicOperations.ZeroMemory(json);
        }
    }

    private async ValueTask EnsureCapacityAsync(
        int immediateBytes,
        string invocationId,
        CancellationToken cancellationToken)
    {
        int reservationCount = _completionReservations.Contains(invocationId)
            ? _completionReservations.Count
            : _completionReservations.Count + 1;
        if (!FitsCapacity(immediateBytes, reservationCount) && _stream.Length > 0)
        {
            await CompactAsync(cancellationToken).ConfigureAwait(false);
        }

        if (!FitsCapacity(immediateBytes, reservationCount))
        {
            throw new JournalCapacityException(
                "Journal cannot reserve a completion before effect execution.");
        }
    }

    private bool FitsCapacity(int immediateBytes, int reservationCount)
    {
        if (immediateBytes < 0
            || reservationCount < 0
            || _stream.Length > _maximumJournalBytes)
        {
            return false;
        }

        long remainingBytes = _maximumJournalBytes - _stream.Length;
        if (immediateBytes > remainingBytes)
        {
            return false;
        }

        remainingBytes -= immediateBytes;
        return reservationCount <= remainingBytes / _completionReservationBytes;
    }

    private async ValueTask WriteRecordAsync(
        JournalPayload payload,
        byte[] json,
        string tag,
        CancellationToken cancellationToken)
    {
        if (_stream.Length > _maximumJournalBytes - json.Length - 1)
        {
            throw new JournalCapacityException("Journal reached its hard size limit.");
        }

        try
        {
            _stream.Position = _stream.Length;
            await _stream.WriteAsync(json, cancellationToken).ConfigureAwait(false);
            await _stream.WriteAsync(Newline, cancellationToken).ConfigureAwait(false);
            await _stream.FlushAsync(cancellationToken).ConfigureAwait(false);
            _stream.Flush(flushToDisk: true);
            InvokeCrashHook(JournalCommitStage.RecordDurableBeforeAnchor);

            var position = new JournalAnchorPosition(
                payload.Sequence,
                tag,
                _stream.Length);
            WriteCommittedAnchor(position);
            InvokeCrashHook(JournalCommitStage.AnchorDurable);

            _sequence = payload.Sequence;
            _lastTag = tag;
        }
        catch
        {
            _faulted = true;
            throw;
        }
    }

    private byte[] SerializeEnvelope(
        JournalPayload payload,
        string previousTag,
        out string tag)
    {
        tag = ComputeRecordTag(payload, previousTag);
        var envelope = new JournalEnvelope(
            JournalFormatVersion,
            JournalHmacAuthenticator.Algorithm,
            payload,
            previousTag,
            tag);
        return JsonSerializer.SerializeToUtf8Bytes(
            envelope,
            JournalJsonContext.Default.JournalEnvelope);
    }

    private string ComputeRecordTag(JournalPayload payload, string previousTag)
    {
        var unsigned = new JournalUnsignedEnvelope(
            JournalFormatVersion,
            JournalHmacAuthenticator.Algorithm,
            payload,
            previousTag);
        byte[] canonical = JsonSerializer.SerializeToUtf8Bytes(
            unsigned,
            JournalJsonContext.Default.JournalUnsignedEnvelope);
        try
        {
            return _authenticator.ComputeTag(RecordAuthenticationDomain, canonical);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(canonical);
        }
    }

    private string ComputeAnchorTag(JournalAnchorPayload payload)
    {
        byte[] canonical = JsonSerializer.SerializeToUtf8Bytes(
            payload,
            JournalJsonContext.Default.JournalAnchorPayload);
        try
        {
            return _authenticator.ComputeTag(AnchorAuthenticationDomain, canonical);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(canonical);
        }
    }

    private void WriteCommittedAnchor(JournalAnchorPosition position) =>
        WriteAnchor(CommittedAnchor(position));

    private void WriteAnchor(JournalAnchorPayload payload) =>
        WriteAnchorFile(_anchorPath, payload);

    private void WriteAnchorFile(string path, JournalAnchorPayload payload)
    {
        ValidateAnchorPayload(payload);
        string tag = ComputeAnchorTag(payload);
        var envelope = new JournalAnchorEnvelope(payload, tag);
        byte[] bytes = JsonSerializer.SerializeToUtf8Bytes(
            envelope,
            JournalJsonContext.Default.JournalAnchorEnvelope);
        if (bytes.Length is < 1 or > MaximumAnchorBytes)
        {
            CryptographicOperations.ZeroMemory(bytes);
            throw new JournalIntegrityException("Journal anchor exceeds its bounded format.");
        }

        string temporaryPath = string.Concat(path, ".tmp");
        try
        {
            _ = PreparePath(path);
            _ = PreparePath(temporaryPath);
            if (File.Exists(temporaryPath))
            {
                File.Delete(temporaryPath);
            }

            using (var stream = new FileStream(
                       temporaryPath,
                       FileMode.CreateNew,
                       FileAccess.Write,
                       FileShare.None,
                       bufferSize: 4096,
                       FileOptions.WriteThrough))
            {
                stream.Write(bytes);
                stream.Flush(flushToDisk: true);
            }

            if (File.Exists(path))
            {
                ReplaceFileWithRetry(
                    temporaryPath,
                    path,
                    ignoreMetadataErrors: false);
            }
            else
            {
                File.Move(temporaryPath, path);
            }

            JournalAnchorPayload verified = ReadAnchorFile(path);
            if (!AnchorPayloadsEqual(payload, verified))
            {
                throw new JournalIntegrityException("Published journal anchor changed.");
            }
        }
        finally
        {
            CryptographicOperations.ZeroMemory(bytes);
            try
            {
                File.Delete(temporaryPath);
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                // The published anchor, if any, remains authoritative.
            }
        }
    }

    private JournalAnchorPayload ReadAnchorFile(string path)
    {
        _ = PreparePath(path);
        byte[] bytes;
        using (var stream = new FileStream(
                   path,
                   FileMode.Open,
                   FileAccess.Read,
                   FileShare.Read,
                   bufferSize: 4096,
                   FileOptions.SequentialScan))
        {
            if (stream.Length is < 1 or > MaximumAnchorBytes)
            {
                throw new JournalIntegrityException("Journal anchor has an invalid length.");
            }

            bytes = GC.AllocateUninitializedArray<byte>(checked((int)stream.Length));
            stream.ReadExactly(bytes);
            if (stream.ReadByte() != -1)
            {
                CryptographicOperations.ZeroMemory(bytes);
                throw new JournalIntegrityException("Journal anchor changed while it was read.");
            }
        }

        try
        {
            JournalAnchorEnvelope envelope;
            try
            {
                envelope = JsonSerializer.Deserialize(
                        bytes,
                        JournalJsonContext.Default.JournalAnchorEnvelope)
                    ?? throw new JournalIntegrityException("Journal anchor is null.");
            }
            catch (JsonException exception)
            {
                throw new JournalIntegrityException("Journal anchor is malformed.", exception);
            }

            JournalAnchorPayload payload = envelope.Payload
                ?? throw new JournalIntegrityException("Journal anchor payload is null.");
            ValidateAnchorPayload(payload);
            if (!IsLowerHexSha256(envelope.Tag)
                || !FixedTimeTagEquals(ComputeAnchorTag(payload), envelope.Tag))
            {
                throw new JournalIntegrityException("Journal anchor HMAC is invalid.");
            }

            byte[] canonical = JsonSerializer.SerializeToUtf8Bytes(
                envelope,
                JournalJsonContext.Default.JournalAnchorEnvelope);
            try
            {
                if (!bytes.AsSpan().SequenceEqual(canonical))
                {
                    throw new JournalIntegrityException("Journal anchor is not canonical JSON.");
                }
            }
            finally
            {
                CryptographicOperations.ZeroMemory(canonical);
            }

            return payload;
        }
        finally
        {
            CryptographicOperations.ZeroMemory(bytes);
        }
    }

    private static void ValidateAnchorPayload(JournalAnchorPayload payload)
    {
        if (payload.Version != JournalFormatVersion
            || !string.Equals(
                payload.Authentication,
                JournalHmacAuthenticator.Algorithm,
                StringComparison.Ordinal)
            || payload.Current is null)
        {
            throw new JournalIntegrityException("Journal anchor header is invalid.");
        }

        ValidateAnchorPosition(payload.Current);
        bool validShape = payload.Phase switch
        {
            JournalAnchorPhases.Committed => payload.Next is null,
            JournalAnchorPhases.CompactionPending => payload.Next is not null,
            _ => false,
        };
        if (!validShape)
        {
            throw new JournalIntegrityException("Journal anchor phase shape is invalid.");
        }

        if (payload.Next is not null)
        {
            ValidateAnchorPosition(payload.Next);
        }
    }

    private static void ValidateAnchorPosition(JournalAnchorPosition position)
    {
        if (position.Sequence < 0
            || position.JournalLength < 0
            || !IsLowerHexSha256(position.LastTag)
            || (position.Sequence == 0
                && (!string.Equals(position.LastTag, InitialTag, StringComparison.Ordinal)
                    || position.JournalLength != 0))
            || (position.Sequence > 0 && position.JournalLength == 0))
        {
            throw new JournalIntegrityException("Journal anchor position is invalid.");
        }
    }

    private static bool AnchorPayloadsEqual(
        JournalAnchorPayload left,
        JournalAnchorPayload right) =>
        left.Version == right.Version
        && string.Equals(left.Authentication, right.Authentication, StringComparison.Ordinal)
        && string.Equals(left.Phase, right.Phase, StringComparison.Ordinal)
        && PositionsEqual(left.Current, right.Current)
        && ((left.Next is null && right.Next is null)
            || (left.Next is not null
                && right.Next is not null
                && PositionsEqual(left.Next, right.Next)));

    private static bool FixedTimeTagEquals(string expected, string actual)
    {
        if (!IsLowerHexSha256(expected) || !IsLowerHexSha256(actual))
        {
            return false;
        }

        Span<byte> expectedBytes = stackalloc byte[64];
        Span<byte> actualBytes = stackalloc byte[64];
        for (int index = 0; index < 64; index++)
        {
            expectedBytes[index] = checked((byte)expected[index]);
            actualBytes[index] = checked((byte)actual[index]);
        }

        return CryptographicOperations.FixedTimeEquals(expectedBytes, actualBytes);
    }

    private void InvokeCrashHook(JournalCommitStage stage) => _crashHook?.Invoke(stage);

    private async ValueTask CompactAsync(CancellationToken cancellationToken)
    {
        string directory = Path.GetDirectoryName(_path)!;
        string temporaryPath = Path.Combine(
            directory,
            $".{Path.GetFileName(_path)}.{Guid.NewGuid():N}.compact.tmp");
        var compactedStates = new Dictionary<string, JournalPayload>(
            _retainedStates.Count,
            StringComparer.Ordinal);
        long compactedSequence = 0;
        string compactedLastTag = InitialTag;
        string candidateAnchorPath = string.Concat(temporaryPath, ".anchor");
        bool transitionStarted = false;

        try
        {
            await using (var compactedStream = new FileStream(
                             temporaryPath,
                             FileMode.CreateNew,
                             FileAccess.Write,
                             FileShare.None,
                             bufferSize: 4096,
                             FileOptions.Asynchronous | FileOptions.WriteThrough))
            {
                foreach (JournalPayload state in _retainedStates.Values
                             .OrderBy(static payload => payload.InvocationId, StringComparer.Ordinal))
                {
                    bool isCompleted = _completed.ContainsKey(state.InvocationId);
                    var compactedPayload = state with
                    {
                        Sequence = ++compactedSequence,
                        Phase = isCompleted
                            ? JournalPhases.RetainedCompleted
                            : JournalPhases.Started,
                        Response = isCompleted ? state.Response : null,
                    };
                    byte[] json = SerializeEnvelope(
                        compactedPayload,
                        compactedLastTag,
                        out string tag);
                    try
                    {
                        if (json.Length + 1 > MaximumRecordBytes
                            || compactedStream.Position > _maximumJournalBytes - json.Length - 1)
                        {
                            throw new JournalCapacityException(
                                "The exact compacted journal exceeds its hard size limit.");
                        }

                        await compactedStream.WriteAsync(json, cancellationToken).ConfigureAwait(false);
                        await compactedStream.WriteAsync(Newline, cancellationToken).ConfigureAwait(false);
                        compactedLastTag = tag;
                        compactedStates.Add(compactedPayload.InvocationId, compactedPayload);
                    }
                    finally
                    {
                        CryptographicOperations.ZeroMemory(json);
                    }
                }

                await compactedStream.FlushAsync(cancellationToken).ConfigureAwait(false);
                compactedStream.Flush(flushToDisk: true);
            }

            WriteAnchorFile(
                candidateAnchorPath,
                CommittedAnchor(new JournalAnchorPosition(
                    compactedSequence,
                    compactedLastTag,
                    new FileInfo(temporaryPath).Length)));
            await VerifyCompactedStateAsync(temporaryPath, cancellationToken).ConfigureAwait(false);
            cancellationToken.ThrowIfCancellationRequested();
            _ = PreparePath(_path);
            _ = PreparePath(temporaryPath);

            var oldPosition = new JournalAnchorPosition(
                _sequence,
                _lastTag,
                _stream.Length);
            var newPosition = new JournalAnchorPosition(
                compactedSequence,
                compactedLastTag,
                new FileInfo(temporaryPath).Length);
            WriteAnchor(CompactionPendingAnchor(oldPosition, newPosition));
            transitionStarted = true;
            InvokeCrashHook(JournalCommitStage.CompactionIntentDurable);

            await _stream.DisposeAsync().ConfigureAwait(false);
            try
            {
                ReplaceFileWithRetry(
                    temporaryPath,
                    _path,
                    ignoreMetadataErrors: false);
            }
            catch
            {
                _stream = OpenJournalStream(_path);
                throw;
            }

            _stream = OpenJournalStream(_path);
            InvokeCrashHook(JournalCommitStage.CompactionJournalPublished);
            WriteCommittedAnchor(newPosition);
            InvokeCrashHook(JournalCommitStage.CompactionAnchorCommitted);

            _sequence = compactedSequence;
            _lastTag = compactedLastTag;
            _retainedStates.Clear();
            foreach ((string invocationId, JournalPayload state) in compactedStates)
            {
                _retainedStates.Add(invocationId, state);
            }

        }
        catch
        {
            if (transitionStarted)
            {
                _faulted = true;
            }

            throw;
        }
        finally
        {
            try
            {
                File.Delete(temporaryPath);
                File.Delete(candidateAnchorPath);
            }
            catch (Exception exception) when (
                exception is IOException or UnauthorizedAccessException)
            {
                // The original or atomically replaced journal remains authoritative.
            }
        }
    }

    private static void ReplaceFileWithRetry(
        string sourcePath,
        string destinationPath,
        bool ignoreMetadataErrors)
    {
        const int maximumAttempts = 200;
        for (int attempt = 1; ; attempt++)
        {
            try
            {
                File.Replace(
                    sourcePath,
                    destinationPath,
                    destinationBackupFileName: null,
                    ignoreMetadataErrors);
                return;
            }
            catch (IOException) when (attempt < maximumAttempts)
            {
                Thread.Sleep(10);
            }
        }
    }

    private async ValueTask VerifyCompactedStateAsync(
        string temporaryPath,
        CancellationToken cancellationToken)
    {
        await using FileInvocationJournal candidate = await OpenCoreAsync(
                temporaryPath,
                _authenticator.Clone(),
                _maximumJournalBytes,
                _completionReservationBytes,
                crashHook: null,
                cancellationToken)
            .ConfigureAwait(false);
        if (candidate._started.Count != _started.Count
            || candidate._completed.Count != _completed.Count)
        {
            throw new JournalIntegrityException("Compacted journal changed invocation counts.");
        }

        foreach ((string invocationId, string fingerprint) in _started)
        {
            if (!candidate._started.TryGetValue(invocationId, out string? candidateFingerprint)
                || !string.Equals(fingerprint, candidateFingerprint, StringComparison.Ordinal))
            {
                throw new JournalIntegrityException("Compacted journal changed a started invocation.");
            }
        }

        foreach ((string invocationId, CompletedInvocation completed) in _completed)
        {
            if (!candidate._completed.TryGetValue(
                    invocationId,
                    out CompletedInvocation? candidateCompleted)
                || !string.Equals(
                    completed.RequestFingerprint,
                    candidateCompleted.RequestFingerprint,
                    StringComparison.Ordinal)
                || !ProtocolJson.SerializeToUtf8Bytes(completed.Response)
                    .AsSpan()
                    .SequenceEqual(ProtocolJson.SerializeToUtf8Bytes(candidateCompleted.Response)))
            {
                throw new JournalIntegrityException("Compacted journal changed a completed invocation.");
            }
        }
    }

    private static void ValidatePayload(JournalPayload payload)
    {
        if (!ContractValidator.IsCanonicalIdentifier(payload.RequestId)
            || !ContractValidator.IsCanonicalIdentifier(payload.MissionId)
            || !ContractValidator.IsCanonicalIdentifier(payload.InvocationId)
            || !ContractValidator.IsOperationName(payload.Operation)
            || payload.TimestampUtc.Offset != TimeSpan.Zero
            || !IsLowerHexSha256(payload.RequestFingerprint))
        {
            throw new JournalIntegrityException("Journal payload fields are invalid.");
        }

        if (payload.Response is not null
            && (!string.Equals(payload.Response.RequestId, payload.RequestId, StringComparison.Ordinal)
                || !string.Equals(payload.Response.MissionId, payload.MissionId, StringComparison.Ordinal)
                || !string.Equals(payload.Response.InvocationId, payload.InvocationId, StringComparison.Ordinal)))
        {
            throw new JournalIntegrityException("Journal response identity does not match its payload.");
        }
    }

    private static void ValidateTerminalResponse(OperationResponse response)
    {
        ContractValidator.Validate(response);
        if (!OperationStatuses.IsTerminal(response.Status))
        {
            throw new JournalIntegrityException(
                "Journal completion contains a nonterminal response.");
        }
    }

    private static bool IsLowerHexSha256(string? value)
    {
        if (value is null || value.Length != 64)
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

    private JournalPayload CreatePayload(
        string phase,
        OperationRequest request,
        string requestFingerprint,
        OperationResponse? response) =>
        new(
            _sequence + 1,
            DateTimeOffset.UtcNow,
            phase,
            request.RequestId,
            request.MissionId,
            request.InvocationId,
            request.Operation,
            requestFingerprint,
            response);

}

internal enum JournalCommitStage
{
    RecordDurableBeforeAnchor,
    AnchorDurable,
    CompactionIntentDurable,
    CompactionJournalPublished,
    CompactionAnchorCommitted,
}
