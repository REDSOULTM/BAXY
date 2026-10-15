using System.Diagnostics;
using System.Reflection;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Audio;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// cu-v3 estab (reintentos-sesion). Within a session a pending entry keeps its
/// identity: the retry of an uncertain or unconfirmed invocation must never run it
/// twice. The session resolves the entry once it says its answer
/// (<see cref="MindPlanSession"/> marks an uncertain effect of a step without risk
/// confirmation resolved), so the same request in a later turn is a new invocation
/// that runs again. Across sessions, the start retires only what a computer-use
/// mission left (hallazgo 12: the Fotos mission and its click «Imagen»); the outbox
/// keeps every other identity, so a late retry never repeats an effect.
/// </summary>
[TestFixture]
public sealed class RetryIdentityNewRequestTests
{
    private const string EndpointHash =
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

    private string _root = null!;
    private string _outboxPath = null!;

    [SetUp]
    public void SetUp()
    {
        _root = PrivateDataRootTestSupport.NewPath("retry-new-request");
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
    public async Task SameRequestAfterTheSessionResolvedItsUncertainAnswerRunsAgainAndVerifies()
    {
        var provider = new FirstSetIgnoredAudioProvider();
        using var journal = new InMemoryInvocationJournal();
        using var engine = CreateEngine(provider, journal);
        var registry = new RetryableOperationRegistry(_outboxPath);
        RoutedOperation routed = VolumeTo(40);

        PreparedOperation first = registry.GetOrAdd(routed);
        OperationResponse uncertain = await engine.ExecuteAsync(first.CreateRequest(), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(uncertain.EffectMayHaveOccurred, Is.True);
            Assert.That(MainWindowViewModel.ShouldRetainRetryIdentity(uncertain), Is.True);
        });

        // What MindPlanSession does with an uncertain effect of a step that needs no
        // risk confirmation: said once, a terminal answer, its entry resolved.
        registry.MarkResolved(first);
        PreparedOperation second = registry.GetOrAdd(routed);
        OperationResponse answered = await engine.ExecuteAsync(second.CreateRequest(), CancellationToken.None);

        PreparedOperation[] pending = registry.SnapshotPendingOperations().ToArray();
        Assert.Multiple(() =>
        {
            Assert.That(second.InvocationId, Is.Not.EqualTo(first.InvocationId));
            Assert.That(second.MissionId, Is.Not.EqualTo(first.MissionId));
            Assert.That(provider.VolumeCalls, Is.EqualTo(2));
            Assert.That(answered.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(answered.Verified, Is.True);
            Assert.That(answered.InvocationId, Is.EqualTo(second.InvocationId));
            Assert.That(pending, Has.Length.EqualTo(1));
            Assert.That(pending[0], Is.SameAs(second));
        });

        registry.MarkResolved(second);
        Assert.That(new RetryableOperationRegistry(_outboxPath).SnapshotPendingOperations(), Is.Empty);
    }

    [Test]
    public async Task RetryOfTheHeldInvocationKeepsItsIdentityAndIsNeverRunTwice()
    {
        var provider = new FirstSetIgnoredAudioProvider();
        using var journal = new InMemoryInvocationJournal();
        using var engine = CreateEngine(provider, journal);
        var registry = new RetryableOperationRegistry(_outboxPath);
        PreparedOperation held = registry.GetOrAdd(VolumeTo(40));
        OperationRequest firstRequest = held.CreateRequest();
        OperationResponse uncertain = await engine.ExecuteAsync(firstRequest, CancellationToken.None);

        OperationRequest retryRequest = held.CreateRequest();
        OperationResponse replayed = await engine.ExecuteAsync(retryRequest, CancellationToken.None);
        PreparedOperation recovered = new RetryableOperationRegistry(_outboxPath)
            .SnapshotPendingOperations()
            .Single();

        Assert.Multiple(() =>
        {
            Assert.That(retryRequest.RequestId, Is.Not.EqualTo(firstRequest.RequestId));
            Assert.That(retryRequest.InvocationId, Is.EqualTo(firstRequest.InvocationId));
            Assert.That(provider.VolumeCalls, Is.EqualTo(1));
            Assert.That(replayed.EffectMayHaveOccurred, Is.EqualTo(uncertain.EffectMayHaveOccurred));
            Assert.That(recovered.InvocationId, Is.EqualTo(held.InvocationId));
            Assert.That(recovered.MissionId, Is.EqualTo(held.MissionId));
        });
    }

    [Test]
    public void DifferentArgumentsLeaveTheEarlierPendingEntryInPlace()
    {
        var registry = new RetryableOperationRegistry(_outboxPath);
        PreparedOperation forty = registry.GetOrAdd(VolumeTo(40));
        PreparedOperation fifty = registry.GetOrAdd(VolumeTo(50));

        PreparedOperation[] pending = new RetryableOperationRegistry(_outboxPath)
            .SnapshotPendingOperations()
            .ToArray();
        Assert.Multiple(() =>
        {
            Assert.That(pending.Select(static operation => operation.InvocationId),
                Is.EquivalentTo(new[] { forty.InvocationId, fifty.InvocationId }));
        });
    }

    [Test]
    public void SessionStartRetiresAnEarlierMissionAndItsActsAndKeepsEveryOtherIdentity()
    {
        // The profile of the cu-v3 audit: a computer-use mission and its click left by
        // an earlier case, next to an audio change that still waits on its check, a
        // chosen note and a note whose creation may have landed.
        var previous = new RetryableOperationRegistry(_outboxPath);
        PreparedOperation mission = previous.GetOrAdd(FotosMission());
        _ = previous.GetOrAdd(ClickImagen());
        PreparedOperation audio = previous.GetOrAdd(VolumeTo(40));
        PreparedOperation selectedNote = previous.GetOrAdd(new RoutedOperation(
            "note.trash",
            new JsonObject
            {
                ["noteId"] = Guid.NewGuid().ToString("D"),
                ["expectedTitle"] = "Compras",
                ["expectedRevision"] = 1,
                ["expectedIsTrashed"] = false,
            }));
        PreparedOperation noteCreate = previous.GetOrAdd(NoteCreate());

        var start = new RetryableOperationRegistry(_outboxPath);
        start.RetireWhere(static operation => ComputerUseMission.Prepares(operation.OperationName));

        var afterRestart = new RetryableOperationRegistry(_outboxPath);
        Assert.Multiple(() =>
        {
            Assert.That(afterRestart.SnapshotPendingOperations().Select(static operation => operation.InvocationId),
                Is.EquivalentTo(new[] { audio.InvocationId, selectedNote.InvocationId, noteCreate.InvocationId }));
            Assert.That(start.SnapshotPendingOperations(), Has.Count.EqualTo(3));
            // A late retry of the note keeps its identity: the Core replays it, never creates it twice.
            Assert.That(afterRestart.GetOrAdd(NoteCreate()).InvocationId, Is.EqualTo(noteCreate.InvocationId));
            // The same mission asked in the new session is a new one.
            Assert.That(afterRestart.GetOrAdd(FotosMission()).InvocationId, Is.Not.EqualTo(mission.InvocationId));
        });
    }

    [Test]
    public void SessionStartWithNoMissionLeftLeavesTheOutboxUntouched()
    {
        var previous = new RetryableOperationRegistry(_outboxPath);
        PreparedOperation audio = previous.GetOrAdd(VolumeTo(40));
        PreparedOperation noteCreate = previous.GetOrAdd(NoteCreate());
        byte[] before = File.ReadAllBytes(_outboxPath);

        new RetryableOperationRegistry(_outboxPath)
            .RetireWhere(static operation => ComputerUseMission.Prepares(operation.OperationName));

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(_outboxPath), Is.EqualTo(before));
            Assert.That(
                new RetryableOperationRegistry(_outboxPath).SnapshotPendingOperations()
                    .Select(static operation => operation.InvocationId),
                Is.EquivalentTo(new[] { audio.InvocationId, noteCreate.InvocationId }));
        });
    }

    [Test]
    public void MissionEntriesAreTheMissionAndItsPrimitivesOnly()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.Prepares(ComputerUseMission.OperationName), Is.True);
            Assert.That(ComputerUseMission.Primitives.All(ComputerUseMission.Prepares), Is.True);
            Assert.That(ComputerUseMission.Prepares(AudioOperationIds.Volume), Is.False);
            Assert.That(ComputerUseMission.Prepares("note.create"), Is.False);
            Assert.That(ComputerUseMission.Prepares("memory.remember"), Is.False);
        });
    }

    /// <summary>
    /// The wiring of the start: <see cref="MainWindowViewModel.InitializeAsync"/> of a new
    /// App session retires the mission an earlier session left and keeps the note; a
    /// core lost and recovered inside the session retires nothing of its own.
    /// </summary>
    [Test]
    [NonParallelizable]
    public async Task AppStartRetiresAnEarlierMissionAndACoreRecoveryKeepsThisSessionsEntries()
    {
        string root = PrivateDataRootTestSupport.NewPath("retry-session-start");
        string? previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", root);
        try
        {
            string outbox = Path.Combine(root, "shell", "retry-outbox.v1.json");
            var previous = new RetryableOperationRegistry(outbox);
            _ = previous.GetOrAdd(FotosMission());
            _ = previous.GetOrAdd(ClickImagen());
            PreparedOperation noteCreate = previous.GetOrAdd(NoteCreate());

            await using var viewModel = new MainWindowViewModel(
                static route => route.ResolveStandaloneOperation());
            await viewModel.InitializeAsync(CancellationToken.None);
            Assert.That(viewModel.IsReady, Is.True);
            Assert.That(PendingInvocations(outbox), Is.EquivalentTo(new[] { noteCreate.InvocationId }));

            RetryableOperationRegistry registry =
                GetPrivateField<RetryableOperationRegistry>(viewModel, "_retryableOperations");
            PreparedOperation thisSession = registry.GetOrAdd(FotosMission());

            Process lostCore = CoreProcess(viewModel);
            int lostCoreId = lostCore.Id;
            lostCore.Kill();
            var deadline = Stopwatch.StartNew();
            while (deadline.Elapsed < TimeSpan.FromSeconds(60)
                && !(viewModel.IsInputEnabled && CoreProcessOrNull(viewModel)?.Id is { } id && id != lostCoreId))
            {
                await Task.Delay(50);
            }

            await viewModel.WaitForCoreRecoveryAsync();
            Assert.Multiple(() =>
            {
                Assert.That(viewModel.IsReady, Is.True, "the core was not restarted");
                Assert.That(CoreProcess(viewModel).Id, Is.Not.EqualTo(lostCoreId));
                Assert.That(PendingInvocations(outbox),
                    Is.EquivalentTo(new[] { noteCreate.InvocationId, thisSession.InvocationId }));
                Assert.That(registry.GetOrAdd(FotosMission()), Is.SameAs(thisSession));
            });
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", previousDataRoot);
            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }

    private static RoutedOperation FotosMission() => new(
        ComputerUseMission.OperationName,
        new JsonObject
        {
            ["goal"] = "guárdala como copia en esa misma carpeta",
            ["application"] = "Fotos",
        });

    private static RoutedOperation ClickImagen() => new(
        "input.visible.click",
        new JsonObject { ["label"] = "Imagen" });

    private static RoutedOperation NoteCreate() => new(
        "note.create",
        new JsonObject { ["title"] = "Compras", ["content"] = "leche y pan" });

    private static string[] PendingInvocations(string outbox) =>
        new RetryableOperationRegistry(outbox)
            .SnapshotPendingOperations()
            .Select(static operation => operation.InvocationId)
            .ToArray();

    private static Process CoreProcess(MainWindowViewModel viewModel) =>
        CoreProcessOrNull(viewModel) ?? throw new AssertionException("The view model has no core process.");

    private static Process? CoreProcessOrNull(MainWindowViewModel viewModel)
    {
        CoreProcessClient? client = GetPrivateField<CoreProcessClient?>(viewModel, "_coreClient");
        return client is null ? null : GetPrivateField<Process?>(client, "_process");
    }

    private static T GetPrivateField<T>(object owner, string name)
    {
        FieldInfo? field = owner.GetType().GetField(name, BindingFlags.Instance | BindingFlags.NonPublic);
        Assert.That(field, Is.Not.Null, name);
        return (T)field!.GetValue(owner)!;
    }

    private static RoutedOperation VolumeTo(int level) => new(
        AudioOperationIds.Volume,
        new JsonObject { ["level"] = level });

    private static MissionEngine CreateEngine(IAudioControlProvider provider, IInvocationJournal journal) =>
        new(
            new OperationRegistry([new AudioVolumeHandler(provider)]),
            journal,
            new MissionEngineOptions { Narrator = ProductOperationNarrator.Instance });

    /// <summary>
    /// An endpoint whose first change does not land (the read after it still shows the
    /// old level) and whose later changes do: the first answer is an uncertain effect,
    /// a later real run is verified.
    /// </summary>
    private sealed class FirstSetIgnoredAudioProvider : IAudioControlProvider
    {
        private int _level = 55;

        public int VolumeCalls { get; private set; }

        public ValueTask<AudioStatusReceipt> GetStatusAsync(
            AudioStatusQuery query,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(new AudioStatusReceipt(
                query.InvocationId,
                AudioOperationIds.Status,
                AudioTargetIds.DefaultOutput,
                EndpointHash,
                new AudioEndpointState(_level, false),
                Verified: true,
                ErrorCode: null));
        }

        public ValueTask<AudioControlReceipt> SetVolumeAsync(
            AudioVolumeCommand command,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            VolumeCalls++;
            int before = _level;
            if (VolumeCalls > 1)
            {
                _level = command.Level;
            }

            return ValueTask.FromResult(new AudioControlReceipt(
                command.InvocationId,
                AudioOperationIds.Volume,
                AudioTargetIds.DefaultOutput,
                EndpointHash,
                command.Level,
                RequestedState: null,
                new AudioEndpointState(before, false),
                new AudioEndpointState(command.Level, false),
                Applied: true,
                Reconciled: false,
                Verified: true,
                ErrorCode: null));
        }

        public ValueTask<AudioControlReceipt> SetMuteAsync(
            AudioMuteCommand command,
            CancellationToken cancellationToken) =>
            throw new InvalidOperationException("Mute is not part of this case.");
    }
}
