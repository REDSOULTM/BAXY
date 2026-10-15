using System.IO;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 19 «app-cerrada-se-abre» (uso real r17): a window.resolve of an installed application that finds no window,
/// before steps that only place that window, opens the application and resolves it once more; a target that is not
/// installed, or still absent, ends the turn with that absence and no replan. Minimizing, closing or focusing never
/// open anything. Pure plan boundary: no core, no window, nothing clicks.
/// </summary>
[TestFixture]
public sealed class R19AppCerradaSeAbreTests
{
    private static MindPlanStep Resolve(string id, string application) =>
        new(id, "window.resolve", "Encuentra la ventana.", [], "literal",
            new JsonObject { ["applicationName"] = application });

    private static MindPlanStep Acting(string id, string operation, string dependsOn, JsonObject? arguments = null) =>
        new(id, operation, "Actúa sobre la ventana.", [dependsOn], "after_dependencies", arguments);

    private static OperationResponse Failed(string code, bool effect = false) =>
        new(
            ProtocolTypes.OperationResponse,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            OperationStatuses.Failed,
            "No se hizo.",
            false,
            false,
            null,
            code,
            EffectMayHaveOccurred: effect);

    private static OperationResponse Done() =>
        Failed("unused") with { Status = OperationStatuses.Completed, Verified = true, ErrorCode = null };

    private static JsonObject Args(MindPlanStep step) => step.Arguments!.DeepClone().AsObject();

    // t2-c18 T1 «pon el Word y el Edge uno al lado del otro»: Word placed, Edge closed.
    [Test]
    public void TheSecondWindowOfASnapIsOpenedAndResolvedAgain()
    {
        MindPlanStep resolveWord = Resolve("word", "Word");
        MindPlanStep resolveEdge = Resolve("edge", "Microsoft Edge");
        MindPlanStep snapEdge = Acting("snapEdge", "window.snap", "edge", new JsonObject { ["side"] = "right" });
        var execution = new PendingMindPlanExecution(
            "pon el Word y el Edge uno al lado del otro",
            [resolveWord, Acting("snapWord", "window.snap", "word"), resolveEdge, snapEdge])
        {
            NextIndex = 2,
        };
        execution.Observations.Add(new JsonObject { ["stepId"] = "word" });
        execution.CompletedMessages.Add("Coloqué Word.");

        PendingMindPlanExecution? reopened =
            MindPlanBoundary.OpenBeforeResolvingAgain(execution, Failed("window_not_found"), Args(resolveEdge));

        Assert.That(reopened, Is.Not.Null);
        MindPlanStep open = reopened!.Steps[0];
        Assert.Multiple(() =>
        {
            Assert.That(reopened.Steps.Select(static step => step.Operation),
                Is.EqualTo(new[] { "app.open", "window.resolve", "window.snap" }));
            Assert.That(open.Arguments!["appId"]!.GetValue<string>(), Is.EqualTo("Microsoft Edge"));
            Assert.That(open.DependsOn, Is.Empty);
            Assert.That(reopened.Steps[1].Id, Is.EqualTo("edge"), "the placement still grounds on the same resolve");
            Assert.That(reopened.Steps[1].DependsOn, Is.EqualTo(new[] { open.Id }));
            Assert.That(reopened.Steps[1].Arguments!["applicationName"]!.GetValue<string>(), Is.EqualTo("Microsoft Edge"));
            Assert.That(reopened.Steps[2], Is.SameAs(snapEdge));
            Assert.That(reopened.NextIndex, Is.Zero);
            Assert.That(reopened.InsertedOpens, Does.Contain(open.Id));
            Assert.That(reopened.Observations, Has.Count.EqualTo(1));
            Assert.That(reopened.CompletedMessages, Is.EqualTo(new[] { "Coloqué Word." }));
        });

        // Opened and still no window: tried once, and the absence ends the turn without another plan.
        reopened.NextIndex = 1;
        Assert.Multiple(() =>
        {
            Assert.That(
                MindPlanBoundary.OpenBeforeResolvingAgain(reopened, Failed("window_not_found"), Args(resolveEdge)),
                Is.Null);
            Assert.That(MindPlanBoundary.MayReplan(reopened, Failed("window_not_found")), Is.False);
        });

        // The open itself failed: its failure is the turn's end, never a replan.
        reopened.NextIndex = 0;
        Assert.That(MindPlanBoundary.MayReplan(reopened, Failed("launch_failed")), Is.False);
    }

    // t3-c15/1 «poné el word a la izquierda y el chrome a la derecha» with both closed (27 s on a «no»).
    [Test]
    public void BothAbsentWindowsAreOpenedEachBeforeItsOwnPlacement()
    {
        MindPlanStep resolveWord = Resolve("word", "Word");
        MindPlanStep resolveChrome = Resolve("chrome", "Google Chrome");
        var execution = new PendingMindPlanExecution(
            "poné el word a la izquierda y el chrome a la derecha",
            [resolveWord, Acting("snapWord", "window.snap", "word"), resolveChrome,
                Acting("snapChrome", "window.snap", "chrome")]);

        PendingMindPlanExecution word =
            MindPlanBoundary.OpenBeforeResolvingAgain(execution, Failed("window_not_found"), Args(resolveWord))!;
        Assert.That(word.Steps.Select(static step => step.Operation),
            Is.EqualTo(new[] { "app.open", "window.resolve", "window.snap", "window.resolve", "window.snap" }));

        // Word opened, resolved and placed; Chrome's resolve then finds no window: Chrome is opened too.
        word.NextIndex = 3;
        PendingMindPlanExecution chrome =
            MindPlanBoundary.OpenBeforeResolvingAgain(word, Failed("window_not_found"), Args(resolveChrome))!;
        Assert.Multiple(() =>
        {
            Assert.That(chrome.Steps.Select(static step => step.Operation),
                Is.EqualTo(new[] { "app.open", "window.resolve", "window.snap" }));
            Assert.That(chrome.Steps[0].Arguments!["appId"]!.GetValue<string>(), Is.EqualTo("Google Chrome"));
            Assert.That(chrome.InsertedOpens, Has.Count.EqualTo(2));
        });

        // Word's open failed: Chrome's chain, which does not hang on it, still runs; the turn is not replanned.
        word.NextIndex = 0;
        IReadOnlyList<MindPlanStep>? remainder = MindPlanBoundary.IndependentRemainder(word, Failed("launch_failed"));
        Assert.Multiple(() =>
        {
            Assert.That(remainder?.Select(static step => step.Id), Is.EqualTo(new[] { "chrome", "snapChrome" }));
            Assert.That(MindPlanBoundary.MayReplan(word, Failed("launch_failed")), Is.False);
        });
    }

    [TestCase("window.move")]
    [TestCase("window.resize")]
    [TestCase("window.snap")]
    public void EveryPlacementOpensAnInstalledApplicationWithNoWindow(string operation)
    {
        MindPlanStep resolve = Resolve("w", "Word");
        var execution = new PendingMindPlanExecution("acomoda word", [resolve, Acting("act", operation, "w")]);

        Assert.That(
            MindPlanBoundary.OpenBeforeResolvingAgain(execution, Failed("window_not_found"), Args(resolve)),
            Is.Not.Null);
    }

    // Contracasos: «minimiza Word» and «cierra Discord» with it closed open nothing; minimize/focus keep replanning
    // as before, and closing keeps ending on the absence (LeavesOnlyClosingAnAbsentTarget).
    [TestCase("window.minimize", true)]
    [TestCase("window.focus", true)]
    [TestCase("app.close", false)]
    public void ActsThatAreNoPlacementNeverOpenTheApplication(string operation, bool replans)
    {
        MindPlanStep resolve = Resolve("w", operation == "app.close" ? "Discord" : "Word");
        var execution = new PendingMindPlanExecution("hazlo", [resolve, Acting("act", operation, "w")]);

        Assert.Multiple(() =>
        {
            Assert.That(
                MindPlanBoundary.OpenBeforeResolvingAgain(execution, Failed("window_not_found"), Args(resolve)),
                Is.Null);
            Assert.That(MindPlanBoundary.MayReplan(execution, Failed("window_not_found")), Is.EqualTo(replans));
        });
    }

    // Contracaso: a rest that both places and minimizes is not only a placement: nothing is opened.
    [Test]
    public void APlacementBesideAnotherActOnTheSameWindowOpensNothing()
    {
        MindPlanStep resolve = Resolve("w", "Word");
        var execution = new PendingMindPlanExecution("hazlo",
            [resolve, Acting("snap", "window.snap", "w"), Acting("min", "window.minimize", "w")]);

        Assert.That(
            MindPlanBoundary.OpenBeforeResolvingAgain(execution, Failed("window_not_found"), Args(resolve)),
            Is.Null);
    }

    // Contracaso: an application that is not installed is said as such (app_not_found), nothing is opened and the
    // placement is not replanned.
    [Test]
    public void AnApplicationThatIsNotInstalledOpensNothingAndEndsTheTurn()
    {
        MindPlanStep resolve = Resolve("w", "Word");
        var execution = new PendingMindPlanExecution("pon word a la izquierda", [resolve, Acting("snap", "window.snap", "w")]);

        Assert.Multiple(() =>
        {
            Assert.That(
                MindPlanBoundary.OpenBeforeResolvingAgain(execution, Failed("app_not_found"), Args(resolve)),
                Is.Null);
            Assert.That(MindPlanBoundary.MayReplan(execution, Failed("app_not_found")), Is.False);
        });
    }

    // A window looked for by process (no installed identity) cannot be opened: the absence ends the placement.
    [Test]
    public void AWindowSelectedByProcessIsNeverOpened()
    {
        var resolve = new MindPlanStep("w", "window.resolve", "Encuentra la ventana.", [], "literal",
            new JsonObject { ["process"] = "WINWORD" });
        var execution = new PendingMindPlanExecution("pon word a la izquierda", [resolve, Acting("snap", "window.snap", "w")]);

        Assert.Multiple(() =>
        {
            Assert.That(
                MindPlanBoundary.OpenBeforeResolvingAgain(execution, Failed("window_not_found"), Args(resolve)),
                Is.Null);
            Assert.That(MindPlanBoundary.MayReplan(execution, Failed("window_not_found")), Is.False);
        });
    }

    // A plan that already opened the application before resolving it («abre Edge y ponelo a la derecha») is not
    // opened twice.
    [Test]
    public void AResolveAfterThePlansOwnOpenIsNotOpenedAgain()
    {
        var open = new MindPlanStep("open", "app.open", "Abre Edge.", [], "literal",
            new JsonObject { ["appId"] = "Microsoft Edge" });
        var resolve = new MindPlanStep("w", "window.resolve", "Encuentra la ventana.", ["open"], "literal",
            new JsonObject { ["applicationName"] = "Microsoft Edge" });
        var execution = new PendingMindPlanExecution("abre edge y ponelo a la derecha",
            [open, resolve, Acting("snap", "window.snap", "w")])
        {
            NextIndex = 1,
        };

        Assert.That(
            MindPlanBoundary.OpenBeforeResolvingAgain(execution, Failed("window_not_found"), Args(resolve)),
            Is.Null);
    }

    // Contracaso: a snap with both windows open is unchanged (the resolve succeeds; nothing is inserted), and other
    // failures of the resolve keep their path.
    [Test]
    public void AResolveThatFoundTheWindowOrFailedOtherwiseChangesNothing()
    {
        MindPlanStep resolve = Resolve("w", "Word");
        var execution = new PendingMindPlanExecution("pon word a la izquierda", [resolve, Acting("snap", "window.snap", "w")]);

        Assert.Multiple(() =>
        {
            Assert.That(MindPlanBoundary.OpenBeforeResolvingAgain(execution, Done(), Args(resolve)), Is.Null);
            Assert.That(
                MindPlanBoundary.OpenBeforeResolvingAgain(execution, Failed("inventory_failed"), Args(resolve)),
                Is.Null);
            Assert.That(
                MindPlanBoundary.OpenBeforeResolvingAgain(execution, Failed("window_not_found", effect: true), Args(resolve)),
                Is.Null);
            Assert.That(MindPlanBoundary.MayReplan(execution, Failed("inventory_failed")), Is.True);
        });
    }

    // Revisión (MUSIC1675, CLOSE1371): a request conditioned on the application being open now. The mind marks the
    // plan (presentStateCondition); its window read is the check, so no window means the condition is false: nothing
    // is opened and the absence ends the turn without another plan.
    [TestCase("si tengo word abierto, ponelo a la izquierda", "Word", "window.snap")]
    [TestCase("pone word a la izquierda si esta abierto", "Word", "window.snap")]
    [TestCase("if Chrome is open, snap it to the right", "Google Chrome", "window.snap")]
    [TestCase("si el edge está abierto movelo a la derecha", "Microsoft Edge", "window.move")]
    [TestCase("si hay spotify corriendo achicalo", "Spotify", "window.resize")]
    [TestCase("pone el edge a la derecha if it's open", "Microsoft Edge", "window.snap")]
    public void AWindowReadThatChecksAConditionNeverOpensTheApplication(
        string objective,
        string application,
        string operation)
    {
        MindPlanStep resolve = Resolve("w", application);
        var execution = new PendingMindPlanExecution(objective, [resolve, Acting("act", operation, "w")])
        {
            PresentStateCondition = true,
        };

        Assert.Multiple(() =>
        {
            Assert.That(
                MindPlanBoundary.OpenBeforeResolvingAgain(execution, Failed("window_not_found"), Args(resolve)),
                Is.Null);
            Assert.That(MindPlanBoundary.MayReplan(execution, Failed("window_not_found")), Is.False);
        });

        // Contracaso: the same plan without the condition («pone word a la izquierda») opens the application.
        var unconditioned = new PendingMindPlanExecution(objective, [resolve, Acting("act", operation, "w")]);
        Assert.That(
            MindPlanBoundary.OpenBeforeResolvingAgain(unconditioned, Failed("window_not_found"), Args(resolve)),
            Is.Not.Null);
    }

    // The mind's mark is optional and only true on a plan; outside a plan it is ignored and the question stays
    // (revisión 2: «si tengo el chrome abierto, movelo» asking where must not end in plan_incomplete).
    [Test]
    public void ThePresentStateConditionIsReadFromThePlanResult()
    {
        JsonObject plan = JsonNode.Parse("""
            {
              "type":"plan.result",
              "id":"1",
              "version":1,
              "kind":"plan",
              "question":"",
              "steps":[
                {
                  "id":"w",
                  "operation":"window.resolve",
                  "purpose":"Encuentra la ventana.",
                  "dependsOn":[],
                  "argumentsMode":"literal",
                  "arguments":{"applicationName":"Word"}
                }
              ]
            }
            """)!.AsObject();
        JsonObject marked = plan.DeepClone().AsObject();
        marked["presentStateCondition"] = true;
        JsonObject falseMark = plan.DeepClone().AsObject();
        falseMark["presentStateCondition"] = false;
        JsonObject textMark = plan.DeepClone().AsObject();
        textMark["presentStateCondition"] = "true";
        JsonObject clarify = JsonNode.Parse("""
            {"type":"plan.result","id":"1","version":1,"kind":"clarify","question":"¿Cuál?","steps":[],
             "presentStateCondition":true}
            """)!.AsObject();
        JsonObject conversation = JsonNode.Parse("""
            {"type":"plan.result","id":"1","version":1,"kind":"conversation","question":"","steps":[],
             "presentStateCondition":"true"}
            """)!.AsObject();

        Assert.Multiple(() =>
        {
            Assert.That(MindSidecarClient.ParsePlanResult(plan)?.PresentStateCondition, Is.False);
            Assert.That(MindSidecarClient.ParsePlanResult(marked)?.PresentStateCondition, Is.True);
            Assert.That(MindSidecarClient.ParsePlanResult(falseMark), Is.Null);
            Assert.That(MindSidecarClient.ParsePlanResult(textMark), Is.Null);
            Assert.That(MindSidecarClient.ParsePlanResult(clarify)?.Question, Is.EqualTo("¿Cuál?"));
            Assert.That(MindSidecarClient.ParsePlanResult(clarify)?.PresentStateCondition, Is.False);
            Assert.That(MindSidecarClient.ParsePlanResult(conversation)?.Kind, Is.EqualTo("conversation"));
            Assert.That(MindSidecarClient.ParsePlanResult(conversation)?.PresentStateCondition, Is.False);
        });
    }

    // The mark survives the durable plan state, and an older state without it reads as unconditioned.
    [Test]
    public void ThePresentStateConditionIsPersistedWithThePlan()
    {
        string root = Path.Combine(Path.GetTempPath(), $"baxy-r19-{Guid.NewGuid():N}");
        Directory.CreateDirectory(root);
        try
        {
            var store = new DurablePlanStore(Path.Combine(root, "plan.bin"), Path.Combine(root, "plan.key"));
            var registry = new RetryableOperationRegistry(Path.Combine(root, "outbox.json"));
            MindPlanStep resolve = Resolve("w", "Word");
            var conditioned = new PendingMindPlanExecution(
                "si tengo word abierto, ponelo a la izquierda",
                [resolve, Acting("snap", "window.snap", "w")])
            {
                PresentStateCondition = true,
            };

            store.Save(conditioned);
            bool restoredConditioned = store.Load(registry)!.PresentStateCondition;
            store.Save(new PendingMindPlanExecution(
                "pone word a la izquierda",
                [resolve, Acting("snap", "window.snap", "w")]));
            bool restoredPlain = store.Load(registry)!.PresentStateCondition;

            Assert.Multiple(() =>
            {
                Assert.That(restoredConditioned, Is.True);
                Assert.That(restoredPlain, Is.False);
            });
        }
        finally
        {
            try
            {
                Directory.Delete(root, recursive: true);
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }
    }

    [TestCase("window.snap", true)]
    [TestCase("window.move", true)]
    [TestCase("window.resize", true)]
    [TestCase("window.minimize", false)]
    [TestCase("window.focus", false)]
    [TestCase("app.close", false)]
    public void ThePlacingOperationsAreData(string operation, bool places)
    {
        Assert.That(OpenWindowOperations.PlacesAnOpenWindow(operation), Is.EqualTo(places));
    }
}
