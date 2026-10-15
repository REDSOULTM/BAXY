using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Pasada r15b B2: the surfaces of one application are read as one. v3-16: an image viewer's editor is a WebView2
/// window lying inside the viewer's window (201,252–1623,923 inside 192,192–1632,932, 89.5 % of it, under 90 %), and the
/// view read only the viewer's empty frame. v3-17: «Más opciones» opened the viewer's popup host, and the click was told
/// visible_button_postread_unchanged because the post-read compared only the window's own image. Pure rules and a
/// scripted worker: nothing on the desktop is touched.
/// </summary>
[TestFixture]
public sealed class ComputerUseSameAppSurfacesTests
{
    private static readonly (int, int, int, int) Viewer = (192, 192, 1632, 932);

    private const string PendingClick =
        "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_pending\"," +
        "\"pending\":true,\"name\":\"Más opciones\",\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":false," +
        "\"selected\":false,\"toggled\":false}";

    private const string UnchangedControl =
        "{\"version\":2,\"ok\":false,\"effectObserved\":true,\"error\":\"visible_button_postread_unchanged\"," +
        "\"name\":\"Más opciones\",\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":false,\"selected\":false}";

    private static JsonElement Json(string text) => JsonDocument.Parse(text).RootElement.Clone();

    private static ValueTask<VisibleControlSurface.CapturedWindow?> SameImage(nint window, bool? selfDrawn, CancellationToken token) =>
        ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(
            new VisibleControlSurface.CapturedWindow(window, [], 0, 0, 10, 10, "same"));

    [Test]
    public void TheEditorLyingInsideTheViewersWindowIsItsSurface()
    {
        VisibleControlSurface.FamilyWindow editor = new(13373098, 41664, 201, 252, 1623, 923, AboveFrame: true);
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.CoversAsSurface(Viewer, (201, 252, 1623, 923)), Is.True);
            Assert.That(VisibleControlSurface.ChooseFamilySurface(Viewer, [editor]), Is.EqualTo((nint)13373098));
            Assert.That(VisibleControlSurface.IsContentOf(Viewer, editor), Is.True);
        });
    }

    [Test]
    public void AWindowInsideThatFillsLittleOrOneThatOverflowsIsNoSurface()
    {
        Assert.Multiple(() =>
        {
            // A dialog of a helper over two thirds of the window (the measured counter-case of v3 point 1) stays out.
            Assert.That(VisibleControlSurface.CoversAsSurface((0, 0, 1938, 1038), (0, 0, 1938, 700)), Is.False);
            // A small popup inside the window is no content.
            Assert.That(VisibleControlSurface.CoversAsSurface(Viewer, (300, 300, 900, 700)), Is.False);
            // As large, but passing the window's border by more than a shadow: it does not lie inside it.
            Assert.That(VisibleControlSurface.CoversAsSurface(Viewer, (150, 252, 1590, 923)), Is.False);
            // A window of its own (a browser it started) inside the window is never its content.
            Assert.That(VisibleControlSurface.IsContentOf(Viewer,
                new VisibleControlSurface.FamilyWindow(80, 5, 201, 252, 1623, 923, AboveFrame: true, ApplicationWindow: true)), Is.False);
            // Under the window it is not what a person sees.
            Assert.That(VisibleControlSurface.ChooseFamilySurface(Viewer,
                [new VisibleControlSurface.FamilyWindow(81, 5, 201, 252, 1623, 923, AboveFrame: false)]), Is.EqualTo((nint)0));
        });
    }

    [Test]
    public void APopupIsTheWindowsOwnWhenOwnedByItOrLyingInsideIt()
    {
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.IsSurfaceOfFrame(Viewer, (1200, 230, 1500, 520), ownedByFrame: false), Is.True);
            // A menu's popup host may hang past the window's border: owned by it, it is its own.
            Assert.That(VisibleControlSurface.IsSurfaceOfFrame(Viewer, (1500, 230, 1800, 520), ownedByFrame: true), Is.True);
            // Counter-case: a window of the family elsewhere on the screen, owned by nobody, is not.
            Assert.That(VisibleControlSurface.IsSurfaceOfFrame(Viewer, (1500, 230, 1800, 520), ownedByFrame: false), Is.False);
            Assert.That(VisibleControlSurface.IsSurfaceOfFrame(Viewer, (0, 0, 0, 0), ownedByFrame: false), Is.False);
        });
    }

    [Test]
    public void APopupBornOfTheClickIsItsEffect()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WindowsVisibleControlAdapter.PopupBorn([], [777]), Is.True);
            Assert.That(WindowsVisibleControlAdapter.PopupBorn([777], [777]), Is.False, "it was there before the click");
            Assert.That(WindowsVisibleControlAdapter.PopupBorn([777], []), Is.False, "one that went away opened nothing");
        });
    }

    // v3-17: the window's own image stayed the same while the click opened its popup host.
    [Test]
    public async Task AClickThatOpenedItsWindowsPopupIsVerifiedThoughItsImageStayedTheSame()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(PendingClick, UnchangedControl);
        int asked = 0;
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, capture: SameImage)
        {
            PopupsOf = window => asked++ == 0 ? [] : [(nint)777],
        };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Más opciones","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("surfaceChanged").GetBoolean(), Is.True);
        });
    }

    // Counter-case: a popup that was already up before the click proves nothing; the click is still unchanged.
    [Test]
    public async Task APopupAlreadyUpBeforeTheClickProvesNothing()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(PendingClick, UnchangedControl);
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, capture: SameImage)
        {
            PopupsOf = window => [(nint)777],
        };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Más opciones","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_postread_unchanged"));
        });
    }

    // Review of fable/cu-v3-carga-preguntas, finding 1: the pointer's press waits for the person's pause first; a popup
    // of that application the person opened meanwhile (a menu of theirs) is not the press's effect. The list is taken
    // with the image, after the pause.
    private const string NeedsPointer =
        "{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_click_needs_pointer\"," +
        "\"name\":\"Más opciones\",\"kind\":\"Button\",\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":false," +
        "\"selected\":false,\"toggled\":false,\"surfaceChanged\":false,\"cascadeStage\":\"uia\",\"pending\":false," +
        "\"method\":\"pointer\",\"needsPointer\":true,\"point\":{\"x\":1300,\"y\":240}}";

    [Test]
    public async Task APopupThePersonOpenedWhileThePressWaitedForTheirPauseIsNotThePresssEffect()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NeedsPointer, UnchangedControl);
        var pointer = new PausingPointer();
        pointer.Paused = () => pointer.PopupUp = true;
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, pointer: pointer, capture: SameImage)
        {
            PopupsOf = window => pointer.PopupUp ? [(nint)777] : [],
            PointerRestsOn = window => false,
        };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Más opciones","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(pointer.Clicks, Is.EqualTo(1), "the point was pressed");
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_postread_unchanged"));
        });
    }

    // Twin: the same press whose popup is born of the press itself is verified by it.
    [Test]
    public async Task APopupBornOfThePointersPressIsItsEffect()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NeedsPointer, UnchangedControl);
        var pointer = new PausingPointer();
        pointer.Pressed = () => pointer.PopupUp = true;
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, pointer: pointer, capture: SameImage)
        {
            PopupsOf = window => pointer.PopupUp ? [(nint)777] : [],
            PointerRestsOn = window => false,
        };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Más opciones","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("popupBorn").GetBoolean(), Is.True);
        });
    }

    // Finding 2: a popup born while the person's pointer rests on the window may be the hover's (a tooltip, a link's
    // status bubble, drawn in a popup host like a menu's): it proves nothing, and the click stays unchanged.
    [Test]
    public async Task APopupBornUnderThePersonsRestingPointerProvesNothing()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(PendingClick, UnchangedControl);
        int asked = 0;
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, capture: SameImage)
        {
            PopupsOf = window => asked++ == 0 ? [] : [(nint)777],
            PointerRestsOn = window => true,
        };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Más opciones","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_postread_unchanged"));
        });
    }

    // Finding 2: before a born popup closes the post-read, the control is asked once more (review finding 7, as for an
    // image that changed): a selection it reports now is the receipt's.
    [Test]
    public async Task ABornPopupAsksTheControlOnceMoreFirst()
    {
        bool popupUp = false;
        var worker = new AnsweringWorker(command =>
            command.Contains("\"cmd\":\"click\"", StringComparison.Ordinal) ? PendingClick
            : popupUp ? UnchangedControl.Replace("\"ok\":false", "\"ok\":true").Replace(
                "\"error\":\"visible_button_postread_unchanged\"", "\"error\":\"\"").Replace(
                "\"selected\":false", "\"selected\":true")
            : UnchangedControl);
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, capture: SameImage)
        {
            PopupsOf = window =>
            {
                if (worker.Postreads >= 2)
                    popupUp = true;
                return popupUp ? [(nint)777] : [];
            },
            PointerRestsOn = window => false,
        };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Más opciones","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("selected").GetBoolean(), Is.True, "the control's own answer");
            Assert.That(receipt.Result?.TryGetProperty("popupBorn", out _), Is.False);
        });
    }

    private sealed class AnsweringWorker(Func<string, string> answer) : IUiaWorker
    {
        internal int Postreads { get; private set; }

        public ValueTask<JsonDocument?> SendAsync(string commandJson, TimeSpan timeout, CancellationToken cancellationToken)
        {
            if (commandJson.Contains("\"cmd\":\"postread\"", StringComparison.Ordinal))
                Postreads++;
            return ValueTask.FromResult<JsonDocument?>(JsonDocument.Parse(answer(commandJson)));
        }
    }

    // A pointer that waits for the person's pause (Paused runs then) and presses (Pressed runs then); the burst is
    // granted at once.
    private sealed class PausingPointer : IPointerFallback
    {
        internal bool PopupUp { get; set; }

        internal Action? Paused { get; set; }

        internal Action? Pressed { get; set; }

        internal int Clicks { get; private set; }

        public ValueTask<(bool Paused, long WaitedMs)> PauseAsync(CancellationToken cancellationToken)
        {
            Paused?.Invoke();
            return ValueTask.FromResult((true, 1200L));
        }

        public ValueTask<IInputBurst> AcquireAsync(nint window, CancellationToken cancellationToken) =>
            ValueTask.FromResult<IInputBurst>(new FakeInputBurst());

        public bool Prepare(nint window, int screenX, int screenY) => true;

        public ValueTask<VisibleControlSurface.CapturedWindow?> CaptureAsync(
            nint window, CancellationToken cancellationToken) =>
            ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(null);

        public bool Click(IInputBurst burst, int screenX, int screenY)
        {
            Clicks++;
            Pressed?.Invoke();
            return burst.MayAct;
        }
    }
}
