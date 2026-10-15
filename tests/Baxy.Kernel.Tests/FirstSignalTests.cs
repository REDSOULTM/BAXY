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

    // Revisión r2, hallazgo 5: since the notice stopped repeating the request (estabilidad cu-v3 2026-10-08) it varies
    // by the turn's language and step, not by its words; the name says what is checked. It is the progress label (a
    // status line, as StatusText «Trabajando»), not a reply: the reply of the turn is still composed.
    [Test]
    public void FormulatedProgressIsNotAStallAndSpeaksEachTurnsLanguage()
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

    // Estabilidad cu-v3 2026-10-08, twins of the boot_stage labels of v2-v3-04, v3-51, v3-14 and v3-39 («Sigo con abre
    // obs y agrega una escena nueva que se.» 16 times, «Sigo con search my onenote notebooks for receta.», «Still
    // working on open media player, go to the video.»): the notice never repeats the request, raw or cut.
    [TestCase("abre obs y agrega una escena nueva que se llame Pruebas", "es")]
    [TestCase("abre powerpint, haz una presentación en blanco con el título Ventas", "es")]
    [TestCase("search my onenote notebooks for receta de pan", "en")]
    [TestCase("open media player, go to the video folder and play the first one", "en")]
    [TestCase("en el explorador entrá a Documentos y creá una carpeta", null)]
    public void ProgressNoticeNeverRepeatsTheRequest(string request, string? language)
    {
        foreach ((string kind, int step, int total) in new[]
                 {
                     (FirstSignal.KindEarly, 0, 0),
                     (FirstSignal.KindMilestone, 0, 0),
                     (FirstSignal.KindMilestone, 2, 3),
                 })
        {
            string notice = FirstSignal.FormulateProgress(request, kind, step, total, language);
            string[] requestWords = request.Split(' ', StringSplitOptions.RemoveEmptyEntries)
                .Select(static word => word.Trim(',', '.').ToLowerInvariant())
                .Where(static word => word.Length > 3)
                .ToArray();
            Assert.Multiple(() =>
            {
                Assert.That(notice, Does.Not.Contain("Sigo con"));
                Assert.That(requestWords.Any(word => notice.ToLowerInvariant().Contains(word, StringComparison.Ordinal)),
                    Is.False, notice);
                Assert.That(notice, Does.Not.Match("(?i)^\\s*(listo|done)\\b"));
                Assert.That(notice, Does.EndWith("."));
            });
        }
    }

    [Test]
    public void ProgressNoticeSpeaksTheTurnsDecidedLanguage()
    {
        // v3-14: an English request read as Spanish by the word list gave «Sigo con search my onenote…»; the decided
        // language wins, and «mixed» (spanglish) falls back to the request's own reading.
        const string request = "search my onenote notebooks for receta";
        Assert.Multiple(() =>
        {
            Assert.That(FirstSignal.FormulateProgress(request, language: "en"), Is.EqualTo("Still working on it."));
            Assert.That(FirstSignal.FormulateProgress(request, language: "es"), Is.EqualTo("Sigo trabajando en ello."));
            Assert.That(
                FirstSignal.FormulateProgress(request, FirstSignal.KindMilestone, 2, 3, "en"),
                Is.EqualTo("Still working, step 2 of 3."));
            Assert.That(
                FirstSignal.FormulateProgress("abre Steam y ve a la biblioteca", FirstSignal.KindMilestone, 2, 3, "mixed"),
                Is.EqualTo("Sigo en el paso 2 de 3."));
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
