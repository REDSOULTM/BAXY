using System.Globalization;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// El progreso visible temprano viaja por el evento histórico
/// <c>boot_stage</c> que el lector sellado ya interpreta. Estas pruebas fijan
/// las tres propiedades que lo hacen promocionable: nunca anticipa un éxito,
/// nunca filtra estado interno y un lector antiguo no puede malinterpretarlo.
/// </summary>
[TestFixture]
public sealed class FieldProgressContractTests
{
    [TestCase("understanding", "understanding", false)]
    [TestCase("Preparando los pasos", "preparing_steps", false)]
    [TestCase("acting", "acting", true)]
    [TestCase("Ejecutando paso 2 de 3", "acting", true)]
    public void MilestoneFactsKeepActualPhaseAndOnlyCurrentExecutionCounts(
        string status, string expectedPhase, bool hasStep)
    {
        UserMessageDraft draft = MainWindowViewModel.CreateMilestoneDraft(status, 2, 3);
        JsonNode facts = JsonNode.Parse(draft.Source)!;
        Assert.That((string?)facts["phase"], Is.EqualTo(expectedPhase));
        Assert.That((int?)facts["step"], Is.EqualTo(hasStep ? 2 : null));
        Assert.That((int?)facts["totalSteps"], Is.EqualTo(hasStep ? 3 : null));
    }

    [Test]
    public async Task ADelayedMilestoneCannotPublishInAnotherTurnOrPhase()
    {
        await using var viewModel = new MainWindowViewModel();
        const string label = "Estoy revisando los detalles de tu petición.";
        Assert.That(viewModel.TryApplyMilestone(label, "t0", "understanding"), Is.False);
        viewModel.BeginTurnPresentation("Lee el archivo de prueba.", DateTimeOffset.UtcNow);
        Assert.That(viewModel.TryApplyMilestone(label, "previous-turn", "understanding"), Is.False);
        Assert.That(viewModel.TryApplyMilestone(label, "t0", "acting"), Is.False);
        Assert.That(viewModel.ProgressLabel, Is.Null);
        Assert.That(viewModel.TryApplyMilestone(label, "t0", "understanding"), Is.True);
        Assert.That(viewModel.ProgressLabel, Is.EqualTo(label));
    }

    [Test]
    public void ReadyAndIdleShowsNoIndication()
    {
        Assert.That(
            FieldBridgeContract.ResolveProgress(
                isReady: true,
                isBusy: false,
                hasStartupError: false,
                statusDescription: "BAXY disponible"),
            Is.Null);
    }

    [Test]
    public void StartupShowsAnHonestPreparingIndication()
    {
        FieldProgressNotice? notice = FieldBridgeContract.ResolveProgress(
            isReady: false,
            isBusy: false,
            hasStartupError: false,
            statusDescription: "Preparando BAXY");

        Assert.That(notice, Is.Not.Null);
        Assert.That(notice!.Stage, Is.EqualTo(FieldProgressNotice.StageStarting));
        Assert.That(notice.Label, Is.Null);
    }

    [Test]
    public void UnderstandingProgressIsTheHonestyCorrectionClaim()
    {
        FieldProgressNotice? notice = FieldBridgeContract.ResolveProgress(
            isReady: true,
            isBusy: true,
            hasStartupError: false,
            statusDescription: "understanding");

        Assert.That(notice, Is.Not.Null);
        Assert.That(notice!.Stage, Is.EqualTo(FieldProgressNotice.StageUnderstanding));
        Assert.That(notice.Label, Is.Null);
        Assert.That(
            HonestyCorrection.NonAssertingInProgress,
            Is.EqualTo(FieldProgressNotice.StageUnderstanding));
        Assert.That(
            FieldBridgeContract.Create(FieldProgressNotice.StageUnderstanding).Label,
            Is.Null);
    }

    [Test]
    public void ProgressPulsesAfterOneSecondWithoutClaimingAResult()
    {
        DateTimeOffset first = DateTimeOffset.Parse(
            "2026-08-23T12:00:00Z",
            CultureInfo.InvariantCulture,
            DateTimeStyles.AssumeUniversal);
        Assert.That(FieldBridgeContract.ProgressPulse, Is.EqualTo(TimeSpan.FromSeconds(1)));
        Assert.That(FieldBridgeContract.ShouldPulseProgress(null, first), Is.True);
        Assert.That(
            FieldBridgeContract.ShouldPulseProgress(first, first.AddMilliseconds(999)),
            Is.False);
        Assert.That(
            FieldBridgeContract.ShouldPulseProgress(first, first.AddSeconds(1)),
            Is.True);

        JsonObject payload = FieldBridgeContract.CreateProgressPayload(
            FieldBridgeContract.Create(FieldProgressNotice.StageActing),
            first);
        Assert.That((string?)payload["stage"], Is.EqualTo(FieldProgressNotice.StageActing));
        Assert.That(payload["error"], Is.Null);
        Assert.That((string?)payload["phase"], Is.EqualTo("active"));
        Assert.That((long?)payload["t"], Is.EqualTo(first.ToUnixTimeMilliseconds()));
    }

    [Test]
    public void MilestoneDueFiresAtThreePointZeroOneSecondsNotAtTheNextPulse()
    {
        DateTimeOffset start = DateTimeOffset.Parse(
            "2026-08-23T12:00:00Z",
            CultureInfo.InvariantCulture,
            DateTimeStyles.AssumeUniversal);
        DateTimeOffset due = FieldBridgeContract.FirstHitoDueAt(start);
        DateTimeOffset pulseOnly = FieldBridgeContract.FirstPulseAfterSilenceBudget(start);

        Assert.That(FieldBridgeContract.ProgressPulse.TotalSeconds, Is.LessThanOrEqualTo(1.0));
        Assert.That((due - start).TotalSeconds, Is.EqualTo(3.01).Within(0.0001));
        Assert.That(FirstSignal.ShouldEmitMilestone(start, start.AddSeconds(3)), Is.False);
        Assert.That(FirstSignal.ShouldEmitMilestone(start, due), Is.True);
        Assert.That((pulseOnly - start).TotalSeconds, Is.EqualTo(4).Within(0.0001));
        Assert.That(due, Is.LessThan(pulseOnly));
        Assert.That(
            (due - start).TotalSeconds,
            Is.GreaterThan(FirstSignal.SilenceBudgetSeconds));
    }

    [Test]
    public async Task TryEmitDueMilestoneOnAWorkingTurnEmitsAtThreePointZeroOneSeconds()
    {
        DateTimeOffset start = DateTimeOffset.Parse(
            "2026-08-23T12:00:00Z",
            CultureInfo.InvariantCulture,
            DateTimeStyles.AssumeUniversal);
        await using var viewModel = new MainWindowViewModel();
        const string request = "Abre Steam y ve a la biblioteca";
        viewModel.BeginTurnPresentation(request, start);

        Assert.That(viewModel.ProgressLabel, Is.Null);
        Assert.That(viewModel.TryEmitDueMilestone(start.AddSeconds(3)), Is.False);
        Assert.That(viewModel.ProgressLabel, Is.Null);

        Assert.That(
            viewModel.TryEmitDueMilestone(FieldBridgeContract.FirstHitoDueAt(start)),
            Is.True);
        Assert.That(viewModel.ProgressLabel, Is.Not.Null.And.Not.Empty);
        Assert.That(viewModel.ProgressLabel, Does.Not.Match("(?i)^\\s*listo\\b"));
        Assert.That(viewModel.ProgressLabel, Does.Not.Contain("un momento").IgnoreCase);
        Assert.That(viewModel.ProgressLabel, Does.Contain("Sigo"));
        string first = viewModel.ProgressLabel!;

        Assert.That(
            viewModel.TryEmitDueMilestone(start.AddSeconds(3.5)),
            Is.False,
            "a fresh hito is not due 0.5 s after the last visible label");
        Assert.That(viewModel.ProgressLabel, Is.EqualTo(first));
    }

    [Test]
    public void FormulatedProgressLabelIsVisibleAndDoesNotClaimAResult()
    {
        string label = FirstSignal.FormulateProgress(
            "Explicame en dos frases que es la fotosintesis.");
        FieldProgressNotice? notice = FieldBridgeContract.ResolveProgress(
            isReady: true,
            isBusy: true,
            hasStartupError: false,
            statusDescription: "understanding",
            progressLabel: label);

        Assert.That(notice, Is.Not.Null);
        Assert.That(notice!.Stage, Is.EqualTo(FieldProgressNotice.StageUnderstanding));
        Assert.That(notice.Label, Is.EqualTo(label));
        Assert.That(notice.Label, Does.Not.Match("(?i)^\\s*listo\\b"));
        Assert.That(notice.Label, Does.Not.Contain("un momento").IgnoreCase);

        JsonObject payload = FieldBridgeContract.CreateProgressPayload(notice);
        Assert.That((string?)payload["label"], Is.EqualTo(label));
        Assert.That((string?)payload["error"], Is.Null);
    }

    [Test]
    public void AWorkingTurnNeverAnnouncesSuccess()
    {
        foreach (string description in new[]
        {
            "understanding",
            "Preparando los pasos",
            "acting",
            "Ejecutando paso 2 de 3",
        })
        {
            FieldProgressNotice? notice = FieldBridgeContract.ResolveProgress(
                isReady: true,
                isBusy: true,
                hasStartupError: false,
                statusDescription: description);

            Assert.That(notice, Is.Not.Null, description);
            Assert.That(notice!.Label, Is.Null, description);
        }
    }

    [Test]
    public void EveryPublishableStageIsNonVerbal()
    {
        foreach (string stage in FieldBridgeContract.ProgressStages)
        {
            FieldProgressNotice notice = FieldBridgeContract.Create(stage);

            Assert.That(notice.Stage, Is.EqualTo(stage));
            Assert.That(notice.Label, Is.Null, stage);
        }
    }

    [Test]
    public void ListeningAndVoiceStatesNeverProduceATurnIndication()
    {
        foreach (string description in new[] { "Te escucho", "Transcribiendo…" })
        {
            Assert.That(
                FieldBridgeContract.ResolveProgress(
                    isReady: true,
                    isBusy: false,
                    hasStartupError: false,
                    statusDescription: description),
                Is.Null,
                description);
        }
    }

    [Test]
    public void AStartupFailureIsHumanAndNeverBlamesTheReader()
    {
        FieldProgressNotice? notice = FieldBridgeContract.ResolveProgress(
            isReady: false,
            isBusy: false,
            hasStartupError: true,
            statusDescription: "Conexión interrumpida");

        Assert.That(notice, Is.Not.Null);
        Assert.That(notice!.Stage, Is.EqualTo(FieldProgressNotice.StageUnavailable));
        Assert.That(notice.Label, Is.Null);
    }

    [Test]
    public void TheClearedPayloadRetiresAnyPreviousIndication()
    {
        JsonObject payload = FieldBridgeContract.CreateProgressPayload(null);

        Assert.That(
            (string?)payload["type"],
            Is.EqualTo(FieldBridgeContract.ProgressPayloadType));
        Assert.That(
            (string?)payload["stage"],
            Is.EqualTo(FieldProgressNotice.StageCleared));
        Assert.That((string?)payload["phase"], Is.EqualTo("completed"));
        Assert.That(payload["label"], Is.Null);
    }

    [Test]
    public void AnActivePayloadCarriesOnlyTheClosedVocabulary()
    {
        JsonObject payload = FieldBridgeContract.CreateProgressPayload(
            FieldBridgeContract.Create(FieldProgressNotice.StageActing));

        Assert.That((string?)payload["phase"], Is.EqualTo("active"));
        Assert.That(
            FieldBridgeContract.ProgressStages,
            Does.Contain((string?)payload["stage"]));
        Assert.That(payload["error"], Is.Null);
    }

    [Test]
    public void RevisionOneEnvelopesStayByteIdenticalForAnOldReader()
    {
        var envelope = new JsonObject { ["channel"] = FieldBridgeContract.Channel };
        string before = envelope.ToJsonString();

        JsonObject stamped = FieldBridgeContract.StampEnvelope(
            envelope,
            FieldBridgeContract.LegacyReaderRevision);

        Assert.That(stamped.ToJsonString(), Is.EqualTo(before));
        Assert.That(stamped[FieldBridgeContract.MinimumReaderProperty], Is.Null);
    }

    [Test]
    public void ANewerEnvelopeIsDeclaredAndWithheldFromAnOldReader()
    {
        JsonObject stamped = FieldBridgeContract.StampEnvelope(
            new JsonObject { ["channel"] = FieldBridgeContract.Channel },
            FieldBridgeContract.TurnProgressRevision);

        Assert.That(
            (int?)stamped[FieldBridgeContract.MinimumReaderProperty],
            Is.EqualTo(FieldBridgeContract.TurnProgressRevision));
        Assert.That(
            FieldBridgeContract.CanDeliver(
                FieldBridgeContract.TurnProgressRevision,
                FieldBridgeContract.LegacyReaderRevision),
            Is.False);
        Assert.That(
            FieldBridgeContract.CanDeliver(
                FieldBridgeContract.TurnProgressRevision,
                FieldBridgeContract.NativeRevision),
            Is.True);
    }

    [Test]
    public void AnUnannouncedOrHostileReaderKeepsTheHistoricalRevision()
    {
        Assert.That(
            FieldBridgeContract.ReadReaderRevision(null),
            Is.EqualTo(FieldBridgeContract.LegacyReaderRevision));
        Assert.That(
            FieldBridgeContract.ReadReaderRevision(
                new JsonObject { ["revision"] = "two" }),
            Is.EqualTo(FieldBridgeContract.LegacyReaderRevision));
        Assert.That(
            FieldBridgeContract.ReadReaderRevision(
                new JsonObject { ["revision"] = 9_999 }),
            Is.EqualTo(FieldBridgeContract.LegacyReaderRevision));
        Assert.That(
            FieldBridgeContract.ReadReaderRevision(
                new JsonObject { ["revision"] = 2 }),
            Is.EqualTo(2));
    }
}
