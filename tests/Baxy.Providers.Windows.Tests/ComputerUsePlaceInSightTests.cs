using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew al máximo (F019, E015): in every practice run the model told Steam's library «la página principal» or «la
/// tienda»: Steam's window is titled «Steam» on every page and its tab strip does not say which tab is chosen. A look at
/// a named application's window says which of its places is in sight when what it read is what only that place shows
/// (app_places.v1.json «shows»). Scripted worker answers; no window is read.
/// </summary>
[TestFixture]
public sealed class ComputerUsePlaceInSightTests
{
    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    // A handle no window has: nothing on the desktop is read or moved.
    private const long Front = 0x7FFF_0F3C;

    private static string Text(string name, string id) =>
        "{\"kind\":\"Text\",\"name\":\"" + name + "\",\"id\":\"" + id + "\",\"state\":\"\",\"value\":null,\"rect\":null,\"repeated\":0}";

    private static async Task<JsonElement> LookAsync(string application, params string[] names)
    {
        string answer = "{\"ok\":true,\"error\":\"\",\"hwnd\":" + Front + ",\"window\":\"Steam\",\"controls\":[" +
            string.Join(',', names.Select((name, index) => Text(name, "4." + index))) + "],\"controlCount\":" + names.Length +
            ",\"focused\":null}";
        var adapter = new WindowsVisibleControlAdapter(new ComputerUsePerceptionTests.ScriptedUiaWorker(answer), null, null,
            requestedWindow: (_, _) => ValueTask.FromResult((nint)Front),
            capture: (_, _, _) => ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null));
        ExternalCapabilityReceipt view = await adapter.InvokeAsync(
            "input.visible.controls", Json($$"""{"application":"{{application}}"}"""), CancellationToken.None);
        Assert.That(view.Verified, Is.True);
        return view.Result!.Value;
    }

    [Test]
    public async Task ALookAtTheLibrarySaysTheLibraryIsInSight()
    {
        JsonElement view = await LookAsync("Steam", "TIENDA", "BIBLIOTECA", "COMUNIDAD", "Página principal", "Novedades");

        JsonElement place = view.GetProperty("place");
        Assert.Multiple(() =>
        {
            Assert.That(place.GetProperty("application").GetString(), Is.EqualTo("Steam"));
            Assert.That(place.GetProperty("name").GetString(), Is.EqualTo("library"));
            Assert.That(place.GetProperty("shown").GetString(), Is.EqualTo("Página principal"));
        });
    }

    // Nothing only one place shows, the texts of two places, or an application whose data declare nothing shown: no
    // place is said.
    [TestCase("Steam", "TIENDA", "BIBLIOTECA", "COMUNIDAD", "Iniciar sesión")]
    [TestCase("Steam", "Página principal", "https://store.steampowered.com/")]
    [TestCase("Spotify", "Página principal")]
    public async Task ALookThatShowsNoSinglePlaceSaysNone(string application, params string[] names)
    {
        JsonElement view = await LookAsync(application, names);

        Assert.That(view.TryGetProperty("place", out _), Is.False);
    }
}
