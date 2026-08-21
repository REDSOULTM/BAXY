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
    public async Task VerificationDenialCorrectsWithoutANewUserPromptAndLeavesATrace()
    {
        const string inProgress = "Entendiendo tu petición";
        Assert.That(inProgress, Does.Not.Contain("Listo"));
        Assert.That(inProgress, Does.Not.Contain("completé"));

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

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.Not.EqualTo(OperationStatuses.Completed));
            Assert.That(response.Verified, Is.False);
            Assert.That(response.ErrorCode, Is.EqualTo("verification_failed"));
            Assert.That(response.Message, Does.Not.Match("(?i)^\\s*listo\\b"));
            Assert.That(engine.LastHonestyCorrection, Is.Not.Null);
            Assert.That(engine.LastHonestyCorrection!.Claim, Is.EqualTo("in_progress_non_asserting"));
            Assert.That(engine.LastHonestyCorrection.Verification, Is.EqualTo("denied"));
            Assert.That(engine.LastHonestyCorrection.Correction, Is.EqualTo(response.Message));
            Assert.That(engine.LastHonestyCorrection.Correction, Is.Not.Empty);
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
