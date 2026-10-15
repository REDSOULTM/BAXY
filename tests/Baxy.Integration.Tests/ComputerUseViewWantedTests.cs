using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 21 (vista ordenada por objetivo): the goal's words the mind ranked a view by come back with its step and go
/// with the sub-goal's next looks («wanted» of input.visible.controls), so the view's cut keeps a bounded room for the
/// controls they name. A look before any step, or in a new sub-goal, carries none (the view of always).
/// </summary>
[TestFixture]
public sealed class ComputerUseViewWantedTests
{
    [Test]
    public void TheNextLookCarriesTheWordsOfTheStepJustDecided()
    {
        var state = new JsonObject();
        JsonObject first = ComputerUseMission.LookArguments(state, includeText: true);
        var step = new MindComputerUseStep("input.scroll", new JsonObject(), "", Wanted: ["aplicacion", "application"]);

        ComputerUseMission.NoteViewWanted(state, step);
        JsonObject next = ComputerUseMission.LookArguments(state, includeText: false);
        ComputerUseMission.NoteViewWanted(state, new MindComputerUseStep("done", new JsonObject(), ""));
        JsonObject kept = ComputerUseMission.LookArguments(state, includeText: false);

        Assert.Multiple(() =>
        {
            Assert.That(first.ContainsKey("wanted"), Is.False);
            Assert.That(first["limit"]!.GetValue<int>(), Is.EqualTo(ComputerUseMission.ViewControlLimit));
            Assert.That(next["wanted"]!.ToJsonString(), Is.EqualTo("""["aplicacion","application"]"""));
            // A step that brings no words (a learned replay, a rule) leaves the last ones.
            Assert.That(kept["wanted"]!.ToJsonString(), Is.EqualTo("""["aplicacion","application"]"""));
        });
    }

    [Test]
    public void TheMindsWordsAreReadWithinTheCatalogsBound()
    {
        JsonArray? read = MindSidecarClient.WantedWords(JsonNode.Parse("""["aplicacion", " ", 3, "x"]"""));
        JsonArray many = [];
        for (int k = 0; k < 40; k++)
        {
            many.Add("palabra" + k);
        }

        Assert.Multiple(() =>
        {
            Assert.That(read!.ToJsonString(), Is.EqualTo("""["aplicacion","x"]"""));
            Assert.That(MindSidecarClient.WantedWords(JsonNode.Parse("\"aplicacion\"")), Is.Null);
            Assert.That(MindSidecarClient.WantedWords(JsonNode.Parse("[]")), Is.Null);
            Assert.That(MindSidecarClient.WantedWords(many)!.Count, Is.EqualTo(24));
            Assert.That(MindSidecarClient.WantedWords(JsonNode.Parse($"[\"{new string('a', 65)}\"]")), Is.Null);
        });
    }
}
