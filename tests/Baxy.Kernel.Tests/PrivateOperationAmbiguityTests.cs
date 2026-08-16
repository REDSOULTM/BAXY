using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// La frontera de operaciones privadas reduce todo fallo a un código de una
/// lista cerrada para que un detalle privado no se escape por el error. Esa
/// reducción no puede llevarse por delante la ambigüedad del efecto: decirle a
/// la persona que «no pasó nada» cuando pudo pasar es peor que decir que no se
/// sabe, porque invita a repetir la operación.
///
/// <see cref="OperationOutcome.EffectMayHaveOccurred"/> es un booleano y no
/// transporta contenido, así que se conserva. <c>CauseCode</c> es texto libre
/// del handler y se sigue descartando por privacidad.
/// </summary>
[TestFixture]
public sealed class PrivateOperationAmbiguityTests
{
    [Test]
    public async Task AnAmbiguousPrivateFailureKeepsItsAmbiguity()
    {
        using var journal = new InMemoryInvocationJournal();
        var handler = new AmbiguousMemoryHandler(retryable: false);
        using var engine = new MissionEngine(
            new OperationRegistry([handler]),
            journal,
            new AcceptingEnvelopeAuthenticator());

        OperationResponse response = await engine.ExecuteAsync(
            CreateMemoryRequest(),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(response.EffectMayHaveOccurred, Is.True);
            // El código se reduce a la lista cerrada y la causa libre no viaja.
            Assert.That(response.ErrorCode, Is.EqualTo("memory_operation_failed"));
            Assert.That(response.CauseCode, Is.Null);
        });
    }

    [Test]
    public async Task AnAmbiguousRetryablePrivateFailureAlsoKeepsIt()
    {
        using var journal = new InMemoryInvocationJournal();
        var handler = new AmbiguousMemoryHandler(retryable: true);
        using var engine = new MissionEngine(
            new OperationRegistry([handler]),
            journal,
            new AcceptingEnvelopeAuthenticator());

        OperationResponse response = await engine.ExecuteAsync(
            CreateMemoryRequest(),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(response.EffectMayHaveOccurred, Is.True);
            Assert.That(response.CauseCode, Is.Null);
        });
    }

    [Test]
    public async Task AnUnambiguousPrivateFailureStaysUnambiguous()
    {
        using var journal = new InMemoryInvocationJournal();
        var handler = new AmbiguousMemoryHandler(retryable: false, ambiguous: false);
        using var engine = new MissionEngine(
            new OperationRegistry([handler]),
            journal,
            new AcceptingEnvelopeAuthenticator());

        OperationResponse response = await engine.ExecuteAsync(
            CreateMemoryRequest(),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(response.EffectMayHaveOccurred, Is.False);
        });
    }

    [Test]
    public async Task APrivateFailureNeverLeaksAnUnlistedErrorCode()
    {
        using var journal = new InMemoryInvocationJournal();
        var handler = new AmbiguousMemoryHandler(
            retryable: false,
            ambiguous: true,
            errorCode: "the_secret_note_titled_alpha_was_half_written");
        using var engine = new MissionEngine(
            new OperationRegistry([handler]),
            journal,
            new AcceptingEnvelopeAuthenticator());

        OperationResponse response = await engine.ExecuteAsync(
            CreateMemoryRequest(),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.ErrorCode, Is.EqualTo("memory_operation_failed"));
            Assert.That(response.EffectMayHaveOccurred, Is.True);
        });
    }

    private static OperationRequest CreateMemoryRequest()
    {
        string requestId = Guid.NewGuid().ToString("D");
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
            requestId,
            missionId,
            invocationId,
            "memory.save",
            JsonDocument.Parse(arguments).RootElement.Clone());
    }

    private sealed class AmbiguousMemoryHandler(
        bool retryable,
        bool ambiguous = true,
        string errorCode = "memory_operation_failed") : IOperationHandler
    {
        public OperationDefinition Definition { get; } =
            new("memory.save", OperationRisk.Reversible, "Test private operation.");

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken) =>
            ValueTask.FromResult(retryable
                ? OperationOutcome.RetryableFailure(
                    errorCode,
                    effectMayHaveOccurred: ambiguous,
                    causeCode: "private_detail_that_must_not_travel")
                : OperationOutcome.Failure(
                    errorCode,
                    effectMayHaveOccurred: ambiguous,
                    causeCode: "private_detail_that_must_not_travel"));
    }

    private sealed class AcceptingEnvelopeAuthenticator
        : IPrivateOperationEnvelopeAuthenticator
    {
        public bool AuthenticateArguments(OperationRequest request) => true;

        public bool AuthenticateResult(OperationRequest request, JsonElement result) =>
            true;
    }
}
