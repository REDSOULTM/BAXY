using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

[TestFixture]
public sealed class HonestyCorrectionTests
{
    [Test]
    public void CorrectTakesTheShippedInProgressSignalAndTheDeniedVerification()
    {
        const string denial = "verification_failed";
        const string correction = "No pude completar la petición solicitada.";

        HonestyCorrectionTrace trace = HonestyCorrection.Correct(
            HonestyCorrection.NonAssertingInProgress,
            denial,
            correction);

        Assert.Multiple(() =>
        {
            Assert.That(
                trace.Claim,
                Is.EqualTo(HonestyCorrection.NonAssertingInProgress));
            Assert.That(trace.Claim, Does.StartWith("Estoy"));
            Assert.That(trace.Claim, Does.Not.Contain("Listo"));
            Assert.That(trace.Claim, Does.Not.Contain("completé"));
            Assert.That(trace.Verification, Is.EqualTo(denial));
            Assert.That(trace.Correction, Is.EqualTo(correction));
        });
    }

    [Test]
    public async Task VerificationDenialCorrectsWithoutANewUserPromptAndJournalsTheTriple()
    {
        var handler = new UnverifiedHandler();
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        var request = new OperationRequest(
            ProtocolTypes.OperationRequest,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            "note.create",
            JsonDocument.Parse("{\"title\":\"x\",\"content\":\"y\"}").RootElement.Clone());

        OperationResponse response = await engine.ExecuteAsync(request, CancellationToken.None);
        CompletedInvocation? completed = await journal.FindCompletedAsync(
            request.InvocationId,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.Not.EqualTo(OperationStatuses.Completed));
            Assert.That(response.Verified, Is.False);
            Assert.That(response.ErrorCode, Is.EqualTo("verification_failed"));
            Assert.That(response.Message, Does.Not.Match("(?i)^\\s*listo\\b"));
            Assert.That(response.HonestyCorrection, Is.Not.Null);
            Assert.That(
                response.HonestyCorrection!.Claim,
                Is.EqualTo(HonestyCorrection.NonAssertingInProgress));
            Assert.That(
                response.HonestyCorrection.Verification,
                Is.EqualTo("verification_failed"));
            Assert.That(response.HonestyCorrection.Correction, Is.EqualTo(response.Message));
            Assert.That(engine.LastHonestyCorrection, Is.EqualTo(response.HonestyCorrection));
            Assert.That(completed, Is.Not.Null);
            Assert.That(
                completed!.Response.HonestyCorrection,
                Is.EqualTo(response.HonestyCorrection));
        });
    }

    [Test]
    public async Task VerifiedSuccessIsTheOnlyCompletedClaim()
    {
        var handler = new VerifiedHandler();
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        var request = new OperationRequest(
            ProtocolTypes.OperationRequest,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            "note.create",
            JsonDocument.Parse("{\"title\":\"x\",\"content\":\"y\"}").RootElement.Clone());

        OperationResponse response = await engine.ExecuteAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(response.Verified, Is.True);
            Assert.That(response.HonestyCorrection, Is.Null);
            Assert.That(engine.LastHonestyCorrection, Is.Null);
        });
    }

    private sealed class UnverifiedHandler : IOperationHandler
    {
        public OperationDefinition Definition { get; } =
            new("note.create", OperationRisk.Reversible, "Test operation.");

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(OperationOutcome.Unverified());
        }
    }

    private sealed class VerifiedHandler : IOperationHandler
    {
        public OperationDefinition Definition { get; } =
            new("note.create", OperationRisk.Reversible, "Test operation.");

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(OperationOutcome.Success());
        }
    }
}
