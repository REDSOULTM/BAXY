using System.Reflection;
using System.Runtime.InteropServices;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso real 03-11 (encargo 54): an entry of a launcher's library (a Chromium/CEF window) was pressed, its page opened,
/// and the click came back input_user_interrupted twice: its window's image changed, and the person's pointer had been
/// over the window meanwhile, so the image proved nothing. A pointer that only passes over a window (no button, no wheel,
/// no key) redraws it but presses nothing: it cannot rename the window nor take what it showed out of its tree. Then the
/// tree read again (and once more while it settles) proves the click by what is gone from the last look or by the
/// window's new name; an input of the person that reached the window, a view after that only gained something (a hover
/// card), or one whose only loss is a single text (a label that updates itself), leaves the click uncertain as before. Every effect goes to fakes: the window is an off-screen one of this test.
/// </summary>
[TestFixture]
public sealed class ComputerUsePointerPassedClickTests
{
    private const string Pending =
        "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_pending\"," +
        "\"pending\":true,\"name\":\"Isla Norte\",\"kind\":\"Text\",\"method\":\"render\"," +
        "\"controlIdentity\":\"1.21\",\"absentOrDisabled\":false,\"selected\":false,\"toggled\":false}";

    private const string Unchanged =
        "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_unchanged\"," +
        "\"name\":\"Isla Norte\",\"controlIdentity\":\"1.21\",\"absentOrDisabled\":false}";

    private static string Control(string kind, string name, string id) =>
        "{\"kind\":\"" + kind + "\",\"name\":\"" + name + "\",\"id\":\"" + id + "\",\"state\":\"\",\"value\":null}";

    private static string View(string title, params string[] controls) =>
        "{\"ok\":true,\"error\":\"\",\"window\":\"" + title + "\",\"controls\":[" + string.Join(',', controls) +
        "],\"controlCount\":" + controls.Length + ",\"partial\":false}";

    // The library: its list (kept when an entry opens), and the home pane the entry's page replaces.
    private static readonly string[] Library =
    [
        Control("Text", "Isla Norte", "1.21"),
        Control("Text", "Valle Gris", "1.22"),
        Control("Text", "Inicio", "1.30"),
        Control("Text", "Elige una entrada.", "1.31"),
    ];

    private static readonly string PageOpened = View("Estante",
        Control("Text", "Isla Norte", "1.21"),
        Control("Text", "Valle Gris", "1.22"),
        Control("Text", "Cargando...", "1.40"));

    // A hover card over the list: the same view with one more control.
    private static readonly string HoverCard = View("Estante", [.. Library, Control("Text", "Jugado hace 2 horas", "1.50")]);

    [TestCase("PointerPassed", "page", null, TestName = "pointer passed, the home pane gone: verified")]
    [TestCase("PointerPassed", "renamed", null, TestName = "pointer passed, the window renamed: verified")]
    [TestCase("PointerPassed", "settling", null, TestName = "pointer passed, the page seen on the second read: verified")]
    [TestCase("PointerPassed", "hover", "input_user_interrupted", TestName = "pointer passed, only a card appeared: uncertain")]
    [TestCase("PointerPassed", "label", "input_user_interrupted", TestName = "pointer passed, one label updated itself: uncertain")]
    [TestCase("Reached", "page", "input_user_interrupted", TestName = "the person's input reached it: uncertain")]
    [TestCase("None", "page", null, TestName = "untouched: verified by its image as before")]
    public void AClickWhoseImageChangedUnderAPassingPointerIsProvedByWhatLeftItsTree(
        string touched, string after, string? error)
    {
        PersonTouch touch = Enum.Parse<PersonTouch>(touched);
        WithWindow(window =>
        {
            int views = 0;
            string ViewNow() => after switch
            {
                "page" => PageOpened,
                "renamed" => ComputerUsePointerPassedClickTests.View("Isla Norte", [.. Library]),
                "label" => ComputerUsePointerPassedClickTests.View("Estante",
                    [.. Library.Take(3), Control("Text", "Elige una entrada (2)", "1.32")]),
                "settling" => views++ == 0 ? ComputerUsePointerPassedClickTests.View("Estante", [.. Library]) : PageOpened,
                _ => HoverCard,
            };
            var worker = new CommandWorker(command => command switch
            {
                "click" => Pending,
                "postread" => Unchanged,
                "view" => ViewNow(),
                _ => null,
            });
            int captures = 0;
            // The three images before the click are the same; every one after it differs from them.
            ValueTask<VisibleControlSurface.CapturedWindow?> Capture(nint hwnd, bool? selfDrawn, CancellationToken token) =>
                ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(
                    new VisibleControlSurface.CapturedWindow(hwnd, [], 0, 0, 10, 10, captures++ < 3 ? "before" : "after"));
            var adapter = new WindowsVisibleControlAdapter(worker, null, null, elevated: _ => false, capture: Capture)
            {
                ReadsAfterAct = true,
                PopupsOf = _ => [],
                PersonTouchOf = (_, _) => touch,
            };
            RememberView(adapter, window, "Estante",
                ("1.21", "Text", "Isla Norte"), ("1.22", "Text", "Valle Gris"), ("1.30", "Text", "Inicio"),
                ("1.31", "Text", "Elige una entrada."));

            ExternalCapabilityReceipt receipt = adapter.InvokeAsync(
                    "input.visible.click",
                    JsonDocument.Parse("{\"label\":\"Isla Norte\",\"controlId\":\"1.21\",\"window\":" + (long)window + "}")
                        .RootElement,
                    CancellationToken.None)
                .AsTask().GetAwaiter().GetResult();

            Assert.Multiple(() =>
            {
                Assert.That(receipt.ErrorCode, Is.EqualTo(error));
                Assert.That(receipt.Verified, Is.EqualTo(error is null));
                if (error is null)
                {
                    JsonElement result = receipt.Result!.Value;
                    Assert.That(result.GetProperty("surfaceChanged").GetBoolean(), Is.True);
                    Assert.That(result.TryGetProperty("after", out JsonElement read), Is.True, "the view after it is told");
                    if (touch == PersonTouch.PointerPassed)
                    {
                        Assert.That(result.GetProperty("pointerOver").GetBoolean(), Is.True,
                            "the receipt says the person's pointer was over the window");
                        Assert.That(read.TryGetProperty("gone", out _) || read.TryGetProperty("title", out _), Is.True,
                            "what proved it: something gone or the window's new name");
                    }
                }
                else
                {
                    Assert.That(receipt.EffectMayHaveOccurred, Is.True, "the click may have acted: never «not pressed»");
                }
            });
        });
    }

    // An off-screen window of this test that takes no activation: alive for the adapter, never the person's.
    private static void WithWindow(Action<nint> test)
    {
        nint window = PumpedWindow.Create("BAXY pointer fixture");
        Assert.That(window, Is.Not.EqualTo(nint.Zero));
        try
        {
            test(window);
        }
        finally
        {
            PumpedWindow.Destroy(window);
        }
    }

    // The last view, as input.visible.controls leaves it, with the window's name in its tree.
    private static void RememberView(
        WindowsVisibleControlAdapter adapter, nint window, string title, params (string Id, string Kind, string Name)[] specs)
    {
        FieldInfo field = typeof(WindowsVisibleControlAdapter).GetField(
            "_lastView", BindingFlags.NonPublic | BindingFlags.Instance)!;
        List<WindowsVisibleControlAdapter.ViewControl> controls = [.. specs.Select((spec, index) =>
            new WindowsVisibleControlAdapter.ViewControl
            {
                Index = index, Id = spec.Id, Kind = spec.Kind, Name = spec.Name, State = string.Empty,
            })];
        object view = Activator.CreateInstance(
            field.FieldType, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance, null,
            [window, controls], null)!;
        field.FieldType.GetProperty("TreeTitle", BindingFlags.NonPublic | BindingFlags.Instance)!.SetValue(view, title);
        field.SetValue(adapter, view);
    }

    // A worker that answers by the command's «cmd».
    private sealed class CommandWorker(Func<string?, string?> answer) : IUiaWorker
    {
        public ValueTask<JsonDocument?> SendAsync(string commandJson, TimeSpan timeout, CancellationToken cancellationToken)
        {
            using JsonDocument command = JsonDocument.Parse(commandJson);
            string? text = answer(command.RootElement.TryGetProperty("cmd", out JsonElement name)
                ? name.GetString()
                : null);
            return ValueTask.FromResult(text is null ? null : JsonDocument.Parse(text));
        }
    }

}
