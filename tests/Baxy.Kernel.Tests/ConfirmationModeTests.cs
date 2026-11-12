using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

[TestFixture]
public sealed class ConfirmationModeTests
{
    // Owner's decision (2026-10-16): sending to the Recycle Bin, or a note or task to its trash, asks for the yes.
    [TestCase("filesystem.known.trash.named")]
    [TestCase("note.trash")]
    [TestCase("task.delete")]
    public void SendingToATrashAsksInNormalMode(string operation) =>
        Assert.That(
            RiskPolicy.Evaluate(ProductCatalog.ToPolicyRisk(ProductCatalog.GetRequired(operation).Risk), ConfirmationMode.Normal, operation),
            Is.EqualTo(PolicyDecision.RequireConfirmation));

    // Encargo L3: «apágalo» about an open application went to system.power shutdown, the model sure of it (rival at 0.02).
    // In normal mode what ends the person's session asks, bound to the invocation; what keeps it all open goes directly;
    // arguments that name neither ask. Bypass asks nothing (orden del dueño, 2026-11-07, REV7: «Bypass es literalmente un
    // modo sin permisos»). Without arguments (what the catalog tells the mind) it depends on them, so it does not ask
    // (MindSidecarClientTests, the prefix does not move).
    [TestCase(ConfirmationMode.Normal, """{"action":"shutdown"}""", PolicyDecision.RequireConfirmation)]
    [TestCase(ConfirmationMode.Bypass, """{"action":"shutdown"}""", PolicyDecision.Allow)]
    [TestCase(ConfirmationMode.Normal, """{"action":"restart"}""", PolicyDecision.RequireConfirmation)]
    [TestCase(ConfirmationMode.Bypass, """{"action":"restart"}""", PolicyDecision.Allow)]
    [TestCase(ConfirmationMode.Normal, """{"action":"signout"}""", PolicyDecision.RequireConfirmation)]
    [TestCase(ConfirmationMode.Bypass, """{"action":"signout"}""", PolicyDecision.Allow)]
    [TestCase(ConfirmationMode.Normal, """{"action":"hibernate"}""", PolicyDecision.RequireConfirmation)]
    [TestCase(ConfirmationMode.Normal, """{"action":7}""", PolicyDecision.RequireConfirmation)]
    [TestCase(ConfirmationMode.Normal, "{}", PolicyDecision.RequireConfirmation)]
    [TestCase(ConfirmationMode.Bypass, """{"action":"hibernate"}""", PolicyDecision.Allow)]
    [TestCase(ConfirmationMode.Bypass, "{}", PolicyDecision.Allow)]
    [TestCase(ConfirmationMode.Normal, """{"action":"lock"}""", PolicyDecision.Allow)]
    [TestCase(ConfirmationMode.Bypass, """{"action":"lock"}""", PolicyDecision.Allow)]
    [TestCase(ConfirmationMode.Normal, """{"action":"sleep"}""", PolicyDecision.Allow)]
    [TestCase(ConfirmationMode.Bypass, """{"action":"sleep"}""", PolicyDecision.Allow)]
    public void WhatEndsThePersonsSessionAsksInNormalModeOnly(ConfirmationMode mode, string arguments, PolicyDecision expected)
    {
        using JsonDocument given = JsonDocument.Parse(arguments);
        OperationRisk risk = ProductCatalog.ToPolicyRisk(ProductCatalog.GetRequired("system.power").Risk);

        Assert.Multiple(() =>
        {
            Assert.That(RiskPolicy.Evaluate(risk, mode, "system.power", given.RootElement), Is.EqualTo(expected));
            Assert.That(RiskPolicy.Evaluate(risk, mode, "system.power"), Is.EqualTo(PolicyDecision.Allow));
        });
    }

    // Orden del dueño (REV7, 2026-11-07: «Bypass es literalmente un modo sin permisos. No te tiene que preguntar nada en
    // Bypass»): ending a process asks in normal mode only (work_loss), as it did before INT5; in Bypass it runs unasked,
    // like asking a window or an application to close. Without arguments (the catalog) nothing changes.
    [TestCase(ConfirmationMode.Normal, "system.process.terminate.named", """{"name":"tintero.exe"}""", PolicyDecision.RequireConfirmation)]
    [TestCase(ConfirmationMode.Bypass, "system.process.terminate.named", """{"name":"tintero.exe"}""", PolicyDecision.Allow)]
    [TestCase(ConfirmationMode.Bypass, "system.process.terminate.named", "{}", PolicyDecision.Allow)]
    [TestCase(ConfirmationMode.Bypass, "app.close", """{"appId":"Tintero"}""", PolicyDecision.Allow)]
    [TestCase(ConfirmationMode.Bypass, "app.close", """{"windowId":"win_1"}""", PolicyDecision.Allow)]
    [TestCase(ConfirmationMode.Bypass, "window.close.all", "{}", PolicyDecision.Allow)]
    [TestCase(ConfirmationMode.Bypass, "baxy.exit", "{}", PolicyDecision.Allow)]
    [TestCase(ConfirmationMode.Normal, "app.close", """{"appId":"Tintero"}""", PolicyDecision.RequireConfirmation)]
    public void EndingAProcessAsksInNormalModeOnlyAndClosingAWindowDoesNotInBypass(
        ConfirmationMode mode, string operation, string arguments, PolicyDecision expected)
    {
        using JsonDocument given = JsonDocument.Parse(arguments);
        OperationRisk risk = ProductCatalog.ToPolicyRisk(ProductCatalog.GetRequired(operation).Risk);

        Assert.Multiple(() =>
        {
            Assert.That(RiskPolicy.Evaluate(risk, mode, operation, given.RootElement), Is.EqualTo(expected));
            Assert.That(
                RiskPolicy.Evaluate(risk, ConfirmationMode.Bypass, operation),
                Is.EqualTo(PolicyDecision.Allow));
        });
    }

    [Test]
    public async Task InNormalModeEndingAProcessWaitsForTheYesAndRunsOnceWithIt()
    {
        var terminate = new CountingHandler(
            "system.process.terminate.named",
            ProductCatalog.ToPolicyRisk(ProductCatalog.GetRequired("system.process.terminate.named").Risk));
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry([terminate]),
            journal,
            new MissionEngineOptions { ConfirmationMode = () => ConfirmationMode.Normal });
        OperationRequest end = Request("system.process.terminate.named", "{\"name\":\"tintero.exe\"}");

        OperationResponse asked = await engine.ExecuteAsync(end, CancellationToken.None);
        int beforeTheYes = terminate.ExecutionCount;
        OperationResponse confirmed = await engine.ExecuteAsync(
            end with { ConfirmationToken = asked.Result!.Value.GetProperty("token").GetString() },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(asked.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(beforeTheYes, Is.Zero);
            Assert.That(confirmed.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(terminate.ExecutionCount, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task InBypassEndingAProcessRunsOnceWithoutAsking()
    {
        var terminate = new CountingHandler(
            "system.process.terminate.named",
            ProductCatalog.ToPolicyRisk(ProductCatalog.GetRequired("system.process.terminate.named").Risk));
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry([terminate]),
            journal,
            new MissionEngineOptions { ConfirmationMode = () => ConfirmationMode.Bypass });

        OperationResponse ended = await engine.ExecuteAsync(
            Request("system.process.terminate.named", "{\"name\":\"tintero.exe\"}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(ended.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(ended.ErrorCode, Is.Null);
            Assert.That(terminate.ExecutionCount, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task InNormalModeAShutdownWaitsForTheYesAndRunsOnceWithIt()
    {
        var power = new CountingHandler(
            "system.power",
            ProductCatalog.ToPolicyRisk(ProductCatalog.GetRequired("system.power").Risk));
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry([power]),
            journal,
            new MissionEngineOptions { ConfirmationMode = () => ConfirmationMode.Normal });
        OperationRequest shutdown = Request("system.power", "{\"action\":\"shutdown\"}");

        OperationResponse asked = await engine.ExecuteAsync(shutdown, CancellationToken.None);
        int beforeTheYes = power.ExecutionCount;
        OperationResponse confirmed = await engine.ExecuteAsync(
            shutdown with { ConfirmationToken = asked.Result!.Value.GetProperty("token").GetString() },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(asked.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(beforeTheYes, Is.Zero);
            Assert.That(confirmed.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(power.ExecutionCount, Is.EqualTo(1));
        });
    }

    [TestCase("shutdown")]
    [TestCase("restart")]
    [TestCase("signout")]
    public async Task InBypassWhatEndsTheSessionRunsOnceWithoutAsking(string action)
    {
        var power = new CountingHandler(
            "system.power",
            ProductCatalog.ToPolicyRisk(ProductCatalog.GetRequired("system.power").Risk));
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry([power]),
            journal,
            new MissionEngineOptions { ConfirmationMode = () => ConfirmationMode.Bypass });

        OperationResponse ended = await engine.ExecuteAsync(
            Request("system.power", $"{{\"action\":\"{action}\"}}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(ended.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(ended.ErrorCode, Is.Null);
            Assert.That(power.ExecutionCount, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task NormalModeLetsALockThroughAndChallengesDeleteOnTheSamePath()
    {
        var power = new CountingHandler(
            "system.power",
            ProductCatalog.ToPolicyRisk(ProductCatalog.GetRequired("system.power").Risk));
        var delete = new CountingHandler(
            "system.recyclebin.empty",
            ProductCatalog.ToPolicyRisk(ProductCatalog.GetRequired("system.recyclebin.empty").Risk));
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry([power, delete]),
            journal,
            new MissionEngineOptions { ConfirmationMode = () => ConfirmationMode.Normal });

        OperationResponse locked = await engine.ExecuteAsync(
            Request("system.power", "{\"action\":\"lock\"}"),
            CancellationToken.None);
        OperationResponse recycle = await engine.ExecuteAsync(
            Request("system.recyclebin.empty", "{}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(locked.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(locked.Verified, Is.True);
            Assert.That(locked.ErrorCode, Is.Null);
            Assert.That(power.ExecutionCount, Is.EqualTo(1));
            Assert.That(recycle.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(recycle.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(recycle.Verified, Is.False);
            Assert.That(delete.ExecutionCount, Is.Zero);
        });
    }

    [Test]
    public async Task ClosingEveryTabIsChallengedOnItsOwnArgumentWhileOneTabCloses()
    {
        var control = new CountingHandler(
            "browser.control",
            ProductCatalog.ToPolicyRisk(ProductCatalog.GetRequired("browser.control").Risk));
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry([control]),
            journal,
            new MissionEngineOptions { ConfirmationMode = () => ConfirmationMode.Normal });

        OperationResponse one = await engine.ExecuteAsync(
            Request("browser.control", "{\"action\":\"close\"}"),
            CancellationToken.None);
        OperationResponse all = await engine.ExecuteAsync(
            Request("browser.control", "{\"action\":\"close_all\"}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(one.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(all.Status, Is.EqualTo(OperationStatuses.Pending));
            Assert.That(all.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(control.ExecutionCount, Is.EqualTo(1), "only the single close ran");
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

    [Test]
    public void NoProfileFileIsNormalWhateverTheEnvironmentSays()
    {
        // Revisión U, H5: bypass is switched on only by the interface's gesture, which writes the profile's file; an
        // environment variable no longer switches it on.
        string root = Path.Combine(Path.GetTempPath(), "baxy-confirmation-env-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        string? previous = Environment.GetEnvironmentVariable("BAXY_CONFIRMATION_MODE");
        Environment.SetEnvironmentVariable("BAXY_CONFIRMATION_MODE", "bypass");
        try
        {
            Assert.That(ConfirmationModeStore.Read(root), Is.EqualTo(ConfirmationMode.Normal));
            Assert.That(ConfirmationModeStore.Read(null), Is.EqualTo(ConfirmationMode.Normal));
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_CONFIRMATION_MODE", previous);
            Directory.Delete(root, recursive: true);
        }
    }

    [Test]
    public void PresentationStoreRoundTripsTheAccessibleModeAndReadsAnythingElseAsNormal()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-presentation-mode-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            Assert.That(PresentationModeStore.ReadAccessible(root), Is.False);
            PresentationModeStore.WriteAccessible(root, true);
            Assert.That(PresentationModeStore.ReadAccessible(root), Is.True);
            PresentationModeStore.WriteAccessible(root, false);
            Assert.That(PresentationModeStore.ReadAccessible(root), Is.False);
            // Contracase: the retired modes of the old interface are not the accessible presentation.
            File.WriteAllText(Path.Combine(root, PresentationModeStore.FileName), "no_vidente");
            Assert.That(PresentationModeStore.ReadAccessible(root), Is.False);
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
            // An effect the provider could not verify: never a completed claim.
            return ValueTask.FromResult(new OperationOutcome(true, false, null, null));
        }
    }
}
