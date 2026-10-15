using System.Buffers;
using System.Globalization;
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

    // Rotation (see documentacion/computer-use/JOURNAL_ROTACION.md): once the live
    // segment passes three quarters of its hard cap it is sealed as
    // <name>.<n><ext> beside its own authenticated anchor, and a new live segment
    // starts with the incomplete invocations carried over. The rotation state lives
    // in an authenticated manifest (<name><ext>.segments), never in the live anchor,
    // so the live segment keeps the format a rolled-back Core reads. Only the newest
    // DefaultRetainedArchiveSegments archived segments are kept; older ones are the
    // only files the journal ever deletes on its own, and every completed invocation
    // they held first leaves a retired-id entry (<name><ext>.retired) so a retry of
    // it is refused, never executed again.
    private const long DefaultRotationThresholdBytes = DefaultMaximumJournalBytes / 4 * 3;
    private const int DefaultRetainedArchiveSegments = 2;
    private const string RotationCandidateSuffix = ".rotating";
    private const string ManifestSuffix = ".segments";
    private const string RetiredSuffix = ".retired";
    private const string ResetSuffix = ".reset-";
    private const int ManifestFormatVersion = 1;
    private const string ManifestAuthenticationDomain = "baxy.journal.segments.v1";
    private const string RetiredAuthenticationDomain = "baxy.journal.retired.v1";
    private const string RetiredIdAuthenticationDomain = "baxy.journal.retired.id.v1";
    private const int MaximumManifestBytes = 64 * 1024;
    private const int MaximumManifestEntries = 256;
    private const int RetiredKeyLength = 32;
    private const int RetiredLineLength = RetiredKeyLength + 1;
    private const int RotationPostponementReportInterval = 64;

    // A sealed segment is immutable, so its full scan is remembered in an
    // authenticated sidecar (<segment>.index) and a later open does not
    // re-authenticate up to 48 MiB of records before the Core can answer.
    private const string SegmentIndexSuffix = ".index";
    private const int SegmentIndexFormatVersion = 1;
    private const string SegmentIndexAuthenticationDomain = "baxy.journal.segment.index.v1";
    private const int MaximumSegmentIndexBytes = 16 * 1024 * 1024;
    private static readonly byte[] Newline = [(byte)'\n'];

    private readonly string _path;
    private readonly string _anchorPath;
    private readonly string _manifestPath;
    private readonly string _retiredPath;
    private readonly JournalHmacAuthenticator _authenticator;
    private FileStream _stream;
    private readonly SemaphoreSlim _gate = new(1, 1);
    private readonly Dictionary<string, CompletedInvocation> _completed =
        new(StringComparer.Ordinal);
    private readonly Dictionary<string, string> _started = new(StringComparer.Ordinal);
    private readonly Dictionary<string, JournalPayload> _retainedStates = new(StringComparer.Ordinal);
    private readonly HashSet<string> _completionReservations = new(StringComparer.Ordinal);
    private readonly Dictionary<string, ArchivedInvocation> _archived = new(StringComparer.Ordinal);
    private readonly Dictionary<long, JournalAnchorPosition> _archivedSegments = [];
    private readonly HashSet<string> _retired = new(StringComparer.Ordinal);
    private readonly long _maximumJournalBytes;
    private readonly int _completionReservationBytes;
    private readonly long? _rotationThresholdBytes;
    private readonly int _retainedArchiveSegments;
    private readonly Action<JournalCommitStage>? _crashHook;
    private readonly Action<string>? _diagnostics;
    private JournalSegmentManifest? _manifest;
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
        long? rotationThresholdBytes,
        int retainedArchiveSegments,
        Action<JournalCommitStage>? crashHook,
        Action<string>? diagnostics)
    {
        _path = path;
        _anchorPath = string.Concat(path, ".anchor");
        _manifestPath = string.Concat(path, ManifestSuffix);
        _retiredPath = string.Concat(path, RetiredSuffix);
        _stream = stream;
        _authenticator = authenticator;
        _maximumJournalBytes = maximumJournalBytes;
        _completionReservationBytes = completionReservationBytes;
        _rotationThresholdBytes = rotationThresholdBytes;
        _retainedArchiveSegments = retainedArchiveSegments;
        _crashHook = crashHook;
        _diagnostics = diagnostics;
    }

    /// <summary>
    /// Rotations the filesystem refused before the new segment was published since
    /// this journal was opened. Each one leaves the live segment growing toward its
    /// hard cap, so they are also reported through the diagnostics callback.
    /// </summary>
    public int RotationPostponements { get; private set; }

    public string? LastRotationPostponement { get; private set; }

    /// <summary>
    /// Opens an authenticated journal and takes ownership of
    /// <paramref name="authenticator"/>, including when opening fails.
    /// </summary>
    public static async ValueTask<FileInvocationJournal> OpenAsync(
        string journalPath,
        JournalHmacAuthenticator authenticator,
        CancellationToken cancellationToken = default) =>
        await OpenAsync(
            journalPath,
            authenticator,
            diagnostics: null,
            cancellationToken).ConfigureAwait(false);

    /// <summary>
    /// Opens like <see cref="OpenAsync(string, JournalHmacAuthenticator, CancellationToken)"/>
    /// and reports each postponed rotation (its cause, bounded in frequency) through
    /// <paramref name="diagnostics"/>, so a journal heading to its hard cap shows up
    /// before it refuses operations.
    /// </summary>
    public static async ValueTask<FileInvocationJournal> OpenAsync(
        string journalPath,
        JournalHmacAuthenticator authenticator,
        Action<string>? diagnostics,
        CancellationToken cancellationToken = default) =>
        await OpenCoreAsync(
            journalPath,
            authenticator,
            DefaultMaximumJournalBytes,
            DefaultCompletionReservationBytes,
            DefaultRotationThresholdBytes,
            DefaultRetainedArchiveSegments,
            crashHook: null,
            diagnostics,
            cancellationToken).ConfigureAwait(false);

    /// <summary>
    /// Opens with a test capacity and rotation disabled, so compaction and the hard
    /// cap can be exercised alone. Archived segments a rotation left are still
    /// validated.
    /// </summary>
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
            rotationThresholdBytes: null,
            DefaultRetainedArchiveSegments,
            crashHook,
            diagnostics: null,
            cancellationToken).ConfigureAwait(false);

    internal static async ValueTask<FileInvocationJournal> OpenWithRotationForTestingAsync(
        string journalPath,
        JournalHmacAuthenticator authenticator,
        long maximumJournalBytes,
        int completionReservationBytes,
        long rotationThresholdBytes,
        int retainedArchiveSegments,
        Action<JournalCommitStage>? crashHook = null,
        Action<string>? diagnostics = null,
        CancellationToken cancellationToken = default) =>
        await OpenCoreAsync(
            journalPath,
            authenticator,
            maximumJournalBytes,
            completionReservationBytes,
            rotationThresholdBytes,
            retainedArchiveSegments,
            crashHook,
            diagnostics,
            cancellationToken).ConfigureAwait(false);

    private static async ValueTask<FileInvocationJournal> OpenCoreAsync(
        string journalPath,
        JournalHmacAuthenticator authenticator,
        long maximumJournalBytes,
        int completionReservationBytes,
        long? rotationThresholdBytes,
        int retainedArchiveSegments,
        Action<JournalCommitStage>? crashHook,
        Action<string>? diagnostics,
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

            if (rotationThresholdBytes is { } threshold
                && (threshold <= 0 || threshold > maximumJournalBytes - completionReservationBytes))
            {
                throw new ArgumentOutOfRangeException(
                    nameof(rotationThresholdBytes),
                    "Rotation must start before the journal's last completion reservation.");
            }

            if (retainedArchiveSegments < 1)
            {
                throw new ArgumentOutOfRangeException(
                    nameof(retainedArchiveSegments),
                    "At least the newest archived segment must be retained.");
            }

            string path = PreparePath(journalPath);
            RecoverInterruptedRotation(path, authenticator);
            FileStream stream = OpenJournalStream(path);
            var journal = new FileInvocationJournal(
                path,
                stream,
                authenticator,
                maximumJournalBytes,
                completionReservationBytes,
                rotationThresholdBytes,
                retainedArchiveSegments,
                crashHook,
                diagnostics);
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
            return _started.GetValueOrDefault(invocationId)
                ?? _archived.GetValueOrDefault(invocationId)?.RequestFingerprint;
        }
        finally
        {
            _gate.Release();
        }
    }

    /// <summary>
    /// True when <paramref name="invocationId"/> completed in an archived segment
    /// that retention has since deleted: its response is gone, so a retry must be
    /// refused rather than executed again.
    /// </summary>
    public async ValueTask<bool> IsRetiredAsync(
        string invocationId,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(invocationId);
        EnsureUsable();
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            return IsRetired(invocationId);
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
            if (_completed.TryGetValue(invocationId, out CompletedInvocation? completed))
            {
                return completed;
            }

            if (!_archived.TryGetValue(invocationId, out ArchivedInvocation? archived))
            {
                return null;
            }

            // An archived completion is replayed from its sealed segment, which is
            // authenticated again end to end before its response is trusted.
            SegmentScan scan = await ScanSegmentAsync(
                    SegmentPath(_path, archived.Segment),
                    _archivedSegments[archived.Segment],
                    invocationId,
                    cancellationToken)
                .ConfigureAwait(false);
            if (scan.Target is null
                || !string.Equals(
                    scan.Target.RequestFingerprint,
                    archived.RequestFingerprint,
                    StringComparison.Ordinal))
            {
                throw new JournalIntegrityException(
                    "Archived journal segment no longer holds its indexed completion.");
            }

            return scan.Target;
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
            if (_completed.ContainsKey(request.InvocationId)
                || _archived.ContainsKey(request.InvocationId)
                || IsRetired(request.InvocationId))
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

        JournalAnchorPayload anchor = LoadOrInitializeAnchor(out bool liveInitialized);

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
        DeleteStaleRotationCandidate();
        LoadManifest(liveInitialized);
        await LoadArchivedSegmentsAsync(cancellationToken).ConfigureAwait(false);
        TryEnforceArchiveRetention();
        if (ShouldRotate(pendingBytes: 0))
        {
            await TryRotateAsync(cancellationToken).ConfigureAwait(false);
        }

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

    private JournalAnchorPayload LoadOrInitializeAnchor(out bool initialized)
    {
        initialized = false;
        if (!File.Exists(_anchorPath))
        {
            if (_stream.Length != 0)
            {
                throw new JournalIntegrityException(
                    "An existing journal has no authenticated tail anchor. Unsigned journals are not migrated.");
            }

            JournalAnchorPayload initial = CommittedAnchor(InitialPosition());
            WriteAnchor(initial);
            initialized = true;
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

    private static JournalAnchorPayload ArchivedAnchor(
        long segment,
        JournalAnchorPosition sealedPosition,
        JournalArchiveLink? previous) =>
        new(
            JournalFormatVersion,
            JournalHmacAuthenticator.Algorithm,
            JournalAnchorPhases.Archived,
            sealedPosition,
            Next: null,
            Segment: segment,
            Archive: previous);

    private static bool PositionsEqual(
        JournalAnchorPosition left,
        JournalAnchorPosition right) =>
        left.Sequence == right.Sequence
        && left.JournalLength == right.JournalLength
        && string.Equals(left.LastTag, right.LastTag, StringComparison.Ordinal);

    private static bool LinksEqual(JournalArchiveLink? left, JournalArchiveLink? right) =>
        (left is null && right is null)
        || (left is not null
            && right is not null
            && left.Segment == right.Segment
            && PositionsEqual(left.Position, right.Position));

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
        JournalPayload payload = ParseRecord(line, _sequence + 1, _lastTag, out string tag);
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
        _lastTag = tag;
    }

    /// <summary>
    /// Authenticates one record against the chain position before it: format
    /// version, HMAC chain, sequence, canonical bytes and payload fields.
    /// </summary>
    private JournalPayload ParseRecord(
        ReadOnlySpan<byte> line,
        long expectedSequence,
        string previousTag,
        out string tag)
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
            || payload.Sequence != expectedSequence
            || !IsLowerHexSha256(envelope.PreviousTag)
            || !IsLowerHexSha256(envelope.Tag)
            || !string.Equals(envelope.PreviousTag, previousTag, StringComparison.Ordinal)
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
        tag = envelope.Tag;
        return payload;
    }

    private async ValueTask<JournalPayload> AppendStartedAsync(
        JournalPayload payload,
        CancellationToken cancellationToken)
    {
        payload = payload with { Sequence = _sequence + 1 };
        byte[] json = SerializeEnvelope(payload, _lastTag, out string tag);
        try
        {
            if (ShouldRotate(json.Length + 1))
            {
                CryptographicOperations.ZeroMemory(json);
                await TryRotateAsync(cancellationToken).ConfigureAwait(false);
                payload = payload with { Sequence = _sequence + 1 };
                json = SerializeEnvelope(payload, _lastTag, out tag);
            }

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

    private static string ComputeAnchorTag(
        JournalHmacAuthenticator authenticator,
        JournalAnchorPayload payload)
    {
        byte[] canonical = JsonSerializer.SerializeToUtf8Bytes(
            payload,
            JournalJsonContext.Default.JournalAnchorPayload);
        try
        {
            return authenticator.ComputeTag(AnchorAuthenticationDomain, canonical);
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

    private void WriteAnchorFile(string path, JournalAnchorPayload payload) =>
        WriteAnchorFile(_authenticator, path, payload);

    private static void WriteAnchorFile(
        JournalHmacAuthenticator authenticator,
        string path,
        JournalAnchorPayload payload)
    {
        ValidateAnchorPayload(payload);
        string tag = ComputeAnchorTag(authenticator, payload);
        var envelope = new JournalAnchorEnvelope(payload, tag);
        byte[] bytes = JsonSerializer.SerializeToUtf8Bytes(
            envelope,
            JournalJsonContext.Default.JournalAnchorEnvelope);
        if (bytes.Length is < 1 or > MaximumAnchorBytes)
        {
            CryptographicOperations.ZeroMemory(bytes);
            throw new JournalIntegrityException("Journal anchor exceeds its bounded format.");
        }

        PublishFile(path, bytes);
        JournalAnchorPayload verified = ReadAnchorFile(path, authenticator);
        if (!AnchorPayloadsEqual(payload, verified))
        {
            throw new JournalIntegrityException("Published journal anchor changed.");
        }
    }

    /// <summary>
    /// Publishes <paramref name="bytes"/> at <paramref name="path"/> atomically
    /// (durable temporary file, then replace) and erases the buffer.
    /// </summary>
    private static void PublishFile(string path, byte[] bytes)
    {
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

    private JournalAnchorPayload ReadAnchorFile(string path) =>
        ReadAnchorFile(path, _authenticator);

    private static JournalAnchorPayload ReadAnchorFile(
        string path,
        JournalHmacAuthenticator authenticator)
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
                || !FixedTimeTagEquals(ComputeAnchorTag(authenticator, payload), envelope.Tag))
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
            JournalAnchorPhases.Committed => payload.Next is null
                && payload.Segment is null
                && payload.Archive is null,
            JournalAnchorPhases.CompactionPending => payload.Next is not null
                && payload.Segment is null
                && payload.Archive is null,
            JournalAnchorPhases.Archived => payload.Next is null && payload.Segment is >= 1,
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

        if (payload.Archive is not null)
        {
            // Segment numbers only grow (a reset of the journal may skip some), so
            // an archived segment can only link to an older one.
            if (payload.Archive.Segment < 1
                || payload.Archive.Position is null
                || payload.Segment is not { } segment
                || payload.Archive.Segment >= segment)
            {
                throw new JournalIntegrityException("Journal anchor archive link is invalid.");
            }

            ValidateAnchorPosition(payload.Archive.Position);
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
                && PositionsEqual(left.Next, right.Next)))
        && left.Segment == right.Segment
        && LinksEqual(left.Archive, right.Archive);

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
                CommittedAnchor(
                    new JournalAnchorPosition(
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

    /// <summary>
    /// Path of archived segment <paramref name="segment"/>: "missions.jsonl"
    /// becomes "missions.3.jsonl", with its anchor at "missions.3.jsonl.anchor".
    /// </summary>
    internal static string SegmentPath(string journalPath, long segment)
    {
        string directory = Path.GetDirectoryName(journalPath)
            ?? throw new ArgumentException("Journal path must have a parent directory.", nameof(journalPath));
        string name = string.Concat(
            Path.GetFileNameWithoutExtension(journalPath),
            ".",
            segment.ToString(CultureInfo.InvariantCulture),
            Path.GetExtension(journalPath));
        return Path.Combine(directory, name);
    }

    private static string SegmentAnchorPath(string journalPath, long segment) =>
        string.Concat(SegmentPath(journalPath, segment), ".anchor");

    /// <summary>
    /// Numbers of the archived segment files ("name.k.ext", plus
    /// <paramref name="suffix"/>) beside the journal, listed by the manifest or not.
    /// </summary>
    private static SortedSet<long> ArchivedSegmentNumbersOnDisk(string journalPath, string suffix)
    {
        var numbers = new SortedSet<long>();
        string directory = Path.GetDirectoryName(journalPath)!;
        if (!Directory.Exists(directory))
        {
            return numbers;
        }

        string prefix = string.Concat(Path.GetFileNameWithoutExtension(journalPath), ".");
        string ending = string.Concat(Path.GetExtension(journalPath), suffix);
        foreach (string file in Directory.EnumerateFiles(directory, string.Concat(prefix, "*", ending)))
        {
            string name = Path.GetFileName(file);
            if (name.Length <= prefix.Length + ending.Length
                || !name.StartsWith(prefix, StringComparison.Ordinal)
                || !name.EndsWith(ending, StringComparison.Ordinal))
            {
                continue;
            }

            string middle = name[prefix.Length..^ending.Length];
            if (middle.Length is >= 1 and <= 18
                && middle[0] != '0'
                && middle.All(char.IsAsciiDigit)
                && long.TryParse(middle, NumberStyles.None, CultureInfo.InvariantCulture, out long number))
            {
                numbers.Add(number);
            }
        }

        return numbers;
    }

    private static long HighestSegment(JournalSegmentManifest manifest)
    {
        long highest = manifest.Floor;
        foreach (JournalArchiveLink link in manifest.Segments)
        {
            highest = Math.Max(highest, link.Segment);
        }

        foreach (long pruned in manifest.Pruned)
        {
            highest = Math.Max(highest, pruned);
        }

        return highest;
    }

    /// <summary>
    /// Finishes a rotation whose intent is durable in the segment manifest, before
    /// the live stream is opened (opening would create an empty live file). Every
    /// rename it does is proven by authenticated lengths; the records themselves are
    /// authenticated again by the live load and the archive validation that follow.
    /// </summary>
    private static void RecoverInterruptedRotation(
        string path,
        JournalHmacAuthenticator authenticator)
    {
        string manifestPath = PreparePath(string.Concat(path, ManifestSuffix));
        if (!File.Exists(manifestPath))
        {
            return;
        }

        JournalSegmentManifest manifest = ReadManifestFile(manifestPath, authenticator);
        if (!string.Equals(manifest.Phase, JournalManifestPhases.RotationPending, StringComparison.Ordinal)
            || manifest.Pending is not { } pending)
        {
            return;
        }

        JournalArchiveLink link = pending.Link;
        JournalAnchorPosition next = pending.Next;
        string archivePath = PreparePath(SegmentPath(path, link.Segment));
        string candidatePath = PreparePath(string.Concat(path, RotationCandidateSuffix));
        bool liveExists = File.Exists(path);
        if (!File.Exists(archivePath))
        {
            if (!liveExists
                || new FileInfo(path).Length != link.Position.JournalLength
                || !File.Exists(candidatePath)
                || new FileInfo(candidatePath).Length != next.JournalLength)
            {
                throw new JournalIntegrityException(
                    "Interrupted rotation matches no authenticated journal state.");
            }

            MoveWithRetry(path, archivePath);
            liveExists = false;
        }

        if (!liveExists)
        {
            if (!File.Exists(candidatePath) || new FileInfo(candidatePath).Length != next.JournalLength)
            {
                throw new JournalIntegrityException(
                    "Interrupted rotation lost its authenticated new segment.");
            }

            MoveWithRetry(candidatePath, path);
        }
        else if (File.Exists(candidatePath))
        {
            throw new JournalIntegrityException(
                "Interrupted rotation left both a live and a candidate segment.");
        }

        // The live anchor vouched for the sealed segment until the rotation moved
        // it on to the new one.
        string anchorPath = PreparePath(string.Concat(path, ".anchor"));
        JournalAnchorPayload liveAnchor = ReadAnchorFile(anchorPath, authenticator);
        bool committedPhase = string.Equals(
            liveAnchor.Phase,
            JournalAnchorPhases.Committed,
            StringComparison.Ordinal);
        if (committedPhase && PositionsEqual(liveAnchor.Current, link.Position))
        {
            WriteAnchorFile(authenticator, anchorPath, CommittedAnchor(next));
        }
        else if (!committedPhase || !PositionsEqual(liveAnchor.Current, next))
        {
            throw new JournalIntegrityException(
                "Interrupted rotation does not match the live journal anchor.");
        }

        WriteManifestFile(authenticator, manifestPath, CommittedManifest(manifest, link));
    }

    private void DeleteStaleRotationCandidate()
    {
        string candidatePath = PreparePath(string.Concat(_path, RotationCandidateSuffix));
        TryDeleteFile(candidatePath);
    }

    /// <summary>
    /// Reads the authenticated segment manifest and the retired ids it vouches for.
    /// Every archived segment file numbered above the manifest's floor must be one
    /// the manifest lists (retained or pruned), so a deleted or replayed manifest is
    /// detected. A live segment created just now (its anchor was absent) means the
    /// journal was reset: the earlier rotation state is set aside, never deleted,
    /// and segment numbering continues above every file left on disk.
    /// </summary>
    private void LoadManifest(bool liveInitialized)
    {
        _ = PreparePath(_manifestPath);
        _ = PreparePath(_retiredPath);
        _retired.Clear();
        SortedSet<long> onDisk = ArchivedSegmentNumbersOnDisk(_path, string.Empty);
        JournalSegmentManifest? manifest = null;
        if (liveInitialized)
        {
            string stamp = DateTime.UtcNow.ToString("yyyyMMddHHmmssfff", CultureInfo.InvariantCulture);
            SetAside(_manifestPath, stamp);
            SetAside(_retiredPath, stamp);
            if (onDisk.Count > 0)
            {
                manifest = EmptyManifest(_authenticator, floor: onDisk.Max);
                WriteManifest(manifest);
            }
        }
        else if (File.Exists(_manifestPath))
        {
            manifest = ReadManifestFile(_manifestPath, _authenticator);
            if (!string.Equals(manifest.Phase, JournalManifestPhases.Committed, StringComparison.Ordinal))
            {
                throw new JournalIntegrityException("Journal segment manifest holds an unfinished rotation.");
            }
        }
        else if (onDisk.Count > 0 || File.Exists(_retiredPath))
        {
            throw new JournalIntegrityException(
                "Archived journal segments exist without their authenticated manifest.");
        }

        long highest = 0;
        if (manifest is not null)
        {
            var accounted = new HashSet<long>(manifest.Pruned);
            foreach (JournalArchiveLink link in manifest.Segments)
            {
                accounted.Add(link.Segment);
            }

            foreach (long number in onDisk)
            {
                if (number > manifest.Floor && !accounted.Contains(number))
                {
                    throw new JournalIntegrityException(
                        "An archived journal segment is missing from its authenticated manifest.");
                }
            }

            highest = HighestSegment(manifest);
            LoadRetired(manifest.Retired);
        }

        // An archived anchor with no segment above everything the manifest knows was
        // written by a rotation interrupted before its intent: nothing vouches for it.
        foreach (long number in ArchivedSegmentNumbersOnDisk(_path, ".anchor"))
        {
            if (number > highest && !onDisk.Contains(number))
            {
                TryDeleteFile(PreparePath(SegmentAnchorPath(_path, number)));
            }
        }

        _manifest = manifest;
    }

    private static void SetAside(string path, string stamp)
    {
        if (File.Exists(path))
        {
            File.Move(path, string.Concat(path, ResetSuffix, stamp), overwrite: false);
        }
    }

    private static JournalSegmentManifest EmptyManifest(
        JournalHmacAuthenticator authenticator,
        long floor) =>
        new(
            ManifestFormatVersion,
            JournalHmacAuthenticator.Algorithm,
            JournalManifestPhases.Committed,
            Segments: [],
            floor,
            Pruned: [],
            new JournalRetiredState(
                Count: 0,
                Length: 0,
                authenticator.ComputeTag(RetiredAuthenticationDomain, ReadOnlySpan<byte>.Empty)));

    private static JournalSegmentManifest CommittedManifest(
        JournalSegmentManifest manifest,
        JournalArchiveLink newest) =>
        manifest with
        {
            Phase = JournalManifestPhases.Committed,
            Segments = [newest, .. manifest.Segments],
            Pending = null,
        };

    /// <summary>
    /// Writes the manifest and keeps the in-memory copy equal to the published one:
    /// if the write fails the journal faults and must be reopened from disk.
    /// </summary>
    private void WriteManifest(JournalSegmentManifest manifest)
    {
        try
        {
            WriteManifestFile(_authenticator, _manifestPath, manifest);
        }
        catch
        {
            _faulted = true;
            throw;
        }
    }

    private static void WriteManifestFile(
        JournalHmacAuthenticator authenticator,
        string path,
        JournalSegmentManifest manifest)
    {
        ValidateManifest(manifest);
        var envelope = new JournalSegmentManifestEnvelope(
            manifest,
            ComputeManifestTag(authenticator, manifest));
        byte[] bytes = JsonSerializer.SerializeToUtf8Bytes(
            envelope,
            JournalJsonContext.Default.JournalSegmentManifestEnvelope);
        if (bytes.Length > MaximumManifestBytes)
        {
            throw new JournalIntegrityException("Journal segment manifest exceeds its bounded format.");
        }

        _ = PreparePath(path);
        PublishFile(path, bytes);
        JournalSegmentManifest verified = ReadManifestFile(path, authenticator);
        if (!ManifestsEqual(manifest, verified))
        {
            throw new JournalIntegrityException("Published journal segment manifest changed.");
        }
    }

    private static JournalSegmentManifest ReadManifestFile(
        string path,
        JournalHmacAuthenticator authenticator)
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
            if (stream.Length is < 1 or > MaximumManifestBytes)
            {
                throw new JournalIntegrityException("Journal segment manifest has an invalid length.");
            }

            bytes = new byte[checked((int)stream.Length)];
            stream.ReadExactly(bytes);
            if (stream.ReadByte() != -1)
            {
                throw new JournalIntegrityException("Journal segment manifest changed while it was read.");
            }
        }

        JournalSegmentManifestEnvelope envelope;
        try
        {
            envelope = JsonSerializer.Deserialize(
                    bytes,
                    JournalJsonContext.Default.JournalSegmentManifestEnvelope)
                ?? throw new JournalIntegrityException("Journal segment manifest is null.");
        }
        catch (JsonException exception)
        {
            throw new JournalIntegrityException("Journal segment manifest is malformed.", exception);
        }

        JournalSegmentManifest manifest = envelope.Payload
            ?? throw new JournalIntegrityException("Journal segment manifest payload is null.");
        ValidateManifest(manifest);
        if (!IsLowerHexSha256(envelope.Tag)
            || !FixedTimeTagEquals(ComputeManifestTag(authenticator, manifest), envelope.Tag))
        {
            throw new JournalIntegrityException("Journal segment manifest HMAC is invalid.");
        }

        byte[] canonical = JsonSerializer.SerializeToUtf8Bytes(
            envelope,
            JournalJsonContext.Default.JournalSegmentManifestEnvelope);
        if (!bytes.AsSpan().SequenceEqual(canonical))
        {
            throw new JournalIntegrityException("Journal segment manifest is not canonical JSON.");
        }

        return manifest;
    }

    private static string ComputeManifestTag(
        JournalHmacAuthenticator authenticator,
        JournalSegmentManifest manifest) =>
        authenticator.ComputeTag(
            ManifestAuthenticationDomain,
            JsonSerializer.SerializeToUtf8Bytes(
                manifest,
                JournalJsonContext.Default.JournalSegmentManifest));

    private static void ValidateManifest(JournalSegmentManifest manifest)
    {
        if (manifest.Version != ManifestFormatVersion
            || !string.Equals(
                manifest.Authentication,
                JournalHmacAuthenticator.Algorithm,
                StringComparison.Ordinal)
            || manifest.Segments is null
            || manifest.Pruned is null
            || manifest.Retired is null
            || manifest.Floor < 0
            || manifest.Segments.Length > MaximumManifestEntries
            || manifest.Pruned.Length > MaximumManifestEntries)
        {
            throw new JournalIntegrityException("Journal segment manifest header is invalid.");
        }

        bool rotationPending = string.Equals(
            manifest.Phase,
            JournalManifestPhases.RotationPending,
            StringComparison.Ordinal);
        if ((!rotationPending
                && !string.Equals(manifest.Phase, JournalManifestPhases.Committed, StringComparison.Ordinal))
            || (manifest.Pending is not null) != rotationPending)
        {
            throw new JournalIntegrityException("Journal segment manifest phase shape is invalid.");
        }

        long previous = long.MaxValue;
        var listed = new HashSet<long>();
        foreach (JournalArchiveLink link in manifest.Segments)
        {
            if (link?.Position is null || link.Segment <= manifest.Floor || link.Segment >= previous)
            {
                throw new JournalIntegrityException("Journal segment manifest lists an invalid segment.");
            }

            ValidateAnchorPosition(link.Position);
            listed.Add(link.Segment);
            previous = link.Segment;
        }

        foreach (long pruned in manifest.Pruned)
        {
            if (pruned < 1 || !listed.Add(pruned))
            {
                throw new JournalIntegrityException("Journal segment manifest prunes an invalid segment.");
            }
        }

        JournalRetiredState retired = manifest.Retired;
        if (retired.Count < 0
            || retired.Count > long.MaxValue / RetiredLineLength
            || retired.Length != retired.Count * RetiredLineLength
            || !IsLowerHexSha256(retired.Tag))
        {
            throw new JournalIntegrityException("Journal segment manifest retired state is invalid.");
        }

        if (manifest.Pending is { } intent)
        {
            if (intent.Link?.Position is null || intent.Next is null)
            {
                throw new JournalIntegrityException("Journal segment manifest rotation intent is invalid.");
            }

            ValidateAnchorPosition(intent.Link.Position);
            ValidateAnchorPosition(intent.Next);
            if (intent.Link.Segment <= HighestSegment(manifest))
            {
                throw new JournalIntegrityException("Journal segment manifest rotation intent is invalid.");
            }
        }
    }

    private static bool ManifestsEqual(JournalSegmentManifest left, JournalSegmentManifest right) =>
        left.Version == right.Version
        && string.Equals(left.Authentication, right.Authentication, StringComparison.Ordinal)
        && string.Equals(left.Phase, right.Phase, StringComparison.Ordinal)
        && left.Floor == right.Floor
        && left.Segments.Length == right.Segments.Length
        && left.Segments.Zip(right.Segments).All(static pair => LinksEqual(pair.First, pair.Second))
        && left.Pruned.AsSpan().SequenceEqual(right.Pruned)
        && left.Retired == right.Retired
        && ((left.Pending is null && right.Pending is null)
            || (left.Pending is not null
                && right.Pending is not null
                && LinksEqual(left.Pending.Link, right.Pending.Link)
                && PositionsEqual(left.Pending.Next, right.Pending.Next)));

    /// <summary>
    /// The retired-id key of an invocation: a keyed hash, so the file of retired
    /// ids holds no invocation id and cannot be extended without the key.
    /// </summary>
    private string RetiredKey(string invocationId) =>
        _authenticator
            .ComputeTag(RetiredIdAuthenticationDomain, System.Text.Encoding.UTF8.GetBytes(invocationId))
            [..RetiredKeyLength];

    private bool IsRetired(string invocationId) =>
        _retired.Count > 0 && _retired.Contains(RetiredKey(invocationId));

    private void LoadRetired(JournalRetiredState state)
    {
        _retired.Clear();
        byte[] committed = ReadCommittedRetired(state);
        for (int offset = 0; offset < committed.Length; offset += RetiredLineLength)
        {
            string key = System.Text.Encoding.ASCII.GetString(committed, offset, RetiredKeyLength);
            if (committed[offset + RetiredKeyLength] != (byte)'\n'
                || !key.All(static character => character is (>= '0' and <= '9') or (>= 'a' and <= 'f'))
                || !_retired.Add(key))
            {
                throw new JournalIntegrityException("Journal retired invocation ids are malformed.");
            }
        }
    }

    /// <summary>
    /// Returns the retired-id bytes the manifest vouches for. Bytes past that length
    /// were appended by a retention interrupted before its manifest was published,
    /// so they were never committed and are cut off.
    /// </summary>
    private byte[] ReadCommittedRetired(JournalRetiredState state)
    {
        _ = PreparePath(_retiredPath);
        byte[] bytes;
        if (!File.Exists(_retiredPath))
        {
            if (state.Length != 0)
            {
                throw new JournalIntegrityException("Journal retired invocation ids are missing.");
            }

            bytes = [];
        }
        else
        {
            using var stream = new FileStream(
                _retiredPath,
                FileMode.Open,
                FileAccess.ReadWrite,
                FileShare.Read,
                bufferSize: 4096,
                FileOptions.WriteThrough);
            if (stream.Length < state.Length)
            {
                throw new JournalIntegrityException("Journal retired invocation ids are truncated.");
            }

            if (stream.Length > state.Length)
            {
                stream.SetLength(state.Length);
                stream.Flush(flushToDisk: true);
            }

            bytes = new byte[checked((int)state.Length)];
            stream.Position = 0;
            stream.ReadExactly(bytes);
        }

        if (!FixedTimeTagEquals(_authenticator.ComputeTag(RetiredAuthenticationDomain, bytes), state.Tag))
        {
            throw new JournalIntegrityException("Journal retired invocation ids fail authentication.");
        }

        return bytes;
    }

    private JournalRetiredState AppendRetired(JournalRetiredState state, List<string> keys)
    {
        if (keys.Count == 0)
        {
            return state;
        }

        byte[] committed = ReadCommittedRetired(state);
        byte[] all = new byte[checked(committed.Length + (keys.Count * RetiredLineLength))];
        committed.CopyTo(all, 0);
        int offset = committed.Length;
        foreach (string key in keys)
        {
            System.Text.Encoding.ASCII.GetBytes(key, all.AsSpan(offset, RetiredKeyLength));
            all[offset + RetiredKeyLength] = (byte)'\n';
            offset += RetiredLineLength;
        }

        using (var stream = new FileStream(
                   _retiredPath,
                   FileMode.OpenOrCreate,
                   FileAccess.Write,
                   FileShare.Read,
                   bufferSize: 4096,
                   FileOptions.WriteThrough))
        {
            stream.Position = committed.Length;
            stream.Write(all.AsSpan(committed.Length));
            stream.Flush(flushToDisk: true);
        }

        return new JournalRetiredState(
            state.Count + keys.Count,
            all.Length,
            _authenticator.ComputeTag(RetiredAuthenticationDomain, all));
    }

    /// <summary>
    /// Authenticates the archived segments the manifest retains end to end, newest
    /// first, and indexes their completed invocations so a retried invocation id is
    /// replayed instead of executed again. Each archived segment's anchor must link
    /// to the next older retained one, and its incomplete invocations must reappear,
    /// with the same fingerprint, in the segment after it.
    /// </summary>
    private async ValueTask LoadArchivedSegmentsAsync(CancellationToken cancellationToken)
    {
        _archived.Clear();
        _archivedSegments.Clear();
        if (_manifest is null)
        {
            return;
        }

        JournalArchiveLink[] segments = _manifest.Segments;
        Dictionary<string, string> newerStarted = _started;
        for (int index = 0; index < segments.Length; index++)
        {
            JournalArchiveLink link = segments[index];
            string segmentPath = PreparePath(SegmentPath(_path, link.Segment));
            string segmentAnchorPath = PreparePath(string.Concat(segmentPath, ".anchor"));
            if (!File.Exists(segmentPath) || !File.Exists(segmentAnchorPath))
            {
                throw new JournalIntegrityException("A retained archived journal segment is missing.");
            }

            JournalAnchorPayload archivedAnchor = ReadAnchorFile(segmentAnchorPath);
            if (!string.Equals(archivedAnchor.Phase, JournalAnchorPhases.Archived, StringComparison.Ordinal)
                || archivedAnchor.Segment != link.Segment
                || !PositionsEqual(archivedAnchor.Current, link.Position)
                || (index + 1 < segments.Length && !LinksEqual(archivedAnchor.Archive, segments[index + 1])))
            {
                throw new JournalIntegrityException(
                    "Archived journal segment does not match its authenticated link.");
            }

            SegmentScan scan = await IndexOrScanSegmentAsync(
                    segmentPath,
                    link,
                    cancellationToken)
                .ConfigureAwait(false);
            foreach ((string invocationId, string fingerprint) in scan.Started)
            {
                if (!scan.Completed.ContainsKey(invocationId)
                    && (!newerStarted.TryGetValue(invocationId, out string? carried)
                        || !string.Equals(carried, fingerprint, StringComparison.Ordinal)))
                {
                    throw new JournalIntegrityException(
                        "An incomplete archived invocation was not carried into the next segment.");
                }
            }

            foreach ((string invocationId, string fingerprint) in scan.Completed)
            {
                _ = _archived.TryAdd(invocationId, new ArchivedInvocation(fingerprint, link.Segment));
            }

            _archivedSegments.Add(link.Segment, link.Position);
            newerStarted = scan.Started;
        }

        foreach (string invocationId in _archived.Keys)
        {
            if (_started.ContainsKey(invocationId))
            {
                throw new JournalIntegrityException(
                    "An archived completed invocation reappears in the live journal.");
            }
        }
    }

    /// <summary>
    /// Retention: only the newest <see cref="_retainedArchiveSegments"/> archived
    /// segments are kept. Before an older segment leaves the manifest, every
    /// invocation it completed becomes a retired id, so a late retry of it is
    /// refused instead of executed again; then its files are deleted. A file another
    /// process still holds open stays listed as pruned and is retried later.
    /// </summary>
    private void EnforceArchiveRetention()
    {
        if (_manifest is not { } manifest)
        {
            return;
        }

        if (manifest.Segments.Length > _retainedArchiveSegments)
        {
            JournalArchiveLink[] kept = manifest.Segments[.._retainedArchiveSegments];
            long[] pruned = manifest.Segments[_retainedArchiveSegments..]
                .Select(static link => link.Segment)
                .ToArray();
            List<string> retiredIds = _archived
                .Where(entry => pruned.Contains(entry.Value.Segment))
                .Select(static entry => entry.Key)
                .ToList();
            List<string> keys = retiredIds
                .Select(RetiredKey)
                .Where(key => !_retired.Contains(key))
                .Distinct(StringComparer.Ordinal)
                .Order(StringComparer.Ordinal)
                .ToList();
            JournalRetiredState retired = AppendRetired(manifest.Retired, keys);
            InvokeCrashHook(JournalCommitStage.RetentionRetiredDurable);
            JournalSegmentManifest next = manifest with
            {
                Segments = kept,
                Pruned = [.. manifest.Pruned, .. pruned],
                Retired = retired,
            };
            WriteManifest(next);
            _manifest = manifest = next;
            foreach (string key in keys)
            {
                _retired.Add(key);
            }

            foreach (string invocationId in retiredIds)
            {
                _archived.Remove(invocationId);
            }

            foreach (long segment in pruned)
            {
                _archivedSegments.Remove(segment);
            }

            InvokeCrashHook(JournalCommitStage.RetentionManifestCommitted);
        }

        if (manifest.Pruned.Length == 0)
        {
            return;
        }

        foreach (long segment in manifest.Pruned)
        {
            TryDeleteFile(PreparePath(SegmentPath(_path, segment)));
            TryDeleteFile(PreparePath(SegmentAnchorPath(_path, segment)));
            TryDeleteFile(PreparePath(string.Concat(SegmentPath(_path, segment), SegmentIndexSuffix)));
        }

        long[] remaining = manifest.Pruned
            .Where(segment =>
                File.Exists(SegmentPath(_path, segment))
                || File.Exists(SegmentAnchorPath(_path, segment)))
            .ToArray();
        if (remaining.Length != manifest.Pruned.Length)
        {
            JournalSegmentManifest next = manifest with { Pruned = remaining };
            WriteManifest(next);
            _manifest = next;
        }
    }

    /// <summary>
    /// Retention the filesystem refuses before its manifest is published changes
    /// nothing the manifest vouches for: every segment stays retained and is pruned
    /// again on the next rotation or open. The refusal is reported, never silent.
    /// </summary>
    private void TryEnforceArchiveRetention()
    {
        try
        {
            EnforceArchiveRetention();
        }
        catch (Exception exception) when (
            !_faulted
            && (exception is UnauthorizedAccessException
                || (exception is IOException and not JournalIntegrityException)))
        {
            _diagnostics?.Invoke(string.Concat(
                "Journal retention postponed: ",
                exception.GetType().Name,
                ": ",
                exception.Message));
        }
    }

    private static void TryDeleteFile(string path)
    {
        try
        {
            if (File.Exists(path))
            {
                File.Delete(path);
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            // Retried on the next open or rotation.
        }
    }

    private bool ShouldRotate(int pendingBytes) =>
        _rotationThresholdBytes is { } threshold
        && _completed.Count > 0
        && _stream.Length + pendingBytes > threshold;

    /// <summary>
    /// Rotates unless the filesystem refuses before the new segment is published;
    /// the sealed live segment is then still authoritative and the journal keeps
    /// appending to it (compaction and the hard cap still apply). A postponement is
    /// counted and reported, never silent: the live segment keeps growing toward the
    /// hard cap until a rotation succeeds.
    /// </summary>
    private async ValueTask TryRotateAsync(CancellationToken cancellationToken)
    {
        try
        {
            await RotateAsync(cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (
            !_faulted
            && (exception is JournalCapacityException
                || exception is UnauthorizedAccessException
                || (exception is IOException and not JournalIntegrityException)))
        {
            RotationPostponements++;
            LastRotationPostponement = string.Concat(exception.GetType().Name, ": ", exception.Message);
            if (RotationPostponements == 1
                || RotationPostponements % RotationPostponementReportInterval == 0)
            {
                _diagnostics?.Invoke(string.Create(
                    CultureInfo.InvariantCulture,
                    $"Journal rotation postponed ({RotationPostponements} so far, live segment {_stream.Length} bytes): {LastRotationPostponement}"));
            }
        }
    }

    /// <summary>The next archived segment number: above every one on disk or known.</summary>
    private long NextSegmentNumber()
    {
        long highest = ArchivedSegmentNumbersOnDisk(_path, string.Empty).Max;
        if (_manifest is { } manifest)
        {
            highest = Math.Max(highest, HighestSegment(manifest));
        }

        return checked(highest + 1);
    }

    private async ValueTask RotateAsync(CancellationToken cancellationToken)
    {
        long segment = NextSegmentNumber();
        string archivePath = PreparePath(SegmentPath(_path, segment));
        string archiveAnchorPath = PreparePath(string.Concat(archivePath, ".anchor"));
        string candidatePath = PreparePath(string.Concat(_path, RotationCandidateSuffix));
        if (File.Exists(archivePath))
        {
            throw new IOException(string.Create(
                CultureInfo.InvariantCulture,
                $"Archived journal segment {segment} appeared while the rotation started."));
        }

        List<JournalPayload> carried = _retainedStates.Values
            .Where(state => !_completed.ContainsKey(state.InvocationId))
            .OrderBy(static state => state.InvocationId, StringComparer.Ordinal)
            .ToList();
        var carriedStates = new Dictionary<string, JournalPayload>(carried.Count, StringComparer.Ordinal);
        long candidateSequence = 0;
        string candidateLastTag = InitialTag;
        bool transitionStarted = false;
        try
        {
            TryDeleteFile(candidatePath);
            await using (var candidateStream = new FileStream(
                             candidatePath,
                             FileMode.CreateNew,
                             FileAccess.Write,
                             FileShare.None,
                             bufferSize: 4096,
                             FileOptions.Asynchronous | FileOptions.WriteThrough))
            {
                foreach (JournalPayload state in carried)
                {
                    JournalPayload carriedPayload = state with
                    {
                        Sequence = ++candidateSequence,
                        Phase = JournalPhases.Started,
                        Response = null,
                    };
                    byte[] json = SerializeEnvelope(carriedPayload, candidateLastTag, out string tag);
                    try
                    {
                        if (json.Length + 1 > MaximumRecordBytes
                            || candidateStream.Position > _maximumJournalBytes - json.Length - 1)
                        {
                            throw new JournalCapacityException(
                                "The incomplete invocations do not fit a new journal segment.");
                        }

                        await candidateStream.WriteAsync(json, cancellationToken).ConfigureAwait(false);
                        await candidateStream.WriteAsync(Newline, cancellationToken).ConfigureAwait(false);
                        candidateLastTag = tag;
                        carriedStates.Add(carriedPayload.InvocationId, carriedPayload);
                    }
                    finally
                    {
                        CryptographicOperations.ZeroMemory(json);
                    }
                }

                await candidateStream.FlushAsync(cancellationToken).ConfigureAwait(false);
                candidateStream.Flush(flushToDisk: true);
            }

            var candidatePosition = new JournalAnchorPosition(
                candidateSequence,
                candidateLastTag,
                new FileInfo(candidatePath).Length);
            SegmentScan verified = await ScanSegmentAsync(
                    candidatePath,
                    candidatePosition,
                    targetInvocationId: null,
                    cancellationToken)
                .ConfigureAwait(false);
            if (verified.Completed.Count != 0
                || verified.Started.Count != carriedStates.Count
                || carriedStates.Any(entry =>
                    !verified.Started.TryGetValue(entry.Key, out string? fingerprint)
                    || !string.Equals(fingerprint, entry.Value.RequestFingerprint, StringComparison.Ordinal)
                    || !string.Equals(_started[entry.Key], fingerprint, StringComparison.Ordinal)))
            {
                throw new JournalIntegrityException("Rotation candidate changed an incomplete invocation.");
            }

            cancellationToken.ThrowIfCancellationRequested();
            JournalSegmentManifest? previousManifest = _manifest;
            JournalSegmentManifest baseManifest = previousManifest
                ?? EmptyManifest(_authenticator, floor: 0);
            var sealedPosition = new JournalAnchorPosition(_sequence, _lastTag, _stream.Length);
            var link = new JournalArchiveLink(segment, sealedPosition);
            WriteAnchorFile(
                archiveAnchorPath,
                ArchivedAnchor(segment, sealedPosition, baseManifest.Segments.FirstOrDefault()));
            InvokeCrashHook(JournalCommitStage.RotationArchiveAnchorDurable);
            transitionStarted = true;
            WriteManifest(baseManifest with
            {
                Phase = JournalManifestPhases.RotationPending,
                Pending = new JournalRotationIntent(link, candidatePosition),
            });
            InvokeCrashHook(JournalCommitStage.RotationIntentDurable);

            await _stream.DisposeAsync().ConfigureAwait(false);
            try
            {
                MoveWithRetry(_path, archivePath);
            }
            catch (IOException)
            {
                // Nothing moved: the sealed segment is still the live one and its
                // anchor never changed. Roll the intent back so the journal keeps
                // working; the rotation is retried at the next append. If the
                // rollback itself fails the journal stays faulted.
                _stream = OpenJournalStream(_path);
                _stream.Position = _stream.Length;
                if (previousManifest is null)
                {
                    File.Delete(_manifestPath);
                }
                else
                {
                    WriteManifest(previousManifest);
                }

                TryDeleteFile(archiveAnchorPath);
                transitionStarted = false;
                throw;
            }

            InvokeCrashHook(JournalCommitStage.RotationSegmentArchived);
            MoveWithRetry(candidatePath, _path);
            _stream = OpenJournalStream(_path);
            _stream.Position = _stream.Length;
            InvokeCrashHook(JournalCommitStage.RotationJournalPublished);
            WriteCommittedAnchor(candidatePosition);
            InvokeCrashHook(JournalCommitStage.RotationAnchorCommitted);
            JournalSegmentManifest committed = CommittedManifest(baseManifest, link);
            WriteManifest(committed);
            _manifest = committed;
            InvokeCrashHook(JournalCommitStage.RotationManifestCommitted);

            foreach ((string invocationId, CompletedInvocation completed) in _completed)
            {
                _archived[invocationId] = new ArchivedInvocation(completed.RequestFingerprint, segment);
                _started.Remove(invocationId);
            }

            _archivedSegments[segment] = sealedPosition;
            _completed.Clear();
            _retainedStates.Clear();
            foreach ((string invocationId, JournalPayload state) in carriedStates)
            {
                _retainedStates.Add(invocationId, state);
            }

            _sequence = candidateSequence;
            _lastTag = candidateLastTag;
            transitionStarted = false;
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
            if (!_faulted)
            {
                TryDeleteFile(candidatePath);
            }
        }

        TryEnforceArchiveRetention();
    }

    /// <summary>
    /// Authenticates a whole segment from its first record to the exact position
    /// its anchor vouches for, with the same per-record checks as the live load,
    /// and returns its started and completed invocation fingerprints (plus the
    /// completion of <paramref name="targetInvocationId"/>, if asked).
    /// </summary>
    private async ValueTask<SegmentScan> ScanSegmentAsync(
        string segmentPath,
        JournalAnchorPosition expectedEnd,
        string? targetInvocationId,
        CancellationToken cancellationToken)
    {
        _ = PreparePath(segmentPath);
        var started = new Dictionary<string, string>(StringComparer.Ordinal);
        var completed = new Dictionary<string, string>(StringComparer.Ordinal);
        CompletedInvocation? target = null;
        long sequence = 0;
        string lastTag = InitialTag;
        long totalRead = 0;
        var line = new ArrayBufferWriter<byte>();
        await using var stream = new FileStream(
            segmentPath,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read,
            bufferSize: 4096,
            FileOptions.Asynchronous | FileOptions.SequentialScan);
        if (stream.Length != expectedEnd.JournalLength)
        {
            throw new JournalIntegrityException(
                "Journal segment length does not match its authenticated anchor.");
        }

        byte[] buffer = ArrayPool<byte>.Shared.Rent(16 * 1024);
        try
        {
            int read;
            while ((read = await stream
                       .ReadAsync(buffer.AsMemory(0, buffer.Length), cancellationToken)
                       .ConfigureAwait(false)) > 0)
            {
                totalRead += read;
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

                    JournalPayload payload = ParseRecord(line.WrittenSpan, sequence + 1, lastTag, out string tag);
                    ApplySegmentRecord(payload, started, completed);
                    if (payload.Response is not null
                        && string.Equals(payload.InvocationId, targetInvocationId, StringComparison.Ordinal))
                    {
                        target = new CompletedInvocation(payload.RequestFingerprint, payload.Response);
                    }

                    sequence = payload.Sequence;
                    lastTag = tag;
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

        if (line.WrittenCount != 0
            || totalRead != expectedEnd.JournalLength
            || sequence != expectedEnd.Sequence
            || !string.Equals(lastTag, expectedEnd.LastTag, StringComparison.Ordinal))
        {
            throw new JournalIntegrityException(
                "Journal segment does not end at its authenticated anchor.");
        }

        return new SegmentScan(started, completed, target);
    }

    /// <summary>
    /// The started and completed invocations of a sealed segment: from its
    /// authenticated index while that index is bound to this exact segment (number,
    /// sealed position, length and last write time), otherwise from a full scan,
    /// which then refreshes the index. The index is only a memo of a scan that
    /// already passed; it never stands in for the records when a completion is
    /// read back (<see cref="FindCompletedAsync"/> scans the segment end to end).
    /// </summary>
    private async ValueTask<SegmentScan> IndexOrScanSegmentAsync(
        string segmentPath,
        JournalArchiveLink link,
        CancellationToken cancellationToken)
    {
        string indexPath = PreparePath(string.Concat(segmentPath, SegmentIndexSuffix));
        var segmentFile = new FileInfo(segmentPath);
        long lastWrite = segmentFile.LastWriteTimeUtc.Ticks;
        if (segmentFile.Length == link.Position.JournalLength
            && TryReadSegmentIndex(indexPath, link, lastWrite) is { } indexed)
        {
            return indexed;
        }

        SegmentScan scan = await ScanSegmentAsync(
                segmentPath,
                link.Position,
                targetInvocationId: null,
                cancellationToken)
            .ConfigureAwait(false);
        segmentFile.Refresh();
        if (segmentFile.LastWriteTimeUtc.Ticks == lastWrite)
        {
            TryWriteSegmentIndex(indexPath, link, lastWrite, scan);
        }

        return scan;
    }

    private SegmentScan? TryReadSegmentIndex(string indexPath, JournalArchiveLink link, long lastWrite)
    {
        byte[] bytes;
        try
        {
            using var stream = new FileStream(
                indexPath,
                FileMode.Open,
                FileAccess.Read,
                FileShare.Read,
                bufferSize: 4096,
                FileOptions.SequentialScan);
            if (stream.Length is < 1 or > MaximumSegmentIndexBytes)
            {
                return null;
            }

            bytes = GC.AllocateUninitializedArray<byte>(checked((int)stream.Length));
            stream.ReadExactly(bytes);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return null;
        }

        JournalSegmentIndexEnvelope? envelope;
        try
        {
            envelope = JsonSerializer.Deserialize(bytes, JournalJsonContext.Default.JournalSegmentIndexEnvelope);
        }
        catch (JsonException)
        {
            return null;
        }

        if (envelope?.Payload is not { } index
            || index.Version != SegmentIndexFormatVersion
            || !string.Equals(index.Authentication, JournalHmacAuthenticator.Algorithm, StringComparison.Ordinal)
            || index.Segment != link.Segment
            || index.LastWriteTimeUtcTicks != lastWrite
            || index.Position is null
            || !PositionsEqual(index.Position, link.Position)
            || index.Completed is null
            || index.Incomplete is null
            || !IsLowerHexSha256(envelope.Tag)
            || !FixedTimeTagEquals(ComputeSegmentIndexTag(index), envelope.Tag))
        {
            return null;
        }

        var started = new Dictionary<string, string>(StringComparer.Ordinal);
        var completed = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (JournalSegmentIndexEntry entry in index.Completed)
        {
            if (!IsIndexEntry(entry)
                || !completed.TryAdd(entry.InvocationId, entry.RequestFingerprint)
                || !started.TryAdd(entry.InvocationId, entry.RequestFingerprint))
            {
                return null;
            }
        }

        foreach (JournalSegmentIndexEntry entry in index.Incomplete)
        {
            if (!IsIndexEntry(entry) || !started.TryAdd(entry.InvocationId, entry.RequestFingerprint))
            {
                return null;
            }
        }

        return new SegmentScan(started, completed, Target: null);
    }

    private static bool IsIndexEntry(JournalSegmentIndexEntry? entry) =>
        entry is not null
        && ContractValidator.IsCanonicalIdentifier(entry.InvocationId)
        && IsLowerHexSha256(entry.RequestFingerprint);

    private void TryWriteSegmentIndex(
        string indexPath,
        JournalArchiveLink link,
        long lastWrite,
        SegmentScan scan)
    {
        var index = new JournalSegmentIndex(
            SegmentIndexFormatVersion,
            JournalHmacAuthenticator.Algorithm,
            link.Segment,
            link.Position,
            lastWrite,
            scan.Completed
                .OrderBy(static entry => entry.Key, StringComparer.Ordinal)
                .Select(static entry => new JournalSegmentIndexEntry(entry.Key, entry.Value))
                .ToArray(),
            scan.Started
                .Where(entry => !scan.Completed.ContainsKey(entry.Key))
                .OrderBy(static entry => entry.Key, StringComparer.Ordinal)
                .Select(static entry => new JournalSegmentIndexEntry(entry.Key, entry.Value))
                .ToArray());
        byte[] bytes = JsonSerializer.SerializeToUtf8Bytes(
            new JournalSegmentIndexEnvelope(index, ComputeSegmentIndexTag(index)),
            JournalJsonContext.Default.JournalSegmentIndexEnvelope);
        if (bytes.Length > MaximumSegmentIndexBytes)
        {
            return;
        }

        try
        {
            PublishFile(indexPath, bytes);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            // Only a memo: the next open scans the segment again.
            _diagnostics?.Invoke(string.Concat(
                "Journal segment index not saved: ",
                exception.GetType().Name,
                ": ",
                exception.Message));
        }
    }

    private string ComputeSegmentIndexTag(JournalSegmentIndex index)
    {
        byte[] canonical = JsonSerializer.SerializeToUtf8Bytes(
            index,
            JournalJsonContext.Default.JournalSegmentIndex);
        try
        {
            return _authenticator.ComputeTag(SegmentIndexAuthenticationDomain, canonical);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(canonical);
        }
    }

    /// <summary>The live load's per-record state rules, over one sealed segment.</summary>
    private static void ApplySegmentRecord(
        JournalPayload payload,
        Dictionary<string, string> started,
        Dictionary<string, string> completed)
    {
        string invocationId = payload.InvocationId;
        string fingerprint = payload.RequestFingerprint;
        switch (payload.Phase)
        {
            case JournalPhases.Started:
                if (payload.Response is not null
                    || completed.ContainsKey(invocationId)
                    || (started.TryGetValue(invocationId, out string? previous)
                        && !string.Equals(previous, fingerprint, StringComparison.Ordinal)))
                {
                    throw new JournalIntegrityException("Archived journal start is inconsistent.");
                }

                started[invocationId] = fingerprint;
                break;
            case JournalPhases.Completed:
                if (payload.Response is null
                    || !started.TryGetValue(invocationId, out string? startedFingerprint)
                    || !string.Equals(startedFingerprint, fingerprint, StringComparison.Ordinal)
                    || completed.ContainsKey(invocationId))
                {
                    throw new JournalIntegrityException("Archived journal completion is inconsistent.");
                }

                ValidateTerminalResponse(payload.Response);
                completed.Add(invocationId, fingerprint);
                break;
            case JournalPhases.RetainedCompleted:
                if (payload.Response is null
                    || started.ContainsKey(invocationId)
                    || completed.ContainsKey(invocationId))
                {
                    throw new JournalIntegrityException("Archived retained completion is inconsistent.");
                }

                ValidateTerminalResponse(payload.Response);
                started.Add(invocationId, fingerprint);
                completed.Add(invocationId, fingerprint);
                break;
            default:
                throw new JournalIntegrityException("Journal phase is unknown.");
        }
    }

    private static void MoveWithRetry(string sourcePath, string destinationPath)
    {
        const int maximumAttempts = 200;
        for (int attempt = 1; ; attempt++)
        {
            try
            {
                File.Move(sourcePath, destinationPath, overwrite: false);
                return;
            }
            catch (IOException) when (attempt < maximumAttempts && !File.Exists(destinationPath))
            {
                Thread.Sleep(10);
            }
        }
    }

    private sealed record ArchivedInvocation(string RequestFingerprint, long Segment);

    private sealed record SegmentScan(
        Dictionary<string, string> Started,
        Dictionary<string, string> Completed,
        CompletedInvocation? Target);

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
                rotationThresholdBytes: null,
                _retainedArchiveSegments,
                crashHook: null,
                diagnostics: null,
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
    RotationArchiveAnchorDurable,
    RotationIntentDurable,
    RotationSegmentArchived,
    RotationJournalPublished,
    RotationAnchorCommitted,
    RotationManifestCommitted,
    RetentionRetiredDurable,
    RetentionManifestCommitted,
}
