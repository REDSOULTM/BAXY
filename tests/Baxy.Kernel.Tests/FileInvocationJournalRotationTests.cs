using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// Journal rotation (documentacion/computer-use/JOURNAL_ROTACION.md): measured on
/// 2026-10-07, a computer-use profile's journal reached its 64 MiB cap and the Core
/// refused every operation. These tests pin the rotation that seals the live segment
/// before that, with the journal's integrity guarantees intact.
/// </summary>
[TestFixture]
public sealed class FileInvocationJournalRotationTests
{
    private const long MaximumJournalBytes = 256 * 1024;
    private const int CompletionReservationBytes = 8 * 1024;
    private const long RotationThresholdBytes = 16 * 1024;

    private string _root = null!;
    private string _journalPath = null!;
    private byte[] _authenticationKey = null!;

    [SetUp]
    public void SetUp()
    {
        _root = Path.Combine(Path.GetTempPath(), "baxy-kernel-tests", Guid.NewGuid().ToString("N"));
        _journalPath = Path.Combine(_root, "journal", "missions.jsonl");
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

    private ValueTask<FileInvocationJournal> OpenRotatingAsync(
        int retainedArchiveSegments = 2,
        long rotationThresholdBytes = RotationThresholdBytes,
        Action<JournalCommitStage>? crashHook = null,
        Action<string>? diagnostics = null) =>
        FileInvocationJournal.OpenWithRotationForTestingAsync(
            _journalPath,
            new JournalHmacAuthenticator(_authenticationKey),
            MaximumJournalBytes,
            CompletionReservationBytes,
            rotationThresholdBytes,
            retainedArchiveSegments,
            crashHook,
            diagnostics);

    private string Archive(long segment) => FileInvocationJournal.SegmentPath(_journalPath, segment);

    private string Manifest => string.Concat(_journalPath, ".segments");

    private string Retired => string.Concat(_journalPath, ".retired");

    private string LiveAnchor => string.Concat(_journalPath, ".anchor");

    private string SegmentIndex(long segment) => string.Concat(Archive(segment), ".index");

    [Test]
    public void SegmentPathKeepsTheJournalNameAndExtension()
    {
        string path = Path.Combine(_root, "journal", "missions.jsonl");
        Assert.That(
            FileInvocationJournal.SegmentPath(path, 3),
            Is.EqualTo(Path.Combine(_root, "journal", "missions.3.jsonl")));
    }

    [Test]
    public async Task RotatesAtTheThresholdAndArchivedInvocationsStillReplayAndConflict()
    {
        OperationRequest early = CreateRequest();
        OperationRequest incomplete = CreateRequest();
        var handler = new CountingHandler();
        OperationResponse earlyResponse;
        await using (FileInvocationJournal journal = await OpenRotatingAsync())
        using (var engine = new MissionEngine(new OperationRegistry([handler]), journal))
        {
            earlyResponse = await engine.ExecuteAsync(early, CancellationToken.None);
            await journal.RecordStartedAsync(
                incomplete,
                RequestFingerprint.Compute(incomplete),
                CancellationToken.None);
            await ExecuteUntilAsync(engine, () => File.Exists(Archive(1)));

            int executed = handler.ExecutionCount;
            OperationResponse replay = await engine.ExecuteAsync(
                early with { RequestId = Guid.NewGuid().ToString("D") },
                CancellationToken.None);
            OperationResponse conflict = await engine.ExecuteAsync(
                ChangeContent(early, "otro contenido"),
                CancellationToken.None);
            string? carried = await journal.FindStartedFingerprintAsync(
                incomplete.InvocationId,
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(File.Exists(string.Concat(Archive(1), ".anchor")), Is.True);
                Assert.That(new FileInfo(_journalPath).Length, Is.LessThan(RotationThresholdBytes));
                Assert.That(replay.Replayed, Is.True);
                Assert.That(replay.Message, Is.EqualTo(earlyResponse.Message));
                Assert.That(conflict.ErrorCode, Is.EqualTo("idempotency_conflict"));
                Assert.That(carried, Is.EqualTo(RequestFingerprint.Compute(incomplete)));
                Assert.That(handler.ExecutionCount, Is.EqualTo(executed));
                Assert.That(File.ReadAllText(LiveAnchor, Encoding.UTF8), Does.Not.Contain("archive"));
                Assert.That(
                    File.ReadAllText(Manifest, Encoding.UTF8),
                    Does.Contain("\"segments\":[{\"segment\":1,"));
            });
        }

        var reopenedHandler = new CountingHandler();
        await using (FileInvocationJournal reopened = await OpenRotatingAsync())
        using (var engine = new MissionEngine(new OperationRegistry([reopenedHandler]), reopened))
        {
            OperationResponse replay = await engine.ExecuteAsync(
                early with { RequestId = Guid.NewGuid().ToString("D") },
                CancellationToken.None);
            OperationResponse recovered = await engine.ExecuteAsync(
                incomplete with { RequestId = Guid.NewGuid().ToString("D") },
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(replay.Replayed, Is.True);
                Assert.That(recovered.Verified, Is.True);
                Assert.That(recovered.Replayed, Is.False);
                Assert.That(reopenedHandler.ExecutionCount, Is.EqualTo(1));
            });
        }
    }

    [Test]
    public async Task CompactionAfterARotationKeepsTheArchiveLink()
    {
        OperationRequest early = CreateRequest();
        OperationRequest incomplete = CreateRequest();
        await using (FileInvocationJournal journal = await OpenRotatingAsync())
        using (var engine = new MissionEngine(new OperationRegistry([new CountingHandler()]), journal))
        {
            _ = await engine.ExecuteAsync(early, CancellationToken.None);
            await ExecuteUntilAsync(engine, () => File.Exists(Archive(1)));
            _ = await engine.ExecuteAsync(CreateRequest(), CancellationToken.None);
            await journal.RecordStartedAsync(
                incomplete,
                RequestFingerprint.Compute(incomplete),
                CancellationToken.None);
        }

        const int smallReservationBytes = 4 * 1024;
        string[] beforeCompaction = File.ReadAllLines(_journalPath, Encoding.UTF8);
        long nearCapacity = new FileInfo(_journalPath).Length + (2 * smallReservationBytes) + 64;
        var compactingHandler = new CountingHandler();
        await using (FileInvocationJournal compacting = await FileInvocationJournal.OpenWithCapacityForTestingAsync(
                         _journalPath,
                         new JournalHmacAuthenticator(_authenticationKey),
                         nearCapacity,
                         smallReservationBytes))
        using (var engine = new MissionEngine(new OperationRegistry([compactingHandler]), compacting))
        {
            OperationResponse trigger = await engine.ExecuteAsync(CreateRequest(), CancellationToken.None);
            Assert.That(trigger.Verified, Is.True);
        }

        string[] afterCompaction = File.ReadAllLines(_journalPath, Encoding.UTF8);
        var handler = new CountingHandler();
        await using FileInvocationJournal reopened = await OpenRotatingAsync();
        using var replayEngine = new MissionEngine(new OperationRegistry([handler]), reopened);
        OperationResponse replay = await replayEngine.ExecuteAsync(
            early with { RequestId = Guid.NewGuid().ToString("D") },
            CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(
                afterCompaction.Any(static line => line.Contains("\"phase\":\"retained_completed\"", StringComparison.Ordinal)),
                Is.True);
            Assert.That(afterCompaction, Has.Length.LessThanOrEqualTo(beforeCompaction.Length));
            Assert.That(File.ReadAllText(LiveAnchor, Encoding.UTF8), Does.Not.Contain("archive"));
            Assert.That(
                File.ReadAllText(Manifest, Encoding.UTF8),
                Does.Contain("\"segments\":[{\"segment\":1,"));
            Assert.That(replay.Replayed, Is.True);
            Assert.That(handler.ExecutionCount, Is.Zero);
        });
    }

    [Test]
    public async Task AJournalThatNeverRotatedKeepsItsAnchorFormat()
    {
        await using (FileInvocationJournal journal = await OpenRotatingAsync())
        using (var engine = new MissionEngine(new OperationRegistry([new CountingHandler()]), journal))
        {
            _ = await engine.ExecuteAsync(CreateRequest(), CancellationToken.None);
        }

        string anchor = File.ReadAllText(string.Concat(_journalPath, ".anchor"), Encoding.UTF8);
        Assert.Multiple(() =>
        {
            Assert.That(anchor, Does.Not.Contain("archive"));
            Assert.That(anchor, Does.Not.Contain("segment"));
            Assert.That(File.Exists(Archive(1)), Is.False);
            Assert.That(File.Exists(Manifest), Is.False);
            Assert.That(File.Exists(Retired), Is.False);
        });
    }

    [Test]
    public async Task AfterARotationTheLiveAnchorKeepsThePreRotationFormat()
    {
        // A Core rolled back to the format before rotation reads the live anchor
        // with exactly these fields; anything else fails its HMAC and canonical
        // checks as tampering. The rotation state lives in the manifest instead.
        await using (FileInvocationJournal journal = await OpenRotatingAsync())
        using (var engine = new MissionEngine(new OperationRegistry([new CountingHandler()]), journal))
        {
            await ExecuteUntilAsync(engine, () => File.Exists(Archive(1)));
        }

        using JsonDocument anchor = JsonDocument.Parse(File.ReadAllBytes(LiveAnchor));
        Assert.Multiple(() =>
        {
            Assert.That(
                anchor.RootElement.EnumerateObject().Select(static property => property.Name),
                Is.EqualTo(new[] { "payload", "tag" }));
            Assert.That(
                anchor.RootElement.GetProperty("payload").EnumerateObject().Select(static property => property.Name),
                Is.EqualTo(new[] { "version", "authentication", "phase", "current", "next" }));
            Assert.That(anchor.RootElement.GetProperty("payload").GetProperty("version").GetInt32(), Is.EqualTo(2));
            Assert.That(
                anchor.RootElement.GetProperty("payload").GetProperty("phase").GetString(),
                Is.EqualTo("committed"));
        });
    }

    [TestCase("modified")]
    [TestCase("truncated")]
    [TestCase("deleted")]
    [TestCase("anchor-deleted")]
    [TestCase("archived-anchor-as-live")]
    [TestCase("live-anchor-as-archived")]
    [TestCase("manifest-deleted")]
    [TestCase("manifest-modified")]
    public async Task AManipulatedArchivedSegmentIsDetected(string manipulation)
    {
        await using (FileInvocationJournal journal = await OpenRotatingAsync())
        using (var engine = new MissionEngine(new OperationRegistry([new CountingHandler()]), journal))
        {
            await ExecuteUntilAsync(engine, () => File.Exists(Archive(1)));
        }

        // Untouched, the rotated journal reopens: what fails below is the manipulation.
        await (await OpenRotatingAsync()).DisposeAsync();
        string archive = Archive(1);
        string archiveAnchor = string.Concat(archive, ".anchor");
        string liveAnchor = string.Concat(_journalPath, ".anchor");
        switch (manipulation)
        {
            case "modified":
                string text = File.ReadAllText(archive, Encoding.UTF8);
                int index = text.IndexOf("pan", StringComparison.Ordinal);
                Assert.That(index, Is.GreaterThan(0));
                File.WriteAllText(
                    archive,
                    string.Concat(text.AsSpan(0, index), "pon", text.AsSpan(index + 3)),
                    new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
                break;
            case "truncated":
                string[] lines = File.ReadAllLines(archive, Encoding.UTF8);
                File.WriteAllText(
                    archive,
                    string.Join('\n', lines[..^1]) + "\n",
                    new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
                break;
            case "deleted":
                File.Delete(archive);
                break;
            case "anchor-deleted":
                File.Delete(archiveAnchor);
                break;
            case "archived-anchor-as-live":
                File.Copy(archiveAnchor, liveAnchor, overwrite: true);
                break;
            case "live-anchor-as-archived":
                File.Copy(liveAnchor, archiveAnchor, overwrite: true);
                break;
            case "manifest-deleted":
                File.Delete(Manifest);
                break;
            case "manifest-modified":
                File.WriteAllText(
                    Manifest,
                    File.ReadAllText(Manifest, Encoding.UTF8).Replace("\"floor\":0", "\"floor\":1", StringComparison.Ordinal),
                    new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
                break;
            default:
                Assert.Fail(manipulation);
                break;
        }

        Assert.That(
            async () => await OpenRotatingAsync(),
            Throws.InstanceOf<JournalIntegrityException>());
    }

    [TestCase((int)JournalCommitStage.RotationArchiveAnchorDurable)]
    [TestCase((int)JournalCommitStage.RotationIntentDurable)]
    [TestCase((int)JournalCommitStage.RotationSegmentArchived)]
    [TestCase((int)JournalCommitStage.RotationJournalPublished)]
    [TestCase((int)JournalCommitStage.RotationAnchorCommitted)]
    [TestCase((int)JournalCommitStage.RotationManifestCommitted)]
    public async Task AnInterruptedRotationRecoversEveryRecordedInvocation(int crashStageValue)
    {
        var crashStage = (JournalCommitStage)crashStageValue;
        var crash = new SimulatedJournalCrashException();
        OperationRequest incomplete = CreateRequest();
        var executed = new List<OperationRequest>();
        OperationRequest? trigger = null;
        await using (FileInvocationJournal crashing = await OpenRotatingAsync(
                         crashHook: stage =>
                         {
                             if (stage == crashStage)
                             {
                                 throw crash;
                             }
                         }))
        using (var engine = new MissionEngine(new OperationRegistry([new CountingHandler()]), crashing))
        {
            await crashing.RecordStartedAsync(
                incomplete,
                RequestFingerprint.Compute(incomplete),
                CancellationToken.None);
            for (int attempt = 0; attempt < 200 && trigger is null; attempt++)
            {
                OperationRequest request = CreateRequest();
                try
                {
                    _ = await engine.ExecuteAsync(request, CancellationToken.None);
                    executed.Add(request);
                }
                catch (SimulatedJournalCrashException)
                {
                    trigger = request;
                }
            }
        }

        Assert.That(trigger, Is.Not.Null, "the rotation never reached the crash stage");
        for (int reopen = 0; reopen < 2; reopen++)
        {
            await using FileInvocationJournal recovered = await FileInvocationJournal.OpenAsync(
                _journalPath,
                new JournalHmacAuthenticator(_authenticationKey));
            foreach (OperationRequest request in executed)
            {
                CompletedInvocation? completed = await recovered.FindCompletedAsync(
                    request.InvocationId,
                    CancellationToken.None);
                Assert.That(completed?.RequestFingerprint, Is.EqualTo(RequestFingerprint.Compute(request)));
            }

            Assert.Multiple(() =>
            {
                Assert.That(
                    recovered.FindStartedFingerprintAsync(incomplete.InvocationId, CancellationToken.None)
                        .AsTask().GetAwaiter().GetResult(),
                    Is.EqualTo(RequestFingerprint.Compute(incomplete)));
                Assert.That(
                    recovered.FindStartedFingerprintAsync(trigger!.InvocationId, CancellationToken.None)
                        .AsTask().GetAwaiter().GetResult(),
                    Is.Null);
                Assert.That(File.Exists(string.Concat(_journalPath, ".rotating")), Is.False);
            });
        }
    }

    [Test]
    public async Task RetentionKeepsOnlyTheNewestArchivedSegments()
    {
        OperationRequest oldest = CreateRequest();
        var handler = new CountingHandler();
        await using (FileInvocationJournal journal = await OpenRotatingAsync(retainedArchiveSegments: 2))
        using (var engine = new MissionEngine(new OperationRegistry([handler]), journal))
        {
            _ = await engine.ExecuteAsync(oldest, CancellationToken.None);
            await ExecuteUntilAsync(engine, () => File.Exists(Archive(4)));
        }

        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(Archive(1)), Is.False);
            Assert.That(File.Exists(string.Concat(Archive(1), ".anchor")), Is.False);
            Assert.That(File.Exists(Archive(2)), Is.False);
            Assert.That(File.Exists(Archive(3)), Is.True);
            Assert.That(File.Exists(Archive(4)), Is.True);
        });

        // An invocation whose segment left the retention window has lost its
        // response, but not its identity: a late retry (the App's durable retry
        // and plan stores have no expiry) is refused, never executed again. The
        // retained ones still replay.
        string newestArchivedId = ArchivedInvocationIds(Archive(4)).First();
        var reopenedHandler = new CountingHandler();
        await using FileInvocationJournal reopened = await OpenRotatingAsync(retainedArchiveSegments: 2);
        using var reopenedEngine = new MissionEngine(new OperationRegistry([reopenedHandler]), reopened);
        OperationResponse lateRetry = await reopenedEngine.ExecuteAsync(
            oldest with { RequestId = Guid.NewGuid().ToString("D") },
            CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(lateRetry.ErrorCode, Is.EqualTo("idempotency_conflict"));
            Assert.That(reopenedHandler.ExecutionCount, Is.Zero);
            Assert.That(
                reopened.IsRetiredAsync(oldest.InvocationId, CancellationToken.None)
                    .AsTask().GetAwaiter().GetResult(),
                Is.True);
            Assert.That(
                reopened.FindCompletedAsync(oldest.InvocationId, CancellationToken.None)
                    .AsTask().GetAwaiter().GetResult(),
                Is.Null);
            Assert.That(
                reopened.FindCompletedAsync(newestArchivedId, CancellationToken.None)
                    .AsTask().GetAwaiter().GetResult(),
                Is.Not.Null);
            Assert.That(
                reopened.IsRetiredAsync(newestArchivedId, CancellationToken.None)
                    .AsTask().GetAwaiter().GetResult(),
                Is.False);
            Assert.That(File.ReadAllText(Retired, Encoding.UTF8), Does.Not.Contain(oldest.InvocationId));
        });
        Assert.That(
            async () => await reopened.RecordStartedAsync(
                oldest,
                RequestFingerprint.Compute(oldest),
                CancellationToken.None),
            Throws.InstanceOf<InvalidOperationException>());
    }

    [Test]
    public async Task RetentionRefusesThePrunedIdInTheSameSessionToo()
    {
        OperationRequest oldest = CreateRequest();
        var handler = new CountingHandler();
        await using FileInvocationJournal journal = await OpenRotatingAsync(retainedArchiveSegments: 1);
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        _ = await engine.ExecuteAsync(oldest, CancellationToken.None);
        await ExecuteUntilAsync(engine, () => File.Exists(Archive(2)));

        int executed = handler.ExecutionCount;
        OperationResponse lateRetry = await engine.ExecuteAsync(
            oldest with { RequestId = Guid.NewGuid().ToString("D") },
            CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(Archive(1)), Is.False);
            Assert.That(lateRetry.ErrorCode, Is.EqualTo("idempotency_conflict"));
            Assert.That(handler.ExecutionCount, Is.EqualTo(executed));
        });
    }

    [TestCase((int)JournalCommitStage.RetentionRetiredDurable)]
    [TestCase((int)JournalCommitStage.RetentionManifestCommitted)]
    public async Task AnInterruptedRetentionNeverExecutesAPrunedInvocationAgain(int crashStageValue)
    {
        var crashStage = (JournalCommitStage)crashStageValue;
        OperationRequest oldest = CreateRequest();
        bool crashed = false;
        await using (FileInvocationJournal crashing = await OpenRotatingAsync(
                         retainedArchiveSegments: 1,
                         crashHook: stage =>
                         {
                             if (stage == crashStage && !crashed)
                             {
                                 crashed = true;
                                 throw new SimulatedJournalCrashException();
                             }
                         }))
        using (var engine = new MissionEngine(new OperationRegistry([new CountingHandler()]), crashing))
        {
            _ = await engine.ExecuteAsync(oldest, CancellationToken.None);
            for (int attempt = 0; attempt < 400 && !crashed; attempt++)
            {
                try
                {
                    _ = await engine.ExecuteAsync(CreateRequest(), CancellationToken.None);
                }
                catch (SimulatedJournalCrashException)
                {
                }
            }
        }

        Assert.That(crashed, Is.True, "the retention never reached the crash stage");
        for (int reopen = 0; reopen < 2; reopen++)
        {
            var handler = new CountingHandler();
            await using FileInvocationJournal recovered = await OpenRotatingAsync(retainedArchiveSegments: 1);
            using var engine = new MissionEngine(new OperationRegistry([handler]), recovered);
            OperationResponse lateRetry = await engine.ExecuteAsync(
                oldest with { RequestId = Guid.NewGuid().ToString("D") },
                CancellationToken.None);
            Assert.Multiple(() =>
            {
                Assert.That(lateRetry.ErrorCode, Is.EqualTo("idempotency_conflict"));
                Assert.That(handler.ExecutionCount, Is.Zero);
                Assert.That(File.Exists(Archive(1)), Is.False);
            });
        }
    }

    [Test]
    public async Task ATamperedRetiredIdFileIsDetected()
    {
        await using (FileInvocationJournal journal = await OpenRotatingAsync(retainedArchiveSegments: 1))
        using (var engine = new MissionEngine(new OperationRegistry([new CountingHandler()]), journal))
        {
            await ExecuteUntilAsync(engine, () => File.Exists(Archive(2)));
        }

        await (await OpenRotatingAsync(retainedArchiveSegments: 1)).DisposeAsync();
        byte[] retired = File.ReadAllBytes(Retired);
        Assert.That(retired, Is.Not.Empty);
        retired[0] = retired[0] == (byte)'a' ? (byte)'b' : (byte)'a';
        File.WriteAllBytes(Retired, retired);

        Assert.That(
            async () => await OpenRotatingAsync(retainedArchiveSegments: 1),
            Throws.InstanceOf<JournalIntegrityException>());
    }

    [Test]
    public async Task AReplayedOlderManifestIsDetected()
    {
        byte[] firstManifest;
        await using (FileInvocationJournal journal = await OpenRotatingAsync())
        using (var engine = new MissionEngine(new OperationRegistry([new CountingHandler()]), journal))
        {
            await ExecuteUntilAsync(engine, () => File.Exists(Archive(1)));
            firstManifest = File.ReadAllBytes(Manifest);
            await ExecuteUntilAsync(engine, () => File.Exists(Archive(2)));
        }

        File.WriteAllBytes(Manifest, firstManifest);
        Assert.That(
            async () => await OpenRotatingAsync(),
            Throws.InstanceOf<JournalIntegrityException>());
    }

    [Test]
    public async Task AResetJournalBesideOldSegmentsKeepsRotating()
    {
        // The reported trap: the live journal and its anchor moved away (by a person
        // or a harness) beside segments of earlier rotations. The next rotation used
        // to ask for segment 1 again, fail in silence on every write and let the live
        // segment reach the hard cap.
        await using (FileInvocationJournal journal = await OpenRotatingAsync())
        using (var engine = new MissionEngine(new OperationRegistry([new CountingHandler()]), journal))
        {
            await ExecuteUntilAsync(engine, () => File.Exists(Archive(2)));
        }

        string movedAway = Path.Combine(_root, "moved");
        Directory.CreateDirectory(movedAway);
        File.Move(_journalPath, Path.Combine(movedAway, "missions.jsonl"));
        File.Move(LiveAnchor, Path.Combine(movedAway, "missions.jsonl.anchor"));
        byte[] oldSegment = File.ReadAllBytes(Archive(1));

        var diagnostics = new List<string>();
        await using (FileInvocationJournal reset = await OpenRotatingAsync(diagnostics: diagnostics.Add))
        using (var engine = new MissionEngine(new OperationRegistry([new CountingHandler()]), reset))
        {
            await ExecuteUntilAsync(engine, () => File.Exists(Archive(3)));
            Assert.Multiple(() =>
            {
                Assert.That(reset.RotationPostponements, Is.Zero, reset.LastRotationPostponement);
                Assert.That(diagnostics, Is.Empty);
            });
        }

        await using FileInvocationJournal reopened = await OpenRotatingAsync();
        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(Archive(1)), Is.EqualTo(oldSegment));
            Assert.That(
                Directory.GetFiles(Path.GetDirectoryName(_journalPath)!, "missions.jsonl.segments.reset-*"),
                Has.Length.EqualTo(1));
            Assert.That(new FileInfo(_journalPath).Length, Is.LessThan(RotationThresholdBytes));
        });
    }

    [Test]
    public async Task ArchivedSegmentsWithoutTheirManifestAreDetected()
    {
        await using (FileInvocationJournal journal = await OpenRotatingAsync())
        using (var engine = new MissionEngine(new OperationRegistry([new CountingHandler()]), journal))
        {
            await ExecuteUntilAsync(engine, () => File.Exists(Archive(1)));
            _ = await engine.ExecuteAsync(CreateRequest(), CancellationToken.None);
        }

        File.Delete(Manifest);
        Assert.That(
            async () => await OpenRotatingAsync(),
            Throws.InstanceOf<JournalIntegrityException>());
    }

    [Test]
    public async Task ASealedSegmentIsScannedOnceAndItsAuthenticatedIndexServesLaterOpens()
    {
        // 2026-10-09: every Core start re-authenticated the whole sealed segments
        // (50 MB) before its hello and missed the App's 10 s budget under load.
        OperationRequest early = CreateRequest();
        await using (FileInvocationJournal journal = await OpenRotatingAsync())
        using (var engine = new MissionEngine(new OperationRegistry([new CountingHandler()]), journal))
        {
            _ = await engine.ExecuteAsync(early, CancellationToken.None);
            await ExecuteUntilAsync(engine, () => File.Exists(Archive(1)));
        }

        Assert.That(ArchivedInvocationIds(Archive(1)), Does.Contain(early.InvocationId));
        await (await OpenRotatingAsync()).DisposeAsync();
        Assert.That(File.Exists(SegmentIndex(1)), Is.True);
        byte[] index = File.ReadAllBytes(SegmentIndex(1));
        DateTime indexWritten = File.GetLastWriteTimeUtc(SegmentIndex(1));

        await (await OpenRotatingAsync()).DisposeAsync();
        Assert.That(File.GetLastWriteTimeUtc(SegmentIndex(1)), Is.EqualTo(indexWritten), "a bound index is not rewritten");

        // An index that no longer authenticates is ignored: the segment is scanned
        // again, the replay still comes from the sealed records, and the index is
        // rebuilt from that scan.
        File.WriteAllText(
            SegmentIndex(1),
            File.ReadAllText(SegmentIndex(1), Encoding.UTF8)
                .Replace(early.InvocationId, Guid.NewGuid().ToString("D"), StringComparison.Ordinal),
            new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
        var handler = new CountingHandler();
        await using (FileInvocationJournal reopened = await OpenRotatingAsync())
        using (var engine = new MissionEngine(new OperationRegistry([handler]), reopened))
        {
            OperationResponse replay = await engine.ExecuteAsync(
                early with { RequestId = Guid.NewGuid().ToString("D") },
                CancellationToken.None);
            Assert.Multiple(() =>
            {
                Assert.That(replay.Replayed, Is.True);
                Assert.That(handler.ExecutionCount, Is.Zero);
                Assert.That(File.ReadAllBytes(SegmentIndex(1)), Is.EqualTo(index));
            });
        }
    }

    [Test]
    public async Task ASealedSegmentChangedBehindItsIndexIsRefusedWhenItsCompletionIsRead()
    {
        OperationRequest early = CreateRequest();
        await using (FileInvocationJournal journal = await OpenRotatingAsync())
        using (var engine = new MissionEngine(new OperationRegistry([new CountingHandler()]), journal))
        {
            _ = await engine.ExecuteAsync(early, CancellationToken.None);
            await ExecuteUntilAsync(engine, () => File.Exists(Archive(1)));
        }

        await (await OpenRotatingAsync()).DisposeAsync();
        Assert.That(File.Exists(SegmentIndex(1)), Is.True);

        // Same length and the old write time: the open trusts the index, but the
        // records themselves are never trusted without their HMAC chain.
        string archive = Archive(1);
        DateTime written = File.GetLastWriteTimeUtc(archive);
        string text = File.ReadAllText(archive, Encoding.UTF8);
        int at = text.IndexOf("pan", StringComparison.Ordinal);
        Assert.That(at, Is.GreaterThan(0));
        File.WriteAllText(
            archive,
            string.Concat(text.AsSpan(0, at), "pon", text.AsSpan(at + 3)),
            new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
        File.SetLastWriteTimeUtc(archive, written);

        var handler = new CountingHandler();
        await using (FileInvocationJournal reopened = await OpenRotatingAsync())
        using (var reopenedEngine = new MissionEngine(new OperationRegistry([handler]), reopened))
        {
            Assert.Multiple(() =>
            {
                Assert.That(
                    async () => await reopened.FindCompletedAsync(early.InvocationId, CancellationToken.None),
                    Throws.InstanceOf<JournalIntegrityException>());
                Assert.That(
                    async () => await reopenedEngine.ExecuteAsync(
                        early with { RequestId = Guid.NewGuid().ToString("D") },
                        CancellationToken.None),
                    Throws.InstanceOf<JournalIntegrityException>());
                Assert.That(handler.ExecutionCount, Is.Zero);
            });
        }

        // With its write time moved (any ordinary edit) the next open scans and refuses.
        File.SetLastWriteTimeUtc(archive, written.AddSeconds(1));
        Assert.That(
            async () => await OpenRotatingAsync(),
            Throws.InstanceOf<JournalIntegrityException>());
    }

    [Test]
    [Explicit("Medida: apertura de un journal de ~80 MB con y sin el índice de sus segmentos sellados.")]
    public async Task MeasureOpeningAnEightyMegabyteJournal()
    {
        const long maximumBytes = 64L * 1024 * 1024;
        const int reservationBytes = 2 * 1024 * 1024;
        const long thresholdBytes = 26L * 1024 * 1024;
        string content = string.Concat(Enumerable.Repeat("pan, leche y huevos para la semana; ", 1100));
        ValueTask<FileInvocationJournal> Open() =>
            FileInvocationJournal.OpenWithRotationForTestingAsync(
                _journalPath,
                new JournalHmacAuthenticator(_authenticationKey),
                maximumBytes,
                reservationBytes,
                thresholdBytes,
                retainedArchiveSegments: 2);

        await using (FileInvocationJournal journal = await Open())
        using (var engine = new MissionEngine(new OperationRegistry([new CountingHandler()]), journal))
        {
            for (int count = 0;
                 count < 5000
                 && !(File.Exists(Archive(2)) && new FileInfo(_journalPath).Length > thresholdBytes * 9 / 10);
                 count++)
            {
                OperationResponse response = await engine.ExecuteAsync(
                    ChangeContent(CreateRequest(), content),
                    CancellationToken.None);
                Assert.That(response.Verified, Is.True);
            }
        }

        string directory = Path.GetDirectoryName(_journalPath)!;
        long total = Directory.GetFiles(directory, "missions*.jsonl").Sum(static file => new FileInfo(file).Length);
        await (await Open()).DisposeAsync(); // JIT and file cache warm for both measures
        foreach (string index in Directory.GetFiles(directory, "*.index"))
        {
            File.Delete(index);
        }

        var clock = System.Diagnostics.Stopwatch.StartNew();
        await (await Open()).DisposeAsync();
        TimeSpan scanned = clock.Elapsed;
        clock.Restart();
        await (await Open()).DisposeAsync();
        TimeSpan indexed = clock.Elapsed;
        TestContext.Out.WriteLine(
            $"journal {total / (1024.0 * 1024):F1} MB (live {new FileInfo(_journalPath).Length / (1024.0 * 1024):F1} MB): "
            + $"open scanning sealed segments {scanned.TotalMilliseconds:F0} ms, with their index {indexed.TotalMilliseconds:F0} ms");
        Assert.That(indexed, Is.LessThan(scanned));
    }

    [Test]
    public async Task AJournalOverTheThresholdRotatesWhenOpened()
    {
        var requests = new List<OperationRequest>();
        await using (FileInvocationJournal unrotated = await FileInvocationJournal.OpenWithCapacityForTestingAsync(
                         _journalPath,
                         new JournalHmacAuthenticator(_authenticationKey),
                         MaximumJournalBytes,
                         CompletionReservationBytes))
        using (var engine = new MissionEngine(new OperationRegistry([new CountingHandler()]), unrotated))
        {
            while (new FileInfo(_journalPath).Length <= RotationThresholdBytes)
            {
                OperationRequest request = CreateRequest();
                _ = await engine.ExecuteAsync(request, CancellationToken.None);
                requests.Add(request);
            }
        }

        Assert.That(File.Exists(Archive(1)), Is.False);
        var handler = new CountingHandler();
        await using FileInvocationJournal opened = await OpenRotatingAsync();
        using var replayEngine = new MissionEngine(new OperationRegistry([handler]), opened);
        OperationResponse replay = await replayEngine.ExecuteAsync(
            requests[0] with { RequestId = Guid.NewGuid().ToString("D") },
            CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(Archive(1)), Is.True);
            Assert.That(new FileInfo(_journalPath).Length, Is.Zero);
            Assert.That(replay.Replayed, Is.True);
            Assert.That(handler.ExecutionCount, Is.Zero);
        });
    }

    [Test]
    public async Task ALiveSegmentHeldOpenByAReaderPostponesRotationWithoutLosingWrites()
    {
        var handler = new CountingHandler();
        var diagnostics = new List<string>();
        await using FileInvocationJournal journal = await OpenRotatingAsync(diagnostics: diagnostics.Add);
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        _ = await engine.ExecuteAsync(CreateRequest(), CancellationToken.None);
        while (new FileInfo(_journalPath).Length <= RotationThresholdBytes - 512)
        {
            _ = await engine.ExecuteAsync(CreateRequest(), CancellationToken.None);
        }

        Assert.That(File.Exists(Archive(1)), Is.False);
        OperationRequest heldRequest = CreateRequest();
        OperationResponse held;
        using (new FileStream(_journalPath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
        {
            while (new FileInfo(_journalPath).Length <= RotationThresholdBytes)
            {
                _ = await engine.ExecuteAsync(CreateRequest(), CancellationToken.None);
            }

            held = await engine.ExecuteAsync(heldRequest, CancellationToken.None);
        }

        Assert.Multiple(() =>
        {
            Assert.That(held.Verified, Is.True);
            Assert.That(File.Exists(Archive(1)), Is.False);
            Assert.That(new FileInfo(_journalPath).Length, Is.GreaterThan(RotationThresholdBytes));
            Assert.That(journal.RotationPostponements, Is.GreaterThan(0));
            Assert.That(diagnostics, Has.Count.GreaterThan(0));
            Assert.That(diagnostics[0], Does.Contain("rotation postponed"));
            Assert.That(File.Exists(Manifest), Is.False);
        });

        _ = await engine.ExecuteAsync(CreateRequest(), CancellationToken.None);
        OperationResponse replay = await engine.ExecuteAsync(
            heldRequest with { RequestId = Guid.NewGuid().ToString("D") },
            CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(Archive(1)), Is.True);
            Assert.That(replay.Replayed, Is.True);
        });
    }

    private static async Task ExecuteUntilAsync(MissionEngine engine, Func<bool> done)
    {
        for (int attempt = 0; attempt < 400 && !done(); attempt++)
        {
            OperationResponse response = await engine.ExecuteAsync(CreateRequest(), CancellationToken.None);
            Assert.That(response.Verified, Is.True);
        }

        Assert.That(done(), Is.True, "the journal never rotated");
    }

    private static IEnumerable<string> ArchivedInvocationIds(string segmentPath)
    {
        foreach (string line in File.ReadLines(segmentPath, Encoding.UTF8))
        {
            using JsonDocument record = JsonDocument.Parse(line);
            JsonElement payload = record.RootElement.GetProperty("payload");
            if (payload.GetProperty("response").ValueKind == JsonValueKind.Object)
            {
                yield return payload.GetProperty("invocationId").GetString()!;
            }
        }
    }

    private static OperationRequest CreateRequest() => new(
        ProtocolTypes.OperationRequest,
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        "note.create",
        JsonDocument.Parse("{\"title\":\"Compras\",\"content\":\"pan\"}").RootElement.Clone());

    private static OperationRequest ChangeContent(OperationRequest request, string content) =>
        request with
        {
            RequestId = Guid.NewGuid().ToString("D"),
            Arguments = JsonDocument.Parse(
                    $"{{\"title\":\"Compras\",\"content\":{JsonSerializer.Serialize(content)}}}")
                .RootElement.Clone(),
        };

    private sealed class CountingHandler : IOperationHandler
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
            return ValueTask.FromResult(OperationOutcome.Success(invocation.Arguments));
        }
    }

    private sealed class SimulatedJournalCrashException : Exception;
}
