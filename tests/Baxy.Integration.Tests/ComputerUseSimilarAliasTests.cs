using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Review r10a finding 5: a click the mind's encoder chose by resemblance (alias «by: semantic») made the check hold
/// through its own alias (a circular proof), and the arrival counted as strong and as a translation confirmed. It is
/// now marked «similar:» and weak, unless a translation of the model or the window's title backs it.
/// </summary>
[TestFixture]
public sealed class ComputerUseSimilarAliasTests
{
    private const string Check = "control:video library:current|title:video library";

    private static JsonObject View() => (JsonObject)JsonNode.Parse("""
        {"window": {"title": "Medios"}, "controls": [{"i": 0, "kind": "ListItem", "name": "Biblioteca de música"}]}
        """)!;

    private static MindComputerUseStep Click(string by, JsonObject? translation = null) => new(
        "input.visible.click", new JsonObject { ["label"] = "Biblioteca de música" }, "similar",
        Alias: new JsonObject { ["from"] = "video library", ["to"] = "Biblioteca de música", ["by"] = by },
        Translation: translation);

    [Test]
    public void AnArrivalThroughANamePickedByResemblanceIsWeakAndNeverConfirmed()
    {
        var state = new JsonObject();
        ComputerUseMission.NoteTranslation(state, Click("semantic"), View(), step: 1, subgoal: 0);
        string? term = ComputerUseMission.WeakenedBySimilarity(state, Check, "control:==Biblioteca de música:current");

        var cache = new ComputerUseLabelTranslations(Path.Combine(Path.GetTempPath(), $"cu-similar-{Guid.NewGuid():N}.json"));
        ComputerUseMission.SettleTranslations(cache, state, Check, reached: true, term);
        Assert.Multiple(() =>
        {
            Assert.That(term, Is.EqualTo("control:==Biblioteca de música:current&similar:biblioteca de musica"));
            Assert.That(cache.Find("video library"), Is.Null, "a resemblance is no translation seen");
        });
    }

    [Test]
    public void ContracaseATranslationOrTheTitleBacksTheSameName()
    {
        // The model's translation gave that very name: an independent corroboration.
        var translated = new JsonObject();
        ComputerUseMission.NoteTranslation(translated, Click("semantic", new JsonObject
        {
            ["label"] = "video library",
            ["names"] = new JsonArray("Biblioteca de música"),
        }), View(), step: 1, subgoal: 0);
        // The alias came from the model's own translation, not from resemblance.
        var modelAlias = new JsonObject();
        ComputerUseMission.NoteTranslation(modelAlias, Click("model"), View(), step: 1, subgoal: 0);
        // The window's title names it.
        var titled = new JsonObject();
        ComputerUseMission.NoteTranslation(titled, Click("semantic"), View(), step: 1, subgoal: 0);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.WeakenedBySimilarity(translated, Check, "control:==Biblioteca de música:current"),
                Is.EqualTo("control:==Biblioteca de música:current"));
            Assert.That(ComputerUseMission.WeakenedBySimilarity(modelAlias, Check, "control:==Biblioteca de música:current"),
                Is.EqualTo("control:==Biblioteca de música:current"));
            Assert.That(ComputerUseMission.WeakenedBySimilarity(titled, Check, "title:==Biblioteca de música"),
                Is.EqualTo("title:==Biblioteca de música"));
            // A planned term that held as planned is never marked.
            Assert.That(ComputerUseMission.WeakenedBySimilarity(titled, Check, "control:video library:current"),
                Is.EqualTo("control:video library:current"));
        });
    }
}
