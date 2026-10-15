using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Estabilización L2 (límites leídos sobre el acto): a sub-goal the mind marked as a declared limit (steps[].limit) is
/// never tried, after the sub-goals before it, the safe part, are done; a step the mind stops on a limit while acting
/// («limit:long_list») is the mission's stop. The floor says each with what was done (tests/test_estab_l2_limites.py).
/// </summary>
public sealed partial class ComputerUseLoopTests
{
    private static JsonObject ExplorerIn(string folder) => Window(folder + " - Explorador de archivos", "explorer", 50, true,
        [Control(0, "ListItem", "baxy-prueba-v3"), Control(1, "ListItem", "notas.txt"), Control(2, "ListItem", "lista.txt")]);

    [Test]
    public async Task ADeclaredLimitIsNeverTriedAndTheSafePartBeforeItIsDone()
    {
        // t-menu-1: «en la carpeta baxy-prueba-v3 … haceme clic derecho en notas.txt y abrime las propiedades».
        var harness = new Harness
        {
            Screen = _ => ExplorerIn("Documentos"),
            Mind = request => request.Subgoal == 0
                ? Step("input.visible.click", new JsonObject { ["label"] = "baxy-prueba-v3" })
                : Step("input.visible.click", new JsonObject { ["label"] = "Propiedades" }),
        };
        var arguments = new JsonObject
        {
            ["goal"] = "en la carpeta baxy-prueba-v3 haceme clic derecho en notas.txt y abrime las propiedades",
            ["steps"] = new JsonArray
            {
                new JsonObject { ["goal"] = "ir a baxy-prueba-v3", ["application"] = "Explorador de archivos",
                    ["successCheck"] = "stepDone:input.visible.click:baxy-prueba-v3" },
                new JsonObject { ["goal"] = "abrir el menu contextual de notas.txt", ["application"] = "Explorador de archivos",
                    ["successCheck"] = null, ["limit"] = "context_menu" },
            },
        };
        Assert.That(MindPlanBoundary.ArgumentsSatisfyExactSchema(ComputerUseMission.OperationName, arguments), Is.True,
            "the catalog declares the mark");

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution((string)arguments["goal"]!, arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        JsonArray subgoals = observed["subgoals"]!.AsArray();
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.False);
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_limit_context_menu"));
            Assert.That((bool?)subgoals[0]!["reached"], Is.True, "the safe part was done");
            Assert.That((bool?)subgoals[1]!["reached"], Is.False);
            Assert.That(harness.Requests.Select(request => request.Subgoal), Is.All.EqualTo(0), "the limit is never asked");
            Assert.That(harness.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "input.visible.click" }));
        });
    }

    [Test]
    public async Task AMissionWhoseOneGoalIsALimitLooksAtNothingAndPressesNothing()
    {
        // t-form-3: «Insert a table with 4 columns and 3 rows in this Word document», marked as the format limit.
        var harness = new Harness
        {
            Screen = _ => Window("Documento1 - Word", "WINWORD", 70, true, [Control(0, "TabItem", "Insertar")]),
            Mind = _ => Step("input.visible.click", new JsonObject { ["label"] = "Insertar" }),
        };
        var arguments = new JsonObject
        {
            ["goal"] = "Insert a table with 4 columns and 3 rows in this Word document",
            ["application"] = "Word",
            ["steps"] = new JsonArray
            {
                new JsonObject { ["goal"] = "Insert a table with 4 columns and 3 rows in this Word document",
                    ["application"] = "Word", ["successCheck"] = null, ["limit"] = "format" },
            },
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution((string)arguments["goal"]!, arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_limit_format"));
            Assert.That(observed["subgoals"], Is.Null, "one marked goal is no chain: it keeps a single goal's budget");
            Assert.That(harness.Looks, Is.Empty);
            Assert.That(harness.Acts, Is.Empty);
            Assert.That(harness.Requests, Is.Empty);
        });
    }

    [Test]
    public async Task TheMindsStopOnALimitIsTheMissionsStop()
    {
        // t-scroll-1: the list did not end after the wheel scrolls the sub-goal may spend.
        var harness = new Harness
        {
            Screen = _ => SettingsAt("Aplicaciones instaladas"),
            Mind = _ => new MindComputerUseStep("none", new JsonObject(), "la lista no acaba", "limit:long_list"),
        };
        var arguments = new JsonObject
        {
            ["goal"] = "mostrar bloc de notas",
            ["application"] = "Configuración",
            ["successCheck"] = "control:=bloc de notas",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("bajá en la lista hasta el Bloc de notas", arguments), arguments,
            CancellationToken.None);

        Assert.That((string?)Observed(result)["stoppedBy"], Is.EqualTo("computer_use_limit_long_list"));
    }

    [Test]
    public void EveryLimitStopTheAppCanSayHasItsCauseInTheFloorData()
    {
        var causes = (JsonObject)OperationFloor.ComputerUseData["causes"]!;
        var kinds = (JsonObject)OperationFloor.ComputerUseData["limits"]!["kinds"]!;
        Assert.Multiple(() =>
        {
            foreach (string kind in kinds.Select(pair => pair.Key).Append("long_list").Append("device"))
            {
                Assert.That(causes[ComputerUseMission.LimitStop + kind], Is.Not.Null, kind);
            }
        });
    }
}
