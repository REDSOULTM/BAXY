using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Encargo TZ-OSC (tandas z3/z4 del notebook, t4-c04 t3 «vale y ahora en configuracion pon el modo oscuro»): «oscuro»
/// typed into Configuración's search, «Activar el modo oscuro para aplicaciones» pressed, then «Oscuro», left selected
/// with «Elige tu modo» = Oscuro. The check read the selected «Oscuro» as the search's echo (its name is what was typed),
/// the mission pressed three accent colours after it and the final said it could not. An option that is the value of a
/// choice box of the window is that choice, not the echo (ComputerUseSuccessCheck.ChoiceBoxValue). The views and the
/// receipts are the real ones, frozen (tests/data/tz_osc_modo_oscuro.json; the mind's side: tests/test_estab_tz_osc.py).
/// </summary>
[TestFixture]
public sealed class ComputerUseTzOscTests
{
    private static readonly JsonObject Fixture = (JsonObject)JsonNode.Parse(File.ReadAllText(Path.Combine(
        FindRepositoryRoot(), "tests", "data", "tz_osc_modo_oscuro.json")))!;

    private static string Check => (string)Fixture["successCheck"]!;

    private static JsonObject View(string name) => (JsonObject)Fixture["views"]![name]!.DeepClone();

    private static JsonArray Steps(int count) =>
        new([.. ((JsonArray)Fixture["steps"]!).Take(count).Select(step => step!.DeepClone())]);

    private static JsonObject Control(JsonObject view, string kind, string name) =>
        ((JsonArray)view["controls"]!).OfType<JsonObject>().Single(control =>
            (string?)control["kind"] == kind && (string?)control["name"] == name);

    // The look after «Oscuro» was pressed (z3/z4 step 4), and the one after the search's result that led to the page,
    // where the mode was already chosen (steps 1-3): both hold, and the window writes it «Oscuro».
    [TestCase(4)]
    [TestCase(3)]
    public void TheModeChosenInItsBoxProvesTheArrival(int steps)
    {
        JsonObject view = View("paso4");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, view, Steps(steps), out string? satisfiedBy), Is.True);
            Assert.That(satisfiedBy, Is.EqualTo("control:oscuro:selected"));
            Assert.That(ComputerUseSuccessCheck.ArrivedAs(satisfiedBy, view, Steps(steps)), Is.EqualTo("Oscuro"));
        });
    }

    // The look the engine saw before its «done» (step 9), the colours pressed and «Menta oscuro» selected, still holds on
    // the mode, never on the colour.
    [Test]
    public void TheLastLookHoldsOnTheModeAndNotOnTheColour()
    {
        JsonObject view = View("paso9");
        Assert.That(ComputerUseSuccessCheck.Evaluate(Check, view, Steps(4), out _), Is.True);
        Control(view, "ComboBox", "Elige tu modo")["value"] = "Claro";
        Control(view, "ListItem", "Oscuro").Remove("state");
        Assert.That(ComputerUseSuccessCheck.Evaluate(Check, view, Steps(4), out _), Is.False,
            "«Menta oscuro» selected holds the typed word only: the search's echo");
    }

    // Contracase: the search's own entry named like the query, selected, with no box of the window showing it chosen, is
    // still the echo (the guard of QueryEchoNames and of the typed names stands).
    [Test]
    public void AnEntryNamedLikeTheQueryWithNoBoxShowingItIsStillTheEcho()
    {
        JsonObject view = View("paso4");
        Control(view, "ComboBox", "Elige tu modo").Remove("value");
        Assert.That(ComputerUseSuccessCheck.Evaluate(Check, view, Steps(4), out _), Is.False);
    }

    // Contracase: a box that searches holding the name is the query, not a choice.
    [Test]
    public void ABoxThatSearchesIsNoChoice()
    {
        JsonObject view = View("paso4");
        Control(view, "ComboBox", "Elige tu modo")["name"] = "Buscar modo";
        Assert.That(ComputerUseSuccessCheck.Evaluate(Check, view, Steps(4), out _), Is.False);
    }

    // Contracase: the box the steps typed the name into is the query too.
    [Test]
    public void TheBoxTypedIntoIsNoChoice()
    {
        JsonObject view = View("paso4");
        JsonArray steps = Steps(4);
        var typed = (JsonObject)steps[1]!.DeepClone();
        typed["step"] = 5;
        typed["into"] = "Elige tu modo";
        steps.Add(typed);
        Assert.That(ComputerUseSuccessCheck.Evaluate(Check, view, steps, out _), Is.False);
    }

    private static string FindRepositoryRoot()
    {
        DirectoryInfo? directory = new(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Baxy.slnx")))
        {
            directory = directory.Parent;
        }

        return directory?.FullName ?? throw new DirectoryNotFoundException("Baxy.slnx was not found.");
    }
}
