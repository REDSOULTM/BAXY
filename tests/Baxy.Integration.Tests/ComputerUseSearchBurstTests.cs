using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Goal v3 point 0, fix 3 (search burst): the mission records each sub-act of a burst as a step of its own (the opener
/// with its search, the text with where it went, the result's click), so the checks and the mind's history read them as
/// any step; a burst that stopped keeps its cause on the sub-act it did not take; any other step is left as it was.
/// </summary>
[TestFixture]
public sealed class ComputerUseSearchBurstTests
{
    [Test]
    public void EverySubActOfABurstIsAStepOfItsOwn()
    {
        var record = new JsonObject
        {
            ["step"] = 3,
            ["operation"] = "input.visible.click",
            ["source"] = "model",
            ["label"] = "Buscar o iniciar una conversación",
            ["index"] = 5,
            ["search"] = "Cotele",
            ["ok"] = true,
            ["name"] = "Cotele",
            ["kind"] = "ListItem",
            ["acts"] = JsonNode.Parse("""
                [{"operation":"input.visible.click","label":"Buscar o iniciar una conversación","ok":true,"kind":"Button","surfaceChanged":true},
                 {"operation":"input.text.type","text":"Cotele","ok":true,"method":"keyboard","into":"Busca servidores, canales o MD"},
                 {"operation":"input.visible.click","label":"Cotele","ok":true,"kind":"ListItem","selected":true}]
                """),
        };
        var steps = new JsonArray { new JsonObject { ["step"] = 2, ["operation"] = "app.open", ["ok"] = true }, record };

        JsonObject last = ComputerUseMission.ExpandSearchBurst(steps, record);

        Assert.Multiple(() =>
        {
            Assert.That(steps, Has.Count.EqualTo(4));
            Assert.That(steps.Select(step => (int?)step?["step"]), Is.EqualTo(new int?[] { 2, 3, 4, 5 }));
            Assert.That(steps.Select(step => (string?)step?["operation"]),
                Is.EqualTo(new[] { "app.open", "input.visible.click", "input.text.type", "input.visible.click" }));
            Assert.That((string?)steps[1]!["kind"], Is.EqualTo("Button"), "the opener says what it pressed, not the result");
            Assert.That((string?)steps[1]!["search"], Is.EqualTo("Cotele"));
            Assert.That((string?)steps[2]!["into"], Is.EqualTo("Busca servidores, canales o MD"));
            Assert.That(ComputerUseSuccessCheck.TypedIntoASearch((JsonObject)steps[2]!), Is.True);
            Assert.That((string?)last["label"], Is.EqualTo("Cotele"));
            Assert.That((bool?)last["changed"], Is.True);
            Assert.That(steps.All(step => step?["acts"] is null), Is.True);
            string[] history = [.. ComputerUseMission.HistoryForMind(steps, 1).Select(item => (string?)item?["label"] ?? (string?)item?["text"] ?? "")];
            Assert.That(history, Is.EqualTo(new[] { "Buscar o iniciar una conversación", "Cotele", "Cotele" }));
        });
    }

    // A burst the person cut short: the cause stays on the sub-act it did not take, so the mission stops for them.
    [Test]
    public void TheCauseOfAStopStaysOnTheSubActNotTaken()
    {
        var record = new JsonObject
        {
            ["step"] = 1,
            ["operation"] = "input.visible.click",
            ["label"] = "Buscar",
            ["search"] = "Cotele",
            ["ok"] = false,
            ["error"] = "input_user_interrupted",
            ["effectUncertain"] = true,
            ["acts"] = JsonNode.Parse("""
                [{"operation":"input.visible.click","label":"Buscar","ok":true,"surfaceChanged":true},
                 {"operation":"input.text.type","text":"Cotele","ok":true},
                 {"operation":"input.visible.click","label":"Cotele","ok":false,"error":"input_user_interrupted"}]
                """),
        };
        var steps = new JsonArray { record };

        JsonObject last = ComputerUseMission.ExpandSearchBurst(steps, record);

        Assert.Multiple(() =>
        {
            Assert.That(steps, Has.Count.EqualTo(3));
            Assert.That((bool?)steps[0]!["ok"], Is.True);
            Assert.That(steps[0]!["error"], Is.Null);
            Assert.That((string?)last["error"], Is.EqualTo("input_user_interrupted"));
            Assert.That(ComputerUseMission.PersonInputStops.Contains((string?)last["error"] ?? ""), Is.True);
        });
    }

    // Contracase: an ordinary click is left exactly as it was.
    [Test]
    public void AnOrdinaryStepIsLeftAsItWas()
    {
        var record = new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "Guardar", ["ok"] = true };
        var steps = new JsonArray { record };

        JsonObject last = ComputerUseMission.ExpandSearchBurst(steps, record);

        Assert.Multiple(() =>
        {
            Assert.That(last, Is.SameAs(record));
            Assert.That(steps, Has.Count.EqualTo(1));
        });
    }
}
