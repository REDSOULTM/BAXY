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
    public void ProgressPulsesAfterTwoSecondsWithoutClaimingAResult()
    {
        DateTimeOffset first = DateTimeOffset.Parse(
            "2026-08-23T12:00:00Z",
            CultureInfo.InvariantCulture,
            DateTimeStyles.AssumeUniversal);
        Assert.That(FieldBridgeContract.ShouldPulseProgress(null, first), Is.True);
        Assert.That(
            FieldBridgeContract.ShouldPulseProgress(first, first.AddSeconds(1)),
            Is.False);
        Assert.That(
            FieldBridgeContract.ShouldPulseProgress(first, first.AddSeconds(2)),
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
