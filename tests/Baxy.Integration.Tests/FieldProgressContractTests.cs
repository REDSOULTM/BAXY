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
        Assert.That(notice.Label, Does.StartWith("Estoy"));
    }

    [Test]
    public void UnderstandingProgressIsTheHonestyCorrectionClaim()
    {
        FieldProgressNotice? notice = FieldBridgeContract.ResolveProgress(
            isReady: true,
            isBusy: true,
            hasStartupError: false,
            statusDescription: "Entendiendo tu petición");

        Assert.That(notice, Is.Not.Null);
        Assert.That(notice!.Stage, Is.EqualTo(FieldProgressNotice.StageUnderstanding));
        Assert.That(notice.Label, Is.EqualTo(HonestyCorrection.NonAssertingInProgress));
        Assert.That(
            FieldBridgeContract.Create(FieldProgressNotice.StageUnderstanding).Label,
            Is.EqualTo(HonestyCorrection.NonAssertingInProgress));
    }

    [Test]
    public void AWorkingTurnNeverAnnouncesSuccess()
    {
        foreach (string description in new[]
        {
            "Entendiendo tu petición",
            "Preparando los pasos",
            "Ejecutando la petición",
            "Ejecutando paso 2 de 3",
        })
        {
            FieldProgressNotice? notice = FieldBridgeContract.ResolveProgress(
                isReady: true,
                isBusy: true,
                hasStartupError: false,
                statusDescription: description);

            Assert.That(notice, Is.Not.Null, description);
            Assert.That(
                notice!.Label.ToLowerInvariant(),
                Does.Not.Contain("list").And.Not.Contain("hecho")
                    .And.Not.Contain("termin").And.Not.Contain("complet")
                    .And.Not.Contain("éxito"),
                description);
        }
    }

    [Test]
    public void EveryPublishableStageHasNaturalHumanText()
    {
        foreach (string stage in FieldBridgeContract.ProgressStages)
        {
            FieldProgressNotice notice = FieldBridgeContract.Create(stage);

            Assert.That(notice.Stage, Is.EqualTo(stage));
            Assert.That(notice.Label, Is.Not.Empty);
            Assert.That(notice.Label, Does.EndWith("."));
            Assert.That(
                notice.Label,
                Does.Not.Contain("{").And.Not.Contain("\"")
                    .And.Not.Contain("_").And.Not.Contain("null"),
                stage);
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
        Assert.That(notice.Label, Does.Contain("intentarlo"));
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
