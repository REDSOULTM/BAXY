using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The step chip the view shows for a call (FieldStepProjection.Finished): its status and first words follow the typed
/// facts of the call's result, never more than they say. «Verificado» is only for an effect read back.
/// </summary>
[TestFixture]
public sealed class FieldStepProjectionTests
{
    private const string Operation = "app.open";

    [TestCase(OperationVisibleFacts.VerificationReadback, "ok", "Verificado")]
    [TestCase(OperationVisibleFacts.VerificationUnchanged, "same", "Ya estaba así")]
    [TestCase(OperationVisibleFacts.VerificationDeliveredOnly, "sent", "Enviado, sin comprobar")]
    [TestCase(OperationVisibleFacts.VerificationOutputOnly, "read", "Leído")]
    public void ACompletedCallIsShownAsItWasVerified(string verification, string status, string said)
    {
        JsonObject view = Finished(OperationStatuses.Completed, verified: true,
            new JsonObject { ["status"] = "completed", ["verification"] = verification });

        Assert.Multiple(() =>
        {
            Assert.That((string?)view["status"], Is.EqualTo(status));
            Assert.That((string?)view["obs"], Is.EqualTo(said));
        });
    }

    [Test]
    public void TheObservedFactsFollowTheVerificationAndNeverRepeatIt()
    {
        JsonObject view = Finished(OperationStatuses.Completed, verified: true, new JsonObject
        {
            ["status"] = "completed",
            ["verification"] = OperationVisibleFacts.VerificationUnchanged,
            ["level"] = 40,
        });

        Assert.That((string?)view["obs"], Is.EqualTo("Ya estaba así · level: 40"));
    }

    [TestCase(OperationVisibleFacts.VerificationNone)]
    [TestCase(null)]
    public void ACompletionWithoutAVerificationIsNotSaidVerified(string? verification)
    {
        var facts = new JsonObject { ["status"] = "completed", ["error"] = "result_unreadable" };
        if (verification is not null)
        {
            facts["verification"] = verification;
        }

        JsonObject view = Finished(OperationStatuses.Completed, verified: true, facts);

        Assert.Multiple(() =>
        {
            Assert.That((string?)view["status"], Is.EqualTo("maybe"));
            Assert.That((string?)view["reason"], Is.EqualTo("Terminó, pero no se pudo verificar"));
            Assert.That(view["obs"], Is.Null);
        });
    }

    [Test]
    public void AVerifiedCompletionWhoseEffectIsUncertainMayHaveRun()
    {
        JsonObject view = Finished(OperationStatuses.Completed, verified: true, new JsonObject
        {
            ["status"] = "completed",
            ["verification"] = OperationVisibleFacts.VerificationReadback,
            ["effectUncertain"] = true,
        });

        Assert.That((string?)view["status"], Is.EqualTo("maybe"));
    }

    [Test]
    public void AFailureWhoseEffectMayHaveHappenedIsNotAFailureNorDone()
    {
        JsonObject view = Finished(OperationStatuses.Failed, verified: false, new JsonObject
        {
            ["status"] = "failed",
            ["error"] = "engine_no_answer",
            ["effectUncertain"] = true,
        });

        Assert.Multiple(() =>
        {
            Assert.That((string?)view["status"], Is.EqualTo("maybe"));
            Assert.That((string?)view["reason"], Is.EqualTo("El motor no respondió a tiempo: puede haber corrido"));
        });
    }

    [TestCase(false)]
    [TestCase(true)]
    public void AResultReplayedFromTheJournalIsNotSaidDoneNow(bool memory)
    {
        var facts = new JsonObject
        {
            ["status"] = "completed",
            ["verification"] = OperationVisibleFacts.VerificationReadback,
        };
        if (memory)
        {
            facts["observed"] = new JsonObject { ["saved"] = true, ["replayed"] = true };
        }
        else
        {
            facts["replayed"] = "this is the recorded result of the same call made earlier; it did not run again now";
        }

        JsonObject view = Finished(OperationStatuses.Completed, verified: true, facts);

        Assert.Multiple(() =>
        {
            Assert.That((string?)view["status"], Is.EqualTo("skip"));
            Assert.That((string?)view["reason"], Is.EqualTo("No se repitió: ya había corrido antes"));
        });
    }

    [Test]
    public void ARetryableCallWhoseEffectDidNotHappenDidNotComplete()
    {
        JsonObject view = Finished(OperationStatuses.Pending, verified: false,
            new JsonObject { ["status"] = "pending", ["error"] = "provider_busy" });

        Assert.Multiple(() =>
        {
            Assert.That((string?)view["status"], Is.EqualTo("fail"));
            Assert.That((string?)view["reason"], Is.EqualTo("No se completó, se puede reintentar · provider_busy"));
        });
    }

    [Test]
    public void ARetryableCallWhoseEffectMayHaveHappenedMayHaveRun()
    {
        JsonObject view = Finished(OperationStatuses.Pending, verified: false,
            new JsonObject { ["status"] = "pending", ["error"] = "provider_busy", ["effectUncertain"] = true });

        Assert.That((string?)view["status"], Is.EqualTo("maybe"));
    }

    [TestCase("cancelled", "declined_by_person", "skip", "No se ejecutó: dijiste que no")]
    [TestCase(OperationStatuses.Rejected, "unknown_operation", "skip", "No se ejecutó: esa acción no existe")]
    [TestCase(OperationStatuses.Failed, "provider_failed", "fail", "Falló · provider_failed")]
    public void ACallThatDidNotCompleteSaysHowItEnded(string status, string error, string shown, string reason)
    {
        JsonObject view = Finished(status, verified: false, new JsonObject { ["status"] = status, ["error"] = error });

        Assert.Multiple(() =>
        {
            Assert.That((string?)view["status"], Is.EqualTo(shown));
            Assert.That((string?)view["reason"], Is.EqualTo(reason));
        });
    }

    [Test]
    public void ACallWaitingForThePersonIsNotAStep()
    {
        var step = new NativeTurnStep(Operation, new JsonObject(), OperationStatuses.Completed, false, null, 5,
            new JsonObject { ["status"] = "needs_confirmation" }.ToJsonString(), "c1");

        Assert.That(FieldStepProjection.Finished("c1", step, net: null), Is.Null);
    }

    [TestCase(true)]
    [TestCase(false)]
    public void TheCardSaysWhetherAnEarlierAttemptMayHaveRun(bool effectStarted)
    {
        JsonObject card = FieldStepProjection.Card("k1", "confirm", "system.recyclebin.empty", new JsonObject(),
            "recoverable_delete", DateTimeOffset.UtcNow.AddMinutes(2), context: null, effectStarted);

        Assert.That((bool?)card["effectStarted"], Is.EqualTo(effectStarted));
    }

    // A game the person did not name waits for their «sí» (NetworkEgress, game_title_not_said): its card names the game.
    [Test]
    public void TheCardOfAGameNamesTheGameNotItsStoreId()
    {
        var arguments = new JsonObject { ["appId"] = "252950", ["title"] = "Rocket League" };
        JsonObject card = FieldStepProjection.Card("k1", "confirm", "game.launch", arguments, OperationRisks.LowReversible,
            DateTimeOffset.UtcNow.AddMinutes(2), context: null);

        Assert.Multiple(() =>
        {
            Assert.That((string?)card["target"], Is.EqualTo("Rocket League"));
            Assert.That(FieldStepProjection.Label("game.launch", arguments), Does.EndWith("· Rocket League"));
            Assert.That(FieldStepProjection.Target(new JsonObject { ["appId"] = "Calculadora" }), Is.EqualTo("Calculadora"));
        });
    }

    internal static JsonObject Finished(string status, bool verified, JsonObject facts, string? errorCode = null)
    {
        var step = new NativeTurnStep(Operation, new JsonObject(), status, verified, errorCode, 5, facts.ToJsonString(), "c1",
            Sent: true);
        return FieldStepProjection.Finished("c1", step, net: null)!;
    }
}
