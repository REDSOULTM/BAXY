using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Estabilización, encargo C: a mission's sub-goal that goes to a place of the application whose data declare its address
/// opens it with app.open «place» (the mind's rule, tests/test_estab_c_lugares_por_direccion.py). The shell keeps what
/// the opening said, reads the arrival on the window, and never tells such a place as one the person was already in.
/// </summary>
[TestFixture]
public sealed class ComputerUsePlaceAddressTests
{
    private static JsonObject Look(params string[] lines) => new()
    {
        ["window"] = new JsonObject { ["title"] = "Steam", ["process"] = "steamwebhelper" },
        ["controls"] = new JsonArray(),
        ["text"] = new JsonObject { ["C"] = new JsonArray([.. lines.Select(line => (JsonNode?)line)]) },
    };

    private static JsonObject Opening(string? place, bool opened, bool alreadyRunning = true) => new()
    {
        ["step"] = 1,
        ["operation"] = "app.open",
        ["ok"] = true,
        ["appId"] = "Steam",
        ["alreadyRunning"] = alreadyRunning,
        ["place"] = place,
        ["placeOpened"] = opened,
    };

    // The view after the opening, with the application's own look right before it recorded for its step.
    private static JsonObject After(JsonObject before, params string[] lines)
    {
        JsonObject view = Look(lines);
        view["textBeforeClick"] = new JsonObject
        {
            ["1"] = new JsonArray([.. ComputerUseSuccessCheck.ShownLines(before).Select(line => (JsonNode?)line)]),
        };
        return view;
    }

    // Review H1: the arrival is the value born on the window after the place was opened, never the value anywhere.
    [Test]
    public void ThePlaceOpenedIsProvedByTheValueBornAfterItNeverByTheValueAlreadyShown()
    {
        const string Check = "opened:results=cuphead";
        JsonObject library = Look("BIBLIOTECA", "Cuphead", "Juegos y Software");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check,
                After(library, "TIENDA", "https://store.steampowered.com/search/?term=cuphead", "Cuphead", "Cuphead - The Delicious Last Course"),
                [Opening("results", opened: true)], out _), Is.True, "the results' lines are new");
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, After(library, "BIBLIOTECA", "Cuphead", "Juegos y Software"),
                [Opening("results", opened: true)], out _), Is.False, "the page did not move: «Cuphead» was already listed");
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, Look("TIENDA", "Cuphead"), [Opening("results", opened: true)], out _),
                Is.False, "no look of the application before the opening: nothing is proved");
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, After(library, "TIENDA", "Cuphead - Juego nuevo"),
                [Opening(null, opened: false)], out _), Is.False, "an opening of the application alone opened no place");
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, After(library, "TIENDA", "Cuphead - Juego nuevo"),
                [Opening("library", opened: true)], out _), Is.False, "another place opened is not the search");
        });
    }

    // What a field holds is the address's own echo (Spotify writes the query in its box): never a result.
    [Test]
    public void TheQueryInAFieldIsNoResult()
    {
        JsonObject home = Look("Inicio");
        JsonObject searched = After(home);
        searched["controls"] = new JsonArray(new JsonObject { ["kind"] = "ComboBox", ["name"] = "Buscar", ["value"] = "Cuphead" });
        Assert.That(ComputerUseSuccessCheck.Evaluate("opened:results=cuphead", searched, [Opening("results", opened: true)], out _),
            Is.False);
    }

    [Test]
    public void AnOpeningThatOpenedAPlaceActedAndMovedTheWindow()
    {
        JsonObject placed = Opening("library", opened: true);
        JsonObject bare = Opening(null, opened: false);
        var look = new JsonObject { ["step"] = 2, ["operation"] = "input.key.press", ["key"] = "escape", ["ok"] = true };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.MayHaveActed(placed), Is.True);
            Assert.That(ComputerUseMission.MayHaveActed(bare), Is.False);
            Assert.That(ComputerUseSuccessCheck.MissionMovedTheWindow([placed.DeepClone(), look.DeepClone()]), Is.True);
            Assert.That(ComputerUseSuccessCheck.MissionMovedTheWindow([bare.DeepClone(), look.DeepClone()]), Is.False);
        });
    }

    // The receipt's «placeOpened» is kept on the step, and the place and its opening reach the mind, whose rule opens a
    // place once per sub-goal.
    [Test]
    public void TheReceiptSaysThePlaceWasOpenedAndTheMindReadsIt()
    {
        var record = new JsonObject { ["step"] = 1, ["operation"] = "app.open", ["appId"] = "Steam", ["place"] = "library" };
        var response = new Baxy.Contracts.OperationResponse(
            Baxy.Contracts.ProtocolTypes.OperationResponse, "inv", "mission", "inv",
            Baxy.Contracts.OperationStatuses.Completed, "{}", true, false,
            System.Text.Json.JsonDocument.Parse("""{"appId":"Steam","alreadyRunning":true,"placeOpened":true}""").RootElement,
            null);

        ComputerUseMission.RecordResponse(record, response);
        JsonNode item = ComputerUseMission.HistoryForMind(new JsonArray(record), 0)[0]!;
        Assert.Multiple(() =>
        {
            Assert.That((bool?)record["placeOpened"], Is.True);
            Assert.That((string?)item["place"], Is.EqualTo("library"));
            Assert.That((bool?)item["placeOpened"], Is.True);
        });
    }

    // Estabilización G2: Settings' sections open by their address (ms-settings:display); the page's own header
    // («Sistema > Pantalla», measured on the notebook, banco e3 u8) proves the arrival once that opening brought the
    // window there, as a verified click does. The first look, and an opening of the application alone, prove nothing.
    [Test]
    public void ASettingsSectionOpenedByItsAddressArrivesByItsHeader()
    {
        var display = (JsonObject)JsonNode.Parse("""
            {"window": {"title": "Configuración", "process": "SystemSettings"}, "controls": [
              {"i": 0, "kind": "ListItem", "name": "Sistema", "state": "selected", "zone": "TL", "rect": {"x": 79, "y": 231, "w": 349, "h": 45}},
              {"i": 1, "kind": "Button", "name": "Sistema", "zone": "T", "rect": {"x": 464, "y": 65, "w": 178, "h": 54}},
              {"i": 2, "kind": "Button", "name": "Pantalla", "zone": "T", "rect": {"x": 643, "y": 69, "w": 126, "h": 47}},
              {"i": 3, "kind": "Slider", "name": "Brillo", "zone": "TR", "rect": {"x": 1026, "y": 196, "w": 225, "h": 41}},
              {"i": 4, "kind": "Text", "name": "Pantalla", "zone": "T", "rect": {"x": 643, "y": 69, "w": 126, "h": 47}}]}
            """)!;
        JsonObject Placed(string? place, bool opened) => new()
        {
            ["step"] = 1,
            ["operation"] = "app.open",
            ["ok"] = true,
            ["appId"] = "Configuración",
            ["alreadyRunning"] = true,
            ["place"] = place,
            ["placeOpened"] = opened,
        };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:pantalla", display, [Placed("display", opened: true)], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:pantalla", display, [], out _), Is.False,
                "the sub-goal's first look is not an arrival");
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:pantalla", display, [Placed(null, opened: false)], out _), Is.False,
                "an opening of the application alone brought the window nowhere");
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:sistema", display, [Placed("display", opened: true)], out _), Is.False,
                "the header's first item is not where the window is");
        });
    }

    // A place is the mission's own to open (its check reads the arrival): an opening outside a mission never carries one.
    [Test]
    public void AnOpeningOutsideAMissionCarriesNoPlace()
    {
        var extracted = new JsonObject { ["appId"] = "Steam", ["place"] = "library", ["placeValue"] = "x" };
        JsonObject normalized = MindArgumentNormalization.Normalize("app.open", "abrí Steam", extracted);
        Assert.Multiple(() =>
        {
            Assert.That(normalized.ContainsKey("place"), Is.False);
            Assert.That(normalized.ContainsKey("placeValue"), Is.False);
            Assert.That((string?)normalized["appId"], Is.EqualTo("Steam"));
        });
    }
}
