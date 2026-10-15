using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 20 P5 (pasada r18): the final says the real cause. v3-27, a 4xx of the model server's grammar told as «en
/// este equipo»; v3-29, «no vi un control» when the search found nothing (v3-28's closed list withdrawn: revisión 1, hallazgo 3).
/// </summary>
[TestFixture]
public sealed class FinalRealCauseTests
{
    // The bounds the mind takes out of the wire copy of a schema above its ceiling (llm.GRAMMAR_REPETITION_CEILING,
    // llm._GRAMMAR_REPETITION_BOUNDS). llama.cpp writes them as repetitions and refuses any above 2 000.
    private const int GrammarRepetitionCeiling = 2000;
    private static readonly string[] StrippedBounds = ["maxLength", "minLength", "maxItems", "minItems"];
    private static readonly string[] RepetitionKeywords = ["maxLength", "minLength", "maxItems", "minItems", "maxProperties", "minProperties"];

    [Test]
    public void EveryRepetitionBoundOfTheRealCatalogAboveTheCeilingIsOneTheMindStrips()
    {
        var above = new List<string>();
        foreach (ProductOperationDescriptor descriptor in ProductCatalog.Descriptors)
        {
            Walk(JsonNode.Parse(descriptor.ArgumentsSchema.CanonicalJson), descriptor.Name, above);
        }

        Assert.That(above, Has.Some.EqualTo("clipboard.write.text/maxLength"), "the case v3-27 measured is in the catalog");
        Assert.That(above.Select(item => item[(item.LastIndexOf('/') + 1)..]), Is.SubsetOf(StrippedBounds));
    }

    private static void Walk(JsonNode? node, string path, List<string> above)
    {
        if (node is JsonArray array)
        {
            foreach (JsonNode? item in array)
            {
                Walk(item, path, above);
            }
        }
        else if (node is JsonObject obj)
        {
            foreach ((string key, JsonNode? value) in obj)
            {
                if (RepetitionKeywords.Contains(key) && value is JsonValue number
                    && number.TryGetValue(out long bound) && bound > GrammarRepetitionCeiling)
                {
                    above.Add($"{path}/{key}");
                }

                Walk(value, path, above);
            }
        }
    }

    [Test]
    public void APlanThatFailedInsideTheMindIsAnInternalFaultAndAContractRefusalStaysIncomplete()
    {
        Assert.That(MindSidecarClient.PlanFailureCause(null), Is.EqualTo("internal_fault"));
        Assert.That(
            MindSidecarClient.PlanFailureCause(new JsonObject
            {
                ["type"] = "error",
                ["code"] = "request_failed",
                ["message"] = "plan_runtime_failure",
            }),
            Is.EqualTo("internal_fault"));
        // Contracase: the planner's contract refused the plan (a semantic failure), still «plan_incomplete».
        Assert.That(
            MindSidecarClient.PlanFailureCause(new JsonObject
            {
                ["type"] = "error",
                ["code"] = "request_failed",
                ["message"] = "plan_contract_failure",
            }),
            Is.EqualTo("plan_incomplete"));
    }

    [Test]
    public void TheInternalFaultIsSaidWholeAndNeverAsALimitOfThisPc()
    {
        var situation = JsonNode.Parse(TurnVisibleFacts.Failure("internal_fault"))!.AsObject();
        string? spanish = OperationFloor.FailureSentence(situation, english: false);
        Assert.That(spanish, Is.Not.Null.And.Not.Empty);
        Assert.That(spanish, Does.Contain("no es un límite de este equipo"));
    }

    private static JsonObject Observed(string stoppedBy, params JsonObject[] steps) => new()
    {
        ["stoppedBy"] = stoppedBy,
        ["steps"] = new JsonArray(steps.Select(step => (JsonNode)step).ToArray()),
    };

    private static JsonObject ComputerUseData() => (JsonObject)JsonNode.Parse(FloorJson())!["computerUse"]!;

    private static string FloorJson()
    {
        string? directory = TestContext.CurrentContext.TestDirectory;
        while (directory is not null && !File.Exists(Path.Combine(directory, "src", "baxy_mind", "data", "operation_floor.v1.json")))
        {
            directory = Path.GetDirectoryName(directory);
        }

        Assert.That(directory, Is.Not.Null, "the repository's floor data");
        return File.ReadAllText(Path.Combine(directory!, "src", "baxy_mind", "data", "operation_floor.v1.json"));
    }

    [Test]
    public void AnEmptySearchIsTheStopsCauseAndAnOpenedListIsNot()
    {
        JsonObject data = ComputerUseData();
        // Revisión 1 de r20 P5, hallazgo 3 (v3-28, «elegí la fuente Wingdings» on a PC without it): every real «opened»
        // receipt carries surfaceChanged false and the list may still be open, so an opening is never said as closed.
        JsonObject opened = Observed(
            "computer_use_no_step_visible",
            new JsonObject { ["operation"] = "input.visible.click", ["ok"] = true, ["manner"] = "open", ["opened"] = true, ["surfaceChanged"] = false, ["method"] = "expand" },
            new JsonObject { ["operation"] = "input.visible.click", ["ok"] = false, ["error"] = "computer_use_no_progress" });
        Assert.That(OperationFloor.RefinedStop(opened, data), Is.Null);
        Assert.That(data["refinedStops"]!["lostOpening"], Is.Null);

        // v3-29 (compose_audit): Enter in the search, the window wrote «no hay caracteres disponibles».
        JsonObject searched = Observed(
            "computer_use_no_step_visible",
            new JsonObject { ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "copyright symbol" },
            new JsonObject { ["operation"] = "input.key.press", ["ok"] = true, ["key"] = "enter", ["appeared"] = new JsonArray("restablecer", "no hay caracteres disponibles") },
            new JsonObject { ["operation"] = "app.open", ["ok"] = true });
        Assert.That(OperationFloor.RefinedStop(searched, data), Is.EqualTo("emptySearch"));

        // Contracases: an opening the window kept, a new query typed after the empty one, a stop with its own cause.
        JsonObject kept = Observed(
            "computer_use_no_step_visible",
            new JsonObject { ["operation"] = "input.visible.click", ["ok"] = true, ["opened"] = true, ["surfaceChanged"] = true });
        Assert.That(OperationFloor.RefinedStop(kept, data), Is.Null);
        JsonObject retyped = Observed(
            "computer_use_no_step_visible",
            new JsonObject { ["operation"] = "input.key.press", ["ok"] = true, ["appeared"] = new JsonArray("sin resultados") },
            new JsonObject { ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "copyright" });
        Assert.That(OperationFloor.RefinedStop(retyped, data), Is.Null);
        JsonObject covered = Observed(
            "computer_use_window_covered",
            new JsonObject { ["operation"] = "input.visible.click", ["ok"] = true, ["opened"] = true, ["surfaceChanged"] = false });
        Assert.That(OperationFloor.RefinedStop(covered, data), Is.Null);

        // Hallazgo 4: a line with no search before it is a state of the window («No hay redes disponibles» on the Wi-Fi
        // click, «No se encontraron dispositivos» on «Agregar dispositivo»), and a click after the search left it.
        JsonObject networks = Observed(
            "computer_use_no_step_visible",
            new JsonObject { ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Wi-Fi", ["appeared"] = new JsonArray("No hay redes disponibles") });
        Assert.That(OperationFloor.RefinedStop(networks, data), Is.Null);
        JsonObject devices = Observed(
            "computer_use_surface_unchanged",
            new JsonObject { ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Agregar dispositivo", ["appeared"] = new JsonArray("No se encontraron dispositivos") });
        Assert.That(OperationFloor.RefinedStop(devices, data), Is.Null);
        JsonObject leftTheSearch = Observed(
            "computer_use_no_step_visible",
            new JsonObject { ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "bluetoth" },
            new JsonObject { ["operation"] = "input.key.press", ["ok"] = true, ["key"] = "enter", ["appeared"] = new JsonArray("No se encontraron resultados") },
            new JsonObject { ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Dispositivos", ["surfaceChanged"] = true, ["appeared"] = new JsonArray("Bluetooth") },
            new JsonObject { ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Bluetooth" });
        Assert.That(OperationFloor.RefinedStop(leftTheSearch, data), Is.Null);
        JsonObject typedOnly = Observed(
            "computer_use_no_step_visible",
            new JsonObject { ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "bluetoth", ["appeared"] = new JsonArray("No se encontraron resultados") });
        Assert.That(OperationFloor.RefinedStop(typedOnly, data), Is.EqualTo("emptySearch"));
    }
}
