using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// Caracteriza la ventana entre «el efecto ocurrió» y «la respuesta viaja»
/// cuando el llamador cancela justo en medio.
///
/// El contrato vigente conserva dos cosas a la vez y este fixture lo fija:
/// la cancelación se propaga al llamador —no se le entrega el resultado de una
/// operación que pidió abandonar— pero el terminal ya quedó asentado en el
/// journal antes de propagarla, así que el efecto nunca se pierde y se
/// recupera exacto repitiendo el mismo <c>invocationId</c>.
/// </summary>
[TestFixture]
public sealed class MissionEngineCancellationTests
{
    [Test]
    public async Task ACancelDuringExecutionCommitsTheTerminalBeforePropagating()
    {
        using var caller = new CancellationTokenSource();
        using var journal = new InMemoryInvocationJournal();
        var handler = new CancelsCallerWhileSucceedingHandler(caller);
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest request = CreateRequest();

        Assert.That(
            async () => await engine.ExecuteAsync(request, caller.Token),
            Throws.InstanceOf<OperationCanceledException>());

        // El efecto ocurrió exactamente una vez y su terminal quedó asentado:
        // una cancelación no puede dejar el journal sin la verdad.
        CompletedInvocation? completed = await journal.FindCompletedAsync(
            request.InvocationId,
            CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
            Assert.That(completed, Is.Not.Null);
            Assert.That(
                completed!.Response.Status,
                Is.EqualTo(OperationStatuses.Completed));
            Assert.That(completed.Response.ErrorCode, Is.Null);
        });
    }

    [Test]
    public async Task TheCancelledCallerRecoversTheExactTerminalByReplay()
    {
        using var caller = new CancellationTokenSource();
        using var journal = new InMemoryInvocationJournal();
        var handler = new CancelsCallerWhileSucceedingHandler(caller);
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest request = CreateRequest();

        Assert.That(
            async () => await engine.ExecuteAsync(request, caller.Token),
            Throws.InstanceOf<OperationCanceledException>());

        OperationResponse replay = await engine.ExecuteAsync(
            request with { RequestId = Guid.NewGuid().ToString("D") },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            // La recuperación no vuelve a producir el efecto.
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
            Assert.That(replay.Replayed, Is.True);
            Assert.That(replay.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(replay.Verified, Is.True);
            Assert.That(replay.EffectMayHaveOccurred, Is.False);
        });
    }

    [Test]
    public async Task AnAmbiguousEffectKeepsItsAmbiguityThroughTheCancelledWindow()
    {
        using var caller = new CancellationTokenSource();
        using var journal = new InMemoryInvocationJournal();
        var handler = new CancelsCallerWhileFailingAmbiguouslyHandler(caller);
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest request = CreateRequest();

        Assert.That(
            async () => await engine.ExecuteAsync(request, caller.Token),
            Throws.InstanceOf<OperationCanceledException>());

        OperationResponse replay = await engine.ExecuteAsync(
            request with { RequestId = Guid.NewGuid().ToString("D") },
            CancellationToken.None);

        // Un efecto que pudo ocurrir nunca se convierte en éxito ni en fallo
        // limpio por haber pasado por una cancelación.
        Assert.Multiple(() =>
        {
            Assert.That(handler.ExecutionCount, Is.EqualTo(1));
            Assert.That(replay.Status, Is.EqualTo(OperationStatuses.Failed));
            Assert.That(replay.Verified, Is.False);
            Assert.That(replay.EffectMayHaveOccurred, Is.True);
            Assert.That(replay.CauseCode, Is.EqualTo("external_effect_ambiguous"));
        });
    }

    [Test]
    public async Task ACancelBeforeExecutionNeverProducesTheEffect()
    {
        using var caller = new CancellationTokenSource();
        await caller.CancelAsync();
        using var journal = new InMemoryInvocationJournal();
        var handler = new CancelsCallerWhileSucceedingHandler(caller);
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        OperationRequest request = CreateRequest();

        Assert.That(
            async () => await engine.ExecuteAsync(request, caller.Token),
            Throws.InstanceOf<OperationCanceledException>());
        Assert.Multiple(() =>
        {
            Assert.That(handler.ExecutionCount, Is.Zero);
            Assert.That(
                journal.FindCompletedAsync(
                    request.InvocationId,
                    CancellationToken.None).AsTask().Result,
                Is.Null);
        });
    }

    private static OperationRequest CreateRequest() => new(
        ProtocolTypes.OperationRequest,
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        "note.create",
        JsonDocument.Parse("{\"title\":\"prueba\"}").RootElement.Clone());

    private sealed class CancelsCallerWhileSucceedingHandler(
        CancellationTokenSource caller) : IOperationHandler
    {
        public int ExecutionCount { get; private set; }

        public OperationDefinition Definition { get; } =
            new("note.create", OperationRisk.Reversible, "Test operation.");

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ExecutionCount++;
            caller.Cancel();
            return ValueTask.FromResult(OperationOutcome.Success());
        }
    }

    private sealed class CancelsCallerWhileFailingAmbiguouslyHandler(
        CancellationTokenSource caller) : IOperationHandler
    {
        public int ExecutionCount { get; private set; }

        public OperationDefinition Definition { get; } =
            new("note.create", OperationRisk.Reversible, "Test operation.");

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ExecutionCount++;
            caller.Cancel();
            return ValueTask.FromResult(OperationOutcome.Failure(
                "note_create_failed",
                effectMayHaveOccurred: true,
                causeCode: "external_effect_ambiguous"));
        }
    }
}
