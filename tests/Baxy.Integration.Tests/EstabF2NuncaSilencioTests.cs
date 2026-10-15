using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Estabilización F2 (banco lug-1, «abrí la página de Rocket League en Steam»; events.jsonl: terminal «filtered», final
/// null, diagnostic unverified_success). The mission reached the game's page (verified); the App refused the mind's
/// floor «Listo, estoy en «rocket league».» (the request reads as out of catalog to the App's fallback, so a status
/// draft crossed the conversation checks), and its own floor of the result was never said in the turn: a greeting
/// still queued from the startup counted as a message ahead, so the floor went to the queue behind it and the turn
/// closed with no answer. BAXY always speaks: only an answer queued ahead holds the floor of the turn back.
/// </summary>
[TestFixture]
public sealed class EstabF2NuncaSilencioTests
{
    private const string Request = "abrí la página de Rocket League en Steam";

    // compose_audit.jsonl of v2-lug-1 (cu-v3/estab/C_lug1_vacio), the situation of the floor_first stage.
    private const string Reached =
        """{"kind": "operation", "operation": "mission.computer.use", "polarity": "success", "verified": true, "succeeded": true, "observed": {"goal": "ir a pagina de rocket league", "application": "Steam", "reached": true, "successCheck": "stepDone:app.open&opened:game=rocket league|control:pagina de rocket league:current|title:pagina de rocket league|page:pagina de rocket league|mark:pagina de rocket league", "stepCount": 2, "steps": [{"step": 1, "operation": "app.open", "source": "model", "appId": "Steam", "place": "game", "placeValue": "252950", "ok": true, "alreadyRunning": true, "frontChanged": true, "frontRestored": true, "placeOpened": true, "changed": true}, {"step": 2, "operation": "input.visible.click", "source": "model", "label": "D TIENDA", "ok": false, "error": "input_window_not_in_front"}], "window": {"title": "Steam", "process": "steamwebhelper", "requested": true, "root": 265376, "surface": {"reason": "not_descendant", "exStyle": "00200100", "owner": 0}, "foreground": false, "rect": {"x": 1, "y": 1, "w": 1918, "h": 1018}}, "joined": false, "elapsedMs": 7491, "modelMs": 2814, "authority": "shell_loop_over_uia_ocr_postread", "satisfiedBy": "stepDone:app.open&opened:game=rocket league", "screen": {"title": "Steam", "values": [{"name": "\"D TIENDA", "state": "selected"}], "lines": ["Formas de jugar v", "Formas de jugar", "Miscelánea v", "Buscar en la tienda", "v", "i"], "controlLines": [0, 1, 2, 3, 4, 5]}}}""";

    private const string Measured = "Listo, estoy en «rocket league».";

    private const string Volume =
        """{"kind":"operation","operation":"audio.volume.adjust","polarity":"success","verified":true,"succeeded":true,"observed":{"level":30,"direction":"down"}}""";

    [Test]
    public async Task AGreetingOrAProgressLineQueuedNeverHoldsTheFloorOfTheTurnBack()
    {
        var draft = new UserMessageDraft(Reached, "status", null);
        JsonObject facts = ModelMessageComposer.CreateFacts(draft);
        // The measured refusal of the mind's floor.
        Assert.That(UserMessagePolicy.ConversationReplyRejectionReason(Request, Measured), Is.EqualTo("unverified_success"));
        string? floor = OperationFloor.Final((JsonObject)JsonNode.Parse(Reached)!, english: false);
        Assert.That(floor, Is.Not.Null.And.Not.Empty);

        using var stop = new CancellationTokenSource();
        var mindNeverComes = new TaskCompletionSource<MindSidecarClient?>();
        var queue = new PendingModelMessageQueue(
            token => mindNeverComes.Task.WaitAsync(token),
            (_, _, _) => Task.CompletedTask,
            _ => Task.CompletedTask,
            () => { },
            () => Task.CompletedTask);
        var greeting = new UserMessageDraft("""{"kind":"welcome","polarity":"success"}""", "welcome", null);
        queue.Enqueue(new PendingModelMessage(greeting, string.Empty, ModelMessageComposer.CreateFacts(greeting), "t0"),
            stop.Token);
        UserMessageDraft progress = MainWindowViewModel.CreateMilestoneDraft("Sigo trabajando en ello.", 1, 2);
        queue.Enqueue(new PendingModelMessage(progress, Request, ModelMessageComposer.CreateFacts(progress), "t1"),
            stop.Token);

        var refused = new ModelMessageCompositionOutcome(null, "unverified_success", UsedRecovery: false,
            Unanswered: false, RejectedText: Measured);
        Assert.Multiple(() =>
        {
            Assert.That(queue.Count, Is.EqualTo(2));
            // The measured silence: counting every queued message held the floor back.
            Assert.That(ModelMessageComposer.InTurnFloor(refused, draft, Request, facts, queue.Count > 0), Is.Null);
            Assert.That(queue.HoldsAnAnswer, Is.False);
            Assert.That(ModelMessageComposer.InTurnFloor(refused, draft, Request, facts, queue.HoldsAnAnswer),
                Is.EqualTo(floor));
        });

        // Contracase: a result queued ahead keeps the order; the floor waits behind it, as before.
        var earlier = new UserMessageDraft(Volume, "status", null);
        queue.Enqueue(new PendingModelMessage(earlier, "baja el volumen", ModelMessageComposer.CreateFacts(earlier), "t1"),
            stop.Token);
        Assert.That(queue.HoldsAnAnswer, Is.True);
        Assert.That(ModelMessageComposer.InTurnFloor(refused, draft, Request, facts, queue.HoldsAnAnswer), Is.Null);
        await stop.CancelAsync();
        await queue.CloseAsync();
    }

    [Test]
    public void ContracaseAnAcceptedFloorAndATurnWithNoActionDoNotChange()
    {
        var volume = new UserMessageDraft(Volume, "status", null);
        string? said = ModelMessageComposer.DeterministicFinal(volume, "baja el volumen",
            ModelMessageComposer.CreateFacts(volume), string.Empty);
        Assert.That(said, Is.Not.Null);
        Assert.That(UserMessagePolicy.AcceptModelAuthoredResponse(said, volume, "baja el volumen", null), Is.EqualTo(said));

        // No action: there is no floor, and nothing is said in its place.
        var talk = new UserMessageDraft("""{"kind":"conversation","polarity":"success"}""", "status", null);
        Assert.That(ModelMessageComposer.DeterministicFinal(talk, "hola", ModelMessageComposer.CreateFacts(talk),
            string.Empty), Is.Null);
    }
}
