using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

[TestFixture]
public sealed class ConfirmationModeTests
{
    [Test]
    public async Task NormalModeLetsShutdownThroughAndChallengesDeleteOnTheSamePath()
    {
        var shutdown = new CountingHandler(
            "system.power",
            ProductCatalog.ToPolicyRisk(ProductCatalog.GetRequired("system.power").Risk));
        var delete = new CountingHandler(
            "system.recyclebin.empty",
            ProductCatalog.ToPolicyRisk(ProductCatalog.GetRequired("system.recyclebin.empty").Risk));
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry([shutdown, delete]),
            journal,
            new MissionEngineOptions { ConfirmationMode = () => ConfirmationMode.Normal });

        OperationResponse power = await engine.ExecuteAsync(
            Request("system.power", "{\"action\":\"shutdown\"}"),
            CancellationToken.None);
        OperationResponse recycle = await engine.ExecuteAsync(
            Request("system.recyclebin.empty", "{}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(power.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(power.Verified, Is.True);
            Assert.That(power.ErrorCode, Is.Null);
            Assert.That(shutdown.ExecutionCount, Is.EqualTo(1));
            Assert.That(recycle.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(recycle.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(recycle.Verified, Is.False);
            Assert.That(delete.ExecutionCount, Is.Zero);
        });
    }

    [Test]
    public async Task BypassSkipsTheChallengeOnTheSamePathAndStillRefusesUnverifiedSuccess()
    {
        ConfirmationMode mode = ConfirmationMode.Bypass;
        var delete = new CountingHandler(
            "system.recyclebin.empty",
            ProductCatalog.ToPolicyRisk(ProductCatalog.GetRequired("system.recyclebin.empty").Risk));
        var unverified = new UnverifiedHandler();
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry([delete, unverified]),
            journal,
            new MissionEngineOptions { ConfirmationMode = () => mode });

        OperationResponse recycle = await engine.ExecuteAsync(
            Request("system.recyclebin.empty", "{}"),
            CancellationToken.None);
        OperationResponse denied = await engine.ExecuteAsync(
            Request("note.create", "{\"title\":\"x\",\"content\":\"y\"}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(recycle.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(recycle.Verified, Is.True);
            Assert.That(delete.ExecutionCount, Is.EqualTo(1));
            Assert.That(denied.Status, Is.Not.EqualTo(OperationStatuses.Completed));
            Assert.That(denied.Verified, Is.False);
            Assert.That(denied.ErrorCode, Is.EqualTo("verification_failed"));
            Assert.That(engine.LastHonestyCorrection, Is.Not.Null);
        });
    }

    [Test]
    public async Task BypassStillDeniesForbiddenAndDoesNotRunUnsolicitedEffects()
    {
        var forbidden = new CountingHandler("note.create", OperationRisk.Forbidden);
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry([forbidden]),
            journal,
            new MissionEngineOptions { ConfirmationMode = () => ConfirmationMode.Bypass });

        OperationResponse response = await engine.ExecuteAsync(
            Request("note.create", "{}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Rejected));
            Assert.That(response.ErrorCode, Is.EqualTo("operation_forbidden"));
            Assert.That(forbidden.ExecutionCount, Is.Zero);
        });
    }

    [Test]
    public void StoreRoundTripsBypassUntilTurnedOff()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-confirmation-mode-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            Assert.That(ConfirmationModeStore.Read(root), Is.EqualTo(ConfirmationMode.Normal));
            ConfirmationModeStore.Write(root, ConfirmationMode.Bypass);
            Assert.That(ConfirmationModeStore.Read(root), Is.EqualTo(ConfirmationMode.Bypass));
            ConfirmationModeStore.Write(root, ConfirmationMode.Normal);
            Assert.That(ConfirmationModeStore.Read(root), Is.EqualTo(ConfirmationMode.Normal));
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    private static OperationRequest Request(string operation, string json) => new(
        ProtocolTypes.OperationRequest,
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        operation,
        JsonDocument.Parse(json).RootElement.Clone());

    private sealed class CountingHandler(string name, OperationRisk risk) : IOperationHandler
    {
        public int ExecutionCount { get; private set; }

        public OperationDefinition Definition { get; } = new(name, risk, "Test operation.");

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ExecutionCount++;
            return ValueTask.FromResult(OperationOutcome.Success());
        }
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
}
