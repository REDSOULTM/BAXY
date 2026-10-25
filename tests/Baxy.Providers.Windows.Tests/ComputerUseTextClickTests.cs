using System.Reflection;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.Infrastructure;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Práctica V5E029 («cambia la calculadora a modo científico y calcula 2 elevado a 10», 7 of 7 runs failed alike): the
/// model clicked the Text «Modo de calculadora Estándar» three times, each unchanged, and never «Abrir navegación» beside
/// it, which opens the list of modes. A click that changed nothing on a static text of the last look says, from the first
/// time, that it is a text and not a control, and names the controls nearest it; with the repeated click's own «next»
/// (and its application's places) both are said. Every effect goes to fakes: no window is touched.
/// </summary>
[TestFixture]
public sealed class ComputerUseTextClickTests
{
    private const nint Window = 4660;

    private const string Expected = "«Modo de calculadora Estándar» is a text the window shows, not a control: clicking it "
        + "changes nothing; the controls nearest it are [4] Button «Abrir navegación», [34] Button «Mantener visible», "
        + "[1] Button «Minimizar Calculadora»";

    // The Calculator's look of the runs, by its places: the mode's text beside the navigation button and «Mantener
    // visible», the title bar's buttons above on the right, the memory row under the display; the system menu has none.
    private static WindowsVisibleControlAdapter.ViewControl[] Calculator() =>
    [
        Control(0, "MenuItem", "Sistema", "collapsed", null),
        Control(1, "Button", "Minimizar Calculadora", "", new(200, 0, 46, 32)),
        Control(4, "Button", "Abrir navegación", "", new(0, 32, 40, 40)),
        Control(5, "Button", "Sumar memoria", "", new(0, 240, 60, 40)),
        Control(34, "Button", "Mantener visible", "", new(160, 32, 40, 40)),
        Control(38, "Text", "Se muestra 0", "focused", new(0, 100, 320, 80)),
        Control(46, "Text", "Modo de calculadora Estándar", "", new(48, 32, 100, 40)),
    ];

    [Test]
    public async Task AnUnchangedClickOnATextNamesTheControlsNearestIt()
    {
        ExternalCapabilityReceipt[] receipts = await ClicksAsync("Modo de calculadora Estándar", "Text", null, 1);

        Assert.Multiple(() =>
        {
            Assert.That(receipts[0].ErrorCode, Is.EqualTo("visible_button_postread_unchanged"));
            Assert.That(receipts[0].Result?.GetProperty("next").GetString(), Is.EqualTo(Expected));
            Assert.That(receipts[0].Result?.GetProperty("unchangedInARow").GetInt32(), Is.EqualTo(1),
                "the count goes with its «next», so the same call's comparisons leave both out");
        });
    }

    // Contracase: a Button that changed nothing keeps the receipt of today (nothing on the first, the count after).
    [Test]
    public async Task AnUnchangedClickOnAButtonKeepsTheReceiptOfToday()
    {
        ExternalCapabilityReceipt[] receipts = await ClicksAsync("Mantener visible", "Button", null, 2);

        Assert.Multiple(() =>
        {
            Assert.That(receipts[0].ErrorCode, Is.EqualTo("visible_button_postread_unchanged"));
            Assert.That(receipts[0].Result, Is.Null);
            Assert.That(receipts[1].Result?.GetProperty("next").GetString(),
                Is.EqualTo("this click on «Mantener visible» changed nothing 2 times in a row: each time the window "
                    + "looked the same after it as before it"));
        });
    }

    // The repeated click's «next» with its application's places (Steam) and the text's: both are said.
    [Test]
    public async Task ARepeatedClickOnATextKeepsTheRepeatAndThePlacesOfItsApplication()
    {
        ExternalCapabilityReceipt[] receipts = await ClicksAsync("Modo de calculadora Estándar", "Text", "Steam", 2);
        string? next = receipts[1].Result?.GetProperty("next").GetString();

        Assert.Multiple(() =>
        {
            Assert.That(receipts[1].Result?.GetProperty("unchangedInARow").GetInt32(), Is.EqualTo(2));
            Assert.That(next, Does.StartWith("this click on «Modo de calculadora Estándar» changed nothing 2 times in a row"));
            Assert.That(next, Does.Contain("app_open with appId \"Steam\" and place "));
            Assert.That(next, Does.EndWith("; " + Expected));
        });
    }

    // With the aids off the receipt is the one of today: nothing on the first click, only the count after it.
    [Test]
    public async Task WithTheAidsOffTheReceiptIsTheOneOfToday()
    {
        using IDisposable setting = ModelAids.Use("none");
        ExternalCapabilityReceipt[] receipts = await ClicksAsync("Modo de calculadora Estándar", "Text", null, 2);

        Assert.Multiple(() =>
        {
            Assert.That(receipts[0].Result, Is.Null);
            Assert.That(receipts[1].Result?.GetRawText(), Is.EqualTo("{\"unchangedInARow\":2}"));
        });
    }

    // A text the look gave no place names the window's collapsed entries; a text with a control's state (it toggles), a
    // label that names a button too, and a click by an index of another control are no text.
    [Test]
    public void OnlyAStaticTextIsSaidAndWithoutAPlaceItsWindowsCollapsedEntries()
    {
        WindowsVisibleControlAdapter.ViewControl[] placeless = Calculator();
        placeless[^1].RectValue = null;
        WindowsVisibleControlAdapter.ViewControl[] toggled = Calculator();
        toggled[^1].State = "off";
        WindowsVisibleControlAdapter.ViewControl[] twice =
            [.. Calculator(), Control(50, "Button", "Modo de calculadora Estándar", "", null)];
        JsonElement byLabel = Json("{\"label\":\"Modo de calculadora Estándar\"}");

        Assert.Multiple(() =>
        {
            Assert.That(WindowsVisibleControlAdapter.TextClickNext(placeless, "Modo de calculadora Estándar", byLabel),
                Does.EndWith("changes nothing; the window's collapsed entries are [0] MenuItem «Sistema» (collapsed)"));
            Assert.That(WindowsVisibleControlAdapter.TextClickNext(toggled, "Modo de calculadora Estándar", byLabel), Is.Null);
            Assert.That(WindowsVisibleControlAdapter.TextClickNext(twice, "Modo de calculadora Estándar", byLabel), Is.Null);
            Assert.That(WindowsVisibleControlAdapter.TextClickNext(Calculator(), "Modo de calculadora Estándar",
                Json("{\"label\":\"Modo de calculadora Estándar\",\"index\":4}")), Is.Null);
            Assert.That(WindowsVisibleControlAdapter.TextClickNext(Calculator(), "Estándar",
                Json("{\"label\":\"Estándar\",\"index\":46}")), Is.EqualTo(Expected));
        });
    }

    private static async Task<ExternalCapabilityReceipt[]> ClicksAsync(string label, string kind, string? application, int times)
    {
        string pending = "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_pending\","
            + "\"pending\":true,\"name\":\"" + label + "\",\"kind\":\"" + kind + "\",\"controlIdentity\":\"1.2.3\","
            + "\"absentOrDisabled\":false,\"selected\":false,\"toggled\":false}";
        string unchanged = "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_unchanged\","
            + "\"name\":\"" + label + "\",\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":false,\"selected\":false}";
        var worker = new CommandWorker(command => command switch
        {
            "click" => pending,
            "postread" => unchanged,
            _ => null,
        });
        ValueTask<VisibleControlSurface.CapturedWindow?> Capture(nint window, bool? selfDrawn, CancellationToken token) =>
            ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(
                new VisibleControlSurface.CapturedWindow(window, [], 0, 0, 10, 10, "same"));
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, capture: Capture);
        RememberView(adapter, application, Calculator());

        var receipts = new ExternalCapabilityReceipt[times];
        for (int i = 0; i < times; i++)
            receipts[i] = await adapter.InvokeAsync("input.visible.click",
                Json("{\"label\":\"" + label + "\",\"window\":" + (long)Window + "}"), CancellationToken.None);
        return receipts;
    }

    private static WindowsVisibleControlAdapter.ViewControl Control(
        int index, string kind, string name, string state, WindowsVisibleControlAdapter.Rect? rect) =>
        new() { Index = index, Id = "1." + index, Kind = kind, Name = name, State = state, RectValue = rect };

    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();

    // The last view, as input.visible.controls leaves it, with the application it named.
    private static void RememberView(
        WindowsVisibleControlAdapter adapter, string? application, IReadOnlyList<WindowsVisibleControlAdapter.ViewControl> controls)
    {
        FieldInfo field = typeof(WindowsVisibleControlAdapter).GetField(
            "_lastView", BindingFlags.NonPublic | BindingFlags.Instance)!;
        object view = Activator.CreateInstance(
            field.FieldType, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance, null,
            [Window, controls], null)!;
        field.FieldType.GetProperty("Application", BindingFlags.NonPublic | BindingFlags.Instance)!.SetValue(view, application);
        field.SetValue(adapter, view);
    }

    private sealed class CommandWorker(Func<string?, string?> answer) : IUiaWorker
    {
        public ValueTask PrewarmAsync(CancellationToken cancellationToken) => ValueTask.CompletedTask;

        public ValueTask<JsonDocument?> SendAsync(string commandJson, TimeSpan timeout, CancellationToken cancellationToken)
        {
            using JsonDocument command = JsonDocument.Parse(commandJson);
            string? text = answer(command.RootElement.TryGetProperty("cmd", out JsonElement name) ? name.GetString() : null);
            return ValueTask.FromResult(text is null ? null : JsonDocument.Parse(text));
        }
    }
}
