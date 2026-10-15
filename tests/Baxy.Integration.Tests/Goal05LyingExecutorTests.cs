using System.Text.Json;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.Audio;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.Notes;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class Goal05LyingExecutorTests
{
    private const string EndpointHash =
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

    [OneTimeSetUp]
    public void ResetScratchLog() => Goal05Scratch.Write("lying-provider.log", string.Empty);

    [Test]
    public async Task LyingAudioExecutorCannotMakeMissionEngineClaimSuccess()
    {
        var log = new List<string>();
        for (int round = 1; round <= 2; round++)
        {
            var provider = new LyingAudioProvider();
            using var journal = new InMemoryInvocationJournal();
            using var engine = new MissionEngine(
                new OperationRegistry([new AudioVolumeHandler(provider)]),
                journal,
                new MissionEngineOptions { Narrator = ProductOperationNarrator.Instance });
            OperationRequest request = Request(
                AudioOperationIds.Volume,
                "{\"level\":30}");

            OperationResponse response = await engine.ExecuteAsync(
                request,
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(response.Status, Is.Not.EqualTo(OperationStatuses.Completed));
                Assert.That(response.Verified, Is.False);
                Assert.That(response.EffectMayHaveOccurred, Is.True);
                Assert.That(response.Message, Does.Not.StartWith("Listo"));
                Assert.That(provider.VolumeCalls, Is.EqualTo(1));
                Assert.That(provider.StatusCalls, Is.EqualTo(1));
            });
            log.Add(
                $"round={round} status={response.Status} verified={response.Verified} "
                + $"effectMayHaveOccurred={response.EffectMayHaveOccurred} "
                + $"error={response.ErrorCode} messageStartsListo={response.Message.StartsWith("Listo", StringComparison.Ordinal)}");
        }

        Goal05Scratch.Append("lying-provider.log", string.Join(Environment.NewLine, log) + Environment.NewLine);
    }

    [Test]
    public async Task LyingAppLauncherCannotMakeMissionEngineClaimSuccess()
    {
        var log = new List<string>();
        for (int round = 1; round <= 2; round++)
        {
            var provider = new WindowsApplicationOpenProvider(
                new LyingNotepadLauncher(),
                new WindowsApplicationOpenVerifier());
            using var journal = new InMemoryInvocationJournal();
            using var engine = new MissionEngine(
                new OperationRegistry([new AppOpenHandler(provider)]),
                journal,
                new MissionEngineOptions { Narrator = ProductOperationNarrator.Instance });
            OperationRequest request = Request("app.open", "{\"appId\":\"windows.notepad\"}");

            OperationResponse response = await engine.ExecuteAsync(
                request,
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(response.Status, Is.Not.EqualTo(OperationStatuses.Completed));
                Assert.That(response.Verified, Is.False);
                Assert.That(response.Message, Does.Not.StartWith("Listo"));
            });
            log.Add(
                $"round={round} status={response.Status} verified={response.Verified} "
                + $"effectMayHaveOccurred={response.EffectMayHaveOccurred} error={response.ErrorCode}");
        }

        Goal05Scratch.Append("lying-provider.log", string.Join(Environment.NewLine, log) + Environment.NewLine);
    }

    [Test]
    public async Task LyingNoteCreateCannotMakeMissionEngineClaimSuccess()
    {
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry([new CreateNoteHandler(new LyingNoteStore())]),
            journal,
            new MissionEngineOptions { Narrator = ProductOperationNarrator.Instance });
        OperationRequest request = Request(
            "note.create",
            "{\"title\":\"Goal05\",\"content\":\"no persistido\"}");

        OperationResponse response = await engine.ExecuteAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(response.Verified, Is.False);
            Assert.That(response.EffectMayHaveOccurred, Is.True);
            Assert.That(response.ErrorCode, Is.EqualTo("verification_failed"));
            Assert.That(response.Message, Does.Not.StartWith("Listo"));
        });
    }

    // audio.app.volume.adjust (AUDIO1801) se suma a message.send: un executor que afirma «verificado»
    // sin efecto observado en la postlectura de sesión nunca completa (plan post-goal 2026-09-20, grupo B).
    [TestCase("message.send", "{\"recipientId\":\"recipient_test\",\"text\":\"hola\"}")]
    [TestCase("audio.app.volume.adjust", "{\"amount\":10,\"app\":\"spotify\",\"direction\":\"down\"}")]
    public async Task VerifiedExternalMutationWithoutObservedEffectNeverCompletes(string operation, string arguments)
    {
        using JsonDocument evidence = JsonDocument.Parse(
            $$"""{"operation":"{{operation}}","source":"lying_executor"}""");
        var handler = new ExternalCapabilityHandler(
            operation,
            new StaticExternalProvider(new ExternalCapabilityReceipt(
                operation,
                EffectObserved: false,
                Verified: true,
                evidence.RootElement.Clone(),
                ErrorCode: null)));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation(arguments),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.Verified, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("external_verification_failed"));
            Assert.That(outcome.CauseCode, Is.EqualTo("external_effect_unobserved"));
            Assert.That(
                ProductOperationNarrator.Instance.Narrate(operation, outcome),
                Does.Not.StartWith("Listo"));
        });
    }

    private static OperationRequest Request(string operation, string json) => new(
        ProtocolTypes.OperationRequest,
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        operation,
        Parse(json));

    private static OperationInvocation Invocation(string json) => new(
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Parse(json));

    private static JsonElement Parse(string json) =>
        JsonDocument.Parse(json).RootElement.Clone();

    private sealed class LyingAudioProvider : IAudioControlProvider
    {
        public int VolumeCalls { get; private set; }

        public int StatusCalls { get; private set; }

        public ValueTask<AudioStatusReceipt> GetStatusAsync(
            AudioStatusQuery query,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            StatusCalls++;
            return ValueTask.FromResult(new AudioStatusReceipt(
                query.InvocationId,
                AudioOperationIds.Status,
                AudioTargetIds.DefaultOutput,
                EndpointHash,
                new AudioEndpointState(55, false),
                Verified: true,
                ErrorCode: null));
        }

        public ValueTask<AudioControlReceipt> SetVolumeAsync(
            AudioVolumeCommand command,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            VolumeCalls++;
            return ValueTask.FromResult(new AudioControlReceipt(
                command.InvocationId,
                AudioOperationIds.Volume,
                AudioTargetIds.DefaultOutput,
                EndpointHash,
                command.Level,
                RequestedState: null,
                new AudioEndpointState(55, false),
                new AudioEndpointState(command.Level, false),
                Applied: true,
                Reconciled: false,
                Verified: true,
                ErrorCode: null));
        }

        public ValueTask<AudioControlReceipt> SetMuteAsync(
            AudioMuteCommand command,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            throw new InvalidOperationException("Mute is not part of this lying-executor case.");
        }
    }

    private sealed class LyingNotepadLauncher : IApplicationLauncher
    {
        public ValueTask<ApplicationLaunchReceipt> LaunchAsync(
            ApplicationOpenRequest request,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(new ApplicationLaunchReceipt(
                request.InvocationId,
                ApplicationIds.Notepad,
                LaunchIssued: true,
                ReusedExisting: false,
                ProcessId: int.MaxValue,
                ProcessCreationTimeUtcTicks: DateTime.UtcNow.Ticks,
                ExecutablePath: @"C:\Windows\System32\notepad.exe",
                PackageFamilyName: null,
                PackageFullName: null,
                WindowHandle: 1,
                ErrorCode: null));
        }
    }

    private sealed class StaticExternalProvider(ExternalCapabilityReceipt receipt)
        : IExternalCapabilityProvider
    {
        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation,
            JsonElement arguments,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(receipt);
        }
    }

    private sealed class LyingNoteStore : INoteStore
    {
        public NoteRecord Create(string title, string content, string? idempotencyKey = null) =>
            new(
                Guid.Parse("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
                title,
                content,
                DateTimeOffset.UtcNow,
                DateTimeOffset.UtcNow,
                TrashedAtUtc: null,
                Revision: 1);

        public NoteRecord Read(Guid id, bool includeTrashed = false) =>
            throw new NoteNotFoundException(id);

        public NoteRecord ReadExactTitle(string title) =>
            throw new NoteNotFoundException(Guid.Empty);

        public NoteRecord ReadSelected(NoteSelection selection) =>
            throw new NoteNotFoundException(selection.Id);

        public NoteRecord UpdateSelected(NoteSelection selection, string title, string content) =>
            throw new NoteNotFoundException(selection.Id);

        public IReadOnlyList<NoteRecord> List(NoteListScope scope = NoteListScope.Active) =>
            [];

        public NotePage ListPage(NoteListScope scope, int limit, int offset) =>
            new([], 0, limit, offset);

        public IReadOnlyList<NoteSummaryRecord> Search(string query, bool includeTrashed, int limit) =>
            [];

        public NoteRecord Trash(Guid id) =>
            throw new NoteNotFoundException(id);

        public NoteRecord TrashExactTitle(string title) =>
            throw new NoteNotFoundException(Guid.Empty);

        public NoteRecord TrashSelected(NoteSelection selection) =>
            throw new NoteNotFoundException(selection.Id);

        public NoteRecord Restore(Guid id) =>
            throw new NoteNotFoundException(id);

        public NoteRecord RestoreExactTitle(string title) =>
            throw new NoteNotFoundException(Guid.Empty);

        public NoteRecord RestoreSelected(NoteSelection selection) =>
            throw new NoteNotFoundException(selection.Id);
    }
}
