using System.IO;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// La ambigüedad de un efecto privado debe sobrevivir al replay. Si la primera
/// ejecución dice «pudo haber ocurrido» y la repetición de la misma
/// invocationId dice implícitamente «no ocurrió», la persona recibe dos
/// verdades distintas sobre el mismo efecto y la segunda invita a repetirlo.
/// </summary>
[TestFixture]
public sealed class PrivateReplayAmbiguityTests
{
    [Test]
    public async Task TheReplayOfAnAmbiguousPrivateFailureStaysAmbiguous()
    {
        using var journal = new InMemoryInvocationJournal();
        var handler = new AmbiguousPrivateHandler();
        using var engine = new MissionEngine(
            new OperationRegistry([handler]),
            journal,
                               new MissionEngineOptions { PrivateEnvelopeAuthenticator = new AcceptingEnvelopeAuthenticator() });
        OperationRequest request = CreateMemoryRequest();

        OperationResponse first = await engine.ExecuteAsync(
            request,
            CancellationToken.None);
        string replayRequestId = Guid.NewGuid().ToString("D");
        OperationResponse replay = await engine.ExecuteAsync(
            request with { RequestId = replayRequestId },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
            Assert.That(first.EffectMayHaveOccurred, Is.True, "primera ejecución");
            Assert.That(replay.EffectMayHaveOccurred, Is.True, "replay");
            Assert.That(replay.Replayed, Is.True);
            Assert.That(replay.RequestId, Is.EqualTo(replayRequestId));
            Assert.That(replay.InvocationId, Is.EqualTo(request.InvocationId));
            Assert.That(replay.Status, Is.EqualTo(OperationStatuses.Failed));
            // La causa privada sigue sin viajar y el código sigue reducido.
            Assert.That(replay.CauseCode, Is.Null);
            Assert.That(replay.ErrorCode, Is.EqualTo("memory_operation_failed"));
        });
    }

    [Test]
    public async Task AnUnambiguousPrivateFailureStaysUnambiguousOnReplay()
    {
        using var journal = new InMemoryInvocationJournal();
        var handler = new AmbiguousPrivateHandler(ambiguous: false);
        using var engine = new MissionEngine(
            new OperationRegistry([handler]),
            journal,
                               new MissionEngineOptions { PrivateEnvelopeAuthenticator = new AcceptingEnvelopeAuthenticator() });
        OperationRequest request = CreateMemoryRequest();

        OperationResponse first = await engine.ExecuteAsync(
            request,
            CancellationToken.None);
        OperationResponse replay = await engine.ExecuteAsync(
            request with { RequestId = Guid.NewGuid().ToString("D") },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.EffectMayHaveOccurred, Is.False);
            Assert.That(replay.EffectMayHaveOccurred, Is.False);
            Assert.That(replay.Replayed, Is.True);
        });
    }

    [Test]
    public async Task AnUnlistedErrorCodeStaysReducedAcrossTheReplay()
    {
        using var journal = new InMemoryInvocationJournal();
        var handler = new AmbiguousPrivateHandler(
            errorCode: "the_private_note_alpha_was_half_written");
        using var engine = new MissionEngine(
            new OperationRegistry([handler]),
            journal,
                               new MissionEngineOptions { PrivateEnvelopeAuthenticator = new AcceptingEnvelopeAuthenticator() });
        OperationRequest request = CreateMemoryRequest();

        OperationResponse first = await engine.ExecuteAsync(
            request,
            CancellationToken.None);
        OperationResponse replay = await engine.ExecuteAsync(
            request with { RequestId = Guid.NewGuid().ToString("D") },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.ErrorCode, Is.EqualTo("memory_operation_failed"));
            Assert.That(replay.ErrorCode, Is.EqualTo("memory_operation_failed"));
            Assert.That(first.EffectMayHaveOccurred, Is.True);
            Assert.That(replay.EffectMayHaveOccurred, Is.True);
        });
    }

    [Test]
    public async Task TheAmbiguitySurvivesAFileJournalRoundTripAndAProcessRestart()
    {
        string root = Path.Combine(
            Path.GetTempPath(),
            "baxy-private-replay-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        string journalPath = Path.Combine(root, "journal.jsonl");
        byte[] key = new byte[JournalHmacAuthenticator.KeyLength];
        System.Security.Cryptography.RandomNumberGenerator.Fill(key);
        OperationRequest request = CreateMemoryRequest();
        try
        {
            OperationResponse first;
            var handler = new AmbiguousPrivateHandler();
            await using (FileInvocationJournal journal = await FileInvocationJournal
                .OpenAsync(
                    journalPath,
                    new JournalHmacAuthenticator(key),
                    CancellationToken.None))
            using (var engine = new MissionEngine(
                new OperationRegistry([handler]),
                journal,
                                    new MissionEngineOptions { PrivateEnvelopeAuthenticator = new AcceptingEnvelopeAuthenticator() }))
            {
                first = await engine.ExecuteAsync(request, CancellationToken.None);
            }

            // Segundo proceso: el journal en disco es la única memoria.
            var replayHandler = new AmbiguousPrivateHandler();
            await using (FileInvocationJournal journal = await FileInvocationJournal
                .OpenAsync(
                    journalPath,
                    new JournalHmacAuthenticator(key),
                    CancellationToken.None))
            using (var engine = new MissionEngine(
                new OperationRegistry([replayHandler]),
                journal,
                                    new MissionEngineOptions { PrivateEnvelopeAuthenticator = new AcceptingEnvelopeAuthenticator() }))
            {
                OperationResponse replay = await engine.ExecuteAsync(
                    request with { RequestId = Guid.NewGuid().ToString("D") },
                    CancellationToken.None);

                Assert.Multiple(() =>
                {
                    Assert.That(first.EffectMayHaveOccurred, Is.True);
                    Assert.That(replay.EffectMayHaveOccurred, Is.True);
                    Assert.That(replay.Replayed, Is.True);
                    Assert.That(replayHandler.ExecutionCount, Is.Zero);
                    Assert.That(replay.CauseCode, Is.Null);
                });
            }
        }
        finally
        {
            try
            {
                Directory.Delete(root, recursive: true);
            }
            catch (IOException)
            {
            }
        }
    }

    private static OperationRequest CreateMemoryRequest()
    {
        string missionId = Guid.NewGuid().ToString("D");
        string invocationId = Guid.NewGuid().ToString("D");
        string purpose = string.Concat(
            "memory.arguments.v1|memory.save|", missionId, "|", invocationId);
        string arguments = JsonSerializer.Serialize(new
        {
            version = 1,
            protection = "test-protection",
            purpose,
            ciphertext = Convert.ToBase64String("cifrado-de-prueba"u8.ToArray()),
        });
        return new OperationRequest(
            ProtocolTypes.OperationRequest,
            Guid.NewGuid().ToString("D"),
            missionId,
            invocationId,
            "memory.save",
            JsonDocument.Parse(arguments).RootElement.Clone());
    }

    private sealed class AmbiguousPrivateHandler(
        bool ambiguous = true,
        string errorCode = "memory_operation_failed") : IOperationHandler
    {
        public int ExecutionCount { get; private set; }

        public OperationDefinition Definition { get; } =
            new("memory.save", OperationRisk.Reversible, "Test private operation.");

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            ExecutionCount++;
            return ValueTask.FromResult(OperationOutcome.Failure(
                errorCode,
                effectMayHaveOccurred: ambiguous,
                causeCode: "private_detail_that_must_not_travel"));
        }
    }

    private sealed class AcceptingEnvelopeAuthenticator
        : IPrivateOperationEnvelopeAuthenticator
    {
        public bool AuthenticateArguments(OperationRequest request) => true;

        public bool AuthenticateResult(OperationRequest request, JsonElement result) =>
            true;
    }
}
