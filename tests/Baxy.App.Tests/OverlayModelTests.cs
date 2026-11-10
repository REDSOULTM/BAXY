using System.IO;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Owner, 2026-11-08: while BAXY is behind another window, a small overlay in a corner says what it is doing. It reads
/// the same events the view gets (FieldProductChannel): the request, each step as it starts and ends, the reply, and a
/// card that waits for the person; and it goes away on its own a while after the turn ends.
/// </summary>
[TestFixture]
public sealed class OverlayModelTests
{
    private static readonly DateTimeOffset T0 = new(2026, 11, 8, 20, 0, 0, TimeSpan.Zero);

    private static JsonObject You(string id, string text) =>
        new() { ["type"] = "item", ["item"] = new JsonObject { ["who"] = "you", ["id"] = id, ["text"] = text } };

    private static JsonObject Step(string phase, string id, string label, string? status = null, string? obs = null) =>
        new() { ["type"] = "step", ["phase"] = phase, ["id"] = id, ["label"] = label, ["status"] = status, ["obs"] = obs };

    private static JsonObject Reply(string text, params (string Id, string Label, string Status)[] steps)
    {
        var list = new JsonArray();
        foreach ((string id, string label, string status) in steps)
        {
            list.Add(new JsonObject { ["id"] = id, ["label"] = label, ["status"] = status });
        }

        return new JsonObject { ["type"] = "item", ["item"] = new JsonObject { ["who"] = "baxy", ["id"] = "b1", ["text"] = text, ["steps"] = list } };
    }

    // The view's state event: «busy» is the App's own word for a turn that runs (MainWindowViewModel.IsBusy).
    private static JsonObject State(bool busy, string quiet = "") => new()
    {
        ["type"] = "state", ["value"] = quiet.Length > 0 ? quiet : busy ? "thinking" : "idle",
        ["quiet"] = quiet.Length > 0 ? quiet : busy ? "thinking" : "idle", ["busy"] = busy,
    };

    private static JsonObject Notice(string text) =>
        new() { ["type"] = "item", ["item"] = new JsonObject { ["who"] = "sys", ["id"] = "s1", ["text"] = text } };

    [Test]
    public void NothingIsShownBeforeARequest()
    {
        var model = new OverlayModel();
        Assert.That(model.Snapshot(T0, hideSeconds: 8, english: false), Is.Null);
    }

    [Test]
    public void EachStepShowsAsItStartsAndEnds()
    {
        var model = new OverlayModel();
        model.Apply(You("y1", "abre la calculadora"), T0);
        model.Apply(Step("start", "s1", "Abrir una aplicación · Calculadora"), T0.AddSeconds(1));

        OverlaySnapshot working = model.Snapshot(T0.AddSeconds(2), 8, false)!;
        Assert.Multiple(() =>
        {
            Assert.That(working.Kind, Is.EqualTo("working"));
            Assert.That(working.Title, Is.EqualTo("Trabajando · paso 1"));
            Assert.That(working.Request, Is.EqualTo("abre la calculadora"));
            Assert.That(working.Steps.Single().Status, Is.EqualTo("run"));
            Assert.That(working.Elapsed, Is.EqualTo("0:02"));
        });

        model.Apply(Step("start", "s2", "Ver el estado del PC"), T0.AddSeconds(3));
        model.Apply(Step("end", "s2", "Ver el estado del PC", "read", "Leído"), T0.AddSeconds(3));
        model.Apply(Step("end", "s1", "Abrir una aplicación · Calculadora", "ok", "La ventana quedó al frente"), T0.AddSeconds(3));
        IReadOnlyList<OverlayStep> steps = model.Snapshot(T0.AddSeconds(3), 8, false)!.Steps;
        Assert.That(steps, Is.EqualTo(new[]
        {
            new OverlayStep("Abrir una aplicación · Calculadora", "ok", "La ventana quedó al frente"),
            new OverlayStep("Ver el estado del PC", "read", null),
        }), "an observation that only repeats the status is left out");
    }

    [Test]
    public void TheEndSaysHowItEndedAndGoesAwayAfterTheChosenSeconds()
    {
        var model = new OverlayModel();
        model.Apply(You("y1", "abre la calculadora"), T0);
        model.Apply(Reply("Listo, la calculadora está abierta.", ("s1", "Abrir una aplicación", "ok")), T0.AddSeconds(4));

        OverlaySnapshot done = model.Snapshot(T0.AddSeconds(5), 8, false)!;
        Assert.Multiple(() =>
        {
            Assert.That(done.Kind, Is.EqualTo("ok"));
            Assert.That(done.Title, Is.EqualTo("✓ Hecho y comprobado"));
            Assert.That(done.Say, Is.EqualTo("Listo, la calculadora está abierta."));
            Assert.That(model.Snapshot(T0.AddSeconds(12.5), 8, false), Is.Null, "8 s after the end it is gone");
            Assert.That(model.Snapshot(T0.AddSeconds(60), 0, false), Is.Not.Null, "«Nunca» keeps it until the next request");
        });
    }

    [Test]
    public void AFailureStaysLongerAndIsNeverSaidAsMoreThanWasChecked()
    {
        var model = new OverlayModel();
        model.Apply(You("y1", "cambia el nombre del informe"), T0);
        model.Apply(Reply("Listo.", ("s1", "Renombrar un archivo", "fail")), T0.AddSeconds(2));

        Assert.Multiple(() =>
        {
            Assert.That(model.Snapshot(T0.AddSeconds(3), 8, false)!.Title, Is.EqualTo("✕ No pude"));
            Assert.That(model.Snapshot(T0.AddSeconds(15), 8, false), Is.Not.Null, "a failure stays 20 s");
            Assert.That(model.Snapshot(T0.AddSeconds(23), 8, true), Is.Null);
        });
    }

    [Test]
    public void ACardWaitingForThePersonIsShownUntilItIsAnswered()
    {
        var model = new OverlayModel();
        model.Apply(You("y1", "borra notas.txt"), T0);
        model.Apply(new JsonObject
        {
            ["type"] = "item",
            ["item"] = new JsonObject { ["who"] = "card", ["id"] = "c1", ["status"] = "pending", ["title"] = "Borrar notas.txt", ["target"] = "Escritorio", ["expires"] = T0.AddMinutes(2).ToUnixTimeMilliseconds() },
        }, T0.AddSeconds(1));

        OverlaySnapshot ask = model.Snapshot(T0.AddSeconds(2), 8, true)!;
        Assert.Multiple(() =>
        {
            Assert.That(ask.Kind, Is.EqualTo("ask"));
            Assert.That(ask.Title, Is.EqualTo("Waiting for your OK"));
            Assert.That(ask.Say, Is.EqualTo("Borrar notas.txt · Escritorio"));
            Assert.That(ask.Card, Is.EqualTo("c1"));
        });

        model.Apply(new JsonObject { ["type"] = "item", ["item"] = new JsonObject { ["who"] = "card", ["id"] = "c1", ["status"] = "no" } }, T0.AddSeconds(3));
        Assert.That(model.Snapshot(T0.AddSeconds(3), 8, false)!.Kind, Is.Not.EqualTo("ask"));
    }

    // INT16, blind review: the overlay asked for the yes with the card's title and target only; the view's card also
    // says its risk (or why the call was held), its context, and that an earlier attempt may already have run.
    [Test]
    public void ACardInTheOverlaySaysWhatTheViewsCardSaysBeforeTheYes()
    {
        var model = new OverlayModel();
        model.Apply(You("y1", "borra notas.txt"), T0);
        model.Apply(new JsonObject
        {
            ["type"] = "item",
            ["item"] = new JsonObject
            {
                ["who"] = "card", ["id"] = "c1", ["status"] = "pending", ["title"] = "Borrar notas.txt", ["target"] = "Escritorio",
                ["risk"] = "Se borra", ["context"] = "otra vez", ["effectStarted"] = true,
                ["expires"] = T0.AddMinutes(2).ToUnixTimeMilliseconds(),
            },
        }, T0.AddSeconds(1));

        Assert.Multiple(() =>
        {
            Assert.That(model.Snapshot(T0.AddSeconds(2), 8, false)!.Say,
                Is.EqualTo("Se borra · un intento anterior pudo haber corrido · otra vez\nBorrar notas.txt · Escritorio"));
            Assert.That(model.Snapshot(T0.AddSeconds(2), 8, true)!.Say,
                Is.EqualTo("Se borra · an earlier attempt may have run · otra vez\nBorrar notas.txt · Escritorio"));
        });
    }

    // INT16, blind review of the texts: Personalización says «Si algo falla, se queda 20 s»; a turn partly done has a
    // step that failed too.
    [Test]
    public void APartlyDoneTurnWithAFailedStepStaysAsLongAsAFailure()
    {
        var model = new OverlayModel();
        model.Apply(You("y1", "renombra los dos informes"), T0);
        model.Apply(Reply("Uno sí, otro no.", ("s1", "Renombrar un archivo", "ok"), ("s2", "Renombrar otro archivo", "fail")), T0.AddSeconds(2));

        Assert.Multiple(() =>
        {
            Assert.That(model.Snapshot(T0.AddSeconds(3), 8, false)!.Title, Is.EqualTo("◐ Hecho en parte"));
            Assert.That(model.Snapshot(T0.AddSeconds(15), 8, false), Is.Not.Null, "something failed: it stays 20 s");
            Assert.That(model.Snapshot(T0.AddSeconds(23), 8, false), Is.Null);
        });
    }

    [Test]
    public void ANewRequestStartsAfresh()
    {
        var model = new OverlayModel();
        model.Apply(You("y1", "uno"), T0);
        model.Apply(Reply("Hecho.", ("s1", "Paso viejo", "ok")), T0.AddSeconds(1));
        model.Apply(You("y2", "dos"), T0.AddSeconds(5));

        OverlaySnapshot fresh = model.Snapshot(T0.AddSeconds(6), 8, false)!;
        Assert.Multiple(() =>
        {
            Assert.That(fresh.Kind, Is.EqualTo("working"));
            Assert.That(fresh.Steps, Is.Empty);
            Assert.That(fresh.Request, Is.EqualTo("dos"));
        });
    }

    // REV_APP OVL-2 (2026-11-09): the clock stopped only with a reply of BAXY's with text and no step left running. A turn
    // cancelled, failed or that ended in a notice said «Trabajando» with its clock running until the next request.
    [Test]
    public void ATurnThatEndsWithNoReplyStopsTheClockAndSaysSo()
    {
        var model = new OverlayModel();
        model.Apply(State(busy: true), T0);
        model.Apply(You("y1", "abre la calculadora"), T0);
        model.Apply(Notice("No pude conectar con el modelo."), T0.AddSeconds(3));
        model.Apply(State(busy: false), T0.AddSeconds(3));

        OverlaySnapshot? ended = model.Snapshot(T0.AddSeconds(5), 8, false);
        OverlaySnapshot? later = model.Snapshot(T0.AddSeconds(7), 8, true);
        Assert.Multiple(() =>
        {
            Assert.That(ended?.Kind, Is.EqualTo("skip"));
            Assert.That(ended?.Title, Is.EqualTo("– Terminó sin respuesta"));
            Assert.That(later?.Title, Is.EqualTo("– Ended with no reply"));
            Assert.That(ended?.Say, Is.EqualTo("No pude conectar con el modelo."), "what the turn said instead");
            Assert.That(later?.Elapsed, Is.EqualTo("0:03"), "the clock stopped when the turn ended");
            Assert.That(model.Snapshot(T0.AddSeconds(12), 8, false), Is.Null, "and it goes away as any end");
        });
    }

    [Test]
    public void ATurnThatEndsWithAStepStillRunningSaysItMayHaveHappened()
    {
        var model = new OverlayModel();
        model.Apply(State(busy: true), T0);
        model.Apply(You("y1", "cierra el bloc de notas"), T0);
        model.Apply(Step("start", "s1", "Cerrar una aplicación"), T0.AddSeconds(1));
        model.Apply(State(busy: false), T0.AddSeconds(2));

        OverlaySnapshot? ended = model.Snapshot(T0.AddSeconds(4), 8, false);
        Assert.Multiple(() =>
        {
            Assert.That(ended?.Kind, Is.EqualTo("maybe"));
            Assert.That(ended?.Steps.Select(static step => step.Status), Is.EqualTo(new[] { "maybe" }));
            Assert.That(ended?.Elapsed, Is.EqualTo("0:02"));
        });
    }

    // Controls: the person speaking while the turn runs is not its end, and the reply that comes just after the App
    // ended the turn is the one shown.
    [Test]
    public void ListeningInsideATurnIsNotItsEndAndAReplyAfterTheEndIsShown()
    {
        var model = new OverlayModel();
        model.Apply(State(busy: true), T0);
        model.Apply(You("y1", "abre la calculadora"), T0);
        model.Apply(State(busy: true, quiet: "listening"), T0.AddSeconds(1));
        OverlaySnapshot? working = model.Snapshot(T0.AddSeconds(2), 8, false);
        model.Apply(State(busy: false), T0.AddSeconds(3));
        model.Apply(Reply("Listo, la calculadora está abierta.", ("s1", "Abrir una aplicación", "ok")), T0.AddSeconds(3));
        OverlaySnapshot? ended = model.Snapshot(T0.AddSeconds(4), 8, false);

        Assert.Multiple(() =>
        {
            Assert.That(working?.Kind, Is.EqualTo("working"));
            Assert.That(ended?.Kind, Is.EqualTo("ok"));
            Assert.That(ended?.Say, Is.EqualTo("Listo, la calculadora está abierta."));
        });
    }

    // The same end through the view's channel: a turn the mind fails ends the overlay's turn by the events the view gets.
    [Test]
    public async Task ATurnTheMindFailsEndsTheOverlaysTurnThroughTheViewsEvents()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject { ["fail"] = new JsonArray("turn.decide"), ["failCode"] = "model_failed" });
        MainWindowViewModel viewModel = await ViewModelHarness.WithMindAsync();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            ViewModelHarness.AcceptTurns(viewModel);
            Assert.That((await view.SendAsync("POST", "/turn", new JsonObject { ["text"] = "abre la calculadora" })).Status, Is.EqualTo(200));
            Assert.That(await ViewModelHarness.UntilAsync(() => !viewModel.IsBusy && viewModel.LastTurnFailure is not null), Is.True);

            var model = new OverlayModel();
            foreach (JsonObject published in view.Sink.Events)
            {
                model.Apply(published, T0);
            }

            OverlaySnapshot? shown = model.Snapshot(T0.AddSeconds(5), 8, false);
            Assert.Multiple(() =>
            {
                Assert.That(shown?.Request, Is.EqualTo("abre la calculadora"));
                Assert.That(shown?.Kind, Is.Not.EqualTo("working"), "the turn ended");
                Assert.That(shown?.Elapsed, Is.EqualTo("0:00"), "and its clock with it");
            });
        }
    }

    private static JsonObject Card(string id, DateTimeOffset expires) => new()
    {
        ["type"] = "item",
        ["item"] = new JsonObject { ["who"] = "card", ["id"] = id, ["status"] = "pending", ["title"] = "Borrar notas.txt", ["expires"] = expires.ToUnixTimeMilliseconds() },
    };

    private static JsonObject Transcript(params string[] ids)
    {
        var items = new JsonArray();
        foreach (string id in ids)
        {
            items.Add(new JsonObject { ["who"] = "you", ["id"] = id, ["text"] = "algo" });
        }

        return new JsonObject { ["type"] = "transcript", ["items"] = items };
    }

    // REV_APP OVL-3 (2026-11-09): the conversation on screen changed (another opened, a new one, the current deleted:
    // FieldProductChannel.StartSession publishes its transcript) and the overlay kept telling the one that was gone.
    [Test]
    public void AConversationThatIsNoLongerOnScreenIsNoLongerTold()
    {
        var model = new OverlayModel();
        model.Apply(You("y1", "abre la calculadora"), T0);
        model.Apply(Reply("Listo.", ("s1", "Abrir una aplicación", "ok")), T0.AddSeconds(2));
        model.Apply(Transcript("y1"), T0.AddSeconds(3));
        OverlaySnapshot? same = model.Snapshot(T0.AddSeconds(4), 0, false);
        model.Apply(Transcript(), T0.AddSeconds(5));

        Assert.Multiple(() =>
        {
            Assert.That(same?.Request, Is.EqualTo("abre la calculadora"), "control: the same conversation again is still told");
            Assert.That(model.Snapshot(T0.AddSeconds(6), 0, false), Is.Null, "a conversation that is gone is not");
        });
    }

    // REV_APP OVL-4 (2026-11-09): the answer given from the overlay was not looked at; when the App did not take it the
    // card stayed as if nothing had been pressed, and the person's Sí went nowhere without a word.
    [Test]
    public void AnAnswerTheAppDidNotTakeIsSaidOnItsCardUntilAnotherComes()
    {
        var model = new OverlayModel();
        model.Apply(You("y1", "borra notas.txt"), T0);
        model.Apply(Card("c1", T0.AddMinutes(2)), T0.AddSeconds(1));
        model.AnswerNotTaken("c0");
        OverlaySnapshot? otherCard = model.Snapshot(T0.AddSeconds(2), 8, false);
        model.AnswerNotTaken("c1");
        OverlaySnapshot? said = model.Snapshot(T0.AddSeconds(3), 8, false);
        OverlaySnapshot? saidEn = model.Snapshot(T0.AddSeconds(3), 8, true);
        model.Apply(Card("c2", T0.AddMinutes(3)), T0.AddSeconds(4));
        OverlaySnapshot? next = model.Snapshot(T0.AddSeconds(5), 8, false);

        Assert.Multiple(() =>
        {
            Assert.That(otherCard?.Say, Is.EqualTo("Borrar notas.txt"), "an answer to another card changes nothing");
            Assert.That(said?.Card, Is.EqualTo("c1"));
            Assert.That(said?.Say, Is.EqualTo("Borrar notas.txt\nBAXY no tomó tu respuesta desde aquí: contesta en su ventana."));
            Assert.That(saidEn?.Say, Is.EqualTo("Borrar notas.txt\nBAXY didn’t take your answer from here: answer in its window."));
            Assert.That(next?.Say, Is.EqualTo("Borrar notas.txt"), "a new card starts clean");
        });
    }

    // REV_APP OVL-4: the overlay looks at what the App did with its answer. Taken: nothing more. Refused (another card is
    // the pending one, the turn could not take it) or failed: the card says so, and a failure is kept with its type.
    [Test]
    public async Task AnAnswerTheAppRefusedOrThatFailedIsSaidAndAFailureIsKept()
    {
        string folder = Path.Combine(Path.GetTempPath(), "baxy-overlay-answer-" + Guid.NewGuid().ToString("N"));
        try
        {
            int said = 0;
            await OverlayPresenter.Answer(static () => Task.FromResult<string?>(null), () => said++, folder);
            int afterTaken = said;
            await OverlayPresenter.Answer(static () => Task.FromResult<string?>("turn_in_progress"), () => said++, folder);
            int afterRefused = said;
            await OverlayPresenter.Answer(static () => throw new InvalidCastException("not the person's"), () => said++, folder);
            string kept = await File.ReadAllTextAsync(Path.Combine(folder, "unhandled.v1.jsonl"));

            Assert.Multiple(() =>
            {
                Assert.That(afterTaken, Is.Zero, "an answer the App took says nothing more");
                Assert.That(afterRefused, Is.EqualTo(1));
                Assert.That(said, Is.EqualTo(2), "nor is a failure left unsaid");
                Assert.That(kept, Does.Contain("overlay.answer").And.Contain("InvalidCastException"));
                Assert.That(kept, Does.Not.Contain("not the person's"), "only its type");
            });
        }
        finally
        {
            if (Directory.Exists(folder))
            {
                Directory.Delete(folder, recursive: true);
            }
        }
    }
}
