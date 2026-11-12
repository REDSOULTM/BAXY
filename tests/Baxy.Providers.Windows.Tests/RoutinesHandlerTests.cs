using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Routines;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// RUT1 (documentacion/RUTINAS.md §3): baxy.routines keeps the person's routines; every step is checked against the
/// catalog when it is saved, so nothing is kept that could not run, and run only gives back the steps of an active one.
/// </summary>
[TestFixture]
public sealed class RoutinesHandlerTests
{
    private string _root = string.Empty;

    [SetUp]
    public void SetUp()
    {
        _root = Path.Combine(Path.GetTempPath(), "baxy-routines-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_root);
    }

    [TearDown]
    public void TearDown() => Directory.Delete(_root, recursive: true);

    // The receipt is the routine as it was saved, read back from the store: name, phrase, steps with their arguments.
    [Test]
    public async Task CreatingSavesTheCheckedStepsAndTheReceiptSaysThem()
    {
        OperationOutcome outcome = await Run("""
            {"action":"create","phrase":"¡Siguiente!","steps":["media.control {\"action\":\"next\"}","say: listo"]}
            """);

        Assert.That(outcome.Succeeded, Is.True);
        JsonObject routine = Result(outcome)["routine"]!.AsObject();
        Assert.Multiple(() =>
        {
            Assert.That(routine["name"]!.GetValue<string>(), Is.EqualTo("¡Siguiente!"));
            Assert.That(routine["trigger"]!["phrase"]!.GetValue<string>(), Is.EqualTo("¡Siguiente!"));
            Assert.That(routine["steps"]![0]!["op"]!.GetValue<string>(), Is.EqualTo("media.control"));
            Assert.That(routine["steps"]![0]!["arguments"]!["action"]!.GetValue<string>(), Is.EqualTo("next"));
            Assert.That(routine["steps"]![1]!["say"]!.GetValue<string>(), Is.EqualTo("listo"));
            Assert.That(routine["active"]!.GetValue<bool>(), Is.True);
            Assert.That(Store().Read(), Has.Count.EqualTo(1));
            // Held-out ch01: what fires it is said, so a phrase named after a time is not told as said every day.
            Assert.That(Result(outcome)["runsWhen"]!.GetValue<string>(), Does.Contain("«¡Siguiente!» alone")
                .And.Contain("never by itself at a time"));
        });
    }

    // A step whose tool does not exist, whose arguments its schema refuses, or that is not one JSON object refuses the
    // whole routine and nothing is kept (the routines retired in 4574604aa promised what nothing ran).
    [TestCase("media.control {\"action\":\"louder\"}", "action")]
    [TestCase("audio.output.switch {\"device\":\"x\"}", "is not one of BAXY's tools")]
    [TestCase("media.control [1]", "one JSON object")]
    [TestCase("baxy.routines {\"action\":\"list\"}", "cannot manage or run routines")]
    [TestCase("say:   ", "say needs a text")]
    public async Task AnInvalidStepSavesNothing(string step, string problem)
    {
        OperationOutcome outcome = await Run(new JsonObject
        {
            ["action"] = "create",
            ["phrase"] = "pausa",
            ["steps"] = new JsonArray("say: hola", step),
        }.ToJsonString());

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("routine_invalid_step"));
            Assert.That(Result(outcome)["step"]!.GetValue<int>(), Is.EqualTo(2));
            Assert.That(Result(outcome)["problem"]!.GetValue<string>(), Does.Contain(problem));
            Assert.That(Store().Read(), Is.Empty);
        });
    }

    // Two active routines cannot share a phrase, compared without case, accents or punctuation; nor two a name.
    [Test]
    public async Task APhraseFiresOneRoutineOnly()
    {
        await Run("""{"action":"create","phrase":"Música","steps":["say: uno"]}""");

        OperationOutcome same = await Run("""{"action":"create","name":"otra","phrase":"musica.","steps":["say: dos"]}""");
        OperationOutcome name = await Run("""{"action":"create","name":"MUSICA","phrase":"tres","steps":["say: tres"]}""");

        Assert.Multiple(() =>
        {
            Assert.That(same.ErrorCode, Is.EqualTo("routine_duplicate_phrase"));
            Assert.That(name.ErrorCode, Is.EqualTo("routine_duplicate_name"));
            Assert.That(Store().Read(), Has.Count.EqualTo(1));
        });
    }

    // run gives back the steps of an active routine, named by its name or its phrase; a disabled one is refused and
    // says so; one that is not there says which there are.
    [Test]
    public async Task RunGivesTheStepsOfAnActiveRoutineOnly()
    {
        await Run("""{"action":"create","name":"cine","phrase":"modo cine","steps":["media.control {\"action\":\"pause\"}"]}""");

        OperationOutcome byPhrase = await Run("""{"action":"run","name":"Modo cine"}""");
        await Run("""{"action":"disable","name":"cine"}""");
        OperationOutcome off = await Run("""{"action":"run","name":"cine"}""");
        OperationOutcome missing = await Run("""{"action":"run","name":"teatro"}""");

        Assert.Multiple(() =>
        {
            Assert.That(byPhrase.Succeeded, Is.True);
            Assert.That(Result(byPhrase)["run"]!["steps"]![0]!["op"]!.GetValue<string>(), Is.EqualTo("media.control"));
            Assert.That(off.ErrorCode, Is.EqualTo("routine_inactive"));
            Assert.That(missing.ErrorCode, Is.EqualTo("routine_not_found"));
            Assert.That(Result(missing)["routines"]![0]!["name"]!.GetValue<string>(), Is.EqualTo("cine"));
        });
    }

    // change keeps what it is not given; delete takes it away and says which it was; list says them all.
    [Test]
    public async Task ChangeKeepsWhatItIsNotGivenAndDeleteRemoves()
    {
        await Run("""{"action":"create","phrase":"luz","steps":["say: uno"]}""");

        OperationOutcome changed = await Run("""{"action":"change","name":"luz","steps":["say: dos"]}""");
        OperationOutcome listed = await Run("""{"action":"list"}""");
        OperationOutcome deleted = await Run("""{"action":"delete","name":"luz"}""");

        Assert.Multiple(() =>
        {
            Assert.That(Result(changed)["routine"]!["trigger"]!["phrase"]!.GetValue<string>(), Is.EqualTo("luz"));
            Assert.That(Result(changed)["routine"]!["steps"]![0]!["say"]!.GetValue<string>(), Is.EqualTo("dos"));
            Assert.That(Result(listed)["count"]!.GetValue<int>(), Is.EqualTo(1));
            Assert.That(Result(deleted)["deleted"]!["name"]!.GetValue<string>(), Is.EqualTo("luz"));
            Assert.That(Store().Read(), Is.Empty);
        });
    }

    // create needs the phrase and the steps; a store file that is not a routines list is never overwritten.
    [Test]
    public async Task MissingPartsAndAnUnreadableStoreSaveNothing()
    {
        OperationOutcome noPhrase = await Run("""{"action":"create","steps":["say: hola"]}""");
        OperationOutcome noSteps = await Run("""{"action":"create","phrase":"hola"}""");
        Directory.CreateDirectory(Store().Folder);
        string file = Path.Combine(Store().Folder, "routines.v1.json");
        await File.WriteAllTextAsync(file, "not json");
        OperationOutcome unreadable = await Run("""{"action":"create","phrase":"hola","steps":["say: hola"]}""");

        Assert.Multiple(() =>
        {
            Assert.That(noPhrase.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(noSteps.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(unreadable.ErrorCode, Is.EqualTo("routines_unreadable"));
            Assert.That(File.ReadAllText(file), Is.EqualTo("not json"));
        });
    }

    // RUT6 (RUTINAS.md §5 c): a routine of a phrase kept as an order is the person's own words and no steps; nothing of
    // it is tried when it is saved and the receipt says so, so «guardada» is never told as «it works». run gives the
    // order back to be done as a request of the person.
    [Test]
    public async Task AnOrderIsKeptAsThePersonsWordsAndTheReceiptSaysNothingWasTried()
    {
        OperationOutcome saved = await Run("""
            {"action":"create","phrase":"Altavoces","order":" cambia a los altavoces Vantor "}
            """);
        OperationOutcome run = await Run("""{"action":"run","name":"altavoces"}""");

        Assert.That(saved.Succeeded, Is.True);
        JsonObject routine = Result(saved)["routine"]!.AsObject();
        Assert.Multiple(() =>
        {
            Assert.That(routine["order"]!.GetValue<string>(), Is.EqualTo("cambia a los altavoces Vantor"));
            Assert.That(routine["steps"]!.AsArray(), Is.Empty);
            Assert.That(Store().Read()[0]["order"]!.GetValue<string>(), Is.EqualTo("cambia a los altavoces Vantor"));
            Assert.That(Result(saved)["runsWhen"]!.GetValue<string>(), Does.Contain("«Altavoces» alone")
                .And.Contain("as if the person had just said it").And.Contain("Nothing of the order was done"));
            Assert.That(run.Succeeded, Is.True);
            Assert.That(Result(run)["run"]!["order"]!.GetValue<string>(), Is.EqualTo("cambia a los altavoces Vantor"));
            Assert.That(Result(run)["next"]!.GetValue<string>(), Does.Contain("as if the person had just said it"));
        });
    }

    // An order goes with a phrase: never with a time (nobody is there to be asked), never beside steps; a phrase with
    // neither says which one is missing; change swaps one for the other and keeps the phrase.
    [Test]
    public async Task AnOrderGoesWithAPhraseAloneAndChangeSwapsItForSteps()
    {
        OperationOutcome timed = await Run("""{"action":"create","at":"10:00","repeat":"daily","order":"pon música"}""");
        OperationOutcome both = await Run("""{"action":"create","phrase":"cine","order":"pausa","steps":["say: listo"]}""");
        OperationOutcome neither = await Run("""{"action":"create","phrase":"cine"}""");
        await Run("""{"action":"create","phrase":"cine","order":"pausa lo que suena"}""");
        OperationOutcome toSteps = await Run("""{"action":"change","name":"cine","steps":["say: listo"]}""");
        OperationOutcome toOrder = await Run("""{"action":"change","name":"cine","order":"atenúa las luces del salón"}""");

        Assert.Multiple(() =>
        {
            Assert.That(timed.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(both.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(neither.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(timed.ArgumentProblems.Single().Name, Is.EqualTo("order"));
            Assert.That(both.ArgumentProblems.Single().Name, Is.EqualTo("steps"));
            Assert.That(neither.ArgumentProblems.Single().Name, Is.EqualTo("order"));
            Assert.That(Result(toSteps)["routine"]!["order"], Is.Null);
            Assert.That(Result(toSteps)["routine"]!["steps"]![0]!["say"]!.GetValue<string>(), Is.EqualTo("listo"));
            Assert.That(Result(toOrder)["routine"]!["order"]!.GetValue<string>(), Is.EqualTo("atenúa las luces del salón"));
            Assert.That(Result(toOrder)["routine"]!["steps"]!.AsArray(), Is.Empty);
            Assert.That(Result(toOrder)["routine"]!["trigger"]!["phrase"]!.GetValue<string>(), Is.EqualTo("cine"));
            Assert.That(Store().Read(), Has.Count.EqualTo(1));
        });
    }

    [TestCase("¡Audio, ya!", "audio ya")]
    [TestCase("  Pantálla   IZQUIERDA ", "pantalla izquierda")]
    [TestCase("...", "")]
    public void PhrasesCompareWithoutCaseAccentsOrPunctuation(string phrase, string folded) =>
        Assert.That(LocalRoutineStore.Folded(phrase), Is.EqualTo(folded));

    private LocalRoutineStore Store() => new(Path.Combine(_root, LocalRoutineStore.FolderName));

    private async Task<OperationOutcome> Run(string json)
    {
        var handler = new RoutinesHandler(_root);
        using JsonDocument arguments = JsonDocument.Parse(json);
        return await handler.ExecuteAsync(
            new OperationInvocation("request", "mission", "invocation", arguments.RootElement.Clone()),
            CancellationToken.None);
    }

    private static JsonObject Result(OperationOutcome outcome) =>
        JsonNode.Parse(outcome.Result!.Value.GetRawText())!.AsObject();
}
