using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Renew al máximo (7.3): two controls of one name (a «Buscar» in the menu and another in the content) or «the first
/// result» could not be told apart: the worker read each control's rectangle and the view dropped it. Each control of
/// the view now carries the coarse zone of the window its centre lies in (the same 3×3 grid as the view's text), from
/// the rectangle the worker read and the window's box it read with it. No rectangle, no box, or a centre outside the
/// box: no zone. Scripted worker answers and the worker's script; no window is read.
/// </summary>
[TestFixture]
public sealed class ComputerUseControlZoneTests
{
    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    // A handle no window has: nothing on the desktop is read or moved.
    private const long Front = 0x7FFF_0F3B;

    private static string Control(string name, string id, string rect) =>
        "{\"kind\":\"Button\",\"name\":\"" + name + "\",\"id\":\"" + id + "\",\"state\":\"\",\"value\":null,\"rect\":" + rect +
        ",\"repeated\":0}";

    private static string Answer(string box, params string[] controls) =>
        "{\"ok\":true,\"error\":\"\",\"hwnd\":" + Front + ",\"window\":\"Trabajo\"," + box + "\"controls\":[" +
        string.Join(',', controls) + "],\"controlCount\":" + controls.Length + ",\"focused\":null}";

    private static async Task<JsonElement[]> LookAsync(string answer)
    {
        var adapter = new WindowsVisibleControlAdapter(new ComputerUsePerceptionTests.ScriptedUiaWorker(answer), null, null,
            requestedWindow: (_, _) => ValueTask.FromResult((nint)Front),
            capture: (_, _, _) => ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null));
        ExternalCapabilityReceipt view = await adapter.InvokeAsync(
            "input.visible.controls", Json("""{"application":"el navegador"}"""), CancellationToken.None);
        Assert.That(view.Verified, Is.True);
        return [.. view.Result!.Value.GetProperty("controls").EnumerateArray()];
    }

    private static string? ZoneOf(JsonElement control) =>
        control.TryGetProperty("zone", out JsonElement zone) ? zone.GetString() : null;

    [Test]
    public async Task EachControlCarriesTheZoneOfTheWindowItsCentreLiesIn()
    {
        // The window's box at (100, 100), 600 × 300: thirds of 200 × 100.
        JsonElement[] controls = await LookAsync(Answer(
            "\"box\":{\"x\":100,\"y\":100,\"w\":600,\"h\":300},",
            Control("Buscar", "4.1", "{\"x\":110,\"y\":110,\"w\":60,\"h\":20}"),
            Control("Buscar", "4.2", "{\"x\":350,\"y\":230,\"w\":100,\"h\":40}"),
            Control("Primer resultado", "4.3", "{\"x\":120,\"y\":320,\"w\":100,\"h\":40}"),
            Control("Aceptar", "4.4", "{\"x\":600,\"y\":360,\"w\":80,\"h\":30}"),
            Control("Sin caja", "4.5", "null"),
            Control("Fuera", "4.6", "{\"x\":900,\"y\":120,\"w\":40,\"h\":20}")));

        Assert.That(controls.Select(ZoneOf), Is.EqualTo(new[] { "TL", "C", "BL", "BR", null, null }),
            "no rectangle, or a centre outside the window: no zone");
    }

    [Test]
    public async Task WithoutTheWindowsBoxNoControlHasAZone()
    {
        JsonElement[] controls = await LookAsync(Answer(
            string.Empty, Control("Buscar", "4.1", "{\"x\":110,\"y\":110,\"w\":60,\"h\":20}")));

        Assert.That(ZoneOf(controls[0]), Is.Null, "a zone is never guessed without the box it is relative to");
    }

    // The worker answers the view with the window's box it already reads (Get-WindowBox), in the same pixels as the
    // controls' rectangles.
    [Test]
    public void TheWorkersViewAnswersWithTheWindowsBox()
    {
        string worker = Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1");
        Assume.That(File.Exists(worker), "the worker script is copied next to the tests");
        string script = File.ReadAllText(worker);
        int start = script.IndexOf("function Do-View(", StringComparison.Ordinal);
        Assert.That(start, Is.GreaterThanOrEqualTo(0));
        int end = script.IndexOf("\nfunction ", start + 1, StringComparison.Ordinal);
        string view = script[start..end];
        string answer = view[view.LastIndexOf("return @{ ok=$true", StringComparison.Ordinal)..];

        Assert.Multiple(() =>
        {
            Assert.That(view, Does.Contain("$box=Get-WindowBox ([IntPtr][long]$target.hwnd)"));
            Assert.That(answer, Does.Contain("box=$box"));
        });
    }
}
