using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Goal v3 paso 5 (A7): the shell's twin of the ⚠ fixes. Every text here is the one the official-window run
/// recorded (FINAL final-once and DEV-A window 3, 2026-09-28): the mind published it and the shell refused it,
/// or every draft died and the turn ended without an answer although its result was verified.
/// </summary>
[TestFixture]
public sealed class A7AvisosTests
{
    private const string VolumeNotConfirmed =
        """{"kind":"failure","polarity":"failure","cause":"mission_failed","stepCount":0,"steps":[],"reason":{"kind":"operation","operation":"audio.volume.adjust","polarity":"failure","verified":false,"succeeded":false,"error":"external_verification_failed","cause":"external_effect_unobserved"}}""";

    private const string Clock =
        """{"kind":"operation","operation":"system.time","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"utc":"2026-09-28T14:01:21.9918672+00:00","localUtcOffsetMinutes":-180}}""";

    private const string Volume =
        """{"kind":"operation","operation":"audio.volume.adjust","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"direction":"down","amount":10,"baselineLevel":50,"level":40,"muted":true,"authority":"windows_core_audio_output_endpoint_postread"}}""";

    // E6 (FINAL t305 «orale y subele 10 al volumen q ya empezo»): the mind published the failure said in the
    // perfect tense, and this twin read it as a reversed result.
    [TestCase("No he podido subir el volumen ni oír nada, ya que el cambio no se confirmó después de la acción.")]
    [TestCase("El cambio de volumen no se ha verificado.")]
    [TestCase("I haven't been able to raise the volume.")]
    public void TheFailureSaidInThePerfectTenseIsTheFailureTold(string reply)
    {
        var draft = new UserMessageDraft(VolumeNotConfirmed, "error", null);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "orale y subele 10 al volumen q ya empezo"),
            Is.Null);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason("Subí el volumen.", draft, "subele 10 al volumen"),
            Is.EqualTo("reversed_result"));
    }

    // E7 (DEV-A3 t201 «new address»): asking the value of a bare noun phrase does not hand the request back.
    [Test]
    public void AskingTheValueOfANounPhraseIsNoEcho()
    {
        Assert.That(
            UserMessagePolicy.ConversationReplyRejectionReason("new address", "What is the new address?",
                clarification: true),
            Is.Null);
        // Handing the bare phrase back as a question is still an echo.
        Assert.That(
            UserMessagePolicy.ConversationReplyRejectionReason("new address", "New address?", clarification: true),
            Is.EqualTo("echoes_request"));
    }

    // C (DEV-A3 t217): the clock later on is the answer to a later-clock question; the current clock stays owed
    // to a plain «qué hora es».
    [Test]
    public void TheLaterClockIsTheAnswerToALaterClockQuestion()
    {
        var draft = new UserMessageDraft(Clock, "status", null);
        Assert.That(UserMessagePolicy.IsLaterClockRequest("¿qué hora serà de aquí a doce minutos?"), Is.True);
        Assert.That(UserMessagePolicy.IsLaterClockRequest("¿qué hora es?"), Is.False);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "Serán las 11:13.", draft, "¿qué hora serà de aquí a doce minutos?"),
            Is.Null);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason("Son las 11:13.", draft, "¿qué hora es?"),
            Is.Not.Null);
    }

    // E2 (FINAL t241 «…botones para operaciones básicas…»): a jargon term is a whole word.
    [Test]
    public void AForbiddenTermIsAWholeWord()
    {
        Assert.That(
            UserMessagePolicy.LeakedInternalTerm(
                "Puedes usar tkinter con botones para operaciones básicas y funciones científicas.", null),
            Is.Null);
        Assert.That(UserMessagePolicy.LeakedInternalTerm("a Python toolkit", null), Is.Null);
        Assert.That(UserMessagePolicy.LeakedInternalTerm("Hice la operacion.", null), Is.EqualTo("operacion"));
        Assert.That(UserMessagePolicy.LeakedInternalTerm("Uso el core local.", null), Is.EqualTo("core"));
        Assert.That(
            UserMessagePolicy.ConversationReplyRejectionReason(
                "Podrías decirme como crear una interfaz sencilla (también conocida como gui) de una calculadora "
                + "para el lenguaje de programación Python?",
                "Para crear una interfaz gráfica en Python, puedes usar la librería Tkinter y buscar ejemplos de "
                + "código que implementen botones para operaciones básicas y funciones científicas adicionales."),
            Is.Null);
    }

    // Last resort (DEV-A3 t418 «like 10»): the refused drafts never said the level; the verified level is told.
    [Test]
    public void AVerifiedVolumeIsToldWhenEveryDraftWasRefused()
    {
        var draft = new UserMessageDraft(Volume, "status", null);
        JsonObject facts = ModelMessageComposer.CreateFacts(draft);
        Assert.That(
            ModelMessageComposer.DeterministicFinal(draft, "bajale 10", facts, "El volumen está silenciado."),
            Is.EqualTo("Bajé el volumen a 40 %; está silenciado."));
        Assert.That(
            ModelMessageComposer.DeterministicFinal(draft, "turn it down 10", facts, "The volume is muted."),
            Is.EqualTo("I turned the volume down to 40%; it is muted."));
    }

    // M107: a failure or an unverified result is no longer left without a final; it is told from its facts — the
    // typed cause the result carries, or the plain «couldn't confirm» of an effect that may have happened — and
    // never as done (M107SueloAccionesTests).
    [Test]
    public void AFailureOrAnUnverifiedResultIsToldFromItsFactsNeverAsDone()
    {
        var failure = new UserMessageDraft(VolumeNotConfirmed, "error", null);
        Assert.That(
            ModelMessageComposer.DeterministicFinal(
                failure, "subele 10", ModelMessageComposer.CreateFacts(failure), "Subí el volumen."),
            Is.EqualTo("No pude confirmar que se hiciera el cambio."));
        // As OperationVisibleFacts.FromOutcome writes an effect that happened and was not verified.
        var unverified = new UserMessageDraft(
            Volume.Replace("\"verified\":true", "\"verified\":false", StringComparison.Ordinal)
                .Replace("\"polarity\":\"success\"", "\"polarity\":\"failure\"", StringComparison.Ordinal),
            "error", null);
        Assert.That(
            ModelMessageComposer.DeterministicFinal(
                unverified, "bajale 10", ModelMessageComposer.CreateFacts(unverified), "El volumen está en 40 %."),
            Is.EqualTo("Intenté cambiar el volumen, pero no pude confirmar si se hizo."));
    }

    [Test]
    public void TheCurrentClockIsToldButNotForALaterClockQuestion()
    {
        var draft = new UserMessageDraft(Clock, "status", null);
        JsonObject facts = ModelMessageComposer.CreateFacts(draft);
        Assert.That(ModelMessageComposer.DeterministicFinal(draft, "¿qué hora es?", facts, "Es la hora."),
            Is.EqualTo("Son las 11:01."));
        Assert.That(
            ModelMessageComposer.DeterministicFinal(
                draft, "¿qué hora serà de aquí a doce minutos?", facts, "Serán las 11:25."),
            Is.Null);
    }

    [Test]
    public async Task ARefusedVerifiedResultPublishesItsDeterministicFinalInsteadOfTheWarning()
    {
        var draft = new UserMessageDraft(Volume, "status", null);
        var pending = new PendingModelMessage(draft, "bajale 10", ModelMessageComposer.CreateFacts(draft), "t418");
        var published = new List<(string Text, string? Failure)>();
        var exhausted = new List<string>();
        var done = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        await using var mind = new MindSidecarClient();
        var queue = new PendingModelMessageQueue(
            _ => Task.FromResult<MindSidecarClient?>(mind),
            (text, failure, _) =>
            {
                published.Add((text, failure));
                done.TrySetResult(true);
                return Task.CompletedTask;
            },
            _ => Task.CompletedTask,
            () => { },
            () =>
            {
                done.TrySetResult(true);
                return Task.CompletedTask;
            },
            (_, _, _) => Task.FromResult(new ModelMessageCompositionOutcome(
                null, "missing_literal_fact", UsedRecovery: false, RejectedText: "El volumen está silenciado.")),
            (_, _) => Task.CompletedTask,
            (_, failure) =>
            {
                exhausted.Add(failure);
                return Task.CompletedTask;
            });

        queue.Enqueue(pending, CancellationToken.None);
        await done.Task.WaitAsync(TimeSpan.FromSeconds(2));
        await queue.CloseAsync();

        Assert.Multiple(() =>
        {
            Assert.That(exhausted, Is.Empty);
            Assert.That(published, Has.Count.EqualTo(1));
            Assert.That(published[0].Text, Is.EqualTo("Bajé el volumen a 40 %; está silenciado."));
            Assert.That(published[0].Failure, Is.EqualTo("missing_literal_fact;deterministic_fallback"));
            Assert.That(pending.LastRejectedText, Is.EqualTo("El volumen está silenciado."));
        });
    }
}
