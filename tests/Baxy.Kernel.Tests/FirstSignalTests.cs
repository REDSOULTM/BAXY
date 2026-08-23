using System.Globalization;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

[TestFixture]
public sealed class FirstSignalTests
{
    [Test]
    public void PredictedFastRecognizerPathEmitsNoEarlySignal()
    {
        Assert.That(FirstSignal.ShouldEmitEarly(FirstSignal.PathRecognizer), Is.False);
        Assert.That(
            FirstSignal.ShouldEmitEarly(FirstSignal.PathClosedConversation),
            Is.False);
    }

    [Test]
    public void PredictedSlowModelPathEmitsEarlySignal()
    {
        Assert.That(FirstSignal.ShouldEmitEarly(FirstSignal.PathModel), Is.True);
        Assert.That(FirstSignal.ShouldEmitEarly(FirstSignal.PathRecognizer, 3), Is.True);
    }

    [Test]
    public void FormulatedProgressIsNotAStallAndVariesByTurn()
    {
        const string spanish = "Explicame en dos frases que es la fotosintesis.";
        const string english = "Tell me something odd about walnut trees.";
        string first = FirstSignal.FormulateProgress(spanish);
        string second = FirstSignal.FormulateProgress(english);

        Assert.Multiple(() =>
        {
            Assert.That(first, Is.Not.EqualTo(second));
            Assert.That(first, Does.Not.Contain("un momento").IgnoreCase);
            Assert.That(second, Does.Not.Contain("one moment").IgnoreCase);
            Assert.That(first, Does.Not.Match("(?i)^\\s*listo\\b"));
            Assert.That(second, Does.Not.Match("(?i)^\\s*listo\\b"));
            Assert.That(first, Does.Contain("Sigo"));
            Assert.That(second, Does.Contain("Still working"));
        });
    }

    [Test]
    public void MilestoneFiresOnlyAfterAGapStrictlyOverThreeSeconds()
    {
        DateTimeOffset started = DateTimeOffset.Parse(
            "2026-08-23T12:00:00Z",
            CultureInfo.InvariantCulture,
            DateTimeStyles.AssumeUniversal);
        Assert.That(
            FirstSignal.ShouldEmitMilestone(started, started.AddSeconds(3)),
            Is.False);
        Assert.That(
            FirstSignal.ShouldEmitMilestone(
                started,
                started.AddSeconds(3.01)),
            Is.True);
        Assert.That(
            FirstSignal.ShouldEmitMilestone(null, started.AddSeconds(10)),
            Is.False);
        Assert.That(
            FirstSignal.MilestoneDueSeconds,
            Is.EqualTo(FirstSignal.SilenceBudgetSeconds + 0.01));
        Assert.That(
            FirstSignal.ShouldEmitMilestone(
                started,
                started.AddSeconds(FirstSignal.MilestoneDueSeconds)),
            Is.True);
        Assert.That(
            FirstSignal.MilestoneDueDelay,
            Is.LessThan(TimeSpan.FromSeconds(4)));

        string spanish = FirstSignal.FormulateProgress(
            "Abre Steam y ve a la biblioteca",
            FirstSignal.KindMilestone,
            2,
            3);
        string english = FirstSignal.FormulateProgress(
            "Open Steam and go to the library",
            FirstSignal.KindMilestone,
            2,
            3);
        Assert.That(spanish, Is.Not.EqualTo(english));
        Assert.That(spanish, Does.Not.Match("(?i)^\\s*listo\\b"));
        Assert.That(english, Does.Not.Match("(?i)^\\s*listo\\b"));
    }

    [Test]
    public async Task VerificationDenialReplacesTheInProgressSignal()
    {
        string inProgress = FirstSignal.FormulateProgress("Silencia el audio.");
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
        string visible = FirstSignal.VisibleAfterVerification(
            inProgress,
            response.HonestyCorrection!.Correction);

        Assert.Multiple(() =>
        {
            Assert.That(response.CauseCode, Is.EqualTo("honesty_self_correction").Or.Null);
            Assert.That(visible, Is.EqualTo(response.HonestyCorrection.Correction));
            Assert.That(visible, Is.Not.EqualTo(inProgress));
            Assert.That(visible, Does.Not.Match("(?i)^\\s*listo\\b"));
            Assert.That(response.HonestyCorrection.Claim, Does.Not.Contain("Listo"));
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
}
