using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Encargo S de estabilización (banco B, fases e1 y e2, 2026-10-11): «andá a tu biblioteca» on a player whose library is
/// a panel. e1 y8: the first press on «Abre Tu biblioteca» opened it (its button became «Comprimir Tu biblioteca» two
/// looks later) and the check never said so, so the mission went on until it played a list. e2 u1: a stranger's list
/// «Tu biblioteca», opened from the search, titled the page while the library's own button still offered to open it, and
/// the final said it had arrived. The place's own button says whether it is open (ComputerUseSuccessCheck.PlaceToggle,
/// data «computerUse.placeToggle»). The views are the real ones, frozen (tests/data/estab_s_spotify_vistas.json).
/// </summary>
[TestFixture]
public sealed class ComputerUseEstabSTests
{
    private const string Library = "control:tu biblioteca:current|title:tu biblioteca|page:tu biblioteca|mark:tu biblioteca";

    private static JsonObject Frozen(string name)
    {
        var fixture = (JsonObject)JsonNode.Parse(File.ReadAllText(Path.Combine(
            FindRepositoryRoot(), "tests", "data", "estab_s_spotify_vistas.json")))!;
        return (JsonObject)fixture["views"]![name]!.DeepClone();
    }

    private static JsonObject Click(int step, string label, bool ok)
    {
        var click = new JsonObject { ["step"] = step, ["operation"] = "input.visible.click", ["ok"] = ok, ["label"] = label };
        if (!ok)
        {
            click["error"] = "visible_button_postread_unchanged";
            click["effectUncertain"] = true;
        }

        return click;
    }

    private static IEnumerable<TestCaseData> Examples()
    {
        var floor = (JsonObject)JsonNode.Parse(File.ReadAllText(Path.Combine(
            FindRepositoryRoot(), "src", "baxy_mind", "data", "operation_floor.v1.json")))!;
        foreach (JsonNode? example in (JsonArray)floor["computerUse"]!["placeToggle"]!["examples"]!)
        {
            yield return new TestCaseData(example!.ToJsonString()).SetName($"PlaceToggleExample({example["place"]}, {string.Join(" + ", ((JsonArray)example["buttons"]!).Select(button => (string?)button))})");
        }
    }

    // The datum's examples tie the App's reader to the mind's (tests/test_estab_s_spotify_lugares_sin_actos.py).
    [TestCaseSource(nameof(Examples))]
    public void ThePlaceToggleReadsTheExamplesOfItsDatum(string json)
    {
        var example = (JsonObject)JsonNode.Parse(json)!;
        var controls = new JsonArray();
        int index = 0;
        foreach (JsonNode? name in (JsonArray)example["buttons"]!)
        {
            controls.Add(new JsonObject { ["i"] = index++, ["kind"] = "Button", ["name"] = (string?)name });
        }

        bool? expected = example["open"] is JsonValue open ? (bool)open : null;
        Assert.That(ComputerUseSuccessCheck.PlaceToggle((string)example["place"]!, new JsonObject { ["controls"] = controls }),
            Is.EqualTo(expected));
    }

    // e1 y8: open by its own button, whichever step opened it (here the press held and a burst failed after it).
    [Test]
    public void ALibraryItsOwnButtonSaysIsOpenIsReached()
    {
        JsonArray steps =
        [
            Click(1, "Abre Tu biblioteca", ok: true),
            new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["ok"] = false, ["label"] = "Buscar",
                ["search"] = "tu biblioteca", ["searchBurst"] = true, ["error"] = "visible_search_focus_unproven" },
        ];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(Library, Frozen("e1_y8_abierta"), steps, out string? satisfiedBy), Is.True);
            Assert.That(satisfiedBy, Is.EqualTo("page:tu biblioteca"));
            Assert.That(ComputerUseSuccessCheck.Evaluate(Library, Frozen("e1_u1_tras_abrir"), [Click(1, "Abre Tu biblioteca", ok: true)], out _), Is.True);
        });
    }

    // e2 u1: the stranger's list titled the page («Tu biblioteca - playlist by ♡ | Spotify») and «Abre Tu biblioteca»
    // still offered to open the library: never reached, by any atom. Counter-case: the home page before any step.
    [Test]
    public void AStrangersListNamedLikeThePlaceIsNotThePlaceWhileItsButtonOffersToOpenIt()
    {
        JsonObject final = Frozen("e2_u1_final");
        JsonArray steps = [Click(1, "Abre Tu biblioteca", ok: false), Click(2, "Tu biblioteca", ok: true)];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.PlaceToggle("tu biblioteca", final), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Library, final, steps, out string? satisfiedBy), Is.False, satisfiedBy);
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:tu biblioteca", final, steps, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Library, Frozen("e2_u1_inicio"), [], out _), Is.False);
        });
    }

    // Counter-case: a place without a button of its own is judged as before (the page's title still says it).
    [Test]
    public void APlaceWithoutAButtonOfItsOwnIsJudgedAsBefore()
    {
        JsonObject search = Frozen("e2_x7_inicio");
        search["controls"]!.AsArray().Add(new JsonObject { ["i"] = 30, ["kind"] = "Document", ["name"] = "Spotify – Buscar" });
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.PlaceToggle("buscar", search), Is.Null);
            Assert.That(ComputerUseSuccessCheck.PlaceToggle("inicio", search), Is.Null);
        });
    }

    // S2 (banco f3 v8, 0/3: already on the home page, «Inicio» keeps no state and the page is titled by the track):
    // the home page is proved by the list only it shows (data app_places.v1.json «shows»), by its whole name.
    // The journal keeps 20 controls of a look; the list was the look's index 62 (the model's prompt of that look).
    [Test]
    public void TheHomePageIsProvedByWhatOnlyItShows()
    {
        JsonObject home = Frozen("f3_v8_inicio");
        const string Check = "control:==filtros de inicio|control:inicio:current|title:inicio|page:inicio";
        Assert.That(ComputerUseSuccessCheck.Evaluate(Check, home, [], out _), Is.False, "without the list");
        home["controls"]!.AsArray().Add(new JsonObject { ["i"] = 62, ["kind"] = "List", ["name"] = "Filtros de Inicio", ["zone"] = "T" });
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, home, [], out string? satisfiedBy), Is.True);
            Assert.That(satisfiedBy, Is.EqualTo("control:==filtros de inicio"));
        });
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
