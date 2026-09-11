using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

[TestFixture]
public sealed class FileInvocationJournalTests
{
    private string _root = null!;
    private string _journalPath = null!;
    private byte[] _authenticationKey = null!;

    [SetUp]
    public void SetUp()
    {
        _root = Path.Combine(Path.GetTempPath(), "baxy-kernel-tests", Guid.NewGuid().ToString("N"));
        _journalPath = Path.Combine(_root, "journal", "events.jsonl");
        _authenticationKey = RandomNumberGenerator.GetBytes(JournalHmacAuthenticator.KeyLength);
    }

    [TearDown]
    public void TearDown()
    {
        if (Directory.Exists(_root))
        {
            Directory.Delete(_root, recursive: true);
        }

        CryptographicOperations.ZeroMemory(_authenticationKey);
    }

    private ValueTask<FileInvocationJournal> OpenJournalAsync() =>
        FileInvocationJournal.OpenAsync(
            _journalPath,
            new JournalHmacAuthenticator(_authenticationKey));

    [Test]
    public async Task DenseOcrCompletionReopensAndReplaysWithoutExecutingAgain()
    {
        OperationRequest request = CreateRequest() with
        {
            Operation = "ocr.read",
            Arguments = JsonSerializer.SerializeToElement(new { captureId = "capture_test" }),
        };
        JsonElement observed = JsonSerializer.SerializeToElement(new
        {
            text = new string('é', 6000),
            layout = new { available = true, lines = Array.Empty<object>() },
        });
        string message = OperationVisibleFacts.FromOutcome("ocr.read", OperationOutcome.Success(observed));
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse, request.RequestId, request.MissionId, request.InvocationId,
            OperationStatuses.Completed, message, true, false, observed, null);
        await using (FileInvocationJournal journal = await OpenJournalAsync())
        {
            string fingerprint = RequestFingerprint.Compute(request);
            await journal.RecordStartedAsync(request, fingerprint, CancellationToken.None);
            await journal.RecordCompletedAsync(request, fingerprint, response, CancellationToken.None);
        }

        var handler = new CountingHandler("ocr.read");
        OperationRequest replayRequest = request with { RequestId = Guid.NewGuid().ToString("D") };
        await using FileInvocationJournal reopened = await OpenJournalAsync();
        using var engine = new MissionEngine(new OperationRegistry([handler]), reopened);
        OperationResponse replay = await engine.ExecuteAsync(replayRequest, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(message.Length, Is.GreaterThan(4096).And.LessThanOrEqualTo(48_000));
            Assert.That(replay.Message, Is.EqualTo(message));
            Assert.That(JsonElement.DeepEquals(replay.Result!.Value, observed), Is.True);
            Assert.That(replay.RequestId, Is.EqualTo(replayRequest.RequestId));
            Assert.That(replay.MissionId, Is.EqualTo(request.MissionId));
            Assert.That(replay.InvocationId, Is.EqualTo(request.InvocationId));
            Assert.That(replay.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(replay.Verified, Is.True);
            Assert.That(replay.Replayed, Is.True);
            Assert.That(handler.ExecutionCount, Is.Zero);
        });
    }

    [Test]
    public async Task ReopenReplaysCompletedInvocationWithCurrentRequestId()
    {
        OperationRequest request = CreateRequest();
        var firstHandler = new CountingHandler();
        await using (FileInvocationJournal journal = await OpenJournalAsync())
        using (var engine = new MissionEngine(new OperationRegistry([firstHandler]), journal))
        {
            OperationResponse response = await engine.ExecuteAsync(request, CancellationToken.None);
            Assert.That(response.Verified, Is.True);
        }

        var replayHandler = new CountingHandler();
        string replayRequestId = Guid.NewGuid().ToString("D");
        await using (FileInvocationJournal journal = await OpenJournalAsync())
        using (var engine = new MissionEngine(new OperationRegistry([replayHandler]), journal))
        {
            OperationResponse replay = await engine.ExecuteAsync(
                request with { RequestId = replayRequestId },
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(replay.Replayed, Is.True);
                Assert.That(replay.RequestId, Is.EqualTo(replayRequestId));
                Assert.That(replayHandler.ExecutionCount, Is.Zero);
            });
        }
    }

    [Test]
    public async Task CancellationAfterReversibleEffectCommitsAmbiguousTerminalBeforePropagating()
    {
        OperationRequest request = CreateRequest();
        using var cancellation = new CancellationTokenSource();
        var firstHandler = new CancelingTerminalHandler(
            cancellation,
            OperationOutcome.Failure(
                "recycle_bin_empty_failed",
                effectMayHaveOccurred: true,
                causeCode: "external_effect_ambiguous"));
        await using (FileInvocationJournal journal = await OpenJournalAsync())
        using (var engine = new MissionEngine(new OperationRegistry([firstHandler]), journal))
        {
            Assert.That(
                async () => await engine.ExecuteAsync(request, cancellation.Token),
                Throws.TypeOf<OperationCanceledException>());
            Assert.That(firstHandler.ExecutionCount, Is.EqualTo(1));
        }

        var replayHandler = new CountingHandler();
        await using (FileInvocationJournal journal = await OpenJournalAsync())
        using (var engine = new MissionEngine(new OperationRegistry([replayHandler]), journal))
        {
            OperationResponse replay = await engine.ExecuteAsync(
                request with { RequestId = Guid.NewGuid().ToString("D") },
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(replay.Status, Is.EqualTo(OperationStatuses.Failed));
                Assert.That(replay.Verified, Is.False);
                Assert.That(replay.Replayed, Is.True);
                Assert.That(replay.ErrorCode, Is.EqualTo("recycle_bin_empty_failed"));
                Assert.That(replay.EffectMayHaveOccurred, Is.True);
                Assert.That(replay.CauseCode, Is.EqualTo("external_effect_ambiguous"));
                Assert.That(replayHandler.ExecutionCount, Is.Zero);
            });
        }
    }

    [Test]
    public async Task CancellationAfterReversibleSuccessCommitsTerminalBeforePropagating()
    {
        OperationRequest request = CreateRequest();
        using var cancellation = new CancellationTokenSource();
        var firstHandler = new CancelingTerminalHandler(
            cancellation,
            OperationOutcome.Success());
        await using (FileInvocationJournal journal = await OpenJournalAsync())
        using (var engine = new MissionEngine(new OperationRegistry([firstHandler]), journal))
        {
            Assert.That(
                async () => await engine.ExecuteAsync(request, cancellation.Token),
                Throws.TypeOf<OperationCanceledException>());
            Assert.That(firstHandler.ExecutionCount, Is.EqualTo(1));
        }

        var replayHandler = new CountingHandler();
        await using (FileInvocationJournal journal = await OpenJournalAsync())
        using (var engine = new MissionEngine(new OperationRegistry([replayHandler]), journal))
        {
            OperationResponse replay = await engine.ExecuteAsync(
                request with { RequestId = Guid.NewGuid().ToString("D") },
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(replay.Status, Is.EqualTo(OperationStatuses.Completed));
                Assert.That(replay.Verified, Is.True);
                Assert.That(replay.Replayed, Is.True);
                Assert.That(replay.ErrorCode, Is.Null);
                Assert.That(replay.EffectMayHaveOccurred, Is.False);
                Assert.That(replayHandler.ExecutionCount, Is.Zero);
            });
        }
    }

    [Test]
    public async Task ReopenDiscardsOnlyTruncatedFinalRecord()
    {
        OperationRequest request = CreateRequest();
        await using (FileInvocationJournal journal = await OpenJournalAsync())
        using (var engine = new MissionEngine(new OperationRegistry([new CountingHandler()]), journal))
        {
            await engine.ExecuteAsync(request, CancellationToken.None);
        }

        await File.AppendAllTextAsync(_journalPath, "{\"payload\":", Encoding.UTF8);

        await using (FileInvocationJournal reopened = await OpenJournalAsync())
        {
            CompletedInvocation? completed = await reopened.FindCompletedAsync(
                request.InvocationId,
                CancellationToken.None);
            Assert.That(completed, Is.Not.Null);
        }

        byte[] bytes = await File.ReadAllBytesAsync(_journalPath);
        Assert.That(bytes[^1], Is.EqualTo((byte)'\n'));
    }

    [Test]
    public async Task OpenFailsClosedWhenHardCapLeavesNoRoomToRepairFinalNewline()
    {
        OperationRequest request = CreateRequest();
        await using (FileInvocationJournal journal = await OpenJournalAsync())
        {
            await journal.RecordStartedAsync(
                request,
                RequestFingerprint.Compute(request),
                CancellationToken.None);
        }

        byte[] complete = await File.ReadAllBytesAsync(_journalPath);
        Assert.That(complete[^1], Is.EqualTo((byte)'\n'));
        await File.WriteAllBytesAsync(_journalPath, complete[..^1]);

        Assert.That(
            async () => await FileInvocationJournal.OpenWithCapacityForTestingAsync(
                _journalPath,
                new JournalHmacAuthenticator(_authenticationKey),
                complete.Length - 1,
                completionReservationBytes: 64),
            Throws.InstanceOf<JournalIntegrityException>());
    }

    [Test]
    public async Task AuthenticatedAnchorRejectsTruncationOfCommittedCompletion()
    {
        OperationRequest request = CreateRequest();
        await using (FileInvocationJournal journal = await OpenJournalAsync())
        using (var engine = new MissionEngine(new OperationRegistry([new CountingHandler()]), journal))
        {
            OperationResponse completed = await engine.ExecuteAsync(request, CancellationToken.None);
            Assert.That(completed.Verified, Is.True);
        }

        byte[] completeJournal = await File.ReadAllBytesAsync(_journalPath);
        int startOfCompletion = Array.LastIndexOf(
            completeJournal,
            (byte)'\n',
            completeJournal.Length - 2) + 1;
        Assert.That(startOfCompletion, Is.GreaterThan(0));
        int partialLength = startOfCompletion + ((completeJournal.Length - startOfCompletion) / 2);
        await File.WriteAllBytesAsync(_journalPath, completeJournal[..partialLength]);

        Assert.That(
            async () => await OpenJournalAsync(),
            Throws.TypeOf<JournalIntegrityException>());
    }

    [Test]
    public async Task AuthenticatedAnchorRejectsReplayOfAnOlderValidJournalPrefix()
    {
        OperationRequest request = CreateRequest();
        string fingerprint = RequestFingerprint.Compute(request);
        await using (FileInvocationJournal journal = await OpenJournalAsync())
        {
            await journal.RecordStartedAsync(request, fingerprint, CancellationToken.None);
        }

        byte[] authenticatedPrefix = await File.ReadAllBytesAsync(_journalPath);
        await using (FileInvocationJournal completing = await OpenJournalAsync())
        {
            var response = new OperationResponse(
                ProtocolTypes.OperationResponse,
                request.RequestId,
                request.MissionId,
                request.InvocationId,
                OperationStatuses.Completed,
                "done",
                true,
                false,
                JsonDocument.Parse("{\"ok\":true}").RootElement.Clone(),
                null);
            await completing.RecordCompletedAsync(
                request,
                fingerprint,
                response,
                CancellationToken.None);
        }

        await File.WriteAllBytesAsync(_journalPath, authenticatedPrefix);

        Assert.That(
            async () => await OpenJournalAsync(),
            Throws.TypeOf<JournalIntegrityException>());
    }

    [Test]
    public async Task PendingResponseCannotCompleteInvocationAndRetryRemainsRecoverableAfterReopen()
    {
        OperationRequest request = CreateRequest();
        string fingerprint = RequestFingerprint.Compute(request);
        var pending = new OperationResponse(
            ProtocolTypes.OperationResponse,
            request.RequestId,
            request.MissionId,
            request.InvocationId,
            OperationStatuses.Pending,
            "La operación requiere reconciliación.",
            Verified: false,
            Replayed: false,
            Result: null,
            ErrorCode: "audio_reconciliation_required");

        await using (FileInvocationJournal journal = await OpenJournalAsync())
        {
            await journal.RecordStartedAsync(request, fingerprint, CancellationToken.None);

            Assert.That(
                async () => await journal.RecordCompletedAsync(
                    request,
                    fingerprint,
                    pending,
                    CancellationToken.None),
                Throws.ArgumentException.With.Property(nameof(ArgumentException.ParamName))
                    .EqualTo("response"));
            Assert.That(
                await journal.FindCompletedAsync(request.InvocationId, CancellationToken.None),
                Is.Null);
        }

        var recoveryHandler = new CountingHandler();
        string retryRequestId = Guid.NewGuid().ToString("D");
        await using (FileInvocationJournal reopened = await OpenJournalAsync())
        using (var engine = new MissionEngine(new OperationRegistry([recoveryHandler]), reopened))
        {
            OperationResponse retry = await engine.ExecuteAsync(
                request with { RequestId = retryRequestId },
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(retry.Status, Is.EqualTo(OperationStatuses.Completed));
                Assert.That(retry.Verified, Is.True);
                Assert.That(retry.Replayed, Is.False);
                Assert.That(retry.RequestId, Is.EqualTo(retryRequestId));
                Assert.That(recoveryHandler.ExecutionCount, Is.EqualTo(1));
            });
        }
    }

    [Test]
    public async Task ReopenRejectsAConflictingIncompleteInvocationAndStillCompletesTheOriginal()
    {
        OperationRequest original = CreateRequest();
        string fingerprint = RequestFingerprint.Compute(original);
        await using (FileInvocationJournal journal = await OpenJournalAsync())
        {
            await journal.RecordStartedAsync(original, fingerprint, CancellationToken.None);
        }

        var handler = new CountingHandler();
        await using (FileInvocationJournal reopened = await OpenJournalAsync())
        using (var engine = new MissionEngine(new OperationRegistry([handler]), reopened))
        {
            OperationRequest conflicting = original with
            {
                RequestId = Guid.NewGuid().ToString("D"),
                Arguments = JsonDocument.Parse("{\"title\":\"Compras\",\"content\":\"café\"}")
                    .RootElement.Clone(),
            };

            OperationResponse conflict = await engine.ExecuteAsync(conflicting, CancellationToken.None);
            OperationResponse recovered = await engine.ExecuteAsync(
                original with { RequestId = Guid.NewGuid().ToString("D") },
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(conflict.Status, Is.EqualTo(OperationStatuses.Rejected));
                Assert.That(conflict.ErrorCode, Is.EqualTo("idempotency_conflict"));
                Assert.That(recovered.Status, Is.EqualTo(OperationStatuses.Completed));
                Assert.That(recovered.Verified, Is.True);
                Assert.That(handler.ExecutionCount, Is.EqualTo(1));
            });
        }

        string[] records = await File.ReadAllLinesAsync(_journalPath, Encoding.UTF8);
        Assert.That(records, Has.Length.EqualTo(2), "The identical retry must not append a second start record.");
    }

    [Test]
    public async Task NearCapacityCompactsAndPreservesReplayRecoveryAndConflictsAfterReopen()
    {
        OperationRequest completedRequest = CreateRequest();
        OperationRequest incompleteRequest = CreateRequest();
        OperationRequest triggerRequest = CreateRequest();
        OperationResponse completedResponse;
        await using (FileInvocationJournal journal = await OpenJournalAsync())
        using (var engine = new MissionEngine(
                   new OperationRegistry([new CountingHandler()]),
                   journal))
        {
            completedResponse = await engine.ExecuteAsync(completedRequest, CancellationToken.None);
            await journal.RecordStartedAsync(
                incompleteRequest,
                RequestFingerprint.Compute(incompleteRequest),
                CancellationToken.None);
        }

        string[] recordsBeforeCompaction = await File.ReadAllLinesAsync(_journalPath, Encoding.UTF8);
        const int completionReservationBytes = 4 * 1024;
        long maximumJournalBytes = new FileInfo(_journalPath).Length
            + (2 * completionReservationBytes)
            + 64;
        var nearCapacityHandler = new CountingHandler();
        string[] compactedRecords;
        await using (FileInvocationJournal nearCapacityJournal =
                     await FileInvocationJournal.OpenWithCapacityForTestingAsync(
                         _journalPath,
                         new JournalHmacAuthenticator(_authenticationKey),
                         maximumJournalBytes,
                         completionReservationBytes))
        using (var engine = new MissionEngine(
                   new OperationRegistry([nearCapacityHandler]),
                   nearCapacityJournal))
        {
            OperationResponse triggerResponse = await engine.ExecuteAsync(
                triggerRequest,
                CancellationToken.None);
            OperationResponse continuedReplay = await engine.ExecuteAsync(
                triggerRequest with { RequestId = Guid.NewGuid().ToString("D") },
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(triggerResponse.Verified, Is.True);
                Assert.That(continuedReplay.Replayed, Is.True);
                Assert.That(nearCapacityHandler.ExecutionCount, Is.EqualTo(1));
            });
        }

        compactedRecords = await File.ReadAllLinesAsync(_journalPath, Encoding.UTF8);
        using (JsonDocument firstRecord = JsonDocument.Parse(compactedRecords[0]))
        {
            Assert.Multiple(() =>
            {
                Assert.That(recordsBeforeCompaction, Has.Length.EqualTo(3));
                Assert.That(compactedRecords, Has.Length.EqualTo(4));
                Assert.That(
                    firstRecord.RootElement.GetProperty("payload").GetProperty("sequence").GetInt64(),
                    Is.EqualTo(1));
                Assert.That(
                    compactedRecords.Any(static record => record.Contains(
                        $"\"phase\":\"{JournalPhases.RetainedCompleted}\"",
                        StringComparison.Ordinal)),
                    Is.True);
            });
        }

        var recoveryHandler = new CountingHandler();
        await using (FileInvocationJournal reopened =
                     await FileInvocationJournal.OpenWithCapacityForTestingAsync(
                         _journalPath,
                         new JournalHmacAuthenticator(_authenticationKey),
                         maximumJournalBytes,
                         completionReservationBytes))
        using (var engine = new MissionEngine(
                   new OperationRegistry([recoveryHandler]),
                   reopened))
        {
            OperationRequest blockedRequest = CreateRequest();
            OperationResponse blocked = await engine.ExecuteAsync(
                blockedRequest,
                CancellationToken.None);
            OperationResponse repeatedBlock = await engine.ExecuteAsync(
                blockedRequest with { RequestId = Guid.NewGuid().ToString("D") },
                CancellationToken.None);
            OperationResponse completedConflict = await engine.ExecuteAsync(
                ChangeContent(completedRequest, "otro contenido"),
                CancellationToken.None);
            string replayRequestId = Guid.NewGuid().ToString("D");
            OperationResponse completedReplay = await engine.ExecuteAsync(
                completedRequest with { RequestId = replayRequestId },
                CancellationToken.None);
            OperationResponse incompleteConflict = await engine.ExecuteAsync(
                ChangeContent(incompleteRequest, "contenido conflictivo"),
                CancellationToken.None);
            OperationResponse recovered = await engine.ExecuteAsync(
                incompleteRequest with { RequestId = Guid.NewGuid().ToString("D") },
                CancellationToken.None);
            OperationResponse triggerReplay = await engine.ExecuteAsync(
                triggerRequest with { RequestId = Guid.NewGuid().ToString("D") },
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(blocked.Status, Is.EqualTo(OperationStatuses.Rejected));
                Assert.That(blocked.ErrorCode, Is.EqualTo("journal_capacity_reached"));
                Assert.That(repeatedBlock.ErrorCode, Is.EqualTo("journal_capacity_reached"));
                Assert.That(completedConflict.ErrorCode, Is.EqualTo("idempotency_conflict"));
                Assert.That(completedReplay.Replayed, Is.True);
                Assert.That(completedReplay.RequestId, Is.EqualTo(replayRequestId));
                Assert.That(completedReplay.Message, Is.EqualTo(completedResponse.Message));
                Assert.That(incompleteConflict.ErrorCode, Is.EqualTo("idempotency_conflict"));
                Assert.That(recovered.Verified, Is.True);
                Assert.That(recovered.Replayed, Is.False);
                Assert.That(triggerReplay.Replayed, Is.True);
                Assert.That(recoveryHandler.ExecutionCount, Is.EqualTo(1));
            });
        }
    }

    [TestCase((int)JournalCommitStage.CompactionIntentDurable)]
    [TestCase((int)JournalCommitStage.CompactionJournalPublished)]
    [TestCase((int)JournalCommitStage.CompactionAnchorCommitted)]
    public async Task InterruptedCompactionRecoversOnlyAnAuthenticatedOldOrNewState(
        int crashStageValue)
    {
        JournalCommitStage crashStage = (JournalCommitStage)crashStageValue;
        OperationRequest completedRequest = CreateRequest();
        OperationRequest incompleteRequest = CreateRequest();
        OperationRequest triggerRequest = CreateRequest();
        await using (FileInvocationJournal initial = await OpenJournalAsync())
        using (var engine = new MissionEngine(
                   new OperationRegistry([new CountingHandler()]),
                   initial))
        {
            _ = await engine.ExecuteAsync(completedRequest, CancellationToken.None);
            await initial.RecordStartedAsync(
                incompleteRequest,
                RequestFingerprint.Compute(incompleteRequest),
                CancellationToken.None);
        }

        const int completionReservationBytes = 4 * 1024;
        long maximumJournalBytes = new FileInfo(_journalPath).Length
            + (2 * completionReservationBytes)
            + 64;
        var crash = new SimulatedJournalCrashException();
        await using (FileInvocationJournal crashing =
                     await FileInvocationJournal.OpenWithCapacityForTestingAsync(
                         _journalPath,
                         new JournalHmacAuthenticator(_authenticationKey),
                         maximumJournalBytes,
                         completionReservationBytes,
                         stage =>
                         {
                             if (stage == crashStage)
                             {
                                 throw crash;
                             }
                         }))
        using (var engine = new MissionEngine(
                   new OperationRegistry([new CountingHandler()]),
                   crashing))
        {
            Assert.That(
                async () => await engine.ExecuteAsync(triggerRequest, CancellationToken.None),
                Throws.TypeOf<SimulatedJournalCrashException>());
        }

        await using FileInvocationJournal recovered = await OpenJournalAsync();
        Assert.Multiple(() =>
        {
            Assert.That(
                recovered.FindCompletedAsync(
                    completedRequest.InvocationId,
                    CancellationToken.None).AsTask().GetAwaiter().GetResult(),
                Is.Not.Null);
            Assert.That(
                recovered.FindStartedFingerprintAsync(
                    incompleteRequest.InvocationId,
                    CancellationToken.None).AsTask().GetAwaiter().GetResult(),
                Is.EqualTo(RequestFingerprint.Compute(incompleteRequest)));
            Assert.That(
                recovered.FindStartedFingerprintAsync(
                    triggerRequest.InvocationId,
                    CancellationToken.None).AsTask().GetAwaiter().GetResult(),
                Is.Null);
        });
    }

    [Test]
    public async Task ReopenFailsClosedWhenCompleteRecordWasModified()
    {
        OperationRequest request = CreateRequest();
        await using (FileInvocationJournal journal = await OpenJournalAsync())
        using (var engine = new MissionEngine(new OperationRegistry([new CountingHandler()]), journal))
        {
            await engine.ExecuteAsync(request, CancellationToken.None);
        }

        string content = await File.ReadAllTextAsync(_journalPath, Encoding.UTF8);
        string modified = content.Replace(
            "\"phase\":\"started\"",
            "\"phase\":\"storted\"",
            StringComparison.Ordinal);
        Assert.That(modified, Is.Not.EqualTo(content));
        await File.WriteAllTextAsync(_journalPath, modified, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));

        Assert.That(
            async () => await OpenJournalAsync(),
            Throws.InstanceOf<JournalIntegrityException>());
    }

    [Test]
    public async Task WrongKeyMissingAnchorAndNoncanonicalAuthenticatedRecordFailClosed()
    {
        OperationRequest request = CreateRequest();
        await using (FileInvocationJournal journal = await OpenJournalAsync())
        {
            await journal.RecordStartedAsync(
                request,
                RequestFingerprint.Compute(request),
                CancellationToken.None);
        }

        Assert.That(
            async () => await FileInvocationJournal.OpenAsync(
                _journalPath,
                new JournalHmacAuthenticator(
                    RandomNumberGenerator.GetBytes(JournalHmacAuthenticator.KeyLength))),
            Throws.TypeOf<JournalIntegrityException>());

        string anchorPath = string.Concat(_journalPath, ".anchor");
        byte[] anchor = await File.ReadAllBytesAsync(anchorPath);
        File.Delete(anchorPath);
        Assert.That(
            async () => await OpenJournalAsync(),
            Throws.TypeOf<JournalIntegrityException>());
        await File.WriteAllBytesAsync(anchorPath, anchor);

        string content = await File.ReadAllTextAsync(_journalPath, Encoding.UTF8);
        const string canonicalPrefix =
            "{\"version\":2,\"authentication\":\"hmac-sha256\",";
        const string reorderedPrefix =
            "{\"authentication\":\"hmac-sha256\",\"version\":2,";
        Assert.That(content, Does.StartWith(canonicalPrefix));
        string noncanonical = string.Concat(
            reorderedPrefix,
            content.AsSpan(canonicalPrefix.Length));
        Assert.That(
            Encoding.UTF8.GetByteCount(noncanonical),
            Is.EqualTo(new FileInfo(_journalPath).Length));
        await File.WriteAllTextAsync(
            _journalPath,
            noncanonical,
            new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));

        Assert.That(
            async () => await OpenJournalAsync(),
            Throws.TypeOf<JournalIntegrityException>());
    }

    [Test]
    public void UnsignedV1JournalIsNeverMigratedOrAuthenticatedByTrustOnFirstUse()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(_journalPath)!);
        File.WriteAllText(
            _journalPath,
            "{\"payload\":{},\"previousHash\":\"00\",\"hash\":\"00\"}\n",
            new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));

        Assert.That(
            async () => await OpenJournalAsync(),
            Throws.TypeOf<JournalIntegrityException>());
        Assert.That(File.Exists(string.Concat(_journalPath, ".anchor")), Is.False);
    }

    [TestCase((int)JournalCommitStage.RecordDurableBeforeAnchor)]
    [TestCase((int)JournalCommitStage.AnchorDurable)]
    public async Task InterruptedAppendRecoversOnlyTheAuthenticatedRecord(
        int crashStageValue)
    {
        JournalCommitStage crashStage = (JournalCommitStage)crashStageValue;
        OperationRequest request = CreateRequest();
        string fingerprint = RequestFingerprint.Compute(request);
        var crash = new SimulatedJournalCrashException();
        await using (FileInvocationJournal crashing =
                     await FileInvocationJournal.OpenWithCapacityForTestingAsync(
                         _journalPath,
                         new JournalHmacAuthenticator(_authenticationKey),
                         maximumJournalBytes: 1024 * 1024,
                         completionReservationBytes: 64 * 1024,
                         crashHook: stage =>
                         {
                             if (stage == crashStage)
                             {
                                 throw crash;
                             }
                         }))
        {
            Assert.That(
                async () => await crashing.RecordStartedAsync(
                    request,
                    fingerprint,
                    CancellationToken.None),
                Throws.TypeOf<SimulatedJournalCrashException>());
            Assert.That(
                async () => await crashing.FindStartedFingerprintAsync(
                    request.InvocationId,
                    CancellationToken.None),
                Throws.TypeOf<JournalIntegrityException>());
        }

        await using FileInvocationJournal recovered = await OpenJournalAsync();
        Assert.That(
            await recovered.FindStartedFingerprintAsync(
                request.InvocationId,
                CancellationToken.None),
            Is.EqualTo(fingerprint));
    }

    [Test]
    public async Task OpenRejectsAReparsePointInTheJournalDirectoryChain()
    {
        Directory.CreateDirectory(_root);
        string target = Path.Combine(_root, "real-journal");
        string link = Path.Combine(_root, "linked-journal");
        Directory.CreateDirectory(target);

        _ = Baxy.Tests.NtfsTestJunction.Create(link, target);

        try
        {
            Assert.That(
                async () => await FileInvocationJournal.OpenAsync(
                    Path.Combine(link, "events.jsonl"),
                    new JournalHmacAuthenticator(_authenticationKey)),
                Throws.InstanceOf<IOException>());
            Assert.That(Directory.GetFileSystemEntries(target), Is.Empty);
        }
        finally
        {
            Directory.Delete(link);
        }
    }

    [Test]
    public async Task OpenRejectsAReparsePointJournalLeafWithoutTouchingItsTarget()
    {
        string? journalDirectory = Path.GetDirectoryName(_journalPath);
        Assert.That(journalDirectory, Is.Not.Null);
        Directory.CreateDirectory(journalDirectory!);
        string target = Path.Combine(_root, "outside");
        string sentinelPath = Path.Combine(target, "sentinel.txt");
        const string sentinel = "outside sentinel";
        Directory.CreateDirectory(target);
        await File.WriteAllTextAsync(sentinelPath, sentinel, new UTF8Encoding(false));
        _ = Baxy.Tests.NtfsTestJunction.Create(_journalPath, target);
        Assert.That(
            File.GetAttributes(_journalPath) & FileAttributes.ReparsePoint,
            Is.EqualTo(FileAttributes.ReparsePoint));

        try
        {
            Assert.That(
                async () => await FileInvocationJournal.OpenAsync(
                    _journalPath,
                    new JournalHmacAuthenticator(_authenticationKey)),
                Throws.InstanceOf<IOException>());
            Assert.That(await File.ReadAllTextAsync(sentinelPath, Encoding.UTF8), Is.EqualTo(sentinel));
        }
        finally
        {
            Directory.Delete(_journalPath);
        }
    }

    [Test]
    public void OpenRejectsAnAlternateDataStreamPathBeforeCreatingAFile()
    {
        string alternateStreamPath = _journalPath + ":hidden";

        Assert.That(
            async () => await FileInvocationJournal.OpenAsync(
                alternateStreamPath,
                new JournalHmacAuthenticator(_authenticationKey)),
            Throws.ArgumentException);
        Assert.That(File.Exists(_journalPath), Is.False);
    }

    [Test]
    public async Task MemoryBoundaryRejectsPlaintextArgumentsBeforeHandlerOrJournal()
    {
        const string canary = "BAXY-MEMORY-PRIVATE-CANARY";
        var handler = new LeakyMemoryHandler(canary);
        await using FileInvocationJournal journal = await OpenJournalAsync();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest request = MemoryRequest(
            JsonDocument.Parse($"{{\"value\":\"{canary}\"}}").RootElement.Clone());

        OperationResponse response = await engine.ExecuteAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Rejected));
            Assert.That(response.ErrorCode, Is.EqualTo("invalid_private_envelope"));
            Assert.That(handler.ExecutionCount, Is.Zero);
            Assert.That(new FileInfo(_journalPath).Length, Is.Zero);
        });
    }

    [Test]
    public async Task MemoryBoundaryReplacesLeakyHandlerOutcomeBeforeJournal()
    {
        const string canary = "BAXY-MEMORY-PRIVATE-CANARY";
        var handler = new ForgedPrivateMemoryHandler(canary);
        OperationRequest request = ProtectedMemoryRequest();
        OperationResponse response;
        await using (FileInvocationJournal journal = await OpenJournalAsync())
        using (var engine = new MissionEngine(
                   new OperationRegistry([handler]),
                   journal,
                                new MissionEngineOptions { PrivateEnvelopeAuthenticator = new StubPrivateAuthenticator(authenticateArguments: true, authenticateResult: false) }))
        {
            response = await engine.ExecuteAsync(request, CancellationToken.None);
        }

        string journalText = await File.ReadAllTextAsync(_journalPath, Encoding.UTF8);
        string encodedCanary = Convert.ToBase64String(Encoding.UTF8.GetBytes(canary));
        Assert.Multiple(() =>
        {
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(response.ErrorCode, Is.EqualTo("memory_operation_failed"));
            Assert.That(response.Message, Does.Not.Contain(canary));
            Assert.That(response.Result, Is.Null);
            Assert.That(journalText, Does.Not.Contain(canary));
            Assert.That(journalText, Does.Not.Contain(encodedCanary));
        });
    }

    [Test]
    public async Task MemoryBoundaryRejectsStructuralEnvelopeWithoutCryptographicAuthority()
    {
        var handler = new LeakyMemoryHandler("BAXY-MEMORY-CANARY");
        await using FileInvocationJournal journal = await OpenJournalAsync();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);

        OperationResponse response = await engine.ExecuteAsync(
            ProtectedMemoryRequest(),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Rejected));
            Assert.That(response.ErrorCode, Is.EqualTo("invalid_private_envelope"));
            Assert.That(handler.ExecutionCount, Is.Zero);
            Assert.That(new FileInfo(_journalPath).Length, Is.Zero);
        });
    }

    [Test]
    public async Task MemoryBoundaryNormalizesUnsafeLegacyReplayWithoutExecutingHandler()
    {
        const string canary = "BAXY-LEGACY-REPLAY-CANARY";
        using var journal = new InMemoryInvocationJournal();
        OperationRequest request = ProtectedMemoryRequest();
        string fingerprint = RequestFingerprint.Compute(request);
        await journal.RecordStartedAsync(request, fingerprint, CancellationToken.None);
        JsonElement privateResult = JsonDocument.Parse(
                $"{{\"secret\":{JsonSerializer.Serialize(canary)}}}")
            .RootElement
            .Clone();
        var legacy = new OperationResponse(
            ProtocolTypes.OperationResponse,
            request.RequestId,
            request.MissionId,
            request.InvocationId,
            OperationStatuses.Completed,
            canary,
            true,
            false,
            privateResult,
            null);
        await journal.RecordCompletedAsync(
            request,
            fingerprint,
            legacy,
            CancellationToken.None);
        var handler = new LeakyMemoryHandler(canary);
        using var engine = new MissionEngine(
            new OperationRegistry([handler]),
            journal,
                               new MissionEngineOptions { PrivateEnvelopeAuthenticator = new StubPrivateAuthenticator(authenticateArguments: true, authenticateResult: false) });

        OperationResponse replay = await engine.ExecuteAsync(
            request with { RequestId = Guid.NewGuid().ToString("D") },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(handler.ExecutionCount, Is.Zero);
            Assert.That(replay.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(replay.Verified, Is.False);
            Assert.That(replay.Replayed, Is.True);
            Assert.That(replay.ErrorCode, Is.EqualTo("memory_operation_failed"));
            Assert.That(replay.Message, Does.Not.Contain(canary));
            Assert.That(replay.Result, Is.Null);
        });
    }

    [Test]
    public async Task MemoryBoundaryAcceptsCachedExportOnlyWhenAuthenticatorRevalidatesIt()
    {
        const string canary = "BAXY-EXPORT-REPLAY-CANARY";
        using var journal = new InMemoryInvocationJournal();
        OperationRequest request = ProtectedMemoryRequest("memory.export");
        string fingerprint = RequestFingerprint.Compute(request);
        await journal.RecordStartedAsync(request, fingerprint, CancellationToken.None);
        JsonElement protectedResult = ProtectedMemoryResult(request, canary);
        var completed = new OperationResponse(
            ProtocolTypes.OperationResponse,
            request.RequestId,
            request.MissionId,
            request.InvocationId,
            OperationStatuses.Completed,
            PrivateOperationBoundary.PublicSuccessMessage,
            true,
            false,
            protectedResult,
            null);
        await journal.RecordCompletedAsync(
            request,
            fingerprint,
            completed,
            CancellationToken.None);
        var handler = new LeakyMemoryHandler(canary, "memory.export");
        using var engine = new MissionEngine(
            new OperationRegistry([handler]),
            journal,
                               new MissionEngineOptions { PrivateEnvelopeAuthenticator = new StubPrivateAuthenticator(authenticateArguments: true, authenticateResult: true) });

        OperationResponse replay = await engine.ExecuteAsync(
            request with { RequestId = Guid.NewGuid().ToString("D") },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(handler.ExecutionCount, Is.Zero);
            Assert.That(replay.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(replay.Verified, Is.True);
            Assert.That(replay.Replayed, Is.True);
            Assert.That(replay.ErrorCode, Is.Null);
            Assert.That(replay.Result?.GetRawText(), Is.EqualTo(protectedResult.GetRawText()));
            Assert.That(replay.Message, Does.Not.Contain(canary));
        });
    }

    private static OperationRequest CreateRequest() => new(
        ProtocolTypes.OperationRequest,
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        "note.create",
        JsonDocument.Parse("{\"title\":\"Compras\",\"content\":\"pan\"}").RootElement.Clone());

    private static OperationRequest MemoryRequest(JsonElement arguments) => new(
        ProtocolTypes.OperationRequest,
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        "memory.recall",
        arguments);

    private static OperationRequest ProtectedMemoryRequest(
        string operation = "memory.recall")
    {
        string requestId = Guid.NewGuid().ToString("D");
        string missionId = Guid.NewGuid().ToString("D");
        string invocationId = Guid.NewGuid().ToString("D");
        string purpose = $"memory.arguments.v1|{operation}|{missionId}|{invocationId}";
        string ciphertext = Convert.ToBase64String([1, 2, 3, 4]);
        JsonElement arguments = JsonDocument.Parse(
                $"{{\"version\":1,\"protection\":\"test-protection\",\"purpose\":\"{purpose}\",\"ciphertext\":\"{ciphertext}\"}}")
            .RootElement
            .Clone();
        return new OperationRequest(
            ProtocolTypes.OperationRequest,
            requestId,
            missionId,
            invocationId,
            operation,
            arguments);
    }

    private static JsonElement ProtectedMemoryResult(
        OperationRequest request,
        string privateCanary)
    {
        string purpose =
            $"memory.result.v1|{request.Operation}|{request.MissionId}|{request.InvocationId}";
        string ciphertext = Convert.ToBase64String(Encoding.UTF8.GetBytes(privateCanary));
        return JsonDocument.Parse(
                $"{{\"version\":1,\"protection\":\"test-protection\",\"purpose\":{JsonSerializer.Serialize(purpose)},\"ciphertext\":\"{ciphertext}\"}}")
            .RootElement
            .Clone();
    }

    private static OperationRequest ChangeContent(OperationRequest request, string content) =>
        request with
        {
            RequestId = Guid.NewGuid().ToString("D"),
            Arguments = JsonDocument.Parse(
                    $"{{\"title\":\"Compras\",\"content\":{JsonSerializer.Serialize(content)}}}")
                .RootElement.Clone(),
        };

    private sealed class CountingHandler(string operation = "note.create") : IOperationHandler
    {
        public int ExecutionCount { get; private set; }

        public OperationDefinition Definition { get; } =
            new(operation, OperationRisk.Reversible, "Create a local note.");

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ExecutionCount++;
            return ValueTask.FromResult(OperationOutcome.Success(invocation.Arguments));
        }
    }

    private sealed class CancelingTerminalHandler(
        CancellationTokenSource cancellation,
        OperationOutcome outcome) : IOperationHandler
    {
        public int ExecutionCount { get; private set; }

        public OperationDefinition Definition { get; } =
            new("note.create", OperationRisk.Reversible, "Create a local note.");

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ExecutionCount++;
            cancellation.Cancel();
            return ValueTask.FromResult(outcome);
        }
    }

    private sealed class LeakyMemoryHandler(
        string canary,
        string operation = "memory.recall") : IOperationHandler
    {
        public int ExecutionCount { get; private set; }

        public OperationDefinition Definition { get; } =
            new(operation, OperationRisk.ReadOnly, "Leaky test memory handler.");

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ExecutionCount++;
            JsonElement result = JsonDocument.Parse(
                    $"{{\"value\":{JsonSerializer.Serialize(canary)}}}")
                .RootElement
                .Clone();
            return ValueTask.FromResult(OperationOutcome.Success(result));
        }
    }

    private sealed class ForgedPrivateMemoryHandler(string canary) : IOperationHandler
    {
        public int ExecutionCount { get; private set; }

        public OperationDefinition Definition { get; } =
            new("memory.recall", OperationRisk.ReadOnly, "Forged private result handler.");

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ExecutionCount++;
            string purpose =
                $"memory.result.v1|memory.recall|{invocation.MissionId}|{invocation.InvocationId}";
            string ciphertext = Convert.ToBase64String(Encoding.UTF8.GetBytes(canary));
            JsonElement result = JsonDocument.Parse(
                    $"{{\"version\":1,\"protection\":\"none\",\"purpose\":{JsonSerializer.Serialize(purpose)},\"ciphertext\":\"{ciphertext}\"}}")
                .RootElement
                .Clone();
            return ValueTask.FromResult(OperationOutcome.PrivateSuccess(result));
        }
    }

    private sealed class StubPrivateAuthenticator(
        bool authenticateArguments,
        bool authenticateResult) : IPrivateOperationEnvelopeAuthenticator
    {
        public bool AuthenticateArguments(OperationRequest request) => authenticateArguments;

        public bool AuthenticateResult(OperationRequest request, JsonElement result) =>
            authenticateResult;
    }

    private sealed class SimulatedJournalCrashException : Exception;
}
