using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Estabilización, encargo C (banco f2c y10: «andá a la tienda y después a la biblioteca» in Steam fell 0/2): the
/// library opened by its address drew 4 s later, and the click rule pressed «BIBLIOTECA» on the first look after the
/// opening, still the store; the failed click then took the mark's proof away. A place just opened by its address is
/// looked at again while the window is as it was before the opening, before any act.
/// </summary>
public sealed partial class ComputerUseLoopTests
{
    [Test]
    public async Task APlaceOpenedByItsAddressIsLookedAtAgainUntilItDrawsBeforeAnyAct()
    {
        bool opened = false;
        int looksAfter = 0;
        JsonObject Store() => Window("Steam", "steamwebhelper", 12, true, [Control(0, "Document", "Steam")],
            "TIENDA", "BIBLIOTECA", "https://store.steampowered.com/", "Destacados");
        JsonObject Library() => Window("Steam - Biblioteca", "steamwebhelper", 12, true, [Control(0, "Document", "Steam")],
            "TIENDA", "BIBLIOTECA", "Pagina principal", "Juegos y Software");
        var harness = new Harness
        {
            // The store stays on screen for three looks after the address, then the library is drawn.
            Screen = _ => !opened ? Store() : looksAfter++ < 3 ? Store() : Library(),
            Mind = request => opened
                ? Step("input.visible.click", new JsonObject { ["label"] = "Biblioteca" })
                : Step("app.open", new JsonObject { ["appId"] = "Steam", ["place"] = "library" }),
        };
        harness.Receipt = (operation, _) =>
        {
            opened |= operation == "app.open";
            return operation == "app.open"
                ? new JsonObject { ["processId"] = 12, ["name"] = "Steam", ["alreadyRunning"] = true, ["placeOpened"] = true }
                : new JsonObject { ["surfaceChanged"] = true };
        };
        var arguments = new JsonObject { ["goal"] = "ir a biblioteca", ["application"] = "Steam", ["successCheck"] = "title:biblioteca" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en Steam andá a la biblioteca", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True, (string?)observed["stoppedBy"]);
            Assert.That(harness.Acts.Select(act => act.Operation), Is.EqualTo(new[] { "app.open" }),
                "nothing is clicked while the place opened by its address is still being drawn");
            Assert.That(harness.Delays.Count(delay => delay == ComputerUseMission.PageLookInterval), Is.InRange(1, ComputerUseMission.PageLooks));
        });
    }
}
