using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Providers.Windows.Audio;
using Baxy.Providers.Windows.Notes;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class DurableRetryStoreTests
{
    private string _root = null!;
    private string _outboxPath = null!;

    [SetUp]
    public void SetUp()
    {
        _root = PrivateDataRootTestSupport.NewPath("outbox-tests");
        _outboxPath = Path.Combine(_root, "shell", "retry-outbox.v1.json");
    }

    [TearDown]
    public void TearDown()
    {
        if (Directory.Exists(_root))
        {
            Directory.Delete(_root, recursive: true);
        }
    }

    [Test]
    public void RestartRecoversIdentifiersUntilTheOperationIsResolved()
    {
        RoutedOperation routed = CreateRoutedOperation("Compras");
        var registry1 = new RetryableOperationRegistry(_outboxPath);
        PreparedOperation first = registry1.GetOrAdd(routed);

        var registry2 = new RetryableOperationRegistry(_outboxPath);
        PreparedOperation recovered = registry2.GetOrAdd(routed);

        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(_outboxPath), Is.True);
            Assert.That(recovered.MissionId, Is.EqualTo(first.MissionId));
            Assert.That(recovered.InvocationId, Is.EqualTo(first.InvocationId));
            Assert.That(recovered.OperationName, Is.EqualTo(first.OperationName));
            Assert.That(
                recovered.CreateRequest().Arguments.GetRawText(),
                Is.EqualTo(first.CreateRequest().Arguments.GetRawText()));
        });

        registry2.MarkResolved(recovered);
        var registry3 = new RetryableOperationRegistry(_outboxPath);
        PreparedOperation next = registry3.GetOrAdd(routed);

        Assert.Multiple(() =>
        {
            Assert.That(next.MissionId, Is.Not.EqualTo(first.MissionId));
            Assert.That(next.InvocationId, Is.Not.EqualTo(first.InvocationId));
        });
    }

    [Test]
    public void FreshSupersedingEffectReplacesEquivalentPendingIdentityAtomically()
    {
        var routed = new RoutedOperation(
            "app.open",
            new JsonObject { ["appId"] = "Steam" });
        var firstRegistry = new RetryableOperationRegistry(_outboxPath);
        PreparedOperation uncertain = firstRegistry.GetOrAdd(routed);

        var resumedRegistry = new RetryableOperationRegistry(_outboxPath);
        PreparedOperation fresh = resumedRegistry.StartFreshSupersedingEquivalent(routed);
        PreparedOperation persisted = new RetryableOperationRegistry(_outboxPath)
            .SnapshotPendingOperations()
            .Single();

        Assert.Multiple(() =>
        {
            Assert.That(fresh.MissionId, Is.Not.EqualTo(uncertain.MissionId));
            Assert.That(fresh.InvocationId, Is.Not.EqualTo(uncertain.InvocationId));
            Assert.That(persisted.MissionId, Is.EqualTo(fresh.MissionId));
            Assert.That(persisted.InvocationId, Is.EqualTo(fresh.InvocationId));
            Assert.That(
                MindPlanBoundary.FreshInvocationSupersedesEquivalentPendingEffect(
                    "app.open"),
                Is.True);
            Assert.That(
                MindPlanBoundary.FreshInvocationSupersedesEquivalentPendingEffect(
                    "message.send"),
                Is.False);
        });
    }

    [Test]
    public void EquivalentArgumentsWithDifferentPropertyOrderRecoverTheSameIdentifiers()
    {
        var firstRoute = new RoutedOperation(
            "note.create",
            new JsonObject { ["title"] = "Compras", ["content"] = "pan" });
        var reorderedRoute = new RoutedOperation(
            "note.create",
            new JsonObject { ["content"] = "pan", ["title"] = "Compras" });
        PreparedOperation first = new RetryableOperationRegistry(_outboxPath).GetOrAdd(firstRoute);

        PreparedOperation recovered = new RetryableOperationRegistry(_outboxPath).GetOrAdd(reorderedRoute);

        Assert.Multiple(() =>
        {
            Assert.That(recovered.MissionId, Is.EqualTo(first.MissionId));
            Assert.That(recovered.InvocationId, Is.EqualTo(first.InvocationId));
        });
    }

    [Test]
    public void UnknownOrCaseMismatchedFieldsAreQuarantinedBeforeRecovery()
    {
        var registry = new RetryableOperationRegistry(_outboxPath);
        _ = registry.GetOrAdd(CreateRoutedOperation("Compras"));
        string valid = File.ReadAllText(_outboxPath, Encoding.UTF8);

        File.WriteAllText(
            _outboxPath,
            valid.Replace("\"version\"", "\"Version\"", StringComparison.Ordinal),
            new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
        _ = AssertQuarantined(
            _outboxPath,
            File.ReadAllBytes(_outboxPath));

        string secondPath = Path.Combine(_root, "shell", "retry-outbox.second.json");
        File.WriteAllText(
            secondPath,
            valid[..^1] + ",\"unexpected\":true}",
            new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
        _ = AssertQuarantined(secondPath, File.ReadAllBytes(secondPath));
    }

    [Test]
    public void CanonicalUuidNibbleFlipFailsClosedBeforeAnyOperationCanResume()
    {
        _ = new RetryableOperationRegistry(_outboxPath).GetOrAdd(CreateRoutedOperation("Compras"));
        byte[] corrupted = File.ReadAllBytes(_outboxPath);
        FlipHexNibbleAfterMarker(corrupted, "\"invocationId\":\"");
        File.WriteAllBytes(_outboxPath, corrupted);

        using JsonDocument document = JsonDocument.Parse(corrupted);
        string changedInvocationId = document.RootElement
            .GetProperty("entries")[0]
            .GetProperty("invocationId")
            .GetString()!;
        RetryableOperationRegistry resumedRegistry = AssertQuarantined(_outboxPath, corrupted);

        Assert.Multiple(() =>
        {
            Assert.That(ContractValidator.IsCanonicalIdentifier(changedInvocationId), Is.True);
            Assert.That(resumedRegistry.SnapshotPendingOperations(), Is.Empty);
        });
    }

    [Test]
    public void ValidArgumentBitFlipFailsClosedBeforeAnyOperationCanResume()
    {
        _ = new RetryableOperationRegistry(_outboxPath).GetOrAdd(CreateRoutedOperation("Compras"));
        byte[] corrupted = File.ReadAllBytes(_outboxPath);
        FlipFirstByteAfterMarker(corrupted, "\"content\":\"");
        File.WriteAllBytes(_outboxPath, corrupted);

        using JsonDocument document = JsonDocument.Parse(corrupted);
        string changedContent = document.RootElement
            .GetProperty("entries")[0]
            .GetProperty("arguments")
            .GetProperty("content")
            .GetString()!;
        RetryableOperationRegistry resumedRegistry = AssertQuarantined(_outboxPath, corrupted);

        Assert.Multiple(() =>
        {
            Assert.That(changedContent, Is.EqualTo("meche y pan"));
            Assert.That(resumedRegistry.SnapshotPendingOperations(), Is.Empty);
        });
    }

    [Test]
    public void OversizedFileIsQuarantinedBeforeItCanBeLoaded()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(_outboxPath)!);
        File.WriteAllBytes(_outboxPath, new byte[DurableRetryStore.MaximumFileBytes + 1]);

        byte[] oversized = File.ReadAllBytes(_outboxPath);
        _ = AssertQuarantined(_outboxPath, oversized);
    }

    [Test]
    public void TooManyEntriesAreQuarantinedBeforeAnyIdentifiersAreRestored()
    {
        var entries = new JsonArray();
        for (int index = 0; index <= DurableRetryStore.MaximumEntries; index++)
        {
            entries.Add(new JsonObject
            {
                ["operation"] = "note.create",
                ["arguments"] = new JsonObject
                {
                    ["title"] = $"Nota {index}",
                    ["content"] = "contenido",
                },
                ["missionId"] = Guid.NewGuid().ToString("D"),
                ["invocationId"] = Guid.NewGuid().ToString("D"),
            });
        }

        Directory.CreateDirectory(Path.GetDirectoryName(_outboxPath)!);
        File.WriteAllText(
            _outboxPath,
            new JsonObject { ["version"] = 1, ["entries"] = entries }.ToJsonString(),
            new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));

        _ = AssertQuarantined(_outboxPath, File.ReadAllBytes(_outboxPath));
    }

    [Test]
    public void OversizedArgumentsAreNotPersisted()
    {
        var registry = new RetryableOperationRegistry(_outboxPath);
        var routed = new RoutedOperation(
            "note.create",
            new JsonObject
            {
                ["title"] = "Grande",
                ["content"] = new string('x', DurableRetryStore.MaximumArgumentsBytes),
            });

        Assert.That(
            () => _ = registry.GetOrAdd(routed),
            Throws.InstanceOf<System.Text.Json.JsonException>());
        Assert.That(File.Exists(_outboxPath), Is.False);
    }

    [Test]
    public void AlternateDataStreamAndRelativePathsAreRejected()
    {
        Assert.Multiple(() =>
        {
            Assert.That(
                () => _ = new RetryableOperationRegistry(_outboxPath + ":hidden"),
                Throws.InstanceOf<ArgumentException>());
            Assert.That(
                () => _ = new RetryableOperationRegistry("retry-outbox.v1.json"),
                Throws.InstanceOf<ArgumentException>());
        });
    }

    [Test]
    public void ReparsePointInDirectoryChainIsRejected()
    {
        Directory.CreateDirectory(_root);
        string target = Path.Combine(_root, "target");
        string link = Path.Combine(_root, "linked-shell");
        Directory.CreateDirectory(target);

        _ = Baxy.Tests.NtfsTestJunction.Create(link, target);

        try
        {
            Assert.That(
                () => _ = new RetryableOperationRegistry(Path.Combine(link, "outbox.json")),
                Throws.InstanceOf<IOException>());
            Assert.That(Directory.GetFileSystemEntries(target), Is.Empty);
        }
        finally
        {
            Directory.Delete(link);
        }
    }

    [Test]
    public void PersistenceFailurePreventsTheCallerFromSending()
    {
        var registry = new RetryableOperationRegistry(_outboxPath);
        Directory.CreateDirectory(_outboxPath);
        bool sent = false;

        try
        {
            _ = registry.GetOrAdd(CreateRoutedOperation("Compras"));
            sent = true;
        }
        catch (IOException)
        {
            // The caller never reaches the transport after durable preparation fails.
        }

        Assert.That(sent, Is.False);
    }

    [Test]
    public void FailedPrecommitVerificationPreservesThePreviousRetryIdentity()
    {
        RoutedOperation routed = CreateRoutedOperation("Compras");
        PreparedOperation original = new RetryableOperationRegistry(_outboxPath).GetOrAdd(routed);
        byte[] previousFile = File.ReadAllBytes(_outboxPath);
        var failingStore = new DurableRetryStore(
            _outboxPath,
            temporaryPath => File.AppendAllText(
                temporaryPath,
                "x",
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: false)));
        var registry = new RetryableOperationRegistry(failingStore);
        PreparedOperation recovered = registry.GetOrAdd(routed);

        Assert.That(
            () => registry.MarkResolved(recovered),
            Throws.TypeOf<IOException>());

        PreparedOperation afterRestart = new RetryableOperationRegistry(_outboxPath).GetOrAdd(routed);
        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(_outboxPath), Is.EqualTo(previousFile));
            Assert.That(afterRestart.MissionId, Is.EqualTo(original.MissionId));
            Assert.That(afterRestart.InvocationId, Is.EqualTo(original.InvocationId));
        });
    }

    [Test]
    public void JournalCapacityResponseKeepsTheDurableRetryIdentity()
    {
        RoutedOperation routed = CreateRoutedOperation("Compras");
        var registry = new RetryableOperationRegistry(_outboxPath);
        PreparedOperation prepared = registry.GetOrAdd(routed);
        var noteStore = new LocalNoteStore(Path.Combine(_root, "notes-store"));
        NoteRecord priorEffect = noteStore.Create(
            "Compras",
            "leche y pan",
            prepared.InvocationId);
        var capacityResponse = new OperationResponse(
            ProtocolTypes.OperationResponse,
            prepared.CreateRequest().RequestId,
            prepared.MissionId,
            prepared.InvocationId,
            OperationStatuses.Rejected,
            "El historial seguro alcanzó su capacidad.",
            false,
            false,
            null,
            "journal_capacity_reached");

        if (!MainWindowViewModel.ShouldRetainRetryIdentity(capacityResponse))
        {
            registry.MarkResolved(prepared);
        }

        PreparedOperation afterRestart = new RetryableOperationRegistry(_outboxPath).GetOrAdd(routed);
        NoteRecord reconciled = noteStore.Create(
            "Compras",
            "leche y pan",
            afterRestart.InvocationId);
        Assert.Multiple(() =>
        {
            Assert.That(afterRestart.MissionId, Is.EqualTo(prepared.MissionId));
            Assert.That(afterRestart.InvocationId, Is.EqualTo(prepared.InvocationId));
            Assert.That(reconciled, Is.EqualTo(priorEffect));
            Assert.That(noteStore.List(NoteListScope.All), Is.EqualTo(new[] { priorEffect }));
        });
    }

    [Test]
    public void PendingAudioResponseKeepsTheExactRecoveryIdentity()
    {
        var routed = new RoutedOperation(
            AudioOperationIds.Volume,
            new JsonObject { ["level"] = 30 });
        var registry = new RetryableOperationRegistry(_outboxPath);
        PreparedOperation prepared = registry.GetOrAdd(routed);
        var pending = new OperationResponse(
            ProtocolTypes.OperationResponse,
            prepared.CreateRequest().RequestId,
            prepared.MissionId,
            prepared.InvocationId,
            OperationStatuses.Pending,
            "El ajuste requiere reconciliación.",
            false,
            false,
            null,
            AudioControlErrorCodes.ReconciliationRequired);

        if (!MainWindowViewModel.ShouldRetainRetryIdentity(pending))
        {
            registry.MarkResolved(prepared);
        }

        PreparedOperation recovered = new RetryableOperationRegistry(_outboxPath)
            .GetOrAdd(routed);
        Assert.Multiple(() =>
        {
            Assert.That(recovered.MissionId, Is.EqualTo(prepared.MissionId));
            Assert.That(recovered.InvocationId, Is.EqualTo(prepared.InvocationId));
            Assert.That(recovered.Matches(routed), Is.True);
        });
    }

    [Test]
    public void TerminalAudioUncertaintyClosesOutboxAndNextRequestGetsNewIdentity()
    {
        var routed = new RoutedOperation(
            AudioOperationIds.Volume,
            new JsonObject { ["level"] = 30 });
        var registry = new RetryableOperationRegistry(_outboxPath);
        PreparedOperation prepared = registry.GetOrAdd(routed);
        var terminal = new OperationResponse(
            ProtocolTypes.OperationResponse,
            prepared.CreateRequest().RequestId,
            prepared.MissionId,
            prepared.InvocationId,
            OperationStatuses.Failed,
            "El estado final observado contradice el intento.",
            false,
            false,
            null,
            AudioControlErrorCodes.EffectUncertain);

        Assert.That(MainWindowViewModel.ShouldRetainRetryIdentity(terminal), Is.False);
        registry.MarkResolved(prepared);
        PreparedOperation next = new RetryableOperationRegistry(_outboxPath).GetOrAdd(routed);

        Assert.Multiple(() =>
        {
            Assert.That(next.MissionId, Is.Not.EqualTo(prepared.MissionId));
            Assert.That(next.InvocationId, Is.Not.EqualTo(prepared.InvocationId));
        });
    }

    [Test]
    public void FailedResponseWithPossibleEffectRetainsExactRecoveryIdentity()
    {
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            OperationStatuses.Failed,
            "La respuesta se perdió después del posible efecto.",
            false,
            false,
            null,
            "transport_lost",
            EffectMayHaveOccurred: true);

        Assert.That(MainWindowViewModel.ShouldRetainRetryIdentity(response), Is.True);
    }

    [Test]
    public void ReplaceAtomicallySwapsAmbiguousTitleForExactSelectedSnapshot()
    {
        var originalRoute = new RoutedOperation(
            "note.trash",
            new JsonObject { ["title"] = "Compras" });
        Guid selectedId = Guid.NewGuid();
        var selectedRoute = new RoutedOperation(
            "note.trash",
            new JsonObject
            {
                ["noteId"] = selectedId.ToString("D"),
                ["expectedTitle"] = "Compras",
                ["expectedRevision"] = 4,
                ["expectedIsTrashed"] = false,
            });
        var registry = new RetryableOperationRegistry(_outboxPath);
        PreparedOperation original = registry.GetOrAdd(originalRoute);

        PreparedOperation selected = registry.ReplaceWithFollowUp(original, selectedRoute);
        PreparedOperation[] recovered = new RetryableOperationRegistry(_outboxPath)
            .SnapshotPendingOperations()
            .ToArray();

        Assert.Multiple(() =>
        {
            Assert.That(recovered, Has.Length.EqualTo(1));
            Assert.That(recovered[0].IdentityKey, Is.EqualTo(selected.IdentityKey));
            Assert.That(recovered[0].IdentityKey, Is.Not.EqualTo(original.IdentityKey));
            Assert.That(recovered[0].MissionId, Is.EqualTo(original.MissionId));
            Assert.That(recovered[0].InvocationId, Is.Not.EqualTo(original.InvocationId));
            Assert.That(
                recovered[0].Arguments.GetProperty("noteId").GetString(),
                Is.EqualTo(selectedId.ToString("D")));
        });
    }

    [Test]
    public void FailedAtomicReplacementPreservesOnlyTheOriginalAmbiguity()
    {
        var originalRoute = new RoutedOperation(
            "note.restore",
            new JsonObject { ["title"] = "Compras" });
        PreparedOperation original = new RetryableOperationRegistry(_outboxPath)
            .GetOrAdd(originalRoute);
        byte[] previousFile = File.ReadAllBytes(_outboxPath);
        var failingStore = new DurableRetryStore(
            _outboxPath,
            temporaryPath => File.AppendAllText(
                temporaryPath,
                "x",
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: false)));
        var registry = new RetryableOperationRegistry(failingStore);
        PreparedOperation current = registry.SnapshotPendingOperations().Single();
        var selectedRoute = new RoutedOperation(
            "note.restore",
            new JsonObject
            {
                ["noteId"] = Guid.NewGuid().ToString("D"),
                ["expectedTitle"] = "Compras",
                ["expectedRevision"] = 1,
                ["expectedIsTrashed"] = true,
            });

        Assert.That(
            () => registry.Replace(current, selectedRoute),
            Throws.TypeOf<IOException>());

        PreparedOperation recovered = new RetryableOperationRegistry(_outboxPath)
            .SnapshotPendingOperations()
            .Single();
        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(_outboxPath), Is.EqualTo(previousFile));
            Assert.That(recovered.IdentityKey, Is.EqualTo(original.IdentityKey));
            Assert.That(recovered.OperationName, Is.EqualTo("note.restore"));
            Assert.That(recovered.Arguments.GetProperty("title").GetString(), Is.EqualTo("Compras"));
        });
    }

    [Test]
    [NonParallelizable]
    public async Task CorruptDefaultOutboxIsQuarantinedAndTheShellRecovers()
    {
        string? previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", _root);
        Directory.CreateDirectory(Path.GetDirectoryName(_outboxPath)!);
        await File.WriteAllTextAsync(
            _outboxPath,
            "{not-json",
            new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));

        try
        {
            await using var viewModel = new MainWindowViewModel();
            await viewModel.InitializeAsync(CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(viewModel.IsReady, Is.True);
                Assert.That(viewModel.HasStartupError, Is.False);
                Assert.That(viewModel.StatusText, Is.EqualTo("Lista"));
                Assert.That(File.Exists(_outboxPath), Is.False);
                Assert.That(
                    viewModel.Messages,
                    Has.Some.Matches<ConversationMessage>(message =>
                        !message.IsUser
                        && message.Body.Contains(
                            "durable_retry_unreadable",
                            StringComparison.Ordinal)));
            });
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", previousDataRoot);
        }
    }

    private static RoutedOperation CreateRoutedOperation(string title) =>
        new(
            "note.create",
            new JsonObject
            {
                ["title"] = title,
                ["content"] = "leche y pan",
            });

    private static RetryableOperationRegistry AssertQuarantined(
        string path,
        byte[] expectedContent)
    {
        var registry = new RetryableOperationRegistry(path);
        string? quarantinePath = registry.UnreadableOutboxPath;

        Assert.Multiple(() =>
        {
            Assert.That(quarantinePath, Is.Not.Null);
            Assert.That(quarantinePath, Is.Not.EqualTo(path));
            Assert.That(File.Exists(path), Is.False);
            Assert.That(File.Exists(quarantinePath), Is.True);
            Assert.That(File.ReadAllBytes(quarantinePath!), Is.EqualTo(expectedContent));
            Assert.That(registry.SnapshotPendingOperations(), Is.Empty);
        });

        return registry;
    }

    private static void FlipFirstByteAfterMarker(byte[] content, string marker)
    {
        byte[] markerBytes = Encoding.UTF8.GetBytes(marker);
        int markerIndex = content.AsSpan().IndexOf(markerBytes);
        Assert.That(markerIndex, Is.GreaterThanOrEqualTo(0), $"Marker not found: {marker}");
        content[markerIndex + markerBytes.Length] ^= 0x01;
    }

    private static void FlipHexNibbleAfterMarker(byte[] content, string marker)
    {
        byte[] markerBytes = Encoding.UTF8.GetBytes(marker);
        int markerIndex = content.AsSpan().IndexOf(markerBytes);
        Assert.That(markerIndex, Is.GreaterThanOrEqualTo(0), $"Marker not found: {marker}");
        int nibbleIndex = markerIndex + markerBytes.Length;
        content[nibbleIndex] = content[nibbleIndex] switch
        {
            >= (byte)'0' and <= (byte)'9' => (byte)(content[nibbleIndex] ^ 0x01),
            (byte)'a' or (byte)'c' or (byte)'d' => (byte)(content[nibbleIndex] ^ 0x02),
            (byte)'b' or (byte)'e' or (byte)'f' => (byte)(content[nibbleIndex] ^ 0x04),
            _ => throw new AssertionException("The selected UUID byte is not a lowercase hex nibble."),
        };
    }
}
